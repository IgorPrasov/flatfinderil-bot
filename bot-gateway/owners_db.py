"""
owners_db.py — база контактов людей, публикующих объявления в Telegram-каналах.
Собирается двумя способами:
  1. Sender info из Telethon (user_id, username, имя) — для групп
  2. Извлечение телефонов и @username из текста объявления — для всех каналов
"""
import json
import os
import re
from datetime import datetime

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
OWNERS_FILE = os.path.join(_DATA_DIR, "owners_db.json")


def _load():
    if os.path.exists(OWNERS_FILE):
        try:
            with open(OWNERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"owners": {}}


def _save(data):
    with open(OWNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _merge(owner: dict, **kwargs):
    for k, v in kwargs.items():
        if v:
            owner[k] = v


def upsert_from_sender(user_id: int, username=None, first_name=None,
                       last_name=None, phone=None, channel: str = None):
    """Сохранить отправителя сообщения из Telethon (реальный пользователь, не канал)."""
    data = _load()
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")

    if uid not in data["owners"]:
        data["owners"][uid] = {"user_id": user_id, "first_seen": today,
                                "listings_count": 0, "channels": []}
    o = data["owners"][uid]
    o["last_seen"] = today
    _merge(o, username=username, first_name=first_name,
           last_name=last_name, phone=phone)
    if channel and channel not in o.get("channels", []):
        o.setdefault("channels", []).append(channel)
    o["listings_count"] = o.get("listings_count", 0) + 1
    _save(data)


def upsert_from_text(text: str, channel: str = None, source_url: str = None):
    """Извлечь телефоны и @username из текста объявления и сохранить."""
    today = datetime.now().strftime("%Y-%m-%d")
    data = _load()
    changed = False

    # ── Израильские телефоны ──────────────────────────────────────────────────
    raw_phones = re.findall(
        r'(?:\+972|972|0)[\s\-]?(?:5[0-9]|[23489])[\s\-]?\d{3}[\s\-]?\d{3,4}',
        text
    )
    phones = list({re.sub(r'[\s\-]', '', p) for p in raw_phones})

    for phone in phones:
        key = f"phone_{phone}"
        if key not in data["owners"]:
            data["owners"][key] = {"user_id": None, "phone": phone,
                                    "first_seen": today, "listings_count": 0,
                                    "channels": []}
        o = data["owners"][key]
        o["last_seen"] = today
        if channel and channel not in o.get("channels", []):
            o.setdefault("channels", []).append(channel)
        o["listings_count"] = o.get("listings_count", 0) + 1
        if source_url:
            o.setdefault("source_urls", [])
            if len(o["source_urls"]) < 10 and source_url not in o["source_urls"]:
                o["source_urls"].append(source_url)
        changed = True

    # ── @username упоминания в тексте ─────────────────────────────────────────
    usernames = re.findall(r'(?<!\w)@([a-zA-Z0-9_]{5,32})(?!\w)', text)
    for username in usernames:
        # Skip channel names we already know
        if username.lower() in {c.lower() for c in [channel] if channel}:
            continue
        key = f"@{username}"
        if key not in data["owners"]:
            data["owners"][key] = {"user_id": None, "username": username,
                                    "first_seen": today, "listings_count": 0,
                                    "channels": []}
        o = data["owners"][key]
        o["last_seen"] = today
        if channel and channel not in o.get("channels", []):
            o.setdefault("channels", []).append(channel)
        o["listings_count"] = o.get("listings_count", 0) + 1
        changed = True

    if changed:
        _save(data)


def get_all_owners(sort_by: str = "listings_count") -> list:
    data = _load()
    owners = list(data["owners"].values())
    return sorted(owners, key=lambda x: x.get(sort_by, 0), reverse=True)


def get_stats() -> dict:
    owners = get_all_owners()
    with_phone = sum(1 for o in owners if o.get("phone"))
    with_username = sum(1 for o in owners if o.get("username"))
    with_name = sum(1 for o in owners if o.get("first_name"))
    return {
        "total": len(owners),
        "with_phone": with_phone,
        "with_username": with_username,
        "with_name": with_name,
    }
