"""
datagov_api.py — Интеграция с data.gov.il (реестр реальных сделок Израиля).

Данные: SHAAM (שמאי) — государственный реестр сделок с недвижимостью.
Resource ID: b8a24193-5b6b-4d19-bb09-c85f5eb11b64  (все сделки купли-продажи)

Запуск:
  python3 datagov_api.py --city "נתניה" --rooms 3 --last-days 90
  python3 datagov_api.py --street "הרצל" --city "תל אביב"
"""

import os
import json
import time
import logging
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

log = logging.getLogger("datagov")

# ── API ─────────────────────────────────────────────────────────────────────

BASE_URL  = "https://data.gov.il/api/3/action/datastore_search"

# Ресурсы реестра сделок (SHAAM / שמאי)
RESOURCES = {
    # Основной ресурс: сделки за последние годы (обновляется ежемесячно)
    "deals_main":     "b8a24193-5b6b-4d19-bb09-c85f5eb11b64",
    # Квартиры: ивритское название улицы + номер + город + дата + цена
    "apartments":     "93cefbd5-f037-4bf8-ab23-01f557e30f7d",
}

# Соответствие русских названий → иврит (для запросов)
CITY_HE = {
    "Нетания":         "נתניה",
    "Тель-Авив":       "תל אביב",
    "Иерусалим":       "ירושלים",
    "Хайфа":           "חיפה",
    "Ришон-ле-Цион":   "ראשון לציון",
    "Петах-Тиква":     "פתח תקווה",
    "Ашдод":           "אשדוד",
    "Бат-Ям":          "בת ים",
    "Холон":           "חולון",
    "Рамат-Ган":       "רמת גן",
    "Беэр-Шева":       "באר שבע",
    "Реховот":         "רחובות",
    "Герцлия":         "הרצליה",
    "Кфар-Саба":       "כפר סבא",
    "Раанана":         "רעננה",
    "Рош-аин":         "ראש העין",
    "Модиин":          "מודיעין",
    "Нес-Циона":       "נס ציונה",
    "Ашкелон":         "אשקלון",
    "Нагария":         "נהריה",
}

# Дисковый кеш
_DATA_DIR   = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
_CACHE_FILE = os.path.join(_DATA_DIR, "datagov_cache.json")
_CACHE_TTL  = 6 * 3600          # 6 часов
_cache_lock = threading.Lock()
_cache: dict = {}


def _load_cache():
    global _cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}

def _save_cache():
    try:
        tmp = _CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
        os.replace(tmp, _CACHE_FILE)
    except Exception as e:
        log.warning(f"Cache save error: {e}")

_load_cache()


# ── Базовый запрос к API ──────────────────────────────────────────────────────

def _api_get(resource_id: str, filters: dict = None, limit: int = 100,
             offset: int = 0, timeout: int = 15) -> dict:
    """
    Вызвать data.gov.il datastore_search.

    Параметры:
      resource_id — идентификатор датасета
      filters     — словарь фильтров {"city": "נתניה", "rooms": 3}
      limit       — кол-во записей
      offset      — смещение для пагинации

    Возвращает dict с ключами "records", "total" или {"error": "..."}.
    """
    params = {
        "resource_id": resource_id,
        "limit":       limit,
        "offset":      offset,
    }
    if filters:
        params["filters"] = json.dumps(filters, ensure_ascii=False)

    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    cache_key = url

    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and time.time() - cached.get("ts", 0) < _CACHE_TTL:
            return cached["data"]

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FlatFinderIL/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        if not raw.get("success"):
            return {"error": raw.get("error", {}).get("message", "API error"), "records": [], "total": 0}

        result = {
            "records": raw["result"].get("records", []),
            "total":   raw["result"].get("total", 0),
        }

        with _cache_lock:
            _cache[cache_key] = {"ts": time.time(), "data": result}
            if len(_cache) % 20 == 0:
                _save_cache()

        return result

    except Exception as e:
        log.warning(f"data.gov.il API error: {e}")
        return {"error": str(e), "records": [], "total": 0}


# ── Поиск сделок ─────────────────────────────────────────────────────────────

def get_recent_deals(
    city_ru: str,
    rooms: Optional[int] = None,
    street_he: str = None,
    last_days: int = 90,
    limit: int = 50,
) -> dict:
    """
    Получить последние сделки купли-продажи в городе.

    Параметры:
      city_ru   — название города на русском (Нетания, Тель-Авив...)
      rooms     — число комнат (int), None = все
      street_he — улица на иврите для фильтрации
      last_days — за сколько дней (по полю дата_сделки)
      limit     — максимум записей

    Возвращает:
      {
        "city": ...,
        "total": ...,
        "deals": [
          {"date": "YYYY-MM-DD", "price": 1650000, "rooms": 4,
           "floor": 3, "area_sqm": 110, "street": "...", "deal_type": "buy"},
          ...
        ],
        "stats": {"avg": ..., "median": ..., "min": ..., "max": ..., "count": ...}
      }
    """
    city_he = CITY_HE.get(city_ru, city_ru)
    cutoff  = (datetime.now() - timedelta(days=last_days)).strftime("%Y-%m-%d")

    filters = {}
    if city_he:
        filters["CITY_NAME"] = city_he
    if rooms:
        filters["ROOMS"] = str(rooms)
    if street_he:
        filters["STREET_NAME"] = street_he

    raw = _api_get(RESOURCES["apartments"], filters=filters, limit=limit)

    # Surface upstream errors instead of silently returning "0 deals" —
    # data.gov.il is undergoing an AWS migration (disruptions expected until
    # ~2026-08-18); the hardcoded resource IDs may 404 during/after this.
    if raw.get("error"):
        return {
            "city": city_ru, "city_he": city_he,
            "total": 0, "api_total": 0, "deals": [],
            "stats": _calc_stats([]),
            "error": f"data.gov.il недоступен: {raw['error']}",
        }

    deals = []
    for rec in raw.get("records", []):
        try:
            # Дата сделки (формат: DD/MM/YYYY или YYYY-MM-DD)
            date_raw = rec.get("DEAL_DATE") or rec.get("DOCUMENT_DATE") or ""
            date_iso = _parse_date(date_raw)
            if date_iso and date_iso < cutoff:
                continue

            price_raw = rec.get("PRICE") or rec.get("DEAL_PRICE") or 0
            price = _parse_int(price_raw)
            if price < 50_000:
                continue

            deals.append({
                "date":     date_iso or date_raw,
                "price":    price,
                "rooms":    _parse_float(rec.get("ROOMS") or rec.get("NEW_ROOMS")),
                "floor":    _parse_int(rec.get("FLOOR")),
                "area_sqm": _parse_float(rec.get("AREA") or rec.get("TOTAL_FLOORS")),
                "street":   (rec.get("STREET_NAME") or rec.get("ADDRESS") or "").strip(),
                "deal_type": "buy",
                "city_he":  rec.get("CITY_NAME", city_he),
            })
        except Exception:
            continue

    # Статистика
    prices = [d["price"] for d in deals if d["price"] > 0]
    stats  = _calc_stats(prices)

    return {
        "city":     city_ru,
        "city_he":  city_he,
        "total":    len(deals),
        "api_total": raw.get("total", 0),
        "deals":    sorted(deals, key=lambda x: x["date"], reverse=True),
        "stats":    stats,
    }


