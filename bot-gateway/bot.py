import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters,
)
from config import BOT_TOKEN
from handlers import (
    start, handle_menu, my_listings, handle_unknown, agent_cabinet,
    refer_command, show_referral_callback, handle_edit_text,
    handle_pre_checkout, handle_successful_payment,
    handle_stars_invoice,
    cmd_testpay, cmd_grant,
)
from search_handler import SearchHandler
from listing_handler import ListingHandler
from commercial_handler import CommercialHandler
from car_handler import CarHandler
from service_handler import ServiceHandler
from crm_handler import CRMHandler
from support_handler import get_conversation_handler as get_support_handler, admin_reply_cmd
from alert_handler import (
    get_conversation_handler as get_alert_handler,
    show_alerts_menu, handle_alert_subscribe, handle_alert_delete,
)
from lead_handler import (
    get_conversation_handler as get_lead_handler,
    handle_buy_lead, handle_balance_topup, show_provider_leads, show_my_leads,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared references set in main() so the HTTP thread can send messages
_bot_app = None
_bot_loop = None

def fix_city_migration():
    """Migration: re-detect city+district for ALL listings using description text."""
    try:
        import json
        from telegram_parser import detect_city, DISTRICT_MAP
        from database import DB_FILE
        db_path = DB_FILE
        with open(db_path) as f:
            db = json.load(f)
        fixed = 0
        for listing in db.get("listings", {}).values():
            # Skip manually added listings (they have correct data)
            if listing.get("source") == "manual":
                continue
            city = listing.get("city", "")
            desc = listing.get("description", "") or listing.get("title", "")
            if desc:
                detected = detect_city(desc)
                if detected and detected != city:
                    listing["city"] = detected
                    city = detected
                    fixed += 1
            # Fix district to match city
            correct_district = DISTRICT_MAP.get(city)
            if correct_district and listing.get("district") != correct_district:
                listing["district"] = correct_district
                fixed += 1
        if fixed:
            with open(db_path, "w") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            logger.info(f"City/district migration: fixed {fixed} fields")
    except Exception as e:
        logger.warning(f"City migration failed: {e}")




async def cmd_testemail(update: Update, context):
    """Send test weekly report to the calling user (if they have email set)."""
    user_id = update.effective_user.id
    await update.message.reply_text("⏳ Отправляю тестовый отчёт...")
    try:
        import database as db
        from email_reporter import send_report, send_all_weekly_reports, send_all_service_reports
        email = db.get_agent_email(user_id)
        if email:
            ok = send_report(user_id)
            if ok:
                await update.message.reply_text(f"✅ Отчёт агента отправлен на {email}")
            else:
                await update.message.reply_text("❌ Ошибка отправки. Проверьте SMTP настройки в логах.")
        else:
            # Send to all agents with email (admin test)
            ok, total = send_all_weekly_reports()
            ok2, total2 = send_all_service_reports()
            await update.message.reply_text(
                f"✅ Отчёты отправлены:\n"
                f"• Агенты: {ok}/{total}\n"
                f"• Перевозчики/упаковщики: {ok2}/{total2}\n\n"
                f"(у вас нет email — добавьте через /add → Агент → введите email)"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_digest(update: Update, context):
    """
    /digest [city] — отправить утреннюю сводку прямо сейчас.
    Примеры: /digest   /digest Нетания   /digest Тель-Авив
    """
    from i18n import get_lang
    lang = get_lang(context)
    city = " ".join(context.args) if context.args else None
    try:
        from morning_digest import build_digest_text
        text = build_digest_text(city=city, lang=lang, include_datagov=True)
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


def _warmup_sessions():
    """При старте: если в БД нет сессий — загружаем из env vars (переживают редеплои)."""
    import os as _os, json as _json
    import database as _db

    # ── Instagram: env var → БД ──────────────────────────────────────────────
    if not _db.get_ig_settings_json():
        env_ig = _os.environ.get("IG_SESSION_JSON", "").strip()
        if env_ig:
            try:
                _db.set_ig_settings_json(env_ig)
                sid = _json.loads(env_ig).get("cookies", {}).get("sessionid", "")
                if sid:
                    _db.set_ig_session(sid)
                logger.info("✅ Startup: Instagram session restored from IG_SESSION_JSON → DB")
            except Exception as e:
                logger.warning(f"⚠️ Startup: could not restore IG session: {e}")

    # ── Facebook: env var → БД ───────────────────────────────────────────────
    if not _db.get_fb_cookies():
        env_fb = _os.environ.get("FB_COOKIES_JSON", "").strip()
        if env_fb:
            try:
                _db.set_fb_cookies(env_fb)
                logger.info("✅ Startup: Facebook cookies restored from FB_COOKIES_JSON → DB")
            except Exception as e:
                logger.warning(f"⚠️ Startup: could not restore FB cookies: {e}")

    # ── Instagram web cookies (Playwright): env var → БД ─────────────────────
    if not _db.get_setting("ig_web_cookies_json"):
        env_web = _os.environ.get("IG_WEB_COOKIES_JSON", "").strip()
        if env_web:
            try:
                _db.set_setting("ig_web_cookies_json", env_web)
                logger.info("✅ Startup: Instagram web cookies restored from IG_WEB_COOKIES_JSON → DB")
            except Exception as e:
                logger.warning(f"⚠️ Startup: could not restore IG web cookies: {e}")


async def _handle_mover_subscribe(update, context):
    """Handle mover_subscribe_{pkg_key} callback — create PayPlus link for mover weekly subscription."""
    from telegram.ext import ContextTypes
    query = update.callback_query
    await query.answer()
    pkg_key = query.data[len("mover_subscribe_"):]
    user_id = update.effective_user.id

    import database as _db
    try:
        data = _db._load()
        lang = data.get("agent_profiles", {}).get(str(user_id), {}).get("lang", "ru") or "ru"
    except Exception:
        lang = "ru"

    import paypal_payment as _mp
    result = _mp.create_mover_subscription_link(pkg_key, user_id, lang)

    if result and result.get("url"):
        from pricing import get_mover_package
        pkg = get_mover_package(pkg_key)
        label = pkg["label"].get(lang, pkg["label"]["ru"]) if pkg else pkg_key
        price = pkg["price_ils"] if pkg else "?"
        msgs = {
            "ru": f"💳 Нажмите кнопку для оплаты:\n<b>{label} — {price} ₪/неделю</b>\n\nПосле оплаты подписка активируется автоматически.",
            "en": f"💳 Tap to pay:\n<b>{label} — {price} ₪/week</b>\n\nSubscription activates automatically after payment.",
            "he": f"💳 לחץ לתשלום:\n<b>{label} — {price} ₪/שבוע</b>\n\nהמנוי יופעל אוטומטית לאחר התשלום.",
        }
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"💳 {label} — {price} ₪", url=result["url"])
        ]])
        await query.message.reply_text(
            msgs.get(lang, msgs["ru"]),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        err = {
            "ru": "⚠️ Не удалось создать ссылку для оплаты. Попробуйте позже.",
            "en": "⚠️ Failed to create payment link. Please try again later.",
            "he": "⚠️ לא ניתן ליצור קישור לתשלום. נסה שוב מאוחר יותר.",
        }
        await query.answer(err.get(lang, err["ru"]), show_alert=True)


async def _set_bot_commands(application) -> None:
    """Register bot command menu + bottom-left menu button."""
    from telegram import BotCommand, BotCommandScopeAllPrivateChats

    # ── 1. Slash-command list (shows when user taps '/') ─────────────────────
    commands_ru = [
        BotCommand("start",    "🏠 Главное меню"),
        BotCommand("search",   "🔍 Поиск квартиры"),
        BotCommand("add",      "➕ Добавить объявление"),
        BotCommand("listings", "📋 Мои объявления"),
        BotCommand("help",     "❓ Помощь"),
    ]
    commands_en = [
        BotCommand("start",    "🏠 Main menu"),
        BotCommand("search",   "🔍 Search listing"),
        BotCommand("add",      "➕ Add listing"),
        BotCommand("listings", "📋 My listings"),
        BotCommand("help",     "❓ Help"),
    ]
    commands_he = [
        BotCommand("start",    "🏠 תפריט ראשי"),
        BotCommand("search",   "🔍 חיפוש דירה"),
        BotCommand("add",      "➕ הוסף מודעה"),
        BotCommand("listings", "📋 המודעות שלי"),
        BotCommand("help",     "❓ עזרה"),
    ]
    try:
        await application.bot.set_my_commands(commands_ru)
        await application.bot.set_my_commands(
            commands_en,
            scope=BotCommandScopeAllPrivateChats(),
            language_code="en",
        )
        await application.bot.set_my_commands(
            commands_he,
            scope=BotCommandScopeAllPrivateChats(),
            language_code="he",
        )
        logger.info("Bot command menu registered (ru/en/he)")
    except Exception as e:
        logger.warning(f"set_my_commands failed: {e}")

    # ── 2. Menu button (bottom-left, next to message input) ──────────────────
    # Opens the Mini App / landing page as a Telegram Web App.
    # URL is taken from WEBAPP_URL env var; falls back to the Railway deployment URL.
    try:
        webapp_url = os.environ.get(
            "WEBAPP_URL",
            "https://flatfinderil-bot-production.up.railway.app/",
        )
        # Point menu button to the Mini App (served at /miniapp)
        miniapp_url = webapp_url.rstrip("/") + "/miniapp"
        from telegram import MenuButtonWebApp, WebAppInfo
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🏠 FlatFinderIL",
                web_app=WebAppInfo(url=miniapp_url),
            )
        )
        logger.info(f"Menu button set → Web App {miniapp_url}")
    except Exception as e:
        logger.warning(f"set_chat_menu_button failed: {e}")


def main():
    global _bot_app, _bot_loop
    fix_city_migration()
    try:
        import database as _db
        if hasattr(_db, "_migrate_sublet_deal_type"):
            _db._migrate_sublet_deal_type()
        if hasattr(_db, "_cleanup_seeking_listings"):
            _db._cleanup_seeking_listings()
    except Exception as _me:
        logger.warning(f"[STARTUP] migrations skipped: {_me}")
    _warmup_sessions()
    app = Application.builder().token(BOT_TOKEN).post_init(_set_bot_commands).build()
    _bot_app = app
    _bot_loop = asyncio.get_event_loop()
    search = SearchHandler()
    listing = ListingHandler()
    commercial = CommercialHandler()
    cars = CarHandler()
    services = ServiceHandler()
    crm = CRMHandler()
    # ── Debug: log every incoming update type (remove after payments are confirmed working) ──
    async def _debug_all_updates(update: Update, context) -> None:
        update_types = [k for k in update.to_dict().keys() if k != "update_id"]
        logger.info(f"[DEBUG_UPDATE] id={update.update_id} types={update_types}")
    from telegram.ext import TypeHandler
    app.add_handler(TypeHandler(Update, _debug_all_updates), group=-2)

    # Global /cancel — works inside conversations (via fallbacks) and outside (returns to main menu)
    async def _cancel_global(update: Update, context):
        from keyboards import main_menu_keyboard
        from formatters import format_welcome
        if update.message:
            await update.message.reply_text(
                format_welcome(update.effective_user.first_name, context),
                reply_markup=main_menu_keyboard(context),
                parse_mode="HTML",
            )
    app.add_handler(CommandHandler("cancel", _cancel_global))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search.start_search))
    app.add_handler(CommandHandler("listings", my_listings))
    app.add_handler(CommandHandler("add", listing.start_add))
    app.add_handler(CommandHandler("help", handle_unknown))
    app.add_handler(CommandHandler("cabinet", agent_cabinet))
    app.add_handler(CommandHandler("refer", refer_command))
    app.add_handler(CallbackQueryHandler(show_referral_callback, pattern="^show_referral$"))
    app.add_handler(CommandHandler("testemail", cmd_testemail))
    app.add_handler(CommandHandler("testpay", cmd_testpay))
    app.add_handler(CommandHandler("digest", cmd_digest))

    _ADMIN_IDS = {668726316, 416049200}

    async def cmd_clearsubscription(update: Update, context) -> None:
        if update.effective_user.id not in _ADMIN_IDS:
            return
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /clearsubscription username1 username2 ...")
            return
        results = []
        import database_pg
        with database_pg._conn() as c:
            with c.cursor() as cur:
                for username in args:
                    uname = username.lstrip("@")
                    cur.execute("SELECT user_id FROM bot_users WHERE LOWER(username) = LOWER(%s)", (uname,))
                    row = cur.fetchone()
                    if not row:
                        results.append(f"@{uname}: not found in bot_users")
                        continue
                    uid = row["user_id"]
                    cur.execute("DELETE FROM paid_subscriptions WHERE user_id = %s", (uid,))
                    cur.execute("UPDATE bot_users SET bonus_days = 0, bonus_expiry = NULL WHERE user_id = %s", (uid,))
                    results.append(f"@{uname} (id={uid}): subscription cleared ✅")
        await update.message.reply_text("\n".join(results))

    app.add_handler(CommandHandler("clearsubscription", cmd_clearsubscription))
    app.add_handler(commercial.get_conversation_handler())
    app.add_handler(cars.get_conversation_handler())
    app.add_handler(CallbackQueryHandler(cars.open_menu,          pattern="^car_menu$"))
    app.add_handler(CallbackQueryHandler(cars.my_listings,        pattern="^car_my_listings$"))
    app.add_handler(CallbackQueryHandler(cars.manage_vehicle,     pattern="^car_manage_"))
    app.add_handler(CallbackQueryHandler(cars.deactivate_vehicle, pattern="^car_deact_"))
    app.add_handler(CallbackQueryHandler(cars.reactivate_vehicle, pattern="^car_react_"))
    app.add_handler(CallbackQueryHandler(cars.delete_vehicle,     pattern="^car_delete_"))
    app.add_handler(services.get_conversation_handler())
    app.add_handler(crm.get_conversation_handler())
    app.add_handler(search.get_conversation_handler())
    app.add_handler(listing.get_conversation_handler())
    app.add_handler(get_support_handler())
    app.add_handler(get_alert_handler())
    app.add_handler(get_lead_handler())
    app.add_handler(CommandHandler("reply", admin_reply_cmd))
    app.add_handler(CommandHandler("grant", cmd_grant))
    # Alert standalone callbacks
    app.add_handler(CallbackQueryHandler(show_alerts_menu,      pattern="^alerts_menu$"))
    app.add_handler(CallbackQueryHandler(handle_alert_subscribe, pattern="^alert_subscribe$"))
    app.add_handler(CallbackQueryHandler(handle_alert_delete,   pattern="^alert_del_"))
    # Lead marketplace callbacks
    app.add_handler(CallbackQueryHandler(handle_buy_lead,       pattern="^buy_lead_"))
    app.add_handler(CallbackQueryHandler(handle_balance_topup,  pattern="^balance_topup$"))
    app.add_handler(CallbackQueryHandler(show_provider_leads,   pattern="^leads_list_"))
    app.add_handler(CallbackQueryHandler(show_my_leads,         pattern="^my_leads$"))
    app.add_handler(CallbackQueryHandler(handle_menu))
    # Payment handlers in group=-1 so they run BEFORE any ConversationHandler
    # (prevents a mid-conversation state from swallowing the pre_checkout_query)
    # Stars invoice + payment handlers at group=-1 — fire BEFORE ConversationHandlers
    app.add_handler(CallbackQueryHandler(handle_stars_invoice, pattern="^sub_(week|two_weeks|month|search_alert|search_alert_confirm)$"), group=-1)
    app.add_handler(CallbackQueryHandler(_handle_mover_subscribe, pattern="^mover_subscribe_"), group=-1)
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout), group=-1)
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment), group=-1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text))

    # Global error handler — always answer pending callback queries so Telegram
    # doesn't show "button is outdated" when an exception occurs in a handler.
    async def _global_error_handler(update: object, context) -> None:
        logger.error("Unhandled exception in handler:", exc_info=context.error)
        try:
            from telegram import Update as _Update
            if isinstance(update, _Update) and update.callback_query:
                await update.callback_query.answer()
        except Exception:
            pass

    app.add_error_handler(_global_error_handler)

    # Start background notification tasks
    from notifications import start_background_tasks
    start_background_tasks(app)


    # Start weekly email reporter (Sunday 10:00)
    _start_email_scheduler()

    # Morning digest auto-scheduling DISABLED — available on-demand only via /digest command
    # (was: schedule_daily_digest(app.bot, hour=9, minute=0))
    logger.info("Morning digest auto-broadcast is disabled; available via /digest on demand")

    # Start alert checker (every 5 min — matches new listings against user alerts)
    try:
        from alert_checker import start_alert_checker
        start_alert_checker(app.bot)
        logger.info("Alert checker started")
    except Exception as _e:
        logger.warning(f"Alert checker not started: {_e}")

    # Start lead trigger checker (every 30 min — sends delayed cleaning offers)
    try:
        from lead_checker import start_lead_checker
        start_lead_checker(app.bot)
        logger.info("Lead trigger checker started")
    except Exception as _e:
        logger.warning(f"Lead checker not started: {_e}")

    # Start subscription campaigner (day3/day7/day14 upsell messages)
    try:
        from subscription_campaigner import start_campaign_loop
        start_campaign_loop(app.bot)
    except Exception as _e:
        logger.warning(f"Subscription campaigner not started: {_e}")

    # Start Facebook parser if cookies are configured (env var OR database)
    if os.environ.get("FB_COOKIES_JSON"):
        _start_fb_parser()
    else:
        try:
            import database as _db
            _fb_cookies = _db.get_fb_cookies()
            if _fb_cookies:
                os.environ["FB_COOKIES_JSON"] = _fb_cookies
                _start_fb_parser()
                logger.info("Facebook parser started from database cookies")
        except Exception as _e:
            logger.warning(f"Could not load FB cookies from DB: {_e}")

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


