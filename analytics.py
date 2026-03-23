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

def track_member(user_id: int):
    """Record that user clicked 'Join' button."""
    data = _load_stats()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    members = data.setdefault("members", {})
    if uid not in members:
        members[uid] = {"joined": today}
        _save_stats(data)

def get_member_count() -> int:
    data = _load_stats()
    return len(data.get("members", {}))

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
    # ── New feature stats from DB ─────────────────────────────────────────
    db_data = db._load()

    # Views & view requests
    total_views = sum(l.get("views", 0) for l in listings)
    total_view_requests = sum(l.get("view_requests", 0) for l in listings)
    top_by_views = sorted(
        [l for l in listings if l.get("views", 0) > 0],
        key=lambda x: x.get("views", 0), reverse=True
    )[:8]

    # Reviews
    reviews_db = db_data.get("reviews", {})
    all_reviews = [r for rv in reviews_db.values() for r in rv]
    total_reviews = len(all_reviews)
    avg_rating = round(sum(r.get("rating", 0) for r in all_reviews) / total_reviews, 2) if total_reviews else 0
    top_by_rating = []
    for lid, revs in reviews_db.items():
        if revs:
            listing = db_data["listings"].get(str(lid))
            if listing:
                avg = round(sum(r.get("rating", 0) for r in revs) / len(revs), 1)
                top_by_rating.append({"title": listing.get("title", "")[:28], "rating": avg, "count": len(revs)})
    top_by_rating.sort(key=lambda x: x["rating"], reverse=True)

    # Search subscriptions
    search_subs_db = db_data.get("subscriptions", {})
    total_search_subs = sum(len(v) for v in search_subs_db.values())
    # cities in subscriptions
    sub_city_counter = Counter()
    for uid, subs_list in search_subs_db.items():
        for s in subs_list:
            for c in (s.get("filters", {}).get("cities") or []):
                if c: sub_city_counter[c] += 1

    # Favorites
    fav_db = db_data.get("favorites", {})
    total_favorites = sum(len(v) for v in fav_db.values())
    fav_listing_counter = Counter(str(lid) for v in fav_db.values() for lid in v)
    top_favorites = []
    for lid, cnt in fav_listing_counter.most_common(5):
        listing = db_data["listings"].get(str(lid))
        if listing:
            top_favorites.append({"title": listing.get("title", "")[:28], "count": cnt})

    # Referrals & bonuses
    referrals_db = db_data.get("referrals", {})
    total_referrals = sum(len(v) for v in referrals_db.values())
    bonus_db = db_data.get("referral_bonuses", {})
    total_bonus_days = sum(v for v in bonus_db.values())

    # Favorites prices (price drops)
    fav_prices = db_data.get("favorites_prices", {})
    total_price_tracked = len(fav_prices)

    members = data.get("members", {})
    total_members = len(members)
    new_members_today = sum(1 for m in members.values() if m.get("joined") == today)
    new_members_week = sum(1 for m in members.values() if m.get("joined", "") >= week_ago)

    # ── Commercial listings ──────────────────────────────────────────────
    COMMERCIAL_KEYS = {"office","retail","warehouse","coworking","restaurant_space","other_commercial"}
    COMMERCIAL_TYPE_NAMES = {
        "office": "Офис", "retail": "Магазин", "warehouse": "Склад",
        "coworking": "Коворкинг", "restaurant_space": "Кафе/Ресторан", "other_commercial": "Другое",
    }
    comm_listings = [l for l in listings if l.get("property_type") in COMMERCIAL_KEYS]
    comm_by_type = Counter(COMMERCIAL_TYPE_NAMES.get(l.get("property_type",""), l.get("property_type","")) for l in comm_listings)
    comm_by_deal = Counter(l.get("deal_type","") for l in comm_listings)
    comm_by_city = Counter(l.get("city","") for l in comm_listings)

    # ── Services ────────────────────────────────────────────────────────
    SVC_TYPE_NAMES = {"moving": "🚚 Перевозки", "packing": "📦 Упаковка", "cleaning": "🧹 Клининг"}
    REGION_NAMES = {"north": "🌿 Север", "center": "🏙 Центр", "south": "☀️ Юг", "all": "🌍 Вся страна"}
    services_all = list(db_data.get("services", {}).values())
    svc_active = [s for s in services_all if s.get("active", True)]
    svc_by_type = Counter(SVC_TYPE_NAMES.get(s.get("service_type",""), s.get("service_type","")) for s in svc_active)
    svc_by_region = Counter(REGION_NAMES.get(s.get("region",""), s.get("region","")) for s in svc_active)
    svc_recent = sorted(svc_active, key=lambda x: x.get("date_added",""), reverse=True)[:5]

    return {
        "users": {
            "total": total_users, "new_today": new_today,
            "active_today": active_today, "new_week": new_week, "active_week": active_week,
        },
        "members": {
            "total": total_members,
            "new_today": new_members_today,
            "new_week": new_members_week,
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
        "commercial": {
            "total": len(comm_listings),
            "by_type": [{"type": t, "count": n} for t, n in comm_by_type.most_common()],
            "by_deal": [
                {"deal": "Аренда", "count": comm_by_deal.get("rent",0) + comm_by_deal.get("commercial",0)},
                {"deal": "Продажа", "count": comm_by_deal.get("buy",0)},
            ],
            "by_city": [{"city": c, "count": n} for c, n in comm_by_city.most_common(8) if c],
        },
        "services": {
            "total": len(svc_active),
            "by_type": [{"type": t, "count": n} for t, n in svc_by_type.most_common()],
            "by_region": [{"region": r, "count": n} for r, n in svc_by_region.most_common()],
            "recent": [
                {
                    "type": SVC_TYPE_NAMES.get(s.get("service_type",""), s.get("service_type","")),
                    "region": REGION_NAMES.get(s.get("region",""), s.get("region","")),
                    "price": s.get("price", 0),
                    "date": s.get("date_added",""),
                    "icon": {"moving":"🚚","packing":"📦","cleaning":"🧹"}.get(s.get("service_type",""),"🔧"),
                }
                for s in svc_recent
            ],
        },
        "engagement": {
            "total_views": total_views,
            "total_view_requests": total_view_requests,
            "total_favorites": total_favorites,
            "total_reviews": total_reviews,
            "avg_rating": avg_rating,
            "total_search_subs": total_search_subs,
            "total_referrals": total_referrals,
            "total_bonus_days": total_bonus_days,
            "total_price_tracked": total_price_tracked,
            "top_by_views": [{"title": l.get("title","")[:28], "views": l.get("views",0), "city": l.get("city","")} for l in top_by_views],
            "top_by_rating": top_by_rating[:6],
            "top_favorites": top_favorites,
            "sub_cities": [{"city": c, "count": n} for c, n in sub_city_counter.most_common(6)],
        },
    }
