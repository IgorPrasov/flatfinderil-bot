from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from i18n import get_lang
import database as db

# States

def _L(d, lang):
    """Безопасный выбор перевода: lang → en → ru → первый доступный."""
    if not isinstance(d, dict):
        return str(d)
    return d.get(lang) or d.get("en") or d.get("ru") or next(iter(d.values()), "")


(
    SVC_MENU, SVC_REGION, SVC_CITY, SVC_RESULTS,
    ADD_SVC_TYPE, ADD_SVC_REGION, ADD_SVC_CITY, ADD_SVC_PRICE, ADD_SVC_DESC, ADD_SVC_NAME, ADD_SVC_PHONE, ADD_SVC_EMAIL, ADD_SVC_CONFIRM
) = range(10, 23)

SERVICE_TYPES = {
    "moving":   {"ru": "🚚 Перевозки",   "en": "🚚 Moving",   "he": "🚚 הובלות", "fr": "🚚 Déménagement"},
    "packing":  {"ru": "📦 Упаковка",    "en": "📦 Packing",  "he": "📦 אריזה", "fr": "📦 Emballage"},
    "cleaning": {"ru": "🧹 Клининг",     "en": "🧹 Cleaning", "he": "🧹 ניקיון", "fr": "🧹 Ménage"},
}

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
    stype = SERVICE_TYPES.get(s.get("service_type", ""), {}).get(lang, s.get("service_type", ""))
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


class ServiceHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start, pattern="^services$"),
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
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.cancel),
            ],
            per_message=False, allow_reentry=True,
        )

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
        context.user_data["svc"]["type"] = svc_type
        lang = get_lang(context)
        type_label = _L(SERVICE_TYPES[svc_type], lang)
        await query.edit_message_text(
            f"✅ <b>{type_label}</b>\n\n" + _t(context, "Выберите район:", "Select region:", "בחר אזור:"),
            reply_markup=_region_kb(context, "svc_region"),
            parse_mode="HTML"
        )
        return SVC_REGION

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
        region = context.user_data["svc"].get("region")
        svc_type = context.user_data["svc"].get("type")
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
        stype = SERVICE_TYPES.get(s.get("service_type", ""), {}).get(lang, s.get("service_type", ""))
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
        context.user_data["add_svc"] = {}
        text = _t(context,
            "➕ <b>Добавить услугу</b>\n\nВыберите тип услуги:",
            "➕ <b>Add service</b>\n\nSelect service type:",
            "➕ <b>הוסף שירות</b>\n\nבחר סוג שירות:"
        )
        await query.edit_message_text(text, reply_markup=_add_type_kb(context), parse_mode="HTML")
        return ADD_SVC_TYPE

    async def add_handle_type(self, update, context):
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("addsvc_type_", "")
        context.user_data["add_svc"]["service_type"] = svc_type
        lang = get_lang(context)
        label = _L(SERVICE_TYPES[svc_type], lang)
        await query.edit_message_text(f"✅ {label}\n\n" + _t(context, "Выберите район работы:", "Select work region:", "בחר אזור עבודה:"),
                                      reply_markup=_add_region_kb(context), parse_mode="HTML")
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
            "movers":   {"ru":"Перевозчики","en":"Movers","he":"הובלות", "fr": "Déménageurs"},
            "packers":  {"ru":"Упаковщики","en":"Packers","he":"אריזה", "fr": "Emballeurs"},
            "cleaning": {"ru":"Уборка","en":"Cleaning","he":"ניקיון", "fr": "Ménage"},
        }.get(svc_type, {}).get(lang, svc_type)

        # ── Pricing block per service type ────────────────────────────────────
        from pricing import format_service_pricing
        pricing_block = format_service_pricing(svc_type, lang)

        if svc_type == "movers":
            text = _t(context,
                f"🚛 <b>FlatFinderIL — Услуга опубликована!</b>\n\n"
                f"{'Здравствуйте, <b>' + svc_name + '</b>!' if svc_name else 'Здравствуйте!'} Ваша компания по перевозкам размещена на платформе.\n\n"
                f"{pricing_block}\n\n"
                f"Нажмите кнопку ниже, чтобы оформить подписку и начать получать клиентов. "
                f"Клиенты находят вас через раздел 🔧 <b>Услуги</b>. 💼",

                f"🚛 <b>FlatFinderIL — Service Published!</b>\n\n"
                f"{'Hello, <b>' + svc_name + '</b>!' if svc_name else 'Hello!'} Your moving company is now on the platform.\n\n"
                f"{pricing_block}\n\n"
                f"Tap the button below to subscribe and start receiving clients through the 🔧 <b>Services</b> section. 💼",

                f"🚛 <b>FlatFinderIL — השירות פורסם!</b>\n\n"
                f"{'שלום, <b>' + svc_name + '</b>!' if svc_name else 'שלום!'} חברת ההובלות שלך פעילה בפלטפורמה.\n\n"
                f"{pricing_block}\n\n"
                f"לחץ על הכפתור למטה כדי להירשם לחבילה ולהתחיל לקבל לקוחות. 💼"
            )
            # Build mover subscription keyboard
            import morning_payment as _mp
            if _mp.is_enabled():
                from pricing import MOVER_PACKAGES
                rows = []
                for mpkg in MOVER_PACKAGES:
                    mpkg_label = mpkg["label"].get(lang, mpkg["label"]["ru"])
                    rows.append([InlineKeyboardButton(
                        f"{mpkg_label} — {mpkg['price_ils']} ₪/{'нед' if lang=='ru' else 'wk' if lang=='en' else 'שבוע'}",
                        callback_data=f"mover_subscribe_{mpkg['key']}"
                    )])
                rows.append([InlineKeyboardButton(
                    {"ru": "⏭ Позже", "en": "⏭ Later", "he": "⏭ מאוחר יותר"}.get(lang, "⏭ Later"),
                    callback_data="back_to_menu"
                )])
                kb = InlineKeyboardMarkup(rows)
            else:
                kb = _back_kb(context)
        elif svc_type == "cleaning":
            text = _t(context,
                f"🧹 <b>FlatFinderIL — Услуга опубликована!</b>\n\n"
                f"{'Здравствуйте, <b>' + svc_name + '</b>!' if svc_name else 'Здравствуйте!'} Ваш клининговый сервис размещён на платформе.\n\n"
                f"{pricing_block}\n\n"
                f"Клиенты уже могут найти вас через раздел 🔧 <b>Услуги</b>. Менеджер свяжется с вами для оформления условий работы. 💼",

                f"🧹 <b>FlatFinderIL — Service Published!</b>\n\n"
                f"{'Hello, <b>' + svc_name + '</b>!' if svc_name else 'Hello!'} Your cleaning service is now live.\n\n"
                f"{pricing_block}\n\n"
                f"Clients can find you through the 🔧 <b>Services</b> section. Our manager will contact you to set up terms. 💼",

                f"🧹 <b>FlatFinderIL — השירות פורסם!</b>\n\n"
                f"{'שלום, <b>' + svc_name + '</b>!' if svc_name else 'שלום!'} שירות הניקיון שלך פעיל בפלטפורמה.\n\n"
                f"{pricing_block}\n\n"
                f"לקוחות יכולים למצוא אותך בסעיף 🔧 <b>שירותים</b>. מנהל שלנו יצור איתך קשר לגיבוש תנאי העבודה. 💼"
            )
            kb = _back_kb(context)
        elif svc_type == "packers":
            text = _t(context,
                f"📦 <b>FlatFinderIL — Услуга опубликована!</b>\n\n"
                f"{'Здравствуйте, <b>' + svc_name + '</b>!' if svc_name else 'Здравствуйте!'} Ваш сервис упаковки размещён на платформе.\n\n"
                f"{pricing_block}\n\n"
                f"Клиенты уже могут найти вас через раздел 🔧 <b>Услуги</b>. Менеджер свяжется с вами для оформления условий. 💼",

                f"📦 <b>FlatFinderIL — Service Published!</b>\n\n"
                f"{'Hello, <b>' + svc_name + '</b>!' if svc_name else 'Hello!'} Your packing service is now live.\n\n"
                f"{pricing_block}\n\n"
                f"Clients can find you through the 🔧 <b>Services</b> section. Our manager will contact you to set up terms. 💼",

                f"📦 <b>FlatFinderIL — השירות פורסם!</b>\n\n"
                f"{'שלום, <b>' + svc_name + '</b>!' if svc_name else 'שלום!'} שירות האריזה שלך פעיל בפלטפורמה.\n\n"
                f"{pricing_block}\n\n"
                f"לקוחות יכולים למצוא אותך בסעיף 🔧 <b>שירותים</b>. מנהל שלנו יצור איתך קשר לגיבוש תנאי העבודה. 💼"
            )
            kb = _back_kb(context)
        else:
            text = _t(context,
                f"🚚 <b>FlatFinderIL — Услуга опубликована!</b>\n\n"
                f"{'Здравствуйте, <b>' + svc_name + '</b>!' if svc_name else 'Здравствуйте!'} Ваша услуга размещена.\n\n"
                f"Клиенты уже могут найти вас через раздел 🔧 <b>Услуги</b>. 💼",
                f"🚚 <b>FlatFinderIL — Service Published!</b>\n\n"
                f"{'Hello, <b>' + svc_name + '</b>!' if svc_name else 'Hello!'} Your service is now live. 💼",
                f"🚚 <b>FlatFinderIL — השירות פורסם!</b>\n\n"
                f"{'שלום, <b>' + svc_name + '</b>!' if svc_name else 'שלום!'} השירות שלך פעיל. 💼"
            )
            kb = _back_kb(context)

        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
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
