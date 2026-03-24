"""
Bulk listing upload via CSV or XLSX file.
Accepts a file sent to the bot, parses rows, and creates listings in the DB.

Required columns (case-insensitive):
  deal_type, property_type, city, price

Optional columns:
  address, neighborhood, district, rooms, floor, area_sqm,
  parking, pool, shelter, elevator, description,
  contact, owner_name, owner_phone, infrastructure

deal_type values : rent | buy | sublet | commercial
property_type    : apartment | house | villa | penthouse | studio | duplex | office | retail | warehouse | land
parking          : 0 / 1 / 2  (number of spaces)
pool/shelter/elevator : yes / no / 1 / 0 / true / false
infrastructure   : comma-separated keys  e.g.  mall,school,park
"""
import csv
import io
import os
import urllib.parse
from datetime import datetime

import database as db
from keyboards import DISTRICT_CITIES

# ── City → district lookup (reverse of DISTRICT_CITIES) ─────────────────────
_CITY_TO_DISTRICT: dict[str, str] = {}
for _dist, _cities in DISTRICT_CITIES.items():
    for _c in _cities:
        _CITY_TO_DISTRICT[_c.lower()] = _dist


def _city_to_district(city: str) -> str:
    return _CITY_TO_DISTRICT.get(city.lower().strip(), "tel_aviv")


def _bool_field(val: str) -> bool:
    return str(val).strip().lower() in ("yes", "1", "true", "да", "כן")


def _int_field(val: str, default: int = 0) -> int:
    try:
        return int(str(val).strip())
    except Exception:
        return default


def _float_field(val: str, default: float = 0.0) -> float:
    try:
        return float(str(val).strip().replace(",", "."))
    except Exception:
        return default


# Valid values
VALID_DEAL_TYPES = {"rent", "buy", "sublet", "commercial"}
VALID_PROPERTY_TYPES = {
    "apartment", "house", "villa", "penthouse", "studio", "duplex",
    "office", "retail", "warehouse", "land",
}
VALID_INFRA = {
    "kindergarten", "school", "mall", "park", "gym",
    "hospital", "beach", "transport", "restaurant", "synagogue",
}


def parse_csv_bytes(raw: bytes) -> tuple[list[dict], list[str]]:
    """Parse CSV bytes. Returns (rows_as_dicts, errors)."""
    try:
        text = raw.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    # Normalize column names to lowercase stripped
    rows = []
    for row in reader:
        rows.append({k.lower().strip(): v.strip() for k, v in row.items()})
    return rows, []


def parse_xlsx_bytes(raw: bytes) -> tuple[list[dict], list[str]]:
    """Parse XLSX bytes. Returns (rows_as_dicts, errors)."""
    try:
        import openpyxl
    except ImportError:
        return [], ["openpyxl not installed — XLSX support unavailable"]

    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    rows_raw = list(ws.values)
    if not rows_raw:
        return [], ["Empty file"]

    headers = [str(h).lower().strip() if h else "" for h in rows_raw[0]]
    rows = []
    for row in rows_raw[1:]:
        d = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            d[h] = str(val).strip() if val is not None else ""
        rows.append(d)
    return rows, []


