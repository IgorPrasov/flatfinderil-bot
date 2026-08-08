"""
Background alert checker for FlatFinderIL.

Runs every CHECK_INTERVAL_SEC, finds new listings added since last check,
matches against each user's alert filters, sends Telegram notifications.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import database as db

logger = logging.getLogger("alert_checker")

CHECK_INTERVAL_SEC = 300   # 5 minutes
MAX_PER_ALERT      = 3     # max listings per notification batch


def _matches(listing: dict, filters: dict) -> bool:
    """Return True if listing satisfies alert filters."""
    if filters.get("deal_type") and listing.get("deal_type") != filters["deal_type"]:
        return False
    if filters.get("city") and listing.get("city") != filters["city"]:
        return False
    if filters.get("district") and listing.get("district") != filters["district"]:
        return False
    if filters.get("rooms_min"):
        try:
            r = float(str(listing.get("rooms", "0")).replace("+", ""))
            if r < float(filters["rooms_min"]):
                return False
        except Exception:
            pass
    if filters.get("rooms_max"):
        try:
            r = float(str(listing.get("rooms", "0")).replace("+", ""))
            if r > float(filters["rooms_max"]):
                return False
        except Exception:
            pass
    if filters.get("price_min") and listing.get("price"):
        try:
            if int(listing["price"]) < int(filters["price_min"]):
                return False
        except Exception:
            pass
    if filters.get("price_max") and listing.get("price"):
        try:
            if int(listing["price"]) > int(filters["price_max"]):
                return False
        except Exception:
            pass
    return True


def _format_alert_listing(listing: dict, lang: str = "ru") -> str:
    """Format a single listing for alert notification."""
    price = listing.get("price")
    rooms = listing.get("rooms")
    city  = listing.get("city", "")
    deal  = listing.get("deal_type", "")
    title = listing.get("title", "")[:80]
    url   = listing.get("source_url", "")

    deal_str = {"rent": "аренда", "buy": "продажа"}.get(deal, deal)
    price_str = f"{price:,} ₪" if isinstance(price, (int, float)) and price else ""
    rooms_str = f"{rooms} комн." if rooms else ""

    parts = [f"🏠 <b>{title}</b>"]
    info = " · ".join(filter(None, [city, rooms_str, price_str, deal_str]))
    if info:
        parts.append(info)
    if url:
        parts.append(f'<a href="{url}">Открыть объявление →</a>')
    return "\n".join(parts)


async def _send_alerts(bot, user_id: int, listings: list, lang: str = "ru"):
    """Send alert notification to user."""
    try:
        header = {
            "ru": "🔔 <b>Новые объявления по вашему запросу:</b>",
            "en": "🔔 <b>New listings matching your alert:</b>",
            "he": "🔔 <b>מודעות חדשות לפי הדרישות שלך:</b>",
        }.get(lang, "🔔 <b>New listings:</b>")

        text = header + "\n\n" + "\n\n".join(
            _format_alert_listing(l, lang) for l in listings[:MAX_PER_ALERT]
        )

        # Send with photo if available
        photos = []
        for l in listings[:1]:
            ps = [p for p in l.get("photos", []) if p.startswith("http")]
            if ps:
                photos = ps[:1]

        if photos:
            await bot.send_photo(
                chat_id=user_id,
                photo=photos[0],
                caption=text,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.warning(f"[alerts] send to {user_id} failed: {e}")


async def check_and_send(bot):
    """Main check: find new listings, match against alerts, send."""
    try:
        all_listings = list(db._load()["listings"].values())
        cutoff = datetime.now() - timedelta(minutes=CHECK_INTERVAL_SEC // 60 + 2)

        # New listings added in last interval
        new_listings = [
            l for l in all_listings
            if l.get("active") and _listing_is_recent(l, cutoff)
        ]
        if not new_listings:
            return

        logger.info(f"[alerts] {len(new_listings)} new listings, checking subscribers…")

        all_alerts = db.get_all_alerts()
        for uid_str, user_alert_list in all_alerts.items():
            try:
                user_id = int(uid_str)
            except Exception:
                continue

            if not db.is_alert_active(user_id):
                continue

            for alert in user_alert_list:
                alert_id   = alert["id"]
                filters    = alert.get("filters", {})
                sent_ids   = set(alert.get("last_sent_ids", []))
                lang       = filters.get("lang", "ru")

                matched = [
                    l for l in new_listings
                    if str(l.get("id")) not in sent_ids and _matches(l, filters)
                ]
                if not matched:
                    continue

                await _send_alerts(bot, user_id, matched[:MAX_PER_ALERT], lang)

                new_sent = list(sent_ids) + [str(l["id"]) for l in matched]
                db.update_alert_sent(user_id, alert_id, new_sent)

    except Exception as e:
        logger.error(f"[alerts] check_and_send error: {e}", exc_info=True)


def _listing_is_recent(listing: dict, cutoff: datetime) -> bool:
    date_str = listing.get("date_added", "")
    if not date_str:
        return False
    try:
        # Try full ISO format first, then date only
        try:
            added = datetime.fromisoformat(date_str)
        except ValueError:
            added = datetime.strptime(date_str, "%Y-%m-%d")
        return added >= cutoff
    except Exception:
        return False


def start_alert_checker(bot):
    """Start alert checker in a background thread."""
    def _loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("[alerts] Checker started (interval=%ds)", CHECK_INTERVAL_SEC)
        while True:
            try:
                loop.run_until_complete(check_and_send(bot))
            except Exception as e:
                logger.error(f"[alerts] loop error: {e}")
            time.sleep(CHECK_INTERVAL_SEC)

    t = threading.Thread(target=_loop, daemon=True, name="alert-checker")
    t.start()
    return t
