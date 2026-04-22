from datetime import datetime
from typing import List, Dict, Optional
import json
import os
import threading

_DB_LOCK = threading.RLock()

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(_DATA_DIR, "listings_db.json")

# On first run with a volume: seed from the bundled file only if volume DB doesn't exist yet
_BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listings_db.json")
if _BUNDLED != DB_FILE and os.path.exists(_BUNDLED) and not os.path.exists(DB_FILE):
    import shutil
    os.makedirs(_DATA_DIR, exist_ok=True)
    shutil.copy2(_BUNDLED, DB_FILE)

def _dedup_listings():
    """Remove duplicate listings by source_url only (not by title).
    Title-based dedup was too aggressive and ate valid FB/Telegram listings."""
    if not os.path.exists(DB_FILE):
        return
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        listings = data.get("listings", {})
        seen_urls, to_remove = set(), []
        for lid, l in listings.items():
            url = l.get('source_url', '').strip()
            if url:  # only dedup if has a real URL
                if url in seen_urls:
                    to_remove.append(lid)
                else:
                    seen_urls.add(url)
            # listings without source_url are kept (manual/old entries)
        if to_remove:
            for lid in to_remove:
                del data["listings"][lid]
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# _dedup_listings()  # disabled — was removing valid FB/Telegram listings on every startup

def _load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key, default in [
                ("subscriptions", {}), ("favorites_prices", {}), ("reviews", {}),
                ("referrals", {}), ("referral_bonuses", {}), ("closed_deals", {}),
                ("view_requesters", {}), ("deal_next_id", 1), ("services", {}),
                ("services_next_id", 1), ("crm_contacts", {}), ("crm_contact_next_id", 1),
                ("crm_deals", {}), ("crm_deal_next_id", 1), ("crm_notes", {}),
                ("paid_subscriptions", {}), ("agent_profiles", {}), ("service_profiles", {}),
            ]:
                if key not in data:
                    data[key] = default
            return data
        except Exception:
            pass
    return {
        "listings": {}, "favorites": {}, "user_listings": {}, "next_id": 11,
        "subscriptions": {}, "favorites_prices": {}, "reviews": {}, "referrals": {},
        "referral_bonuses": {}, "closed_deals": {}, "view_requesters": {},
        "deal_next_id": 1, "services": {}, "services_next_id": 1,
        "crm_contacts": {}, "crm_contact_next_id": 1, "crm_deals": {},
        "crm_deal_next_id": 1, "crm_notes": {},
    }

