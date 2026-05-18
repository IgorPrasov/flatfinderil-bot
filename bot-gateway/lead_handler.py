"""
Client lead system — packing and cleaning marketplace.

User flows (triggered by bot after "I rented/bought"):
  request_packing  → rooms → city → phone → save → notify providers
  request_cleaning → type → rooms → ptype → city → options → date → status → phone → save → notify

Provider flows (standalone callbacks):
  leads_list_{type}  → show available leads with buy buttons
  buy_lead_{id}      → spend balance → reveal client phone
  balance_topup      → top-up PayPlus links
"""
import logging
from datetime import datetime, timezone

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

import database as db
from i18n import get_lang
from pricing import CLEANING_LEAD_PRICE_ILS, PACKING_LEAD_PRICE_ILS, LEAD_BALANCE_PACKAGES

MAX_BUYERS_PER_LEAD = 3  # max companies that can purchase the same lead

logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
(
    PACK_ROOMS, PACK_CITY, PACK_PHONE,
    CLEAN_TYPE, CLEAN_ROOMS, CLEAN_PTYPE, CLEAN_CITY,
    CLEAN_OPTIONS, CLEAN_DATE, CLEAN_STATUS, CLEAN_PHONE,
) = range(200, 211)

_LEAD_KEY = "_lead_pending"

_CITIES = [
    "Тель-Авив", "Иерусалим", "Хайфа", "Ришон-ле-Цион",
    "Петах-Тиква", "Ашдод", "Нетания", "Беэр-Шева",
    "Холон", "Рамат-Ган", "Реховот", "Бат-Ям",
    "Кфар-Саба", "Герцлия", "Нес-Циона", "Модиин",
    "Хадера", "Акко", "Нагария", "Эйлат",
]

# ── Localization helpers ──────────────────────────────────────────────────────

def _L(d: dict, lang: str) -> str:
    return d.get(lang) or d.get("ru") or d.get("en") or ""


def _lang(context) -> str:
    return context.user_data.get("lang", "ru")


def _pending(context) -> dict:
    return context.user_data.setdefault(_LEAD_KEY, {})


# ── Label maps ────────────────────────────────────────────────────────────────

CLEAN_TYPE_LABELS = {
    "after_reno": {"ru": "🧹 После ремонта / строительства", "en": "🧹 Post-renovation", "he": "🧹 אחרי שיפוץ"},
    "pre_move":   {"ru": "📦 Перед въездом / После выезда",   "en": "📦 Pre-move-in / Post-move-out", "he": "📦 לפני/אחרי עברה"},
    "general":    {"ru": "✨ Генеральная уборка",               "en": "✨ General deep clean", "he": "✨ ניקיון כללי"},
    "windows":    {"ru": "🪟 Только мытье окон",               "en": "🪟 Windows only", "he": "🪟 חלונות בלבד"},
}

CLEAN_OPT_LABELS = {
    "windows":    {"ru": "Мойка окон в пол / триплекс", "en": "Floor-to-ceiling windows", "he": "ניקוי חלונות גדולים"},
    "furniture":  {"ru": "Химчистка мебели / матрасов",  "en": "Furniture / mattress cleaning", "he": "ניקוי ריפוד"},
    "appliances": {"ru": "Техника (холодильник, духовка)", "en": "Appliances (fridge, oven)", "he": "מכשירים (מקרר, תנור)"},
    "balcony":    {"ru": "Балкон / двор / техзона",      "en": "Balcony / yard", "he": "מרפסת / חצר"},
}

PTYPE_LABELS = {
    "apartment": {"ru": "🏢 Квартира",    "en": "🏢 Apartment",    "he": "🏢 דירה"},
    "penthouse": {"ru": "🏰 Пентхаус",    "en": "🏰 Penthouse",    "he": "🏰 פנטהאוס"},
    "house":     {"ru": "🏡 Частный дом", "en": "🏡 Private house", "he": "🏡 בית פרטי"},
}

DATE_LABELS = {
    "asap":  {"ru": "⚡ Как можно скорее",  "en": "⚡ ASAP",           "he": "⚡ בהקדם האפשרי"},
    "week":  {"ru": "📅 В течение недели",   "en": "📅 Within a week",  "he": "📅 תוך שבוע"},
    "later": {"ru": "🗓️ Позже (уточним)",    "en": "🗓️ Later (TBD)",    "he": "🗓️ מאוחר יותר"},
}

STATUS_LABELS = {
    "empty":     {"ru": "🪑 Пустая",      "en": "🪑 Empty",     "he": "🪑 ריקה"},
    "furnished": {"ru": "🛋️ С мебелью",   "en": "🛋️ Furnished",  "he": "🛋️ מרוהטת"},
}


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _rooms_kb(context) -> InlineKeyboardMarkup:
    lang = _lang(context)
    back = _L({"ru": "⬅ Отмена", "en": "⬅ Cancel", "he": "⬅ ביטול"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(r, callback_data=f"leadrooms_{r}") for r in ["1", "2", "3", "4", "5+"]],
        [InlineKeyboardButton(back, callback_data="lead_cancel")],
    ])


