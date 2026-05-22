#!/usr/bin/env python3
"""
restore_users.py — Restore user data from volume listings_db.json → PostgreSQL.

Migrates: user_listings, paid_subscriptions, agent_profiles,
          user_meta (trial_warnings, lang, referral_bonuses, free_listing_used)

Run inside Railway or with DATABASE_URL + DATA_DIR set:
    DATABASE_URL="postgresql://..." DATA_DIR=/data python restore_users.py
"""
import json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    sys.exit("ERROR: DATABASE_URL not set")

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
JSON_FILE = os.path.join(DATA_DIR, "listings_db.json")
if not os.path.exists(JSON_FILE):
    sys.exit(f"ERROR: {JSON_FILE} not found")

def info(msg): print(f"[restore] {msg}", flush=True)

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

with open(JSON_FILE, encoding="utf-8") as f:
    data = json.load(f)

# ── 1. user_listings ─────────────────────────────────────────────────────────
user_listings = data.get("user_listings", {})
info(f"user_listings: {len(user_listings)} users found in JSON")
ok = skip = 0
for user_id_str, listing_ids in user_listings.items():
    try:
        uid = int(user_id_str)
    except ValueError:
        continue
    for lid in listing_ids:
        try:
            cur.execute(
                "INSERT INTO user_listings(user_id, listing_id) VALUES(%s, %s) ON CONFLICT DO NOTHING",
                (uid, int(lid))
            )
            ok += 1
        except Exception:
            conn.rollback()
            skip += 1
conn.commit()
info(f"user_listings: {ok} inserted, {skip} skipped")

# ── 2. paid_subscriptions ────────────────────────────────────────────────────
paid = data.get("paid_subscriptions", {})
info(f"paid_subscriptions: {len(paid)} found in JSON")
ok = skip = 0
for user_id_str, sub in paid.items():
    try:
        uid = int(user_id_str)
        plan = sub.get("plan", "unknown")
        expiry = sub.get("expiry")
        expiry_dt = datetime.fromisoformat(expiry) if expiry else None
        cur.execute(
            "INSERT INTO paid_subscriptions(user_id, plan_type, expiry_iso) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (uid, plan, expiry_dt)
        )
        ok += 1
    except Exception as e:
        conn.rollback()
        skip += 1
        info(f"  WARNING paid_sub {user_id_str}: {e}")
conn.commit()
info(f"paid_subscriptions: {ok} inserted, {skip} skipped")

# ── 3. agent_profiles ────────────────────────────────────────────────────────
agents = data.get("agent_profiles", {})
info(f"agent_profiles: {len(agents)} found in JSON")
ok = skip = 0
for user_id_str, profile in agents.items():
    try:
        uid = int(user_id_str)
        cur.execute("""
            INSERT INTO agent_profiles(user_id, email, lang, owner_name, owner_phone, extra)
            VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id) DO UPDATE SET
                email=EXCLUDED.email, lang=EXCLUDED.lang,
                owner_name=EXCLUDED.owner_name, owner_phone=EXCLUDED.owner_phone,
                extra=EXCLUDED.extra
        """, (
            uid,
            profile.get("email"),
            profile.get("lang", "ru"),
            profile.get("owner_name") or profile.get("name"),
            profile.get("owner_phone") or profile.get("phone"),
            json.dumps({k: v for k, v in profile.items()
                        if k not in ("email","lang","owner_name","name","owner_phone","phone")})
        ))
        ok += 1
    except Exception as e:
        conn.rollback()
        skip += 1
        info(f"  WARNING agent {user_id_str}: {e}")
conn.commit()
info(f"agent_profiles: {ok} inserted/updated, {skip} skipped")

# ── 4. user_meta: lang, trial_warnings, referral_bonuses, free_listing_used ──
user_meta: dict = {}  # user_id → meta dict

# language preferences (stored as top-level keys user_lang_<uid>)
for key, value in data.items():
    if key.startswith("user_lang_"):
        try:
            uid = int(key.split("_", 2)[2])
            if uid not in user_meta:
                user_meta[uid] = {}
            user_meta[uid]["lang"] = value
        except (ValueError, IndexError):
            pass

# trial_warnings_sent
for uid_str in data.get("trial_warnings_sent", {}).keys():
    try:
        uid = int(uid_str)
        if uid not in user_meta:
            user_meta[uid] = {}
        user_meta[uid]["trial_warning_sent"] = True
    except ValueError:
        pass

# referral_bonuses
for uid_str, bonus in data.get("referral_bonuses", {}).items():
    try:
        uid = int(uid_str)
        if uid not in user_meta:
            user_meta[uid] = {}
        user_meta[uid]["referral_bonus"] = bonus
    except ValueError:
        pass

# free_listing_used
for uid_str in data.get("listing_free_used", {}).keys():
    try:
        uid = int(uid_str)
        if uid not in user_meta:
            user_meta[uid] = {}
        user_meta[uid]["free_listing_used"] = True
    except ValueError:
        pass

info(f"user_meta: {len(user_meta)} users found")
ok = skip = 0
for uid, meta in user_meta.items():
    try:
        cur.execute("""
            INSERT INTO user_meta(user_id, free_listing_used, trial_warning, listing_credits)
            VALUES(%s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                free_listing_used = EXCLUDED.free_listing_used OR user_meta.free_listing_used,
                trial_warning = user_meta.trial_warning || EXCLUDED.trial_warning
        """, (
            uid,
            meta.get("free_listing_used", False),
            json.dumps({"sent": meta.get("trial_warning_sent", False),
                        "lang": meta.get("lang", "ru"),
                        "referral_bonus": meta.get("referral_bonus")}),
            json.dumps({"count": 0, "expiry": None})
        ))
        ok += 1
    except Exception as e:
        conn.rollback()
        skip += 1
conn.commit()
info(f"user_meta: {ok} inserted/updated, {skip} skipped")

# ── 5. Summary ───────────────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM user_listings"); info(f"→ user_listings in PG: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM paid_subscriptions"); info(f"→ paid_subscriptions in PG: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM agent_profiles"); info(f"→ agent_profiles in PG: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM user_meta"); info(f"→ user_meta in PG: {cur.fetchone()[0]}")

# ── 6. Users derived from listings ───────────────────────────────────────────
cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_listings")
info(f"→ unique users who posted listings: {cur.fetchone()[0]}")

conn.close()
info("Done!")