import threading
import os
import hmac
import time as _time_mod

# ── Analytics in-memory cache ────────────────────────────────────────────────
# get_analytics() can take 5-15 s — Railway will 502 if we compute it
# synchronously on every request.  Instead we keep a cached copy and refresh
# it in a background thread every 5 minutes.  HTTP requests always return
# the cached value instantly (or "loading" on the very first boot).
_ANALYTICS_CACHE: dict = {"data": None, "ts": 0.0, "lock": threading.Lock(), "refreshing": False}

def _analytics_bg_refresh(date_from=None, date_to=None):
    """Compute analytics and update the cache; called from background thread."""
    try:
        from analytics import get_analytics
        d = get_analytics(date_from=date_from, date_to=date_to)
        with _ANALYTICS_CACHE["lock"]:
            _ANALYTICS_CACHE["data"] = d
            _ANALYTICS_CACHE["ts"]   = _time_mod.time()
    except Exception as _ae:
        logger.error(f"Analytics background refresh error: {_ae}")
    finally:
        with _ANALYTICS_CACHE["lock"]:
            _ANALYTICS_CACHE["refreshing"] = False

def _analytics_warmup_loop():
    """Daemon thread: warm cache on startup then refresh every 5 minutes."""
    import time as _t
    _t.sleep(5)  # let the bot finish initialising first
    while True:
        with _ANALYTICS_CACHE["lock"]:
            already = _ANALYTICS_CACHE["refreshing"]
            if not already:
                _ANALYTICS_CACHE["refreshing"] = True
        if not already:
            _analytics_bg_refresh()
        _t.sleep(300)  # 5 minutes

# ─────────────────────────────────────────────────────────────────────────────

def _filter_analytics_by_date(data: dict, date_from: str, date_to: str) -> dict:
    """Apply date filtering to cached all-time analytics without recomputing."""
    from datetime import datetime, timedelta
    from collections import Counter
    try:
        from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        to_dt   = datetime.strptime(date_to,   "%Y-%m-%d")
        days    = (to_dt - from_dt).days + 1
    except ValueError:
        return data

    def in_p(s):
        return date_from <= (s or "")[:10] <= date_to

    ul = data.get("users_list", [])
    sl = data.get("searches_log", [])

    # Precompute counters for O(1) day lookups
    new_by_day    = Counter(u.get("first_seen", "")     for u in ul)
    active_by_day = Counter(u.get("last_seen",  "")     for u in ul)
    search_by_day = Counter((s.get("time") or "")[:10]  for s in sl)

    d = dict(data)
    d["period"]   = {"from": date_from, "to": date_to, "days": days}
    d["users"]    = dict(data.get("users", {}))
    d["listings"] = dict(data.get("listings", {}))

    d["users"]["new_period"]    = sum(v for k, v in new_by_day.items()    if in_p(k))
    d["users"]["active_period"] = sum(v for k, v in active_by_day.items() if in_p(k))
    d["total_searches_period"]  = sum(v for k, v in search_by_day.items() if in_p(k))

    ua = data.get("listings", {}).get("user_added", [])
    d["listings"]["added_period"] = sum(1 for l in ua if in_p(l.get("date_added", "")))

    days_ru = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    cap = min(days, 90)
    activity = []
    for i in range(cap - 1, -1, -1):
        day_dt  = to_dt - timedelta(days=i)
        day_str = day_dt.strftime("%Y-%m-%d")
        activity.append({
            "day":      days_ru[day_dt.weekday()],
            "date":     day_str,
            "searches": search_by_day.get(day_str, 0),
            "users":    active_by_day.get(day_str, 0),
            "new":      new_by_day.get(day_str, 0),
        })
    d["activity_week"] = activity
    return d


def _start_fb_parser():
    def _fb_loop():
        try:
            from facebook_parser import run_loop
            logger.info("Facebook parser started (interval=60 min)")
            run_loop(interval_min=60)
        except Exception as e:
            logger.error(f"Facebook parser crashed: {e}", exc_info=True)

    t = threading.Thread(target=_fb_loop, daemon=True, name="fb-parser")
    t.start()
    logger.info("Facebook parser thread launched")
import secrets

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json as json_module

DASHBOARD_FILE  = os.path.join(os.path.dirname(__file__), "dashboard.html")
BACKOFFICE_FILE = os.path.join(os.path.dirname(__file__), "backoffice.html")
LANDING_FILE    = os.path.join(os.path.dirname(__file__), "landing.html")
LEGAL_FILE      = os.path.join(os.path.dirname(__file__), "legal.html")
MINIAPP_FILE    = os.path.join(os.path.dirname(__file__), "miniapp.html")

# Public-facing domains — show landing page only, block internal tools
_PUBLIC_DOMAINS = {
    "flatfinderil.com", "www.flatfinderil.com",
    "flatfinderil.co.il", "www.flatfinderil.co.il",
}


def _payment_notify_user(user_id: int, plan_key: str, expiry) -> None:
    """Send a Telegram confirmation message after successful card payment (PayPlus)."""
    try:
        from config import BOT_TOKEN
        import requests as _req
        from subscription import PLANS

        plan = PLANS.get(plan_key, {})
        expiry_str = expiry.strftime("%d.%m.%Y") if hasattr(expiry, "strftime") else str(expiry)

        # Look up stored language for this user, default to Russian
        try:
            import database as _db
            data = _db._load()
            lang = data.get("agent_profiles", {}).get(str(user_id), {}).get("lang", "ru") or "ru"
        except Exception:
            lang = "ru"

        plan_name = plan.get(f"name_{lang}") or plan.get("name_ru", plan_key)

        msgs = {
            "ru": f"✅ <b>Оплата прошла!</b>\n\nПодписка <b>{plan_name}</b> активна до <b>{expiry_str}</b>.\n\nСпасибо, что выбрали FlatFinderIL! 🏠",
            "en": f"✅ <b>Payment successful!</b>\n\n<b>{plan_name}</b> subscription active until <b>{expiry_str}</b>.\n\nThank you for choosing FlatFinderIL! 🏠",
            "he": f"✅ <b>התשלום בוצע!</b>\n\nמנוי <b>{plan_name}</b> פעיל עד <b>{expiry_str}</b>.\n\nתודה שבחרתם FlatFinderIL! 🏠",
        }
        text = msgs.get(lang, msgs["ru"])

        _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        logger.info(f"[PAYPAL] Confirmation sent to user={user_id}")
    except Exception as e:
        logger.error(f"[PAYPAL] Failed to notify user={user_id}: {e}")

def _notify_agent_credits(user_id: int, pkg: dict) -> None:
    """Notify agent that listing credits were added after payment."""
    try:
        from config import BOT_TOKEN
        import requests as _req
        import database as _db

        try:
            data = _db._load()
            lang = data.get("agent_profiles", {}).get(str(user_id), {}).get("lang", "ru") or "ru"
        except Exception:
            lang = "ru"

        label = pkg["label"].get(lang, pkg["label"]["ru"])
        count = pkg["count"]
        msgs = {
            "ru": (
                f"✅ <b>Оплата прошла!</b>\n\n"
                f"На ваш счёт добавлено <b>{count}</b> слот(а) для объявлений.\n"
                f"Пакет: <b>{label}</b>\n\n"
                "Вернитесь в бот и опубликуйте объявление — кредиты уже зачислены! 🏠"
            ),
            "en": (
                f"✅ <b>Payment successful!</b>\n\n"
                f"<b>{count}</b> listing slot(s) added to your account.\n"
                f"Package: <b>{label}</b>\n\n"
                "Go back to the bot and publish your listing — credits are ready! 🏠"
            ),
            "he": (
                f"✅ <b>התשלום בוצע!</b>\n\n"
                f"נוספו <b>{count}</b> חריצי מודעות לחשבון שלך.\n"
                f"חבילה: <b>{label}</b>\n\n"
                "חזור לבוט ופרסם את המודעה — הקרדיטים כבר זוכו! 🏠"
            ),
        }
        text = msgs.get(lang, msgs["ru"])

        _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        logger.info(f"[PAYPAL] Agent credits notification sent user={user_id}")
    except Exception as e:
        logger.error(f"[PAYPAL] Failed to notify agent user={user_id}: {e}")


def _notify_mover_subscription(user_id: int, pkg: dict, expiry_iso: str) -> None:
    """Notify mover that weekly subscription is active."""
    try:
        from config import BOT_TOKEN
        import requests as _req
        import database as _db

        try:
            data = _db._load()
            lang = data.get("agent_profiles", {}).get(str(user_id), {}).get("lang", "ru") or "ru"
        except Exception:
            lang = "ru"

        label = pkg["label"].get(lang, pkg["label"]["ru"])
        from datetime import datetime
        try:
            expiry_str = datetime.fromisoformat(expiry_iso).strftime("%d.%m.%Y")
        except Exception:
            expiry_str = expiry_iso[:10]

        msgs = {
            "ru": (
                f"✅ <b>Оплата прошла!</b>\n\n"
                f"Подписка <b>{label}</b> активна до <b>{expiry_str}</b>.\n\n"
                "Ваша компания уже отображается пользователям FlatFinderIL! 🚛"
            ),
            "en": (
                f"✅ <b>Payment successful!</b>\n\n"
                f"<b>{label}</b> subscription active until <b>{expiry_str}</b>.\n\n"
                "Your company is now visible to FlatFinderIL users! 🚛"
            ),
            "he": (
                f"✅ <b>התשלום בוצע!</b>\n\n"
                f"מנוי <b>{label}</b> פעיל עד <b>{expiry_str}</b>.\n\n"
                "החברה שלך כבר מוצגת למשתמשי FlatFinderIL! 🚛"
            ),
        }
        text = msgs.get(lang, msgs["ru"])

        _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        logger.info(f"[PAYPAL] Mover subscription notification sent user={user_id}")
    except Exception as e:
        logger.error(f"[PAYPAL] Failed to notify mover user={user_id}: {e}")


async def _notify_service_subscription(user_id: int, svc_type: str, expiry_iso: str) -> None:
    """Notify cleaning/packing provider that monthly subscription is active."""
    try:
        from config import BOT_TOKEN
        import requests as _req
        import database as _db

        try:
            data = _db._load()
            lang = data.get("agent_profiles", {}).get(str(user_id), {}).get("lang", "ru") or "ru"
        except Exception:
            lang = "ru"

        from datetime import datetime
        try:
            expiry_str = datetime.fromisoformat(expiry_iso).strftime("%d.%m.%Y")
        except Exception:
            expiry_str = expiry_iso[:10]

        icon = "🧹" if svc_type == "cleaning" else "📦"
        msgs = {
            "ru": (
                f"✅ <b>Оплата прошла!</b>\n\n"
                f"Подписка <b>Присутствие в базе</b> активна до <b>{expiry_str}</b>.\n\n"
                f"Ваш сервис {icon} уже отображается пользователям FlatFinderIL!"
            ),
            "en": (
                f"✅ <b>Payment successful!</b>\n\n"
                f"<b>Listed in database</b> subscription active until <b>{expiry_str}</b>.\n\n"
                f"Your {icon} service is now visible to FlatFinderIL users!"
            ),
            "he": (
                f"✅ <b>התשלום בוצע!</b>\n\n"
                f"מנוי <b>נוכחות במאגר</b> פעיל עד <b>{expiry_str}</b>.\n\n"
                f"השירות שלך {icon} כבר מוצג למשתמשי FlatFinderIL!"
            ),
        }
        text = msgs.get(lang, msgs["ru"])
        _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        logger.info(f"[PAYPAL] Service subscription notification sent user={user_id} svc={svc_type}")
    except Exception as e:
        logger.error(f"[PAYPAL] Failed to notify service user={user_id}: {e}")