def _city_kb(context) -> InlineKeyboardMarkup:
    lang = _lang(context)
    back = _L({"ru": "⬅ Назад", "en": "⬅ Back", "he": "⬅ חזרה"}, lang)
    rows = []
    for i in range(0, len(_CITIES), 2):
        row = [InlineKeyboardButton(_CITIES[i], callback_data=f"leadcity_{_CITIES[i]}")]
        if i + 1 < len(_CITIES):
            row.append(InlineKeyboardButton(_CITIES[i + 1], callback_data=f"leadcity_{_CITIES[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(back, callback_data="lead_back")])
    return InlineKeyboardMarkup(rows)


def _clean_type_kb(context) -> InlineKeyboardMarkup:
    lang = _lang(context)
    back = _L({"ru": "⬅ Отмена", "en": "⬅ Cancel", "he": "⬅ ביטול"}, lang)
    rows = [
        [InlineKeyboardButton(_L(lbl, lang), callback_data=f"cleantype_{k}")]
        for k, lbl in CLEAN_TYPE_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(back, callback_data="lead_cancel")])
    return InlineKeyboardMarkup(rows)


def _ptype_kb(context) -> InlineKeyboardMarkup:
    lang = _lang(context)
    back = _L({"ru": "⬅ Назад", "en": "⬅ Back", "he": "⬅ חזרה"}, lang)
    rows = [
        [InlineKeyboardButton(_L(lbl, lang), callback_data=f"cleanptype_{k}")]
        for k, lbl in PTYPE_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(back, callback_data="lead_back")])
    return InlineKeyboardMarkup(rows)


def _options_kb(context, selected: set) -> InlineKeyboardMarkup:
    lang = _lang(context)
    done = _L({"ru": "✅ Готово — следующий шаг", "en": "✅ Done — next step", "he": "✅ המשך"}, lang)
    rows = []
    for key, lbl in CLEAN_OPT_LABELS.items():
        mark = "☑️" if key in selected else "◻️"
        rows.append([InlineKeyboardButton(f"{mark} {_L(lbl, lang)}", callback_data=f"cleanopt_{key}")])
    rows.append([InlineKeyboardButton(done, callback_data="cleanopt_done")])
    return InlineKeyboardMarkup(rows)


def _date_kb(context) -> InlineKeyboardMarkup:
    lang = _lang(context)
    back = _L({"ru": "⬅ Назад", "en": "⬅ Back", "he": "⬅ חזרה"}, lang)
    rows = [
        [InlineKeyboardButton(_L(lbl, lang), callback_data=f"cleandate_{k}")]
        for k, lbl in DATE_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(back, callback_data="lead_back")])
    return InlineKeyboardMarkup(rows)


def _status_kb(context) -> InlineKeyboardMarkup:
    lang = _lang(context)
    back = _L({"ru": "⬅ Назад", "en": "⬅ Back", "he": "⬅ חזרה"}, lang)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_L(STATUS_LABELS["empty"], lang), callback_data="cleanstatus_empty"),
            InlineKeyboardButton(_L(STATUS_LABELS["furnished"], lang), callback_data="cleanstatus_furnished"),
        ],
        [InlineKeyboardButton(back, callback_data="lead_back")],
    ])


