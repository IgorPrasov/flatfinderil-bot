from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from i18n import get_lang
import database as db
from datetime import datetime as _dt

# States

def _L(d, lang):
    """Безопасный выбор перевода: lang → en → ru → первый доступный."""
    if not isinstance(d, dict):
        return str(d)
    return d.get(lang) or d.get("en") or d.get("ru") or next(iter(d.values()), "")


(
    SVC_MENU, SVC_REGION, SVC_CITY, SVC_RESULTS,
    ADD_SVC_TYPE, ADD_SVC_REGION, ADD_SVC_CITY, ADD_SVC_PRICE, ADD_SVC_DESC, ADD_SVC_NAME, ADD_SVC_PHONE, ADD_SVC_EMAIL, ADD_SVC_CONFIRM,
    ADD_SVC_AWAIT_PAYMENT,
    SVC_REPAIR_TYPE,
    ADD_SVC_REPAIR_TYPE,
) = range(10, 26)

SERVICE_TYPES = {
    "moving":           {"ru": "🚚 Перевозки",          "en": "🚚 Moving",          "he": "🚚 הובלות",         "fr": "🚚 Déménagement"},
    "packing":          {"ru": "📦 Упаковка",           "en": "📦 Packing",         "he": "📦 אריזה",          "fr": "📦 Emballage"},
    "cleaning":         {"ru": "🧹 Клининг",            "en": "🧹 Cleaning",        "he": "🧹 ניקיון",         "fr": "🧹 Ménage"},
    "repair":           {"ru": "🔨 Ремонт",             "en": "🔨 Repairs",         "he": "🔨 שיפוצים",        "fr": "🔨 Rénovation"},
    "mortgage_broker":  {"ru": "💰 Кредитный брокер",  "en": "💰 Mortgage Broker", "he": "💰 יועץ משכנתאות", "fr": "💰 Courtier en prêt"},
}

# Sub-types for the "repair" category
REPAIR_SUBTYPES = {
    "repair_painting":  {"ru": "🎨 Покраска",    "en": "🎨 Painting",    "he": "🎨 צביעה",           "fr": "🎨 Peinture"},
    "repair_plumbing":  {"ru": "🔧 Сантехника",  "en": "🔧 Plumbing",    "he": "🔧 אינסטלציה",      "fr": "🔧 Plomberie"},
    "repair_electric":  {"ru": "⚡ Электрика",   "en": "⚡ Electrical",  "he": "⚡ חשמל",            "fr": "⚡ Électricité"},
    "repair_ac":        {"ru": "❄️ Кондиционер", "en": "❄️ AC / Heating","he": "❄️ מיזוג אוויר",    "fr": "❄️ Clim / Chauffage"},
}

# All service types including repair sub-types (for card formatting)
ALL_SERVICE_TYPES = {**SERVICE_TYPES, **REPAIR_SUBTYPES}

REGIONS = {
    "north":  {"ru": "🌿 Север",  "en": "🌿 North",  "he": "🌿 צפון", "fr": "🌿 Nord"},
    "center": {"ru": "🏙 Центр",  "en": "🏙 Center", "he": "🏙 מרכז", "fr": "🏙 Centre"},
    "south":  {"ru": "☀️ Юг",     "en": "☀️ South",  "he": "☀️ דרום", "fr": "☀️ Sud"},
}

# Cities per region
REGION_CITIES = {
    "north":  ["Хайфа","Кирьят-Ата","Кирьят-Бялик","Кирьят-Хаим","Кирьят-Ям","Кирьят-Моцкин","Акко","Нагария","Тиверия","Хадера","Кармиэль","Афула","Нацрат-Илит"],
    "center": ["Тель-Авив","Иерусалим","Нетания","Рамат-Ган","Гиватаим","Бней-Брак","Бат-Ям","Холон","Ор-Иегуда","Петах-Тиква","Ришон-ле-Цион","Реховот","Нес-Циона","Лод","Рамла","Модиин","Кфар-Саба","Раанана","Герцлия","Ход-ха-Шарон","Рош-аин","Рамат-ха-Шарон"],
    "south":  ["Ашдод","Ашкелон","Беэр-Шева","Эйлат","Нетивот","Сдерот"],
}

# Districts that belong to each region (for filtering)
REGION_DISTRICTS = {
    "north":  ["haifa"],
    "center": ["tel_aviv", "jerusalem", "sharon", "center"],
    "south":  ["south"],
}

# Reverse mapping: city name → region key  (built automatically from REGION_CITIES)
CITY_TO_REGION = {city: region for region, cities in REGION_CITIES.items() for city in cities}


def _t(ctx, ru, en, he):
    lang = get_lang(ctx)
    return _L({"ru": ru, "en": en, "he": he}, lang)


def _lbl(ctx, key, mapping):
    lang = get_lang(ctx)
    return _L(mapping.get(key, {}), lang)


def _back_kb(ctx):
    lang = get_lang(ctx)
    back = _L({"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי", "fr": "🏠 Menu principal"}, lang)
    return InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="back_to_menu")]])


def _services_menu_kb(ctx, provider_types: list = None):
    lang = get_lang(ctx)
    rows = []
    for key, names in SERVICE_TYPES.items():
        rows.append([InlineKeyboardButton(_L(names, lang), callback_data=f"svc_type_{key}")])
    add_label  = _L({"ru": "➕ Разместить услугу",  "en": "➕ Add service",   "he": "➕ הוסף שירות",  "fr": "➕ Ajouter service"}, lang)
    back_label = _L({"ru": "🏠 Главное меню",        "en": "🏠 Main menu",    "he": "🏠 תפריט ראשי", "fr": "🏠 Menu principal"}, lang)
    rows.append([InlineKeyboardButton(add_label, callback_data="svc_add")])
    # Show lead marketplace buttons for registered cleaning/packing providers
    if provider_types:
        for ptype in provider_types:
            if ptype in ("cleaning", "packing"):
                leads_label = _L({"ru": "📋 Заявки клиентов", "en": "📋 Client leads", "he": "📋 לידים מלקוחות"}, lang)
                my_leads_label = _L({"ru": "🗂 Мои купленные лиды", "en": "🗂 My purchased leads", "he": "🗂 הלידים שרכשתי"}, lang)
                rows.append([InlineKeyboardButton(leads_label, callback_data=f"leads_list_{ptype}")])
                rows.append([InlineKeyboardButton(my_leads_label, callback_data="my_leads")])
                break
    rows.append([InlineKeyboardButton(back_label, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def _region_kb(ctx, prefix):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(REGIONS[r], lang), callback_data=f"{prefix}_{r}")] for r in REGIONS]
    all_label = _L({"ru": "🌍 Вся страна", "en": "🌍 All country", "he": "🌍 כל הארץ", "fr": "🌍 Tout le pays"}, lang)
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    rows.append([InlineKeyboardButton(all_label, callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _add_type_kb(ctx):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(names, lang), callback_data=f"addsvc_type_{key}")]
            for key, names in SERVICE_TYPES.items()]
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    rows.append([InlineKeyboardButton(back_label, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def _add_region_kb(ctx):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(REGIONS[r], lang), callback_data=f"addsvc_region_{r}")] for r in REGIONS]
    all_label = _L({"ru": "🌍 Вся страна", "en": "🌍 All country", "he": "🌍 כל הארץ", "fr": "🌍 Tout le pays"}, lang)
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    rows.append([InlineKeyboardButton(all_label, callback_data="addsvc_region_all")])
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _city_kb(ctx, region, prefix):
    lang = get_lang(ctx)
    cities = REGION_CITIES.get(region, [])
    rows = []
    row = []
    for city in cities:
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_{city}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    all_label = _L({"ru": "🌍 Весь район", "en": "🌍 All region", "he": "🌍 כל האזור", "fr": "🌍 Toute la région"}, lang)
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    rows.append([InlineKeyboardButton(all_label, callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _all_cities_kb(ctx, prefix: str):
    """Flat keyboard with ALL cities across all regions + 'All Israel' + Back."""
    lang = get_lang(ctx)
    all_cities = (
        REGION_CITIES["north"]
        + REGION_CITIES["center"]
        + REGION_CITIES["south"]
    )
    rows = []
    row = []
    for city in all_cities:
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_{city}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    all_label  = _L({"ru": "🌍 Вся страна",  "en": "🌍 All Israel",  "he": "🌍 כל הארץ"}, lang)
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    rows.append([InlineKeyboardButton(all_label,  callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _repair_kb(ctx, prefix: str):
    """Sub-type keyboard for the repair category. prefix = 'svc_reptype_' or 'addrep_type_'."""
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(names, lang), callback_data=f"{prefix}{key}")]
            for key, names in REPAIR_SUBTYPES.items()]
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _back_step_kb(ctx):
    lang = get_lang(ctx)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    return InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="svc_back")]])


