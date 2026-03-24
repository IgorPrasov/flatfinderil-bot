from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from i18n import get_lang
import database as db

# States
(
    SVC_MENU, SVC_REGION, SVC_CITY, SVC_RESULTS,
    ADD_SVC_TYPE, ADD_SVC_REGION, ADD_SVC_CITY, ADD_SVC_PRICE, ADD_SVC_DESC, ADD_SVC_NAME, ADD_SVC_PHONE, ADD_SVC_EMAIL, ADD_SVC_CONFIRM
) = range(10, 23)

SERVICE_TYPES = {
    "moving":   {"ru": "🚚 Перевозки",   "en": "🚚 Moving",   "he": "🚚 הובלות"},
    "packing":  {"ru": "📦 Упаковка",    "en": "📦 Packing",  "he": "📦 אריזה"},
    "cleaning": {"ru": "🧹 Клининг",     "en": "🧹 Cleaning", "he": "🧹 ניקיון"},
}

REGIONS = {
    "north":  {"ru": "🌿 Север",  "en": "🌿 North",  "he": "🌿 צפון"},
    "center": {"ru": "🏙 Центр",  "en": "🏙 Center", "he": "🏙 מרכז"},
    "south":  {"ru": "☀️ Юг",     "en": "☀️ South",  "he": "☀️ דרום"},
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
    return {"ru": ru, "en": en, "he": he}.get(lang, ru)


def _lbl(ctx, key, mapping):
    lang = get_lang(ctx)
    return mapping[key].get(lang, mapping[key]["ru"])


def _back_kb(ctx):
    lang = get_lang(ctx)
    back = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[lang]
    return InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="back_to_menu")]])


def _services_menu_kb(ctx):
    lang = get_lang(ctx)
    rows = []
    for key, names in SERVICE_TYPES.items():
        rows.append([InlineKeyboardButton(names[lang], callback_data=f"svc_type_{key}")])
    add_label = {"ru": "➕ Разместить услугу", "en": "➕ Add service", "he": "➕ הוסף שירות"}[lang]
    back_label = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[lang]
    rows.append([InlineKeyboardButton(add_label, callback_data="svc_add")])
    rows.append([InlineKeyboardButton(back_label, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def _region_kb(ctx, prefix):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(REGIONS[r][lang], callback_data=f"{prefix}_{r}")] for r in REGIONS]
    all_label = {"ru": "🌍 Вся страна", "en": "🌍 All country", "he": "🌍 כל הארץ"}[lang]
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    rows.append([InlineKeyboardButton(all_label, callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _add_type_kb(ctx):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(names[lang], callback_data=f"addsvc_type_{key}")]
            for key, names in SERVICE_TYPES.items()]
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    rows.append([InlineKeyboardButton(back_label, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def _add_region_kb(ctx):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(REGIONS[r][lang], callback_data=f"addsvc_region_{r}")] for r in REGIONS]
    all_label = {"ru": "🌍 Вся страна", "en": "🌍 All country", "he": "🌍 כל הארץ"}[lang]
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
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
    all_label = {"ru": "🌍 Весь район", "en": "🌍 All region", "he": "🌍 כל האזור"}[lang]
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    rows.append([InlineKeyboardButton(all_label, callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back_label, callback_data="svc_back")])
    return InlineKeyboardMarkup(rows)


def _back_step_kb(ctx):
    lang = get_lang(ctx)
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    return InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="svc_back")]])


def _confirm_kb(ctx):
    lang = get_lang(ctx)
    pub = {"ru": "✅ Опубликовать", "en": "✅ Publish", "he": "✅ פרסם"}[lang]
    cancel = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(pub, callback_data="addsvc_confirm_yes")],
        [InlineKeyboardButton(cancel, callback_data="back_to_menu")],
    ])


def _format_service_card(s, lang):
    stype = SERVICE_TYPES.get(s.get("service_type", ""), {}).get(lang, s.get("service_type", ""))
    region_key = s.get("region", "")
    region = REGIONS.get(region_key, {}).get(lang, region_key) if region_key not in ("all", "") else {
        "ru": "Вся страна", "en": "All country", "he": "כל הארץ"
    }.get(lang, "All")
    city = s.get("city", "")
    location = city if city else region
    price = s.get("price", 0)
    price_str = f"{price:,} ₪".replace(",", " ") if price else {"ru": "Договорная", "en": "Negotiable", "he": "לפי הסכמה"}.get(lang)
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
        await query.edit_message_text(text, reply_markup=_services_menu_kb(context), parse_mode="HTML")
        return SVC_MENU

    async def handle_type(self, update, context):
        query = update.callback_query
        await query.answer()
        svc_type = query.data.replace("svc_type_", "")
        context.user_data["svc"]["type"] = svc_type
        lang = get_lang(context)
        type_label = SERVICE_TYPES[svc_type][lang]
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
        region_label = REGIONS.get(region, {}).get(lang, region) if region != "all" else {
            "ru": "Вся страна", "en": "All country", "he": "כל הארץ"
        }[lang]
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
        back_label = {"ru": "🏠 Меню", "en": "🏠 Menu", "he": "🏠 תפריט"}[lang]
        kb = InlineKeyboardMarkup([nav_buttons, [InlineKeyboardButton(back_label, callback_data="back_to_menu")]]) if nav_buttons else InlineKeyboardMarkup([[InlineKeyboardButton(back_label, callback_data="back_to_menu")]])
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

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
        label = SERVICE_TYPES[svc_type][lang]
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
                hint = {"ru": f"\n(сохранён: {existing})", "en": f"\n(saved: {existing})", "he": f"\n(שמור: {existing})"}[lang]
            email_text = _t(context,
                f"📧 Email для еженедельных отчётов о просмотрах:{hint}\n\n<i>Отчёт приходит каждое воскресенье в 10:00</i>",
                f"📧 Email for weekly view reports:{hint}\n\n<i>Report arrives every Sunday at 10:00</i>",
                f"📧 אימייל לדוחות שבועיים:{hint}\n\n<i>הדוח מגיע כל יום ראשון ב-10:00</i>"
            )
            skip_btn_label = {"ru": "⏭ Пропустить", "en": "⏭ Skip", "he": "⏭ דלג"}.get(lang, "⏭ Skip")
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
        text = _t(context,
            "✅ <b>Услуга опубликована!</b>\n\nДругие пользователи увидят ваше объявление.",
            "✅ <b>Service published!</b>\n\nOther users will see your listing.",
            "✅ <b>השירות פורסם!</b>\n\nמשתמשים אחרים יראו את המודעה שלך."
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
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            format_welcome(update.effective_user.first_name, context),
            reply_markup=main_menu_keyboard(context),
            parse_mode="HTML"
        )
        return ConversationHandler.END
