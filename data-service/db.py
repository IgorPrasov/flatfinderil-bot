import os
import psycopg2
import psycopg2.pool
import psycopg2.extras

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=os.environ["DATABASE_URL"],
        )
    return _pool


def execute(query: str, params=None) -> list[dict]:
    """Execute a SELECT query and return rows as dicts."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        pool.putconn(conn)


def execute_one(query: str, params=None) -> dict | None:
    """Execute a SELECT query and return the first row as a dict, or None."""
    rows = execute(query, params)
    return rows[0] if rows else None


def execute_write(query: str, params=None) -> dict | None:
    """Execute an INSERT/UPDATE/DELETE with optional RETURNING clause."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            conn.commit()
            try:
                row = cur.fetchone()
                return dict(row) if row else None
            except psycopg2.ProgrammingError:
                return None
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def notify(channel: str, payload: str = "") -> None:
    """Send a PostgreSQL NOTIFY on the given channel."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT pg_notify(%s, %s)", (channel, payload))
            conn.commit()
    finally:
        pool.putconn(conn)
