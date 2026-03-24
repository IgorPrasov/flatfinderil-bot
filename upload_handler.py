"""
Bulk CSV/XLSX upload for agents.
All columns are required — file is rejected if any cell is empty.
"""

import csv
import io
import os
import datetime
import logging

logger = logging.getLogger(__name__)

try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

import database as db

# ── Required columns ─────────────────────────────────────────────────────────
REQUIRED_COLUMNS = [
    "deal_type",        # rent | buy | sublet | commercial
    "property_type",    # apartment | house | room | studio | duplex | penthouse | villa | townhouse
    "district",         # tel_aviv | jerusalem | haifa | sharon | center | south
    "city",
    "neighborhood",
    "address",
    "rooms",
    "floor",
    "area_sqm",
    "price",
    "parking",          # 0 | 1 | 2
    "pool",             # yes | no
    "shelter",          # yes | no
    "elevator",         # yes | no
    "infrastructure",   # comma-sep: mall,school,park,gym,hospital,beach,transport,restaurant,synagogue,kindergarten
    "description",
    "owner_name",
    "owner_phone",
    "contact",
]

VALID_DEAL_TYPES = {"rent", "buy", "sublet", "commercial"}
VALID_PROP_TYPES = {
    "apartment","house","room","studio","duplex","penthouse","villa","townhouse",
    "office","retail","warehouse","coworking","restaurant_space","other_commercial",
}
VALID_DISTRICTS  = {"tel_aviv","jerusalem","haifa","sharon","center","south"}
VALID_INFRA      = {
    "mall","school","park","gym","hospital","beach","transport",
    "restaurant","synagogue","kindergarten",
}
BOOL_YES = {"yes","да","true","1","כן"}

TEMPLATE_ROW = {
    "deal_type":      "rent",
    "property_type":  "apartment",
    "district":       "tel_aviv",
    "city":           "Тель-Авив",
    "neighborhood":   "Центр",
    "address":        "ул. Дизенгоф 1",
    "rooms":          "3",
    "floor":          "4",
    "area_sqm":       "75",
    "price":          "5000",
    "parking":        "1",
    "pool":           "no",
    "shelter":        "yes",
    "elevator":       "yes",
    "infrastructure": "mall,park,transport",
    "description":    "Светлая квартира в центре города",
    "owner_name":     "Имя Агента",
    "owner_phone":    "0501234567",
    "contact":        "@agent_tg",
}

COLUMN_HINTS = (
    "deal_type: rent | buy | sublet | commercial\n"
    "property_type: apartment | house | room | studio | duplex | penthouse | villa | townhouse\n"
    "district: tel_aviv | jerusalem | haifa | sharon | center | south\n"
    "parking: 0 | 1 | 2\n"
    "pool / shelter / elevator: yes | no\n"
    "infrastructure: mall, school, park, gym, hospital, beach, transport, restaurant, synagogue, kindergarten\n"
)


def generate_template_bytes() -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=REQUIRED_COLUMNS)
    w.writeheader()
    w.writerow(TEMPLATE_ROW)
    return buf.getvalue().encode("utf-8-sig")