def _phone_request_kb(lang: str) -> ReplyKeyboardMarkup:
    share  = {"ru": "📱 Поделиться номером телефона", "en": "📱 Share my phone number", "he": "📱 שתף מספר טלפון"}.get(lang, "📱 Share phone")
    cancel = {"ru": "❌ Отменить заявку", "en": "❌ Cancel request", "he": "❌ בטל בקשה"}.get(lang, "❌ Cancel")
    return ReplyKeyboardMarkup(
        [[KeyboardButton(share, request_contact=True)], [KeyboardButton(cancel)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ── Summary text builders ─────────────────────────────────────────────────────

def _clean_summary(p: dict, lang: str) -> str:
    type_lbl = _L(CLEAN_TYPE_LABELS.get(p.get("clean_type", ""), {}), lang)
    rooms = p.get("rooms", "—")
    ptype_lbl = _L(PTYPE_LABELS.get(p.get("ptype", "apartment"), {}), lang)
    city = p.get("city", "—")
    opts = p.get("options", [])
    opts_str = ", ".join(_L(CLEAN_OPT_LABELS.get(o, {}), lang) for o in opts) if opts else _L({"ru": "нет", "en": "none", "he": "ללא"}, lang)
    date_lbl = _L(DATE_LABELS.get(p.get("date", ""), {}), lang)
    status_lbl = _L(STATUS_LABELS.get(p.get("status", ""), {}), lang)
    return {
        "ru": (
            f"📋 <b>Ваша заявка:</b>\n\n"
            f"🧹 {type_lbl}\n"
            f"🏠 {ptype_lbl}, {rooms} комн.\n"
            f"📍 {city}\n"
            f"✨ Доп. опции: {opts_str}\n"
            f"📅 Когда: {date_lbl}\n"
            f"🪑 Квартира: {status_lbl}"
        ),
        "en": (
            f"📋 <b>Your request:</b>\n\n"
            f"🧹 {type_lbl}\n"
            f"🏠 {ptype_lbl}, {rooms} rooms\n"
            f"📍 {city}\n"
            f"✨ Extras: {opts_str}\n"
            f"📅 When: {date_lbl}\n"
            f"🪑 Apartment: {status_lbl}"
        ),
        "he": (
            f"📋 <b>הבקשה שלך:</b>\n\n"
            f"🧹 {type_lbl}\n"
            f"🏠 {ptype_lbl}, {rooms} חדרים\n"
            f"📍 {city}\n"
            f"✨ תוספות: {opts_str}\n"
            f"📅 מתי: {date_lbl}\n"
            f"🪑 דירה: {status_lbl}"
        ),
    }.get(lang, f"Cleaning: {type_lbl}, {city}, {rooms} rooms")


def _pack_summary(p: dict, lang: str) -> str:
    rooms = p.get("rooms", "—")
    city = p.get("city", "—")
    return {
        "ru": f"📦 <b>Заявка на упаковку:</b>\n\n🏠 Комнат: {rooms}\n📍 Город: {city}",
        "en": f"📦 <b>Packing request:</b>\n\n🏠 Rooms: {rooms}\n📍 City: {city}",
        "he": f"📦 <b>בקשה לאריזה:</b>\n\n🏠 חדרים: {rooms}\n📍 עיר: {city}",
    }.get(lang, f"Packing: {rooms} rooms, {city}")


# ── Provider notification ─────────────────────────────────────────────────────

async def _notify_providers(bot, svc_type: str, lead: dict):
    """Push new-lead notification to all matching registered providers."""
    providers = db.get_services(svc_type=svc_type)
    price = CLEANING_LEAD_PRICE_ILS if svc_type == "cleaning" else PACKING_LEAD_PRICE_ILS
    lead_id = lead["id"]
    city = lead.get("city", "")
    rooms = lead.get("rooms", "")

    if svc_type == "cleaning":
        type_lbl = _L(CLEAN_TYPE_LABELS.get(lead.get("clean_type", ""), {}), "ru")
        ptype_lbl = _L(PTYPE_LABELS.get(lead.get("ptype", "apartment"), {}), "ru")
        opts = lead.get("options", [])
        opts_str = ", ".join(_L(CLEAN_OPT_LABELS.get(o, {}), "ru") for o in opts)
        status_lbl = _L(STATUS_LABELS.get(lead.get("status", ""), {}), "ru")
        date_lbl = _L(DATE_LABELS.get(lead.get("date", ""), {}), "ru")
        body = (
            f"📋 <b>Новая заявка! Клининг</b>\n\n"
            f"📍 {city} | {rooms} комн. | {ptype_lbl}\n"
            f"🧹 {type_lbl}\n"
            + (f"✨ Доп. опции: {opts_str}\n" if opts_str else "")
            + f"🪑 {status_lbl} | 📅 {date_lbl}"
        )
    else:
        body = f"📦 <b>Новая заявка! Упаковка и коробки</b>\n\n📍 {city} | {rooms} комн."

    btn_label = f"📞 Взять контакт — {price} ₪"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_label, callback_data=f"buy_lead_{lead_id}")]])

    for svc in providers:
        provider_id = svc.get("user_id")
        if not provider_id:
            continue
        svc_city = svc.get("city", "")
        svc_region = svc.get("region", "all")
        if city and svc_city and svc_city != city and svc_region != "all":
            continue
        try:
            await bot.send_message(chat_id=int(provider_id), text=body, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not notify provider {provider_id}: {e}")
        # Email fallback
        try:
            provider_email = db.get_service_email(int(provider_id))
            if provider_email:
                import email_reporter
                email_reporter.send_service_order_email(
                    to_email=provider_email,
                    service_type=svc_type,
                    customer_username=lead.get("username", ""),
                    customer_tg_id=lead.get("user_id", 0),
                )
        except Exception:
            pass


# ── Packing wizard ────────────────────────────────────────────────────────────

async def start_packing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    lang = _lang(context)
    context.user_data[_LEAD_KEY] = {"type": "packing"}

    msg = {
        "ru": "📦 <b>Заявка на упаковку и коробки</b>\n\n<b>Шаг 1/3 — Сколько комнат?</b>",
        "en": "📦 <b>Packing & boxes request</b>\n\n<b>Step 1/3 — How many rooms?</b>",
        "he": "📦 <b>בקשה לאריזה וקופסאות</b>\n\n<b>שלב 1/3 — כמה חדרים?</b>",
    }.get(lang, "📦 Packing request — Step 1/3: rooms?")

    if query:
        await query.edit_message_text(msg, reply_markup=_rooms_kb(context), parse_mode="HTML")
    else:
        await update.effective_message.reply_text(msg, reply_markup=_rooms_kb(context), parse_mode="HTML")
    return PACK_ROOMS


async def pack_set_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    rooms = query.data[len("leadrooms_"):]
    _pending(context)["rooms"] = rooms

    msg = {
        "ru": f"✅ {rooms} комнат\n\n<b>Шаг 2/3 — Ваш город?</b>",
        "en": f"✅ {rooms} rooms\n\n<b>Step 2/3 — Your city?</b>",
        "he": f"✅ {rooms} חדרים\n\n<b>שלב 2/3 — העיר שלך?</b>",
    }.get(lang, f"✅ {rooms}\n\nStep 2/3 — City?")
    await query.edit_message_text(msg, reply_markup=_city_kb(context), parse_mode="HTML")
    return PACK_CITY


async def pack_set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    city = query.data[len("leadcity_"):]
    p = _pending(context)
    p["city"] = city

    summary = _pack_summary(p, lang)
    confirm_note = {
        "ru": "\n\n📱 <b>Шаг 3/3 — Отправить заявку</b>\n\nВсё верно? Поставщики упаковки получат уведомление и свяжутся с вами в WhatsApp в течение 15–30 минут.",
        "en": "\n\n📱 <b>Step 3/3 — Submit</b>\n\nAll correct? Packing suppliers will contact you via WhatsApp within 15–30 minutes.",
        "he": "\n\n📱 <b>שלב 3/3 — שליחה</b>\n\nהכל נכון? ספקי האריזה ייצרו איתך קשר בוואטסאפ תוך 15–30 דקות.",
    }.get(lang, "\n\n📱 Step 3/3 — Share phone to submit.")

    await query.edit_message_text(summary + confirm_note, parse_mode="HTML")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=_L({"ru": "👇 Нажмите кнопку, чтобы поделиться номером:", "en": "👇 Tap to share your phone:", "he": "👇 לחץ לשתף מספר:"}, lang),
        reply_markup=_phone_request_kb(lang),
    )
    return PACK_PHONE


