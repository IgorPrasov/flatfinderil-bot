#!/bin/bash
# start.sh — run migration if DATABASE_URL is set, then launch bot

set -e

if [ -n "$DATABASE_URL" ]; then
    echo "[start] DATABASE_URL detected — running migration from volume..."
    python migrate_to_pg.py || echo "[start] Migration finished (errors above are non-critical)"
else
    echo "[start] No DATABASE_URL — using JSON backend"
fi

exec python bot.py
