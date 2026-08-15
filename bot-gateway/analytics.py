import json
import os
from datetime import datetime, timedelta
from collections import Counter

import os as _os
_DATA_DIR = _os.environ.get("DATA_DIR", _os.path.dirname(_os.path.abspath(__file__)))
STATS_FILE = _os.path.join(_DATA_DIR, "stats.json")

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

def track_member(user_id: int, first_name: str = None, last_name: str = None, username: str = None):
    """Record that user clicked 'Join' button."""
    data = _load_stats()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    members = data.setdefault("members", {})
    if uid not in members:
        members[uid] = {"joined": today}
    _save_stats(data)
    # Also store user info so they appear in users list
    track_user(user_id, first_name=first_name, last_name=last_name, username=username)

def get_member_count() -> int:
    data = _load_stats()
    return len(data.get("members", {}))

def track_user(user_id: int, lang: str = "ru", first_name: str = None, last_name: str = None, username: str = None, phone: str = None):
    data = _load_stats()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in data["users"]:
        data["users"][uid] = {"first_seen": today, "last_seen": today, "lang": lang, "searches": 0, "subscribed": False}
    else:
        data["users"][uid]["last_seen"] = today
        data["users"][uid]["lang"] = lang
    u = data["users"][uid]
    if first_name: u["first_name"] = first_name
    if last_name:  u["last_name"]  = last_name
    if username:   u["username"]   = username
    if phone:      u["phone"]      = phone
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

_PLAN_PRICES = {"week": 19.90, "two_weeks": 29.90, "month": 39.90}

_CRYPTO_PRICES_USD = {"week": 5.50, "two_weeks": 8.00, "month": 11.00}

def track_subscription(user_id: int, plan: str, payment_type: str = "card",
                        crypto_asset: str = None, crypto_amount: str = None):
    """Track a subscription activation.
    payment_type: 'card' | 'crypto'
    """
    data = _load_stats()
    uid = str(user_id)
    now = datetime.now()
    data["subscriptions"][uid] = {"plan": plan, "date": now.strftime("%Y-%m-%d")}
    if uid in data["users"]:
        data["users"][uid]["subscribed"] = True
    log = data.setdefault("payments_log", [])
    u = data["users"].get(uid, {})
    entry = {
        "user_id": uid,
        "first_name": u.get("first_name", ""),
        "username": u.get("username", ""),
        "plan": plan,
        "amount": _PLAN_PRICES.get(plan, 0),
        "payment_type": payment_type,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
    }
    if payment_type == "crypto" and crypto_asset:
        entry["crypto_asset"] = crypto_asset
        entry["crypto_amount"] = crypto_amount or str(_CRYPTO_PRICES_USD.get(plan, 0))
        entry["amount"] = 0  # ILS amount unknown for crypto
    log.append(entry)
    _save_stats(data)

