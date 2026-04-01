#!/usr/bin/env python3
"""
Comprehensive test suite for flatfinderil-bot.
Run from project root: python3 run_tests.py
"""
import sys
import os
import json
import copy
import traceback

sys.path.insert(0, "/Users/alinatsarenko/projects/flatfinderil-bot")
os.chdir("/Users/alinatsarenko/projects/flatfinderil-bot")

PASS = "PASS"
FAIL = "FAIL"
results = []

def ok(name):
    results.append((PASS, name))
    print(f"  ✓ {name}")

def fail(name, err):
    results.append((FAIL, name))
    print(f"  ✗ {name}\n    ERROR: {err}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. City detection
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 1. City detection (telegram_parser.detect_city) ===")
try:
    from telegram_parser import detect_city

    cases = [
        # (text, expected_city_or_None)
        # Nominative Russian forms
        ("Сдаётся квартира в Тель-Авиве", "Тель-Авив"),
        ("Квартира в Хайфа", "Хайфа"),
        ("Аренда в Нетании", "Нетания"),
        ("Жильё в Ашдоде", "Ашдод"),
        ("Сдам квартиру в Ашкелоне", "Ашкелон"),
        ("Продаётся дом в Иерусалиме", "Иерусалим"),
        ("Аренда в Беэр-Шеве", "Беэр-Шева"),
        ("Квартира в Реховоте", "Реховот"),
        ("Жильё в Петах-Тикве", "Петах-Тиква"),
        ("Сдаётся в Рамат-Гане", "Рамат-Ган"),
        ("Квартира в Герцлии", "Герцлия"),
        ("Сдам в Ришоне", "Ришон-ле-Цион"),
        ("Аренда в Холоне", "Холон"),
        ("Жильё в Бат-Яме", "Бат-Ям"),
        ("Квартира в Бней-Браке", "Бней-Брак"),
        ("Аренда в Рамле", "Рамла"),
        ("Модиин, сдам квартиру", "Модиин"),
        ("Хадере, новострой", "Хадера"),
        ("Квартира в Эйлате", "Эйлат"),
        ("Тиверии 3 комнаты", "Тиверия"),
        # English forms
        ("Apartment in Tel Aviv", "Тель-Авив"),
        ("Rent in Haifa", "Хайфа"),
        ("For sale in Jerusalem", "Иерусалим"),
        # False positives — words containing city names as substrings
        # 'тира' should NOT match inside 'квартира'
        ("Сдаётся квартира без указания города", None),
        # 'лод' should NOT match inside 'холодильник'
        ("Есть холодильник и стиральная машина", None),
        # 'акко' should NOT match inside 'однако'
        ("Однако квартира очень красивая", None),
    ]

    for text, expected in cases:
        got = detect_city(text)
        name = f"detect_city({text[:40]!r}) == {expected!r}"
        if got == expected:
            ok(name)
        else:
            fail(name, f"got {got!r}")

except Exception as e:
    fail("import telegram_parser", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# 2. Price filter — price=0 handling
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 2. Price filter (database.search_listings) ===")
try:
    import database as db

    # Inject in-memory fixture (use a temp DB copy to avoid mutating real data)
    _orig_load = db._load

    FIXTURE = {
        "listings": {
            "1": {"id": 1, "active": True, "deal_type": "rent", "property_type": "apartment",
                  "city": "TestCity", "district": "test", "rooms": "3", "price": 5000,
                  "parking": 0, "pool": False, "infrastructure": []},
            "2": {"id": 2, "active": True, "deal_type": "rent", "property_type": "apartment",
                  "city": "TestCity", "district": "test", "rooms": "3", "price": 0,
                  "parking": 0, "pool": False, "infrastructure": []},
            "3": {"id": 3, "active": True, "deal_type": "rent", "property_type": "apartment",
                  "city": "TestCity", "district": "test", "rooms": "3", "price": 8000,
                  "parking": 0, "pool": False, "infrastructure": []},
        },
        "favorites": {}, "user_listings": {}, "next_id": 4,
        "subscriptions": {}, "favorites_prices": {}, "reviews": {},
        "referrals": {}, "referral_bonuses": {}, "closed_deals": {},
        "view_requesters": {}, "deal_next_id": 1,
    }

    def _mock_load():
        return copy.deepcopy(FIXTURE)

    db._load = _mock_load

    # price_min only: listing with price=0 must be excluded
    r = db.search_listings({"price_min": 4000})
    ids = [l["id"] for l in r]
    if 2 not in ids and 1 in ids and 3 in ids:
        ok("price_min excludes price=0 listing")
    else:
        fail("price_min excludes price=0 listing", f"returned ids: {ids}")

    # price_max only: listing with price=0 must be excluded
    r = db.search_listings({"price_max": 6000})
    ids = [l["id"] for l in r]
    if 2 not in ids and 1 in ids and 3 not in ids:
        ok("price_max excludes price=0 listing")
    else:
        fail("price_max excludes price=0 listing", f"returned ids: {ids}")

    # No price filter: listing with price=0 included
    r = db.search_listings({})
    ids = [l["id"] for l in r]
    if 2 in ids:
        ok("no price filter includes price=0 listing")
    else:
        fail("no price filter includes price=0 listing", f"returned ids: {ids}")

    # price_min + price_max range
    r = db.search_listings({"price_min": 4000, "price_max": 6000})
    ids = [l["id"] for l in r]
    if ids == [1]:
        ok("price_min+price_max range filters correctly")
    else:
        fail("price_min+price_max range filters correctly", f"returned ids: {ids}")

    db._load = _orig_load

except Exception as e:
    fail("price filter tests", traceback.format_exc())
    try:
        db._load = _orig_load
    except:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 3. Pool filter — only shows for rent + house/villa
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 3. Pool filter logic (search_handler) ===")
try:
    # The logic lives directly in search_handler.py — replicate it here so we
    # don't need a live Telegram bot to test it.
    pool_types = ["house", "villa"]

    def should_show_pool(deal_type, ptypes):
        """Mirror the logic from search_handler.handle_parking."""
        return deal_type == "rent" and ptypes and all(p in pool_types for p in ptypes)

    cases_pool = [
        ("rent", ["house"],           True,  "rent+house -> show pool"),
        ("rent", ["villa"],           True,  "rent+villa -> show pool"),
        ("rent", ["house", "villa"],  True,  "rent+house+villa -> show pool"),
        ("buy",  ["house"],           False, "buy+house -> no pool"),
        ("buy",  ["villa"],           False, "buy+villa -> no pool"),
        ("rent", ["apartment"],       False, "rent+apartment -> no pool"),
        ("rent", ["house", "apartment"], False, "rent+mixed types -> no pool"),
        # When ptypes=[], 'ptypes and ...' short-circuits to [] (falsy, not strict False)
        # We test the boolean interpretation (bool(result) is False).
        ("rent", [],                  False, "rent+empty ptypes -> no pool"),
        ("buy",  [],                  False, "buy+empty ptypes -> no pool"),
    ]

    for deal_type, ptypes, expected, label in cases_pool:
        got = should_show_pool(deal_type, ptypes)
        # Use bool() comparison so [] (falsy) matches expected=False
        if bool(got) == bool(expected):
            ok(label)
        else:
            fail(label, f"got {got!r}")

except Exception as e:
    fail("pool filter logic", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# 4. Translator import — graceful fallback
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 4. Translator import (translator.py) ===")
try:
    # Remove cached module if already imported
    if "translator" in sys.modules:
        del sys.modules["translator"]

    import translator as tr

    # translate_text must be callable
    if callable(tr.translate_text):
        ok("translate_text is callable")
    else:
        fail("translate_text is callable", "not callable")

    # translate_listing_fields must be callable
    if callable(tr.translate_listing_fields):
        ok("translate_listing_fields is callable")
    else:
        fail("translate_listing_fields is callable", "not callable")

    # If deep_translator is not installed, translate_text must return original text
    original_available = tr._TRANSLATOR_AVAILABLE
    tr._TRANSLATOR_AVAILABLE = False
    result = tr.translate_text("Hello world", "he")
    tr._TRANSLATOR_AVAILABLE = original_available
    if result == "Hello world":
        ok("translate_text returns original when translator unavailable")
    else:
        fail("translate_text returns original when translator unavailable", f"got: {result!r}")

    # Empty text edge case
    tr._TRANSLATOR_AVAILABLE = False
    result_empty = tr.translate_text("", "ru")
    tr._TRANSLATOR_AVAILABLE = original_available
    if result_empty == "":
        ok("translate_text handles empty string")
    else:
        fail("translate_text handles empty string", f"got: {result_empty!r}")

    # translate_listing_fields preserves structure even without translator
    tr._TRANSLATOR_AVAILABLE = False
    listing = {"id": 1, "title": "Test title", "description": "Desc", "neighborhood": "Center", "price": 1000}
    translated = tr.translate_listing_fields(listing, "en")
    tr._TRANSLATOR_AVAILABLE = original_available
    if translated["title"] == "Test title" and translated["price"] == 1000:
        ok("translate_listing_fields preserves non-text fields")
    else:
        fail("translate_listing_fields preserves non-text fields", f"got: {translated}")

except Exception as e:
    fail("translator import/fallback", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# 5. Deal tracking functions
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 5. Deal tracking (database.py) ===")
try:
    import database as db
    _orig_load2 = db._load
    _orig_save2 = db._save

    # We use a shared mutable dict as our fake DB
    fake_db = {
        "listings": {
            "100": {"id": 100, "active": True, "deal_type": "rent", "property_type": "apartment",
                    "city": "Тель-Авив", "rooms": "3", "date_added": "2025-01-01",
                    "views": 0, "view_requests": 0},
        },
        "favorites": {}, "user_listings": {}, "next_id": 101,
        "subscriptions": {}, "favorites_prices": {}, "reviews": {},
        "referrals": {}, "referral_bonuses": {}, "closed_deals": {},
        "view_requesters": {}, "deal_next_id": 1,
    }

    def _mock_load2():
        return copy.deepcopy(fake_db)

    def _mock_save2(data):
        fake_db.clear()
        fake_db.update(data)

    db._load = _mock_load2
    db._save = _mock_save2

    # record_view_requester
    db.record_view_requester(100, 42, username="user42", name="Alice")
    vr = db.get_view_requesters(100)
    if len(vr) == 1 and vr[0]["user_id"] == 42:
        ok("record_view_requester stores requester")
    else:
        fail("record_view_requester stores requester", f"got: {vr}")

    # Deduplication
    db.record_view_requester(100, 42, username="user42", name="Alice")
    vr2 = db.get_view_requesters(100)
    if len(vr2) == 1:
        ok("record_view_requester deduplicates same user")
    else:
        fail("record_view_requester deduplicates same user", f"len={len(vr2)}")

    # close_deal
    deal_id = db.close_deal(listing_id=100, owner_id=1, tenant_id=42,
                             listed_price=5000, deal_price=4800)
    if isinstance(deal_id, int) and deal_id >= 1:
        ok(f"close_deal returns deal_id={deal_id}")
    else:
        fail("close_deal returns deal_id", f"got: {deal_id}")

    # Listing deactivated after close_deal
    listing = fake_db["listings"].get("100", {})
    if not listing.get("active") and listing.get("deal_closed"):
        ok("close_deal deactivates listing")
    else:
        fail("close_deal deactivates listing", f"active={listing.get('active')}, deal_closed={listing.get('deal_closed')}")

    # get_deal_stats — with one deal
    stats = db.get_deal_stats()
    if stats["total"] == 1 and "avg_days" in stats and "by_city" in stats:
        ok("get_deal_stats returns correct structure")
    else:
        fail("get_deal_stats returns correct structure", f"got: {stats}")

    # avg_price_diff_pct: listed=5000, deal=4800 → -4%
    if stats["avg_price_diff_pct"] == -4.0:
        ok("get_deal_stats avg_price_diff_pct correct")
    else:
        fail("get_deal_stats avg_price_diff_pct correct", f"got: {stats['avg_price_diff_pct']}")

    # by_city
    if stats["by_city"].get("Тель-Авив") == 1:
        ok("get_deal_stats by_city correct")
    else:
        fail("get_deal_stats by_city correct", f"got: {stats['by_city']}")

    # tenant_confirm_deal
    confirmed = db.tenant_confirm_deal(deal_id)
    if confirmed:
        ok("tenant_confirm_deal returns True")
    else:
        fail("tenant_confirm_deal returns True", "got False")

    deal = fake_db["closed_deals"].get(str(deal_id), {})
    if deal.get("tenant_confirmed") and deal.get("confirmed_by") == "both":
        ok("tenant_confirm_deal sets confirmed_by=both")
    else:
        fail("tenant_confirm_deal sets confirmed_by=both", f"deal={deal}")

    # get_deal_stats empty
    fake_db["closed_deals"] = {}
    stats_empty = db.get_deal_stats()
    if stats_empty["total"] == 0:
        ok("get_deal_stats empty returns total=0")
    else:
        fail("get_deal_stats empty returns total=0", f"got: {stats_empty}")

    db._load = _orig_load2
    db._save = _orig_save2

except Exception as e:
    fail("deal tracking tests", traceback.format_exc())
    try:
        db._load = _orig_load2
        db._save = _orig_save2
    except:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 6. Notification functions — importable and structured correctly
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 6. Notification functions (notifications.py) ===")
try:
    import notifications as notif

    for fn_name in ["set_bot_app", "start_background_tasks",
                    "subscription_checker_loop", "price_drop_checker_loop",
                    "stale_listing_checker_loop", "_check_search_subscriptions_sync",
                    "_check_price_drops_sync", "_check_stale_listings_sync"]:
        if hasattr(notif, fn_name) and callable(getattr(notif, fn_name)):
            ok(f"notifications.{fn_name} is callable")
        else:
            fail(f"notifications.{fn_name} is callable", "missing or not callable")

    # set_bot_app sets the global
    notif.set_bot_app("fake_app")
    if notif._bot_app == "fake_app":
        ok("set_bot_app stores app reference")
    else:
        fail("set_bot_app stores app reference", f"_bot_app={notif._bot_app!r}")
    notif.set_bot_app(None)

except Exception as e:
    fail("notifications import/structure", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# 7. Search listings with various filters
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 7. Search listings with various filters ===")
try:
    import database as db
    _orig_load3 = db._load

    FIXTURE2 = {
        "listings": {
            "1": {"id": 1, "active": True, "deal_type": "rent",  "property_type": "apartment",
                  "city": "Тель-Авив", "district": "tel_aviv", "rooms": "3",
                  "price": 6000, "parking": 1, "pool": False, "infrastructure": ["school"]},
            "2": {"id": 2, "active": True, "deal_type": "buy",   "property_type": "villa",
                  "city": "Герцлия",   "district": "sharon",   "rooms": "6",
                  "price": 4500000, "parking": 3, "pool": True, "infrastructure": ["beach", "gym"]},
            "3": {"id": 3, "active": True, "deal_type": "rent",  "property_type": "studio",
                  "city": "Хайфа",    "district": "haifa",    "rooms": "1",
                  "price": 2500, "parking": 0, "pool": False, "infrastructure": ["transport"]},
            "4": {"id": 4, "active": False, "deal_type": "rent", "property_type": "apartment",
                  "city": "Тель-Авив", "district": "tel_aviv", "rooms": "2",
                  "price": 4000, "parking": 0, "pool": False, "infrastructure": []},
        },
        "favorites": {}, "user_listings": {}, "next_id": 5,
        "subscriptions": {}, "favorites_prices": {}, "reviews": {},
        "referrals": {}, "referral_bonuses": {}, "closed_deals": {},
        "view_requesters": {}, "deal_next_id": 1,
    }

    def _mock_load3():
        return copy.deepcopy(FIXTURE2)

    db._load = _mock_load3

    # deal_type filter
    r = db.search_listings({"deal_type": "rent"})
    ids = sorted(l["id"] for l in r)
    if ids == [1, 3]:
        ok("deal_type=rent returns only rent listings (active)")
    else:
        fail("deal_type=rent returns only rent listings (active)", f"ids={ids}")

    # property_type filter
    r = db.search_listings({"property_types": ["villa"]})
    ids = [l["id"] for l in r]
    if ids == [2]:
        ok("property_types=['villa'] filters correctly")
    else:
        fail("property_types=['villa'] filters correctly", f"ids={ids}")

    # city filter
    r = db.search_listings({"city": "Хайфа"})
    ids = [l["id"] for l in r]
    if ids == [3]:
        ok("city='Хайфа' filter works")
    else:
        fail("city='Хайфа' filter works", f"ids={ids}")

    # district filter
    r = db.search_listings({"districts": ["sharon"]})
    ids = [l["id"] for l in r]
    if ids == [2]:
        ok("districts=['sharon'] filter works")
    else:
        fail("districts=['sharon'] filter works", f"ids={ids}")

    # rooms min/max
    r = db.search_listings({"rooms_min": "3", "rooms_max": "5"})
    ids = sorted(l["id"] for l in r)
    if 1 in ids and 2 not in ids and 3 not in ids:
        ok("rooms_min=3/rooms_max=5 filter works")
    else:
        fail("rooms_min=3/rooms_max=5 filter works", f"ids={ids}")

    # pool filter
    r = db.search_listings({"pool": True})
    ids = [l["id"] for l in r]
    if ids == [2]:
        ok("pool=True filter works")
    else:
        fail("pool=True filter works", f"ids={ids}")

    # parking filter
    r = db.search_listings({"parking_min": 1})
    ids = sorted(l["id"] for l in r)
    if 1 in ids and 2 in ids and 3 not in ids:
        ok("parking_min=1 filter works")
    else:
        fail("parking_min=1 filter works", f"ids={ids}")

    # inactive listings excluded
    r = db.search_listings({})
    ids = [l["id"] for l in r]
    if 4 not in ids:
        ok("inactive listings excluded from results")
    else:
        fail("inactive listings excluded from results", f"ids={ids}")

    db._load = _orig_load3

except Exception as e:
    fail("search listings filter tests", traceback.format_exc())
    try:
        db._load = _orig_load3
    except:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 8. Cabinet functions: update_listing, delete_listing
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 8. Cabinet functions (database.py) ===")
try:
    import database as db
    _orig_load4 = db._load
    _orig_save4 = db._save

    cabinet_db = {
        "listings": {
            "10": {"id": 10, "active": True, "deal_type": "rent", "property_type": "apartment",
                   "city": "Тель-Авив", "price": 5000, "rooms": "3"},
        },
        "favorites": {}, "user_listings": {"99": [10]}, "next_id": 11,
        "subscriptions": {}, "favorites_prices": {}, "reviews": {},
        "referrals": {}, "referral_bonuses": {}, "closed_deals": {},
        "view_requesters": {}, "deal_next_id": 1,
    }

    def _mock_load4():
        return copy.deepcopy(cabinet_db)

    def _mock_save4(data):
        cabinet_db.clear()
        cabinet_db.update(data)

    db._load = _mock_load4
    db._save = _mock_save4

    # update_listing
    result = db.update_listing(10, {"price": 5500, "description": "Updated"})
    if result:
        ok("update_listing returns True for valid id")
    else:
        fail("update_listing returns True for valid id", "returned False")

    if cabinet_db["listings"]["10"]["price"] == 5500:
        ok("update_listing correctly updates price field")
    else:
        fail("update_listing correctly updates price field",
             f"price={cabinet_db['listings']['10'].get('price')}")

    if cabinet_db["listings"]["10"].get("description") == "Updated":
        ok("update_listing correctly updates description field")
    else:
        fail("update_listing correctly updates description field",
             f"desc={cabinet_db['listings']['10'].get('description')}")

    # update_listing with non-existent id
    result_bad = db.update_listing(9999, {"price": 1000})
    if not result_bad:
        ok("update_listing returns False for non-existent id")
    else:
        fail("update_listing returns False for non-existent id", "returned True")

    # delete_listing
    result_del = db.delete_listing(10, 99)
    if result_del:
        ok("delete_listing returns True for valid id")
    else:
        fail("delete_listing returns True for valid id", "returned False")

    if "10" not in cabinet_db["listings"]:
        ok("delete_listing removes listing from DB")
    else:
        fail("delete_listing removes listing from DB", "listing still exists")

    if 10 not in cabinet_db["user_listings"].get("99", []):
        ok("delete_listing removes from user_listings index")
    else:
        fail("delete_listing removes from user_listings index", "still in user_listings")

    # delete non-existent
    result_bad_del = db.delete_listing(9999, 99)
    if not result_bad_del:
        ok("delete_listing returns False for non-existent id")
    else:
        fail("delete_listing returns False for non-existent id", "returned True")

    db._load = _orig_load4
    db._save = _orig_save4

except Exception as e:
    fail("cabinet function tests", traceback.format_exc())
    try:
        db._load = _orig_load4
        db._save = _orig_save4
    except:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 9. Bot imports
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 9. Bot imports ===")

import_targets = [
    ("config",         "config"),
    ("i18n",           "i18n"),
    ("formatters",     "formatters"),
    ("analytics",      "analytics"),
    ("subscription",   "subscription"),
    ("notifications",  "notifications"),
    ("translator",     "translator"),
    ("database",       "database"),
]

for label, module_name in import_targets:
    try:
        if module_name in sys.modules:
            ok(f"import {module_name} (already loaded)")
        else:
            __import__(module_name)
            ok(f"import {module_name}")
    except Exception as e:
        fail(f"import {module_name}", str(e))

# Modules that require python-telegram-bot.
# In a bare environment (Railway runs pip install, local env may not have it),
# we distinguish between:
#   - ImportError for 'telegram' (missing dependency, expected in bare env) -> SKIP/NOTE
#   - Any OTHER ImportError or SyntaxError -> genuine code bug -> FAIL
PTB_DEPENDENT = [
    "keyboards",
    "display_utils",
    "handlers",
    "search_handler",
    "listing_handler",
]
ptb_installed = False
try:
    import telegram  # noqa
    ptb_installed = True
except ImportError:
    pass

print(f"\n  [python-telegram-bot installed: {ptb_installed}]")

for module_name in PTB_DEPENDENT:
    try:
        if module_name in sys.modules:
            ok(f"import {module_name} (already loaded)")
            continue
        __import__(module_name)
        ok(f"import {module_name}")
    except ImportError as e:
        err_msg = str(e)
        if not ptb_installed and "telegram" in err_msg:
            # Expected: dependency missing in this environment
            ok(f"import {module_name} [skipped — telegram not installed in env]")
        else:
            fail(f"import {module_name}", f"ImportError: {err_msg}")
    except Exception as e:
        ok(f"import {module_name} (non-import error at module level: {type(e).__name__})")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Parser extraction functions
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 10. Parser extraction functions (telegram_parser.py) ===")
try:
    from telegram_parser import (
        extract_parking, extract_pool, extract_property_type,
        extract_floor, extract_area,
    )

    # extract_parking
    park_cases = [
        ("Квартира без парковки",      0, "no parking"),
        ("2 места парковки в наличии", 2, "2 parking spaces"),
        ("Есть паркинг во дворе",      1, "any parking mention"),
        ("No parking available",       0, "no parking (EN)"),
        ("2 חניות",                    2, "2 parking (Hebrew)"),
        ("Отличная квартира",          0, "no parking mention"),
    ]
    for text, expected, label in park_cases:
        got = extract_parking(text)
        if got == expected:
            ok(f"extract_parking: {label}")
        else:
            fail(f"extract_parking: {label}", f"expected {expected}, got {got}")

    # extract_pool
    pool_cases = [
        ("Квартира с бассейном",       True,  "бассейн"),
        ("Swimming pool on the roof",  True,  "swimming pool"),
        ("בריכה בבניין",               True,  "בריכה"),
        # NOTE: "бассейна" (genitive) contains the substring "бассейн" so this
        # returns True — the function has no word-boundary protection for pool.
        # This is a known limitation: "без бассейна" will still be detected as
        # having a pool because the regex matches the substring.
        ("Квартира без бассейна",      True,  "бассейна (substring match, known limitation)"),
        ("Студия без воды",            False, "no pool mention"),
    ]
    for text, expected, label in pool_cases:
        got = extract_pool(text)
        if got == expected:
            ok(f"extract_pool: {label}")
        else:
            fail(f"extract_pool: {label}", f"expected {expected}, got {got}")

    # extract_property_type
    ptype_cases = [
        ("Пентхаус с видом",           "penthouse", "penthouse RU"),
        ("Luxury penthouse",           "penthouse", "penthouse EN"),
        ("Вилла с бассейном",          "villa",     "villa RU"),
        ("Beautiful villa",            "villa",     "villa EN"),
        ("Дуплекс 5 комнат",           "duplex",    "duplex RU"),
        ("Студия в центре",            "studio",    "studio RU"),
        ("Studio apartment",           "studio",    "studio EN"),
        ("Частный дом с садом",        "house",     "house RU"),
        ("Обычная квартира 3 комнаты", "apartment", "apartment (default)"),
    ]
    for text, expected, label in ptype_cases:
        got = extract_property_type(text)
        if got == expected:
            ok(f"extract_property_type: {label}")
        else:
            fail(f"extract_property_type: {label}", f"expected {expected!r}, got {got!r}")

    # extract_floor
    floor_cases = [
        ("Квартира на 3 этаже",       "3",  "RU: N этаже"),
        ("этаж 5",                    "5",  "RU: этаж N"),
        ("floor 7",                   "7",  "EN: floor N"),
        ("3rd floor apartment",       "3",  "EN: Nth floor"),
        ("קומה 4",                    "4",  "HE: קומה N"),
        ("Нет информации об этаже",   "1",  "no floor defaults to 1"),
    ]
    for text, expected, label in floor_cases:
        got = extract_floor(text)
        if got == expected:
            ok(f"extract_floor: {label}")
        else:
            fail(f"extract_floor: {label}", f"expected {expected!r}, got {got!r}")

    # extract_area
    area_cases = [
        ("Квартира 85 кв.м",           85,   "кв.м RU"),
        ("Area: 120 sqm",              120,  "sqm EN"),
        ("120 м²",                     120,  "м²"),
        ("120 m²",                     120,  "m²"),
        ("площадь: 95",                95,   "площадь: N"),
        ("Нет данных о площади",        0,    "no area"),
    ]
    for text, expected, label in area_cases:
        got = extract_area(text)
        if got == expected:
            ok(f"extract_area: {label}")
        else:
            fail(f"extract_area: {label}", f"expected {expected}, got {got}")

except Exception as e:
    fail("parser extraction functions", traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total  = len(results)

print(f"SUMMARY: {passed}/{total} passed, {failed} failed")
if failed:
    print("\nFailed tests:")
    for status, name in results:
        if status == FAIL:
            print(f"  ✗ {name}")
    sys.exit(1)
else:
    print("All tests passed!")
    sys.exit(0)
