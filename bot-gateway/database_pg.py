"""
database_pg.py — PostgreSQL backend for FlatFinder IL.

Drop-in replacement for database.py.  Every public function has the
same signature and return type as its counterpart so callers only
need to change one import line:

    import database_pg as db
"""

import hashlib
import json
import logging
import os
import re
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json

log = logging.getLogger(__name__)

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

UNLIMITED_CREDITS = 999_999

_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if not DATABASE_URL:
                    raise EnvironmentError(
                        "DATABASE_URL is not set. "
                        "Set it to a valid PostgreSQL connection string."
                    )
                _pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    dsn=DATABASE_URL,
                    cursor_factory=RealDictCursor,
                )
    return _pool


class _Conn:
    """Context manager: borrow a connection from the pool and auto-return it."""

    def __enter__(self):
        self._c = _get_pool().getconn()
        return self._c

    def __exit__(self, exc_type, *_):
        if exc_type:
            self._c.rollback()
        else:
            self._c.commit()
        _get_pool().putconn(self._c)


def _conn() -> _Conn:
    return _Conn()


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def _listing_row(row) -> Optional[Dict]:
    """Convert a DB row (RealDictRow) to the dict format callers expect."""
    if row is None:
        return None
    d = dict(row)
    # JSONB fields are already Python objects via psycopg2
    if not isinstance(d.get("photos"), list):
        d["photos"] = []
    if not isinstance(d.get("infrastructure"), list):
        d["infrastructure"] = []
    d["rooms"] = str(d.get("rooms") or "")
    d["floor"] = d.get("floor") or 0
    d["area_sqm"] = d.get("area_sqm") or 0
    d["price"] = d.get("price") or 0
    d["views"] = d.get("views") or 0
    d["view_requests"] = d.get("view_requests") or 0
    d["active"] = bool(d.get("active", True))
    # Merge extra JSONB fields back into the dict so legacy callers find them
    extra = d.pop("extra", None) or {}
    d.update(extra)
    # Serialize date for backward-compat (callers expect strings)
    if d.get("date_added") and hasattr(d["date_added"], "isoformat"):
        d["date_added"] = d["date_added"].isoformat()
    return d


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def _init_db():
    """Execute schema.sql to create tables if they don't exist."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    if not os.path.exists(schema_path):
        log.warning("schema.sql not found — skipping _init_db()")
        return
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql)
    log.info("PostgreSQL schema initialised.")


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------

def _text_fingerprint(text: str) -> str:
    """SHA-256 hex of the normalised first-200 chars of text."""
    t = re.sub(r"\s+", "", text.lower())
    t = re.sub(r"[^\wЀ-ӿא-ת]", "", t)
    t = t[:200]
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Core listing functions
# ---------------------------------------------------------------------------

def add_listing(listing_data: Dict, skip_dedup: bool = False) -> int:
    """
    Insert a new listing.  Returns the assigned id, or -1 if it is a
    duplicate / blacklisted.

    The optional *skip_dedup* flag bypasses fingerprint / URL checks
    (used by the migration script).
    """
    desc = listing_data.get("description", "")
    source = listing_data.get("source", "")

    with _conn() as c:
        with c.cursor() as cur:
            # ── text fingerprint dedup ──────────────────────────────────────
            if not skip_dedup and desc and source in ("facebook", "telegram"):
                fp = _text_fingerprint(desc)
                cur.execute(
                    "SELECT 1 FROM listing_fingerprints WHERE fingerprint = %s",
                    (fp,),
                )
                if cur.fetchone():
                    return -1
                cur.execute(
                    "INSERT INTO listing_fingerprints (fingerprint, listing_id) "
                    "VALUES (%s, NULL) ON CONFLICT DO NOTHING",
                    (fp,),
                )

            # ── source_url dedup ───────────────────────────────────────────
            if not skip_dedup:
                url = (listing_data.get("source_url") or "").strip()
                if url:
                    cur.execute(
                        "SELECT id FROM listings WHERE source_url = %s LIMIT 1",
                        (url,),
                    )
                    if cur.fetchone():
                        return -1

            # ── phone classification (optional) ────────────────────────────
            if not skip_dedup and source in ("facebook", "telegram") and \
                    not listing_data.get("user_id"):
                try:
                    from classifier import process_listing_phones  # type: ignore
                    listing_data, _, should_save = process_listing_phones(
                        listing_data, {}
                    )
                    if not should_save:
                        return -1
                except Exception:
                    pass  # classifier is optional

            # ── build INSERT ───────────────────────────────────────────────
            now = datetime.now()
            listing_data.setdefault("date_added", now.strftime("%Y-%m-%d"))
            listing_data.setdefault("active", True)
            listing_data.setdefault("views", 0)
            listing_data.setdefault("view_requests", 0)
            listing_data.setdefault("poster_type", "unknown")
            listing_data.setdefault("seller_type", "private")

            # Known scalar columns
            cols = {
                "title", "description", "property_type", "city", "district",
                "neighborhood", "rooms", "price", "deal_type", "parking", "pool",
                "contact", "source", "source_url", "active", "views",
                "view_requests", "poster_type", "poster_name", "poster_phone",
                "poster_username", "lat", "lng", "ai_score", "is_duplicate",
                "is_suspicious", "suspicion_reason", "seller_type", "user_id",
                "deal_closed", "deal_id",
            }
            # Columns needing type coercion
            int_cols = {"floor", "floors_total"}
            float_cols = {"area_sqm"}
            json_cols = {"photos", "infrastructure"}
            date_col = "date_added"

            fields: List[str] = []
            values: List = []
            extra: Dict = {}

            for k, v in listing_data.items():
                if k == "id":
                    continue
                if k == date_col:
                    fields.append(k)
                    values.append(v)
                elif k in json_cols:
                    fields.append(k)
                    values.append(Json(v if isinstance(v, list) else []))
                elif k in int_cols:
                    fields.append(k)
                    try:
                        values.append(int(float(str(v))) if v not in (None, "") else None)
                    except (ValueError, TypeError):
                        values.append(None)
                elif k in float_cols:
                    fields.append(k)
                    try:
                        values.append(float(v) if v not in (None, "") else 0.0)
                    except (ValueError, TypeError):
                        values.append(0.0)
                elif k in cols:
                    fields.append(k)
                    values.append(v)
                else:
                    # unknown column → stash in extra JSONB
                    extra[k] = v

            if extra:
                fields.append("extra")
                values.append(Json(extra))

            placeholders = ", ".join(["%s"] * len(fields))
            col_list = ", ".join(fields)
            cur.execute(
                f"INSERT INTO listings ({col_list}) VALUES ({placeholders}) RETURNING id",
                values,
            )
            new_id = cur.fetchone()["id"]

            # ── update fingerprint with real listing_id ────────────────────
            if not skip_dedup and desc and source in ("facebook", "telegram"):
                cur.execute(
                    "UPDATE listing_fingerprints SET listing_id = %s WHERE fingerprint = %s",
                    (new_id, _text_fingerprint(desc)),
                )

            # ── user_listings index ────────────────────────────────────────
            uid = listing_data.get("user_id")
            if uid:
                cur.execute(
                    "INSERT INTO user_listings (user_id, listing_id) "
                    "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (int(uid), new_id),
                )

    # background translation (optional)
    try:
        from translator import schedule_pre_translate  # type: ignore
        schedule_pre_translate(new_id, listing_data)
    except Exception:
        pass

    return new_id


def get_listing(listing_id: int) -> Optional[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM listings WHERE id = %s", (listing_id,))
            return _listing_row(cur.fetchone())


def get_all_listings(limit: int = None) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '15000'")
            if limit is not None:
                cur.execute(
                    "SELECT * FROM listings WHERE active = TRUE ORDER BY id LIMIT %s",
                    (limit,),
                )
            else:
                cur.execute("SELECT * FROM listings WHERE active = TRUE ORDER BY id")
            return [_listing_row(r) for r in cur.fetchall()]


def get_all_listings_for_export() -> List[Dict]:
    """Same as get_all_listings — convenience alias for data exports."""
    return get_all_listings()


def get_user_listings(user_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT l.* FROM listings l
                JOIN user_listings ul ON ul.listing_id = l.id
                WHERE ul.user_id = %s
                ORDER BY l.id
                """,
                (user_id,),
            )
            return [_listing_row(r) for r in cur.fetchall()]