def get_price_by_street(city_ru: str, street_he: str, last_days: int = 365) -> dict:
    """
    Средняя цена сделок на конкретной улице города за период.

    Особенно полезно для инвесторов: «Сколько стоит квартира на ул. Герцль в Нетании?»

    Возвращает:
      {"street": ..., "city": ..., "stats": {...}, "deals": [...]}
    """
    return get_recent_deals(
        city_ru=city_ru,
        street_he=street_he,
        last_days=last_days,
        limit=100,
    )


def get_market_overview(city_ru: str, last_days: int = 90) -> dict:
    """
    Обзор рынка города: средние цены по числу комнат.

    Возвращает:
      {
        "city": "Нетания",
        "period_days": 90,
        "by_rooms": {
          "2": {"avg": 1200000, "count": 12},
          "3": {"avg": 1650000, "count": 28},
          "4": {"avg": 2100000, "count": 15},
        },
        "total_deals": 55,
        "overall": {"avg": 1750000, "median": 1650000, ...}
      }
    """
    raw = get_recent_deals(city_ru=city_ru, last_days=last_days, limit=200)

    by_rooms: dict[str, list] = defaultdict(list)
    for deal in raw["deals"]:
        r = deal.get("rooms")
        if r is not None:
            by_rooms[str(int(r) if r == int(r) else r)].append(deal["price"])

    overview = {
        "city":        city_ru,
        "period_days": last_days,
        "total_deals": raw["total"],
        "by_rooms":    {k: _calc_stats(v) for k, v in sorted(by_rooms.items())},
        "overall":     raw["stats"],
    }
    if raw.get("error"):
        overview["error"] = raw["error"]
    return overview


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _parse_date(raw: str) -> Optional[str]:
    """Привести дату к ISO 8601 (YYYY-MM-DD)."""
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(raw).strip()[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def _parse_int(val) -> int:
    try:
        return int(str(val).replace(",", "").replace(" ", "").split(".")[0])
    except (ValueError, TypeError):
        return 0

def _parse_float(val) -> Optional[float]:
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None

def _calc_stats(prices: list[int]) -> dict:
    import statistics as _stats
    if not prices:
        return {"count": 0, "avg": 0, "median": 0, "min": 0, "max": 0}
    return {
        "count":  len(prices),
        "avg":    round(_stats.mean(prices)),
        "median": round(_stats.median(prices)),
        "min":    min(prices),
        "max":    max(prices),
    }


# ── Точка входа / тест ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="data.gov.il — Реестр сделок")
    ap.add_argument("--city",      default="Нетания", help="Город на русском")
    ap.add_argument("--rooms",     type=int, default=None)
    ap.add_argument("--street",    default=None, help="Улица на иврите")
    ap.add_argument("--days",      type=int, default=90)
    ap.add_argument("--overview",  action="store_true", help="Обзор по комнатам")
    args = ap.parse_args()

    if args.overview:
        result = get_market_overview(args.city, last_days=args.days)
        print(f"\n🏙 Рынок {result['city']} (последние {result['period_days']} дн.):")
        print(f"   Сделок всего: {result['total_deals']}")
        print(f"   Общая статистика: ср. {result['overall'].get('avg', 0):,} ₪")
        print(f"\n   По числу комнат:")
        for rooms, s in result["by_rooms"].items():
            print(f"     {rooms}к: ср. {s['avg']:,} ₪  (n={s['count']})")
    else:
        result = get_recent_deals(
            city_ru=args.city,
            rooms=args.rooms,
            street_he=args.street,
            last_days=args.days,
        )
        print(f"\n🔍 Сделки в {result['city']} за {args.days} дней:")
        print(f"   Найдено: {result['total']} (всего в API: {result['api_total']})")
        s = result["stats"]
        if s["count"]:
            print(f"   Ср. цена: {s['avg']:,} ₪")
            print(f"   Медиана:  {s['median']:,} ₪")
            print(f"   Мин/Макс: {s['min']:,} — {s['max']:,} ₪\n")
        for d in result["deals"][:10]:
            print(f"   {d['date']}  {d['price']:>12,} ₪  {d['rooms']}к  {d['street']}")