def row_to_listing(row: dict, row_num: int, user_id: int) -> tuple[dict | None, str | None]:
    """Convert a CSV/XLSX row dict to a listing dict ready for db.add_listing().
    Returns (listing_dict, error_string) — one of them is None."""

    # Required fields
    deal_type = row.get("deal_type", "").strip().lower()
    if deal_type not in VALID_DEAL_TYPES:
        return None, f"Строка {row_num}: неверный deal_type '{deal_type}'"

    property_type = row.get("property_type", "").strip().lower()
    if property_type not in VALID_PROPERTY_TYPES:
        return None, f"Строка {row_num}: неверный property_type '{property_type}'"

    city = row.get("city", "").strip()
    if not city:
        return None, f"Строка {row_num}: пустое поле city"

    price = _int_field(row.get("price", "0"))

    # Optional fields
    address = row.get("address", "").strip()
    neighborhood = row.get("neighborhood", "").strip()
    district = row.get("district", "").strip() or _city_to_district(city)
    rooms = row.get("rooms", "").strip() or "0"
    floor = row.get("floor", "").strip() or "0"
    area_sqm = _int_field(row.get("area_sqm", row.get("area", "0")))
    parking = _int_field(row.get("parking", "0"))
    pool = _bool_field(row.get("pool", "0"))
    shelter = _bool_field(row.get("shelter", "0"))
    elevator = "yes" if _bool_field(row.get("elevator", "0")) else "no"
    description = row.get("description", "").strip() or "—"
    contact = row.get("contact", "").strip()
    owner_name = row.get("owner_name", row.get("name", "")).strip()
    owner_phone = row.get("owner_phone", row.get("phone", "")).strip()

    # Infrastructure
    infra_raw = row.get("infrastructure", "").strip()
    infrastructure = [k.strip() for k in infra_raw.split(",") if k.strip() in VALID_INFRA] if infra_raw else []

    # Build map URL if address provided
    map_url = ""
    if address:
        q = urllib.parse.quote(f"{address}, {city}, Israel")
        map_url = f"https://maps.google.com/?q={q}"

    # Build title
    deal_ru = {"rent": "Аренда", "buy": "Продажа", "sublet": "Субаренда", "commercial": "Коммерция"}
    title = f"{deal_ru.get(deal_type, deal_type)}: {rooms} комн., {city}"

    # Geocode city
    lat, lng = None, None
    try:
        from geocoding import get_city_coords
        coords = get_city_coords(city)
        if coords:
            lat, lng = coords
    except Exception:
        pass

    listing = {
        "title": title,
        "deal_type": deal_type,
        "property_type": property_type,
        "city": city,
        "district": district,
        "neighborhood": neighborhood,
        "address": address,
        "map_url": map_url,
        "rooms": rooms,
        "floor": floor,
        "area_sqm": area_sqm,
        "price": price,
        "parking": parking,
        "pool": pool,
        "shelter": shelter,
        "elevator": elevator,
        "infrastructure": infrastructure,
        "description": description,
        "contact": contact,
        "owner_name": owner_name,
        "owner_phone": owner_phone,
        "photos": ["🏠"],
        "user_id": user_id,
        "source": "upload",
        "date_added": datetime.now().strftime("%Y-%m-%d"),
        "active": True,
        "views": 0,
        "view_requests": 0,
    }
    if lat:
        listing["lat"] = lat
        listing["lng"] = lng

    return listing, None


def process_upload(raw: bytes, filename: str, user_id: int) -> dict:
    """
    Parse file and import listings.
    Returns {
      "ok": int,    # imported count
      "errors": list[str],
      "total": int,
    }
    """
    fn_lower = filename.lower()
    if fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls"):
        rows, parse_errors = parse_xlsx_bytes(raw)
    elif fn_lower.endswith(".csv"):
        rows, parse_errors = parse_csv_bytes(raw)
    else:
        return {"ok": 0, "errors": ["Поддерживаются только .csv и .xlsx файлы"], "total": 0}

    if parse_errors:
        return {"ok": 0, "errors": parse_errors, "total": 0}

    errors = []
    ok = 0
    for i, row in enumerate(rows, start=2):  # row 1 = header
        if not any(row.values()):
            continue  # skip empty rows
        listing, err = row_to_listing(row, i, user_id)
        if err:
            errors.append(err)
            continue
        try:
            db.add_listing(listing)
            ok += 1
        except Exception as e:
            errors.append(f"Строка {i}: DB error — {e}")

    return {"ok": ok, "errors": errors, "total": len(rows)}


# ── CSV template ─────────────────────────────────────────────────────────────

CSV_TEMPLATE = (
    "deal_type,property_type,city,address,neighborhood,rooms,floor,area_sqm,"
    "price,parking,pool,shelter,elevator,infrastructure,description,contact,owner_name,owner_phone\n"
    "rent,apartment,Тель-Авив,ул. Дизенгоф 99,Центр,3,4,85,"
    "7500,1,no,yes,yes,\"mall,school\",Светлая квартира с балконом,@agent1,Иван,0501234567\n"
    "buy,house,Хайфа,ул. Хагалиль 12,,5,1,150,"
    "2500000,2,yes,yes,no,park,Частный дом с садом,@agent2,Мария,0521234567\n"
)


def get_csv_template_bytes() -> bytes:
    return CSV_TEMPLATE.encode("utf-8-sig")  # BOM for Excel compatibility