async def pack_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        return PACK_PHONE
    lang = _lang(context)
    user = update.effective_user
    p = _pending(context)
    p.update({
        "phone": contact.phone_number,
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
    })

    lead_id = db.save_client_lead(p)
    context.user_data.pop(_LEAD_KEY, None)

    await update.message.reply_text(
        _L({
            "ru": "✅ <b>Заявка принята!</b>\n\nПоставщики упаковки в вашем городе уже видят вашу заявку и свяжутся с вами в WhatsApp в течение 15–30 минут. Оставайтесь на связи!",
            "en": "✅ <b>Request received!</b>\n\nPacking suppliers in your city have been notified and will contact you via WhatsApp within 15–30 minutes.",
            "he": "✅ <b>הבקשה התקבלה!</b>\n\nספקי האריזה בעירך קיבלו הודעה וייצרו איתך קשר בוואטסאפ תוך 15–30 דקות.",
        }, lang),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )

    try:
        lead = db.get_lead_by_id(lead_id)
        if lead:
            await _notify_providers(context.bot, "packing", lead)
    except Exception as exc:
        logger.warning(f"Provider notify failed: {exc}")

    return ConversationHandler.END


# ── Cleaning wizard ───────────────────────────────────────────────────────────

async def start_cleaning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    lang = _lang(context)
    context.user_data[_LEAD_KEY] = {"type": "cleaning", "options": []}

    msg = {
        "ru": "🧹 <b>Заявка на клининг</b>\n\n<b>Шаг 1/6 — Тип уборки</b>\n\nЧто именно нужно сделать?",
        "en": "🧹 <b>Cleaning request</b>\n\n<b>Step 1/6 — Cleaning type</b>\n\nWhat kind of cleaning do you need?",
        "he": "🧹 <b>בקשה לניקיון</b>\n\n<b>שלב 1/6 — סוג ניקיון</b>\n\nאיזה סוג ניקיון?",
    }.get(lang, "🧹 Cleaning — Step 1/6: type?")

    if query:
        await query.edit_message_text(msg, reply_markup=_clean_type_kb(context), parse_mode="HTML")
    else:
        await update.effective_message.reply_text(msg, reply_markup=_clean_type_kb(context), parse_mode="HTML")
    return CLEAN_TYPE


async def clean_set_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    ct = query.data[len("cleantype_"):]
    _pending(context)["clean_type"] = ct
    type_lbl = _L(CLEAN_TYPE_LABELS.get(ct, {}), lang)

    msg = {
        "ru": f"✅ {type_lbl}\n\n<b>Шаг 2/6 — Сколько комнат?</b>",
        "en": f"✅ {type_lbl}\n\n<b>Step 2/6 — How many rooms?</b>",
        "he": f"✅ {type_lbl}\n\n<b>שלב 2/6 — כמה חדרים?</b>",
    }.get(lang, f"✅\n\nStep 2/6 — Rooms?")
    await query.edit_message_text(msg, reply_markup=_rooms_kb(context), parse_mode="HTML")
    return CLEAN_ROOMS


async def clean_set_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    rooms = query.data[len("leadrooms_"):]
    _pending(context)["rooms"] = rooms

    msg = {
        "ru": f"✅ {rooms} комнат\n\n<b>Шаг 2/6 — Тип недвижимости</b>",
        "en": f"✅ {rooms} rooms\n\n<b>Step 2/6 — Property type</b>",
        "he": f"✅ {rooms} חדרים\n\n<b>שלב 2/6 — סוג נכס</b>",
    }.get(lang, f"✅ {rooms}\n\nStep 2/6 — Property type")
    await query.edit_message_text(msg, reply_markup=_ptype_kb(context), parse_mode="HTML")
    return CLEAN_PTYPE


async def clean_set_ptype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    ptype = query.data[len("cleanptype_"):]
    _pending(context)["ptype"] = ptype
    ptype_lbl = _L(PTYPE_LABELS.get(ptype, {}), lang)

    msg = {
        "ru": f"✅ {ptype_lbl}\n\n<b>Шаг 3/6 — Город</b>",
        "en": f"✅ {ptype_lbl}\n\n<b>Step 3/6 — City</b>",
        "he": f"✅ {ptype_lbl}\n\n<b>שלב 3/6 — עיר</b>",
    }.get(lang, f"✅\n\nStep 3/6 — City")
    await query.edit_message_text(msg, reply_markup=_city_kb(context), parse_mode="HTML")
    return CLEAN_CITY


async def clean_set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    city = query.data[len("leadcity_"):]
    _pending(context)["city"] = city

    selected = set(_pending(context).get("options", []))
    msg = {
        "ru": f"✅ {city}\n\n<b>Шаг 4/6 — Дополнительные опции</b>\n\nВыберите всё нужное (можно несколько):",
        "en": f"✅ {city}\n\n<b>Step 4/6 — Extra options</b>\n\nSelect all that apply:",
        "he": f"✅ {city}\n\n<b>שלב 4/6 — אפשרויות נוספות</b>\n\nסמן הכל שרלוונטי:",
    }.get(lang, f"✅ {city}\n\nStep 4/6 — Extras")
    await query.edit_message_text(msg, reply_markup=_options_kb(context, selected), parse_mode="HTML")
    return CLEAN_OPTIONS


async def clean_toggle_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    opt = query.data[len("cleanopt_"):]
    p = _pending(context)
    opts = list(p.get("options", []))
    if opt in opts:
        opts.remove(opt)
    else:
        opts.append(opt)
    p["options"] = opts

    city = p.get("city", "")
    selected = set(opts)
    msg = {
        "ru": f"✅ {city}\n\n<b>Шаг 4/6 — Дополнительные опции</b>\n\nВыберите всё нужное (можно несколько):",
        "en": f"✅ {city}\n\n<b>Step 4/6 — Extra options</b>\n\nSelect all that apply:",
        "he": f"✅ {city}\n\n<b>שלב 4/6 — אפשרויות נוספות</b>\n\nסמן הכל שרלוונטי:",
    }.get(lang, f"✅ {city}\n\nStep 4/6 — Extras")
    await query.edit_message_text(msg, reply_markup=_options_kb(context, selected), parse_mode="HTML")
    return CLEAN_OPTIONS


