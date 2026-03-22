from datetime import datetime
from typing import List, Dict, Optional
import json
import os

DB_FILE = "listings_db.json"

def _load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Migrate: ensure all new keys exist
                if "subscriptions" not in data:
                    data["subscriptions"] = {}
                if "favorites_prices" not in data:
                    data["favorites_prices"] = {}
                if "reviews" not in data:
                    data["reviews"] = {}
                if "referrals" not in data:
                    data["referrals"] = {}
                if "referral_bonuses" not in data:
                    data["referral_bonuses"] = {}
                return data
        except:
            pass
    return {
        "listings": {},
        "favorites": {},
        "user_listings": {},
        "next_id": 11,
        "subscriptions": {},
        "favorites_prices": {},
        "reviews": {},
        "referrals": {},
        "referral_bonuses": {},
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
        # price min
        p = listing.get("price", 0)
        if filters.get("price_min") and p > 0 and p < filters["price_min"]: continue
        # price max
        if filters.get("price_max") and p > 0 and p > filters["price_max"]: continue
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

def get_all_listings(limit: int = 1000) -> List[Dict]:
    data = _load()
    active = [l for l in data["listings"].values() if l.get("active")]
    return active[:limit]

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

# ── Price market comparison ───────────────────────────────────────────────────

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
