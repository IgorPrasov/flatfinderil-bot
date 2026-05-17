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


def _check_trial_warnings_sync():
    """Send one-time trial-ending warnings to all users at thresholds 7/3/1/0 days."""
    import database as db
    from subscription import (
        days_left_trial, is_trial_active, get_trial_warning,
        TRIAL_WARNING_THRESHOLDS, has_access,
    )
    # Если триал ещё не подходит к концу — выходим
    days = days_left_trial()
    # Триал кончился (days == 0) — тоже шлём, threshold 0
    if is_trial_active() and days > max(TRIAL_WARNING_THRESHOLDS):
        return

    # Какой порог уведомлений сейчас актуален
    threshold = None
    for t in sorted(TRIAL_WARNING_THRESHOLDS):
        if days <= t:
            threshold = t
            break
    if threshold is None:
        return

    # Берём всех пользователей из stats.json
    try:
        from analytics import _load_stats
        stats = _load_stats()
        users = stats.get("users", {})
    except Exception as e:
        logger.error(f"trial warnings: cannot load users: {e}")
        return

    sent_count = 0
    for uid, u in users.items():
        try:
            user_id = int(uid)
        except ValueError:
            continue
        # У кого есть оплаченная подписка — не беспокоим
        try:
            if has_access(user_id) and not is_trial_active():
                # has_access возвращает True во время триала — поэтому проверяем только после триала
                continue
            # Если у пользователя есть платная подписка — пропускаем
            from subscription import get_expiry
            from datetime import datetime as _dt
            paid = get_expiry(user_id, "main")
            if paid and paid > _dt.now():
                continue
        except Exception:
            pass

        # Уже отправляли этот порог?
        if db.was_trial_warning_sent(user_id, threshold):
            continue

        lang = u.get("lang", "ru")
        text = get_trial_warning(lang, days)
        try:
            _run_coroutine(_send_message(user_id, text))
            db.mark_trial_warning_sent(user_id, threshold)
            sent_count += 1
        except Exception as e:
            logger.warning(f"trial warning send failed uid={user_id}: {e}")
    if sent_count:
        logger.info(f"[TRIAL] Sent {sent_count} warnings at threshold={threshold} days_left={days}")


def trial_warning_loop():
    """Background thread: check trial warnings once a day."""
    logger.info("Trial warning checker started")
    # Initial delay so we don't spam on every restart
    time.sleep(60)
    while True:
        try:
            _check_trial_warnings_sync()
            time.sleep(24 * 60 * 60)  # 24 hours
        except Exception as e:
            logger.error(f"trial_warning_loop error: {e}")
            time.sleep(60 * 60)  # retry in 1h on error


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


_crypto_seen_ids: set = set()


def _check_crypto_payments_sync():
    """Poll CryptoPay for newly paid invoices and activate subscriptions."""
    global _crypto_seen_ids
    try:
        import cryptopay
        if not cryptopay.is_enabled():
            return
        new_paid = cryptopay.get_paid_invoices_since(_crypto_seen_ids)
        for inv in new_paid:
            inv_id = inv.get("invoice_id")
            _crypto_seen_ids.add(inv_id)
            payload = inv.get("payload", "")
            if not payload or ":" not in payload:
                continue
            plan_key, uid_str = payload.split(":", 1)
            try:
                user_id = int(uid_str)
            except ValueError:
                continue
            asset = inv.get("asset", "USDT")
            amount = inv.get("amount", "")
            logger.info(f"[CRYPTOPAY] Payment confirmed uid={user_id} plan={plan_key} {amount} {asset}")

            # ── Agent listing package ────────────────────────────────────────
            if plan_key.startswith("agent_"):
                from pricing import get_agent_package
                import database as _db
                pkg = get_agent_package(plan_key)
                if pkg:
                    _db.add_listing_credits(user_id, pkg["count"],
                                            duration_days=pkg.get("duration_days", 30))
                    lbl = pkg["label"].get("ru", plan_key)
                    cnt = pkg["count"]
                    slots_str = "∞" if cnt >= 999999 else str(cnt)
                    async def _notify_agent(uid=user_id, label=lbl, slots=slots_str, amt=amount, ast=asset):
                        if _bot_app:
                            try:
                                await _bot_app.bot.send_message(
                                    chat_id=uid,
                                    text=(f"✅ <b>Крипто-оплата получена!</b>\n\n"
                                          f"Пакет: <b>{label}</b>\n"
                                          f"Слотов добавлено: <b>{slots}</b>\n"
                                          f"Оплачено: {amt} {ast}\n\nСпасибо! 🏠"),
                                    parse_mode="HTML",
                                )
                            except Exception as e:
                                logger.error(f"[CRYPTOPAY] notify agent error: {e}")
                    _run_coroutine(_notify_agent())
                continue

            # ── Subscription plan ────────────────────────────────────────────
            from subscription import activate_subscription, PLANS
            from analytics import track_subscription
            expiry = activate_subscription(user_id, plan_key)
            track_subscription(user_id, plan_key, payment_type="crypto",
                                crypto_asset=asset, crypto_amount=amount)
            plan = PLANS.get(plan_key, {})
            plan_name = plan.get("name_ru", plan_key)
            expiry_str = expiry.strftime("%d.%m.%Y")
            async def _notify(uid=user_id, pname=plan_name, exp=expiry_str, amt=amount, ast=asset):
                if _bot_app:
                    try:
                        await _bot_app.bot.send_message(
                            chat_id=uid,
                            text=(f"✅ <b>Крипто-оплата получена!</b>\n\n"
                                  f"Тариф: <b>{pname}</b>\n"
                                  f"Активна до: <b>{exp}</b>\n"
                                  f"Оплачено: {amt} {ast}\n\nСпасибо! 🏠"),
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.error(f"[CRYPTOPAY] notify error: {e}")
            _run_coroutine(_notify())
    except Exception as e:
        logger.error(f"[CRYPTOPAY] check error: {e}")


def crypto_payment_checker_loop():
    logger.info("CryptoPay checker started")
    time.sleep(30)  # initial delay
    while True:
        try:
            _check_crypto_payments_sync()
            time.sleep(60)  # poll every 60 seconds
        except Exception as e:
            logger.error(f"crypto_payment_checker_loop error: {e}")
            time.sleep(60)


def start_background_tasks(app):
    """Start all background notification threads."""
    set_bot_app(app)

    t1 = threading.Thread(target=subscription_checker_loop, daemon=True, name="sub-checker")
    t1.start()

    t2 = threading.Thread(target=price_drop_checker_loop, daemon=True, name="price-drop-checker")
    t2.start()

    t3 = threading.Thread(target=stale_listing_checker_loop, daemon=True, name="stale-checker")
    t3.start()

    t4 = threading.Thread(target=crypto_payment_checker_loop, daemon=True, name="crypto-checker")
    t4.start()

    t5 = threading.Thread(target=trial_warning_loop, daemon=True, name="trial-warning")
    t5.start()

    logger.info("Background notification tasks started")
