"""
Background notification tasks:
  - check_search_subscriptions: every 30 min, notifies users of new listings
  - check_price_drops: every hour, notifies users of price drops in favorites
"""
import logging
import threading
import time
import asyncio

logger = logging.getLogger(__name__)

_bot_app = None  # Will be set from bot.py


def set_bot_app(app):
    global _bot_app
    _bot_app = app


def _run_coroutine(coro):
    """Run a coroutine from a background thread using the bot's event loop."""
    if _bot_app is None:
        return
    try:
        loop = _bot_app.bot._loop if hasattr(_bot_app.bot, "_loop") else None
        if loop is None:
            # Try getting running loop via asyncio internals
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"_run_coroutine error: {e}")


async def _send_message(chat_id, text):
    if _bot_app is None:
        return
    try:
        await _bot_app.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to send notification to {chat_id}: {e}")


def _check_search_subscriptions_sync():
    """Check all search subscriptions and send notifications for new listings."""
    import database as db
    from database import search_listings

    all_subs = db.get_all_subscriptions()
    for uid, subs in all_subs.items():
        for i, sub in enumerate(subs):
            try:
                filters = sub.get("filters", {})
                last_ids = set(str(x) for x in sub.get("last_result_ids", []))
                results = search_listings(filters)
                current_ids = [str(l["id"]) for l in results]
                new_ids = [lid for lid in current_ids if lid not in last_ids]

                if new_ids and last_ids:
                    # Only notify when there are actually NEW ones (not on first run)
                    count = len(new_ids)
                    msg = f"🔔 <b>Новые объявления по вашей подписке!</b>\n\n{count} новых результат(ов).\n\nИспользуйте /search для просмотра."
                    _run_coroutine(_send_message(int(uid), msg))

                db.update_subscription_last_checked(int(uid), i, current_ids)
            except Exception as e:
                logger.error(f"Subscription check error for user {uid} sub {i}: {e}")


def _check_price_drops_sync():
    """Check favorites prices and notify on drops."""
    import database as db

    favorites_prices = db.get_all_favorites_with_prices()
    for fp_key, saved_price in favorites_prices.items():
        try:
            parts = fp_key.split("_")
            if len(parts) < 2:
                continue
            uid = parts[0]
            lid = parts[1]
            listing = db.get_listing(int(lid))
            if not listing:
                continue
            current_price = listing.get("price", 0)
            if current_price > 0 and saved_price > 0 and current_price < saved_price:
                title = listing.get("title", "")
                msg = f"📉 <b>Цена снижена!</b>\n\n{title}\nБыло: {saved_price:,} ₪ → Стало: {current_price:,} ₪"
                _run_coroutine(_send_message(int(uid), msg))
                # Update saved price
                db.update_favorite_price(int(uid), int(lid), current_price)
        except Exception as e:
            logger.error(f"Price drop check error for {fp_key}: {e}")


def subscription_checker_loop():
    """Background thread: check search subscriptions every 30 minutes."""
    logger.info("Search subscription checker started")
    while True:
        try:
            time.sleep(30 * 60)  # 30 minutes
            logger.info("Checking search subscriptions...")
            _check_search_subscriptions_sync()
        except Exception as e:
            logger.error(f"subscription_checker_loop error: {e}")


def price_drop_checker_loop():
    """Background thread: check price drops every hour."""
    logger.info("Price drop checker started")
    while True:
        try:
            time.sleep(60 * 60)  # 1 hour
            logger.info("Checking price drops...")
            _check_price_drops_sync()
        except Exception as e:
            logger.error(f"price_drop_checker_loop error: {e}")


def _check_stale_listings_sync():
    """Remind owners of listings with view requests that have been active 30+ days."""
    import database as db
    stale = db.get_stale_listings(days=30)
    for listing in stale:
        owner_id = listing.get("user_id")
        if not owner_id:
            continue
        title = listing.get("title", "")[:50]
        msg = (
            f"⏰ <b>Напоминание</b>\n\n"
            f"Ваше объявление активно более 30 дней и получало запросы просмотра.\n\n"
            f"{title}\n\n"
            f"Сделка уже закрыта? Отметьте это в кабинете /cabinet"
        )
        _run_coroutine(_send_message(owner_id, msg))


def stale_listing_checker_loop():
    """Background thread: check stale listings once a day."""
    logger.info("Stale listing checker started")
    while True:
        try:
            time.sleep(24 * 60 * 60)  # 24 hours
            logger.info("Checking stale listings...")
            _check_stale_listings_sync()
        except Exception as e:
            logger.error(f"stale_listing_checker_loop error: {e}")


def start_background_tasks(app):
    """Start all background notification threads."""
    set_bot_app(app)

    t1 = threading.Thread(target=subscription_checker_loop, daemon=True, name="sub-checker")
    t1.start()

    t2 = threading.Thread(target=price_drop_checker_loop, daemon=True, name="price-drop-checker")
    t2.start()

    t3 = threading.Thread(target=stale_listing_checker_loop, daemon=True, name="stale-checker")
    t3.start()

    logger.info("Background notification tasks started")
