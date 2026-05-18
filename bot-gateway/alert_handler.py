"""
Alert notifications handler for FlatFinderIL.

Flow:
  Main menu → 🔔 Уведомления → alerts_menu
    • Not subscribed → paywall (PayPlus link)
    • Subscribed     → list alerts + Add / Delete

Add alert wizard (5 steps):
  deal_type → city → rooms → price_max → confirm → save
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, ContextTypes,
)

import database as db
from i18n import get_lang
from keyboards import (
    alerts_menu_keyboard, alert_deal_type_keyboard,
    alert_city_keyboard, alert_rooms_keyboard,
    alert_price_keyboard, alert_confirm_keyboard,
)

logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
(
    ALERTS_MENU,
    AL_DEAL, AL_CITY, AL_ROOMS, AL_PRICE, AL_CONFIRM,
) = range(6)

_ALERT_KEY = "pending_alert"   # key in context.user_data


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lang(context):
    return context.user_data.get("lang", "ru")


def _alerts_text(lang: str, is_active: bool, expiry: str | None, alerts: list) -> str:
    if not is_active:
        return {
            "ru": (
                "🔔 <b>Уведомления о новых объявлениях</b>\n\n"
                "Бот будет присылать свежие объявления по вашим фильтрам сразу, как только они появятся.\n\n"
                "💳 <b>Стоимость: 39.90 ₪/месяц</b>\n\n"
                "Нажмите кнопку ниже, чтобы подписаться."
            ),
            "en": (
                "🔔 <b>New listing alerts</b>\n\n"
                "The bot will send you fresh listings matching your filters as soon as they appear.\n\n"
                "💳 <b>Price: ₪39.90/month</b>\n\n"
                "Tap the button below to subscribe."
            ),
            "he": (
                "🔔 <b>התראות על מודעות חדשות</b>\n\n"
                "הבוט ישלח לך מודעות חדשות לפי הפילטרים שלך ברגע שהן יופיעו.\n\n"
                "💳 <b>מחיר: 39.90 ₪/חודש</b>\n\n"
                "לחץ על הכפתור למטה כדי להירשם."
            ),
        }.get(lang, "🔔 <b>Alerts</b>\n\nSubscribe to receive new listing notifications.")
    # Subscribed
    try:
        from datetime import datetime
        expiry_str = datetime.fromisoformat(expiry).strftime("%d.%m.%Y") if expiry else "?"
    except Exception:
        expiry_str = (expiry or "?")[:10]
    count = len(alerts)
    header = {
        "ru": f"🔔 <b>Уведомления активны</b> до <b>{expiry_str}</b>\n\nФильтров настроено: {count}/5",
        "en": f"🔔 <b>Alerts active</b> until <b>{expiry_str}</b>\n\nFilters set: {count}/5",
        "he": f"🔔 <b>התראות פעילות</b> עד <b>{expiry_str}</b>\n\nפילטרים מוגדרים: {count}/5",
    }.get(lang, f"🔔 Alerts active until {expiry_str}")

    if not alerts:
        tip = {
            "ru": "\n\nНажмите ➕ чтобы настроить первый фильтр.",
            "en": "\n\nTap ➕ to set up your first filter.",
            "he": "\n\nלחץ ➕ להגדרת הפילטר הראשון.",
        }.get(lang, "\n\nTap ➕ to add a filter.")
        return header + tip
    return header


def _pending(context) -> dict:
    return context.user_data.setdefault(_ALERT_KEY, {})


def _alert_summary(filters: dict, lang: str) -> str:
    deal = filters.get("deal_type", "")
    deal_str = {"rent": "🏠 Аренда / Rent", "buy": "🏦 Покупка / Buy"}.get(deal, "🔎 Любой / Any")
    city = filters.get("city", "") or {"ru": "Любой город", "en": "Any city", "he": "כל עיר"}.get(lang, "Any city")
    rooms_min = filters.get("rooms_min", "")
    rooms_max = filters.get("rooms_max", "")
    rooms_str = (f"{rooms_min}+" if rooms_min and not rooms_max else
                 (f"до {rooms_max}" if rooms_max and not rooms_min else
                  (f"{rooms_min}–{rooms_max}" if rooms_min and rooms_max else "–")))
    price_max = filters.get("price_max", "")
    price_str = f"до {price_max:,} ₪".replace(",", " ") if price_max and str(price_max).isdigit() else "–"
    return (
        f"📋 <b>Новый фильтр / New filter</b>\n\n"
        f"• Тип сделки: {deal_str}\n"
        f"• Город: {city}\n"
        f"• Комнаты: {rooms_str}\n"
        f"• Макс. цена: {price_str}"
    )


# ── Entry: show alerts menu ───────────────────────────────────────────────────

async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called from handle_menu on callback_data == 'alerts_menu'."""
    query = update.callback_query
    if query:
        await query.answer()
    lang = _lang(context)
    user_id = update.effective_user.id

    is_active = db.is_alert_active(user_id)
    expiry    = db.get_alert_expiry(user_id)
    alerts    = db.get_user_alerts(user_id)

    text = _alerts_text(lang, is_active, expiry, alerts)
    kb   = alerts_menu_keyboard(context, alerts, is_active)

    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def handle_alert_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create Morning payment link for alert subscription."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    user_id = update.effective_user.id

    import morning_payment as mp
    result = mp.create_payment_link("alerts", user_id, lang)

    if result and result.get("url"):
        label = {"ru": "💳 Оплатить 39.90 ₪/мес", "en": "💳 Pay ₪39.90/mo", "he": "💳 שלם 39.90 ₪/חודש"}.get(lang, "💳 Pay")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(label, url=result["url"])],
            [InlineKeyboardButton({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}.get(lang, "◀"), callback_data="alerts_menu")],
        ])
        msg = {
            "ru": "💳 Нажмите кнопку для оплаты. После подтверждения подписка активируется автоматически.",
            "en": "💳 Tap the button to pay. Subscription activates automatically after payment.",
            "he": "💳 לחץ על הכפתור לתשלום. המנוי יופעל אוטומטית לאחר האישור.",
        }.get(lang, "💳 Tap to pay.")
        await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
    else:
        err = {"ru": "⚠️ Не удалось создать ссылку для оплаты. Попробуйте позже.", "en": "⚠️ Could not create payment link. Try later.", "he": "⚠️ לא ניתן ליצור קישור תשלום."}.get(lang, "⚠️ Error")
        await query.answer(err, show_alert=True)