def _confirm_kb(ctx):
    lang = get_lang(ctx)
    pub = _L({"ru": "✅ Опубликовать", "en": "✅ Publish", "he": "✅ פרסם", "fr": "✅ Publier"}, lang)
    cancel = _L({"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול", "fr": "❌ Annuler"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(pub, callback_data="addsvc_confirm_yes")],
        [InlineKeyboardButton(cancel, callback_data="back_to_menu")],
    ])


def _format_service_card(s, lang):
    stype = ALL_SERVICE_TYPES.get(s.get("service_type", ""), {}).get(lang, s.get("service_type", ""))
    region_key = s.get("region", "")
    region = REGIONS.get(region_key, {}).get(lang, region_key) if region_key not in ("all", "") else {
        "ru": "Вся страна", "en": "All country", "he": "כל הארץ"
    , "fr": "Tout le pays"}.get(lang, "All")
    city = s.get("city", "")
    location = city if city else region
    price = s.get("price", 0)
    price_str = f"{price:,} ₪".replace(",", " ") if price else {"ru": "Договорная", "en": "Negotiable", "he": "לפי הסכמה", "fr": "Négociable"}.get(lang)
    desc = s.get("description", "")
    name = s.get("owner_name", "")
    phone = s.get("phone", "")
    contact = s.get("contact", "")
    lines = [
        f"<b>{stype}</b>",
        f"📍 {location}",
        f"💰 {price_str}",
    ]
    if desc:
        lines.append(f"\n{desc}")
    if name:
        lines.append(f"\n👤 {name}")
    if phone:
        lines.append(f"📞 {phone}")
    if contact:
        lines.append(f"✉️ {contact}")
    return "\n".join(lines)


def _has_active_svc_subscription(user_id: int) -> bool:
    """Return True if the user has an active service-provider subscription."""
    try:
        sub = db.get_service_subscription(str(user_id))
        if not sub:
            return False
        return sub.get("expiry", "") > _dt.utcnow().isoformat()
    except Exception:
        return False