async def clean_options_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    msg = {
        "ru": "<b>Шаг 5/6 — Когда нужна уборка?</b>",
        "en": "<b>Step 5/6 — When do you need cleaning?</b>",
        "he": "<b>שלב 5/6 — מתי צריך ניקיון?</b>",
    }.get(lang, "Step 5/6 — When?")
    await query.edit_message_text(msg, reply_markup=_date_kb(context), parse_mode="HTML")
    return CLEAN_DATE


async def clean_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    date_key = query.data[len("cleandate_"):]
    _pending(context)["date"] = date_key
    date_lbl = _L(DATE_LABELS.get(date_key, {}), lang)

    msg = {
        "ru": f"✅ {date_lbl}\n\n<b>Шаг 5/6 — Квартира пустая или с мебелью?</b>",
        "en": f"✅ {date_lbl}\n\n<b>Step 5/6 — Apartment status?</b>",
        "he": f"✅ {date_lbl}\n\n<b>שלב 5/6 — הדירה ריקה או מרוהטת?</b>",
    }.get(lang, f"✅\n\nStep 5/6 — Status?")
    await query.edit_message_text(msg, reply_markup=_status_kb(context), parse_mode="HTML")
    return CLEAN_STATUS


async def clean_set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    status = query.data[len("cleanstatus_"):]
    p = _pending(context)
    p["status"] = status

    summary = _clean_summary(p, lang)
    confirm_note = {
        "ru": "\n\n📱 <b>Шаг 6/6 — Отправить заявку</b>\n\nВсё верно? Поделитесь номером — клининговые компании свяжутся с вами в течение 15–30 минут.",
        "en": "\n\n📱 <b>Step 6/6 — Submit</b>\n\nAll correct? Share your phone — cleaning companies will contact you within 15–30 minutes.",
        "he": "\n\n📱 <b>שלב 6/6 — שליחה</b>\n\nהכל נכון? שתף מספר — חברות ניקיון ייצרו קשר תוך 15–30 דקות.",
    }.get(lang, "\n\n📱 Step 6/6 — Share phone.")

    await query.edit_message_text(summary + confirm_note, parse_mode="HTML")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=_L({"ru": "👇 Нажмите кнопку:", "en": "👇 Tap the button:", "he": "👇 לחץ על הכפתור:"}, lang),
        reply_markup=_phone_request_kb(lang),
    )
    return CLEAN_PHONE


async def clean_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        return CLEAN_PHONE
    lang = _lang(context)
    user = update.effective_user
    p = _pending(context)
    p.update({
        "phone": contact.phone_number,
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
    })

    lead_id = db.save_client_lead(p)
    context.user_data.pop(_LEAD_KEY, None)

    await update.message.reply_text(
        _L({
            "ru": "✅ <b>Заявка принята!</b>\n\nПроверенные клининговые компании в вашем городе уже видят вашу заявку. Ожидайте звонка в течение 15–30 минут!",
            "en": "✅ <b>Request received!</b>\n\nVerified cleaning companies in your city have been notified. Expect a call within 15–30 minutes!",
            "he": "✅ <b>הבקשה התקבלה!</b>\n\nחברות ניקיון מאומתות בעירך קיבלו הודעה. צפה לשיחה תוך 15–30 דקות!",
        }, lang),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )

    try:
        lead = db.get_lead_by_id(lead_id)
        if lead:
            await _notify_providers(context.bot, "cleaning", lead)
    except Exception as exc:
        logger.warning(f"Provider notify failed: {exc}")

    return ConversationHandler.END


# ── Cancel / fallback ─────────────────────────────────────────────────────────

async def lead_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data.pop(_LEAD_KEY, None)
    lang = _lang(context)
    msg = _L({"ru": "❌ Заявка отменена.", "en": "❌ Request cancelled.", "he": "❌ הבקשה בוטלה."}, lang)
    if query:
        try:
            await query.edit_message_text(msg)
        except Exception:
            pass
    return ConversationHandler.END


# ── Provider: buy lead ────────────────────────────────────────────────────────