# ── Add alert wizard ──────────────────────────────────────────────────────────

async def start_add_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin the add-alert wizard."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    user_id = update.effective_user.id
    if not db.is_alert_active(user_id):
        await show_alerts_menu(update, context)
        return ConversationHandler.END

    context.user_data[_ALERT_KEY] = {}   # reset pending filter

    msg = {
        "ru": "🔔 <b>Шаг 1/4 — Тип сделки</b>\n\nВыберите, какие объявления вас интересуют:",
        "en": "🔔 <b>Step 1/4 — Deal type</b>\n\nWhat kind of listings are you looking for?",
        "he": "🔔 <b>שלב 1/4 — סוג עסקה</b>\n\nאיזה סוג מודעות מעניין אותך?",
    }.get(lang, "🔔 Step 1/4 — Deal type")
    await query.edit_message_text(msg, reply_markup=alert_deal_type_keyboard(context), parse_mode="HTML")
    return AL_DEAL


async def al_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    choice = query.data  # aldeal_rent | aldeal_buy | aldeal_any
    deal = {"aldeal_rent": "rent", "aldeal_buy": "buy"}.get(choice, "")
    _pending(context)["deal_type"] = deal

    msg = {
        "ru": "🔔 <b>Шаг 2/4 — Город</b>\n\nВ каком городе искать?",
        "en": "🔔 <b>Step 2/4 — City</b>\n\nWhich city?",
        "he": "🔔 <b>שלב 2/4 — עיר</b>\n\nבאיזו עיר לחפש?",
    }.get(lang, "🔔 Step 2/4 — City")
    await query.edit_message_text(msg, reply_markup=alert_city_keyboard(context), parse_mode="HTML")
    return AL_CITY


async def al_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    raw = query.data[len("alcity_"):]   # e.g. "Тель-Авив" or "any"
    _pending(context)["city"] = "" if raw == "any" else raw

    msg = {
        "ru": "🔔 <b>Шаг 3/4 — Комнаты</b>\n\nМинимальное количество комнат (или пропустить):",
        "en": "🔔 <b>Step 3/4 — Rooms</b>\n\nMinimum rooms (or skip):",
        "he": "🔔 <b>שלב 3/4 — חדרים</b>\n\nמספר חדרים מינימלי (או דלג):",
    }.get(lang, "🔔 Step 3/4 — Rooms")
    await query.edit_message_text(msg, reply_markup=alert_rooms_keyboard(context), parse_mode="HTML")
    return AL_ROOMS


async def al_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    raw = query.data[len("alrooms_"):]   # e.g. "2" or "any"
    p = _pending(context)
    if raw != "any":
        p["rooms_min"] = raw
    else:
        p.pop("rooms_min", None)

    deal = p.get("deal_type", "rent")
    msg = {
        "ru": "🔔 <b>Шаг 4/4 — Максимальная цена</b>\n\nВыберите верхний порог цены (или пропустить):",
        "en": "🔔 <b>Step 4/4 — Max price</b>\n\nChoose maximum price (or skip):",
        "he": "🔔 <b>שלב 4/4 — מחיר מקסימלי</b>\n\nבחר מחיר מקסימלי (או דלג):",
    }.get(lang, "🔔 Step 4/4 — Max price")
    await query.edit_message_text(msg, reply_markup=alert_price_keyboard(context, deal), parse_mode="HTML")
    return AL_PRICE