def _get_pricing_stats(db, raw: dict = None, stats_data: dict = None, lead_stats: dict = None) -> dict:
    """Collect monetisation stats from database for the dashboard.
    Pass pre-loaded raw dict to avoid a second db._load() call.
    Pass stats_data (from _load_stats()) to avoid a duplicate stats.json read.
    Pass lead_stats (from get_lead_marketplace_stats()) to avoid a sequential DB call."""
    from datetime import datetime as _dt
    if raw is None:
        try:
            import database_json as _dbj
            raw = _dbj._load()
        except Exception:
            raw = {}

    # ── Agent credits ─────────────────────────────────────────────────────────
    credits_map    = raw.get("listing_credits", {})          # {uid: count}
    free_used_map  = raw.get("listing_free_used", {})        # {uid: bool}
    total_credits  = sum(int(v) for v in credits_map.values())
    agents_with_credits = sum(1 for v in credits_map.values() if int(v) > 0)
    free_used_count = sum(1 for v in free_used_map.values() if v)

    # Agent credit table (non-zero only)
    users_data = raw.get("users", {})
    agent_credits_list = []
    for uid, cnt in credits_map.items():
        cnt = int(cnt)
        if cnt <= 0:
            continue
        u = users_data.get(str(uid), {})
        name = ((u.get("first_name","") or "") + " " + (u.get("last_name","") or "")).strip()
        agent_credits_list.append({
            "user_id":  uid,
            "name":     name or f"user_{uid}",
            "username": u.get("username",""),
            "credits":  cnt,
        })
    agent_credits_list.sort(key=lambda x: x["credits"], reverse=True)

    # ── Mover subscriptions ───────────────────────────────────────────────────
    svc_subs = raw.get("service_subscriptions", {})          # {svc_id: {plan_key, expiry}}
    now_iso  = _dt.utcnow().isoformat()
    mover_subs_list = []
    active_mover_subs = 0
    for svc_id, sub in svc_subs.items():
        expiry = sub.get("expiry", "")
        is_active = expiry > now_iso if expiry else False
        if is_active:
            active_mover_subs += 1
        # look up service name
        svc_all = raw.get("services", {})
        svc = svc_all.get(str(svc_id), {})
        pkg_label = {
            "mover_base": "База",
            "mover_top":  "База + ТОП",
        }.get(sub.get("plan_key",""), sub.get("plan_key",""))
        mover_subs_list.append({
            "svc_id":   svc_id,
            "name":     svc.get("name") or svc.get("company") or f"svc_{svc_id}",
            "region":   svc.get("region",""),
            "plan":     pkg_label,
            "expiry":   expiry[:10] if expiry else "—",
            "active":   is_active,
        })
    mover_subs_list.sort(key=lambda x: (not x["active"], x["expiry"]))

    # ── Revenue estimate (from payments_log) ──────────────────────────────────
    from pricing import (AGENT_PACKAGES, MOVER_PACKAGES,
                         MOVER_MONTHLY_BASE_ILS, MOVER_TOP_WEEKLY_ILS,
                         CLEANING_LEAD_PRICE_ILS, PACKING_LEAD_PRICE_ILS)
    pkg_prices = {p["key"]: p["price_ils"] for p in AGENT_PACKAGES}
    mover_prices = {p["key"]: p["price_ils"] for p in MOVER_PACKAGES}

    revenue_agent  = 0
    revenue_movers = 0
    # Use pre-loaded stats_data if provided (avoids duplicate _load_stats() call)
    payments_log = []
    if stats_data is not None:
        payments_log = stats_data.get("payments_log", [])
    else:
        # Fallback: try raw db data first, then load stats.json
        payments_log = raw.get("payments_log", []) if hasattr(raw, "get") else []
        try:
            _s = _load_stats()
            payments_log = _s.get("payments_log", [])
        except Exception:
            pass

    for p in payments_log:
        pk = p.get("plan") or p.get("plan_key","")
        if pk.startswith("agent_pkg_"):
            pkg_key = pk[len("agent_pkg_"):]
            revenue_agent += pkg_prices.get(pkg_key, 0)
        elif pk.startswith("mover_pkg_"):
            pkg_key = pk[len("mover_pkg_"):]
            revenue_movers += mover_prices.get(pkg_key, 0)

    # ── Lead marketplace stats (use pre-fetched if available) ────────────────
    if lead_stats is None:
        try:
            import database as _db
            lead_stats = _db.get_lead_marketplace_stats()
        except Exception:
            lead_stats = {}
    revenue_leads = lead_stats.get("revenue_total", 0)

    return {
        "agent_credits": {
            "total_credits_available": total_credits,
            "agents_with_credits":    agents_with_credits,
            "free_listings_used":     free_used_count,
            "list":                   agent_credits_list[:100],
        },
        "mover_subscriptions": {
            "total":  len(svc_subs),
            "active": active_mover_subs,
            "list":   mover_subs_list[:100],
        },
        "lead_marketplace": lead_stats,
        "revenue": {
            "agent_packages":     revenue_agent,
            "mover_subs":         revenue_movers,
            "leads":              revenue_leads,
            "total":              revenue_agent + revenue_movers + revenue_leads,
        },
        "price_table": {
            "agents": [
                {
                    "label": p["label"]["ru"],
                    "price": p["price_ils"],
                    "note":  p["note"]["ru"],
                }
                for p in AGENT_PACKAGES
            ],
            "movers": [
                {"label": "База (присутствие в базе)", "price": MOVER_MONTHLY_BASE_ILS, "note": "₪/мес"},
                {"label": "ТОП-место в городе",        "price": MOVER_TOP_WEEKLY_ILS,   "note": "₪/нед"},
            ],
            "cleaning": {"model": "subscription_and_lead", "price": CLEANING_LEAD_PRICE_ILS, "subscription_ils": 70},
            "packers":  {"model": "subscription_and_lead", "price": PACKING_LEAD_PRICE_ILS,  "subscription_ils": 70},
        },
    }