def count_user_private_listings_this_month(user_id: int) -> int:
    """Count active private listings published by user in the last 30 days."""
    cutoff = (datetime.now() - timedelta(days=30)).date()
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM listings l
                JOIN user_listings ul ON ul.listing_id = l.id
                WHERE ul.user_id = %s
                  AND l.seller_type = 'private'
                  AND l.active = TRUE
                  AND l.date_added >= %s
                """,
                (user_id, cutoff),
            )
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0


def update_listing(listing_id: int, fields: dict) -> bool:
    """Update arbitrary fields on a listing."""
    if not fields:
        return False

    scalar_cols = {
        "title", "description", "property_type", "city", "district",
        "neighborhood", "rooms", "floor", "floors_total", "area_sqm", "price",
        "deal_type", "parking", "pool", "contact", "source", "source_url",
        "active", "views", "view_requests", "poster_type", "poster_name",
        "poster_phone", "poster_username", "lat", "lng", "ai_score",
        "is_duplicate", "is_suspicious", "suspicion_reason", "seller_type",
        "user_id", "deal_closed", "deal_id",
    }
    json_cols = {"photos", "infrastructure"}

    set_parts: List[str] = []
    values: List = []
    extra_updates: Dict = {}

    for k, v in fields.items():
        if k in json_cols:
            set_parts.append(f"{k} = %s")
            values.append(Json(v))
        elif k in scalar_cols:
            set_parts.append(f"{k} = %s")
            values.append(v)
        else:
            extra_updates[k] = v

    if extra_updates:
        set_parts.append("extra = extra || %s")
        values.append(Json(extra_updates))

    if not set_parts:
        return False

    values.append(listing_id)
    sql = f"UPDATE listings SET {', '.join(set_parts)} WHERE id = %s"
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, values)
            return cur.rowcount > 0


def delete_listing(listing_id: int, user_id: int) -> bool:
    """Remove a listing (user must own it)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "DELETE FROM user_listings WHERE listing_id = %s AND user_id = %s",
                (listing_id, user_id),
            )
            cur.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
            return cur.rowcount > 0


def admin_delete_listing(listing_id: int) -> bool:
    """Hard-delete a listing (admin, no ownership check)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
            return cur.rowcount > 0


# ---------------------------------------------------------------------------
# View counters
# ---------------------------------------------------------------------------

def increment_views(listing_id: int):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE listings SET views = views + 1 WHERE id = %s",
                (listing_id,),
            )


def increment_view_requests(listing_id: int):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE listings SET view_requests = view_requests + 1 WHERE id = %s",
                (listing_id,),
            )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_listings(filters: Dict, limit: int = 200) -> List[Dict]:
    """
    Build a dynamic SQL WHERE clause from the filters dict and return
    matching active listings. limit caps rows returned from the DB.
    """
    clauses: List[str] = ["active = TRUE"]
    params: List = []

    deal_type = filters.get("deal_type")
    if deal_type:
        clauses.append("deal_type = %s")
        params.append(deal_type)

    property_types = filters.get("property_types") or []
    if property_types:
        clauses.append("property_type = ANY(%s)")
        params.append(property_types)

    districts = filters.get("districts") or []
    if districts:
        clauses.append("district = ANY(%s)")
        params.append(districts)

    cities = filters.get("cities") or []
    if cities:
        clauses.append("city = ANY(%s)")
        params.append(cities)
    elif filters.get("city"):
        clauses.append("city = %s")
        params.append(filters["city"])

    rooms_min = filters.get("rooms_min")
    if rooms_min is not None:
        try:
            m = float(str(rooms_min).replace("+", ""))
            clauses.append(
                "(rooms ~ '^[0-9]+(\\.[0-9]+)?$' "
                " AND rooms::float >= %s)"
            )
            params.append(m)
        except (ValueError, TypeError):
            pass

    rooms_max = filters.get("rooms_max")
    if rooms_max is not None:
        try:
            m = float(str(rooms_max).replace("+", ""))
            clauses.append(
                "(rooms ~ '^[0-9]+(\\.[0-9]+)?$' "
                " AND rooms::float <= %s)"
            )
            params.append(m)
        except (ValueError, TypeError):
            pass

    price_min = filters.get("price_min")
    if price_min is not None:
        clauses.append("price > 0 AND price >= %s")
        params.append(int(price_min))

    price_max = filters.get("price_max")
    if price_max is not None:
        clauses.append("price > 0 AND price <= %s")
        params.append(int(price_max))

    parking_min = filters.get("parking_min")
    if parking_min is not None:
        clauses.append("parking >= %s")
        params.append(int(parking_min))

    if filters.get("pool") is True:
        clauses.append("pool = TRUE")

    infra = filters.get("infrastructure") or []
    if infra:
        # listing must have ALL requested infrastructure values
        clauses.append("infrastructure @> %s")
        params.append(Json(infra))

    if filters.get("with_photos"):
        clauses.append("jsonb_array_length(photos) > 0")

    where = " AND ".join(clauses)
    sql = f"SELECT * FROM listings WHERE {where} ORDER BY id DESC LIMIT %s"
    params.append(limit)

    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
            return [_listing_row(r) for r in cur.fetchall()]


def get_listings_by_tier(filters: Dict, is_premium: bool) -> List[Dict]:
    """Return search results filtered by subscription tier."""
    try:
        from classifier import filter_for_tier  # type: ignore
        return filter_for_tier(search_listings(filters), is_premium)
    except Exception:
        return search_listings(filters)


def get_all_listings_admin(filters: Optional[Dict] = None) -> List[Dict]:
    """Return ALL listings (active + inactive) for back-office."""
    clauses: List[str] = []
    params: List = []

    if filters:
        q = (filters.get("q") or "").lower()
        if q:
            clauses.append(
                "(LOWER(title) LIKE %s OR LOWER(description) LIKE %s)"
            )
            like = f"%{q}%"
            params.extend([like, like])
        city = (filters.get("city") or "").lower()
        if city:
            clauses.append("LOWER(city) LIKE %s")
            params.append(f"%{city}%")
        deal = filters.get("deal_type")
        if deal:
            clauses.append("deal_type = %s")
            params.append(deal)
        ptype = filters.get("property_type")
        if ptype:
            clauses.append("property_type = %s")
            params.append(ptype)
        active = filters.get("active")
        if active is not None:
            clauses.append("active = %s")
            params.append(bool(active))

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM listings {where} ORDER BY date_added DESC, id DESC"
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
            return [_listing_row(r) for r in cur.fetchall()]


def get_similar_listings(listing: Dict) -> List[Dict]:
    """Active listings in same city / property_type / deal_type, excluding self."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM listings
                WHERE active = TRUE
                  AND id != %s
                  AND city = %s
                  AND property_type = %s
                  AND deal_type = %s
                  AND price > 0
                ORDER BY id DESC
                """,
                (
                    listing.get("id", 0),
                    listing.get("city", ""),
                    listing.get("property_type", ""),
                    listing.get("deal_type", ""),
                ),
            )
            return [_listing_row(r) for r in cur.fetchall()]


def get_stale_listings(days: int = 30) -> List[Dict]:
    """Active listings with view requests that haven't been closed for *days* days."""
    cutoff = (datetime.now() - timedelta(days=days)).date()
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM listings
                WHERE active = TRUE
                  AND deal_closed = FALSE
                  AND view_requests > 0
                  AND date_added <= %s
                ORDER BY date_added
                """,
                (cutoff,),
            )
            return [_listing_row(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

def toggle_favorite(user_id: int, listing_id: int) -> bool:
    """Toggle favorite. Returns True if added, False if removed."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM favorites WHERE user_id = %s AND listing_id = %s",
                (user_id, listing_id),
            )
            if cur.fetchone():
                cur.execute(
                    "DELETE FROM favorites WHERE user_id = %s AND listing_id = %s",
                    (user_id, listing_id),
                )
                return False
            # Get current price to save
            cur.execute("SELECT price FROM listings WHERE id = %s", (listing_id,))
            row = cur.fetchone()
            price = row["price"] if row else 0
            cur.execute(
                "INSERT INTO favorites (user_id, listing_id, price_at_save) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (user_id, listing_id, price),
            )
            return True