async def al_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    raw = query.data[len("alprice_"):]   # e.g. "5000" or "any"
    p = _pending(context)
    if raw != "any":
        p["price_max"] = raw
    else:
        p.pop("price_max", None)

    p["lang"] = lang
    summary = _alert_summary(p, lang)
    confirm_title = {
        "ru": "\n\n✅ <b>Всё верно?</b>",
        "en": "\n\n✅ <b>Looks good?</b>",
        "he": "\n\n✅ <b>הכל נכון?</b>",
    }.get(lang, "\n\n✅ Confirm?")
    await query.edit_message_text(summary + confirm_title, reply_markup=alert_confirm_keyboard(context), parse_mode="HTML")
    return AL_CONFIRM


async def al_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    user_id = update.effective_user.id

    filters = dict(_pending(context))
    filters["lang"] = lang
    context.user_data.pop(_ALERT_KEY, None)

    db.add_alert(user_id, filters)

    saved_msg = {
        "ru": "✅ <b>Фильтр сохранён!</b>\n\nБот пришлёт уведомление, как только появится подходящее объявление.",
        "en": "✅ <b>Filter saved!</b>\n\nThe bot will notify you as soon as a matching listing appears.",
        "he": "✅ <b>הפילטר נשמר!</b>\n\nהבוט יודיע לך ברגע שתופיע מודעה מתאימה.",
    }.get(lang, "✅ Filter saved!")

    alerts = db.get_user_alerts(user_id)
    expiry = db.get_alert_expiry(user_id)
    kb = alerts_menu_keyboard(context, alerts, True)
    await query.edit_message_text(
        saved_msg + "\n\n" + _alerts_text(lang, True, expiry, alerts),
        reply_markup=kb,
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ── Delete alert ──────────────────────────────────────────────────────────────

async def handle_alert_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a specific alert by ID."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    user_id = update.effective_user.id

    alert_id = query.data[len("alert_del_"):]
    db.delete_alert(user_id, alert_id)

    alerts = db.get_user_alerts(user_id)
    expiry = db.get_alert_expiry(user_id)
    text = _alerts_text(lang, True, expiry, alerts)
    kb   = alerts_menu_keyboard(context, alerts, True)

    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ── Cancel / back helpers ─────────────────────────────────────────────────────

async def _back_to_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(_ALERT_KEY, None)
    await show_alerts_menu(update, context)
    return ConversationHandler.END


async def _city_step_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to city step from rooms."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    msg = {
        "ru": "🔔 <b>Шаг 2/4 — Город</b>\n\nВ каком городе искать?",
        "en": "🔔 <b>Step 2/4 — City</b>\n\nWhich city?",
        "he": "🔔 <b>שלב 2/4 — עיר</b>\n\nבאיזו עיר לחפש?",
    }.get(lang, "🔔 Step 2/4 — City")
    await query.edit_message_text(msg, reply_markup=alert_city_keyboard(context), parse_mode="HTML")
    return AL_CITY


async def _rooms_step_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to rooms step from price."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    msg = {
        "ru": "🔔 <b>Шаг 3/4 — Комнаты</b>\n\nМинимальное количество комнат:",
        "en": "🔔 <b>Step 3/4 — Rooms</b>\n\nMinimum rooms:",
        "he": "🔔 <b>שלב 3/4 — חדרים</b>\n\nמספר חדרים מינימלי:",
    }.get(lang, "🔔 Step 3/4 — Rooms")
    await query.edit_message_text(msg, reply_markup=alert_rooms_keyboard(context), parse_mode="HTML")
    return AL_ROOMS


# ── ConversationHandler factory ───────────────────────────────────────────────

def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_alert, pattern="^alert_add$"),
        ],
        states={
            AL_DEAL: [
                CallbackQueryHandler(al_deal, pattern="^aldeal_"),
                CallbackQueryHandler(_back_to_alerts, pattern="^alerts_menu$"),
            ],
            AL_CITY: [
                CallbackQueryHandler(al_city, pattern="^alcity_"),
                CallbackQueryHandler(start_add_alert, pattern="^alert_add$"),
            ],
            AL_ROOMS: [
                CallbackQueryHandler(al_rooms, pattern="^alrooms_"),
                CallbackQueryHandler(_city_step_back, pattern="^alert_city_step$"),
            ],
            AL_PRICE: [
                CallbackQueryHandler(al_price, pattern="^alprice_"),
                CallbackQueryHandler(_rooms_step_back, pattern="^alert_rooms_step$"),
            ],
            AL_CONFIRM: [
                CallbackQueryHandler(al_save, pattern="^alert_save$"),
                CallbackQueryHandler(start_add_alert, pattern="^alert_add$"),
                CallbackQueryHandler(_back_to_alerts, pattern="^alerts_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_back_to_alerts, pattern="^alerts_menu$"),
            CallbackQueryHandler(_back_to_alerts, pattern="^back_to_menu$"),
        ],
        per_message=False,
        allow_reentry=True,
    )