async def handle_buy_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provider presses 'Take contact — X ₪'."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    provider_id = update.effective_user.id
    lead_id = query.data[len("buy_lead_"):]

    lead = db.get_lead_by_id(lead_id)
    if not lead:
        await query.answer(
            _L({"ru": "Заявка не найдена или истекла (72 ч).", "en": "Lead not found or expired (72h).", "he": "הליד לא נמצא או פג תוקפו."}, lang),
            show_alert=True,
        )
        return

    svc_type = lead.get("type", "cleaning")
    price = CLEANING_LEAD_PRICE_ILS if svc_type == "cleaning" else PACKING_LEAD_PRICE_ILS

    # Already purchased?
    if db.has_unlocked_lead(provider_id, lead_id):
        phone = lead.get("phone", "")
        uname = lead.get("username", "")
        fname = lead.get("first_name", "")
        contact_str = f"📞 {phone}" + (f"\n📱 @{uname}" if uname else "") + (f"\n👤 {fname}" if fname else "")
        await query.edit_message_text(
            _L({
                "ru": f"✅ <b>Вы уже купили этот контакт</b>\n\n{contact_str}",
                "en": f"✅ <b>You already purchased this lead</b>\n\n{contact_str}",
                "he": f"✅ <b>כבר רכשת ליד זה</b>\n\n{contact_str}",
            }, lang),
            parse_mode="HTML",
        )
        return

    # Lead sold out?
    buyers_count = len(lead.get("buyers", []))
    if buyers_count >= MAX_BUYERS_PER_LEAD:
        await query.answer(
            _L({
                "ru": f"❌ Лид уже выкуплен {MAX_BUYERS_PER_LEAD} компаниями — мест нет.",
                "en": f"❌ This lead was already purchased by {MAX_BUYERS_PER_LEAD} companies.",
                "he": f"❌ הליד נרכש כבר על ידי {MAX_BUYERS_PER_LEAD} חברות.",
            }, lang),
            show_alert=True,
        )
        return

    balance = db.get_lead_balance(provider_id)
    if balance < price:
        await _show_top_up_prompt(query, context, balance, price, lang)
        return

    ok, new_balance = db.spend_lead_balance(provider_id, price)
    if not ok:
        await query.answer(_L({"ru": "Недостаточно средств.", "en": "Insufficient balance.", "he": "יתרה לא מספיקה."}, lang), show_alert=True)
        return

    db.record_lead_purchase(lead_id, provider_id)
    db.mark_lead_unlocked(provider_id, lead_id)

    phone = lead.get("phone", "")
    uname = lead.get("username", "")
    fname = lead.get("first_name", "")
    contact_str = f"📞 {phone}" + (f"\n📱 @{uname}" if uname else "") + (f"\n👤 {fname}" if fname else "")

    text = _L({
        "ru": (
            f"✅ <b>Контакт открыт!</b>\n\n"
            f"{contact_str}\n\n"
            f"💳 Списано: {price} ₪ | Остаток: {new_balance} ₪\n\n"
            f"Позвоните клиенту — он ждёт предложения!"
        ),
        "en": (
            f"✅ <b>Contact unlocked!</b>\n\n"
            f"{contact_str}\n\n"
            f"💳 Charged: {price} ₪ | Balance: {new_balance} ₪\n\n"
            f"Call the client — they're waiting for your offer!"
        ),
        "he": (
            f"✅ <b>הפרטים נחשפו!</b>\n\n"
            f"{contact_str}\n\n"
            f"💳 חויב: {price} ₪ | יתרה: {new_balance} ₪\n\n"
            f"התקשר ללקוח — הוא מחכה!"
        ),
    }, lang)

    topup_label = _L({"ru": "💳 Пополнить баланс", "en": "💳 Top up balance", "he": "💳 הוסף יתרה"}, lang)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(topup_label, callback_data="balance_topup")]])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

    # Ping the client
    user_tg_id = lead.get("user_id")
    if user_tg_id:
        try:
            await context.bot.send_message(
                chat_id=int(user_tg_id),
                text=_L({
                    "ru": "📞 <b>Компания уже видит вашу заявку и скоро позвонит!</b>\n\nОставайтесь на связи.",
                    "en": "📞 <b>A company has accepted your request and will call soon!</b>\n\nStay tuned.",
                    "he": "📞 <b>חברה קיבלה את הבקשה שלך ותתקשר בקרוב!</b>\n\nהישאר בקשר.",
                }, lang),
                parse_mode="HTML",
            )
        except Exception:
            pass


async def _show_top_up_prompt(query, context, balance: int, price: int, lang: str):
    """Show Morning top-up options when balance is insufficient."""
    import paypal_payment as mp
    provider_id = query.from_user.id
    needed = price - balance
    header = _L({
        "ru": (
            f"💳 <b>Недостаточно средств</b>\n\n"
            f"Текущий баланс: {balance} ₪\n"
            f"Нужно: {price} ₪ (не хватает {needed} ₪)\n\n"
            f"Пополните баланс:"
        ),
        "en": (
            f"💳 <b>Insufficient balance</b>\n\n"
            f"Current: {balance} ₪\n"
            f"Required: {price} ₪ (missing {needed} ₪)\n\n"
            f"Top up your balance:"
        ),
        "he": (
            f"💳 <b>יתרה לא מספיקה</b>\n\n"
            f"נוכחי: {balance} ₪\n"
            f"נדרש: {price} ₪ (חסר {needed} ₪)\n\n"
            f"הוסף יתרה:"
        ),
    }, lang)

    rows = []
    for pkg in LEAD_BALANCE_PACKAGES:
        amount = pkg["amount_ils"]
        credits = amount + pkg.get("bonus_ils", 0)
        result = mp.create_lead_topup_link(amount, credits, provider_id, lang)
        if result and result.get("url"):
            label = _L(pkg["label"], lang)
            rows.append([InlineKeyboardButton(label, url=result["url"])])

    if not rows:
        rows = [[InlineKeyboardButton(
            _L({"ru": "📞 Связаться с поддержкой", "en": "📞 Contact support", "he": "📞 צור קשר"}, lang),
            callback_data="contact_admin",
        )]]

    await query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_balance_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Standalone balance top-up entry (from provider cabinet)."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    provider_id = update.effective_user.id
    balance = db.get_lead_balance(provider_id)
    await _show_top_up_prompt(query, context, balance, 0, lang)


# ── Provider: view available leads ───────────────────────────────────────────