def get_favorites(user_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT l.* FROM listings l
                JOIN favorites f ON f.listing_id = l.id
                WHERE f.user_id = %s
                ORDER BY l.id
                """,
                (user_id,),
            )
            return [_listing_row(r) for r in cur.fetchall()]


def get_all_favorites_with_prices() -> Dict:
    """Return {uid_lid: saved_price} for all favorites."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT user_id, listing_id, price_at_save FROM favorites")
            return {
                f"{r['user_id']}_{r['listing_id']}": (r["price_at_save"] or 0)
                for r in cur.fetchall()
            }


def update_favorite_price(user_id: int, listing_id: int, new_price: int):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE favorites SET price_at_save = %s "
                "WHERE user_id = %s AND listing_id = %s",
                (new_price, user_id, listing_id),
            )


# ---------------------------------------------------------------------------
# Search subscriptions
# ---------------------------------------------------------------------------

def add_search_subscription(user_id: int, filters: Dict) -> str:
    """Save search filters as a subscription. Returns sub_id (UUID)."""
    sub_id = str(uuid.uuid4())
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO search_subscriptions
                    (id, user_id, filters, created_at, last_checked, last_result_ids, is_alert)
                VALUES (%s, %s, %s, NOW(), NOW(), %s, FALSE)
                """,
                (sub_id, user_id, Json(filters), Json([])),
            )
    return sub_id


def get_user_subscriptions(user_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM search_subscriptions "
                "WHERE user_id = %s AND is_alert = FALSE "
                "ORDER BY created_at",
                (user_id,),
            )
            rows = cur.fetchall()
    result = []
    for i, r in enumerate(rows):
        result.append({
            "id": str(r["id"]),
            "filters": r["filters"] or {},
            "created": r["created_at"].isoformat() if r["created_at"] else "",
            "last_checked": r["last_checked"].isoformat() if r["last_checked"] else "",
            "last_result_ids": r["last_result_ids"] or [],
            "_index": i,
        })
    return result


def remove_search_subscription(user_id: int, sub_index: int):
    """Remove subscription by its position in the user's subscription list."""
    subs = get_user_subscriptions(user_id)
    if 0 <= sub_index < len(subs):
        sub_id = subs[sub_index]["id"]
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "DELETE FROM search_subscriptions WHERE id = %s AND user_id = %s",
                    (sub_id, user_id),
                )


def get_all_subscriptions() -> Dict:
    """Return {str(user_id): [sub_dicts]} for all users."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM search_subscriptions WHERE is_alert = FALSE ORDER BY user_id, created_at"
            )
            rows = cur.fetchall()
    result: Dict[str, List] = {}
    # Track per-user index
    user_idx: Dict[int, int] = {}
    for r in rows:
        uid = str(r["user_id"])
        idx = user_idx.get(r["user_id"], 0)
        user_idx[r["user_id"]] = idx + 1
        result.setdefault(uid, []).append({
            "id": str(r["id"]),
            "filters": r["filters"] or {},
            "created": r["created_at"].isoformat() if r["created_at"] else "",
            "last_checked": r["last_checked"].isoformat() if r["last_checked"] else "",
            "last_result_ids": r["last_result_ids"] or [],
            "_index": idx,
        })
    return result


def update_subscription_last_checked(user_id: int, sub_index: int, last_result_ids: List):
    """Update last_checked + last_result_ids for subscription at position sub_index."""
    subs = get_user_subscriptions(user_id)
    if 0 <= sub_index < len(subs):
        sub_id = subs[sub_index]["id"]
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE search_subscriptions "
                    "SET last_checked = NOW(), last_result_ids = %s "
                    "WHERE id = %s",
                    (Json(last_result_ids), sub_id),
                )


# ---------------------------------------------------------------------------
# Alert subscriptions (paid)
# ---------------------------------------------------------------------------

ALERT_PLAN_DAYS = 30


def is_alert_active(user_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT alert_expiry FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row or not row["alert_expiry"]:
        return False
    return row["alert_expiry"] > datetime.now(row["alert_expiry"].tzinfo)


def set_alert_expiry(user_id: int, days: int = ALERT_PLAN_DAYS):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT alert_expiry FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            existing = row["alert_expiry"] if row else None
            base = (
                max(existing, datetime.now(existing.tzinfo))
                if existing
                else datetime.now()
            )
            new_expiry = base + timedelta(days=days)
            cur.execute(
                """
                INSERT INTO user_meta (user_id, alert_expiry)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET alert_expiry = EXCLUDED.alert_expiry
                """,
                (user_id, new_expiry),
            )


def get_alert_expiry(user_id: int) -> Optional[str]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT alert_expiry FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row or not row["alert_expiry"]:
        return None
    return row["alert_expiry"].isoformat()


def add_alert(user_id: int, filters: Dict) -> str:
    """Add an alert filter. Returns alert_id (UUID)."""
    sub_id = str(uuid.uuid4())
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO search_subscriptions
                    (id, user_id, filters, created_at, last_checked, last_result_ids, is_alert)
                VALUES (%s, %s, %s, NOW(), NOW(), %s, TRUE)
                """,
                (sub_id, user_id, Json(filters), Json([])),
            )
    return sub_id


def get_user_alerts(user_id: int) -> list:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM search_subscriptions "
                "WHERE user_id = %s AND is_alert = TRUE "
                "ORDER BY created_at",
                (user_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(r["id"]),
            "filters": r["filters"] or {},
            "created": r["created_at"].isoformat() if r["created_at"] else "",
            "last_sent_ids": r["last_result_ids"] or [],
            "last_checked": r["last_checked"].isoformat() if r["last_checked"] else "",
        }
        for r in rows
    ]


def delete_alert(user_id: int, alert_id: str):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "DELETE FROM search_subscriptions WHERE id = %s AND user_id = %s",
                (alert_id, user_id),
            )


def get_all_alerts() -> Dict:
    """Return {str(user_id): [alert_dicts]} for all users with alerts."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM search_subscriptions WHERE is_alert = TRUE ORDER BY user_id, created_at"
            )
            rows = cur.fetchall()
    result: Dict[str, List] = {}
    for r in rows:
        uid = str(r["user_id"])
        result.setdefault(uid, []).append({
            "id": str(r["id"]),
            "filters": r["filters"] or {},
            "created": r["created_at"].isoformat() if r["created_at"] else "",
            "last_sent_ids": r["last_result_ids"] or [],
            "last_checked": r["last_checked"].isoformat() if r["last_checked"] else "",
        })
    return result


def update_alert_sent(user_id: int, alert_id: str, sent_ids: list):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE search_subscriptions "
                "SET last_result_ids = %s, last_checked = NOW() "
                "WHERE id = %s AND user_id = %s",
                (Json(sent_ids[-200:]), alert_id, user_id),
            )


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def add_review(listing_id: int, user_id: int, rating: int, comment: str = "") -> bool:
    try:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO reviews (listing_id, user_id, rating, comment) "
                    "VALUES (%s, %s, %s, %s)",
                    (listing_id, user_id, rating, comment),
                )
        return True
    except psycopg2.errors.UniqueViolation:
        return False
    except Exception as exc:
        log.warning("add_review error: %s", exc)
        return False


def get_reviews(listing_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT user_id, rating, comment, created_at "
                "FROM reviews WHERE listing_id = %s ORDER BY created_at",
                (listing_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "user_id": str(r["user_id"]),
            "rating": r["rating"],
            "comment": r["comment"] or "",
            "date": r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else "",
        }
        for r in rows
    ]


def get_average_rating(listing_id: int):
    """Returns (avg_rating, count) or (None, 0)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT AVG(rating)::numeric(4,1) AS avg, COUNT(*) AS cnt "
                "FROM reviews WHERE listing_id = %s",
                (listing_id,),
            )
            row = cur.fetchone()
    if not row or not row["cnt"]:
        return None, 0
    return float(row["avg"]), int(row["cnt"])