def _paywall_type_kb(ctx):
    """Type-selection keyboard shown on the paywall screen."""
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(names, lang), callback_data=f"svcpay_type_{key}")]
            for key, names in SERVICE_TYPES.items()]
    later = _L({"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}, lang)
    rows.append([InlineKeyboardButton(later, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def _paywall_action_kb(ctx, svc_type: str, paypal_url: str = None):
    """Keyboard with pay-link + 'I paid' + 'Later' buttons."""
    lang = get_lang(ctx)
    rows = []
    if paypal_url:
        pay_label = _L({"ru": "💳 Оплатить", "en": "💳 Pay now", "he": "💳 שלם עכשיו"}, lang)
        rows.append([InlineKeyboardButton(pay_label, url=paypal_url)])
    check_label = _L({"ru": "✅ Я оплатил — продолжить", "en": "✅ I paid — continue", "he": "✅ שילמתי — המשך"}, lang)
    rows.append([InlineKeyboardButton(check_label, callback_data=f"svcpay_check_{svc_type}")])
    back_label = _L({"ru": "◀ Выбрать другой тип", "en": "◀ Change type", "he": "◀ שנה סוג"}, lang)
    rows.append([InlineKeyboardButton(back_label, callback_data="svcpay_back")])
    later_label = _L({"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}, lang)
    rows.append([InlineKeyboardButton(later_label, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


class ServiceHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start,                  pattern="^services$"),
                CallbackQueryHandler(self.start_mortgage_broker,  pattern="^find_mortgage_broker$"),
            ],
            states={
                SVC_MENU: [
                    CallbackQueryHandler(self.handle_type, pattern="^svc_type_"),
                    CallbackQueryHandler(self.start_add, pattern="^svc_add$"),
                ],
                SVC_REGION: [
                    CallbackQueryHandler(self.handle_region, pattern="^svc_region_"),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                SVC_CITY: [
                    CallbackQueryHandler(self.handle_city, pattern="^svc_city_"),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                SVC_RESULTS: [
                    CallbackQueryHandler(self.handle_prev,  pattern="^svc_prev$"),
                    CallbackQueryHandler(self.handle_next,  pattern="^svc_next$"),
                    CallbackQueryHandler(self.order_service, pattern="^svc_order_"),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^back_to_menu$"),
                ],
                ADD_SVC_TYPE: [
                    CallbackQueryHandler(self.add_handle_type, pattern="^addsvc_type_"),
                ],
                ADD_SVC_REGION: [
                    CallbackQueryHandler(self.add_handle_region, pattern="^addsvc_region_"),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                ADD_SVC_CITY: [
                    CallbackQueryHandler(self.add_handle_city, pattern="^addsvc_city_"),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                ADD_SVC_PRICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_handle_price),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                ADD_SVC_DESC: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_handle_desc),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                ADD_SVC_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_handle_name),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                ADD_SVC_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_handle_phone),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^svc_back$"),
                ],
                ADD_SVC_EMAIL: [
                    CallbackQueryHandler(self.add_handle_email_skip, pattern="^svc_email_skip$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_handle_email),
                ],
                ADD_SVC_CONFIRM: [
                    CallbackQueryHandler(self.add_confirm, pattern="^addsvc_confirm_yes$"),
                    CallbackQueryHandler(self.back_to_menu_cb, pattern="^back_to_menu$"),
                ],
                ADD_SVC_AWAIT_PAYMENT: [
                    CallbackQueryHandler(self.handle_svc_paywall_type,   pattern="^svcpay_type_"),
                    CallbackQueryHandler(self.handle_svc_pkg_profi,      pattern="^svcpay_pkg_profi_"),
                    CallbackQueryHandler(self.handle_svc_pkg_partner,    pattern="^svcpay_pkg_partner_"),
                    CallbackQueryHandler(self.handle_svc_partner_free,   pattern="^svcpay_partner_free_"),
                    CallbackQueryHandler(self.handle_svc_partner_promo,  pattern="^svcpay_partner_promo_"),
                    CallbackQueryHandler(self.handle_svc_check_payment,  pattern="^svcpay_check_"),
                    CallbackQueryHandler(self.start_add,                 pattern="^svcpay_back$"),
                    CallbackQueryHandler(self.back_to_menu_cb,           pattern="^back_to_menu$"),
                ],
                SVC_REPAIR_TYPE: [
                    CallbackQueryHandler(self.handle_repair_browse_type, pattern="^svc_reptype_"),
                    CallbackQueryHandler(self.back_to_menu_cb,           pattern="^svc_back$"),
                ],
                ADD_SVC_REPAIR_TYPE: [
                    CallbackQueryHandler(self.handle_repair_add_type, pattern="^addrep_type_"),
                    CallbackQueryHandler(self.back_to_menu_cb,         pattern="^svc_back$"),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.cancel),
            ],
            per_message=False, allow_reentry=True,
        )

    async def start_mortgage_broker(self, update, context):
        """Entry point from buy-search results — pre-selects mortgage_broker type."""
        query = update.callback_query
        await query.answer()
        lang = get_lang(context)

        # City might be pre-filled from the search filters
        city = (context.user_data.get("search_filters") or {}).get("city", "all")
        context.user_data["svc"] = {"type": "mortgage_broker", "city": city}

        # Search brokers (try city first, fallback to all)
        services = db.get_services(svc_type="mortgage_broker", city=city if city != "any" else None)
        if not services and city not in ("all", "any", None):
            services = db.get_services(svc_type="mortgage_broker")

        if services:
            context.user_data["svc_results"] = services
            context.user_data["svc_idx"] = 0
            header = _L({
                "ru": f"💰 <b>Кредитные брокеры</b>  —  найдено: {len(services)}",
                "en": f"💰 <b>Mortgage Brokers</b>  —  found: {len(services)}",
                "he": f"💰 <b>יועצי משכנתאות</b>  —  נמצאו: {len(services)}",
                "fr": f"💰 <b>Courtiers en prêt</b>  —  trouvés: {len(services)}",
            }, lang)
            await query.edit_message_text(header, parse_mode="HTML")
            await self._show_service(update, context, query=query)
            return SVC_RESULTS
        else:
            no_text = _L({
                "ru": (
                    "💰 <b>Кредитные брокеры</b>\n\n"
                    "😔 Пока нет зарегистрированных брокеров.\n\n"
                    "Вы ипотечный брокер? Зарегистрируйтесь — получайте клиентов прямо из бота!\n"
                    "👉 @flatfinderil_bot"
                ),
                "en": (
                    "💰 <b>Mortgage Brokers</b>\n\n"
                    "😔 No brokers registered yet.\n\n"
                    "Are you a mortgage broker? Register now and get leads directly from the bot!\n"
                    "👉 @flatfinderil_bot"
                ),
                "he": (
                    "💰 <b>יועצי משכנתאות</b>\n\n"
                    "😔 עדיין אין יועצים רשומים.\n\n"
                    "האם אתה יועץ משכנתאות? הירשם עכשיו וקבל לקוחות ישירות מהבוט!\n"
                    "👉 @flatfinderil_bot"
                ),
                "fr": (
                    "💰 <b>Courtiers en prêt immobilier</b>\n\n"
                    "😔 Aucun courtier enregistré pour l'instant.\n\n"
                    "Vous êtes courtier en crédit immobilier? Inscrivez-vous et recevez des leads!\n"
                    "👉 @flatfinderil_bot"
                ),
            }, lang)
            await query.edit_message_text(no_text, reply_markup=_back_kb(context), parse_mode="HTML")
            return ConversationHandler.END

    async def start(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["svc"] = {}
        text = _t(context,
            "🚚 <b>Услуги</b>\n\nВыберите категорию:",
            "🚚 <b>Services</b>\n\nSelect category:",
            "🚚 <b>שירותים</b>\n\nבחר קטגוריה:"
        )
        # Detect which service types this user has registered (to show lead marketplace buttons)
        user_id = update.effective_user.id
        my_svcs = db.get_services()
        provider_types = list({s["service_type"] for s in my_svcs if str(s.get("user_id", "")) == str(user_id)})
        lead_provider_types = [p for p in provider_types if p in ("cleaning", "packing")]
        if lead_provider_types:
            balance = db.get_lead_balance(user_id)
            balance_line = _L({"ru": f"\n💰 <b>Баланс лидов:</b> {balance}₪",
                                "en": f"\n💰 <b>Lead balance:</b> {balance}₪",
                                "he": f"\n💰 <b>יתרת לידים:</b> ₪{balance}"}, get_lang(context))
            text += balance_line
        await query.edit_message_text(text, reply_markup=_services_menu_kb(context, provider_types), parse_mode="HTML")
        return SVC_MENU

    async def handle_type(self, update, context):
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svc_type_", "")
        lang = get_lang(context)

        if svc_type == "repair":
            # Drill down into repair sub-types
            type_label = _L(SERVICE_TYPES["repair"], lang)
            text = f"🔨 <b>{type_label}</b>\n\n" + _t(
                context,
                "Выберите вид ремонтных работ:",
                "Select type of repair work:",
                "בחר סוג עבודות שיפוץ:"
            )
            await query.edit_message_text(text, reply_markup=_repair_kb(context, "svc_reptype_"), parse_mode="HTML")
            return SVC_REPAIR_TYPE

        context.user_data["svc"]["type"] = svc_type
        type_label = _L(SERVICE_TYPES[svc_type], lang)
        await query.edit_message_text(
            f"✅ <b>{type_label}</b>\n\n" + _t(context, "Выберите город:", "Select city:", "בחר עיר:"),
            reply_markup=_all_cities_kb(context, "svc_city"),
            parse_mode="HTML"
        )
        return SVC_CITY

    async def handle_repair_browse_type(self, update, context):
        """User picked a repair sub-type while browsing — proceed directly to city."""
        query = update.callback_query
        await query.answer()
        sub_type = query.data.replace("svc_reptype_", "")
        context.user_data["svc"]["type"] = sub_type
        lang = get_lang(context)
        type_label = _L(REPAIR_SUBTYPES.get(sub_type, {}), lang)
        await query.edit_message_text(
            f"✅ <b>{type_label}</b>\n\n" + _t(context, "Выберите город:", "Select city:", "בחר עיר:"),
            reply_markup=_all_cities_kb(context, "svc_city"),
            parse_mode="HTML"
        )
        return SVC_CITY

    async def handle_region(self, update, context):
        query = update.callback_query
        await query.answer()
        region = query.data.replace("svc_region_", "")
        context.user_data["svc"]["region"] = region
        lang = get_lang(context)
        region_label = REGIONS.get(region, {}).get(lang, region) if region != "all" else _L({
            "ru": "Вся страна", "en": "All country", "he": "כל הארץ"
        , "fr": "Tout le pays"}, lang)
        if region == "all":
            # Skip city selection, search all
            context.user_data["svc"]["city"] = "all"
            services = db.get_services(svc_type=context.user_data["svc"].get("type"), region="all")
            if not services:
                await query.edit_message_text(
                    _t(context,"😔 Объявления не найдены.\n\nБудьте первым — разместите услугу!",
                       "😔 No listings found.\n\nBe the first — add your service!",
                       "😔 לא נמצאו מודעות.\n\nהיה ראשון — הוסף שירות!"),
                    reply_markup=_back_kb(context), parse_mode="HTML"
                )
                return ConversationHandler.END
            context.user_data["svc_results"] = services
            context.user_data["svc_idx"] = 0
            await self._show_service(update, context, query=query)
            return SVC_RESULTS
        # Show city selection
        await query.edit_message_text(
            f"✅ {region_label}\n\n" + _t(context, "Выберите город:", "Select city:", "בחר עיר:"),
            reply_markup=_city_kb(context, region, "svc_city"),
            parse_mode="HTML"
        )
        return SVC_CITY

    async def handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        city = query.data.replace("svc_city_", "")
        context.user_data["svc"]["city"] = city
        svc_type = context.user_data["svc"].get("type")
        # Look up region from city (so providers scoped to that region are also returned)
        region = CITY_TO_REGION.get(city) if city != "all" else None
        services = db.get_services(svc_type=svc_type, region=region, city=city)
        if not services:
            await query.edit_message_text(
                _t(context,"😔 Объявления не найдены.\n\nБудьте первым — разместите услугу!",
                   "😔 No listings found.\n\nBe the first — add your service!",
                   "😔 לא נמצאו מודעות.\n\nהיה ראשון — הוסף שירות!"),
                reply_markup=_back_kb(context), parse_mode="HTML"
            )
            return ConversationHandler.END
        context.user_data["svc_results"] = services
        context.user_data["svc_idx"] = 0
        await self._show_service(update, context, query=query)
        return SVC_RESULTS

    async def _show_service(self, update, context, query=None):
        results = context.user_data.get("svc_results", [])
        idx = context.user_data.get("svc_idx", 0)
        lang = get_lang(context)
        if not results:
            return
        s = results[idx]
        text = f"📋 <i>{idx+1} / {len(results)}</i>\n\n" + _format_service_card(s, lang)

        nav_buttons = []
        if idx > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data="svc_prev"))
        if idx < len(results) - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data="svc_next"))

        order_label = _L({"ru": "✅ Заказать", "en": "✅ Order", "he": "✅ להזמין", "fr": "✅ Commander"}, lang)
        back_label  = _L({"ru": "🏠 Меню",    "en": "🏠 Menu",  "he": "🏠 תפריט", "fr": "🏠 Menu"}, lang)
        sid = s.get("id", "")
        rows = []
        if nav_buttons:
            rows.append(nav_buttons)
        rows.append([InlineKeyboardButton(order_label, callback_data=f"svc_order_{sid}")])
        rows.append([InlineKeyboardButton(back_label,  callback_data="back_to_menu")])
        kb = InlineKeyboardMarkup(rows)

        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

    async def handle_prev(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["svc_idx"] = max(0, context.user_data.get("svc_idx", 0) - 1)
        await self._show_service(update, context, query=query)
        return SVC_RESULTS

    async def handle_next(self, update, context):
        query = update.callback_query
        await query.answer()
        results = context.user_data.get("svc_results", [])
        context.user_data["svc_idx"] = min(len(results) - 1, context.user_data.get("svc_idx", 0) + 1)
        await self._show_service(update, context, query=query)
        return SVC_RESULTS

    async def order_service(self, update, context):
        """User pressed 'Order'. Notify the service provider via Telegram + email."""
        query = update.callback_query
        await query.answer()
        lang = get_lang(context)
        sid_str = query.data.replace("svc_order_", "")

        # Find service in results
        results = context.user_data.get("svc_results", [])
        s = next((x for x in results if str(x.get("id", "")) == str(sid_str)), None)
        if not s:
            await query.answer({"ru": "Услуга не найдена", "en": "Service not found", "he": "שירות לא נמצא", "fr": "Service introuvable"}.get(lang, "Not found"), show_alert=True)
            return SVC_RESULTS

        user = update.effective_user
        username = f"@{user.username}" if user.username else user.first_name or str(user.id)
        stype = ALL_SERVICE_TYPES.get(s.get("service_type", ""), {}).get(lang, s.get("service_type", ""))
        owner_tg_id = s.get("user_id")
        owner_phone = s.get("phone", "")
        owner_email = s.get("contact", "") or db.get_service_email(owner_tg_id) if owner_tg_id else ""

        # ── Notify provider via Telegram ────────────────────────────────────
        if owner_tg_id:
            notify_text = {
                "ru": f"📩 <b>Новый заказ!</b>\n\nПользователь {username} хочет заказать вашу услугу <b>{stype}</b>.\n\n📞 Свяжитесь с ним в Telegram.",
                "en": f"📩 <b>New order!</b>\n\nUser {username} wants to order your <b>{stype}</b> service.\n\n📞 Contact them on Telegram.",
                "he": f"📩 <b>הזמנה חדשה!</b>\n\nמשתמש {username} רוצה להזמין את שירות <b>{stype}</b>.\n\n📞 צרו קשר בטלגרם.",
            }.get(lang, f"New order from {username} for {stype}")
            try:
                await context.bot.send_message(chat_id=owner_tg_id, text=notify_text, parse_mode="HTML")
            except Exception:
                pass

        # ── Notify provider via email ────────────────────────────────────────
        if owner_email:
            try:
                import email_reporter
                email_reporter.send_service_order_email(
                    to_email=owner_email,
                    service_type=stype,
                    customer_username=username,
                    customer_tg_id=user.id,
                )
            except Exception:
                pass

        # ── Confirm to customer ──────────────────────────────────────────────
        confirm_text = {
            "ru": f"✅ Заявка отправлена!\n\nПровайдер <b>{s.get('owner_name','')}</b> получил уведомление и свяжется с вами.\n📞 {owner_phone}" if owner_phone else f"✅ Заявка отправлена провайдеру!",
            "en": f"✅ Request sent!\n\nProvider <b>{s.get('owner_name','')}</b> has been notified and will contact you.\n📞 {owner_phone}" if owner_phone else "✅ Request sent to provider!",
            "he": f"✅ הבקשה נשלחה!\n\n<b>{s.get('owner_name','')}</b> קיבל הודעה ויצור איתך קשר.\n📞 {owner_phone}" if owner_phone else "✅ הבקשה נשלחה!",
        }.get(lang, "✅ Order sent!")
        back_label = _L({"ru": "🏠 Меню", "en": "🏠 Menu", "he": "🏠 תפריט", "fr": "🏠 Menu"}, lang)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(back_label, callback_data="back_to_menu")]])
        await query.edit_message_text(confirm_text, reply_markup=kb, parse_mode="HTML")
        return SVC_RESULTS

    # ── Add service flow ─────────────────────────────────────────────────────

    async def start_add(self, update, context):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        # If the user already has an active service-provider subscription — go straight to the form
        if _has_active_svc_subscription(user_id):
            context.user_data["add_svc"] = {}
            text = _t(context,
                "✅ <b>Подписка активна!</b>\n\n➕ Добавить услугу\n\nВыберите тип услуги:",
                "✅ <b>Subscription active!</b>\n\n➕ Add service\n\nSelect service type:",
                "✅ <b>המנוי פעיל!</b>\n\n➕ הוסף שירות\n\nבחר סוג שירות:"
            )
            await query.edit_message_text(text, reply_markup=_add_type_kb(context), parse_mode="HTML")
            return ADD_SVC_TYPE

        # No active subscription — show pricing first
        lang = get_lang(context)
        intro = _L({
            "ru": (
                "💼 <b>Размещение услуги на FlatFinderIL</b>\n\n"
                "Для публикации вашего профиля выберите тип услуги и оплатите пакет.\n\n"
                "Выберите тип услуги, чтобы увидеть тарифы:"
            ),
            "en": (
                "💼 <b>List your service on FlatFinderIL</b>\n\n"
                "To publish your profile, select your service type and purchase a plan.\n\n"
                "Select service type to see pricing:"
            ),
            "he": (
                "💼 <b>פרסם את השירות שלך ב-FlatFinderIL</b>\n\n"
                "כדי לפרסם את הפרופיל שלך, בחר סוג שירות ורכוש חבילה.\n\n"
                "בחר סוג שירות לצפייה בתמחור:"
            ),
        }, lang)
        await query.edit_message_text(intro, reply_markup=_paywall_type_kb(context), parse_mode="HTML")
        return ADD_SVC_AWAIT_PAYMENT

    # ── Paywall payment flow ──────────────────────────────────────────────────

    async def handle_svc_paywall_type(self, update, context):
        """User picked a service type on the paywall screen — show Профи / Партнер choice."""
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svcpay_type_", "")
        lang = get_lang(context)
        context.user_data["svcpay_type"] = svc_type

        # If "repair" (parent type) — drill down to sub-type first
        if svc_type == "repair":
            type_label = _L(SERVICE_TYPES["repair"], lang)
            text = _L({
                "ru": f"🔨 <b>{type_label}</b>\n\nУточните вид ремонтных работ:",
                "en": f"🔨 <b>{type_label}</b>\n\nSelect type of repair work:",
                "he": f"🔨 <b>{type_label}</b>\n\nבחר סוג עבודות שיפוץ:",
            }, lang)
            await query.edit_message_text(text, reply_markup=_repair_kb(context, "svcpay_type_"), parse_mode="HTML")
            return ADD_SVC_AWAIT_PAYMENT

        from pricing import SERVICE_PACKAGES, SVC_PROMO_PACKAGE, SVC_PROFI_MONTHLY_ILS, SVC_PROMO_MONTHLY_ILS
        type_label = _L(ALL_SERVICE_TYPES.get(svc_type, {}), lang)
        profi_pkg  = next(p for p in SERVICE_PACKAGES if p["key"] == "profi")
        partner_pkg = next(p for p in SERVICE_PACKAGES if p["key"] == "partner")

        text = _L({
            "ru": (
                f"💼 <b>{type_label}</b>\n\n"
                f"Выберите тарифный план:\n\n"
                f"🏆 <b>{profi_pkg['label']['ru']}</b>\n"
                f"  {profi_pkg['desc']['ru']}\n\n"
                f"🤝 <b>{partner_pkg['label']['ru']}</b>\n"
                f"  {partner_pkg['desc']['ru']}\n"
                f"  ⭐ Продвижение ТОП — {SVC_PROMO_MONTHLY_ILS} ₪/мес (опционально)"
            ),
            "en": (
                f"💼 <b>{type_label}</b>\n\n"
                f"Choose a plan:\n\n"
                f"🏆 <b>{profi_pkg['label']['en']}</b>\n"
                f"  {profi_pkg['desc']['en']}\n\n"
                f"🤝 <b>{partner_pkg['label']['en']}</b>\n"
                f"  {partner_pkg['desc']['en']}\n"
                f"  ⭐ TOP Promotion — {SVC_PROMO_MONTHLY_ILS} ₪/month (optional)"
            ),
            "he": (
                f"💼 <b>{type_label}</b>\n\n"
                f"בחר תוכנית:\n\n"
                f"🏆 <b>{profi_pkg['label']['he']}</b>\n"
                f"  {profi_pkg['desc']['he']}\n\n"
                f"🤝 <b>{partner_pkg['label']['he']}</b>\n"
                f"  {partner_pkg['desc']['he']}\n"
                f"  ⭐ קידום TOP — {SVC_PROMO_MONTHLY_ILS} ₪/חודש (אופציונלי)"
            ),
        }, lang)

        profi_label   = _L({"ru": f"🏆 Профи — {SVC_PROFI_MONTHLY_ILS} ₪/мес",
                             "en": f"🏆 Profi — {SVC_PROFI_MONTHLY_ILS} ₪/mo",
                             "he": f"🏆 פרו — {SVC_PROFI_MONTHLY_ILS} ₪/חודש"}, lang)
        partner_label = _L({"ru": "🤝 Партнер — комиссия",
                             "en": "🤝 Partner — commission",
                             "he": "🤝 שותף — עמלה"}, lang)
        back_label    = _L({"ru": "« Назад",  "en": "« Back",  "he": "« חזרה"}, lang)
        later_label   = _L({"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}, lang)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(profi_label,   callback_data=f"svcpay_pkg_profi_{svc_type}")],
            [InlineKeyboardButton(partner_label, callback_data=f"svcpay_pkg_partner_{svc_type}")],
            [InlineKeyboardButton(back_label,    callback_data="svcpay_back")],
            [InlineKeyboardButton(later_label,   callback_data="back_to_menu")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return ADD_SVC_AWAIT_PAYMENT

    async def handle_svc_pkg_profi(self, update, context):
        """User chose the Профи plan — show pricing + PayPal link."""
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svcpay_pkg_profi_", "")
        lang = get_lang(context)
        context.user_data["svcpay_type"] = svc_type

        from pricing import SVC_PROFI_MONTHLY_ILS, SVC_PROFI_LEAD_ILS
        type_label = _L(ALL_SERVICE_TYPES.get(svc_type, {}), lang)
        text = _L({
            "ru": (
                f"🏆 <b>Абонемент Профи — {type_label}</b>\n\n"
                f"• {SVC_PROFI_MONTHLY_ILS} ₪/мес — присутствие в базе\n"
                f"• {SVC_PROFI_LEAD_ILS} ₪/лид — открытие контакта клиента\n\n"
                "Оплатите абонемент и нажмите «✅ Я оплатил — продолжить»."
            ),
            "en": (
                f"🏆 <b>Profi Plan — {type_label}</b>\n\n"
                f"• {SVC_PROFI_MONTHLY_ILS} ₪/month — listed in directory\n"
                f"• {SVC_PROFI_LEAD_ILS} ₪/lead — unlock client contact\n\n"
                "Pay the subscription and tap «✅ I paid — continue»."
            ),
            "he": (
                f"🏆 <b>מנוי פרו — {type_label}</b>\n\n"
                f"• {SVC_PROFI_MONTHLY_ILS} ₪/חודש — רישום במאגר\n"
                f"• {SVC_PROFI_LEAD_ILS} ₪/ליד — פתיחת פרטי לקוח\n\n"
                "שלם את המנוי ולחץ «✅ שילמתי — המשך»."
            ),
        }, lang)

        import paypal_payment as _mp
        paypal_url = None
        if _mp.is_enabled():
            try:
                result = _mp.create_service_subscription_link("profi", svc_type, update.effective_user.id, lang)
                paypal_url = result.get("url") if result else None
            except Exception:
                pass

        if not _mp.is_enabled():
            text += _L({
                "ru": "\n\n⏳ <b>Оплата картой скоро будет доступна!</b>\n\nСвяжитесь с нами в Telegram для ручной активации.",
                "en": "\n\n⏳ <b>Card payment coming soon!</b>\n\nContact us in Telegram for manual activation.",
                "he": "\n\n⏳ <b>תשלום בכרטיס בקרוב!</b>\n\nצרו קשר בטלגרם להפעלה ידנית.",
            }, lang)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Telegram", url="https://t.me/flatfinderil_bot")],
                [InlineKeyboardButton(_L({"ru": "✅ Я оплатил — продолжить", "en": "✅ I paid — continue", "he": "✅ שילמתי — המשך"}, lang),
                                      callback_data=f"svcpay_check_{svc_type}")],
                [InlineKeyboardButton(_L({"ru": "◀ Назад к планам", "en": "◀ Back to plans", "he": "◀ חזרה לתוכניות"}, lang),
                                      callback_data=f"svcpay_type_{svc_type}")],
                [InlineKeyboardButton(_L({"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}, lang),
                                      callback_data="back_to_menu")],
            ])
        else:
            kb = _paywall_action_kb(context, svc_type, paypal_url)

        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return ADD_SVC_AWAIT_PAYMENT

    async def handle_svc_pkg_partner(self, update, context):
        """User chose the Партнер plan — show commission info + register/promo options."""
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svcpay_pkg_partner_", "")
        lang = get_lang(context)
        context.user_data["svcpay_type"] = svc_type

        from pricing import SVC_PROMO_MONTHLY_ILS
        type_label = _L(ALL_SERVICE_TYPES.get(svc_type, {}), lang)
        text = _L({
            "ru": (
                f"🤝 <b>Абонемент Партнер — {type_label}</b>\n\n"
                "• Комиссия 10% с каждого заказа\n"
                "• Регистрация в базе — бесплатно\n\n"
                f"⭐ <b>Продвижение ТОП</b> — {SVC_PROMO_MONTHLY_ILS} ₪/мес\n"
                "  Ваш профиль первым в результатах по вашим городам\n\n"
                "Выберите действие:"
            ),
            "en": (
                f"🤝 <b>Partner Plan — {type_label}</b>\n\n"
                "• 10% commission per order\n"
                "• Listed in directory — free\n\n"
                f"⭐ <b>TOP Promotion</b> — {SVC_PROMO_MONTHLY_ILS} ₪/month\n"
                "  Your profile appears first in results for your cities\n\n"
                "Choose an action:"
            ),
            "he": (
                f"🤝 <b>מנוי שותף — {type_label}</b>\n\n"
                "• עמלה 10% מכל הזמנה\n"
                "• רישום במאגר — חינם\n\n"
                f"⭐ <b>קידום TOP</b> — {SVC_PROMO_MONTHLY_ILS} ₪/חודש\n"
                "  הפרופיל שלך יופיע ראשון בתוצאות בעריך\n\n"
                "בחר פעולה:"
            ),
        }, lang)

        free_label  = _L({"ru": "✅ Зарегистрироваться бесплатно", "en": "✅ Register for free", "he": "✅ הרשמה חינם"}, lang)
        promo_label = _L({"ru": f"⭐ + Продвижение ТОП ({SVC_PROMO_MONTHLY_ILS} ₪/мес)",
                          "en": f"⭐ + TOP Promotion ({SVC_PROMO_MONTHLY_ILS} ₪/mo)",
                          "he": f"⭐ + קידום TOP ({SVC_PROMO_MONTHLY_ILS} ₪/חודש)"}, lang)
        back_label  = _L({"ru": "◀ Назад к планам", "en": "◀ Back to plans", "he": "◀ חזרה לתוכניות"}, lang)
        later_label = _L({"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}, lang)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(free_label,  callback_data=f"svcpay_partner_free_{svc_type}")],
            [InlineKeyboardButton(promo_label, callback_data=f"svcpay_partner_promo_{svc_type}")],
            [InlineKeyboardButton(back_label,  callback_data=f"svcpay_type_{svc_type}")],
            [InlineKeyboardButton(later_label, callback_data="back_to_menu")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return ADD_SVC_AWAIT_PAYMENT

    async def handle_svc_partner_free(self, update, context):
        """Партнер registers for free — auto-activate partner subscription then open form."""
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svcpay_partner_free_", "")
        lang = get_lang(context)
        user_id = update.effective_user.id
        context.user_data["svcpay_type"] = svc_type

        # Auto-activate a free partner subscription (365-day validity)
        from datetime import timedelta
        expiry = (_dt.utcnow() + timedelta(days=365)).isoformat()
        db.set_service_subscription(str(user_id), "partner", expiry)

        context.user_data["add_svc"] = {"service_type": svc_type}

        # For repair: ask sub-type before opening region form
        if svc_type in ("repair", *REPAIR_SUBTYPES.keys()):
            type_label = _L(SERVICE_TYPES["repair"], lang)
            text = _L({
                "ru": f"✅ Вы зарегистрированы как Партнер!\n\n🔨 <b>{type_label}</b>\n\nУточните вид ремонтных работ:",
                "en": f"✅ Registered as Partner!\n\n🔨 <b>{type_label}</b>\n\nSelect type of repair work:",
                "he": f"✅ נרשמת כשותף!\n\n🔨 <b>{type_label}</b>\n\nבחר סוג עבודות שיפוץ:",
            }, lang)
            await query.edit_message_text(text, reply_markup=_repair_kb(context, "addrep_type_"), parse_mode="HTML")
            return ADD_SVC_REPAIR_TYPE

        type_label = _L(ALL_SERVICE_TYPES.get(svc_type, {}), lang)
        text = _L({
            "ru": f"✅ Вы зарегистрированы как Партнер!\n\n<b>{type_label}</b>\n\nВыберите район работы:",
            "en": f"✅ Registered as Partner!\n\n<b>{type_label}</b>\n\nSelect work region:",
            "he": f"✅ נרשמת כשותף!\n\n<b>{type_label}</b>\n\nבחר אזור עבודה:",
        }, lang)
        await query.edit_message_text(text, reply_markup=_add_region_kb(context), parse_mode="HTML")
        return ADD_SVC_REGION

    async def handle_svc_partner_promo(self, update, context):
        """Партнер wants TOP promo — auto-activate free subscription then show PayPal for 500₪."""
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svcpay_partner_promo_", "")
        lang = get_lang(context)
        user_id = update.effective_user.id
        context.user_data["svcpay_type"] = svc_type

        # Ensure partner subscription is active (free, 365 days)
        if not _has_active_svc_subscription(user_id):
            from datetime import timedelta
            expiry = (_dt.utcnow() + timedelta(days=365)).isoformat()
            db.set_service_subscription(str(user_id), "partner", expiry)

        from pricing import SVC_PROMO_MONTHLY_ILS
        type_label = _L(ALL_SERVICE_TYPES.get(svc_type, {}), lang)
        text = _L({
            "ru": (
                f"⭐ <b>Продвижение ТОП — {type_label}</b>\n\n"
                f"Стоимость: <b>{SVC_PROMO_MONTHLY_ILS} ₪/мес</b>\n\n"
                "Ваш профиль будет первым в результатах поиска по вашим городам.\n\n"
                "Оплатите и нажмите «✅ Я оплатил — продолжить»."
            ),
            "en": (
                f"⭐ <b>TOP Promotion — {type_label}</b>\n\n"
                f"Price: <b>{SVC_PROMO_MONTHLY_ILS} ₪/month</b>\n\n"
                "Your profile will appear first in search results for your cities.\n\n"
                "Pay and tap «✅ I paid — continue»."
            ),
            "he": (
                f"⭐ <b>קידום TOP — {type_label}</b>\n\n"
                f"מחיר: <b>{SVC_PROMO_MONTHLY_ILS} ₪/חודש</b>\n\n"
                "הפרופיל שלך יופיע ראשון בתוצאות החיפוש בעריך.\n\n"
                "שלם ולחץ «✅ שילמתי — המשך»."
            ),
        }, lang)

        import paypal_payment as _mp
        paypal_url = None
        if _mp.is_enabled():
            try:
                result = _mp.create_service_subscription_link("promo", svc_type, user_id, lang)
                paypal_url = result.get("url") if result else None
            except Exception:
                pass

        rows = []
        if paypal_url:
            rows.append([InlineKeyboardButton(
                _L({"ru": "💳 Оплатить", "en": "💳 Pay now", "he": "💳 שלם עכשיו"}, lang),
                url=paypal_url
            )])
        else:
            rows.append([InlineKeyboardButton("💬 Telegram", url="https://t.me/flatfinderil_bot")])
        rows.append([InlineKeyboardButton(
            _L({"ru": "✅ Я оплатил — продолжить", "en": "✅ I paid — continue", "he": "✅ שילמתי — המשך"}, lang),
            callback_data=f"svcpay_check_{svc_type}"
        )])
        rows.append([InlineKeyboardButton(
            _L({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}, lang),
            callback_data=f"svcpay_pkg_partner_{svc_type}"
        )])
        rows.append([InlineKeyboardButton(
            _L({"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}, lang),
            callback_data="back_to_menu"
        )])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return ADD_SVC_AWAIT_PAYMENT

    async def handle_svc_check_payment(self, update, context):
        """User tapped '✅ I paid' — verify subscription and open the form."""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        lang = get_lang(context)
        svc_type = query.data.replace("svcpay_check_", "")
        context.user_data["svcpay_type"] = svc_type

        if _has_active_svc_subscription(user_id):
            context.user_data["add_svc"] = {"service_type": svc_type}

            # For repair: ask sub-type before opening region form
            if svc_type in ("repair", *REPAIR_SUBTYPES.keys()):
                type_label = _L(SERVICE_TYPES["repair"], lang)
                ok_msg = _L({
                    "ru": f"✅ Оплата подтверждена!\n\n🔨 <b>{type_label}</b>\n\nУточните вид ремонтных работ:",
                    "en": f"✅ Payment confirmed!\n\n🔨 <b>{type_label}</b>\n\nSelect type of repair work:",
                    "he": f"✅ התשלום אושר!\n\n🔨 <b>{type_label}</b>\n\nבחר סוג עבודות שיפוץ:",
                }, lang)
                await query.edit_message_text(ok_msg, reply_markup=_repair_kb(context, "addrep_type_"), parse_mode="HTML")
                return ADD_SVC_REPAIR_TYPE

            type_label = _L(ALL_SERVICE_TYPES.get(svc_type, {}), lang)
            ok_msg = _L({
                "ru": f"✅ Оплата подтверждена!\n\n<b>{type_label}</b>\n\nВыберите район работы:",
                "en": f"✅ Payment confirmed!\n\n<b>{type_label}</b>\n\nSelect work region:",
                "he": f"✅ התשלום אושר!\n\n<b>{type_label}</b>\n\nבחר אזור עבודה:",
            }, lang)
            await query.edit_message_text(ok_msg, reply_markup=_add_region_kb(context), parse_mode="HTML")
            return ADD_SVC_REGION
        else:
            # Payment not received yet
            not_yet = _L({
                "ru": "⏳ Оплата ещё не поступила. Завершите оплату и нажмите «✅ Я оплатил» снова.",
                "en": "⏳ Payment not received yet. Complete the payment and tap «✅ I paid» again.",
                "he": "⏳ התשלום טרם התקבל. השלם את התשלום ולחץ שוב על «✅ שילמתי».",
            }, lang)
            await query.answer(not_yet, show_alert=True)
            return ADD_SVC_AWAIT_PAYMENT

    # ── Add service form ──────────────────────────────────────────────────────

    async def add_handle_type(self, update, context):
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("addsvc_type_", "")
        lang = get_lang(context)

        if svc_type == "repair":
            # Drill down into repair sub-types before continuing
            context.user_data["add_svc"]["service_type"] = "repair"  # temp, overwritten by sub-type
            type_label = _L(SERVICE_TYPES["repair"], lang)
            text = f"🔨 <b>{type_label}</b>\n\n" + _t(
                context,
                "Уточните вид ремонтных работ:",
                "Select type of repair work:",
                "בחר סוג עבודות שיפוץ:"
            )
            await query.edit_message_text(text, reply_markup=_repair_kb(context, "addrep_type_"), parse_mode="HTML")
            return ADD_SVC_REPAIR_TYPE

        context.user_data["add_svc"]["service_type"] = svc_type
        label = _L(SERVICE_TYPES[svc_type], lang)
        await query.edit_message_text(
            f"✅ {label}\n\n" + _t(context, "Выберите район работы:", "Select work region:", "בחר אזור עבודה:"),
            reply_markup=_add_region_kb(context), parse_mode="HTML"
        )
        return ADD_SVC_REGION

    async def handle_repair_add_type(self, update, context):
        """User picked a repair sub-type while adding a service."""
        query = update.callback_query
        await query.answer()
        sub_type = query.data.replace("addrep_type_", "")
        context.user_data["add_svc"]["service_type"] = sub_type
        lang = get_lang(context)
        type_label = _L(REPAIR_SUBTYPES.get(sub_type, {}), lang)
        await query.edit_message_text(
            f"✅ {type_label}\n\n" + _t(context, "Выберите район работы:", "Select work region:", "בחר אזור עבודה:"),
            reply_markup=_add_region_kb(context), parse_mode="HTML"
        )
        return ADD_SVC_REGION

    async def add_handle_region(self, update, context):
        query = update.callback_query
        await query.answer()
        region = query.data.replace("addsvc_region_", "")
        context.user_data["add_svc"]["region"] = region
        lang = get_lang(context)
        if region == "all":
            context.user_data["add_svc"]["city"] = ""
            text = _t(context,
                "💰 Укажите стоимость услуги (₪)\n\nНапример: 500\nИли напишите <b>0</b> если договорная",
                "💰 Enter service price (₪)\n\nExample: 500\nOr write <b>0</b> for negotiable",
                "💰 הזן מחיר השירות (₪)\n\nלדוגמה: 500\nאו כתוב <b>0</b> לפי הסכמה"
            )
            await query.edit_message_text(text, reply_markup=_back_step_kb(context), parse_mode="HTML")
            return ADD_SVC_PRICE
        region_label = REGIONS.get(region, {}).get(lang, region)
        await query.edit_message_text(
            f"✅ {region_label}\n\n" + _t(context, "Выберите город:", "Select city:", "בחר עיר:"),
            reply_markup=_city_kb(context, region, "addsvc_city"),
            parse_mode="HTML"
        )
        return ADD_SVC_CITY

    async def add_handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        city = query.data.replace("addsvc_city_", "")
        context.user_data["add_svc"]["city"] = "" if city == "all" else city
        text = _t(context,
            "💰 Укажите стоимость услуги (₪)\n\nНапример: 500\nИли напишите <b>0</b> если договорная",
            "💰 Enter service price (₪)\n\nExample: 500\nOr write <b>0</b> for negotiable",
            "💰 הזן מחיר השירות (₪)\n\nלדוגמה: 500\nאו כתוב <b>0</b> לפי הסכמה"
        )
        await query.edit_message_text(text, reply_markup=_back_step_kb(context), parse_mode="HTML")
        return ADD_SVC_PRICE

    async def add_handle_price(self, update, context):
        text = update.message.text.strip()
        try:
            price = int(text.replace(" ", "").replace(",", ""))
        except ValueError:
            price = 0
        context.user_data["add_svc"]["price"] = price
        msg = _t(context,
            "📝 Опишите вашу услугу подробнее:\n\n<i>Например: Бригада 2 человека, газель, работаем по всему северу, упаковка включена</i>",
            "📝 Describe your service:\n\n<i>E.g.: 2-person team, van, work across north, packing included</i>",
            "📝 תאר את השירות שלך:\n\n<i>לדוגמה: צוות 2 אנשים, טרנזיט, עובדים בכל הצפון, אריזה כלולה</i>"
        )
        kb = _back_step_kb(context)
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
        return ADD_SVC_DESC

    async def add_handle_desc(self, update, context):
        context.user_data["add_svc"]["description"] = update.message.text.strip()
        msg = _t(context, "👤 Ваше имя:", "👤 Your name:", "👤 שמך:")
        await update.message.reply_text(msg, reply_markup=_back_step_kb(context), parse_mode="HTML")
        return ADD_SVC_NAME

    async def add_handle_name(self, update, context):
        context.user_data["add_svc"]["owner_name"] = update.message.text.strip()
        msg = _t(context, "📞 Номер телефона:", "📞 Phone number:", "📞 מספר טלפון:")
        await update.message.reply_text(msg, reply_markup=_back_step_kb(context), parse_mode="HTML")
        return ADD_SVC_PHONE

    async def add_handle_phone(self, update, context):
        context.user_data["add_svc"]["phone"] = update.message.text.strip()
        svc_type = context.user_data["add_svc"].get("service_type", "")
        if svc_type in ("moving", "packing"):
            lang = get_lang(context)
            user = update.effective_user
            existing = db.get_service_email(user.id if user else None)
            hint = ""
            if existing:
                hint = _L({"ru": f"\n(сохранён: {existing})", "en": f"\n(saved: {existing})", "he": f"\n(שמור: {existing})"}, lang)
            email_text = _t(context,
                f"📧 Email для еженедельных отчётов о просмотрах:{hint}\n\n<i>Отчёт приходит каждое воскресенье в 10:00</i>",
                f"📧 Email for weekly view reports:{hint}\n\n<i>Report arrives every Sunday at 10:00</i>",
                f"📧 אימייל לדוחות שבועיים:{hint}\n\n<i>הדוח מגיע כל יום ראשון ב-10:00</i>"
            )
            skip_btn_label = {"ru": "⏭ Пропустить", "en": "⏭ Skip", "he": "⏭ דלג", "fr": "⏭ Passer"}.get(lang, "⏭ Skip")
            skip_kb = InlineKeyboardMarkup([[InlineKeyboardButton(skip_btn_label, callback_data="svc_email_skip")]])
            await update.message.reply_text(email_text, reply_markup=skip_kb, parse_mode="HTML")
            return ADD_SVC_EMAIL
        # cleaning — go straight to confirm
        return await self._show_svc_confirm(update, context)

    async def add_handle_email(self, update, context):
        import re
        email = update.message.text.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            lang = get_lang(context)
            await update.message.reply_text(
                _t(context,
                   "❌ Неверный формат e-mail. Попробуйте ещё раз или нажмите Пропустить.",
                   "❌ Invalid e-mail. Try again or press Skip.",
                   "❌ כתובת אימייל שגויה. נסה שוב או לחץ דלג.")
            )
            return ADD_SVC_EMAIL
        db.save_service_email(update.effective_user.id, email)
        context.user_data["add_svc"]["email"] = email
        lang = get_lang(context)
        await update.message.reply_text(
            _t(context, f"✅ Email сохранён: {email}", f"✅ Email saved: {email}", f"✅ אימייל נשמר: {email}"),
            parse_mode="HTML"
        )
        return await self._show_svc_confirm(update, context)

    async def add_handle_email_skip(self, update, context):
        query = update.callback_query
        await query.answer()
        return await self._show_svc_confirm(update, context, via_query=True)

    async def _show_svc_confirm(self, update, context, via_query=False):
        lang = get_lang(context)
        context.user_data["add_svc"]["lang"] = lang
        svc = context.user_data["add_svc"]
        svc_type = svc.get("service_type", "")
        region_key = svc.get("region", "")
        type_label = SERVICE_TYPES.get(svc_type, {}).get(lang, svc_type)
        region_label = REGIONS.get(region_key, {}).get(lang, region_key) if region_key != "all" else {
            "ru": "Вся страна", "en": "All country", "he": "כל הארץ"
        }.get(lang)
        price = svc.get("price", 0)
        price_str = f"{price:,} ₪".replace(",", " ") if price else {"ru": "Договорная", "en": "Negotiable", "he": "לפי הסכמה"}.get(lang)
        city = svc.get("city", "")
        location_str = city if city else region_label
        summary = _t(context,
            (
                f"📋 <b>Проверьте данные:</b>\n\n"
                f"• Услуга: {type_label}\n"
                f"• Район: {region_label}\n"
                f"• Город: {location_str}\n"
                f"• Цена: {price_str}\n"
                f"• Описание: {svc.get('description','')}\n"
                f"• Имя: {svc.get('owner_name','')}\n"
                f"• Телефон: {svc.get('phone','')}"
            ),
            (
                f"📋 <b>Check your data:</b>\n\n"
                f"• Service: {type_label}\n"
                f"• Region: {region_label}\n"
                f"• City: {location_str}\n"
                f"• Price: {price_str}\n"
                f"• Description: {svc.get('description','')}\n"
                f"• Name: {svc.get('owner_name','')}\n"
                f"• Phone: {svc.get('phone','')}"
            ),
            (
                f"📋 <b>בדוק את הנתונים:</b>\n\n"
                f"• שירות: {type_label}\n"
                f"• אזור: {region_label}\n"
                f"• עיר: {location_str}\n"
                f"• מחיר: {price_str}\n"
                f"• תיאור: {svc.get('description','')}\n"
                f"• שם: {svc.get('owner_name','')}\n"
                f"• טלפון: {svc.get('phone','')}"
            ),
        )
        if via_query:
            await update.callback_query.edit_message_text(summary, reply_markup=_confirm_kb(context), parse_mode="HTML")
        else:
            await update.message.reply_text(summary, reply_markup=_confirm_kb(context), parse_mode="HTML")
        return ADD_SVC_CONFIRM

    async def add_confirm(self, update, context):
        query = update.callback_query
        await query.answer()
        user = update.effective_user
        svc = context.user_data.get("add_svc", {})
        svc["user_id"] = str(user.id)
        svc["category"] = "service"
        svc["lang"] = get_lang(context)
        db.add_service(svc)
        lang = get_lang(context)
        svc_name = svc.get("name") or svc.get("company") or ""
        svc_type = svc.get("service_type") or svc.get("type") or ""

        # ── Send welcome email to the new service provider ────────────────
        try:
            svc_email = svc.get("email") or db.get_service_email(user.id)
            if svc_email and svc_type:
                import welcome_emails
                welcome_emails.send_service_welcome(
                    user_id=user.id,
                    svc_type=svc_type,
                    lang=lang,
                    name=svc_name,
                    email=svc_email,
                )
        except Exception as _we:
            import logging as _log
            _log.getLogger(__name__).warning(f"[WELCOME] service email error: {_we}")
        type_label = {
            "moving":   {"ru":"Перевозчики","en":"Movers","he":"הובלות", "fr": "Déménageurs"},
            "packing":  {"ru":"Упаковщики","en":"Packers","he":"אריזה", "fr": "Emballeurs"},
            "cleaning": {"ru":"Уборка","en":"Cleaning","he":"ניקיון", "fr": "Ménage"},
        }.get(svc_type, {}).get(lang, svc_type)

        # User already paid before filling the form — just show success
        icons = {"moving": "🚛", "packing": "📦", "cleaning": "🧹"}
        icon = icons.get(svc_type, "✅")
        greeting = f"{'Здравствуйте, <b>' + svc_name + '</b>!' if svc_name else 'Здравствуйте!'}"
        greeting_en = f"{'Hello, <b>' + svc_name + '</b>!' if svc_name else 'Hello!'}"
        greeting_he = f"{'שלום, <b>' + svc_name + '</b>!' if svc_name else 'שלום!'}"

        text = _t(context,
            f"{icon} <b>FlatFinderIL — Профиль опубликован!</b>\n\n"
            f"{greeting} Ваш профиль активен и виден клиентам в разделе 🔧 <b>Услуги</b>. 💼",
            f"{icon} <b>FlatFinderIL — Profile Published!</b>\n\n"
            f"{greeting_en} Your profile is live and visible to clients in the 🔧 <b>Services</b> section. 💼",
            f"{icon} <b>FlatFinderIL — הפרופיל פורסם!</b>\n\n"
            f"{greeting_he} הפרופיל שלך פעיל וגלוי ללקוחות בקטגוריה 🔧 <b>שירותים</b>. 💼"
        )
        await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ConversationHandler.END

    async def back_to_menu_cb(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["svc"] = {}
        text = _t(context,
            "🚚 <b>Услуги</b>\n\nВыберите категорию:",
            "🚚 <b>Services</b>\n\nSelect category:",
            "🚚 <b>שירותים</b>\n\nבחר קטגוריה:"
        )
        await query.edit_message_text(text, reply_markup=_services_menu_kb(context), parse_mode="HTML")
        return SVC_MENU

    async def cancel(self, update, context):
        from keyboards import main_menu_keyboard
        from formatters import format_welcome
        text = format_welcome(update.effective_user.first_name, context)
        kb = main_menu_keyboard(context)
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
        return ConversationHandler.END