async def _notify_alert_activated(user_id: int, expiry_iso: str) -> None:
    """Notify user that alert subscription is active."""
    try:
        from config import BOT_TOKEN
        import requests as _req
        import database as _db
        try:
            lang = _db._load().get("user_settings", {}).get(str(user_id), {}).get("lang", "ru") or "ru"
        except Exception:
            lang = "ru"
        try:
            from datetime import datetime
            expiry_str = datetime.fromisoformat(expiry_iso).strftime("%d.%m.%Y")
        except Exception:
            expiry_str = (expiry_iso or "")[:10]
        msgs = {
            "ru": (
                f"✅ <b>Оплата прошла!</b>\n\n"
                f"Подписка <b>🔔 Уведомления</b> активна до <b>{expiry_str}</b>.\n\n"
                "Теперь настройте фильтры — бот будет присылать новые объявления автоматически.\n\n"
                "Нажмите 🔔 Уведомления в главном меню."
            ),
            "en": (
                f"✅ <b>Payment successful!</b>\n\n"
                f"<b>🔔 Alerts</b> subscription active until <b>{expiry_str}</b>.\n\n"
                "Now set your filters — the bot will send new listings automatically.\n\n"
                "Tap 🔔 Alerts in the main menu."
            ),
            "he": (
                f"✅ <b>התשלום בוצע!</b>\n\n"
                f"מנוי <b>🔔 התראות</b> פעיל עד <b>{expiry_str}</b>.\n\n"
                "עכשיו הגדר פילטרים — הבוט ישלח מודעות חדשות אוטומטית.\n\n"
                "לחץ 🔔 התראות בתפריט הראשי."
            ),
        }
        _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": msgs.get(lang, msgs["ru"]), "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"[PAYPAL] Failed to notify alert user={user_id}: {e}")


def _request_host(headers) -> str:
    """Return the real public hostname from request headers."""
    for h in ("X-Forwarded-Host", "X-Original-Host", "Host"):
        val = headers.get(h, "")
        if val:
            return val.split(":")[0].split(",")[0].strip().lower()
    return ""
BACKOFFICE_PASSWORD = os.environ.get("BACKOFFICE_PASSWORD", "FlatFinderIL2026")

_BO_SESSIONS: dict = {}
_BO_LOCK = threading.Lock()

def _bo_create_session():
    token = secrets.token_hex(32)
    with _BO_LOCK:
        _BO_SESSIONS[token] = datetime.utcnow() + timedelta(hours=24)
    return token

def _bo_check_session(headers):
    raw = headers.get("Cookie","")
    token = ""
    for part in raw.split(";"):
        k,_,v = part.strip().partition("=")
        if k.strip() == "bo_session":
            token = v.strip(); break
    with _BO_LOCK:
        exp = _BO_SESSIONS.get(token)
    if not exp: return False
    if datetime.utcnow() > exp:
        with _BO_LOCK: _BO_SESSIONS.pop(token, None)
        return False
    return True