async def show_provider_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available leads list for a cleaning/packing provider."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    provider_id = update.effective_user.id
    svc_type = query.data[len("leads_list_"):]  # "cleaning" or "packing"

    my_svcs = [s for s in db.get_services(svc_type=svc_type) if str(s.get("user_id", "")) == str(provider_id)]
    my_city = my_svcs[0].get("city", "") if my_svcs else ""
    leads = db.get_available_leads(svc_type, my_city)
    balance = db.get_lead_balance(provider_id)
    price = CLEANING_LEAD_PRICE_ILS if svc_type == "cleaning" else PACKING_LEAD_PRICE_ILS

    type_lbl = _L({"ru": "Клининг", "en": "Cleaning", "he": "ניקיון"} if svc_type == "cleaning"
                  else {"ru": "Упаковка", "en": "Packing", "he": "אריזה"}, lang)

    topup_btn = InlineKeyboardButton(
        _L({"ru": "💳 Пополнить баланс", "en": "💳 Top up", "he": "💳 הוסף יתרה"}, lang),
        callback_data="balance_topup",
    )
    menu_btn = InlineKeyboardButton(
        _L({"ru": "🏠 Меню", "en": "🏠 Menu", "he": "🏠 תפריט"}, lang),
        callback_data="back_to_menu",
    )

    if not leads:
        text = _L({
            "ru": f"📋 <b>Заявки: {type_lbl}</b>\n\nАктивных заявок пока нет.\nКак только клиент оставит заявку — вы получите push-уведомление.\n\n💳 Ваш баланс: {balance} ₪",
            "en": f"📋 <b>Leads: {type_lbl}</b>\n\nNo active leads yet.\nYou'll get a push when a client submits a request.\n\n💳 Balance: {balance} ₪",
            "he": f"📋 <b>לידים: {type_lbl}</b>\n\nאין לידים פעילים עדיין.\nתקבל הודעה כשלקוח ישלח בקשה.\n\n💳 יתרה: {balance} ₪",
        }, lang)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[topup_btn], [menu_btn]]), parse_mode="HTML")
        return

    lines = [_L({
        "ru": f"📋 <b>Активные заявки — {type_lbl}</b>\n\n💳 Баланс: {balance} ₪ | Цена лида: {price} ₪\n",
        "en": f"📋 <b>Active leads — {type_lbl}</b>\n\n💳 Balance: {balance} ₪ | Lead price: {price} ₪\n",
        "he": f"📋 <b>לידים פעילים — {type_lbl}</b>\n\n💳 יתרה: {balance} ₪ | מחיר ליד: {price} ₪\n",
    }, lang)]

    rows = []
    for i, lead in enumerate(leads[:10]):
        lid = lead["id"]
        rooms = lead.get("rooms", "—")
        city = lead.get("city", "—")
        already = db.has_unlocked_lead(provider_id, lid)
        buyers_count = len(lead.get("buyers", []))
        slots_left = MAX_BUYERS_PER_LEAD - buyers_count
        sold_out = slots_left <= 0 and not already

        slots_tag = (
            "✅" if already else
            f"🔴 {'Мест нет' if lang == 'ru' else 'Full' if lang == 'en' else 'מלא'}" if sold_out else
            f"🟡 {'Место: 1' if slots_left == 1 else f'Мест: {slots_left}'}" if lang == "ru" and slots_left <= 2 else
            f"🟡 {slots_left} {'spot' if slots_left == 1 else 'spots'} left" if lang == "en" and slots_left <= 2 else
            f"🟡 נותרו {slots_left}" if lang == "he" and slots_left <= 2 else
            f"{i+1}."
        )

        if svc_type == "cleaning":
            ct_lbl = _L(CLEAN_TYPE_LABELS.get(lead.get("clean_type", ""), {}), lang)
            opts = lead.get("options", [])
            opts_str = (", ".join(_L(CLEAN_OPT_LABELS.get(o, {}), lang) for o in opts)) if opts else ""
            status_lbl = _L(STATUS_LABELS.get(lead.get("status", ""), {}), lang)
            line = f"{slots_tag} 📍 {city} | {rooms} комн. | {ct_lbl}"
            if opts_str:
                line += f"\n   ✨ {opts_str}"
            if status_lbl:
                line += f" | {status_lbl}"
        else:
            line = f"{slots_tag} 📍 {city} | {rooms} комн."

        lines.append(line)
        if not already and not sold_out:
            btn_lbl = (f"Взять лид #{i+1} — {price} ₪" if lang == "ru"
                       else f"Buy lead #{i+1} — {price} ₪" if lang == "en"
                       else f"קנה ליד #{i+1} — {price} ₪")
            rows.append([InlineKeyboardButton(btn_lbl, callback_data=f"buy_lead_{lid}")])

    rows.extend([[topup_btn], [menu_btn]])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


# ── Back-navigation helpers (fix: don't read query.data for step value) ──────

async def _back_to_clean_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    msg = {"ru": "🧹 <b>Шаг 1/6 — Тип уборки</b>\n\nЧто именно нужно сделать?",
           "en": "🧹 <b>Step 1/6 — Cleaning type</b>\n\nWhat kind of cleaning?",
           "he": "🧹 <b>שלב 1/6 — סוג ניקיון</b>\n\nמה צריך לנקות?"}.get(lang, "Step 1/6 — Type?")
    await query.edit_message_text(msg, reply_markup=_clean_type_kb(context), parse_mode="HTML")
    return CLEAN_TYPE


async def _back_to_clean_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    ct = _pending(context).get("clean_type", "")
    ct_lbl = _L(CLEAN_TYPE_LABELS.get(ct, {}), lang)
    msg = (f"✅ {ct_lbl}\n\n" if ct_lbl else "") + {"ru": "<b>Шаг 2/6 — Сколько комнат?</b>",
           "en": "<b>Step 2/6 — How many rooms?</b>",
           "he": "<b>שלב 2/6 — כמה חדרים?</b>"}.get(lang, "Step 2/6 — Rooms?")
    await query.edit_message_text(msg, reply_markup=_rooms_kb(context), parse_mode="HTML")
    return CLEAN_ROOMS


async def _back_to_clean_ptype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    rooms = _pending(context).get("rooms", "")
    msg = (f"✅ {rooms} комн.\n\n" if rooms else "") + {"ru": "<b>Шаг 2/6 — Тип недвижимости</b>",
           "en": "<b>Step 2/6 — Property type</b>",
           "he": "<b>שלב 2/6 — סוג נכס</b>"}.get(lang, "Step 2/6 — Property type")
    await query.edit_message_text(msg, reply_markup=_ptype_kb(context), parse_mode="HTML")
    return CLEAN_PTYPE


