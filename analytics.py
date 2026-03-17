import json
import os
from datetime import datetime, timedelta
from collections import Counter

STATS_FILE = "stats.json"

def _load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"users": {}, "searches": [], "subscriptions": {}, "daily": {}}

def _save_stats(data):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def track_user(user_id: int, lang: str = "ru"):
    data = _load_stats()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in data["users"]:
        data["users"][uid] = {"first_seen": today, "last_seen": today, "lang": lang, "searches": 0, "subscribed": False}
    else:
        data["users"][uid]["last_seen"] = today
        data["users"][uid]["lang"] = lang
    _save_stats(data)

def track_search(user_id: int, filters: dict):
    data = _load_stats()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    data["searches"].append({
        "user_id": uid, "time": now,
        "deal_type": filters.get("deal_type"),
        "cities": filters.get("cities", []),
        "districts": filters.get("districts", []),
        "rooms_min": filters.get("rooms_min"),
        "rooms_max": filters.get("rooms_max"),
        "price_min": filters.get("price_min"),
        "price_max": filters.get("price_max"),
        "parking": filters.get("parking_min"),
        "pool": filters.get("pool"),
        "shelter": filters.get("shelter"),
        "elevator": filters.get("elevator"),
        "infra": filters.get("infrastructure", []),
    })
    if uid in data["users"]:
        data["users"][uid]["searches"] = data["users"][uid].get("searches", 0) + 1
    if today not in data["daily"]:
        data["daily"][today] = {"searches": 0, "users": []}
    data["daily"][today]["searches"] = data["daily"][today].get("searches", 0) + 1
    if uid not in data["daily"][today]["users"]:
        data["daily"][today]["users"].append(uid)
    _save_stats(data)

def track_subscription(user_id: int, plan: str):
    data = _load_stats()
    uid = str(user_id)
    data["subscriptions"][uid] = {"plan": plan, "date": datetime.now().strftime("%Y-%m-%d")}
    if uid in data["users"]:
        data["users"][uid]["subscribed"] = True
    _save_stats(data)

def get_analytics():
    data = _load_stats()
    import database as db
    listings = db.get_all_listings(limit=10000)
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    users = data.get("users", {})
    total_users = len(users)
    new_today = sum(1 for u in users.values() if u.get("first_seen") == today)
    active_today = sum(1 for u in users.values() if u.get("last_seen") == today)
    new_week = sum(1 for u in users.values() if u.get("first_seen", "") >= week_ago)
    active_week = sum(1 for u in users.values() if u.get("last_seen", "") >= week_ago)
    lang_counter = Counter(u.get("lang", "ru") for u in users.values())
    searches = data.get("searches", [])
    city_counter = Counter()
    filter_counter = Counter()
    for s in searches:
        for c in (s.get("cities") or []):
            if c: city_counter[c] += 1
        if s.get("deal_type") == "rent": filter_counter["Аренда"] += 1
        elif s.get("deal_type") == "buy": filter_counter["Покупка"] += 1
        if s.get("parking"): filter_counter["Парковка"] += 1
        if s.get("pool"): filter_counter["Бассейн"] += 1
        if s.get("shelter"): filter_counter["Мамад/Миклат"] += 1
        if s.get("elevator") == "yes": filter_counter["Лифт"] += 1
        if s.get("rooms_min"): filter_counter[f"от {s['rooms_min']} комн."] += 1
    subs = data.get("subscriptions", {})
    sub_plans = Counter(v.get("plan") for v in subs.values())
    conversion = round(len(subs) / total_users * 100, 1) if total_users > 0 else 0
    daily = data.get("daily", {})
    last_7 = []
    days = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_data = daily.get(d, {})
        dow = (datetime.now() - timedelta(days=i)).weekday()
        last_7.append({
            "day": days[dow], "date": d,
            "searches": day_data.get("searches", 0),
            "users": len(day_data.get("users", [])),
            "new": sum(1 for u in users.values() if u.get("first_seen") == d),
        })
    listing_cities = Counter(l.get("city","") for l in listings)
    listing_sources = Counter(l.get("source","manual") for l in listings)
    source_details = Counter(l.get("contact","") for l in listings if l.get("source") == "telegram")
    income = round(
        sub_plans.get("week", 0) * 19.90 +
        sub_plans.get("two_weeks", 0) * 29.90 +
        sub_plans.get("month", 0) * 39.90, 2
    )
    return {
        "users": {
            "total": total_users, "new_today": new_today,
            "active_today": active_today, "new_week": new_week, "active_week": active_week,
        },
        "languages": [
            {"name": k.upper(), "value": round(v/total_users*100) if total_users else 0, "count": v}
            for k, v in lang_counter.most_common()
        ],
        "searches_by_city": [{"city": c, "count": n} for c, n in city_counter.most_common(8)],
        "popular_filters": [{"filter": f, "count": n, "pct": round(n/len(searches)*100) if searches else 0} for f, n in filter_counter.most_common(8)],
        "activity_week": last_7,
        "subscription": {
            "trial": total_users - len(subs),
            "week": sub_plans.get("week", 0),
            "two_weeks": sub_plans.get("two_weeks", 0),
            "month": sub_plans.get("month", 0),
            "conversion": conversion,
        },
        "listings": {
            "total": len(listings),
            "telegram": listing_sources.get("telegram", 0),
            "manual": listing_sources.get("manual", 0),
            "by_city": [{"city": c, "count": n} for c, n in listing_cities.most_common(5)],
            "sources": [{"name": s, "count": n} for s, n in source_details.most_common(5)],
        },
        "responses": {"total": 0, "favorites": 0, "contacts": 0, "avg_per_user": 0, "by_day": last_7},
        "income": {
            "current": income,
            "projected_month": round(income * 3, 2),
            "projected_year": round(income * 24, 2),
            "history": [],
        },
        "total_searches": len(searches),
    }