def _bo_delete_session(headers):
    raw = headers.get("Cookie","")
    for part in raw.split(";"):
        k,_,v = part.strip().partition("=")
        if k.strip() == "bo_session":
            with _BO_LOCK: _BO_SESSIONS.pop(v.strip(), None)

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def _send_json(self, data, status=200):
        body = json_module.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path):
        try:
            with open(path,"rb") as f: content = f.read()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate")
            self.send_header("Pragma","no-cache")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except: self.send_response(500); self.end_headers()

    def _handle_admin_api(self, method: str, path: str, body: dict, query: dict = None):
        """Internal admin API — no session required (dashboard-only, not public)."""
        import database as db
        # Strip /api/admin/ prefix and split into resource + optional id + action
        parts = path.lstrip("/").split("/")  # ['api', 'admin', resource, id?, action?]
        resource = parts[2] if len(parts) > 2 else ""
        rid      = parts[3] if len(parts) > 3 else ""
        action   = parts[4] if len(parts) > 4 else ""
        query    = query or {}

        # ── Search users  GET /api/admin/users?q=... ───────────────────────
        if resource == "users" and method == "GET":
            try:
                from analytics import _load_stats
                q = (query.get("q") or [""])[0].strip().lower().lstrip("@")
                stats = _load_stats()
                users = stats.get("users", {})
                items = [{"user_id": uid, **udata} for uid, udata in users.items()]
                if q:
                    def _match(u):
                        return (
                            q in str(u.get("user_id", "")).lower() or
                            q in (u.get("username") or "").lower() or
                            q in (u.get("first_name") or "").lower() or
                            q in (u.get("last_name") or "").lower()
                        )
                    items = [u for u in items if _match(u)]
                items.sort(key=lambda u: u.get("last_seen", ""), reverse=True)
                return self._send_json({"total": len(items), "items": items[:100]})
            except Exception as e:
                return self._send_json({"error": str(e), "total": 0, "items": []}, 500)

        # ── Vehicles (Cars vertical)  GET /api/admin/vehicles?q=... ────────
        if resource == "vehicles" and not rid and method == "GET":
            try:
                items = db.get_all_vehicles() if hasattr(db, "get_all_vehicles") else []
                q = (query.get("q") or [""])[0].strip().lower()
                if q:
                    def _match(v):
                        return (q in (v.get("make") or "").lower() or
                                q in (v.get("model") or "").lower() or
                                q in (v.get("city") or "").lower())
                    items = [v for v in items if _match(v)]
                active_count = sum(1 for v in items if v.get("active", True))
                return self._send_json({
                    "total": len(items), "active": active_count,
                    "items": items[:200],
                })
            except Exception as e:
                return self._send_json({"error": str(e), "total": 0, "items": []}, 500)

        # ── Resolve a vehicle photo's Telegram file_id to a real image URL ───
        # (photos are stored as Telegram file_ids, not URLs — dashboard <img>
        # tags hit this, which redirects to Telegram's file CDN)
        if resource == "vehicle-photo" and rid and method == "GET":
            try:
                import requests as _req
                r = _req.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                    params={"file_id": rid}, timeout=10,
                )
                file_path = (r.json().get("result") or {}).get("file_path")
                if not file_path:
                    return self._send_json({"error": "file not found"}, 404)
                # Proxy the bytes rather than redirecting — a redirect would
                # put the bot token, embedded in the Telegram file URL, in
                # plain sight in the client's network tab.
                img = _req.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}", timeout=15)
                self.send_response(200)
                # Telegram's file server often replies with a generic
                # application/octet-stream regardless of the actual file —
                # bot-uploaded photos are always JPEG, so force it.
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "private, max-age=3600")
                self.send_header("Content-Length", str(len(img.content)))
                self.end_headers()
                self.wfile.write(img.content)
                return
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        # ── GET single vehicle ──────────────────────────────────────────────
        if resource == "vehicles" and rid and method == "GET":
            try:
                v = db.get_vehicle(int(rid))
                if v:
                    return self._send_json({"vehicle": v})
                return self._send_json({"error": "Not found"}, 404)
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        # ── PATCH vehicle (edit fields) ─────────────────────────────────────
        if resource == "vehicles" and rid and method == "PATCH":
            try:
                v = db.update_vehicle(int(rid), body or {})
                if v:
                    return self._send_json({"ok": True, "vehicle": v})
                return self._send_json({"error": "Not found"}, 404)
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        # ── GET single listing ────────────────────────────────────────────
        if resource == "listings" and rid and method == "GET":
            try:
                listing = db.get_listing(int(rid))
                if listing:
                    return self._send_json({"listing": listing})
                return self._send_json({"error": "Not found"}, 404)
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        # ── PATCH listing (edit fields) ────────────────────────────────────
        if resource == "listings" and rid and method == "PATCH":
            try:
                lid = int(rid)
                fields = {k: v for k, v in body.items()
                          if k in ("title","city","neighborhood","rooms","floor","price",
                                   "deal_type","property_type","area_sqm","contact",
                                   "description","parking","pool","active","pinned")}
                ok = db.update_listing(lid, fields)
                if ok:
                    listing = db.get_listing(lid)
                    logger.info(f"[ADMIN] Edited listing {lid}: {list(fields.keys())}")
                    return self._send_json({"ok": True, "listing": listing})
                return self._send_json({"ok": False, "error": "Listing not found"}, 404)
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── POST boost listing  /api/admin/listings/:id/boost ─────────────
        if resource == "listings" and action == "boost" and method == "POST":
            try:
                lid = int(rid)
                today = datetime.now().strftime("%Y-%m-%d")
                ok = db.update_listing(lid, {"date_added": today, "boosted": True})
                listing = db.get_listing(lid)
                logger.info(f"[ADMIN] Boosted listing {lid}")
                return self._send_json({"ok": ok, "listing": listing})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── POST pin/unpin listing  /api/admin/listings/:id/pin ───────────
        if resource == "listings" and action == "pin" and method == "POST":
            try:
                lid = int(rid)
                pin_val = body.get("pin", True)
                ok = db.update_listing(lid, {"pinned": bool(pin_val)})
                listing = db.get_listing(lid)
                logger.info(f"[ADMIN] {'Pinned' if pin_val else 'Unpinned'} listing {lid}")
                return self._send_json({"ok": ok, "listing": listing})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── POST send-message (contact client via Telegram) ────────────────
        if resource == "send-message" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                text = body.get("text", "").strip()
                if not uid or not text:
                    return self._send_json({"ok": False, "error": "user_id и text обязательны"}, 400)
                self._send_tg_notify(uid, text)
                logger.info(f"[ADMIN] Sent message to user {uid}: {text[:60]}")
                return self._send_json({"ok": True})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── Engagement: personal cards (referrals/favorites/reviews/bonus/price/subs) ─
        # GET /api/admin/engagement-users — summary list, every user with ANY activity
        if resource == "engagement-users" and not rid and method == "GET":
            try:
                from analytics import _load_stats
                stats = _load_stats()
                users_meta = stats.get("users", {})

                favs   = db.get_all_favorites_bulk()          if hasattr(db, "get_all_favorites_bulk") else {}
                revs   = db.get_all_reviews_bulk()             if hasattr(db, "get_all_reviews_bulk") else {}
                refs   = db.get_all_referrals_bulk()           if hasattr(db, "get_all_referrals_bulk") else {}
                bonus  = db.get_all_bonus_days_bulk()          if hasattr(db, "get_all_bonus_days_bulk") else {}
                prices = db.get_all_favorites_with_prices()    if hasattr(db, "get_all_favorites_with_prices") else {}
                subs   = db.get_all_subscriptions()
                paid   = db.get_all_paid_subscriptions_bulk()  if hasattr(db, "get_all_paid_subscriptions_bulk") else {}

                now_iso = datetime.now().isoformat()

                # Reviews are keyed by listing_id → invert to per-user counts
                reviews_by_user: dict = {}
                for lid, rv in revs.items():
                    for r in rv:
                        uid = str(r.get("user_id"))
                        reviews_by_user.setdefault(uid, []).append(r)

                # Price-tracking keys are "uid_lid" → group by uid
                price_by_user: dict = {}
                for key in prices.keys():
                    uid = key.split("_")[0]
                    price_by_user.setdefault(uid, []).append(key)

                all_uids = set(favs) | set(reviews_by_user) | set(refs) | set(bonus) | set(price_by_user) | set(subs) | set(paid)

                out = []
                for uid in all_uids:
                    u = users_meta.get(uid, {})
                    name = " ".join(filter(None, [u.get("first_name"), u.get("last_name")])) or f"ID {uid}"
                    plans = paid.get(uid, {})
                    active_plans = [p for p, exp in plans.items() if exp > now_iso]
                    out.append({
                        "user_id": uid,
                        "user_name": name,
                        "username": u.get("username", ""),
                        "favorites_count": len(favs.get(uid, [])),
                        "reviews_count": len(reviews_by_user.get(uid, [])),
                        "referrals_count": len(refs.get(uid, [])),
                        "bonus_days": bonus.get(uid, 0),
                        "price_tracked_count": len(price_by_user.get(uid, [])),
                        "search_subs_count": len(subs.get(uid, [])),
                        "paid_plans": list(plans.keys()),
                        "paid_active": len(active_plans) > 0,
                    })
                out.sort(key=lambda x: sum([
                    x["favorites_count"], x["reviews_count"], x["referrals_count"],
                    1 if x["bonus_days"] else 0, x["price_tracked_count"], x["search_subs_count"],
                    1 if x["paid_active"] else 0,
                ]), reverse=True)
                return self._send_json({"total": len(out), "items": out})
            except Exception as e:
                return self._send_json({"error": str(e), "total": 0, "items": []}, 500)

        # GET /api/admin/engagement-users/<user_id> — full personal card
        if resource == "engagement-users" and rid and method == "GET":
            try:
                uid = rid
                from analytics import _load_stats
                stats = _load_stats()
                u = stats.get("users", {}).get(uid, {})
                name = " ".join(filter(None, [u.get("first_name"), u.get("last_name")])) or f"ID {uid}"

                listings_by_id = {str(l.get("id")): l for l in db.get_all_listings(limit=10000)}

                # Favorites
                favs = db.get_all_favorites_bulk() if hasattr(db, "get_all_favorites_bulk") else {}
                fav_ids = favs.get(uid, [])
                favorites = [{
                    "listing_id": lid,
                    "title": listings_by_id.get(str(lid), {}).get("title", "—")[:60],
                    "city": listings_by_id.get(str(lid), {}).get("city", "—"),
                    "price": listings_by_id.get(str(lid), {}).get("price", 0),
                } for lid in fav_ids]

                # Reviews written by this user
                revs = db.get_all_reviews_bulk() if hasattr(db, "get_all_reviews_bulk") else {}
                reviews = []
                for lid, rv in revs.items():
                    for r in rv:
                        if str(r.get("user_id")) == uid:
                            reviews.append({
                                "listing_id": lid,
                                "listing_title": listings_by_id.get(str(lid), {}).get("title", "—")[:60],
                                "rating": r.get("rating"),
                                "comment": r.get("comment", ""),
                                "date": r.get("date", ""),
                            })

                # Referrals given by this user
                refs = db.get_all_referrals_bulk() if hasattr(db, "get_all_referrals_bulk") else {}
                referred_ids = refs.get(uid, [])
                users_meta = stats.get("users", {})
                referrals = [{
                    "new_user_id": nid,
                    "name": " ".join(filter(None, [
                        users_meta.get(str(nid), {}).get("first_name"),
                        users_meta.get(str(nid), {}).get("last_name"),
                    ])) or f"ID {nid}",
                } for nid in referred_ids]

                # Bonus days
                bonus = db.get_all_bonus_days_bulk() if hasattr(db, "get_all_bonus_days_bulk") else {}
                bonus_days = bonus.get(uid, 0)

                # Price tracking (favorites with a saved price, show current vs saved)
                prices = db.get_all_favorites_with_prices() if hasattr(db, "get_all_favorites_with_prices") else {}
                price_tracking = []
                for key, saved_price in prices.items():
                    if key.startswith(f"{uid}_"):
                        lid = key.split("_", 1)[1]
                        listing = listings_by_id.get(str(lid), {})
                        current_price = listing.get("price", 0)
                        price_tracking.append({
                            "listing_id": lid,
                            "title": listing.get("title", "—")[:60],
                            "saved_price": saved_price,
                            "current_price": current_price,
                            "diff": (current_price - saved_price) if (current_price and saved_price) else 0,
                        })

                # Search subscriptions (reuse the same live source as /api/admin/search-subscriptions)
                subs = db.get_all_subscriptions()
                sub_entries = subs.get(uid, [])
                is_active = db.is_alert_active(int(uid)) if uid.isdigit() else False
                search_subscriptions = [{
                    "sub_id": e.get("id"),
                    "created": e.get("created"),
                    "filters": e.get("filters", {}),
                    "reason": e.get("reason", ""),
                } for e in sub_entries]

                # Paid app subscription (main plan / custom grants — separate from search alerts)
                paid_all = db.get_all_paid_subscriptions_bulk() if hasattr(db, "get_all_paid_subscriptions_bulk") else {}
                plans = paid_all.get(uid, {})
                now_iso = datetime.now().isoformat()
                paid_subscription = [{
                    "plan_type": p,
                    "expiry": exp,
                    "active": exp > now_iso,
                } for p, exp in plans.items()]

                return self._send_json({
                    "user_id": uid,
                    "user_name": name,
                    "username": u.get("username", ""),
                    "favorites": favorites,
                    "reviews": reviews,
                    "referrals": referrals,
                    "bonus_days": bonus_days,
                    "price_tracking": price_tracking,
                    "search_subscriptions": search_subscriptions,
                    "search_subs_active": is_active,
                    "paid_subscription": paid_subscription,
                })
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        # ── Search subscriptions (paid alerts, 39.90₪/wk) ────────────────────
        # GET /api/admin/search-subscriptions — full list with user info + status
        if resource == "search-subscriptions" and method == "GET":
            from analytics import _load_stats
            stats = _load_stats()
            users_meta = stats.get("users", {})
            import subscription as sub
            all_subs = db.get_all_subscriptions()  # cross-backend: hits live PG table or JSON file
            out = []
            for uid, entries in all_subs.items():
                u = users_meta.get(uid, {})
                name = " ".join(filter(None, [u.get("first_name"), u.get("last_name")])) or "—"
                is_active = db.is_alert_active(int(uid)) if uid.isdigit() else False
                expiry = db.get_alert_expiry(int(uid)) if uid.isdigit() else None
                is_admin = int(uid) in getattr(sub, "_ADMIN_IDS", set()) if uid.isdigit() else False
                for e in entries:
                    out.append({
                        "user_id": uid,
                        "user_name": name,
                        "username": u.get("username", ""),
                        "sub_id": e.get("id"),
                        "created": e.get("created"),
                        "filters": e.get("filters", {}),
                        "reason": e.get("reason", ""),
                        "created_by": e.get("created_by", ""),
                        "is_active": is_active or is_admin,
                        "is_admin": is_admin,
                        "expiry": expiry,
                    })
            out.sort(key=lambda x: x.get("created", ""), reverse=True)
            return self._send_json({"total": len(out), "items": out})

        # DELETE /api/admin/search-subscriptions/<user_id>  — remove ALL subs for a user
        if resource == "search-subscriptions" and rid and method == "DELETE":
            try:
                uid = int(rid)
                removed = db.remove_all_subscriptions_for_user(uid)
                from analytics import _load_stats, _save_stats
                stats = _load_stats()
                stats.setdefault("admin_audit_log", []).append({
                    "user_id": str(uid), "action": "remove_search_subscriptions",
                    "action_label": f"Удалено {removed} подписок на поиск",
                    "reason": (query.get("reason") or ["Не оплачено"])[0] if query else "Не оплачено",
                    "ts": datetime.now().isoformat()
                })
                _save_stats(stats)
                logger.info(f"[ADMIN] Removed {removed} search-subscriptions for user {uid}")
                return self._send_json({"ok": True, "removed": removed})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── FB parser diagnostics  GET /api/admin/fb-status ─────────────────
        if resource == "fb-status" and method == "GET":
            keys = [
                "fb_parser_status", "fb_parser_started_at",
                "fb_parser_run_status", "fb_parser_run_started_at",
                "fb_parser_run_finished_at", "fb_parser_cookie_count",
                "fb_parser_progress", "fb_parser_run_summary",
                "fb_parser_last_error", "fb_parser_error_at",
                "fb_parser_blocked_count", "fb_parser_blocked_url",
                "fb_parser_proxy_mode",
            ]
            out = {k: db.get_setting(k) for k in keys}
            return self._send_json(out)

        # ── Audit log GET ──────────────────────────────────────────────────
        if resource == "audit-log" and method == "GET":
            from analytics import _load_stats
            uid_filter = (query.get("user_id") or [""])[0]
            stats = _load_stats()
            log = stats.get("admin_audit_log", [])
            if uid_filter:
                log = [e for e in log if str(e.get("user_id")) == str(uid_filter)]
            log = sorted(log, key=lambda e: e.get("ts", ""), reverse=True)[:50]
            return self._send_json({"items": log})

        # ── Grant subscription ──────────────────────────────────────────────
        if resource == "accounts" and rid == "grant" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                plan = body.get("plan", "month")
                expiry_iso = body.get("expiry_iso")
                days = int(body.get("days", 30))
                reason = body.get("reason", "")
                features = body.get("features", [])
                if not uid or not expiry_iso:
                    return self._send_json({"ok": False, "error": "user_id и expiry_iso обязательны"}, 400)
                db.set_user_paid_subscription(uid, plan, expiry_iso)
                # Mark subscribed in stats.json + write audit entry
                from analytics import _load_stats, _save_stats
                s = _load_stats()
                u = s.get("users", {}).get(str(uid))
                if u: u["subscribed"] = True
                s.setdefault("admin_audit_log", []).append({
                    "user_id": str(uid), "action": "grant_subscription",
                    "action_label": f"Подписка: {plan} ({days} дн.)",
                    "reason": reason, "ts": datetime.now().isoformat()
                })
                _save_stats(s)
                label = {"week":"1 неделя","two_weeks":"2 недели","month":"1 месяц",
                         "premium_search":"Премиум поиск"}.get(plan, plan)
                if plan == "premium_search" and features:
                    label += f" ({', '.join(features)})"
                self._send_tg_notify(uid,
                    f"🎁 <b>Доступ активирован администратором!</b>\n\n"
                    f"Тариф: <b>{label}</b>\nАктивен до <b>{expiry_iso[:10]}</b>.")
                logger.info(f"[ADMIN] Granted {plan} to user {uid} | reason: {reason}")
                return self._send_json({"ok": True, "expiry_iso": expiry_iso})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── Bonus days (trial extension) ────────────────────────────────────
        if resource == "accounts" and rid == "bonus" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                days = int(body.get("days", 0))
                reason = body.get("reason", "")
                if not uid or not days:
                    return self._send_json({"ok": False, "error": "user_id и days обязательны"}, 400)
                db.add_bonus_days(uid, days)
                from analytics import _load_stats, _save_stats
                s = _load_stats()
                s.setdefault("admin_audit_log", []).append({
                    "user_id": str(uid), "action": "bonus_days",
                    "action_label": f"Продление триала: +{days} дн.",
                    "reason": reason, "ts": datetime.now().isoformat()
                })
                _save_stats(s)
                self._send_tg_notify(uid,
                    f"🎁 <b>Бонус от администратора!</b>\n\nНачислено <b>+{days} дней</b>.")
                logger.info(f"[ADMIN] +{days} bonus days to user {uid} | reason: {reason}")
                return self._send_json({"ok": True})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── Set account status ─────────────────────────────────────────────
        if resource == "accounts" and rid == "set-status" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                action = body.get("action", "")
                subscribed = body.get("subscribed")
                reason = body.get("reason", "")
                if not uid:
                    return self._send_json({"ok": False, "error": "user_id обязателен"}, 400)
                from analytics import _load_stats, _save_stats
                stats = _load_stats()
                u = stats.get("users", {}).get(str(uid))
                msg = None
                labels = {"blocked":"Заблокирован","active":"Активирован","reset":"Подписка сброшена"}
                if action == "blocked":
                    if u: u["blocked"] = True
                    msg = "🚫 Ваш аккаунт заблокирован администратором."
                elif action == "active":
                    if u: u["blocked"] = False; u["subscribed"] = True
                    msg = "✅ Ваш аккаунт активирован администратором."
                elif action == "reset":
                    if u: u["subscribed"] = False
                elif subscribed is not None:
                    if u: u["subscribed"] = bool(subscribed)
                stats.setdefault("admin_audit_log", []).append({
                    "user_id": str(uid), "action": f"set_status_{action}",
                    "action_label": labels.get(action, action),
                    "reason": reason, "ts": datetime.now().isoformat()
                })
                _save_stats(stats)
                if msg: self._send_tg_notify(uid, msg)
                logger.info(f"[ADMIN] set-status action={action!r} for user {uid} | reason: {reason}")
                return self._send_json({"ok": True})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── Promo codes ────────────────────────────────────────────────────
        if resource == "promo-codes":
            from analytics import _load_stats, _save_stats
            if method == "GET":
                stats = _load_stats()
                items = sorted(stats.get("promo_codes", {}).values(),
                               key=lambda x: x.get("created", ""), reverse=True)
                return self._send_json({"items": list(items)})
            if method == "POST":
                code = (body.get("code") or "").strip().upper()
                reason = (body.get("reason") or "").strip()
                if not code:
                    return self._send_json({"ok": False, "error": "Код обязателен"}, 400)
                if not reason:
                    return self._send_json({"ok": False, "error": "Причина/описание обязательны"}, 400)
                stats = _load_stats()
                pcs = stats.setdefault("promo_codes", {})
                if code in pcs:
                    return self._send_json({"ok": False, "error": "Код уже существует"}, 409)
                category = body.get("category", "subscription")
                pcs[code] = {
                    "code": code,
                    "category": category,
                    "type": body.get("type", "days"),   # legacy field, kept for old readers
                    "value": int(body.get("value", 7)),
                    "max_uses": int(body.get("max_uses", 0)),
                    "expiry": body.get("expiry"), "used": 0,
                    "reason": reason,
                    "created": datetime.now().isoformat(), "active": True,
                }
                stats.setdefault("admin_audit_log", []).append({
                    "user_id": "", "action": "create_promo",
                    "action_label": f"Создан промокод {code} ({category})",
                    "reason": reason, "ts": datetime.now().isoformat()
                })
                _save_stats(stats)
                logger.info(f"[ADMIN] Created promo {code} ({category}) | reason: {reason}")
                return self._send_json({"ok": True, "code": code})
            if method == "DELETE" and rid:
                stats = _load_stats()
                code = rid.upper()
                stats.get("promo_codes", {}).pop(code, None)
                _save_stats(stats)
                logger.info(f"[ADMIN] Deleted promo {code}")
                return self._send_json({"ok": True})

        return self._send_json({"error": "Not found"}, 404)

    def _send_tg_notify(self, user_id: int, text: str):
        """Fire-and-forget Telegram message via requests (sync, from HTTP handler thread)."""
        try:
            from config import BOT_TOKEN as _tok
            import urllib.request as _ur, json as _j
            data = _j.dumps({"chat_id": user_id, "text": text, "parse_mode": "HTML"}).encode()
            req = _ur.Request(
                f"https://api.telegram.org/bot{_tok}/sendMessage",
                data=data, headers={"Content-Type": "application/json"}
            )
            _ur.urlopen(req, timeout=8)
        except Exception as _e:
            logger.debug(f"_send_tg_notify failed: {_e}")

    async def _bot_notify(self, user_id: int, text: str):
        """Send Telegram message to a user (fire-and-forget from backoffice)."""
        try:
            from config import BOT_TOKEN as _tok
            import httpx
            async with httpx.AsyncClient(timeout=8) as cl:
                await cl.post(
                    f"https://api.telegram.org/bot{_tok}/sendMessage",
                    json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
                )
        except Exception as _e:
            logger.debug(f"_bot_notify failed: {_e}")

    def _redirect(self, loc):
        self.send_response(302)
        self.send_header("Location", loc)
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length",0))
        if not length: return {}
        raw = self.rfile.read(length)
        try: return json_module.loads(raw)
        except:
            from urllib.parse import parse_qs as pqs
            d = pqs(raw.decode())
            return {k: v[0] for k,v in d.items()}

    def _handle_crm_api(self, method, path):
        """Public CRM CRUD API — /api/crm/contacts[/{id}[/notes]] and /api/crm/deals[/{id}]."""
        from urllib.parse import parse_qs, urlparse
        parsed  = urlparse(self.path)
        qs_p    = parse_qs(parsed.query)
        parts   = [p for p in path.split("/") if p]
        sub     = parts[2] if len(parts) > 2 else ""
        cid     = parts[3] if len(parts) > 3 else ""
        action  = parts[4] if len(parts) > 4 else ""
        try:
            if sub == "contacts":
                if method == "GET" and not cid:
                    stype = (qs_p.get("type") or [None])[0]
                    items = db.get_crm_contacts(contact_type=stype)
                    return self._send_json({"total": len(items), "items": items})
                if method == "POST" and not cid:
                    b = self._read_body()
                    nid = db.add_crm_contact({
                        "contact_type": b.get("contact_type", "agent"),
                        "name":    b.get("name", ""),
                        "phone":   b.get("phone", ""),
                        "telegram":b.get("telegram", ""),
                        "region":  b.get("region", ""),
                        "city":    b.get("city", ""),
                        "notes":   b.get("notes", ""),
                    })
                    return self._send_json({"ok": True, "id": nid})
                if method in ("PATCH", "PUT") and cid and not action:
                    return self._send_json({"ok": db.update_crm_contact(cid, self._read_body())})
                if method == "DELETE" and cid and not action:
                    return self._send_json({"ok": db.deactivate_crm_contact(cid)})
                if method == "GET" and cid and action == "notes":
                    return self._send_json({"items": db.get_crm_notes(int(cid))})
                if method == "POST" and cid and action == "notes":
                    b = self._read_body()
                    db.add_crm_note(int(cid), b.get("text", ""), 0)
                    return self._send_json({"ok": True})
            elif sub == "deals":
                if method == "GET" and not cid:
                    status = (qs_p.get("status") or [None])[0]
                    items  = db.get_crm_deals(status=status)
                    return self._send_json({"total": len(items), "items": items})
                if method == "POST" and not cid:
                    b = self._read_body()
                    db.add_crm_deal({
                        "contact_id":  b.get("contact_id", ""),
                        "description": b.get("description", ""),
                        "amount":      b.get("amount", 0),
                        "status":      b.get("status", "new"),
                    })
                    return self._send_json({"ok": True})
                if method in ("PATCH", "PUT") and cid:
                    b = self._read_body()
                    return self._send_json({"ok": db.update_crm_deal_status(cid, b.get("status", "new"))})
            else:
                return self._send_json(db.get_crm_stats())
        except Exception as e:
            return self._send_json({"error": str(e)})
        self._send_json({"error": "not found"}, 404)

    def _handle_backoffice(self, method, path):
        from urllib.parse import parse_qs as pqs

        # login page
        if path in ("/backoffice/login","/backoffice/login/"):
            if method == "GET":
                error = "?error=1" in self.path
                html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Back-office Login</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#f5f5f0;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;border-radius:16px;padding:40px 36px;width:360px;box-shadow:0 4px 20px rgba(0,0,0,.10)}}
