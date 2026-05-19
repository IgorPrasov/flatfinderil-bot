"""
mini_app_api.py — REST API для Telegram Mini App FlatFinder IL.

Endpoints:
  GET  /api/miniapp/listings            → поиск объявлений (фильтры через query params)
  GET  /api/miniapp/listings/<id>       → конкретное объявление
  GET  /api/miniapp/listings/<id>/ai    → AI-анализ объявления
  GET  /api/miniapp/favorites           → избранное пользователя
  POST /api/miniapp/favorites/toggle    → добавить/убрать из избранного
  POST /api/miniapp/viewing             → бронь просмотра
  POST /api/miniapp/ai-search           → AI поиск (текст → фильтры)
"""

from __future__ import annotations
import json
import os
import sys
import hashlib
import hmac
import time
import asyncio
from urllib.parse import parse_qs
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


# ── Telegram initData validation ─────────────────────────────────────────────

def _validate_init_data(init_data: str) -> Optional[dict]:
    """Validate Telegram WebApp initData. Returns parsed dict or None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(pair.split("=", 1) for pair in init_data.split("&") if "=" in pair)
        received_hash = parsed.pop("hash", "")
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return None
        # Check auth_date (max 1 hour old)
        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > 3600:
            return None
        user_str = parsed.get("user", "{}")
        return json.loads(user_str)
    except Exception:
        return None


def _get_user(headers: dict) -> Optional[dict]:
    """Extract validated Telegram user from request headers."""
    init_data = headers.get("X-Telegram-Init-Data", "")
    if init_data:
        user = _validate_init_data(init_data)
        if user:
            return user
    # In dev mode (no initData), allow unauthenticated
    if os.environ.get("MINI_APP_DEV_MODE") == "1":
        return {"id": 0, "first_name": "Dev"}
    return None


# ── AI Search ─────────────────────────────────────────────────────────────────

def _ai_parse_query(query: str, lang: str = "ru") -> dict:
    """
    Simple rule-based NL→filter parser (no LLM needed for common patterns).
    Extend this with Claude API calls for complex queries.
    """
    import re
    filters: dict = {}
    q = query.lower()

    # Deal type
    if any(w in q for w in ["снять", "аренда", "аренду", "rent", "להשכיר"]):
        filters["deal_type"] = "rent"
    elif any(w in q for w in ["купить", "покупка", "продажа", "buy", "לקנות"]):
        filters["deal_type"] = "buy"

    # Rooms (e.g. "3 комнаты", "2-3 к", "2к", "3 rooms")
    rooms_match = re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(?:комн|к\b|room)', q)
    if rooms_match:
        filters["rooms_min"] = int(rooms_match.group(1))
        filters["rooms_max"] = int(rooms_match.group(2))
    else:
        rooms_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:комн|к\b|room)', q)
        if rooms_match:
            r = float(rooms_match.group(1).replace(",", "."))
            filters["rooms_min"] = r
            filters["rooms_max"] = r

    # Price (e.g. "до 6000", "up to 8000", "6000-8000")
    price_range = re.search(r'(\d{3,7})\s*[-–]\s*(\d{3,7})', q)
    if price_range:
        a, b = int(price_range.group(1)), int(price_range.group(2))
        filters["price_min"], filters["price_max"] = min(a, b), max(a, b)
    else:
        price_max = re.search(r'(?:до|до|up\s+to|не\s+более|max)\s*(\d{3,7})', q)
        if price_max:
            filters["price_max"] = int(price_max.group(1))
        price_min = re.search(r'(?:от|from|min)\s*(\d{3,7})', q)
        if price_min:
            filters["price_min"] = int(price_min.group(1))

    # Cities
    CITY_MAP = {
        "тель-авив": "Тель-Авив", "тель авив": "Тель-Авив", "та": "Тель-Авив", "tel aviv": "Тель-Авив",
        "нетания": "Нетания", "netanya": "Нетания", "натания": "Нетания",
        "хайфа": "Хайфа", "haifa": "Хайфа",
        "беэр-шева": "Беэр-Шева", "беэр шева": "Беэр-Шева", "beer sheva": "Беэр-Шева",
        "ашдод": "Ашдод", "ashdod": "Ашдод",
        "реховот": "Реховот", "петах-тиква": "Петах-Тиква",
        "ришон": "Ришон-ле-Цион", "раанана": "Раанана",
        "хадера": "Хадера", "холон": "Холон",
    }
    found_cities = []
    for key, city in CITY_MAP.items():
        if key in q and city not in found_cities:
            found_cities.append(city)
    if found_cities:
        filters["cities"] = found_cities

    # Property type
    if any(w in q for w in ["студия", "studio"]):
        filters["property_types"] = ["studio"]
    elif any(w in q for w in ["дом", "house", "коттедж", "villa"]):
        filters["property_types"] = ["house"]
    elif any(w in q for w in ["комнату", "комната", "room"]):
        filters["property_types"] = ["room"]

    # With photos
    if any(w in q for w in ["с фото", "with photo", "with photos"]):
        filters["with_photos"] = True

    # Build human-readable explanation
    parts = []
    if filters.get("deal_type") == "rent":
        parts.append("аренда")
    elif filters.get("deal_type") == "buy":
        parts.append("покупка")
    if filters.get("cities"):
        parts.append(", ".join(filters["cities"]))
    if "rooms_min" in filters and "rooms_max" in filters and filters["rooms_min"] == filters["rooms_max"]:
        parts.append(f"{filters['rooms_min']} комн.")
    elif "rooms_min" in filters or "rooms_max" in filters:
        mn = filters.get("rooms_min", "")
        mx = filters.get("rooms_max", "")
        parts.append(f"комнат: {mn}–{mx}".strip("–").strip())
    if filters.get("price_max"):
        parts.append(f"до ₪{filters['price_max']:,}")
    if filters.get("price_min"):
        parts.append(f"от ₪{filters['price_min']:,}")

    explanation = "Фильтры: " + ", ".join(parts) if parts else "Показываю все объявления"
    return {"filters": filters, "explanation": explanation}


def _ai_analyze_listing(listing: dict) -> dict:
    """
    AI analysis of a single listing: valuation, duplicate detection, suspicious flag.
    Simple heuristics — can be upgraded to real ML later.
    """
    import statistics as st
    import database as db

    result = {
        "is_suspicious": False,
        "is_duplicate": False,
        "suspicion_reason": None,
        "valuation": None,
        "score": None,
    }

    desc = (listing.get("description") or "").lower()

    # Suspicion heuristics
    suspicious_phrases = [
        "без посредников звоните", "срочно", "предоплата", "задаток",
        "перевести деньги", "вышлите", "only serious", "no agents",
        "telegram только", "whatsapp only"
    ]
    for phrase in suspicious_phrases:
        if phrase in desc:
            result["is_suspicious"] = True
            result["suspicion_reason"] = f"Подозрительная фраза: «{phrase}»"
            break

    # Price sanity check (price per room unusually low)
    price = listing.get("price", 0)
    rooms = listing.get("rooms", 2)
    deal = listing.get("deal_type", "rent")
    city = listing.get("city", "")

    if deal == "rent" and price > 0 and rooms:
        per_room = price / max(rooms, 1)
        if per_room < 800:  # very cheap per room
            result["is_suspicious"] = True
            result["suspicion_reason"] = "Цена подозрительно низкая для данного типа жилья"

    # Valuation: median price for same city+deal+rooms
    try:
        data = db._load()
        similar = [
            l.get("price", 0) for l in data.get("listings", {}).values()
            if l.get("active")
            and l.get("deal_type") == deal
            and l.get("city") == city
            and l.get("price", 0) > 0
            and abs(float(str(l.get("rooms", 0)).replace("+", "") or 0) - float(str(rooms or 0))) < 1
        ]
        if len(similar) >= 3:
            result["valuation"] = int(st.median(similar))
    except Exception:
        pass

    # Quality score (0-100)
    score = 50
    if listing.get("photos") and len([p for p in listing.get("photos", []) if len(p) > 20]) >= 3:
        score += 20
    if listing.get("description") and len(listing.get("description", "")) > 100:
        score += 15
    if listing.get("area"):
        score += 5
    if listing.get("floor") is not None:
        score += 5
    if listing.get("address"):
        score += 5
    if result["is_suspicious"]:
        score -= 30
    result["score"] = max(0, min(100, score))

    return result


# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_get_listings(params: dict) -> dict:
    import database as db

    filters = {}
    if params.get("deal_type"):
        filters["deal_type"] = params["deal_type"][0]
    if params.get("property_types"):
        filters["property_types"] = params["property_types"]
    if params.get("cities"):
        filters["cities"] = params["cities"]
    if params.get("city"):
        filters["city"] = params["city"][0]
    if params.get("rooms_min"):
        filters["rooms_min"] = float(params["rooms_min"][0])
    if params.get("rooms_max"):
        filters["rooms_max"] = float(params["rooms_max"][0])
    if params.get("price_min"):
        filters["price_min"] = int(params["price_min"][0])
    if params.get("price_max"):
        filters["price_max"] = int(params["price_max"][0])
    if params.get("with_photos"):
        filters["with_photos"] = params["with_photos"][0] in ("1", "true", "True")

    listings = db.search_listings(filters)
    # Sort: active first, then by date added desc
    listings.sort(key=lambda l: l.get("date_added", ""), reverse=True)
    # Limit
    limit = int((params.get("limit") or [100])[0])
    return {"listings": listings[:limit], "total": len(listings)}


def handle_get_listing(listing_id: int) -> dict:
    import database as db
    listing = db.get_listing(listing_id)
    if not listing:
        return {"error": "Not found"}
    db.increment_views(listing_id)
    return listing


def handle_get_listing_ai(listing_id: int) -> dict:
    import database as db
    listing = db.get_listing(listing_id)
    if not listing:
        return {"error": "Not found"}
    return _ai_analyze_listing(listing)


def handle_get_favorites(user_id: int) -> dict:
    import database as db
    listings = db.get_favorites(user_id)
    return {"listings": listings}


def handle_toggle_favorite(body: dict) -> dict:
    import database as db
    user_id = int(body.get("user_id", 0))
    listing_id = int(body.get("listing_id", 0))
    if not user_id or not listing_id:
        return {"error": "Missing user_id or listing_id"}
    favs = db.get_favorites(user_id)
    fav_ids = {l["id"] for l in favs}
    if listing_id in fav_ids:
        db.remove_favorite(user_id, listing_id)
        return {"saved": False}
    else:
        db.add_favorite(user_id, listing_id)
        return {"saved": True}


def handle_book_viewing(body: dict, user: dict) -> dict:
    """Send a booking request to the listing owner via bot notification."""
    listing_id = int(body.get("listing_id", 0))
    date = body.get("date", "")
    message = body.get("message", "")
    if not listing_id or not date:
        return {"error": "Missing listing_id or date"}

    # Log the viewing request (could also send bot message to owner)
    import database as db
    listing = db.get_listing(listing_id)
    if not listing:
        return {"error": "Listing not found"}

    # Store viewing request in DB
    try:
        data = db._load()
        if "viewing_requests" not in data:
            data["viewing_requests"] = {}
        req_id = str(int(time.time()))
        data["viewing_requests"][req_id] = {
            "listing_id": listing_id,
            "user_id": user.get("id", 0) if user else 0,
            "user_name": user.get("first_name", "") if user else "",
            "date": date,
            "message": message,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        db._save(data)
    except Exception:
        pass

    return {"ok": True}


def handle_ai_search(body: dict) -> dict:
    query = body.get("query", "")
    lang = body.get("lang", "ru")
    if not query:
        return {"filters": {}, "explanation": "Пустой запрос"}
    return _ai_parse_query(query, lang)


def handle_get_services(params: dict) -> dict:
    """Return service providers (movers, cleaning, packing, repairs)."""
    try:
        import database as db
        category = (params.get("category") or [None])[0]
        services = db.get_services(category)
        return {"services": services}
    except Exception as e:
        # Fallback: return sample data if DB doesn't have services yet
        sample = [
            {
                "id": 1, "name": "MoversIL", "category": "moving",
                "phone": "+972-50-000-0001", "telegram": "@moversil",
                "description": "Профессиональные перевозки по всему Израилю",
                "regions": ["Тель-Авив", "Центр"], "price_from": 500,
            },
            {
                "id": 2, "name": "CleanPro", "category": "cleaning",
                "phone": "+972-50-000-0002", "telegram": "@cleanpro_il",
                "description": "Генеральная и регулярная уборка квартир",
                "regions": ["Тель-Авив", "Хайфа", "Нетания"], "price_from": 300,
            },
            {
                "id": 3, "name": "PackMaster", "category": "packing",
                "phone": "+972-50-000-0003", "telegram": None,
                "description": "Упаковка вещей для переезда, защитные материалы",
                "regions": ["Весь Израиль"], "price_from": 200,
            },
            {
                "id": 4, "name": "FixIT", "category": "repairs",
                "phone": "+972-50-000-0004", "telegram": "@fixit_il",
                "description": "Мелкий ремонт, сантехника, электрика",
                "regions": ["Центр", "Юг"], "price_from": 150,
            },
        ]
        if category:
            sample = [s for s in sample if s["category"] == category]
        return {"services": sample}


# ── Main router (called from analytics_server.py) ────────────────────────────

def route(method: str, path: str, params: dict, body: dict, headers: dict) -> tuple[dict, int]:
    """Returns (response_dict, status_code)."""

    # Auth
    user = _get_user(headers)

    # GET /api/miniapp/listings
    if method == "GET" and path == "/api/miniapp/listings":
        return handle_get_listings(params), 200

    # GET /api/miniapp/listings/<id>/ai
    if method == "GET" and path.startswith("/api/miniapp/listings/") and path.endswith("/ai"):
        try:
            lid = int(path.split("/")[-2])
            return handle_get_listing_ai(lid), 200
        except ValueError:
            return {"error": "Invalid id"}, 400

    # GET /api/miniapp/listings/<id>
    if method == "GET" and path.startswith("/api/miniapp/listings/"):
        try:
            lid = int(path.split("/")[-1])
            result = handle_get_listing(lid)
            return result, 200 if "error" not in result else 404
        except ValueError:
            return {"error": "Invalid id"}, 400

    # GET /api/miniapp/favorites
    if method == "GET" and path == "/api/miniapp/favorites":
        uid = int((params.get("user_id") or ["0"])[0])
        if not uid and user:
            uid = user.get("id", 0)
        return handle_get_favorites(uid), 200

    # POST /api/miniapp/favorites/toggle
    if method == "POST" and path == "/api/miniapp/favorites/toggle":
        return handle_toggle_favorite(body), 200

    # POST /api/miniapp/viewing
    if method == "POST" and path == "/api/miniapp/viewing":
        return handle_book_viewing(body, user), 200

    # POST /api/miniapp/ai-search
    if method == "POST" and path == "/api/miniapp/ai-search":
        return handle_ai_search(body), 200

    # GET /api/miniapp/services
    if method == "GET" and path == "/api/miniapp/services":
        return handle_get_services(params), 200

    return {"error": "Not found"}, 404
