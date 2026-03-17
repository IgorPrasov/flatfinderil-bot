from datetime import datetime
from typing import List, Dict, Optional
import json
import os

DB_FILE = "listings_db.json"

def _load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"listings": {}, "favorites": {}, "user_listings": {}, "next_id": 11}

def _save(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _get_listings():
    return _load()

SAMPLE_LISTINGS = [
    {"id":1,"title":"Светлая квартира в центре Тель-Авива","property_type":"apartment","city":"Тель-Авив","district":"tel_aviv","neighborhood":"Florentin","rooms":"3","floor":"4","area_sqm":85,"price":8500,"deal_type":"rent","parking":1,"pool":False,"infrastructure":["school","transport","restaurant","gym"],"description":"Уютная квартира с ремонтом. 3 комнаты, 2 балкона.","contact":"@tlaviv_realty","photos":["🏢"],"date_added":"2025-01-10","active":True},
    {"id":2,"title":"Вилла с бассейном в Герцлии","property_type":"villa","city":"Герцлия","district":"sharon","neighborhood":"Герцлия Питуах","rooms":"6","floor":"1","area_sqm":350,"price":4500000,"deal_type":"buy","parking":3,"pool":True,"infrastructure":["beach","gym","restaurant","mall"],"description":"Роскошная вилла с частным бассейном.","contact":"@luxury_israel","photos":["🏡"],"date_added":"2025-01-12","active":True},
    {"id":3,"title":"Пентхаус с видом на море в Нетании","property_type":"penthouse","city":"Нетания","district":"sharon","neighborhood":"Центр","rooms":"5","floor":"Пентхаус","area_sqm":220,"price":2800000,"deal_type":"buy","parking":2,"pool":True,"infrastructure":["beach","transport","restaurant","park"],"description":"Пентхаус 220 кв.м с террасой 80 кв.м.","contact":"@netanya_premium","photos":["🌆"],"date_added":"2025-01-15","active":True},
    {"id":4,"title":"Квартира 4 комнаты в Иерусалиме","property_type":"apartment","city":"Иерусалим","district":"jerusalem","neighborhood":"Рехавия","rooms":"4","floor":"3","area_sqm":110,"price":5500,"deal_type":"rent","parking":1,"pool":False,"infrastructure":["school","kindergarten","synagogue","park","transport"],"description":"Просторная квартира в тихом районе Рехавия.","contact":"@jerusalem_homes","photos":["🏠"],"date_added":"2025-01-08","active":True},
    {"id":5,"title":"Студия в Хайфе","property_type":"studio","city":"Хайфа","district":"haifa","neighborhood":"Неве-Шаанан","rooms":"1","floor":"2","area_sqm":42,"price":2800,"deal_type":"rent","parking":0,"pool":False,"infrastructure":["transport","restaurant","gym"],"description":"Компактная студия с новым ремонтом.","contact":"@haifa_student","photos":["🛋"],"date_added":"2025-01-18","active":True},
    {"id":6,"title":"Дом в Раанане с садом","property_type":"house","city":"Раанана","district":"sharon","neighborhood":"Северный","rooms":"5","floor":"1","area_sqm":200,"price":3200000,"deal_type":"buy","parking":2,"pool":False,"infrastructure":["school","kindergarten","park","mall","transport"],"description":"Частный дом с большим садом 400 кв.м.","contact":"@raanana_realty","photos":["🏠"],"date_added":"2025-01-05","active":True},
    {"id":7,"title":"Квартира 2.5 комнаты в Ришон-ле-Ционе","property_type":"apartment","city":"Ришон-ле-Цион","district":"center","neighborhood":"Нахлат-Иегуда","rooms":"2.5","floor":"5","area_sqm":68,"price":1650000,"deal_type":"buy","parking":1,"pool":True,"infrastructure":["school","mall","transport","gym","park"],"description":"Новострой 2021 года. Общий бассейн на крыше.","contact":"@rishon_new","photos":["🏢"],"date_added":"2025-01-20","active":True},
    {"id":8,"title":"Дуплекс 5 комнат в Модиине","property_type":"duplex","city":"Модиин","district":"center","neighborhood":"Анава","rooms":"5","floor":"1","area_sqm":160,"price":7500,"deal_type":"rent","parking":2,"pool":False,"infrastructure":["school","kindergarten","park","mall","transport","gym"],"description":"Просторный дуплекс в новом квартале.","contact":"@modiin_family","photos":["🏘"],"date_added":"2025-01-14","active":True},
    {"id":9,"title":"Квартира у моря в Тель-Авиве","property_type":"apartment","city":"Тель-Авив","district":"tel_aviv","neighborhood":"Яффо","rooms":"3.5","floor":"6","area_sqm":95,"price":12000,"deal_type":"rent","parking":1,"pool":True,"infrastructure":["beach","restaurant","gym","transport","park"],"description":"Роскошный вид на море. Новострой 2023.","contact":"@tlv_sea_view","photos":["🏢"],"date_added":"2025-01-22","active":True},
    {"id":10,"title":"Вилла в Кесарии","property_type":"villa","city":"Кесария","district":"sharon","neighborhood":"Кесария","rooms":"7","floor":"1","area_sqm":450,"price":8500000,"deal_type":"buy","parking":4,"pool":True,"infrastructure":["beach","gym","restaurant"],"description":"Эксклюзивная вилла в закрытом поселке.","contact":"@caesarea_elite","photos":["🏡"],"date_added":"2025-01-25","active":True},
]

def _init_db():
    if not os.path.exists(DB_FILE):
        data = {
            "listings": {str(l["id"]): l for l in SAMPLE_LISTINGS},
            "favorites": {},
            "user_listings": {},
            "next_id": 11
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
        _save(data)
        return False
    data["favorites"][uid].append(listing_id)
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