def _run_timed(fn, timeout_secs=12, default=None):
    """Run fn() in a thread with timeout; return default on timeout/error."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _TE
    _ex = ThreadPoolExecutor(max_workers=1)
    try:
        return _ex.submit(fn).result(timeout=timeout_secs)
    except (_TE, Exception):
        return default
    finally:
        _ex.shutdown(wait=False)


def get_analytics(date_from: str = None, date_to: str = None):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _TE, as_completed
    data = _load_stats()
    import database as db

    # ── Parallel I/O: run ALL heavy DB/file tasks concurrently ──────────────
    # This keeps total time ≈ max(individual times) instead of sum.
    # IMPORTANT: include every DB/file call here so nothing runs sequentially after.
    _parallel = ThreadPoolExecutor(max_workers=7)
    _f_listings  = _parallel.submit(lambda: db.get_all_listings(limit=10000))
    _f_db_data   = _parallel.submit(db._load)
    _f_crm       = _parallel.submit(db.get_crm_stats)
    _f_svcs      = _parallel.submit(lambda: db.get_all_services() if hasattr(db, 'get_all_services') else [])
    _f_svc_subs  = _parallel.submit(lambda: db.get_all_service_subscriptions() if hasattr(db, 'get_all_service_subscriptions') else {})
    _f_lead_stats = _parallel.submit(lambda: db.get_lead_marketplace_stats() if hasattr(db, 'get_lead_marketplace_stats') else {})
    def _get_owners():
        try:
            import owners_db as _odb
            return _odb.get_all_owners()
        except Exception:
            return []
    _f_owners    = _parallel.submit(_get_owners)
    _parallel.shutdown(wait=False)

    def _get(fut, default, timeout=15):
        try: return fut.result(timeout=timeout)
        except Exception: return default

    listings_all = _get(_f_listings, [], timeout=15)
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # ── Date range setup ──────────────────────────────────────────────────────
    # Normalise the period so all downstream counters respect it
    _df = date_from or "2026-03-01"   # "all time" fallback
    _dt = date_to   or today
    # Make sure _dt is inclusive end
    in_period = lambda d: _df <= (d or "") <= _dt

    # Filter listings to the selected period
    listings = [l for l in listings_all if in_period(l.get("date_added",""))]
    # When no date filter given we show totals, so use all listings for city/source counters
    listings_for_counters = listings if date_from else listings_all

    users = data.get("users", {})
    total_users = len(users)
    # "Real" users — have at least a name or @username (excludes ghost/privacy accounts)
    real_users = sum(
        1 for u in users.values()
        if u.get("first_name") or u.get("username")
    )

    # User counts scoped to period
    new_today  = sum(1 for u in users.values() if u.get("first_seen") == today)
    active_today = sum(1 for u in users.values() if u.get("last_seen") == today)
    new_week   = sum(1 for u in users.values() if u.get("first_seen", "") >= week_ago)
    active_week = sum(1 for u in users.values() if u.get("last_seen", "") >= week_ago)
    # Period-specific
    new_period    = sum(1 for u in users.values() if in_period(u.get("first_seen","")))
    active_period = sum(1 for u in users.values() if in_period(u.get("last_seen","")))

    lang_counter = Counter(u.get("lang", "ru") for u in users.values())

    # Searches scoped to period
    searches_all = data.get("searches", [])
    searches = [s for s in searches_all if in_period((s.get("time") or "")[:10])] if date_from else searches_all

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

    # ── Daily breakdown for the period ────────────────────────────────────────
    daily = data.get("daily", {})
    days_ru = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]

    # Build day list: if period given use it, else last 7 days
    if date_from and date_to:
        try:
            from_dt = datetime.strptime(_df, "%Y-%m-%d")
            to_dt   = datetime.strptime(_dt, "%Y-%m-%d")
        except ValueError:
            from_dt = datetime.now() - timedelta(days=6)
            to_dt   = datetime.now()
        delta_days = (to_dt - from_dt).days + 1
        # Cap at 90 days for display
        cap = min(delta_days, 90)
        day_list = []
        for i in range(cap - 1, -1, -1):
            d = (to_dt - timedelta(days=i)).strftime("%Y-%m-%d")
            day_data = daily.get(d, {})
            dow = (to_dt - timedelta(days=i)).weekday()
            day_list.append({
                "day": days_ru[dow], "date": d,
                "searches": day_data.get("searches", 0),
                "users": len(day_data.get("users", [])),
                "new": sum(1 for u in users.values() if u.get("first_seen") == d),
            })
    else:
        day_list = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_data = daily.get(d, {})
            dow = (datetime.now() - timedelta(days=i)).weekday()
            day_list.append({
                "day": days_ru[dow], "date": d,
                "searches": day_data.get("searches", 0),
                "users": len(day_data.get("users", [])),
                "new": sum(1 for u in users.values() if u.get("first_seen") == d),
            })

    last_7 = day_list  # keep compat name

    listing_cities  = Counter(l.get("city","")    for l in listings_for_counters)
    listing_sources = Counter(l.get("source","manual") for l in listings_for_counters)
    source_details  = Counter(l.get("contact","") for l in listings_for_counters if l.get("source") == "telegram")
    source_counter  = Counter(l.get("source","manual") for l in listings_all)

    # Facebook группы: извлекаем ID из source_url и считаем объявления
    _FB_GROUP_NAMES = {
        # Тель-Авив
        "101875683484689":  "מפה לאוזן תל אביב",
        "295395253832427":  "דירות בתל אביב",
        "457465901082882":  "ת״א ללא תיווך",
        "tel.aviv.dirot":   "לוח דירות תל אביב",
        "341195019300726":  "דירות במרכז",
        "191591524188001":  "דרום תל אביב",
        "1485565508385836": "צפון תל אביב",
        "184920528370332":  "דירות ת״א",
        "365588344194085":  "2-3 חדרים ת״א",
        "250663073164312":  "Tel Aviv Housing",
        "1664977427442936": "מרכז עד 5000₪",
        # Хайфа
        "173351201739":     "מפה לאוזן חיפה",
        "1591401697779759": "קריות ללא תיווך",
        "837431273097770":  "דירות בחיפה",
        "yad2k":            "דירות בקריות",
        "110907419268500":  "סטודנטים חיפה",
        "611703096084191":  "חיפה עם מחיר",
        "1896414753945570": "דירות חיפה",
        "783424098674651":  "דירות חיפה",
        "131650282168271":  "חיפה ללא תיווך",
        # Иерусалим
        "172544843294":     "מפה לאוזן ירושלים",
        "325992450444":     "דירות בירושלים",
        "344780799040537":  "להשכרה ירושלים",
        "apartmentsinjerusalem": "ירושלים ללא תיווך",
        # Ришон-ле-Цион
        "555578950202434":  "ראשון לציון",
        "959597644173111":  "ראשל״צ ללא תיווך",
        "111163552234056":  "מפה לאוזן ראשל״צ",
        "963153170558917":  "חולון בת-ים ראשל״צ",
        "201105170260427":  "ראשל״צ חולון בת-ים",
        # Холон
        "1354045801786047": "חולון",
        "801470026653021":  "להשכרה חולון",
        "266774507954665":  "חולון בלבד",
        "509654872819955":  "חולון בת-ים ללא תיווך",
        "dirot.batyam.holon":"בת-ים חולון",
        # Ашдод
        "1624818081000281": "אשדוד והסביבה",
        "1087635731246729": "אשדוד ללא תיווך",
        "215752412333714":  "דירות אשדוד",
        "rent.in.ashdod":   "אשדוד / Ашдод",
        "585483232340913":  "אשדוד אשקלון",
        # Нетания
        "228387647805774":  "נתניה ללא תיווך",
        "554754367898974":  "מפה לאוזן נתניה",
        "1153910968018350": "נתניה והסביבה",
        "rentflatnetanya":  "נתניה / Нетания",
        # Рамат-Ган
        "1870209196564360": "רמת גן גבעתיים",
        "192850633573":     "מפה לאוזן ר״ג",
        "253957624766723":  "להשכרה רמת גן",
        "441654752934426":  "ר״ג גבעתיים ללא תיווך",
        # Бат-Ям
        "647964450757105":  "Аренда Бат Ям",
        "rentbatyam":       "АРЕНДА БАТ ЯМ",
        "198851813933632":  "Аренда в Бат Яме",
        "1903124356581754": "Без маклера Бат Ям",
        "RentBuySaleBatYam":"Аренда/продажа Бат Ям",
        "holonandbatyam":   "Холон и Бат-Ям",
        "batyam.ad":        "Бат-Ям объявления",
        # Рош-аАин
        "1777924022257391": "ראש העין רבתי",
        "1773509336205184": "ראש העין",
        "1824690151020636": "לוח ראש העין",
        "1797166367186177": "הפרלמנט ראש העין",
        "509084853121039":  "להשכרה ראש העין",
        "308216903043626":  "ראש העין ללא תיווך",
        # Общеизраильские
        "819372811594662":  "Аренда квартир IL",
        "141464740539934":  "Аренда в Израиле",
        "1697329423753683": "Квартиры без маклера",
        "321202505245057":  "Из рук в руки",
        "2928147683954852": "Весь Гуш-Дан",
        "919120634860210":  "Русскояз. Израиль",
        "LiveandWork":      "Apartment Rentals IL",
        "TelAvivBoard":     "ТА доска объявлений",
        "2lumi":            "Доска объявлений IL",
        "adsisrael":        "Объявления (RU)",
    }
    def _fb_group_id(url):
        if "/groups/" in url:
            part = url.split("/groups/")[1].split("/")[0]
            return part if part else ""
        return ""
    fb_group_counter = Counter(
        _fb_group_id(l.get("source_url",""))
        for l in listings_all if l.get("source") == "facebook"
    )
    fb_sources_list = [
        {"name": _FB_GROUP_NAMES.get(gid, gid), "count": cnt,
         "url": f"https://www.facebook.com/groups/{gid}"}
        for gid, cnt in fb_group_counter.most_common(200)
        if gid
    ]
    income = round(
        sub_plans.get("week", 0) * 19.90 +
        sub_plans.get("two_weeks", 0) * 29.90 +
        sub_plans.get("month", 0) * 39.90, 2
    )
    # ── New feature stats from DB ─────────────────────────────────────────
    db_data = _get(_f_db_data, {}, timeout=12)

    # Views & view requests
    total_views = sum(l.get("views", 0) for l in listings)
    total_view_requests = sum(l.get("view_requests", 0) for l in listings)
    top_by_views = sorted(
        [l for l in listings if l.get("views", 0) > 0],
        key=lambda x: x.get("views", 0), reverse=True
    )[:8]

    # Lookup map by listing id — built from the CORRECTLY-loaded listings_all
    # (not db_data, which is a stale JSON snapshot under the PG backend)
    listings_by_id = {str(l.get("id")): l for l in listings_all}

    # Reviews
    reviews_db = db.get_all_reviews_bulk() if hasattr(db, "get_all_reviews_bulk") else db_data.get("reviews", {})
    all_reviews = [r for rv in reviews_db.values() for r in rv]
    total_reviews = len(all_reviews)
    avg_rating = round(sum(r.get("rating", 0) for r in all_reviews) / total_reviews, 2) if total_reviews else 0
    top_by_rating = []
    for lid, revs in reviews_db.items():
        if revs:
            listing = listings_by_id.get(str(lid))
            if listing:
                avg = round(sum(r.get("rating", 0) for r in revs) / len(revs), 1)
                top_by_rating.append({"title": listing.get("title", "")[:28], "rating": avg, "count": len(revs)})
    top_by_rating.sort(key=lambda x: x["rating"], reverse=True)

    # Search subscriptions (live — same source used by /api/admin/search-subscriptions)
    search_subs_db = db.get_all_subscriptions()
    total_search_subs = sum(len(v) for v in search_subs_db.values())
    # cities in subscriptions
    sub_city_counter = Counter()
    for uid, subs_list in search_subs_db.items():
        for s in subs_list:
            for c in (s.get("filters", {}).get("cities") or []):
                if c: sub_city_counter[c] += 1

    # Favorites
    fav_db = db.get_all_favorites_bulk() if hasattr(db, "get_all_favorites_bulk") else db_data.get("favorites", {})
    total_favorites = sum(len(v) for v in fav_db.values())
    fav_listing_counter = Counter(str(lid) for v in fav_db.values() for lid in v)
    top_favorites = []
    for lid, cnt in fav_listing_counter.most_common(5):
        listing = listings_by_id.get(str(lid))
        if listing:
            top_favorites.append({"title": listing.get("title", "")[:28], "count": cnt})

    # Referrals & bonuses
    referrals_db = db.get_all_referrals_bulk() if hasattr(db, "get_all_referrals_bulk") else db_data.get("referrals", {})
    total_referrals = sum(len(v) for v in referrals_db.values())
    bonus_db = db.get_all_bonus_days_bulk() if hasattr(db, "get_all_bonus_days_bulk") else db_data.get("referral_bonuses", {})
    total_bonus_days = sum(v for v in bonus_db.values())

    # Favorites prices (price drops)
    fav_prices = db.get_all_favorites_with_prices() if hasattr(db, "get_all_favorites_with_prices") else db_data.get("favorites_prices", {})
    total_price_tracked = len(fav_prices)

    members = data.get("members", {})
    total_members = len(members)
    new_members_today = sum(1 for m in members.values() if m.get("joined") == today)
    new_members_week = sum(1 for m in members.values() if m.get("joined", "") >= week_ago)

    # ── CRM ──────────────────────────────────────────────────────────────────
    crm_stats = _get(_f_crm, {}, timeout=10)
    crm_by_type = crm_stats.get("by_type", {})
    crm_deals_by_status = crm_stats.get("deals_by_status", {})
    crm_recent = crm_stats.get("recent_deals", [])

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

    # ── Services — read directly from PostgreSQL ─────────────────────────
    SVC_TYPE_NAMES = {
        "moving":          "🚚 Перевозки",
        "packing":         "📦 Упаковка",
        "cleaning":        "🧹 Клининг",
        "repair":          "🔨 Ремонт",
        "repair_painting": "🔨 Ремонт (Покраска)",
        "repair_plumbing": "🔨 Ремонт (Сантехника)",
        "repair_electric": "🔨 Ремонт (Электрика)",
        "repair_ac":       "🔨 Ремонт (Кондиционер)",
    }
    REGION_NAMES = {"north": "🌿 Север", "center": "🏙 Центр", "south": "☀️ Юг", "all": "🌍 Вся страна"}

    _svc_err = None
    _r1 = _get(_f_svcs, None, timeout=8)
    if _r1 is None:
        _svc_err = "services: timeout/error"
        services_all = list(db_data.get("services", {}).values())
    else:
        services_all = _r1

    _r2 = _get(_f_svc_subs, None, timeout=8)
    if _r2 is None:
        _svc_err = (_svc_err + " | " if _svc_err else "") + "svc_subs: timeout/error"
        _svc_subs_all = {}
    else:
        _svc_subs_all = _r2

    svc_active = [s for s in services_all if s.get("active", True)]
    svc_by_type = Counter(SVC_TYPE_NAMES.get(s.get("service_type",""), s.get("service_type","")) for s in svc_active)
    svc_by_region = Counter(REGION_NAMES.get(s.get("region",""), s.get("region","")) for s in svc_active)
    svc_recent = sorted(svc_active, key=lambda x: x.get("date_added",""), reverse=True)[:5]

    SVC_TYPE_LABELS = {
        "moving":          "🚚 Перевозчик",
        "packing":         "📦 Упаковщик",
        "cleaning":        "🧹 Клининг",
        "repair":          "🔨 Ремонт",
        "repair_painting": "🎨 Покраска",
        "repair_plumbing": "🔧 Сантехника",
        "repair_electric": "⚡ Электрика",
        "repair_ac":       "❄️ Кондиционер",
    }

    now_iso_svc = datetime.utcnow().isoformat()
    svc_providers_all = sorted(
        [
            {
                "svc_id":       s.get("id", ""),
                "user_id":      str(s.get("user_id", "")),
                "name":         s.get("owner_name") or s.get("contact") or "—",
                "type":         SVC_TYPE_LABELS.get(s.get("service_type",""), s.get("service_type","")),
                "region":       REGION_NAMES.get(s.get("region",""), s.get("region","")),
                "city":         s.get("city") or "—",
                "phone":        s.get("phone") or s.get("owner_phone") or "—",
                "price":        s.get("price") or 0,
                "views":        s.get("views") or 0,
                "desc":         (s.get("description") or "")[:80],
                "date":         s.get("date_added",""),
                "active":       s.get("active", True),
                "plan_key":     (_svc_subs_all.get(str(s.get("user_id",""))) or {}).get("plan_key",""),
                "plan":         (lambda pk: pk.split("_")[-1] if pk else "")(
                                    (_svc_subs_all.get(str(s.get("user_id",""))) or {}).get("plan_key","")),
                "promo_active": bool(
                                    s.get("promo_expiry","") and
                                    s.get("promo_expiry","") > now_iso_svc
                                ),
            }
            for s in services_all
        ],
        key=lambda x: x["date"], reverse=True
    )

    # ── User cabinets & user-added listings ───────────────────────────────
    user_listings_db = db.get_all_user_listings_bulk() if hasattr(db, "get_all_user_listings_bulk") else db_data.get("user_listings", {})
    user_added = []
    cabinets = []
    for uid, lid_list in user_listings_db.items():
        cab_listings = []
        for lid in lid_list:
            listing = listings_by_id.get(str(lid))
            if listing:
                entry = {
                    "id": lid,
                    "owner_name": listing.get("owner_name") or "—",
                    "owner_phone": listing.get("owner_phone") or "—",
                    "contact": listing.get("contact") or "—",
                    "city": listing.get("city") or "—",
                    "rooms": listing.get("rooms") or "—",
                    "price": listing.get("price") or 0,
                    "deal_type": listing.get("deal_type") or "—",
                    "date_added": listing.get("date_added") or "—",
                    "active": listing.get("active", True),
                    "views": listing.get("views", 0),
                    "user_id": uid,
                }
                if listing.get("active"):
                    user_added.append(entry)
                cab_listings.append(entry)
        if cab_listings:
            # Pick contact info from latest listing
            latest = sorted(cab_listings, key=lambda x: x["date_added"], reverse=True)[0]
            cabinets.append({
                "user_id": uid,
                "owner_name": latest["owner_name"],
                "owner_phone": latest["owner_phone"],
                "contact": latest["contact"],
                "total_listings": len(cab_listings),
                "active_listings": sum(1 for l in cab_listings if l["active"]),
                "total_views": sum(l["views"] for l in cab_listings),
                "last_date": latest["date_added"],
                "listings": sorted(cab_listings, key=lambda x: x["date_added"], reverse=True),
            })
    user_added.sort(key=lambda x: x["date_added"], reverse=True)
    cabinets.sort(key=lambda x: x["last_date"], reverse=True)

    # ── Email subscribers ──────────────────────────────────────────────────
    agent_profiles   = db.get_all_agent_profiles_bulk() if hasattr(db, "get_all_agent_profiles_bulk") else db_data.get("agent_profiles", {})
    service_profiles = db.get_all_service_profiles_bulk() if hasattr(db, "get_all_service_profiles_bulk") else db_data.get("service_profiles", {})
    # services_all was already fetched correctly above (PG-aware, via _f_svcs)

    # Agents with email
    email_agents = []
    for uid, prof in agent_profiles.items():
        if not prof.get("email"):
            continue
        # get their listings
        lids = user_listings_db.get(uid, [])
        active_count = sum(1 for lid in lids if listings_by_id.get(str(lid), {}).get("active"))
        agent_views  = sum(listings_by_id.get(str(lid), {}).get("views", 0) for lid in lids)
        email_agents.append({
            "user_id":    uid,
            "name":       prof.get("owner_name") or f"Агент #{uid}",
            "email":      prof.get("email"),
            "lang":       prof.get("lang", "ru"),
            "type":       "🏢 Агент",
            "listings":   len(lids),
            "active":     active_count,
            "views":      agent_views,
        })

    # Service providers with email (movers/packers)
    email_services = []
    for uid, prof in service_profiles.items():
        if not prof.get("email"):
            continue
        user_svcs = [s for s in services_all
                     if str(s.get("user_id","")) == uid
                     and s.get("service_type") in ("moving","packing")
                     and s.get("active", True)]
        if not user_svcs:
            continue
        latest = sorted(user_svcs, key=lambda x: x.get("date_added",""), reverse=True)[0]
        svc_type_label = {"moving": "🚚 Перевозчик", "packing": "📦 Упаковщик"}.get(latest.get("service_type",""), "")
        svc_views = sum(s.get("views", 0) for s in user_svcs)
        email_services.append({
            "user_id":  uid,
            "name":     latest.get("owner_name") or f"#{uid}",
            "email":    prof.get("email"),
            "lang":     latest.get("lang", "ru"),
            "type":     svc_type_label,
            "services": len(user_svcs),
            "views":    svc_views,
        })

    email_subscribers = {
        "agents":         sorted(email_agents,   key=lambda x: x["views"], reverse=True),
        "services":       sorted(email_services, key=lambda x: x["views"], reverse=True),
        "total_agents":   len(email_agents),
        "total_services": len(email_services),
        "total":          len(email_agents) + len(email_services),
    }

    # ── Seller type split (agent vs private) ──────────────────────────────
    # Reliable set of user-submitted listing IDs (from user_listings registry)
    _user_listing_ids = set(
        str(lid)
        for lids in user_listings_db.values()
        for lid in lids
    )
    # Include listings that are in user_listings registry OR explicitly source=="user"
    user_submitted = [
        l for l in listings_all
        if str(l.get("id", "")) in _user_listing_ids or l.get("source") == "user"
    ]
    # Agent = seller_type=="agent" OR user_id is in agent_profiles registry
    _agent_user_ids = set(str(k) for k in agent_profiles.keys())
    agent_listings   = [
        l for l in user_submitted
        if l.get("seller_type") == "agent" or str(l.get("user_id", "")) in _agent_user_ids
    ]
    private_listings = [l for l in user_submitted if l not in agent_listings]

    def _avg_price(lst):
        prices = [l.get("price", 0) for l in lst if (l.get("price") or 0) > 0]
        return round(sum(prices) / len(prices)) if prices else 0

    def _price_ranges(lst):
        prices = [l.get("price", 0) for l in lst if (l.get("price") or 0) > 0]
        if not prices:
            return {"min": 0, "max": 0, "avg": 0}
        return {"min": min(prices), "max": max(prices), "avg": round(sum(prices) / len(prices))}

    seller_stats = {
        "agent": {
            "total":       len(agent_listings),
            "active":      sum(1 for l in agent_listings if l.get("active")),
            "price_rent":  _price_ranges([l for l in agent_listings if l.get("deal_type") == "rent"]),
            "price_buy":   _price_ranges([l for l in agent_listings if l.get("deal_type") == "buy"]),
            "top_cities":  [{"city": c, "count": n} for c, n in Counter(l.get("city","") for l in agent_listings).most_common(5) if c],
            "recent":      sorted(agent_listings, key=lambda x: x.get("date_added",""), reverse=True)[:5],
        },
        "private": {
            "total":       len(private_listings),
            "active":      sum(1 for l in private_listings if l.get("active")),
            "price_rent":  _price_ranges([l for l in private_listings if l.get("deal_type") == "rent"]),
            "price_buy":   _price_ranges([l for l in private_listings if l.get("deal_type") == "buy"]),
            "top_cities":  [{"city": c, "count": n} for c, n in Counter(l.get("city","") for l in private_listings).most_common(5) if c],
            "recent":      sorted(private_listings, key=lambda x: x.get("date_added",""), reverse=True)[:5],
        },
        "unknown": len(listings) - len(agent_listings) - len(private_listings),
    }

    # ── Owners / contacts from channels (pre-fetched in parallel) ────────────
    owners_list = _get(_f_owners, [], timeout=8)
    try:
        import owners_db as _owners_db
        owners_stats = _owners_db.get_stats()
    except Exception:
        owners_stats = {"total": 0, "with_phone": 0, "with_username": 0, "with_name": 0}

    # ── Lead marketplace stats (pre-fetched in parallel) ──────────────────────
    _lead_stats = _get(_f_lead_stats, {}, timeout=8)

    return {
        "period": {"from": _df, "to": _dt, "days": (datetime.strptime(_dt,"%Y-%m-%d")-datetime.strptime(_df,"%Y-%m-%d")).days+1},
        "users": {
            "total": total_users, "real": real_users, "new_today": new_today,
            "active_today": active_today, "new_week": new_week, "active_week": active_week,
            "new_period": new_period, "active_period": active_period,
        },
        "members": {
            "total": total_members,
            "new_today": new_members_today,
            "new_week": new_members_week,
        },
        "users_list": sorted([
            {
                "user_id": uid,
                "first_name": u.get("first_name", ""),
                "last_name": u.get("last_name", ""),
                "username": u.get("username", ""),
                "phone": u.get("phone", ""),
                "first_seen": u.get("first_seen", u.get("last_seen", "")),
                "last_seen": u.get("last_seen", ""),
                "lang": u.get("lang", "ru"),
                "searches": u.get("searches", 0),
                "subscribed": u.get("subscribed", False),
            }
            for uid, u in {
                **{uid: {"first_seen": m.get("joined",""), "last_seen": m.get("joined","")} for uid, m in members.items()},
                **data["users"],
            }.items()
        ], key=lambda x: x["last_seen"], reverse=True),
        "languages": [
            {"name": k.upper(), "value": round(v/total_users*100) if total_users else 0, "count": v}
            for k, v in lang_counter.most_common()
        ],
        "searches_by_city": [{"city": c, "count": n} for c, n in city_counter.most_common(20)],
        "popular_filters": [{"filter": f, "count": n, "pct": round(n/len(searches)*100) if searches else 0} for f, n in filter_counter.most_common(8)],
        "total_searches_period": len(searches),
        "searches_log": [
            {
                "user_id":   s.get("user_id", ""),
                "time":      s.get("time", ""),
                "deal":      s.get("deal_type", ""),
                "cities":    ", ".join(s.get("cities") or []) or "—",
                "rooms":     f'{s.get("rooms_min","?")}-{s.get("rooms_max","?")}' if s.get("rooms_min") else "—",
                "price":     f'{s.get("price_min","?")}-{s.get("price_max","?")}' if s.get("price_min") else "—",
                "parking":   bool(s.get("parking")),
                "pool":      bool(s.get("pool")),
            }
            for s in sorted(searches_all, key=lambda x: x.get("time",""), reverse=True)[:300]
        ],
        "activity_week": last_7,
        "subscription": {
            "trial": total_users - len(subs),
            "week": sub_plans.get("week", 0),
            "two_weeks": sub_plans.get("two_weeks", 0),
            "month": sub_plans.get("month", 0),
            "conversion": conversion,
        },
        "listings": {
            "total": len(listings_all),
            "added_period": len(listings),
            "telegram": source_counter.get("telegram", 0),
            "facebook": source_counter.get("facebook", 0),
            "manual":   source_counter.get("manual", 0),
            "by_city": [{"city": c, "count": n} for c, n in Counter(l.get("city","") for l in listings_all if l.get("active", True) and l.get("city","") not in ("", "Израиль")).most_common(30)],
            "by_deal_type": [{"deal_type": dt, "count": n} for dt, n in Counter(l.get("deal_type","rent") for l in listings_all if l.get("active", True)).most_common()],
            "sources": [{"name": s, "count": n} for s, n in Counter(l.get("contact","") for l in listings_all if l.get("source") == "telegram").most_common(30)],
            "channels_total": len(set(l.get("contact","") for l in listings_all if l.get("source") == "telegram")),
            "fb_sources": fb_sources_list,
            "user_added": user_added,
        },
        "cabinets": cabinets,
        "email_subscribers": email_subscribers,
        "seller_stats": seller_stats,
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
        "service_providers_all": svc_providers_all,
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
                    "icon": {"moving":"🚚","packing":"📦","cleaning":"🧹",
                             "repair":"🔨","repair_painting":"🎨","repair_plumbing":"🔧",
                             "repair_electric":"⚡","repair_ac":"❄️"}.get(s.get("service_type",""),"🔧"),
                }
                for s in svc_recent
            ],
        },
        "crm": {
            "total_contacts": crm_stats.get("total_contacts", 0),
            "by_type": [
                {"type": "🏘 Агент",      "key": "agent",   "count": crm_by_type.get("agent", 0)},
                {"type": "🚚 Перевозчик", "key": "mover",   "count": crm_by_type.get("mover", 0)},
                {"type": "📦 Упаковщик",  "key": "packer",  "count": crm_by_type.get("packer", 0)},
                {"type": "🧹 Клининг",    "key": "cleaner", "count": crm_by_type.get("cleaner", 0)},
            ],
            "total_deals": crm_stats.get("total_deals", 0),
            "deals_by_status": [
                {"status": "🆕 Новая",     "key": "new",         "count": crm_deals_by_status.get("new", 0)},
                {"status": "⏳ В работе",  "key": "in_progress", "count": crm_deals_by_status.get("in_progress", 0)},
                {"status": "✅ Завершена", "key": "done",        "count": crm_deals_by_status.get("done", 0)},
                {"status": "❌ Отменена",  "key": "cancelled",   "count": crm_deals_by_status.get("cancelled", 0)},
            ],
            "total_notes": crm_stats.get("total_notes", 0),
            "recent_deals": [
                {
                    "contact_name": d.get("contact_name", "—"),
                    "contact_type": d.get("contact_type", ""),
                    "amount": d.get("amount", 0),
                    "status": d.get("status", "new"),
                    "date": d.get("date", ""),
                    "description": (d.get("description") or "")[:40],
                }
                for d in crm_recent
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
        "owners": {
            "stats": owners_stats,
            "list": owners_list[:500],
        },
        "payments_log": sorted(
            data.get("payments_log", []),
            key=lambda x: x.get("date","") + x.get("time",""),
            reverse=True
        )[:200],
        "pricing": _get_pricing_stats(db, raw=db_data, stats_data=data, lead_stats=_lead_stats),
        "_svc_debug": _svc_err,
    }