def user_has_reviewed(listing_id: int, user_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM reviews WHERE listing_id = %s AND user_id = %s",
                (listing_id, user_id),
            )
            return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

def add_referral(referrer_id: int, new_user_id: int) -> bool:
    try:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO referrals (referrer_id, new_user_id) VALUES (%s, %s)",
                    (referrer_id, new_user_id),
                )
        return True
    except psycopg2.errors.UniqueViolation:
        return False


def get_referral_count(user_id: int) -> int:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM referrals WHERE referrer_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return int(row["cnt"]) if row else 0


# ---------------------------------------------------------------------------
# Bonus days (referral reward)
# ---------------------------------------------------------------------------

def add_bonus_days(user_id: int, days: int):
    """Add bonus subscription days to a user's pool."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_meta (user_id, bonus_expiry)
                VALUES (%s, NOW() + %s * INTERVAL '1 day')
                ON CONFLICT (user_id) DO UPDATE
                  SET bonus_expiry = COALESCE(user_meta.bonus_expiry, NOW())
                                     + %s * INTERVAL '1 day'
                """,
                (user_id, days, days),
            )


def get_bonus_days(user_id: int) -> int:
    """Return remaining bonus days (rounded down)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT bonus_expiry FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row or not row["bonus_expiry"]:
        return 0
    now = datetime.now(row["bonus_expiry"].tzinfo)
    remaining = (row["bonus_expiry"] - now).days
    return max(0, remaining)


def get_bonus_expiry(user_id: int):
    """Return expiry datetime if user has bonus days, else None."""
    days = get_bonus_days(user_id)
    if days > 0:
        return datetime.now() + timedelta(days=days)
    return None


# ---------------------------------------------------------------------------
# Paid subscriptions
# ---------------------------------------------------------------------------

def get_user_paid_subscriptions(user_id: int) -> dict:
    """Return {plan_type: iso_expiry_string}."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT plan_type, expiry_iso FROM paid_subscriptions WHERE user_id = %s",
                (user_id,),
            )
            rows = cur.fetchall()
    return {r["plan_type"]: r["expiry_iso"].isoformat() for r in rows if r["expiry_iso"]}


def set_user_paid_subscription(user_id: int, plan_type: str, expiry_iso: str):
    """Upsert paid subscription. Raises on verification failure."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paid_subscriptions (user_id, plan_type, expiry_iso)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, plan_type) DO UPDATE SET expiry_iso = EXCLUDED.expiry_iso
                """,
                (user_id, plan_type, expiry_iso),
            )
    # verify
    subs = get_user_paid_subscriptions(user_id)
    if plan_type not in subs:
        raise IOError(
            f"Subscription save verification failed for user {user_id} plan {plan_type}"
        )


# ---------------------------------------------------------------------------
# Trial warning tracking
# ---------------------------------------------------------------------------

def was_trial_warning_sent(user_id: int, threshold: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT trial_warning FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row or not row["trial_warning"]:
        return False
    tw = row["trial_warning"]
    return bool(tw.get(str(threshold)))


def mark_trial_warning_sent(user_id: int, threshold: int):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_meta (user_id, trial_warning)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                  SET trial_warning = user_meta.trial_warning || EXCLUDED.trial_warning
                """,
                (user_id, Json({str(threshold): True})),
            )


# ---------------------------------------------------------------------------
# Listing credits
# ---------------------------------------------------------------------------

def get_listing_credits(user_id: int) -> int:
    """Return available listing slots (0 if expired or none)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT listing_credits FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row or not row["listing_credits"]:
        return 0
    rec = row["listing_credits"]
    count = rec.get("count", 0)
    if count <= 0:
        return 0
    expiry = rec.get("expiry")
    if expiry and expiry < datetime.now().strftime("%Y-%m-%d"):
        return 0
    return count


def add_listing_credits(user_id: int, count: int, duration_days: int = 30):
    """Add purchased listing slots with an expiry date."""
    existing = get_listing_credits(user_id)
    expiry = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    new_rec = Json({"count": existing + count, "expiry": expiry})
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_meta (user_id, listing_credits)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET listing_credits = EXCLUDED.listing_credits
                """,
                (user_id, new_rec),
            )


def use_listing_credit(user_id: int) -> bool:
    """Consume one slot. Returns True if successful."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT listing_credits FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row or not row["listing_credits"]:
        return False
    rec = row["listing_credits"]
    count = rec.get("count", 0)
    expiry = rec.get("expiry")
    if count <= 0:
        return False
    if expiry and expiry < datetime.now().strftime("%Y-%m-%d"):
        return False
    if count < UNLIMITED_CREDITS:
        new_rec = Json({"count": count - 1, "expiry": expiry})
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE user_meta SET listing_credits = %s WHERE user_id = %s",
                    (new_rec, user_id),
                )
    return True


def has_used_free_listing(user_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT free_listing_used FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return bool(row["free_listing_used"]) if row else False


def mark_free_listing_used(user_id: int):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_meta (user_id, free_listing_used)
                VALUES (%s, TRUE)
                ON CONFLICT (user_id) DO UPDATE SET free_listing_used = TRUE
                """,
                (user_id,),
            )


# ---------------------------------------------------------------------------
# Service subscriptions
# ---------------------------------------------------------------------------

def set_service_subscription(service_id: str, plan_key: str, expiry_iso: str):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service_subscriptions (service_id, plan_key, expiry)
                VALUES (%s, %s, %s)
                ON CONFLICT (service_id) DO UPDATE
                  SET plan_key = EXCLUDED.plan_key, expiry = EXCLUDED.expiry
                """,
                (str(service_id), plan_key, expiry_iso),
            )


def get_service_subscription(service_id: str) -> dict:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT plan_key, expiry FROM service_subscriptions WHERE service_id = %s",
                (str(service_id),),
            )
            row = cur.fetchone()
    if not row:
        return {}
    return {
        "plan_key": row["plan_key"],
        "expiry": row["expiry"].isoformat() if row["expiry"] else "",
    }


# ---------------------------------------------------------------------------
# Lead balance
# ---------------------------------------------------------------------------

def get_lead_balance(user_id: int) -> int:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT lead_balance FROM user_meta WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return int(row["lead_balance"]) if row and row["lead_balance"] is not None else 0