async def _back_to_clean_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    city = _pending(context).get("city", "")
    selected = set(_pending(context).get("options", []))
    msg = (f"✅ {city}\n\n" if city else "") + {"ru": "<b>Шаг 4/6 — Дополнительные опции</b>\n\nВыберите всё нужное:",
           "en": "<b>Step 4/6 — Extra options</b>\n\nSelect all that apply:",
           "he": "<b>שלב 4/6 — אפשרויות נוספות</b>\n\nסמן הכל שרלוונטי:"}.get(lang, "Step 4/6 — Extras")
    await query.edit_message_text(msg, reply_markup=_options_kb(context, selected), parse_mode="HTML")
    return CLEAN_OPTIONS


async def _back_to_clean_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    msg = {"ru": "<b>Шаг 5/6 — Когда нужна уборка?</b>",
           "en": "<b>Step 5/6 — When do you need cleaning?</b>",
           "he": "<b>שלב 5/6 — מתי צריך ניקיון?</b>"}.get(lang, "Step 5/6 — When?")
    await query.edit_message_text(msg, reply_markup=_date_kb(context), parse_mode="HTML")
    return CLEAN_DATE


# ── Phone-step cancel (user sends text instead of sharing contact) ────────────

async def _phone_cancel_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _lang(context)
    context.user_data.pop(_LEAD_KEY, None)
    await update.message.reply_text(
        _L({"ru": "❌ Заявка отменена.", "en": "❌ Request cancelled.", "he": "❌ הבקשה בוטלה."}, lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── Provider: my purchased leads ──────────────────────────────────────────────

async def show_my_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    provider_id = update.effective_user.id

    leads = db.get_provider_unlocked_leads(provider_id)
    menu_btn = InlineKeyboardButton(_L({"ru": "🏠 Меню", "en": "🏠 Menu", "he": "🏠 תפריט"}, lang), callback_data="back_to_menu")

    if not leads:
        text = _L({"ru": "📋 <b>Мои лиды</b>\n\nВы пока не купили ни одного лида.",
                   "en": "📋 <b>My leads</b>\n\nYou haven't purchased any leads yet.",
                   "he": "📋 <b>הלידים שלי</b>\n\nעדיין לא רכשת לידים."}, lang)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[menu_btn]]), parse_mode="HTML")
        return

    lines = [_L({"ru": f"📋 <b>Мои купленные лиды</b> ({len(leads)})\n",
                 "en": f"📋 <b>My purchased leads</b> ({len(leads)})\n",
                 "he": f"📋 <b>הלידים שרכשתי</b> ({len(leads)})\n"}, lang)]

    for i, lead in enumerate(leads[:15]):
        svc_type = lead.get("type", "")
        city = lead.get("city", "—")
        rooms = lead.get("rooms", "—")
        phone = lead.get("phone", "")
        uname = lead.get("username", "")
        date = lead.get("created_at", "")[:10]
        type_icon = "🧹" if svc_type == "cleaning" else "📦"
        contact = f"📞 {phone}" + (f" @{uname}" if uname else "")
        lines.append(f"{i+1}. {type_icon} {city} | {rooms} комн. | {date}\n   {contact}")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[menu_btn]]),
        parse_mode="HTML",
    )


# ── ConversationHandler factory ───────────────────────────────────────────────

def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_packing, pattern="^request_packing$"),
            CallbackQueryHandler(start_cleaning, pattern="^request_cleaning$"),
        ],
        states={
            PACK_ROOMS: [
                CallbackQueryHandler(pack_set_rooms, pattern="^leadrooms_"),
                CallbackQueryHandler(lead_cancel, pattern="^lead_cancel$"),
            ],
            PACK_CITY: [
                CallbackQueryHandler(pack_set_city, pattern="^leadcity_"),
                CallbackQueryHandler(start_packing, pattern="^lead_back$"),
            ],
            PACK_PHONE: [
                MessageHandler(filters.CONTACT, pack_receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _phone_cancel_text),
            ],
            CLEAN_TYPE: [
                CallbackQueryHandler(clean_set_type, pattern="^cleantype_"),
                CallbackQueryHandler(lead_cancel, pattern="^lead_cancel$"),
            ],
            CLEAN_ROOMS: [
                CallbackQueryHandler(clean_set_rooms, pattern="^leadrooms_"),
                CallbackQueryHandler(start_cleaning, pattern="^lead_back$"),
            ],
            CLEAN_PTYPE: [
                CallbackQueryHandler(clean_set_ptype, pattern="^cleanptype_"),
                CallbackQueryHandler(_back_to_clean_type, pattern="^lead_back$"),
            ],
            CLEAN_CITY: [
                CallbackQueryHandler(clean_set_city, pattern="^leadcity_"),
                CallbackQueryHandler(_back_to_clean_rooms, pattern="^lead_back$"),
            ],
            CLEAN_OPTIONS: [
                CallbackQueryHandler(clean_options_done, pattern="^cleanopt_done$"),
                CallbackQueryHandler(clean_toggle_option, pattern="^cleanopt_"),
                CallbackQueryHandler(_back_to_clean_ptype, pattern="^lead_back$"),
            ],
            CLEAN_DATE: [
                CallbackQueryHandler(clean_set_date, pattern="^cleandate_"),
                CallbackQueryHandler(_back_to_clean_options, pattern="^lead_back$"),
            ],
            CLEAN_STATUS: [
                CallbackQueryHandler(clean_set_status, pattern="^cleanstatus_"),
                CallbackQueryHandler(_back_to_clean_date, pattern="^lead_back$"),
            ],
            CLEAN_PHONE: [
                MessageHandler(filters.CONTACT, clean_receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _phone_cancel_text),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lead_cancel, pattern="^lead_cancel$"),
            CallbackQueryHandler(lead_cancel, pattern="^back_to_menu$"),
        ],
        per_message=False,
        allow_reentry=True,
    )