h1{{font-size:22px;font-weight:700;color:#222;margin-bottom:6px}}p{{font-size:13px;color:#888;margin-bottom:28px}}
label{{font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:6px}}
input{{width:100%;padding:11px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;outline:none}}
input:focus{{border-color:#2AABEE}}
button{{width:100%;margin-top:18px;padding:12px;background:#2AABEE;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
button:hover{{background:#1a9de0}}.err{{color:#E24B4A;font-size:12px;margin-top:10px;text-align:center}}</style></head>
<body><div class="card"><h1>🏠 Back-office</h1><p>FlatFinderIL Admin Panel</p>
<form method="POST" action="/backoffice/login">
<label>Пароль</label><input type="password" name="password" autofocus placeholder="Введите пароль...">
<button type="submit">Войти</button>
{'<div class="err">❌ Неверный пароль</div>' if error else ''}
</form></div></body></html>"""
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return
            if method == "POST":
                length = int(self.headers.get("Content-Length",0))
                raw = self.rfile.read(length).decode()
                params = pqs(raw)
                password = (params.get("password") or [""])[0]
                if hmac.compare_digest(password, BACKOFFICE_PASSWORD):
                    token = _bo_create_session()
                    self.send_response(302)
                    self.send_header("Location","/backoffice")
                    self.send_header("Set-Cookie",f"bo_session={token}; HttpOnly; SameSite=Strict; Max-Age=86400; Path=/")
                    self.end_headers()
                else:
                    self._redirect("/backoffice/login?error=1")
                return

        # logout
        if path == "/backoffice/logout":
            _bo_delete_session(self.headers)
            self.send_response(302)
            self.send_header("Location","/backoffice/login")
            self.send_header("Set-Cookie","bo_session=; HttpOnly; Max-Age=0; Path=/")
            self.end_headers()
            return

        # back-office main page
        if path in ("/backoffice","/backoffice/"):
            if not _bo_check_session(self.headers):
                return self._redirect("/backoffice/login")
            return self._send_html(BACKOFFICE_FILE)

        # Static files (promo images etc.)
        if path.startswith("/backoffice/static/"):
            if not _bo_check_session(self.headers):
                return self._redirect("/backoffice/login")
            import os as _os, mimetypes as _mt
            # Strip prefix, handle uploads/ subdirectory
            rel = path[len("/backoffice/static/"):]
            # Security: forbid path traversal
            rel = rel.replace("..", "").lstrip("/")
            base_dir = _os.path.dirname(__file__)
            if rel.startswith("uploads/"):
                file_path = _os.path.join(base_dir, "uploads", _os.path.basename(rel))
            else:
                file_path = _os.path.join(base_dir, _os.path.basename(rel))
            if _os.path.exists(file_path) and _os.path.isfile(file_path):
                ctype, _ = _mt.guess_type(file_path)
                ctype = ctype or "application/octet-stream"
                with open(file_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", len(data))
                self.send_header("Cache-Control", "max-age=3600")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()
            return

        # API routes
        if path.startswith("/backoffice/api/"):
            if not _bo_check_session(self.headers):
                return self._send_json({"error":"Unauthorized"}, 401)
            return self._handle_bo_api(method, path)

        self._send_json({"error":"Not found"}, 404)

    def _handle_bo_api(self, method, path):
        import database as db
        parts = [p for p in path.split("/") if p]
        # parts: ["backoffice","api","resource","id","action"]
        resource = parts[2] if len(parts) > 2 else ""
        rid      = parts[3] if len(parts) > 3 else ""
        action   = parts[4] if len(parts) > 4 else ""
        qs = parse_qs(urlparse(self.path).query)
        def qp(k, d=None): return (qs.get(k) or [d])[0]

        # stats
        if resource == "stats":
            import psycopg2 as _pg, os as _os
            _db_url = _os.environ.get("DATABASE_URL")
            if _db_url:
                _c = _pg.connect(_db_url)
                _cur = _c.cursor()
                _cur.execute("SELECT COUNT(*) FROM listings"); total_l = _cur.fetchone()[0]
                _cur.execute("SELECT COUNT(*) FROM listings WHERE active=true"); active_l = _cur.fetchone()[0]
                _cur.execute("SELECT COUNT(*) FROM bot_users"); total_u = _cur.fetchone()[0]
                _cur.execute("SELECT COUNT(*) FROM search_subscriptions"); total_subs = _cur.fetchone()[0]
                _cur.execute("SELECT COUNT(*) FROM paid_subscriptions"); total_paid = _cur.fetchone()[0]
                _cur.execute("SELECT COUNT(*) FROM services"); total_svcs = _cur.fetchone()[0]
                _cur.execute("SELECT COUNT(*) FROM services WHERE active=true"); active_svcs = _cur.fetchone()[0]
                _c.close()
                emails = len(db.get_all_agent_emails()) if hasattr(db,'get_all_agent_emails') else 0
                return self._send_json({
                    "total_listings": total_l,
                    "active_listings": active_l,
                    "total_services": total_svcs,
                    "active_services": active_svcs,
                    "total_users": total_u,
                    "total_subscriptions": total_subs,
                    "total_paid": total_paid,
                    "total_crm_contacts": 0,
                    "total_crm_deals": 0,
                    "email_subscribers": emails,
                })
            else:
                data = db._load()
                listings = list(data["listings"].values())
                return self._send_json({
                    "total_listings":  len(listings),
                    "active_listings": sum(1 for l in listings if l.get("active")),
                    "total_services":  0,
                    "active_services": 0,
                    "total_users":     len(data.get("user_listings",{})),
                    "total_crm_contacts": 0,
                    "total_crm_deals": 0,
                    "email_subscribers": 0,
                })

        # listings
        if resource == "listings":
            if method == "GET" and not rid:
                filters = {}
                q = qp("q"); city = qp("city"); deal = qp("deal_type")
                ptype = qp("property_type"); active_qs = qp("active")
                if q: filters["q"] = q
                if city: filters["city"] = city
                if deal: filters["deal_type"] = deal
                if ptype: filters["property_type"] = ptype
                if active_qs == "true":  filters["active"] = True
                if active_qs == "false": filters["active"] = False
                all_l = db.get_all_listings_admin(filters or None)
                page = int(qp("page",1)); per_page = int(qp("per_page",50))
                start = (page-1)*per_page
                return self._send_json({"total":len(all_l),"page":page,"per_page":per_page,"items":all_l[start:start+per_page]})
            if method == "GET" and rid:
                l = db.get_listing(int(rid))
                return self._send_json(l) if l else self._send_json({"error":"Not found"},404)
            if method == "PATCH" and rid and action == "toggle":
                l = db.get_listing(int(rid))
                if not l: return self._send_json({"error":"Not found"},404)
                new_active = not l.get("active",True)
                db.update_listing(int(rid),{"active":new_active})
                return self._send_json({"ok":True,"active":new_active})
            if method == "PATCH" and rid:
                fields = self._read_body(); fields.pop("id",None)
                return self._send_json({"ok": db.update_listing(int(rid),fields)})
            if method == "DELETE" and rid:
                return self._send_json({"ok": db.admin_delete_listing(int(rid))})

        # users
        if resource == "users":
            if method == "GET" and not rid:
                if hasattr(db, 'get_all_bot_users'):
                    users = db.get_all_bot_users(limit=int(qp("per_page",200)), offset=(int(qp("page",1))-1)*int(qp("per_page",200)))
                    total = db.get_bot_users_count() if hasattr(db,'get_bot_users_count') else len(users)
                else:
                    users = db.get_all_users_admin()
                    total = len(users)
                return self._send_json({"total": total, "items": users})
            if method == "GET" and rid:
                profile = {}
                listings = []
                import os as _os2
                _db_url2 = _os2.environ.get("DATABASE_URL")
                if _db_url2:
                    import psycopg2 as _pg2
                    from psycopg2.extras import RealDictCursor as _RDC
                    _c2 = _pg2.connect(_db_url2, cursor_factory=_RDC)
                    _cur2 = _c2.cursor()
                    # Merge bot_users + agent_profiles
                    _cur2.execute("""
                        SELECT bu.*, ap.email, ap.owner_name, ap.owner_phone,
                               ap.lang AS agent_lang, ps.plan_type, ps.expiry_iso
                        FROM bot_users bu
                        LEFT JOIN agent_profiles ap ON ap.user_id = bu.user_id
                        LEFT JOIN paid_subscriptions ps ON ps.user_id = bu.user_id
                        WHERE bu.user_id = %s
                    """, (int(rid),))
                    row = _cur2.fetchone()
                    if row:
                        profile = dict(row)
                        profile["lang"] = profile.get("agent_lang") or profile.get("lang") or "ru"
                        if profile.get("expiry_iso"):
                            profile["expiry_iso"] = profile["expiry_iso"].isoformat()
                        if profile.get("first_seen"):
                            profile["first_seen"] = profile["first_seen"].isoformat()
                        if profile.get("last_seen"):
                            profile["last_seen"] = profile["last_seen"].isoformat()
                    _cur2.execute("""
                        SELECT l.* FROM listings l
                        JOIN user_listings ul ON ul.listing_id = l.id
                        WHERE ul.user_id = %s ORDER BY l.id DESC
                    """, (int(rid),))
                    listings = [dict(r) for r in _cur2.fetchall()]
                    for l in listings:
                        if l.get("date_added") and hasattr(l["date_added"], "isoformat"):
                            l["date_added"] = l["date_added"].isoformat()
                    _c2.close()
                else:
                    data = db._load()
                    profile = data.get("agent_profiles", {}).get(rid, {})
                    lid_list = data.get("user_listings", {}).get(rid, [])
                    listings = [data["listings"][str(l)] for l in lid_list if str(l) in data["listings"]]
                return self._send_json({"user_id": rid, "profile": profile, "listings": listings})

        # services
        if resource == "services":
            if method == "GET" and not rid:
                try:
                    svcs = db.get_all_services()
                except Exception:
                    data = db._load()
                    svcs = list(data.get("services",{}).values())
                stype = qp("type"); active_qs = qp("active")
                if stype: svcs = [s for s in svcs if s.get("service_type")==stype]
                if active_qs=="true":  svcs=[s for s in svcs if s.get("active",True)]
                if active_qs=="false": svcs=[s for s in svcs if not s.get("active",True)]
                svcs.sort(key=lambda x:x.get("date_added",""),reverse=True)
                return self._send_json({"total":len(svcs),"items":svcs})
            if method == "GET" and rid:
                try:
                    all_svcs = db.get_all_services()
                    svc = next((s for s in all_svcs if str(s.get("id","")) == str(rid)), None)
                except Exception:
                    data = db._load()
                    svc = data.get("services",{}).get(rid)
                if not svc: return self._send_json({"error":"Not found"},404)
                return self._send_json(svc)
            if method == "PATCH" and rid and action == "toggle":
                data = db._load()
                svc = data.get("services",{}).get(rid)
                if not svc: return self._send_json({"error":"Not found"},404)
                new_active = not svc.get("active",True)
                db.update_service(rid,{"active":new_active})
                return self._send_json({"ok":True,"active":new_active})
            if method == "PATCH" and rid:
                fields = self._read_body(); fields.pop("id",None)
                return self._send_json({"ok": db.update_service(rid,fields)})
            if method == "POST":
                b = self._read_body()
                b.setdefault("active", True)
                b.setdefault("source", "backoffice")
                sid = db.add_service(b)
                return self._send_json({"ok": True, "id": sid})
            if method == "DELETE" and rid:
                return self._send_json({"ok": db.delete_service(rid)})

        # CRM
        if resource == "crm":
            sub = rid; cid = action; act = parts[5] if len(parts)>5 else ""
            if sub == "contacts":
                if method=="GET" and not cid:
                    stype=qp("type"); contacts=db.get_crm_contacts(contact_type=stype)
                    return self._send_json({"total":len(contacts),"items":contacts})
                if method=="POST":
                    b=self._read_body()
                    new_id=db.add_crm_contact({"contact_type":b.get("contact_type","agent"),"name":b.get("name",""),"phone":b.get("phone",""),"telegram":b.get("telegram",""),"region":b.get("region",""),"city":b.get("city",""),"notes":b.get("notes","")})
                    return self._send_json({"ok":True,"id":new_id})
                if method=="PATCH" and cid:
                    return self._send_json({"ok":db.update_crm_contact(cid,self._read_body())})
                if method=="DELETE" and cid:
                    return self._send_json({"ok":db.deactivate_crm_contact(cid)})
                if method=="GET" and cid and act=="notes":
                    return self._send_json({"items":db.get_crm_notes(cid)})
                if method=="POST" and cid and act=="notes":
                    b=self._read_body(); db.add_crm_note(int(cid),b.get("text",""),0)
                    return self._send_json({"ok":True})
            if sub == "deals":
                if method=="GET":
                    status=qp("status"); deals=db.get_crm_deals()
                    if status: deals=[d for d in deals if d.get("status")==status]
                    return self._send_json({"total":len(deals),"items":deals})
                if method=="POST":
                    b=self._read_body(); db.add_crm_deal({"contact_id":b.get("contact_id",""),"description":b.get("description",""),"amount":b.get("amount",0),"status":b.get("status","new")})
                    return self._send_json({"ok":True})
                if method=="PATCH" and cid:
                    b=self._read_body()
                    return self._send_json({"ok":db.update_crm_deal_status(cid,b.get("status","new"))})

        # sources — GET /backoffice/api/sources  (parsing sources from PG)
        if resource == "sources" and method == "GET":
            if hasattr(db, "get_sources_stats"):
                return self._send_json(db.get_sources_stats())
            return self._send_json({"telegram": [], "facebook": [], "other": []})

        # analytics users — GET /backoffice/api/analytics-users  (from stats.json)
        if resource == "analytics-users" and method == "GET":
            try:
                from analytics import _load_stats
                stats = _load_stats()
                users = stats.get("users", {})
                return self._send_json({
                    "total": len(users),
                    "items": [
                        {"user_id": uid, **udata}
                        for uid, udata in users.items()
                    ]
                })
            except Exception as e:
                return self._send_json({"error": str(e), "total": 0, "items": []})

        # ── Accounts management ──────────────────────────────────────────────────
        # POST /backoffice/api/accounts/grant  — issue subscription
        if resource == "accounts" and rid == "grant" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                plan = body.get("plan", "month")
                expiry_iso = body.get("expiry_iso")
                days = int(body.get("days", 30))
                if not uid or not expiry_iso:
                    return self._send_json({"ok": False, "error": "user_id и expiry_iso обязательны"}, 400)
                db.set_user_paid_subscription(uid, plan, expiry_iso)
                # Notify user in Telegram
                try:
                    import asyncio as _aio
                    exp_str = expiry_iso[:10]
                    msg = f"🎁 <b>Подписка активирована администратором!</b>\n\nВаша подписка активна до <b>{exp_str}</b>.\nСпасибо!"
                    _aio.run_coroutine_threadsafe(
                        self._bot_notify(uid, msg),
                        asyncio.get_event_loop()
                    )
                except Exception:
                    pass
                logger.info(f"[ACCOUNTS] Granted {plan} subscription to user {uid} until {expiry_iso}")
                return self._send_json({"ok": True, "user_id": uid, "expiry_iso": expiry_iso})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # POST /backoffice/api/accounts/bonus  — add bonus days
        if resource == "accounts" and rid == "bonus" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                days = int(body.get("days", 0))
                if not uid or not days:
                    return self._send_json({"ok": False, "error": "user_id и days обязательны"}, 400)
                db.add_bonus_days(uid, days)
                try:
                    import asyncio as _aio
                    msg = f"🎁 <b>Бонус от администратора!</b>\n\nВам начислено <b>+{days} дней</b> подписки."
                    _aio.run_coroutine_threadsafe(self._bot_notify(uid, msg), asyncio.get_event_loop())
                except Exception:
                    pass
                logger.info(f"[ACCOUNTS] +{days} bonus days to user {uid}")
                return self._send_json({"ok": True})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # POST /backoffice/api/accounts/set-status
        if resource == "accounts" and rid == "set-status" and method == "POST":
            try:
                uid = int(body.get("user_id", 0))
                action = body.get("action", "")
                subscribed = body.get("subscribed")
                if not uid:
                    return self._send_json({"ok": False, "error": "user_id обязателен"}, 400)
                from analytics import _load_stats, _save_stats
                stats = _load_stats()
                u = stats.get("users", {}).get(str(uid))
                if action == "blocked":
                    if u: u["blocked"] = True
                    msg = "🚫 Ваш аккаунт был заблокирован администратором."
                elif action == "active":
                    if u:
                        u["blocked"] = False
                        u["subscribed"] = True
                    msg = "✅ Ваш аккаунт активирован администратором."
                elif action == "reset":
                    if u: u["subscribed"] = False
                    msg = None
                elif subscribed is not None:
                    if u: u["subscribed"] = bool(subscribed)
                    msg = None
                else:
                    msg = None
                _save_stats(stats)
                if msg:
                    try:
                        import asyncio as _aio
                        _aio.run_coroutine_threadsafe(self._bot_notify(uid, msg), asyncio.get_event_loop())
                    except Exception:
                        pass
                logger.info(f"[ACCOUNTS] set-status action={action} subscribed={subscribed} for user {uid}")
                return self._send_json({"ok": True})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── Promo codes ───────────────────────────────────────────────────────────
        if resource == "promo-codes":
            from analytics import _load_stats, _save_stats
            if method == "GET" and not rid:
                stats = _load_stats()
                items = list(stats.get("promo_codes", {}).values())
                items.sort(key=lambda x: x.get("created", ""), reverse=True)
                return self._send_json({"items": items})

            if method == "POST":
                code = (body.get("code") or "").strip().upper()
                if not code:
                    return self._send_json({"ok": False, "error": "Код обязателен"}, 400)
                stats = _load_stats()
                if "promo_codes" not in stats:
                    stats["promo_codes"] = {}
                if code in stats["promo_codes"]:
                    return self._send_json({"ok": False, "error": "Такой код уже существует"}, 409)
                stats["promo_codes"][code] = {
                    "code":      code,
                    "type":      body.get("type", "days"),
                    "value":     int(body.get("value", 7)),
                    "max_uses":  int(body.get("max_uses", 0)),
                    "expiry":    body.get("expiry"),
                    "used":      0,
                    "created":   datetime.now().isoformat(),
                    "active":    True,
                }
                _save_stats(stats)
                logger.info(f"[PROMO] Created promo code {code}")
                return self._send_json({"ok": True, "code": code})

            if method == "DELETE" and rid:
                stats = _load_stats()
                code = rid.upper()
                if code in stats.get("promo_codes", {}):
                    del stats["promo_codes"][code]
                    _save_stats(stats)
                    logger.info(f"[PROMO] Deleted promo code {code}")
                return self._send_json({"ok": True})

        # email subscribers
        if resource == "email-subscribers":
            if method=="GET":
                agents=db.get_all_agent_emails()
                try: svcs=db.get_all_service_emails()
                except: svcs=[]
                combined=[{**a,"subscriber_type":"agent"} for a in agents]+[{**s,"subscriber_type":s.get("service_type","service")} for s in svcs]
                return self._send_json({"total":len(combined),"items":combined})
            if method=="POST" and rid=="send-now":
                from email_reporter import send_all_weekly_reports
                threading.Thread(target=send_all_weekly_reports, daemon=True).start()
                return self._send_json({"ok":True,"queued":True})
            if method=="POST" and rid:
                from email_reporter import send_report
                try: ok=send_report(int(rid))
                except Exception as e: ok=False
                return self._send_json({"ok":ok})

        # subscriptions (stats.json + paid_subscriptions in DB)
        if resource == "subscriptions":
            from analytics import _load_stats, _save_stats
            if method == "GET":
                data = _load_stats()
                subs = data.get("subscriptions", {})
                return self._send_json({"total": len(subs), "items": subs})
            if method == "DELETE" and rid:
                # Remove from stats.json subscriptions
                data = _load_stats()
                subs = data.get("subscriptions", {})
                removed_stats = subs.pop(rid, None)
                if rid in data.get("users", {}):
                    data["users"][rid]["subscribed"] = False
                data["subscriptions"] = subs
                _save_stats(data)
                # Remove from listings_db.json paid_subscriptions
                db_data = db._load()
                removed_db = db_data.get("paid_subscriptions", {}).pop(rid, None)
                db._save(db_data)
                return self._send_json({"ok": True, "removed_stats": removed_stats, "removed_db": removed_db})

        # payments log
        if resource == "payments":
            from analytics import _load_stats, _save_stats
            if method == "GET":
                data = _load_stats()
                log = data.get("payments_log", [])
                return self._send_json({"total": len(log), "items": log})
            if method == "DELETE" and rid:
                try:
                    i = int(rid)
                except ValueError:
                    return self._send_json({"error": "Invalid index"}, 400)
                data = _load_stats()
                log = data.get("payments_log", [])
                if i < 0 or i >= len(log):
                    return self._send_json({"error": "Index out of range"}, 404)
                removed = log.pop(i)
                data["payments_log"] = log
                _save_stats(data)
                return self._send_json({"ok": True, "removed": removed})

        # support messages
        if resource == "support-messages":
            if method == "GET":
                msgs = db.get_support_messages(limit=200)
                return self._send_json({"total": len(msgs), "items": msgs})
            if method == "POST" and not rid:
                body = self._read_body()
                msg_id = db.add_support_message(
                    user_id=int(body.get("user_id", 0)),
                    username=body.get("username", ""),
                    first_name=body.get("first_name", ""),
                    lang=body.get("lang", "ru"),
                    text=body.get("text", ""),
                )
                return self._send_json({"ok": True, "id": msg_id})
            if method == "DELETE" and rid:
                ok = db.delete_support_message(int(rid))
                return self._send_json({"ok": ok})
            if method == "PATCH" and rid and action == "read":
                ok = db.mark_support_message_read(int(rid))
                return self._send_json({"ok": ok})
            if method == "POST" and rid and action == "reply":
                body = self._read_body()
                reply_text = body.get("text", "").strip()
                if not reply_text:
                    return self._send_json({"error": "text required"}, 400)
                entry = db.reply_support_message(int(rid), reply_text)
                if not entry:
                    return self._send_json({"error": "Not found"}, 404)
                # Relay reply to user via Telegram
                target_uid = entry["user_id"]
                target_lang = entry.get("lang", "ru")
                prefix = {
                    "ru": "📩 <b>Ответ от администрации:</b>\n\n",
                    "en": "📩 <b>Reply from the administration:</b>\n\n",
                    "he": "📩 <b>תשובה מההנהלה:</b>\n\n",
                }.get(target_lang, "📩 <b>Ответ от администрации:</b>\n\n")
                try:
                    if _bot_app and _bot_loop:
                        future = asyncio.run_coroutine_threadsafe(
                            _bot_app.bot.send_message(
                                chat_id=target_uid,
                                text=prefix + reply_text,
                                parse_mode="HTML",
                            ),
                            _bot_loop,
                        )
                        future.result(timeout=10)
                except Exception as e:
                    logger.error(f"[SUPPORT] relay reply failed: {e}")
                return self._send_json({"ok": True})

        # logout via API
        if resource == "logout":
            _bo_delete_session(self.headers)
            return self._send_json({"ok":True})

        # broadcast — POST /backoffice/api/broadcast
        if resource == "broadcast" and method == "POST":
            body = self._read_body()
            texts = body.get("texts", {})   # {"ru": "...", "en": "...", "he": "..."}
            default_text = body.get("text", "")
            if not texts and not default_text:
                return self._send_json({"error": "texts or text required"}, 400)

            from analytics import _load_stats
            stats_data = _load_stats()
            all_users = stats_data.get("users", {})

            if not _bot_app or not _bot_loop:
                return self._send_json({"error": "bot not running"}, 503)

            sent = 0; failed = 0; blocked = 0
            for uid_str, udata in all_users.items():
                lang = udata.get("lang", "ru") or "ru"
                msg = texts.get(lang) or texts.get("ru") or default_text
                if not msg:
                    continue
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        _bot_app.bot.send_message(
                            chat_id=int(uid_str),
                            text=msg,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        ),
                        _bot_loop,
                    )
                    future.result(timeout=8)
                    sent += 1
                except Exception as e:
                    err_str = str(e).lower()
                    if "blocked" in err_str or "deactivated" in err_str or "forbidden" in err_str:
                        blocked += 1
                    else:
                        failed += 1
                    logger.warning(f"[BROADCAST] uid={uid_str}: {e}")
            return self._send_json({"ok": True, "sent": sent, "blocked": blocked, "failed": failed,
                                    "total": len(all_users)})

        # fb-post — POST /backoffice/api/fb-post
        if resource == "fb-post" and method == "POST":
            body = self._read_body()
            message = body.get("message", "").strip()
            group_ids = body.get("group_ids", [])  # [] = все группы
            dry_run   = bool(body.get("dry_run", False))
            if not message:
                return self._send_json({"error": "message required"}, 400)
            try:
                import subprocess, sys as _sys, os as _os
                script = _os.path.join(_os.path.dirname(__file__), "facebook_poster.py")
                import tempfile, json as _json
                # Записываем сообщение во временный файл
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                                  delete=False, encoding='utf-8') as tf:
                    tf.write(message)
                    tmp_path = tf.name
                cmd = [_sys.executable, script, "--file", tmp_path, "--pause", "15"]
                if group_ids:
                    cmd += ["--groups", ",".join(str(g) for g in group_ids)]
                if dry_run:
                    cmd += ["--dry-run"]
                # Запускаем в фоне, не ждём завершения
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=_os.path.dirname(__file__),
                )
                return self._send_json({
                    "ok": True,
                    "pid": proc.pid,
                    "groups": len(group_ids) if group_ids else "all",
                    "message": "Рассылка запущена в фоне. Результаты в fb_posting_log.json",
                })
            except Exception as e:
                logger.error(f"[FB-POST] {e}")
                return self._send_json({"error": str(e)}, 500)

        # db-export — GET /backoffice/api/db-export  (download full listings_db.json)
        if resource == "db-export" and method == "GET":
            import os as _os, json as _json
            # With PG backend, read directly from volume JSON file
            _data_dir = _os.environ.get("DATA_DIR", _os.path.dirname(_os.path.abspath(__file__)))
            _json_path = _os.path.join(_data_dir, "listings_db.json")
            if _os.path.exists(_json_path):
                with open(_json_path, encoding="utf-8") as _f:
                    data = _json.load(_f)
            else:
                import database as _db
                data = _db._load()
            body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="listings_db.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # db-import — POST /backoffice/api/db-import  (upload full listings_db.json)
        if resource == "db-import" and method == "POST":
            import database as _db, json as _json, os as _os
            body = self._read_body()
            incoming = body.get("data")
            if not incoming:
                return self._send_json({"error": "data required"}, 400)
            try:
                if isinstance(incoming, str):
                    incoming = _json.loads(incoming)
                # Merge: keep existing listings, add new ones
                current = _db._load()
                existing_ids = set(current.get("listings", {}).keys())
                new_listings = incoming.get("listings", {})
                added = 0
                for lid, listing in new_listings.items():
                    if lid not in existing_ids:
                        current.setdefault("listings", {})[lid] = listing
                        added += 1
                # Update next_id
                all_ids = [int(i) for i in current["listings"].keys() if str(i).isdigit()]
                current["next_id"] = max(all_ids) + 1 if all_ids else 1
                _db._save(current)
                return self._send_json({"ok": True, "added": added, "total": len(current["listings"])})
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        # fb-post-log — GET /backoffice/api/fb-post-log
        if resource == "fb-post-log" and method == "GET":
            import os as _os, json as _json
            log_file = _os.path.join(_os.path.dirname(__file__), "fb_posting_log.json")
            if _os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    return self._send_json(_json.load(f))
            return self._send_json([])

        # fb-cookies — POST /backoffice/api/fb-cookies  (save Facebook cookies)
        if resource == "fb-cookies" and method == "POST":
            import os as _os, json as _json
            body = self._read_body()
            raw = body.get("cookies", "").strip()
            if not raw:
                return self._send_json({"error": "cookies required"}, 400)
            try:
                # Validate JSON
                parsed = _json.loads(raw)
                if not isinstance(parsed, (list, dict)):
                    raise ValueError("Expected JSON array or object")
                # Save to database (persistent across deploys)
                import database as _db
                _db.set_fb_cookies(raw)
                # Also set in current process env + restart parser if not running
                _os.environ["FB_COOKIES_JSON"] = raw
                # Try to (re)start parser
                try:
                    from facebook_parser import run_loop as _run_loop
                    import threading as _thr, traceback as _tb
                    def _fb_restart():
                        import database as _db2
                        try:
                            _db2.set_setting("fb_parser_status", "running")
                            _db2.set_setting("fb_parser_started_at", datetime.now().isoformat())
                            _run_loop(interval_min=60)
                        except Exception as _e:
                            err = f"{_e}\n{_tb.format_exc()[-2000:]}"
                            logger.error(f"FB parser restart error: {_e}")
                            try:
                                _db2.set_setting("fb_parser_status", "error")
                                _db2.set_setting("fb_parser_last_error", err)
                                _db2.set_setting("fb_parser_error_at", datetime.now().isoformat())
                            except Exception:
                                pass
                    _t = _thr.Thread(target=_fb_restart, daemon=True, name="fb-parser-restart")
                    _t.start()
                    logger.info("Facebook parser (re)started with new cookies")
                except Exception as _e:
                    logger.warning(f"Could not restart FB parser: {_e}")
                cookie_count = len(parsed) if isinstance(parsed, list) else len(parsed)
                return self._send_json({"ok": True, "cookie_count": cookie_count,
                                        "message": f"✅ {cookie_count} cookies saved, parser started"})
            except Exception as e:
                return self._send_json({"error": str(e)}, 400)

        # ig-session — POST /backoffice/api/ig-session  (save sessionid from user)
        if resource == "ig-session" and method == "POST":
            import os as _os, json as _json
            from urllib.parse import unquote as _unquote
            body = self._read_body()
            raw  = body.get("sessionid", "").strip()
            # Accept "sessionid=VALUE" or just "VALUE"
            if raw.startswith("sessionid="):
                raw = raw[len("sessionid="):]
            # URL-decode: %3A → : etc.
            raw = _unquote(raw)
            if not raw:
                return self._send_json({"error": "sessionid required"}, 400)
            try:
                # Save sessionid directly — skip instagrapi API verification
                # (Instagram blocks API calls from server IPs)
                session_data = {
                    "uuids": {},
                    "cookies": {"sessionid": raw},
                    "last_login": 0,
                    "device_settings": {},
                    "user_agent": "Instagram 269.0.0.18.75 Android",
                }
                session_json = _json.dumps(session_data, ensure_ascii=False)
                session_file = _os.path.join(_os.path.dirname(__file__), "ig_session.json")
                with open(session_file, "w", encoding="utf-8") as f:
                    f.write(session_json)
                _os.environ["IG_SESSION_JSON"] = session_json
                # Persist in database so session survives redeployments
                import database as _db
                _db.set_ig_session(raw)
                _db.set_ig_settings_json(session_json)  # full settings → survives redeploys
                return self._send_json({
                    "ok": True,
                    "username": "flatfinderil",
                    "message": "✅ Session saved. Try posting to verify.",
                })
            except Exception as e:
                return self._send_json({"error": str(e)}, 400)

        # ig-post — POST /backoffice/api/ig-post
        if resource == "ig-post" and method == "POST":
            body    = self._read_body()
            caption = body.get("caption", "").strip()
            image   = body.get("image", "").strip()   # имя файла из uploads/ или promo_dayN.jpg
            dry_run = bool(body.get("dry_run", False))
            if not caption:
                return self._send_json({"error": "caption required"}, 400)
            import os as _os, sys as _sys
            # Разрешаем путь к изображению
            if image:
                base_dir = _os.path.dirname(__file__)
                for candidate in [
                    _os.path.join(base_dir, "uploads", image),
                    _os.path.join(base_dir, image),
                ]:
                    if _os.path.exists(candidate):
                        image = candidate
                        break
                else:
                    image = None
            try:
                _sys.path.insert(0, _os.path.dirname(__file__))
                from instagram_poster import post_to_instagram
                result = post_to_instagram(
                    caption=caption,
                    image_path=image or None,
                    dry_run=dry_run,
                )
                return self._send_json(result)
            except Exception as e:
                logger.error(f"[IG-POST] {e}")
                return self._send_json({"error": str(e)}, 500)

        # ig-post-log — GET /backoffice/api/ig-post-log
        if resource == "ig-post-log" and method == "GET":
            import os as _os, json as _json
            log_file = _os.path.join(_os.path.dirname(__file__), "ig_posting_log.json")
            if _os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    return self._send_json(_json.load(f))
            return self._send_json([])

        # images — GET /backoffice/api/images  (list uploaded images)
        if resource == "images" and method == "GET":
            import os as _os
            uploads_dir = _os.path.join(_os.path.dirname(__file__), "uploads")
            _os.makedirs(uploads_dir, exist_ok=True)
            IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}
            files = sorted(
                f for f in _os.listdir(uploads_dir)
                if _os.path.splitext(f)[1].lower() in IMAGE_EXT
            )
            return self._send_json(files)

        # images — POST /backoffice/api/images  (upload image, base64 JSON)
        if resource == "images" and method == "POST":
            import os as _os, base64 as _b64, re as _re, mimetypes as _mt
            body = self._read_body()
            raw_name = body.get("filename", "upload.jpg")
            data_b64 = body.get("data", "")
            if not data_b64:
                return self._send_json({"error": "data required"}, 400)
            # Sanitise filename
            safe_name = _re.sub(r"[^\w.\-]", "_", _os.path.basename(raw_name))
            if not safe_name:
                safe_name = "upload.jpg"
            ext = _os.path.splitext(safe_name)[1].lower()
            VIDEO_EXT = {".mp4", ".mov"}
            IMAGE_EXT_UP = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            if ext not in IMAGE_EXT_UP | VIDEO_EXT:
                return self._send_json({"error": "unsupported file type"}, 400)
            MAX_SIZE = 50 * 1024 * 1024 if ext in VIDEO_EXT else 10 * 1024 * 1024
            # Avoid overwrites — add suffix if exists
            uploads_dir = _os.path.join(_os.path.dirname(__file__), "uploads")
            _os.makedirs(uploads_dir, exist_ok=True)
            dest = _os.path.join(uploads_dir, safe_name)
            if _os.path.exists(dest):
                base, ex = _os.path.splitext(safe_name)
                import time as _time
                safe_name = f"{base}_{int(_time.time())}{ex}"
                dest = _os.path.join(uploads_dir, safe_name)
            try:
                raw_bytes = _b64.b64decode(data_b64)
            except Exception as e:
                return self._send_json({"error": f"base64 decode error: {e}"}, 400)
            if len(raw_bytes) > MAX_SIZE:
                size_label = "50 MB" if ext in VIDEO_EXT else "10 MB"
                return self._send_json({"error": f"file too large (max {size_label})"}, 413)
            with open(dest, "wb") as f:
                f.write(raw_bytes)
            logger.info(f"[UPLOAD] {safe_name} ({len(raw_bytes)//1024} KB)")
            return self._send_json({"ok": True, "filename": safe_name,
                                    "url": f"/backoffice/static/uploads/{safe_name}"})

        # images — DELETE /backoffice/api/images/<name>
        if parts[0] == "images" and len(parts) == 2 and method == "DELETE":
            import os as _os, re as _re
            raw_name = parts[1]
            safe_name = _re.sub(r"[^\w.\-]", "_", _os.path.basename(raw_name))
            uploads_dir = _os.path.join(_os.path.dirname(__file__), "uploads")
            dest = _os.path.join(uploads_dir, safe_name)
            if _os.path.exists(dest) and _os.path.isfile(dest):
                _os.remove(dest)
                logger.info(f"[DELETE IMG] {safe_name}")
                return self._send_json({"ok": True})
            return self._send_json({"error": "not found"}, 404)

        self._send_json({"error":"Not found"},404)

    # ── HEAD: mirrors GET headers without body (required for GSC verification) ──
    def do_HEAD(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        host   = _request_host(self.headers)

        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", 15)
            self.end_headers()
            return

        if host in _PUBLIC_DOMAINS:
            if path in ("/", "/legal", "/robots.txt", "/sitemap.xml"):
                self.send_response(200)
                ct = "text/xml; charset=utf-8" if path.endswith(".xml") else (
                     "text/plain; charset=utf-8" if path.endswith(".txt") else
                     "text/html; charset=utf-8")
                self.send_header("Content-Type", ct)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ── Public domain guard ───────────────────────────────────────────
        host = _request_host(self.headers)
        if host in _PUBLIC_DOMAINS:
            default_lang = "he" if "co.il" in host else "ru"

            # ── robots.txt ────────────────────────────────────────────────
            if path == "/robots.txt":
                sitemap_domain = "https://flatfinderil.co.il" if "co.il" in host else "https://flatfinderil.com"
                body = (
                    "User-agent: *\n"
                    "Allow: /\n"
                    "Disallow: /backoffice/\n"
                    "Disallow: /api/\n\n"
                    f"Sitemap: {sitemap_domain}/sitemap.xml\n"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return

            # ── sitemap.xml ───────────────────────────────────────────────
            if path == "/sitemap.xml":
                if "co.il" in host:
                    # co.il sitemap: Hebrew version is primary
                    body = (
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
                        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
                        '  <url>\n'
                        '    <loc>https://flatfinderil.co.il/</loc>\n'
                        '    <changefreq>weekly</changefreq>\n'
                        '    <priority>1.0</priority>\n'
                        '    <xhtml:link rel="alternate" hreflang="he" href="https://flatfinderil.co.il/"/>\n'
                        '    <xhtml:link rel="alternate" hreflang="ru" href="https://flatfinderil.com/"/>\n'
                        '    <xhtml:link rel="alternate" hreflang="en" href="https://flatfinderil.com/"/>\n'
                        '    <xhtml:link rel="alternate" hreflang="x-default" href="https://flatfinderil.co.il/"/>\n'
                        '  </url>\n'
                        '</urlset>\n'
                    ).encode()
                else:
                    body = (
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
                        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
                        '  <url>\n'
                        '    <loc>https://flatfinderil.com/</loc>\n'
                        '    <changefreq>weekly</changefreq>\n'
                        '    <priority>1.0</priority>\n'
                        '    <xhtml:link rel="alternate" hreflang="ru" href="https://flatfinderil.com/"/>\n'
                        '    <xhtml:link rel="alternate" hreflang="en" href="https://flatfinderil.com/"/>\n'
                        '    <xhtml:link rel="alternate" hreflang="he" href="https://flatfinderil.co.il/"/>\n'
                        '    <xhtml:link rel="alternate" hreflang="x-default" href="https://flatfinderil.com/"/>\n'
                        '  </url>\n'
                        '  <url>\n'
                        '    <loc>https://flatfinderil.co.il/</loc>\n'
                        '    <changefreq>weekly</changefreq>\n'
                        '    <priority>0.9</priority>\n'
                        '  </url>\n'
                        '</urlset>\n'
                    ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/xml; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return

            if path in ("/", "/legal"):
                file_path = LEGAL_FILE if path == "/legal" else LANDING_FILE
                try:
                    with open(file_path, "rb") as f:
                        content = f.read()
                    content = content.replace(
                        b'data-default-lang="auto"',
                        f'data-default-lang="{default_lang}"'.encode()
                    )
                    # co.il: fix canonical + og:url to point to THIS domain
                    if "co.il" in host and path == "/":
                        content = content.replace(
                            b'<link rel="canonical" href="https://flatfinderil.com/">',
                            b'<link rel="canonical" href="https://flatfinderil.co.il/">'
                        )
                        content = content.replace(
                            b'<meta property="og:url" content="https://flatfinderil.com/">',
                            b'<meta property="og:url" content="https://flatfinderil.co.il/">'
                        )
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", len(content))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception:
                    self.send_response(500); self.end_headers()
                return
            # Google Search Console verification
            if path == "/google6c7ba3b919c578f9.html":
                body = b"google-site-verification: google6c7ba3b919c578f9.html"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return
            # Stripe success/cancel pages — allowed on public domain
            if path in ("/stripe/success", "/stripe/cancel"):
                lang_param = "he" if "co.il" in host else "ru"
                if path == "/stripe/success":
                    msgs = {
                        "ru": ("✅ Оплата прошла успешно!", "Вернитесь в бот — подписка уже активна."),
                        "en": ("✅ Payment successful!", "Return to the bot — your subscription is now active."),
                        "he": ("✅ התשלום בוצע בהצלחה!", "חזרו לבוט — המנוי שלכם פעיל."),
                    }
                else:
                    msgs = {
                        "ru": ("❌ Оплата отменена", "Вы можете попробовать снова в боте."),
                        "en": ("❌ Payment cancelled", "You can try again in the bot."),
                        "he": ("❌ התשלום בוטל", "תוכלו לנסות שוב בבוט."),
                    }
                title, sub = msgs.get(lang_param, msgs["ru"])
                html = (
                    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                    "<style>body{font-family:sans-serif;text-align:center;padding:60px 20px;background:#f0f4f8}"
                    "h1{font-size:2em}a{display:inline-block;margin-top:20px;padding:12px 28px;"
                    "background:#2563eb;color:white;border-radius:8px;text-decoration:none;font-size:1.1em}"
                    "</style></head><body>"
                    f"<h1>{title}</h1><p>{sub}</p>"
                    "<a href='https://t.me/flatfinderil_bot'>↩ Открыть бот</a>"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(html))
                self.end_headers()
                self.wfile.write(html)
                return
            # Block ALL internal pages/API on public domains
            body = b"Not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        # Health check — Railway uses this to verify the process is alive
        if path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        # Back-office routes
        if path.startswith("/backoffice"):
            return self._handle_backoffice("GET", path)

        if path == "/analytics":
            qs = parse_qs(parsed.query)
            date_from = (qs.get("from") or [None])[0]
            date_to   = (qs.get("to")   or [None])[0]
            force     = (qs.get("refresh") or ["0"])[0] == "1"

            # We always serve from cache for fast response.
            # The cache is pre-computed with no date filter (= all-time data).
            # The date params are stored in the response so the client can
            # do lightweight client-side filtering if needed.
            with _ANALYTICS_CACHE["lock"]:
                data          = _ANALYTICS_CACHE["data"]
                cache_age     = _time_mod.time() - _ANALYTICS_CACHE["ts"]
                is_refreshing = _ANALYTICS_CACHE["refreshing"]

            # NEVER compute analytics synchronously in the HTTP handler —
            # it can take 10-30 s and Railway will 502.  Always use cache.
            # Background thread keeps the cache fresh.

            if force and not is_refreshing:
                # ?refresh=1 — kick off a background refresh, return current cache
                with _ANALYTICS_CACHE["lock"]:
                    _ANALYTICS_CACHE["refreshing"] = True
                threading.Thread(
                    target=_analytics_bg_refresh, daemon=True,
                    name="analytics-refresh"
                ).start()

            if data is None:
                # Cache not warm yet — trigger background refresh if not running
                if not is_refreshing:
                    with _ANALYTICS_CACHE["lock"]:
                        _ANALYTICS_CACHE["refreshing"] = True
                    threading.Thread(
                        target=_analytics_bg_refresh, daemon=True,
                        name="analytics-refresh"
                    ).start()
                data = {"loading": True, "message": "Analytics are being computed, please retry in 30 seconds"}
            elif cache_age > 300 and not is_refreshing and not force:
                # Cache is stale — return old data now, refresh in background
                with _ANALYTICS_CACHE["lock"]:
                    _ANALYTICS_CACHE["refreshing"] = True
                threading.Thread(
                    target=_analytics_bg_refresh, daemon=True,
                    name="analytics-refresh"
                ).start()
                # data still holds the stale-but-valid cached result — serve it

            # Apply lightweight date filtering to cached all-time data
            if data and not data.get("loading") and (date_from or date_to):
                try:
                    from datetime import datetime as _dt
                    _today = _dt.now().strftime("%Y-%m-%d")
                    data = _filter_analytics_by_date(
                        data,
                        date_from or "2026-03-01",
                        date_to   or _today,
                    )
                except Exception as _fe:
                    logger.warning(f"Date filter error (returning unfiltered): {_fe}")

            try:
                body = json_module.dumps(data, ensure_ascii=False, default=str).encode()
            except Exception as _je:
                logger.error(f"Analytics JSON serialization error: {_je}")
                body = json_module.dumps({"error": f"Serialization error: {_je}"}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path in ("/news", "/api/news"):
            try:
                from news_fetcher import get_news
                qs = parse_qs(parsed.query)
                category = (qs.get("category") or qs.get("cat") or [None])[0]
                lang     = (qs.get("lang")     or [None])[0]
                region   = (qs.get("region")   or [None])[0]
                limit    = int((qs.get("limit") or qs.get("n") or ["20"])[0])
                data = get_news(category=category, lang=lang, region=region, limit=limit)
            except Exception as e:
                data = {"error": str(e), "items": [], "ticker": []}
            self._send_json(data)

        elif path == "/api/price-stats":
            try:
                from analytics_server import _get_price_stats
                qs = parse_qs(parsed.query)
                city = (qs.get("city")  or [None])[0]
                deal = (qs.get("deal")  or ["rent"])[0]
                days = int((qs.get("days") or ["30"])[0])
                data = _get_price_stats(city=city, deal_type=deal, days=days)
            except Exception as e:
                data = {"error": str(e)}
            self._send_json(data)

        elif path == "/api/datagov":
            try:
                from datagov_api import get_market_overview, get_recent_deals
                qs = parse_qs(parsed.query)
                city  = (qs.get("city")  or ["Нетания"])[0]
                rooms = (qs.get("rooms") or [None])[0]
                days  = int((qs.get("days") or ["90"])[0])
                if rooms:
                    data = get_recent_deals(city_ru=city, rooms=int(rooms), last_days=days)
                else:
                    data = get_market_overview(city_ru=city, last_days=days)
            except Exception as e:
                data = {"error": str(e)}
            self._send_json(data)

        elif path.startswith("/api/crm"):
            return self._handle_crm_api("GET", path)

        elif path == "/api/daily-digest":
            try:
                from morning_digest import get_daily_stats, build_digest_text
                qs = parse_qs(parsed.query)
                city = (qs.get("city") or [None])[0]
                lang = (qs.get("lang") or ["ru"])[0]
                stats = get_daily_stats(city=city)
                text  = build_digest_text(city=city, lang=lang, include_datagov=False)
                data  = {"stats": stats, "text": text, "lang": lang}
            except Exception as e:
                data = {"error": str(e)}
            self._send_json(data)

        elif path == "/rss.xml":
            try:
                from news_fetcher import get_news
                from analytics_server import _build_rss
                qs   = parse_qs(parsed.query)
                lang = (qs.get("lang") or ["he"])[0]
                cat  = (qs.get("cat")  or [None])[0]
                news = get_news(category=cat, lang=lang, limit=40)
                xml  = _build_rss(news.get("items", []), lang=lang, category=cat)
                body = xml.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_json({"error": str(e)})

        elif path == "/admin/cleanup-spam":
            # GET proxy for the cleanup action (legacy compat)
            try:
                from analytics_server import _cleanup_spam_listings
                result = _cleanup_spam_listings()
            except Exception as e:
                result = {"error": str(e)}
            self._send_json(result)

        elif path == "/download-pdf":
            try:
                import bot_map_pdf
                pdf_bytes, mime, fname = bot_map_pdf.generate_safe()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Disposition",
                                 f"attachment; filename={fname}")
                self.send_header("Content-Length", len(pdf_bytes))
                self.end_headers()
                self.wfile.write(pdf_bytes)
            except Exception as e:
                # generate_safe() should never raise, but be defensive.
                body = f"PDF error: {e}".encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)

        elif path.startswith("/api/admin/"):
            # All internal admin GET routes: users search, listings, promo-codes, audit-log
            qs_params = parse_qs(parsed.query)
            return self._handle_admin_api("GET", path, {}, qs_params)

        elif path in ("/miniapp", "/app", "/miniapp/"):
            # Telegram Mini App (opened via bot button)
            self._send_html(MINIAPP_FILE)

        elif path in ("/", ""):
            # Root → internal admin dashboard
            self._send_html(DASHBOARD_FILE)

        elif path.startswith("/api/miniapp/"):
            try:
                from mini_app_api import route as miniapp_route
                from urllib.parse import parse_qs as _pqs
                params  = _pqs(parsed.query)
                headers = dict(self.headers)
                result, status = miniapp_route("GET", path, params, {}, headers)
                body = json_module.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
            except Exception as e:
                body   = json_module.dumps({"error": str(e)}).encode("utf-8")
                status = 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Telegram-Init-Data")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            body = b"Not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path

        # ── Internal admin API (no session required — dashboard at / is internal) ──
        if path.startswith("/api/admin/"):
            content_len = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_len) if content_len else b"{}"
            try: body = json_module.loads(raw)
            except Exception: body = {}
            return self._handle_admin_api("POST", path, body)

        if path.startswith("/api/crm"):
            return self._handle_crm_api("POST", path)
        if path.startswith("/backoffice"):
            return self._handle_backoffice("POST", path)
        if path == "/send-message":
            return self._handle_send_message()
        if path == "/admin/cleanup-spam":
            try:
                from analytics_server import _cleanup_spam_listings
                result = _cleanup_spam_listings()
            except Exception as e:
                result = {"error": str(e)}
            return self._send_json(result)
        # ── Mini App API ──────────────────────────────────────────────────
        if path.startswith("/api/miniapp/"):
            content_len = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            try:
                body_data = json_module.loads(raw_body)
            except Exception:
                body_data = {}
            try:
                from mini_app_api import route as miniapp_route
                from urllib.parse import parse_qs as _pqs
                params  = _pqs(urlparse(self.path).query)
                headers = dict(self.headers)
                result, status = miniapp_route("POST", path, params, body_data, headers)
                body = json_module.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
            except Exception as e:
                body   = json_module.dumps({"error": str(e)}).encode("utf-8")
                status = 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        # ── Morning webhook ───────────────────────────────────────────────
        if path == "/webhook/paypal":
            return self._handle_paypal_webhook()
        self._send_json({"error":"Not found"},404)

    def _handle_paypal_webhook(self):
        """Verify Morning callback and activate subscription/credits on payment."""
        import json as _json
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)

            try:
                callback_data = _json.loads(body)
            except Exception:
                from urllib.parse import parse_qs
                callback_data = {k: v[0] for k, v in parse_qs(body.decode("utf-8", errors="replace")).items()}

            logger.info(f"[PAYPAL] Webhook received: {_json.dumps(callback_data)[:300]}")

            import paypal_payment as morning_payment
            user_id, plan_key = morning_payment.verify_and_extract(callback_data)

            if user_id and plan_key:
                logger.info(f"[PAYPAL] Payment confirmed user={user_id} plan={plan_key}")

                # ── Lead balance top-up ──────────────────────────────────────
                if plan_key.startswith("leads_"):
                    try:
                        credits = int(plan_key.split("_")[1])
                        import database as _db
                        _db.add_lead_balance(user_id, credits)
                        logger.info(f"[PAYPAL] Lead balance +{credits} ₪ user={user_id}")
                    except Exception as _e:
                        logger.error(f"[PAYPAL] Lead topup error: {_e}")

                # ── Agent listing package ────────────────────────────────────
                elif plan_key.startswith("agent_pkg_"):
                    pkg_key = plan_key[len("agent_pkg_"):]
                    from pricing import get_agent_package
                    pkg = get_agent_package(pkg_key)
                    if pkg:
                        import database as _db
                        _db.add_listing_credits(user_id, pkg["count"],
                                                duration_days=pkg.get("duration_days", 30))
                        logger.info(f"[PAYPAL] Agent credits +{pkg['count']} user={user_id}")
                        _notify_agent_credits(user_id, pkg)
                    else:
                        logger.error(f"[PAYPAL] Unknown agent pkg={pkg_key!r}")

                # ── Mover weekly subscription ────────────────────────────────
                elif plan_key.startswith("mover_pkg_"):
                    pkg_key = plan_key[len("mover_pkg_"):]
                    from pricing import get_mover_package
                    pkg = get_mover_package(pkg_key)
                    if pkg:
                        from datetime import datetime, timedelta
                        expiry = (datetime.utcnow() + timedelta(weeks=1)).isoformat()
                        import database as _db
                        _db.set_service_subscription(str(user_id), pkg_key, expiry)
                        logger.info(f"[PAYPAL] Mover sub activated user={user_id} until={expiry}")
                        _notify_mover_subscription(user_id, pkg, expiry)
                    else:
                        logger.error(f"[PAYPAL] Unknown mover pkg={pkg_key!r}")

                # ── Service subscription / promo ─────────────────────────────
                elif plan_key.startswith("svc_"):
                    # custom_id format: svc_{svc_type}_{package_key}
                    parts = plan_key[len("svc_"):].split("_", 1)
                    if len(parts) == 2:
                        svc_type, pkg_key = parts
                        from pricing import get_service_package
                        pkg = get_service_package(pkg_key)
                        if pkg:
                            from datetime import datetime, timedelta
                            expiry = (datetime.utcnow() + timedelta(days=pkg.get("duration_days", 30))).isoformat()
                            import database as _db
                            if pkg_key == "promo":
                                # TOP promotion: update promo_expiry on the user's services
                                _db.activate_service_promo(user_id, expiry)
                                logger.info(f"[PAYPAL] Service promo activated user={user_id} until={expiry}")
                            else:
                                # Regular subscription (profi, partner, etc.)
                                _db.set_service_subscription(str(user_id), f"{svc_type}_{pkg_key}", expiry)
                                logger.info(f"[PAYPAL] Service sub activated svc={svc_type} pkg={pkg_key} user={user_id} until={expiry}")
                                asyncio.run_coroutine_threadsafe(
                                    _notify_service_subscription(user_id, svc_type, expiry),
                                    asyncio.get_event_loop()
                                )
                        else:
                            logger.error(f"[PAYPAL] Unknown service pkg={pkg_key!r}")

                # ── Alert subscription (39.90₪/month) ───────────────────────
                elif plan_key == "alerts":
                    import database as _db
                    _db.set_alert_expiry(user_id, days=30)
                    expiry = _db.get_alert_expiry(user_id)
                    logger.info(f"[PAYPAL] Alert sub activated user={user_id} until={expiry}")
                    asyncio.run_coroutine_threadsafe(
                        _notify_alert_activated(user_id, expiry),
                        asyncio.get_event_loop()
                    )

                # ── Bot subscription (week / two_weeks / month) ──────────────
                else:
                    from subscription import activate_subscription
                    expiry = activate_subscription(user_id, plan_key)
                    if expiry:
                        logger.info(f"[PAYPAL] Subscription activated user={user_id} plan={plan_key} until={expiry}")
                        _payment_notify_user(user_id, plan_key, expiry)
                    else:
                        logger.error(f"[PAYPAL] activate_subscription returned None user={user_id} plan={plan_key}")
            else:
                logger.info("[PAYPAL] Webhook ignored (not our document or payment not confirmed)")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            logger.error(f"[PAYPAL] Webhook handler exception: {e}")
            self.send_response(200)
            self.end_headers()

    def _handle_send_message(self):
        # Optional internal API key check
        if INTERNAL_API_KEY:
            auth = self.headers.get("X-Internal-Key", "")
            if not hmac.compare_digest(auth, INTERNAL_API_KEY):
                return self._send_json({"error": "Unauthorized"}, 401)

        body = self._read_body()
        chat_id = body.get("chat_id")
        text = body.get("text", "")
        parse_mode = body.get("parse_mode", "HTML")

        if not chat_id or not text:
            return self._send_json({"error": "chat_id and text are required"}, 400)

        if _bot_app is None or _bot_loop is None:
            return self._send_json({"error": "Bot not ready"}, 503)

        try:
            future = asyncio.run_coroutine_threadsafe(
                _bot_app.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode=parse_mode,
                ),
                _bot_loop,
            )
            future.result(timeout=10)
            return self._send_json({"ok": True})
        except Exception as e:
            logger.error(f"send-message failed for chat_id={chat_id}: {e}")
            return self._send_json({"error": str(e)}, 500)

    def do_PATCH(self):
        path = urlparse(self.path).path
        if path.startswith("/api/admin/"):
            content_len = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_len) if content_len else b"{}"
            try: body = json_module.loads(raw)
            except Exception: body = {}
            return self._handle_admin_api("PATCH", path, body)
        if path.startswith("/api/crm"):
            return self._handle_crm_api("PATCH", path)
        if path.startswith("/backoffice/api/"):
            if not _bo_check_session(self.headers):
                return self._send_json({"error":"Unauthorized"},401)
            return self._handle_bo_api("PATCH", path)
        self._send_json({"error":"Not found"},404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/admin/"):
            qs_params = parse_qs(parsed.query)
            return self._handle_admin_api("DELETE", path, {}, qs_params)
        if path.startswith("/api/crm"):
            return self._handle_crm_api("DELETE", path)
        if path.startswith("/backoffice/api/"):
            if not _bo_check_session(self.headers):
                return self._send_json({"error":"Unauthorized"},401)
            return self._handle_bo_api("DELETE", path)
        # Mini App API DELETE (e.g. DELETE /api/miniapp/alerts/<id>)
        if path.startswith("/api/miniapp/"):
            try:
                from mini_app_api import route as miniapp_route
                from urllib.parse import parse_qs as _pqs
                params  = _pqs(parsed.query)
                headers = dict(self.headers)
                result, status = miniapp_route("DELETE", path, params, {}, headers)
                body = json_module.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
            except Exception as e:
                body   = json_module.dumps({"error": str(e)}).encode("utf-8")
                status = 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_json({"error":"Not found"},404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type, X-Telegram-Init-Data")
        self.end_headers()

def start_web_server():
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    logger.info(f"Web server on port {port}")
    server.serve_forever()


def _email_scheduler_loop():
    """Background thread: every Sunday at 10:00 IL time send weekly reports."""
    import time
    from datetime import datetime, timezone, timedelta
    IL_TZ = timezone(timedelta(hours=3))  # Israel Standard Time (UTC+3)
    sent_this_week = None
    while True:
        now = datetime.now(IL_TZ)
        week_key = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
        # Sunday=6 in Python weekday(), 10:00–10:59
        if now.weekday() == 6 and now.hour == 10 and sent_this_week != week_key:
            try:
                from email_reporter import send_all_weekly_reports
                ok, total = send_all_weekly_reports()
                logger.info(f"Email scheduler: {ok}/{total} reports sent")
                sent_this_week = week_key
            except Exception as e:
                logger.error(f"Email scheduler error: {e}")
        time.sleep(60)   # check every minute


def _start_email_scheduler():
    t = threading.Thread(target=_email_scheduler_loop, daemon=True, name="email-scheduler")
    t.start()
    logger.info("Email scheduler started (runs every Sunday 10:00 IL)")

def _resilient_web_server():
    """Web server wrapper with auto-restart on crash. Non-daemon — keeps process alive."""
    while True:
        try:
            start_web_server()
        except Exception as _ws_err:
            logger.error(f"Web server crashed, restarting in 3s: {_ws_err}")
            import time as _time
            _time.sleep(3)

# NON-daemon thread: web server keeps the process alive even if Telegram bot fails
web_thread = threading.Thread(target=_resilient_web_server, daemon=False, name="web-server")
web_thread.start()

# Start news refresh loop (fetches RSS every 60 min)
try:
    from news_fetcher import start_news_refresh_loop, fetch_all_news, CACHE_FILE
    import os as _os
    # Delete stale cache so first fetch runs immediately with new sources
    if _os.path.exists(CACHE_FILE):
        _os.remove(CACHE_FILE)
        logger.info("News cache cleared — will refetch on first request")
    start_news_refresh_loop()
except Exception as _ne:
    logger.warning(f"News fetcher not started: {_ne}")

def start_telegram_parser():
    try:
        from telegram_parser import run_parser
        asyncio.run(run_parser())
    except Exception as e:
        logger.error(f"Telegram parser error: {e}")

parser_thread = threading.Thread(target=start_telegram_parser, daemon=True)
parser_thread.start()

# Start analytics cache warmup loop (pre-computes analytics in background)
analytics_warmup_thread = threading.Thread(
    target=_analytics_warmup_loop, daemon=True, name="analytics-warmup"
)
analytics_warmup_thread.start()
logger.info("Analytics warmup thread started")

if __name__ == "__main__":
    try:
        main()
    except Exception as _main_err:
        logger.critical(f"Bot main() crashed: {_main_err}", exc_info=True)
        # Web server is non-daemon — it keeps running so Railway health checks pass
        # and the backoffice stays accessible for debugging
        import time as _time
        logger.info("Web server still running. Sleeping to keep process alive...")
        while True:
            _time.sleep(60)
