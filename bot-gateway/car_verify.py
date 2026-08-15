"""
car_verify.py — vehicle lookup against Israel's Ministry of Transport
public registry (data.gov.il), by license plate number OR VIN/chassis
("misgeret").

Same CKAN datastore_search API family as datagov_api.py, but a
different resource_id / dataset (private+commercial vehicle registry),
so kept as its own module rather than folded into datagov_api.py.
"""
import logging
import re
import requests

log = logging.getLogger(__name__)

_BASE = "https://data.gov.il/api/3/action/datastore_search"
# "פרטי וציבורי – מאגר רכבים" — private/commercial vehicle registry.
# Covers the vast majority of used-car listings regardless of body type
# (the `baalut` field is ownership type, not body type).
_RESOURCE_ACTIVE = "053cea08-09bc-40ec-8f7a-156f0677aff3"
# "רכב לא פעיל" — deregistered/inactive vehicles. Sparse (3 fields), used
# only as a red-flag fallback when the plate/VIN isn't in the active registry.
_RESOURCE_INACTIVE = "bb2355dc-9ec7-4f06-9c3f-3344672171da"

_TIMEOUT = 10


def _query(resource_id: str, field: str, value):
    import json as _json
    try:
        r = requests.get(
            _BASE,
            params={"resource_id": resource_id, "filters": _json.dumps({field: value})},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            return None, data.get("error") or "data.gov.il returned success=false"
        records = (data.get("result") or {}).get("records") or []
        return (records[0] if records else None), None
    except requests.exceptions.RequestException as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def lookup_vehicle(query: str) -> dict:
    """
    Look up a vehicle by license plate number or VIN/chassis number.

    Returns a dict. On success: {"found": True, ...normalized fields...}.
    Not found: {"found": False}. On a real fetch/API failure: {"found":
    False, "error": "..."} — surfaced honestly rather than silently
    returning "not found", per the same principle applied to the
    real-estate deals registry integration.
    """
    raw = (query or "").strip().upper()
    if not raw:
        return {"found": False, "error": "empty query"}
    if len(raw) > 32:
        return {"found": False, "error": "query too long"}

    digits_only = re.sub(r"[\s\-]", "", raw)
    is_plate = digits_only.isdigit()

    # VIN candidates: registry entries have been observed both with and
    # without the internal dash (e.g. "JMZDEA455-00443499"), so try the
    # value as typed (dash preserved, spaces trimmed) before falling back
    # to a fully stripped variant.
    vin_candidates = [re.sub(r"\s", "", raw)]
    stripped = re.sub(r"[\s\-]", "", raw)
    if stripped not in vin_candidates:
        vin_candidates.append(stripped)

    record = None
    if is_plate:
        record, err = _query(_RESOURCE_ACTIVE, "mispar_rechev", int(digits_only))
        if err:
            return {"found": False, "error": err}
        if not record:
            # Might actually be a short/odd VIN that happens to be all digits.
            for cand in vin_candidates:
                record, err = _query(_RESOURCE_ACTIVE, "misgeret", cand)
                if err:
                    return {"found": False, "error": err}
                if record:
                    break
    else:
        for cand in vin_candidates:
            record, err = _query(_RESOURCE_ACTIVE, "misgeret", cand)
            if err:
                return {"found": False, "error": err}
            if record:
                break
        if not record and digits_only.isdigit():
            record, err = _query(_RESOURCE_ACTIVE, "mispar_rechev", int(digits_only))
            if err:
                return {"found": False, "error": err}

    if record:
        return {
            "found": True,
            "plate": record.get("mispar_rechev"),
            "vin": record.get("misgeret"),
            "make": record.get("tozeret_nm"),
            "model": record.get("kinuy_mishari") or record.get("degem_nm"),
            "year": record.get("shnat_yitzur"),
            "color": record.get("tzeva_rechev"),
            "fuel_type": record.get("sug_delek_nm"),
            "ownership": record.get("baalut"),
            "country_of_origin": record.get("tozeret_eretz_nm"),
            "last_test_date": record.get("mivchan_acharon_dt"),
            "test_valid_until": record.get("tokef_dt"),
            "registered_since": record.get("moed_aliya_lakvish"),
        }

    # Not in the active registry — check the inactive/deregistered dataset
    # as a red-flag signal (plate-only; that dataset has no VIN field).
    if is_plate:
        inactive, err2 = _query(_RESOURCE_INACTIVE, "mispar_rechev", int(digits_only))
        if inactive:
            return {
                "found": True, "deregistered": True,
                "plate": inactive.get("mispar_rechev"),
                "ownership": inactive.get("baalut"),
            }

    return {"found": False}


def format_vehicle_info(info: dict) -> str:
    """Render a lookup_vehicle() result as an HTML message for Telegram."""
    if info.get("error"):
        return (
            "⚠️ Не удалось проверить авто — реестр Минтранса временно недоступен.\n"
            f"({info['error']})\n\nПопробуйте ещё раз чуть позже."
        )
    if not info.get("found"):
        return "❌ Авто с таким номером/VIN не найдено в реестре Министерства транспорта Израиля."
    if info.get("deregistered"):
        return (
            f"⚠️ <b>Номер {info.get('plate')}</b> числится как <b>снятый с учёта</b> "
            f"(неактивный) в реестре Минтранса.\nВладение: {info.get('ownership') or '—'}\n\n"
            "Это может быть красный флаг — уточните у продавца, почему авто не в активном реестре."
        )
    lines = ["🔍 <b>Информация об авто (реестр Минтранса Израиля)</b>\n"]
    make = info.get("make") or ""
    model = info.get("model") or ""
    if make or model:
        lines.append(f"🚗 <b>{make} {model}</b>".strip())
    if info.get("year"):
        lines.append(f"📅 Год выпуска: {info['year']}")
    if info.get("color"):
        lines.append(f"🎨 Цвет: {info['color']}")
    if info.get("fuel_type"):
        lines.append(f"⛽ Топливо: {info['fuel_type']}")
    if info.get("country_of_origin"):
        lines.append(f"🌍 Страна происхождения: {info['country_of_origin']}")
    if info.get("plate"):
        lines.append(f"🔢 Гос. номер: {info['plate']}")
    if info.get("vin"):
        lines.append(f"🔧 VIN (шасси): <code>{info['vin']}</code>")
    if info.get("ownership"):
        lines.append(f"👤 Тип владения: {info['ownership']}")
    if info.get("registered_since"):
        lines.append(f"📆 На дорогах с: {info['registered_since']}")
    if info.get("last_test_date"):
        lines.append(f"🗓 Последний тех. осмотр: {info['last_test_date']}")
    if info.get("test_valid_until"):
        lines.append(f"✅ Тех. осмотр действителен до: {info['test_valid_until']}")
    lines.append(
        "\nℹ️ Эта проверка НЕ включает историю аварий и банковский залог (שעבוד) — "
        "открытых госданных по ним нет. Залог можно проверить напрямую: "
        "<a href=\"https://www.gov.il/he/service/pawn_perusal\">gov.il — עיון בשעבודים</a>."
    )
    return "\n".join(lines)