def _save(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _get_listings():
    return _load()

SAMPLE_LISTINGS = [
    {"id":1,"title":"Светлая квартира в центре Тель-Авива","property_type":"apartment","city":"Тель-Авив","district":"tel_aviv","neighborhood":"Florentin","rooms":"3","floor":"4","area_sqm":85,"price":8500,"deal_type":"rent","parking":1,"pool":False,"infrastructure":["school","transport","restaurant","gym"],"description":"Уютная квартира с ремонтом. 3 комнаты, 2 балкона.","contact":"@tlaviv_realty","photos":["🏢"],"date_added":"2025-01-10","active":True,"views":0,"view_requests":0},
    {"id":2,"title":"Вилла с бассейном в Герцлии","property_type":"villa","city":"Герцлия","district":"sharon","neighborhood":"Герцлия Питуах","rooms":"6","floor":"1","area_sqm":350,"price":4500000,"deal_type":"buy","parking":3,"pool":True,"infrastructure":["beach","gym","restaurant","mall"],"description":"Роскошная вилла с частным бассейном.","contact":"@luxury_israel","photos":["🏡"],"date_added":"2025-01-12","active":True,"views":0,"view_requests":0},
    {"id":3,"title":"Пентхаус с видом на море в Нетании","property_type":"penthouse","city":"Нетания","district":"sharon","neighborhood":"Центр","rooms":"5","floor":"Пентхаус","area_sqm":220,"price":2800000,"deal_type":"buy","parking":2,"pool":True,"infrastructure":["beach","transport","restaurant","park"],"description":"Пентхаус 220 кв.м с террасой 80 кв.м.","contact":"@netanya_premium","photos":["🌆"],"date_added":"2025-01-15","active":True,"views":0,"view_requests":0},
    {"id":4,"title":"Квартира 4 комнаты в Иерусалиме","property_type":"apartment","city":"Иерусалим","district":"jerusalem","neighborhood":"Рехавия","rooms":"4","floor":"3","area_sqm":110,"price":5500,"deal_type":"rent","parking":1,"pool":False,"infrastructure":["school","kindergarten","synagogue","park","transport"],"description":"Просторная квартира в тихом районе Рехавия.","contact":"@jerusalem_homes","photos":["🏠"],"date_added":"2025-01-08","active":True,"views":0,"view_requests":0},
    {"id":5,"title":"Студия в Хайфе","property_type":"studio","city":"Хайфа","district":"haifa","neighborhood":"Неве-Шаанан","rooms":"1","floor":"2","area_sqm":42,"price":2800,"deal_type":"rent","parking":0,"pool":False,"infrastructure":["transport","restaurant","gym"],"description":"Компактная студия с новым ремонтом.","contact":"@haifa_student","photos":["🛋"],"date_added":"2025-01-18","active":True,"views":0,"view_requests":0},
    {"id":6,"title":"Дом в Раанане с садом","property_type":"house","city":"Раанана","district":"sharon","neighborhood":"Северный","rooms":"5","floor":"1","area_sqm":200,"price":3200000,"deal_type":"buy","parking":2,"pool":False,"infrastructure":["school","kindergarten","park","mall","transport"],"description":"Частный дом с большим садом 400 кв.м.","contact":"@raanana_realty","photos":["🏠"],"date_added":"2025-01-05","active":True,"views":0,"view_requests":0},
    {"id":7,"title":"Квартира 2.5 комнаты в Ришон-ле-Ционе","property_type":"apartment","city":"Ришон-ле-Цион","district":"center","neighborhood":"Нахлат-Иегуда","rooms":"2.5","floor":"5","area_sqm":68,"price":1650000,"deal_type":"buy","parking":1,"pool":True,"infrastructure":["school","mall","transport","gym","park"],"description":"Новострой 2021 года. Общий бассейн на крыше.","contact":"@rishon_new","photos":["🏢"],"date_added":"2025-01-20","active":True,"views":0,"view_requests":0},
    {"id":8,"title":"Дуплекс 5 комнат в Модиине","property_type":"duplex","city":"Модиин","district":"center","neighborhood":"Анава","rooms":"5","floor":"1","area_sqm":160,"price":7500,"deal_type":"rent","parking":2,"pool":False,"infrastructure":["school","kindergarten","park","mall","transport","gym"],"description":"Просторный дуплекс в новом квартале.","contact":"@modiin_family","photos":["🏘"],"date_added":"2025-01-14","active":True,"views":0,"view_requests":0},
    {"id":9,"title":"Квартира у моря в Тель-Авиве","property_type":"apartment","city":"Тель-Авив","district":"tel_aviv","neighborhood":"Яффо","rooms":"3.5","floor":"6","area_sqm":95,"price":12000,"deal_type":"rent","parking":1,"pool":True,"infrastructure":["beach","restaurant","gym","transport","park"],"description":"Роскошный вид на море. Новострой 2023.","contact":"@tlv_sea_view","photos":["🏢"],"date_added":"2025-01-22","active":True,"views":0,"view_requests":0},
    {"id":10,"title":"Вилла в Кесарии","property_type":"villa","city":"Кесария","district":"sharon","neighborhood":"Кесария","rooms":"7","floor":"1","area_sqm":450,"price":8500000,"deal_type":"buy","parking":4,"pool":True,"infrastructure":["beach","gym","restaurant"],"description":"Эксклюзивная вилла в закрытом поселке.","contact":"@caesarea_elite","photos":["🏡"],"date_added":"2025-01-25","active":True,"views":0,"view_requests":0},
]

def _init_db():
    if not os.path.exists(DB_FILE):
        data = {
            "listings": {str(l["id"]): l for l in SAMPLE_LISTINGS},
            "favorites": {},
            "user_listings": {},
            "next_id": 11,
            "subscriptions": {},
            "favorites_prices": {},
            "reviews": {},
            "referrals": {},
            "referral_bonuses": {},
        }
        _save(data)

_init_db()

def search_listings(filters: Dict) -> List[Dict]:
    data = _load()
    results = []
    for listing in data["listings"].values():
        if not listing.get("active"): continue
        # deal type
        if filters.get("deal_type") and listing.get("deal_type") and listing["deal_type"] != filters["deal_type"]: continue
        # property type
        if filters.get("property_types") and len(filters["property_types"]) > 0 and listing.get("property_type") and listing["property_type"] not in filters["property_types"]: continue
                # districts
        districts = filters.get("districts")
        if districts and len(districts) > 0:
            if listing.get("district","") not in districts: continue
        # cities
        cities = filters.get("cities")
        if cities and len(cities) > 0:
            if listing.get("city","") not in cities: continue
        # single city
        if filters.get("city"):
            if listing.get("city","") != filters["city"]: continue
        # rooms min
        if filters.get("rooms_min"):
            try:
                r = float(str(listing.get("rooms","0")).replace("+",""))
                m = float(str(filters["rooms_min"]).replace("+",""))
                if r > 0 and r < m: continue
            except: pass
        # rooms max
        if filters.get("rooms_max"):
            try:
                r = float(str(listing.get("rooms","0")).replace("+",""))
                m = float(str(filters["rooms_max"]).replace("+",""))
                if r > 0 and r > m: continue
            except: pass
        # price min / max — skip listings with unknown price (0) when a price filter is active
        p = listing.get("price", 0)
        if filters.get("price_min"):
            if p == 0 or p < filters["price_min"]: continue
        if filters.get("price_max"):
            if p == 0 or p > filters["price_max"]: continue
        # parking
        if filters.get("parking_min") and listing.get("parking", 0) < filters["parking_min"]: continue
        # pool
        if filters.get("pool") is True and not listing.get("pool"): continue
        # infrastructure
        if filters.get("infrastructure") and len(filters["infrastructure"]) > 0:
            if not set(filters["infrastructure"]).issubset(set(listing.get("infrastructure",[]))): continue
        # with photos only
        if filters.get("with_photos"):
            has_real = any(len(p) > 20 for p in listing.get("photos", []))
            if not has_real: continue
        results.append(listing)
    return results

def get_listing(listing_id: int) -> Optional[Dict]:
    data = _load()
    return data["listings"].get(str(listing_id))

def add_listing(listing_data: Dict) -> int:
    with _DB_LOCK:
        data = _load()
        next_id = data["next_id"]
        listing_data["id"] = next_id
        listing_data["date_added"] = datetime.now().strftime("%Y-%m-%d")
        listing_data["active"] = True
        listing_data.setdefault("views", 0)
        listing_data.setdefault("view_requests", 0)
        data["listings"][str(next_id)] = listing_data
        data["next_id"] = next_id + 1
        user_id = listing_data.get("user_id")
        if user_id:
            uid = str(user_id)
            if uid not in data["user_listings"]:
                data["user_listings"][uid] = []
            data["user_listings"][uid].append(next_id)
        _save(data)
        return next_id

def get_user_listings(user_id: int) -> List[Dict]:
    data = _load()
    ids = data["user_listings"].get(str(user_id), [])
    return [data["listings"][str(i)] for i in ids if str(i) in data["listings"]]

def toggle_favorite(user_id: int, listing_id: int) -> bool:
    data = _load()
    uid = str(user_id)
    if uid not in data["favorites"]:
        data["favorites"][uid] = []
    if listing_id in data["favorites"][uid]:
        data["favorites"][uid].remove(listing_id)
        # Remove saved price
        fp_key = f"{uid}_{listing_id}"
        data.get("favorites_prices", {}).pop(fp_key, None)
        _save(data)
        return False
    data["favorites"][uid].append(listing_id)
    # Save current price for price drop tracking
    listing = data["listings"].get(str(listing_id))
    if listing:
        if "favorites_prices" not in data:
            data["favorites_prices"] = {}
        fp_key = f"{uid}_{listing_id}"
        data["favorites_prices"][fp_key] = listing.get("price", 0)
    _save(data)
    return True

def get_favorites(user_id: int) -> List[Dict]:
    data = _load()
    ids = data["favorites"].get(str(user_id), [])
    return [data["listings"][str(i)] for i in ids if str(i) in data["listings"]]

def get_all_listings(limit: int = None) -> List[Dict]:
    data = _load()
    active = [l for l in data["listings"].values() if l.get("active")]
    return active if limit is None else active[:limit]

# ── View counter ──────────────────────────────────────────────────────────────

def increment_views(listing_id: int):
    data = _load()
    key = str(listing_id)
    if key in data["listings"]:
        data["listings"][key]["views"] = data["listings"][key].get("views", 0) + 1
        _save(data)

def increment_view_requests(listing_id: int):
    data = _load()
    key = str(listing_id)
    if key in data["listings"]:
        data["listings"][key]["view_requests"] = data["listings"][key].get("view_requests", 0) + 1
        _save(data)

# ── Search subscriptions ──────────────────────────────────────────────────────

def add_search_subscription(user_id: int, filters: Dict) -> str:
    """Save search filters as a subscription. Returns sub_id."""
    data = _load()
    if "subscriptions" not in data:
        data["subscriptions"] = {}
    uid = str(user_id)
    if uid not in data["subscriptions"]:
        data["subscriptions"][uid] = []
    sub_id = f"{uid}_{len(data['subscriptions'][uid])}"
    sub = {
        "id": sub_id,
        "filters": filters,
        "created": datetime.now().isoformat(),
        "last_checked": datetime.now().isoformat(),
        "last_result_ids": [],
    }
    data["subscriptions"][uid].append(sub)
    _save(data)
    return sub_id

def get_user_subscriptions(user_id: int) -> List[Dict]:
    data = _load()
    return data.get("subscriptions", {}).get(str(user_id), [])

def remove_search_subscription(user_id: int, sub_index: int):
    data = _load()
    uid = str(user_id)
    subs = data.get("subscriptions", {}).get(uid, [])
    if 0 <= sub_index < len(subs):
        subs.pop(sub_index)
        data["subscriptions"][uid] = subs
        _save(data)

def get_all_subscriptions() -> Dict:
    data = _load()
    return data.get("subscriptions", {})

def update_subscription_last_checked(user_id: int, sub_index: int, last_result_ids: List):
    data = _load()
    uid = str(user_id)
    subs = data.get("subscriptions", {}).get(uid, [])
    if 0 <= sub_index < len(subs):
        subs[sub_index]["last_checked"] = datetime.now().isoformat()
        subs[sub_index]["last_result_ids"] = last_result_ids
        data["subscriptions"][uid] = subs
        _save(data)

# ── Price drop tracking ───────────────────────────────────────────────────────

def get_all_favorites_with_prices() -> Dict:
    """Returns {uid_lid: saved_price} for all favorites."""
    data = _load()
    return data.get("favorites_prices", {})

def update_favorite_price(user_id: int, listing_id: int, new_price: int):
    data = _load()
    if "favorites_prices" not in data:
        data["favorites_prices"] = {}
    fp_key = f"{user_id}_{listing_id}"
    data["favorites_prices"][fp_key] = new_price
    _save(data)

# ── Reviews ───────────────────────────────────────────────────────────────────

def add_review(listing_id: int, user_id: int, rating: int, comment: str = "") -> bool:
    """Add a review. Returns False if user already reviewed this listing."""
    data = _load()
    lid = str(listing_id)
    uid = str(user_id)
    if "reviews" not in data:
        data["reviews"] = {}
    if lid not in data["reviews"]:
        data["reviews"][lid] = []
    # Check duplicate
    if any(str(r.get("user_id")) == uid for r in data["reviews"][lid]):
        return False
    data["reviews"][lid].append({
        "user_id": uid,
        "rating": rating,
        "comment": comment,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    _save(data)
    return True

def get_reviews(listing_id: int) -> List[Dict]:
    data = _load()
    return data.get("reviews", {}).get(str(listing_id), [])

def get_average_rating(listing_id: int):
    """Returns (avg_rating, count) or (None, 0) if no reviews."""
    reviews = get_reviews(listing_id)
    if not reviews:
        return None, 0
    avg = sum(r["rating"] for r in reviews) / len(reviews)
    return round(avg, 1), len(reviews)

def user_has_reviewed(listing_id: int, user_id: int) -> bool:
    reviews = get_reviews(listing_id)
    return any(str(r.get("user_id")) == str(user_id) for r in reviews)

# ── Referrals ─────────────────────────────────────────────────────────────────

def add_referral(referrer_id: int, new_user_id: int) -> bool:
    """Register a referral. Returns False if already registered."""
    data = _load()
    rid = str(referrer_id)
    nid = str(new_user_id)
    if "referrals" not in data:
        data["referrals"] = {}
    if rid not in data["referrals"]:
        data["referrals"][rid] = []
    if nid in [str(x) for x in data["referrals"][rid]]:
        return False
    data["referrals"][rid].append(nid)
    _save(data)
    return True

def get_referral_count(user_id: int) -> int:
    data = _load()
    return len(data.get("referrals", {}).get(str(user_id), []))

def add_bonus_days(user_id: int, days: int):
    """Add bonus subscription days to user's referral bonus pool."""
    data = _load()
    uid = str(user_id)
    if "referral_bonuses" not in data:
        data["referral_bonuses"] = {}
    data["referral_bonuses"][uid] = data["referral_bonuses"].get(uid, 0) + days
    _save(data)

def get_bonus_days(user_id: int) -> int:
    data = _load()
    return data.get("referral_bonuses", {}).get(str(user_id), 0)


def get_bonus_expiry(user_id: int):
    """Returns expiry datetime if user has bonus days, else None."""
    from datetime import datetime, timedelta
    days = get_bonus_days(user_id)
    if days > 0:
        return datetime.now() + timedelta(days=days)
    return None


# ── Paid subscriptions (persistent) ──────────────────────────────────────────

def get_user_paid_subscriptions(user_id: int) -> dict:
    """Return dict of plan_type -> iso expiry string for user."""
    data = _load()
    return data.get("paid_subscriptions", {}).get(str(user_id), {})


def set_user_paid_subscription(user_id: int, plan_type: str, expiry_iso: str):
    """Save paid subscription expiry for user."""
    data = _load()
    if "paid_subscriptions" not in data:
        data["paid_subscriptions"] = {}
    uid = str(user_id)
    if uid not in data["paid_subscriptions"]:
        data["paid_subscriptions"][uid] = {}
    data["paid_subscriptions"][uid][plan_type] = expiry_iso
    _save(data)


# ── Price market comparison ───────────────────────────────────────────────────

def delete_listing(listing_id: int, user_id: int) -> bool:
    """Remove listing from DB and from user_listings index."""
    data = _load()
    lid = str(listing_id)
    if lid not in data["listings"]:
        return False
    del data["listings"][lid]
    uid = str(user_id)
    if uid in data["user_listings"]:
        data["user_listings"][uid] = [i for i in data["user_listings"][uid] if i != listing_id]
    _save(data)
    return True


def update_listing(listing_id: int, fields: dict) -> bool:
    """Update arbitrary fields of an existing listing."""
    data = _load()
    lid = str(listing_id)
    if lid not in data["listings"]:
        return False
    data["listings"][lid].update(fields)
    _save(data)
    return True


# ── Admin helpers ─────────────────────────────────────────────────────────────

def get_all_listings_admin(filters: Optional[Dict] = None) -> List[Dict]:
    """Return ALL listings (active + inactive) for back-office."""
    data = _load()
    result = list(data["listings"].values())
    if filters:
        q = (filters.get("q") or "").lower()
        city = (filters.get("city") or "").lower()
        deal = filters.get("deal_type")
        ptype = filters.get("property_type")
        active = filters.get("active")  # True / False / None = all
        if q:
            result = [l for l in result if q in l.get("title","").lower() or q in l.get("description","").lower()]
        if city:
            result = [l for l in result if city in l.get("city","").lower()]
        if deal:
            result = [l for l in result if l.get("deal_type") == deal]
        if ptype:
            result = [l for l in result if l.get("property_type") == ptype]
        if active is not None:
            result = [l for l in result if bool(l.get("active", True)) == active]
    return sorted(result, key=lambda x: str(x.get("date_added", "")), reverse=True)


def admin_delete_listing(listing_id: int) -> bool:
    """Hard-delete a listing (admin only, no user_id check)."""
    data = _load()
    lid = str(listing_id)
    if lid not in data["listings"]:
        return False
    uid = str(data["listings"][lid].get("user_id", ""))
    del data["listings"][lid]
    if uid and uid in data.get("user_listings", {}):
        data["user_listings"][uid] = [i for i in data["user_listings"][uid] if str(i) != lid]
    _save(data)
    return True


def update_service(service_id: str, fields: dict) -> bool:
    """Update arbitrary fields of an existing service."""
    data = _load()
    if service_id not in data.get("services", {}):
        return False
    data["services"][service_id].update(fields)
    _save(data)
    return True


def delete_service(service_id: str) -> bool:
    """Hard-delete a service record."""
    data = _load()
    if service_id not in data.get("services", {}):
        return False
    del data["services"][service_id]
    _save(data)
    return True


def get_all_users_admin() -> List[Dict]:
    """Return merged user info for back-office (from user_listings + agent_profiles + stats)."""
    data = _load()
    users: Dict[str, dict] = {}

    for uid, lid_list in data.get("user_listings", {}).items():
        if uid not in users:
            users[uid] = {"user_id": uid, "listing_ids": [], "email": None, "lang": None}
        users[uid]["listing_ids"] = lid_list

    for uid, profile in data.get("agent_profiles", {}).items():
        if uid not in users:
            users[uid] = {"user_id": uid, "listing_ids": [], "email": None, "lang": None}
        users[uid]["email"] = profile.get("email")
        users[uid]["lang"]  = profile.get("lang")
        users[uid]["owner_name"]  = profile.get("owner_name")
        users[uid]["owner_phone"] = profile.get("owner_phone")

    for uid, info in users.items():
        lid_list = info.get("listing_ids", [])
        active = sum(1 for lid in lid_list if data["listings"].get(str(lid), {}).get("active"))
        info["total_listings"]  = len(lid_list)
        info["active_listings"] = active

    return sorted(users.values(), key=lambda x: x["total_listings"], reverse=True)


def get_similar_listings(listing: Dict) -> List[Dict]:
    """Returns active listings in same city + property_type + deal_type, excluding self."""
    data = _load()
    city = listing.get("city", "")
    ptype = listing.get("property_type", "")
    deal = listing.get("deal_type", "")
    lid = str(listing.get("id", ""))
    results = []
    for k, l in data["listings"].items():
        if k == lid: continue
        if not l.get("active"): continue
        if l.get("city") == city and l.get("property_type") == ptype and l.get("deal_type") == deal:
            price = l.get("price", 0)
            if price > 0:
                results.append(l)
    return results


# ─── Deal tracking ───────────────────────────────────────────────────────────

def record_view_requester(listing_id: int, user_id: int, username: str = "", name: str = ""):
    """Record that a user requested viewing of a listing."""
    data = _load()
    lid = str(listing_id)
    if "view_requesters" not in data:
        data["view_requesters"] = {}
    if lid not in data["view_requesters"]:
        data["view_requesters"][lid] = []
    # Avoid duplicates
    existing_ids = [r["user_id"] for r in data["view_requesters"][lid]]
    if user_id not in existing_ids:
        data["view_requesters"][lid].append({
            "user_id": user_id,
            "username": username,
            "name": name,
            "date": datetime.now().strftime("%Y-%m-%d"),
        })
    _save(data)


def get_view_requesters(listing_id: int) -> List[Dict]:
    """Return list of users who requested viewing of this listing."""
    data = _load()
    return data.get("view_requesters", {}).get(str(listing_id), [])


def close_deal(listing_id: int, owner_id: int, tenant_id: int,
               listed_price: int, deal_price: int) -> int:
    """Record a closed deal. Returns deal_id."""
    data = _load()
    lid = str(listing_id)
    listing = data["listings"].get(lid, {})

    deal_id = data.get("deal_next_id", 1)
    date_listed = listing.get("date_added", "")
    days_to_close = 0
    if date_listed:
        try:
            from datetime import date
            d0 = date.fromisoformat(date_listed)
            d1 = date.today()
            days_to_close = (d1 - d0).days
        except Exception:
            pass

    deal = {
        "id": deal_id,
        "listing_id": listing_id,
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "listed_price": listed_price,
        "deal_price": deal_price if deal_price > 0 else listed_price,
        "deal_type": listing.get("deal_type", "rent"),
        "property_type": listing.get("property_type", "apartment"),
        "city": listing.get("city", ""),
        "rooms": listing.get("rooms", ""),
        "days_to_close": days_to_close,
        "closed_at": datetime.now().strftime("%Y-%m-%d"),
        "confirmed_by": "owner",
        "tenant_confirmed": False,
    }
    data["closed_deals"][str(deal_id)] = deal
    data["deal_next_id"] = deal_id + 1

    # Deactivate listing
    if lid in data["listings"]:
        data["listings"][lid]["active"] = False
        data["listings"][lid]["deal_closed"] = True
        data["listings"][lid]["deal_id"] = deal_id

    _save(data)
    return deal_id


def tenant_confirm_deal(deal_id: int) -> bool:
    """Tenant confirms deal — updates confirmed_by to 'both'."""
    data = _load()
    deal = data.get("closed_deals", {}).get(str(deal_id))
    if not deal:
        return False
    deal["tenant_confirmed"] = True
    deal["confirmed_by"] = "both"
    _save(data)
    return True


def get_closed_deals() -> List[Dict]:
    """Return all closed deals."""
    data = _load()
    return list(data.get("closed_deals", {}).values())


def get_user_closed_deals(user_id: int) -> List[Dict]:
    """Return deals where user is owner or tenant."""
    deals = get_closed_deals()
    return [d for d in deals if d.get("owner_id") == user_id or d.get("tenant_id") == user_id]


def get_listing_deal(listing_id: int) -> Optional[Dict]:
    """Return closed deal for a listing if exists."""
    data = _load()
    for deal in data.get("closed_deals", {}).values():
        if deal.get("listing_id") == listing_id:
            return deal
    return None


def get_deal_stats() -> Dict:
    """Aggregated stats for analytics dashboard."""
    deals = get_closed_deals()
    if not deals:
        return {"total": 0, "avg_days": 0, "avg_price_diff_pct": 0,
                "by_city": {}, "by_type": {}, "both_confirmed": 0}
    total = len(deals)
    avg_days = round(sum(d.get("days_to_close", 0) for d in deals) / total)
    both = sum(1 for d in deals if d.get("confirmed_by") == "both")

    diffs = []
    for d in deals:
        lp, dp = d.get("listed_price", 0), d.get("deal_price", 0)
        if lp > 0 and dp > 0:
            diffs.append((dp - lp) / lp * 100)
    avg_diff = round(sum(diffs) / len(diffs), 1) if diffs else 0

    by_city: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for d in deals:
        c = d.get("city", "Unknown")
        t = d.get("deal_type", "rent")
        by_city[c] = by_city.get(c, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": total,
        "avg_days": avg_days,
        "avg_price_diff_pct": avg_diff,
        "by_city": by_city,
        "by_type": by_type,
        "both_confirmed": both,
    }


def get_stale_listings(days: int = 30) -> List[Dict]:
    """Return active listings with view requests that haven't been closed for `days` days."""
    data = _load()
    result = []
    from datetime import date
    today = date.today()
    for lid, listing in data["listings"].items():
        if not listing.get("active"):
            continue
        if listing.get("deal_closed"):
            continue
        if listing.get("view_requests", 0) == 0:
            continue
        date_added = listing.get("date_added", "")
        if not date_added:
            continue
        try:
            d0 = date.fromisoformat(date_added)
            if (today - d0).days >= days:
                result.append(listing)
        except Exception:
            continue
    return result


# ── Services ──────────────────────────────────────────────────────────────────

def add_service(svc_data: dict) -> int:
    data = _load()
    sid = data.get("services_next_id", 1)
    svc_data["id"] = sid
    svc_data["date_added"] = datetime.now().strftime("%Y-%m-%d")
    svc_data["active"] = True
    data["services"][str(sid)] = svc_data
    data["services_next_id"] = sid + 1
    _save(data)
    return sid


def get_services(svc_type: str = None, region: str = None, city: str = None) -> list:
    data = _load()
    results = []
    for svc in data.get("services", {}).values():
        if not svc.get("active", True):
            continue
        if svc_type and svc.get("service_type") != svc_type:
            continue
        if region and region != "all":
            svc_region = svc.get("region", "all")
            if svc_region != "all" and svc_region != region:
                continue
        if city and city != "all":
            svc_city = svc.get("city", "")
            if svc_city and svc_city != city:
                continue
        results.append(svc)
    return results


# ── CRM ───────────────────────────────────────────────────────────────────────

VALID_DEAL_STATUSES = {"new", "in_progress", "done", "cancelled"}


def add_crm_contact(contact_data: dict) -> int:
    data = _load()
    cid = data.get("crm_contact_next_id", 1)
    contact_data["id"] = cid
    contact_data["date_added"] = datetime.now().strftime("%Y-%m-%d")
    contact_data["active"] = True
    data["crm_contacts"][str(cid)] = contact_data
    data["crm_contact_next_id"] = cid + 1
    _save(data)
    return cid


def get_crm_contact(contact_id: int) -> Optional[Dict]:
    data = _load()
    return data.get("crm_contacts", {}).get(str(contact_id))


def get_crm_contacts(contact_type: str = None, region: str = None,
                     city: str = None, active_only: bool = True) -> List[Dict]:
    data = _load()
    results = []
    for c in data.get("crm_contacts", {}).values():
        if active_only and not c.get("active", True):
            continue
        if contact_type and c.get("contact_type") != contact_type:
            continue
        if region and region != "all" and c.get("region") != region:
            continue
        if city and city != "all" and c.get("city") != city:
            continue
        results.append(c)
    return results


def update_crm_contact(contact_id: int, fields: dict) -> bool:
    data = _load()
    cid = str(contact_id)
    if cid not in data.get("crm_contacts", {}):
        return False
    data["crm_contacts"][cid].update(fields)
    _save(data)
    return True


def deactivate_crm_contact(contact_id: int) -> bool:
    return update_crm_contact(contact_id, {"active": False})


def add_crm_deal(deal_data: dict) -> int:
    data = _load()
    did = data.get("crm_deal_next_id", 1)
    deal_data["id"] = did
    deal_data["date"] = datetime.now().strftime("%Y-%m-%d")
    deal_data["updated_at"] = datetime.now().isoformat()
    data["crm_deals"][str(did)] = deal_data
    data["crm_deal_next_id"] = did + 1
    _save(data)
    return did


def get_crm_deals(contact_id: int = None, status: str = None) -> List[Dict]:
    data = _load()
    results = []
    for d in data.get("crm_deals", {}).values():
        if contact_id and d.get("contact_id") != contact_id:
            continue
        if status and d.get("status") != status:
            continue
        results.append(d)
    return sorted(results, key=lambda x: x.get("date", ""), reverse=True)


def update_crm_deal_status(deal_id: int, status: str) -> bool:
    if status not in VALID_DEAL_STATUSES:
        return False
    data = _load()
    did = str(deal_id)
    if did not in data.get("crm_deals", {}):
        return False
    data["crm_deals"][did]["status"] = status
    data["crm_deals"][did]["updated_at"] = datetime.now().isoformat()
    _save(data)
    return True


def add_crm_note(contact_id: int, text: str, author_id: int):
    data = _load()
    cid = str(contact_id)
    if cid not in data.get("crm_notes", {}):
        data["crm_notes"][cid] = []
    data["crm_notes"][cid].append({
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "author_id": author_id,
    })
    _save(data)


def get_crm_notes(contact_id: int) -> List[Dict]:
    data = _load()
    return data.get("crm_notes", {}).get(str(contact_id), [])


def get_crm_stats() -> Dict:
    data = _load()
    contacts = list(data.get("crm_contacts", {}).values())
    deals = list(data.get("crm_deals", {}).values())
    notes = data.get("crm_notes", {})
    total_notes = sum(len(v) for v in notes.values())
    by_type: Dict[str, int] = {}
    for c in contacts:
        if c.get("active", True):
            t = c.get("contact_type", "agent")
            by_type[t] = by_type.get(t, 0) + 1
    deals_by_status: Dict[str, int] = {}
    for d in deals:
        s = d.get("status", "new")
        deals_by_status[s] = deals_by_status.get(s, 0) + 1
    recent_deals = sorted(deals, key=lambda x: x.get("date", ""), reverse=True)[:5]
    for rd in recent_deals:
        cid = str(rd.get("contact_id", ""))
        contact = data.get("crm_contacts", {}).get(cid, {})
        rd["contact_name"] = contact.get("name", "—")
        rd["contact_type"] = contact.get("contact_type", "")
    return {
        "total_contacts": len([c for c in contacts if c.get("active", True)]),
        "by_type": by_type,
        "total_deals": len(deals),
        "deals_by_status": deals_by_status,
        "total_notes": total_notes,
        "recent_deals": recent_deals,
    }


# ── Agent profile (email + stats) ────────────────────────────────────────────

def save_agent_email(user_id: int, email: str, lang: str = "ru"):
    data = _load()
    uid = str(user_id)
    if "agent_profiles" not in data:
        data["agent_profiles"] = {}
    if uid not in data["agent_profiles"]:
        data["agent_profiles"][uid] = {}
    data["agent_profiles"][uid]["email"] = email
    data["agent_profiles"][uid]["lang"] = lang
    _save(data)

def get_agent_email(user_id: int) -> Optional[str]:
    data = _load()
    uid = str(user_id)
    return data.get("agent_profiles", {}).get(uid, {}).get("email")

def get_all_agent_emails() -> List[Dict]:
    """Return list of {user_id, email} for agents who have email set."""
    data = _load()
    result = []
    for uid, profile in data.get("agent_profiles", {}).items():
        if profile.get("email"):
            result.append({"user_id": int(uid), "email": profile["email"]})
    return result

def get_agent_report_data(user_id: int) -> Dict:
    """Collect weekly stats for a single agent."""
    import datetime
    data = _load()
    uid = str(user_id)
    listing_ids = data.get("user_listings", {}).get(uid, [])
    listings = []
    total_views = 0
    for lid in listing_ids:
        l = data["listings"].get(str(lid))
        if l and l.get("active"):
            views = l.get("views", 0)
            total_views += views
            listings.append({
                "id": lid,
                "title": l.get("title", "—"),
                "city": l.get("city", "—"),
                "rooms": l.get("rooms", "—"),
                "price": l.get("price", 0),
                "deal_type": l.get("deal_type", "—"),
                "views": views,
                "view_requests": l.get("view_requests", 0),
                "date_added": l.get("date_added", "—"),
            })
    listings.sort(key=lambda x: x["views"], reverse=True)
    profile = data.get("agent_profiles", {}).get(uid, {})
    return {
        "user_id": user_id,
        "email": profile.get("email", ""),
        "owner_name": profile.get("owner_name", ""),
        "lang": profile.get("lang", "ru"),
        "total_listings": len(listings),
        "total_views": total_views,
        "listings": listings,
        "week": datetime.date.today().strftime("%d.%m.%Y"),
    }


# ── Service provider profile (email + stats) ─────────────────────────────────

def save_service_email(user_id: int, email: str):
    data = _load()
    uid = str(user_id)
    if "service_profiles" not in data:
        data["service_profiles"] = {}
    if uid not in data["service_profiles"]:
        data["service_profiles"][uid] = {}
    data["service_profiles"][uid]["email"] = email
    _save(data)


def get_service_email(user_id) -> Optional[str]:
    if user_id is None:
        return None
    data = _load()
    return data.get("service_profiles", {}).get(str(user_id), {}).get("email")


def get_all_service_emails() -> List[Dict]:
    """Return {user_id, email, service_type, lang} for movers/packers with email."""
    data = _load()
    result = []
    profiles = data.get("service_profiles", {})
    services = data.get("services", {})
    for uid, profile in profiles.items():
        email = profile.get("email")
        if not email:
            continue
        user_svcs = [s for s in services.values()
                     if str(s.get("user_id", "")) == uid
                     and s.get("service_type") in ("moving", "packing")]
        if user_svcs:
            latest = sorted(user_svcs, key=lambda x: x.get("date_added", ""), reverse=True)[0]
            result.append({
                "user_id": int(uid),
                "email": email,
                "service_type": latest.get("service_type", ""),
                "owner_name": latest.get("owner_name", ""),
                "lang": latest.get("lang", "ru"),
            })
    return result


def get_service_report_data(user_id: int) -> Dict:
    """Collect stats for a service provider."""
    import datetime
    data = _load()
    uid = str(user_id)
    profile = data.get("service_profiles", {}).get(uid, {})
    services = [s for s in data.get("services", {}).values()
                if str(s.get("user_id", "")) == uid
                and s.get("active", True)
                and s.get("service_type") in ("moving", "packing")]
    total_views = sum(s.get("views", 0) for s in services)
    return {
        "user_id": user_id,
        "email": profile.get("email", ""),
        "owner_name": services[0].get("owner_name", "") if services else "",
        "lang": services[0].get("lang", "ru") if services else "ru",
        "service_type": services[0].get("service_type", "") if services else "",
        "total_services": len(services),
        "total_views": total_views,
        "services": sorted(services, key=lambda x: x.get("views", 0), reverse=True),
        "week": datetime.date.today().strftime("%d.%m.%Y"),
    }