def add_lead_balance(user_id: int, amount_ils: int) -> int:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_meta (user_id, lead_balance)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                  SET lead_balance = COALESCE(user_meta.lead_balance, 0) + %s
                RETURNING lead_balance
                """,
                (user_id, amount_ils, amount_ils),
            )
            row = cur.fetchone()
    return int(row["lead_balance"]) if row else amount_ils


def spend_lead_balance(user_id: int, amount_ils: int):
    """Deduct amount if sufficient. Returns (success, new_balance)."""
    current = get_lead_balance(user_id)
    if current < amount_ils:
        return False, current
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE user_meta SET lead_balance = lead_balance - %s "
                "WHERE user_id = %s AND lead_balance >= %s "
                "RETURNING lead_balance",
                (amount_ils, user_id, amount_ils),
            )
            row = cur.fetchone()
    if not row:
        return False, current
    return True, int(row["lead_balance"])


def mark_lead_unlocked(user_id: int, lead_id: str) -> bool:
    try:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO unlocked_leads (user_id, lead_id) VALUES (%s, %s)",
                    (user_id, lead_id),
                )
        return True
    except psycopg2.errors.UniqueViolation:
        return False


def has_unlocked_lead(user_id: int, lead_id: str) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM unlocked_leads WHERE user_id = %s AND lead_id = %s",
                (user_id, lead_id),
            )
            return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def add_service(svc_data: dict) -> int:
    scalar_cols = {
        "service_type", "name", "phone", "city", "region", "description",
        "price", "subscription_ils", "active", "views", "user_id", "date_added",
    }
    fields: List[str] = []
    values: List = []
    extra: Dict = {}

    now_date = datetime.now().strftime("%Y-%m-%d")
    svc_data.setdefault("date_added", now_date)
    svc_data.setdefault("active", True)

    for k, v in svc_data.items():
        if k == "id":
            continue
        if k in scalar_cols:
            fields.append(k)
            values.append(v)
        else:
            extra[k] = v

    if extra:
        fields.append("extra")
        values.append(Json(extra))

    placeholders = ", ".join(["%s"] * len(fields))
    col_list = ", ".join(fields)
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                f"INSERT INTO services ({col_list}) VALUES ({placeholders}) RETURNING id",
                values,
            )
            return cur.fetchone()["id"]


def get_all_services() -> list:
    """Return ALL services (active and inactive) for admin/analytics use."""
    order = (
        "CASE WHEN extra->>'promo_expiry' IS NOT NULL "
        "     AND (extra->>'promo_expiry')::timestamp > NOW() "
        "THEN 0 ELSE 1 END, id"
    )
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '7000'")
            cur.execute(f"SELECT * FROM services ORDER BY {order}")
            rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        extra = d.pop("extra", None) or {}
        d.update(extra)
        result.append(d)
    return result


def get_all_service_subscriptions() -> dict:
    """Return all service subscriptions as {service_id_str: {plan_key, expiry}}."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '7000'")
            cur.execute("SELECT service_id, plan_key, expiry FROM service_subscriptions")
            rows = cur.fetchall()
    result = {}
    for r in rows:
        result[str(r["service_id"])] = {
            "plan_key": r["plan_key"],
            "expiry": r["expiry"].isoformat() if r["expiry"] else "",
        }
    return result


def activate_service_promo(user_id: int, expiry_iso: str) -> int:
    """Set promo_expiry on all active services belonging to user_id. Returns rows updated."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                UPDATE services
                   SET extra = extra || %s
                 WHERE user_id = %s::text
                   AND active = TRUE
                """,
                (Json({"promo_expiry": expiry_iso}), str(user_id)),
            )
            return cur.rowcount


def get_services(svc_type: str = None, region: str = None, city: str = None) -> list:
    clauses = ["s.active = TRUE"]
    params: List = []
    if svc_type:
        clauses.append("s.service_type = %s")
        params.append(svc_type)
    if region and region != "all":
        clauses.append("(s.region = 'all' OR s.region = %s)")
        params.append(region)
    if city and city != "all":
        clauses.append("(s.city IS NULL OR s.city = %s)")
        params.append(city)
    where = " AND ".join(clauses)
    # Promoted providers (active promo_expiry) come first
    order = (
        "CASE WHEN s.extra->>'promo_expiry' IS NOT NULL "
        "     AND (s.extra->>'promo_expiry')::timestamp > NOW() "
        "THEN 0 ELSE 1 END, s.id"
    )
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(f"SELECT * FROM services s WHERE {where} ORDER BY {order}", params)
            rows = cur.fetchall()
    now_iso = datetime.utcnow().isoformat()
    result = []
    for r in rows:
        if r.get("service_type") == "moving":
            sub = get_service_subscription(str(r["id"]))
            if not sub or sub.get("expiry", "") < now_iso:
                continue
        d = dict(r)
        extra = d.pop("extra", None) or {}
        d.update(extra)
        result.append(d)
    return result


def update_service(service_id: str, fields: dict) -> bool:
    scalar_cols = {
        "service_type", "name", "phone", "city", "region", "description",
        "price", "subscription_ils", "active", "views", "user_id",
    }
    set_parts: List[str] = []
    values: List = []
    extra: Dict = {}
    for k, v in fields.items():
        if k in scalar_cols:
            set_parts.append(f"{k} = %s")
            values.append(v)
        else:
            extra[k] = v
    if extra:
        set_parts.append("extra = extra || %s")
        values.append(Json(extra))
    if not set_parts:
        return False
    values.append(int(service_id))
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                f"UPDATE services SET {', '.join(set_parts)} WHERE id = %s",
                values,
            )
            return cur.rowcount > 0


def delete_service(service_id: str) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM services WHERE id = %s", (int(service_id),))
            return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Deal tracking
# ---------------------------------------------------------------------------

def record_view_requester(listing_id: int, user_id: int, username: str = "", name: str = ""):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO view_requesters (listing_id, user_id, username, name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (listing_id, user_id) DO NOTHING
                """,
                (listing_id, user_id, username, name),
            )


def get_view_requesters(listing_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, name, date_added FROM view_requesters "
                "WHERE listing_id = %s ORDER BY date_added",
                (listing_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "user_id": r["user_id"],
            "username": r["username"] or "",
            "name": r["name"] or "",
            "date": r["date_added"].isoformat() if r["date_added"] else "",
        }
        for r in rows
    ]


def close_deal(
    listing_id: int,
    owner_id: int,
    tenant_id: int,
    listed_price: int,
    deal_price: int,
) -> int:
    listing = get_listing(listing_id)
    days_to_close = 0
    if listing and listing.get("date_added"):
        try:
            from datetime import date as _date
            d0 = _date.fromisoformat(str(listing["date_added"]))
            days_to_close = (_date.today() - d0).days
        except Exception:
            pass

    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO closed_deals
                    (listing_id, owner_id, tenant_id, listed_price, deal_price,
                     deal_type, property_type, city, rooms, days_to_close,
                     closed_at, confirmed_by, tenant_confirmed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, 'owner', FALSE)
                RETURNING id
                """,
                (
                    listing_id, owner_id, tenant_id, listed_price,
                    deal_price or listed_price,
                    listing.get("deal_type", "rent") if listing else "rent",
                    listing.get("property_type", "apartment") if listing else "apartment",
                    listing.get("city", "") if listing else "",
                    listing.get("rooms", "") if listing else "",
                    days_to_close,
                ),
            )
            deal_id = cur.fetchone()["id"]
            cur.execute(
                "UPDATE listings SET active = FALSE, deal_closed = TRUE, deal_id = %s "
                "WHERE id = %s",
                (deal_id, listing_id),
            )
    return deal_id


def tenant_confirm_deal(deal_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE closed_deals SET tenant_confirmed = TRUE, confirmed_by = 'both' "
                "WHERE id = %s",
                (deal_id,),
            )
            return cur.rowcount > 0


def get_closed_deals() -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM closed_deals ORDER BY id")
            return [dict(r) for r in cur.fetchall()]


def get_user_closed_deals(user_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM closed_deals WHERE owner_id = %s OR tenant_id = %s ORDER BY id",
                (user_id, user_id),
            )
            return [dict(r) for r in cur.fetchall()]