def _read_csv(data: bytes) -> list:
    text = data.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _read_xlsx(data: bytes) -> list:
    if not _HAS_OPENPYXL:
        raise ImportError("openpyxl not installed")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [
        {headers[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(row)}
        for row in rows[1:]
    ]


def validate_and_import(data: bytes, filename: str, seller_user_id: int) -> dict:
    """
    Returns:
      {"ok": True,  "imported": N, "ids": [...]}
      {"ok": False, "errors": [...]}
    """
    # Parse
    try:
        rows = _read_xlsx(data) if filename.lower().endswith(".xlsx") else _read_csv(data)
    except ImportError:
        return {"ok": False, "errors": ["openpyxl не установлен на сервере. Загрузите CSV файл."]}
    except Exception as e:
        return {"ok": False, "errors": [f"Ошибка чтения файла: {e}"]}

    if not rows:
        return {"ok": False, "errors": ["Файл пустой — нет строк с данными."]}

    # Check headers
    actual = set(rows[0].keys())
    missing = [c for c in REQUIRED_COLUMNS if c not in actual]
    if missing:
        return {"ok": False, "errors": [
            f"❌ Отсутствуют колонки ({len(missing)} шт.):\n" + ", ".join(missing),
            "Скачайте шаблон: нажмите «📄 Скачать шаблон»",
        ]}

    errors = []
    listings = []

    for i, row in enumerate(rows, start=2):
        row_err = []

        # All columns must be non-empty
        empty = [c for c in REQUIRED_COLUMNS if not str(row.get(c, "")).strip()]
        if empty:
            errors.append(f"Строка {i}: пустые колонки — {', '.join(empty)}")
            continue

        deal_type = row["deal_type"].strip().lower()
        if deal_type not in VALID_DEAL_TYPES:
            row_err.append(f"deal_type «{deal_type}» — допустимо: {', '.join(sorted(VALID_DEAL_TYPES))}")

        prop_type = row["property_type"].strip().lower()
        if prop_type not in VALID_PROP_TYPES:
            row_err.append(f"property_type «{prop_type}» неверный")

        district = row["district"].strip().lower()
        if district not in VALID_DISTRICTS:
            row_err.append(f"district «{district}» — допустимо: {', '.join(sorted(VALID_DISTRICTS))}")

        try:
            rooms = float(row["rooms"].strip())
        except ValueError:
            row_err.append("rooms должно быть числом"); rooms = 0

        try:
            floor = int(row["floor"].strip())
        except ValueError:
            row_err.append("floor должно быть числом"); floor = 0

        try:
            area_sqm = float(row["area_sqm"].strip())
        except ValueError:
            row_err.append("area_sqm должно быть числом"); area_sqm = 0

        try:
            price = int(float(row["price"].strip()))
        except ValueError:
            row_err.append("price должно быть числом"); price = 0

        try:
            parking = int(row["parking"].strip())
            if parking not in (0, 1, 2):
                row_err.append("parking: 0, 1 или 2")
        except ValueError:
            row_err.append("parking: 0, 1 или 2"); parking = 0

        pool     = row["pool"].strip().lower() in BOOL_YES
        shelter  = row["shelter"].strip().lower() in BOOL_YES
        elevator = row["elevator"].strip().lower() in BOOL_YES
        infra    = [x.strip() for x in row["infrastructure"].split(",") if x.strip().lower() in VALID_INFRA]

        if row_err:
            errors.append(f"Строка {i}: " + "; ".join(row_err))
            continue

        city = row["city"].strip()
        listings.append({
            "seller_type":    "agent",
            "deal_type":      deal_type,
            "property_type":  prop_type,
            "district":       district,
            "city":           city,
            "neighborhood":   row["neighborhood"].strip(),
            "address":        row["address"].strip(),
            "rooms":          rooms,
            "floor":          floor,
            "area_sqm":       area_sqm,
            "price":          price,
            "parking":        parking,
            "pool":           pool,
            "shelter":        shelter,
            "elevator":       elevator,
            "infrastructure": infra,
            "description":    row["description"].strip(),
            "owner_name":     row["owner_name"].strip(),
            "owner_phone":    row["owner_phone"].strip(),
            "contact":        row["contact"].strip(),
            "title":          f"{city}, {rooms} комн.",
            "photos":         [],
            "active":         True,
            "date_added":     datetime.date.today().isoformat(),
            "user_id":        seller_user_id,
            "source":         "csv_upload",
            "views":          0,
            "view_requests":  0,
        })

    if errors:
        return {"ok": False, "errors": errors}

    imported_ids = []
    for listing in listings:
        lid = db.add_listing(listing)
        db.add_user_listing(seller_user_id, lid)
        imported_ids.append(lid)

    return {"ok": True, "imported": len(imported_ids), "ids": imported_ids}
