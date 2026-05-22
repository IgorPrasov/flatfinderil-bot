#!/usr/bin/env python3
"""
migrate_to_pg.py — Migrate listings_db.json → PostgreSQL.

Run once after deploying the PostgreSQL service:

    DATABASE_URL="postgresql://..." python migrate_to_pg.py

The script is idempotent: it skips listings whose source_url already
exists in the database, and uses INSERT … ON CONFLICT DO NOTHING for
fingerprints, favorites, subscriptions, and referrals.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database_pg as db
from psycopg2.extras import Json

# Check DATA_DIR (Railway volume) first, then fall back to script directory
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
JSON_FILE = os.path.join(_DATA_DIR, "listings_db.json")
if not os.path.exists(JSON_FILE):
    # fallback to bundled file next to script
    JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listings_db.json")

# ─── helpers ────────────────────────────────────────────────────────────────


def _info(msg: str):
    print(f"[migrate] {msg}", flush=True)


def _warn(msg: str):
    print(f"[migrate] WARNING: {msg}", flush=True, file=sys.stderr)


# ─── listings ────────────────────────────────────────────────────────────────


def migrate_listings(data: dict) -> dict:
    """Insert listings; return {old_str_id: new_int_id} mapping."""
    listings = data.get("listings", {})
    _info(f"Migrating {len(listings)} listings …")
    id_map: dict = {}
    ok = skip = err = 0
    for old_id, lst in listings.items():
        try:
            new_id = db.add_listing(dict(lst), skip_dedup=True)
            if new_id > 0:
                id_map[old_id] = new_id
                ok += 1
            else:
                skip += 1
        except Exception as exc:
            _warn(f"listing {old_id}: {exc}")
            err += 1
    _info(f"Listings: {ok} inserted, {skip} skipped, {err} errors")
    return id_map


# ─── fingerprints ────────────────────────────────────────────────────────────


def migrate_fingerprints(data: dict, id_map: dict):
    fps = data.get("listing_fingerprints", {})
    if not fps:
        return
    _info(f"Migrating {len(fps)} fingerprints …")
    ok = skip = 0
    with db._conn() as c:
        with c.cursor() as cur:
            for fp, _ in fps.items():
                try:
                    cur.execute(
                        "INSERT INTO listing_fingerprints (fingerprint) "
                        "VALUES (%s) ON CONFLICT DO NOTHING",
                        (fp,),
                    )
                    if cur.rowcount:
                        ok += 1
                    else:
                        skip += 1
                except Exception as exc:
                    _warn(f"fingerprint {fp[:20]}: {exc}")
    _info(f"Fingerprints: {ok} inserted, {skip} already existed")


# ─── favorites ───────────────────────────────────────────────────────────────


def migrate_favorites(data: dict, id_map: dict):
    favs = data.get("favorites", {})
    prices = data.get("favorites_prices", {})
    if not favs:
        return
    _info("Migrating favorites …")
    ok = skip = 0
    with db._conn() as c:
        with c.cursor() as cur:
            for uid, lid_list in favs.items():
                for old_lid in lid_list:
                    new_lid = id_map.get(str(old_lid))
                    if new_lid is None:
                        skip += 1
                        continue
                    price = prices.get(f"{uid}_{old_lid}", 0)
                    try:
                        cur.execute(
                            "INSERT INTO favorites (user_id, listing_id, price_at_save) "
                            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                            (int(uid), new_lid, price),
                        )
                        ok += 1
                    except Exception as exc:
                        _warn(f"favorite {uid}/{old_lid}: {exc}")
                        skip += 1
    _info(f"Favorites: {ok} inserted, {skip} skipped")


# ─── search subscriptions ─────────────────────────────────────────────────────


def migrate_subscriptions(data: dict):
    subs_all = data.get("subscriptions", {})
    if not subs_all:
        return
    count = sum(len(v) for v in subs_all.values())
    _info(f"Migrating {count} search subscriptions …")
    ok = 0
    with db._conn() as c:
        with c.cursor() as cur:
            for uid, subs in subs_all.items():
                for sub in subs:
                    try:
                        created = sub.get("created", datetime.now().isoformat())
                        last_checked = sub.get("last_checked", created)
                        last_ids = sub.get("last_result_ids", [])
                        sub_id = sub.get("id") or str(__import__("uuid").uuid4())
                        # Normalise UUID: if old id is "uid_index" format, generate a new UUID
                        try:
                            __import__("uuid").UUID(str(sub_id))
                        except ValueError:
                            sub_id = str(__import__("uuid").uuid4())
                        cur.execute(
                            "INSERT INTO search_subscriptions "
                            "    (id, user_id, filters, created_at, last_checked, "
                            "     last_result_ids, is_alert) "
                            "VALUES (%s, %s, %s, %s, %s, %s, FALSE) "
                            "ON CONFLICT (id) DO NOTHING",
                            (
                                sub_id, int(uid), Json(sub.get("filters", {})),
                                created, last_checked, Json(last_ids),
                            ),
                        )
                        ok += 1
                    except Exception as exc:
                        _warn(f"subscription {uid}: {exc}")
    _info(f"Search subscriptions: {ok} inserted")


# ─── alert subscriptions ──────────────────────────────────────────────────────


def migrate_alerts(data: dict):
    alerts_all = data.get("user_alerts", {})
    if not alerts_all:
        return
    count = sum(len(v) for v in alerts_all.values())
    _info(f"Migrating {count} alert subscriptions …")
    ok = 0
    with db._conn() as c:
        with c.cursor() as cur:
            for uid, alerts in alerts_all.items():
                for alert in alerts:
                    try:
                        alert_id = alert.get("id") or str(__import__("uuid").uuid4())
                        try:
                            __import__("uuid").UUID(str(alert_id))
                        except ValueError:
                            alert_id = str(__import__("uuid").uuid4())
                        created = alert.get("created", datetime.now().isoformat())
                        cur.execute(
                            "INSERT INTO search_subscriptions "
                            "    (id, user_id, filters, created_at, last_checked, "
                            "     last_result_ids, is_alert) "
                            "VALUES (%s, %s, %s, %s, %s, %s, TRUE) "
                            "ON CONFLICT (id) DO NOTHING",
                            (
                                alert_id, int(uid), Json(alert.get("filters", {})),
                                created, created, Json(alert.get("last_sent_ids", [])),
                            ),
                        )
                        ok += 1
                    except Exception as exc:
                        _warn(f"alert {uid}: {exc}")
    _info(f"Alert subscriptions: {ok} inserted")


# ─── alert expiries ───────────────────────────────────────────────────────────


def migrate_alert_expiries(data: dict):
    expiries = data.get("alert_expiry", {})
    if not expiries:
        return
    _info(f"Migrating {len(expiries)} alert expiries …")
    with db._conn() as c:
        with c.cursor() as cur:
            for uid, expiry in expiries.items():
                try:
                    cur.execute(
                        "INSERT INTO user_meta (user_id, alert_expiry) "
                        "VALUES (%s, %s) "
                        "ON CONFLICT (user_id) DO UPDATE SET alert_expiry = EXCLUDED.alert_expiry",
                        (int(uid), expiry),
                    )
                except Exception as exc:
                    _warn(f"alert_expiry {uid}: {exc}")
    _info("Alert expiries done")


# ─── referrals ───────────────────────────────────────────────────────────────


def migrate_referrals(data: dict):
    refs = data.get("referrals", {})
    if not refs:
        return
    _info("Migrating referrals …")
    ok = skip = 0
    with db._conn() as c:
        with c.cursor() as cur:
            for referrer_id, new_user_ids in refs.items():
                for new_uid in new_user_ids:
                    try:
                        cur.execute(
                            "INSERT INTO referrals (referrer_id, new_user_id) "
                            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (int(referrer_id), int(new_uid)),
                        )
                        if cur.rowcount:
                            ok += 1
                        else:
                            skip += 1
                    except Exception as exc:
                        _warn(f"referral {referrer_id}/{new_uid}: {exc}")
    _info(f"Referrals: {ok} inserted, {skip} already existed")


# ─── paid subscriptions ───────────────────────────────────────────────────────


def migrate_paid_subscriptions(data: dict):
    paid = data.get("paid_subscriptions", {})
    if not paid:
        return
    _info("Migrating paid subscriptions …")
    ok = 0
    with db._conn() as c:
        with c.cursor() as cur:
            for uid, plans in paid.items():
                if not isinstance(plans, dict):
                    continue
                for plan_type, expiry_iso in plans.items():
                    try:
                        cur.execute(
                            "INSERT INTO paid_subscriptions (user_id, plan_type, expiry_iso) "
                            "VALUES (%s, %s, %s) "
                            "ON CONFLICT (user_id, plan_type) DO UPDATE "
                            "  SET expiry_iso = EXCLUDED.expiry_iso",
                            (int(uid), plan_type, expiry_iso),
                        )
                        ok += 1
                    except Exception as exc:
                        _warn(f"paid_subscription {uid}/{plan_type}: {exc}")
    _info(f"Paid subscriptions: {ok} upserted")


# ─── listing credits ──────────────────────────────────────────────────────────


def migrate_listing_credits(data: dict):
    credits = data.get("listing_credits", {})
    free_used = data.get("listing_free_used", {})
    if not credits and not free_used:
        return
    _info("Migrating listing credits & free-listing flags …")
    with db._conn() as c:
        with c.cursor() as cur:
            for uid, rec in credits.items():
                if isinstance(rec, int):
                    rec = {"count": rec, "expiry": None}
                try:
                    cur.execute(
                        "INSERT INTO user_meta (user_id, listing_credits) "
                        "VALUES (%s, %s) "
                        "ON CONFLICT (user_id) DO UPDATE "
                        "  SET listing_credits = EXCLUDED.listing_credits",
                        (int(uid), Json(rec)),
                    )
                except Exception as exc:
                    _warn(f"listing_credits {uid}: {exc}")
            for uid, used in free_used.items():
                if not used:
                    continue
                try:
                    cur.execute(
                        "INSERT INTO user_meta (user_id, free_listing_used) "
                        "VALUES (%s, TRUE) "
                        "ON CONFLICT (user_id) DO UPDATE SET free_listing_used = TRUE",
                        (int(uid),),
                    )
                except Exception as exc:
                    _warn(f"free_listing_used {uid}: {exc}")
    _info("Listing credits done")


# ─── services ────────────────────────────────────────────────────────────────


def migrate_services(data: dict):
    services = data.get("services", {})
    if not services:
        return
    _info(f"Migrating {len(services)} services …")
    ok = skip = 0
    for sid, svc in services.items():
        try:
            db.add_service(dict(svc))
            ok += 1
        except Exception as exc:
            _warn(f"service {sid}: {exc}")
            skip += 1
    _info(f"Services: {ok} inserted, {skip} errors")


# ─── reviews ─────────────────────────────────────────────────────────────────


def migrate_reviews(data: dict, id_map: dict):
    reviews = data.get("reviews", {})
    if not reviews:
        return
    count = sum(len(v) for v in reviews.values())
    _info(f"Migrating {count} reviews …")
    ok = skip = 0
    for old_lid, rev_list in reviews.items():
        new_lid = id_map.get(str(old_lid))
        if new_lid is None:
            skip += len(rev_list)
            continue
        for rev in rev_list:
            try:
                db.add_review(
                    new_lid,
                    int(rev.get("user_id", 0)),
                    int(rev.get("rating", 3)),
                    rev.get("comment", ""),
                )
                ok += 1
            except Exception:
                skip += 1
    _info(f"Reviews: {ok} inserted, {skip} skipped")


# ─── main ────────────────────────────────────────────────────────────────────


def main():
    if not os.environ.get("DATABASE_URL"):
        sys.exit("ERROR: DATABASE_URL is not set.")

    if not os.path.exists(JSON_FILE):
        sys.exit(f"ERROR: JSON file not found: {JSON_FILE}")

    _info("Initialising PostgreSQL schema …")
    db._init_db()

    _info(f"Loading {JSON_FILE} …")
    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)

    id_map = migrate_listings(data)
    migrate_fingerprints(data, id_map)
    migrate_favorites(data, id_map)
    migrate_reviews(data, id_map)
    migrate_subscriptions(data)
    migrate_alerts(data)
    migrate_alert_expiries(data)
    migrate_referrals(data)
    migrate_paid_subscriptions(data)
    migrate_listing_credits(data)
    migrate_services(data)

    _info("Migration complete.")


if __name__ == "__main__":
    main()