def get_listing_deal(listing_id: int) -> Optional[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM closed_deals WHERE listing_id = %s ORDER BY id DESC LIMIT 1",
                (listing_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_deal_stats() -> Dict:
    deals = get_closed_deals()
    if not deals:
        return {
            "total": 0, "avg_days": 0, "avg_price_diff_pct": 0,
            "by_city": {}, "by_type": {}, "both_confirmed": 0,
        }
    total = len(deals)
    avg_days = round(sum(d.get("days_to_close", 0) for d in deals) / total)
    both = sum(1 for d in deals if d.get("confirmed_by") == "both")
    diffs = []
    for d in deals:
        lp, dp = d.get("listed_price", 0), d.get("deal_price", 0)
        if lp and dp:
            diffs.append((dp - lp) / lp * 100)
    avg_diff = round(sum(diffs) / len(diffs), 1) if diffs else 0
    by_city: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for d in deals:
        by_city[d.get("city", "?")] = by_city.get(d.get("city", "?"), 0) + 1
        by_type[d.get("deal_type", "rent")] = by_type.get(d.get("deal_type", "rent"), 0) + 1
    return {
        "total": total,
        "avg_days": avg_days,
        "avg_price_diff_pct": avg_diff,
        "by_city": by_city,
        "by_type": by_type,
        "both_confirmed": both,
    }


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

VALID_DEAL_STATUSES = {"new", "in_progress", "done", "cancelled"}


def add_crm_contact(contact_data: dict) -> int:
    scalar_cols = {
        "user_id", "name", "phone", "notes", "contact_type",
        "region", "city", "active",
    }
    fields = ["active", "created_at"]
    values: List = [True, datetime.now()]
    extra: Dict = {}
    for k, v in contact_data.items():
        if k == "id":
            continue
        if k in scalar_cols:
            fields.append(k)
            values.append(v)
        else:
            extra[k] = v
    if extra:
        fields.append("extra")
        values.append(Json(extra))
    col_list = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                f"INSERT INTO crm_contacts ({col_list}) VALUES ({placeholders}) RETURNING id",
                values,
            )
            return cur.fetchone()["id"]


def get_crm_contact(contact_id: int) -> Optional[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM crm_contacts WHERE id = %s", (contact_id,))
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    extra = d.pop("extra", None) or {}
    d.update(extra)
    return d


def get_crm_contacts(
    contact_type: str = None,
    region: str = None,
    city: str = None,
    active_only: bool = True,
) -> List[Dict]:
    clauses: List[str] = []
    params: List = []
    if active_only:
        clauses.append("active = TRUE")
    if contact_type:
        clauses.append("contact_type = %s")
        params.append(contact_type)
    if region and region != "all":
        clauses.append("region = %s")
        params.append(region)
    if city and city != "all":
        clauses.append("city = %s")
        params.append(city)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '10000'")
            cur.execute(f"SELECT * FROM crm_contacts {where} ORDER BY id", params)
            rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        extra = d.pop("extra", None) or {}
        d.update(extra)
        result.append(d)
    return result


def update_crm_contact(contact_id: int, fields: dict) -> bool:
    scalar_cols = {
        "user_id", "name", "phone", "notes", "contact_type",
        "region", "city", "active",
    }
    set_parts: List[str] = []
    values: List = []
    extra: Dict = {}
    for k, v in fields.items():
        if k in scalar_cols:
            set_parts.append(f"{k} = %s")
            values.append(v)
        else:
            extra[k] = v
    if extra:
        set_parts.append("extra = extra || %s")
        values.append(Json(extra))
    if not set_parts:
        return False
    values.append(contact_id)
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                f"UPDATE crm_contacts SET {', '.join(set_parts)} WHERE id = %s",
                values,
            )
            return cur.rowcount > 0


def deactivate_crm_contact(contact_id: int) -> bool:
    return update_crm_contact(contact_id, {"active": False})


def add_crm_deal(deal_data: dict) -> int:
    scalar_cols = {"user_id", "contact_id", "listing_id", "status", "notes"}
    fields = ["created_at", "updated_at"]
    values: List = [datetime.now(), datetime.now()]
    extra: Dict = {}
    for k, v in deal_data.items():
        if k == "id":
            continue
        if k in scalar_cols:
            fields.append(k)
            values.append(v)
        else:
            extra[k] = v
    if extra:
        fields.append("extra")
        values.append(Json(extra))
    col_list = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                f"INSERT INTO crm_deals ({col_list}) VALUES ({placeholders}) RETURNING id",
                values,
            )
            return cur.fetchone()["id"]


def get_crm_deals(contact_id: int = None, status: str = None) -> List[Dict]:
    clauses: List[str] = []
    params: List = []
    if contact_id:
        clauses.append("contact_id = %s")
        params.append(contact_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '10000'")
            cur.execute(
                f"SELECT * FROM crm_deals {where} ORDER BY created_at DESC",
                params,
            )
            rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        extra = d.pop("extra", None) or {}
        d.update(extra)
        result.append(d)
    return result


def update_crm_deal_status(deal_id: int, status: str) -> bool:
    if status not in VALID_DEAL_STATUSES:
        return False
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE crm_deals SET status = %s, updated_at = NOW() WHERE id = %s",
                (status, deal_id),
            )
            return cur.rowcount > 0


def add_crm_note(contact_id: int, text: str, author_id: int):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO crm_notes (contact_id, text, author_id) VALUES (%s, %s, %s)",
                (contact_id, text, author_id),
            )


def get_crm_notes(contact_id: int) -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT text, author_id, created_at FROM crm_notes "
                "WHERE contact_id = %s ORDER BY created_at",
                (contact_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "text": r["text"],
            "author_id": r["author_id"],
            "date": r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "",
        }
        for r in rows
    ]


def get_crm_stats() -> Dict:
    contacts = get_crm_contacts(active_only=True)
    deals = get_crm_deals()
    by_type: Dict[str, int] = {}
    for c in contacts:
        t = c.get("contact_type", "agent")
        by_type[t] = by_type.get(t, 0) + 1
    deals_by_status: Dict[str, int] = {}
    for d in deals:
        s = d.get("status", "new")
        deals_by_status[s] = deals_by_status.get(s, 0) + 1
    recent_deals = sorted(deals, key=lambda x: str(x.get("created_at", "")), reverse=True)[:5]
    with _conn() as c_conn:
        with c_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM crm_notes")
            note_row = cur.fetchone()
    total_notes = int(note_row["cnt"]) if note_row else 0
    return {
        "total_contacts": len(contacts),
        "by_type": by_type,
        "total_deals": len(deals),
        "deals_by_status": deals_by_status,
        "total_notes": total_notes,
        "recent_deals": recent_deals,
    }


# ---------------------------------------------------------------------------
# Agent profiles
# ---------------------------------------------------------------------------

def save_agent_email(user_id: int, email: str, lang: str = "ru"):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_profiles (user_id, email, lang)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET email = EXCLUDED.email, lang = EXCLUDED.lang
                """,
                (user_id, email, lang),
            )


def get_agent_email(user_id: int) -> Optional[str]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT email FROM agent_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
    return row["email"] if row else None


def get_all_agent_emails() -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT user_id, email FROM agent_profiles WHERE email IS NOT NULL AND email != ''"
            )
            return [{"user_id": r["user_id"], "email": r["email"]} for r in cur.fetchall()]


def get_agent_report_data(user_id: int) -> Dict:
    import datetime as _dt
    listings = get_user_listings(user_id)
    active = [l for l in listings if l.get("active")]
    total_views = sum(l.get("views", 0) for l in active)
    email = get_agent_email(user_id) or ""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT owner_name, lang FROM agent_profiles WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    owner_name = row["owner_name"] if row and row["owner_name"] else ""
    lang = row["lang"] if row and row["lang"] else "ru"
    listing_stats = sorted(
        [
            {
                "id": l["id"],
                "title": l.get("title", "—"),
                "city": l.get("city", "—"),
                "rooms": l.get("rooms", "—"),
                "price": l.get("price", 0),
                "deal_type": l.get("deal_type", "—"),
                "views": l.get("views", 0),
                "view_requests": l.get("view_requests", 0),
                "date_added": l.get("date_added", "—"),
            }
            for l in active
        ],
        key=lambda x: x["views"],
        reverse=True,
    )
    return {
        "user_id": user_id,
        "email": email,
        "owner_name": owner_name,
        "lang": lang,
        "total_listings": len(active),
        "total_views": total_views,
        "listings": listing_stats,
        "week": _dt.date.today().strftime("%d.%m.%Y"),
    }


def get_all_users_admin() -> List[Dict]:
    """Return merged user info for back-office."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT ul.user_id,
                       array_agg(ul.listing_id) AS listing_ids,
                       COUNT(ul.listing_id) FILTER (WHERE l.active) AS active_listings,
                       COUNT(ul.listing_id) AS total_listings,
                       ap.email, ap.lang, ap.owner_name, ap.owner_phone
                FROM user_listings ul
                LEFT JOIN listings l ON l.id = ul.listing_id
                LEFT JOIN agent_profiles ap ON ap.user_id = ul.user_id
                GROUP BY ul.user_id, ap.email, ap.lang, ap.owner_name, ap.owner_phone
                ORDER BY total_listings DESC
                """
            )
            rows = cur.fetchall()
    return [
        {
            "user_id": str(r["user_id"]),
            "listing_ids": list(r["listing_ids"]) if r["listing_ids"] else [],
            "active_listings": int(r["active_listings"] or 0),
            "total_listings": int(r["total_listings"] or 0),
            "email": r["email"],
            "lang": r["lang"],
            "owner_name": r["owner_name"],
            "owner_phone": r["owner_phone"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Service profiles
# ---------------------------------------------------------------------------

def save_service_email(user_id: int, email: str):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service_profiles (user_id, email)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET email = EXCLUDED.email
                """,
                (user_id, email),
            )


def get_service_email(user_id) -> Optional[str]:
    if user_id is None:
        return None
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT email FROM service_profiles WHERE user_id = %s", (int(user_id),))
            row = cur.fetchone()
    return row["email"] if row else None


def get_all_service_emails() -> List[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT sp.user_id, sp.email, s.service_type, s.extra
                FROM service_profiles sp
                LEFT JOIN services s ON s.user_id = sp.user_id
                WHERE sp.email IS NOT NULL AND sp.email != ''
                """
            )
            rows = cur.fetchall()
    result = []
    seen: set = set()
    for r in rows:
        uid = r["user_id"]
        if uid in seen:
            continue
        seen.add(uid)
        extra = r["extra"] or {}
        result.append({
            "user_id": uid,
            "email": r["email"],
            "service_type": r["service_type"] or "",
            "owner_name": extra.get("owner_name", ""),
            "lang": extra.get("lang", "ru"),
        })
    return result


def get_service_report_data(user_id: int) -> Dict:
    import datetime as _dt
    email = get_service_email(user_id) or ""
    services = get_services()
    user_svcs = [s for s in services if str(s.get("user_id", "")) == str(user_id)]
    total_views = sum(s.get("views", 0) for s in user_svcs)
    return {
        "user_id": user_id,
        "email": email,
        "owner_name": user_svcs[0].get("owner_name", "") if user_svcs else "",
        "lang": user_svcs[0].get("lang", "ru") if user_svcs else "ru",
        "service_type": user_svcs[0].get("service_type", "") if user_svcs else "",
        "total_services": len(user_svcs),
        "total_views": total_views,
        "services": sorted(user_svcs, key=lambda x: x.get("views", 0), reverse=True),
        "week": _dt.date.today().strftime("%d.%m.%Y"),
    }


# ---------------------------------------------------------------------------
# Support messages
# ---------------------------------------------------------------------------

def add_support_message(
    user_id: int, username: str, first_name: str, lang: str, text: str
) -> int:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO support_messages (user_id, username, first_name, lang, text) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (user_id, username, first_name, lang, text),
            )
            return cur.fetchone()["id"]


def get_support_messages(limit: int = 100) -> list:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM support_messages ORDER BY date DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def delete_support_message(msg_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM support_messages WHERE id = %s", (msg_id,))
            return cur.rowcount > 0


def mark_support_message_read(msg_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE support_messages SET read = TRUE WHERE id = %s",
                (msg_id,),
            )
            return cur.rowcount > 0


def reply_support_message(msg_id: int, reply_text: str) -> Optional[dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE support_messages SET reply = %s, read = TRUE "
                "WHERE id = %s RETURNING *",
                (reply_text, msg_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# App settings (generic key-value, covers ig_session, fb_cookies, etc.)
# ---------------------------------------------------------------------------

def get_setting(key: str) -> str:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = cur.fetchone()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )


def get_ig_session() -> str:
    return get_setting("ig_session")


def set_ig_session(sessionid: str):
    set_setting("ig_session", sessionid)


def get_ig_settings_json() -> str:
    return get_setting("ig_settings_json")


def set_ig_settings_json(settings_json: str):
    set_setting("ig_settings_json", settings_json)


def get_fb_cookies() -> str:
    return get_setting("fb_cookies_json")


def set_fb_cookies(cookies_json: str):
    set_setting("fb_cookies_json", cookies_json)


# ---------------------------------------------------------------------------
# Client leads
# ---------------------------------------------------------------------------

def save_client_lead(lead: dict) -> str:
    lead_id = str(int(datetime.utcnow().timestamp() * 1000))
    scalar_cols = {"type", "city"}
    extra: Dict = {}
    for k, v in lead.items():
        if k not in scalar_cols:
            extra[k] = v
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO client_leads (id, type, city, status, buyers, created_at, extra) "
                "VALUES (%s, %s, %s, 'open', %s, NOW(), %s)",
                (lead_id, lead.get("type", ""), lead.get("city", ""), Json([]), Json(extra)),
            )
    return lead_id


def get_available_leads(svc_type: str, provider_city: str = "") -> list:
    clauses = ["type = %s", "status = 'open'", "created_at > NOW() - INTERVAL '72 hours'"]
    params: List = [svc_type]
    if provider_city:
        clauses.append("(city IS NULL OR city = '' OR city = %s)")
        params.append(provider_city)
    where = " AND ".join(clauses)
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                f"SELECT * FROM client_leads WHERE {where} ORDER BY created_at DESC",
                params,
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_lead_by_id(lead_id: str) -> Optional[Dict]:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM client_leads WHERE id = %s", (str(lead_id),))
            row = cur.fetchone()
    return dict(row) if row else None


def record_lead_purchase(lead_id: str, provider_id: int) -> bool:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT buyers FROM client_leads WHERE id = %s", (str(lead_id),))
            row = cur.fetchone()
    if not row:
        return False
    buyers = row["buyers"] or []
    if str(provider_id) in [str(b) for b in buyers]:
        return False
    buyers.append(provider_id)
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE client_leads SET buyers = %s WHERE id = %s",
                (Json(buyers), str(lead_id)),
            )
    return True


def cleanup_expired_leads(hours: int = 72) -> int:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "DELETE FROM client_leads WHERE created_at < NOW() - %s * INTERVAL '1 hour'",
                (hours,),
            )
            return cur.rowcount


def get_provider_unlocked_leads(user_id: int) -> list:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT cl.* FROM client_leads cl "
                "JOIN unlocked_leads ul ON ul.lead_id = cl.id "
                "WHERE ul.user_id = %s ORDER BY cl.created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_lead_marketplace_stats() -> dict:
    try:
        from pricing import CLEANING_LEAD_PRICE_ILS, PACKING_LEAD_PRICE_ILS  # type: ignore
    except Exception:
        CLEANING_LEAD_PRICE_ILS = PACKING_LEAD_PRICE_ILS = 0

    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT type, city, buyers FROM client_leads")
            leads = cur.fetchall()
            cur.execute(
                "SELECT COALESCE(SUM(lead_balance), 0) AS total FROM user_meta"
            )
            balance_row = cur.fetchone()

    total = len(leads)
    cleaning = [l for l in leads if l["type"] == "cleaning"]
    packing = [l for l in leads if l["type"] == "packing"]
    revenue_cleaning = sum(len(l["buyers"] or []) * CLEANING_LEAD_PRICE_ILS for l in cleaning)
    revenue_packing = sum(len(l["buyers"] or []) * PACKING_LEAD_PRICE_ILS for l in packing)
    by_city: Dict[str, int] = {}
    for l in leads:
        c_name = l["city"] or "—"
        by_city[c_name] = by_city.get(c_name, 0) + 1
    top_cities = sorted(by_city.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "total_leads": total,
        "cleaning_leads": len(cleaning),
        "packing_leads": len(packing),
        "revenue_cleaning": revenue_cleaning,
        "revenue_packing": revenue_packing,
        "revenue_total": revenue_cleaning + revenue_packing,
        "top_cities": [{"city": c, "count": n} for c, n in top_cities],
        "total_balance_held": int(balance_row["total"]) if balance_row else 0,
    }


def add_pending_lead_trigger(user_id: int, trigger_type: str, city: str, send_after_iso: str):
    with _conn() as c:
        with c.cursor() as cur:
            # Deduplicate: skip if already a pending unsent trigger of same type for this user
            cur.execute(
                "SELECT 1 FROM pending_lead_triggers "
                "WHERE user_id = %s AND type = %s AND sent = FALSE",
                (user_id, trigger_type),
            )
            if cur.fetchone():
                return
            cur.execute(
                "INSERT INTO pending_lead_triggers (user_id, type, city, send_after) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, trigger_type, city, send_after_iso),
            )


def pop_due_lead_triggers() -> list:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE pending_lead_triggers SET sent = TRUE "
                "WHERE sent = FALSE AND send_after <= NOW() "
                "RETURNING *"
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Phone classifier helpers
# ---------------------------------------------------------------------------

def report_phone_db(phone: str, reporter_id: int, reason: str = "spam") -> dict:
    try:
        from classifier import report_phone, _ensure_classifier_tables  # type: ignore
        data: dict = {}
        data = _ensure_classifier_tables(data)
        data = report_phone(phone, reporter_id, reason, data)
        strikes = len({r["reporter_id"] for r in data.get("phone_reports", {}).get(phone, [])})
        blacklisted = phone in data.get("phone_blacklist", {})
        status = "blacklisted" if blacklisted else "reported"
        return {"status": status, "strikes": strikes}
    except Exception as exc:
        log.warning("report_phone_db error: %s", exc)
        return {"status": "error", "strikes": 0}


def get_phone_stats(phone: str) -> dict:
    try:
        from classifier import _ensure_classifier_tables  # type: ignore
        data: dict = {}
        data = _ensure_classifier_tables(data)
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        posts = data.get("phone_post_counts", {}).get(phone, [])
        recent = [p for p in posts if p.get("date", "") >= cutoff]
        return {
            "phone": phone,
            "is_agent": phone in data.get("phone_agents", {}),
            "is_blacklisted": phone in data.get("phone_blacklist", {}),
            "posts_last_30d": len(recent),
            "total_reports": len(
                {r["reporter_id"] for r in data.get("phone_reports", {}).get(phone, [])}
            ),
            "blacklist_info": data.get("phone_blacklist", {}).get(phone),
            "agent_info": data.get("phone_agents", {}).get(phone),
        }
    except Exception:
        return {"phone": phone, "is_agent": False, "is_blacklisted": False,
                "posts_last_30d": 0, "total_reports": 0,
                "blacklist_info": None, "agent_info": None}


# ── bot_users ──────────────────────────────────────────────────────────────────

def upsert_bot_user(user_id: int, username: str = None, first_name: str = None,
                    last_name: str = None, lang: str = "ru") -> None:
    """Insert or update a bot user record (called on every /start)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO bot_users(user_id, username, first_name, last_name, lang, first_seen, last_seen)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT(user_id) DO UPDATE SET
                    username   = COALESCE(EXCLUDED.username,   bot_users.username),
                    first_name = COALESCE(EXCLUDED.first_name, bot_users.first_name),
                    last_name  = COALESCE(EXCLUDED.last_name,  bot_users.last_name),
                    lang       = EXCLUDED.lang,
                    last_seen  = NOW()
            """, (user_id, username, first_name, last_name, lang))
        c.commit()


def get_bot_users_count() -> int:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bot_users")
            return cur.fetchone()["count"]


def get_all_bot_users(limit: int = 500, offset: int = 0) -> list:
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("""
                SELECT bu.user_id, bu.username, bu.first_name, bu.last_name,
                       bu.lang, bu.first_seen, bu.last_seen,
                       COUNT(ul.listing_id) AS total_listings,
                       COUNT(ul.listing_id) FILTER (WHERE l.active) AS active_listings,
                       ap.email, ap.owner_name, ap.owner_phone
                FROM bot_users bu
                LEFT JOIN user_listings ul ON ul.user_id = bu.user_id
                LEFT JOIN listings l ON l.id = ul.listing_id
                LEFT JOIN agent_profiles ap ON ap.user_id = bu.user_id
                GROUP BY bu.user_id, ap.email, ap.owner_name, ap.owner_phone
                ORDER BY bu.last_seen DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            rows = cur.fetchall()
    return [
        {
            "user_id": str(r["user_id"]),
            "username": r["username"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "lang": r["lang"],
            "first_seen": r["first_seen"].isoformat() if r["first_seen"] else None,
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            "total_listings": int(r["total_listings"] or 0),
            "active_listings": int(r["active_listings"] or 0),
            "email": r["email"],
            "owner_name": r["owner_name"],
            "owner_phone": r["owner_phone"],
        }
        for r in rows
    ]


def get_sources_stats() -> dict:
    """Return stats on parsing sources (Telegram channels, Facebook groups)."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("""
                SELECT source_url,
                       COUNT(*) AS cnt,
                       MAX(date_added) AS last_seen
                FROM listings
                WHERE source_url IS NOT NULL AND source_url != ''
                GROUP BY source_url
                ORDER BY cnt DESC
            """)
            rows = cur.fetchall()

    telegram, facebook, other = [], [], []
    for r in rows:
        url = r["source_url"] or ""
        entry = {"url": url, "count": r["cnt"],
                 "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None}
        # extract channel/group name
        if "t.me/" in url:
            parts = url.replace("https://","").replace("http://","").split("/")
            entry["name"] = "@" + parts[1] if len(parts) > 1 else url
            telegram.append(entry)
        elif "facebook.com/" in url or "fb.com/" in url:
            parts = url.replace("https://","").replace("http://","").split("/")
            entry["name"] = parts[2] if len(parts) > 2 else url
            facebook.append(entry)
        else:
            entry["name"] = url[:50]
            other.append(entry)

    # Aggregate by channel (strip post ID)
    def _agg(items):
        agg = {}
        for item in items:
            name = item["name"]
            if name not in agg:
                agg[name] = {"name": name, "count": 0, "last_seen": item["last_seen"]}
            agg[name]["count"] += item["count"]
        return sorted(agg.values(), key=lambda x: x["count"], reverse=True)

    return {
        "telegram": _agg(telegram),
        "facebook": _agg(facebook),
        "other":    _agg(other),
        "total_telegram": sum(e["count"] for e in telegram),
        "total_facebook": sum(e["count"] for e in facebook),
    }


def _load() -> dict:
    """
    Backward-compatibility shim: read listings_db.json from volume.
    Used by legacy code (analytics, backoffice) that hasn't been migrated to PG queries.
    New code should use proper PG functions instead.
    """
    import json as _json
    data_dir = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(data_dir, "listings_db.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            pass
    return {"listings": {}, "favorites": {}, "user_listings": {}, "next_id": 1}
