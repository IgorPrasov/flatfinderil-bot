from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, CommandHandler, filters
)
from i18n import get_lang
import database as db


def _L(d, lang):
    """Безопасный выбор перевода: lang → en → ru → первый доступный."""
    if not isinstance(d, dict):
        return str(d)
    return d.get(lang) or d.get("en") or d.get("ru") or next(iter(d.values()), "")

# States (100–116)
(
    CRM_MENU, CRM_LIST, CRM_VIEW,
    CRM_ADD_TYPE, CRM_ADD_NAME, CRM_ADD_PHONE, CRM_ADD_TELEGRAM,
    CRM_ADD_REGION, CRM_ADD_CITY, CRM_ADD_NOTES, CRM_ADD_CONFIRM,
    CRM_ADD_DEAL, CRM_ADD_DEAL_DESC, CRM_ADD_DEAL_STATUS, CRM_ADD_DEAL_CONFIRM,
    CRM_ADD_NOTE,
) = range(100, 116)

CONTACT_TYPES = {
    "agent":   {"ru": "🏘 Агент",      "en": "🏘 Agent",   "he": "🏘 סוכן"},
    "mover":   {"ru": "🚚 Перевозчик", "en": "🚚 Mover",   "he": "🚚 הובלה"},
    "packer":  {"ru": "📦 Упаковщик",  "en": "📦 Packer",  "he": "📦 אורזים"},
    "cleaner": {"ru": "🧹 Клининг",    "en": "🧹 Cleaning","he": "🧹 ניקיון"},
}

REGIONS = {
    "north":  {"ru": "🌿 Север",  "en": "🌿 North",  "he": "🌿 צפון"},
    "center": {"ru": "🏙 Центр",  "en": "🏙 Center", "he": "🏙 מרכז"},
    "south":  {"ru": "☀️ Юг",     "en": "☀️ South",  "he": "☀️ דרום"},
}

REGION_CITIES = {
    "north":  ["Хайфа","Кирьят-Ата","Кирьят-Бялик","Акко","Нагария","Тиверия","Хадера","Кармиэль","Афула"],
    "center": ["Тель-Авив","Иерусалим","Нетания","Рамат-Ган","Бней-Брак","Бат-Ям","Холон","Петах-Тиква","Ришон-ле-Цион","Реховот","Нес-Циона","Лод","Рамла","Модиин","Кфар-Саба","Раанана","Герцлия"],
    "south":  ["Ашдод","Ашкелон","Беэр-Шева","Эйлат","Нетивот","Сдерот"],
}

DEAL_STATUSES = {
    "new":         {"ru": "🆕 Новая",     "en": "🆕 New",        "he": "🆕 חדשה"},
    "in_progress": {"ru": "⏳ В работе",  "en": "⏳ In progress","he": "⏳ בתהליך"},
    "done":        {"ru": "✅ Завершена", "en": "✅ Done",       "he": "✅ הושלם"},
    "cancelled":   {"ru": "❌ Отменена",  "en": "❌ Cancelled",  "he": "❌ בוטל"},
}

STATUS_ICONS = {"new": "🆕", "in_progress": "⏳", "done": "✅", "cancelled": "❌"}


def _t(ctx, ru, en="", he=""):
    lang = get_lang(ctx)
    return _L({"ru": ru, "en": en or ru, "he": he or ru}, lang)


def _lang(ctx):
    return get_lang(ctx)


# ── Keyboards ─────────────────────────────────────────────────────────────────

def _crm_main_kb(ctx):
    lang = get_lang(ctx)
    rows = []
    row = []
    for key, names in CONTACT_TYPES.items():
        row.append(InlineKeyboardButton(_L(names, lang), callback_data=f"crm_type_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    add = _L({"ru": "➕ Добавить контакт", "en": "➕ Add contact", "he": "➕ הוסף איש קשר"}, lang)
    back = _L({"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}, lang)
    rows.append([InlineKeyboardButton(add, callback_data="crm_add")])
    rows.append([InlineKeyboardButton(back, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def _contact_type_kb(ctx, prefix="crm_add_type"):
    lang = get_lang(ctx)
    rows = []
    row = []
    for key, names in CONTACT_TYPES.items():
        row.append(InlineKeyboardButton(_L(names, lang), callback_data=f"{prefix}_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    rows.append([InlineKeyboardButton(back, callback_data="crm_back")])
    return InlineKeyboardMarkup(rows)


def _region_kb(ctx, prefix):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(REGIONS[r], lang), callback_data=f"{prefix}_{r}")] for r in REGIONS]
    all_lbl = _L({"ru": "🌍 Вся страна", "en": "🌍 All country", "he": "🌍 כל הארץ"}, lang)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    rows.append([InlineKeyboardButton(all_lbl, callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back, callback_data="crm_back")])
    return InlineKeyboardMarkup(rows)


def _city_kb(ctx, region, prefix):
    lang = get_lang(ctx)
    cities = REGION_CITIES.get(region, [])
    rows, row = [], []
    for city in cities:
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_{city}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    all_lbl = _L({"ru": "🌍 Весь район", "en": "🌍 All region", "he": "🌍 כל האזור"}, lang)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    rows.append([InlineKeyboardButton(all_lbl, callback_data=f"{prefix}_all")])
    rows.append([InlineKeyboardButton(back, callback_data="crm_back")])
    return InlineKeyboardMarkup(rows)


def _skip_back_kb(ctx, skip_data):
    lang = get_lang(ctx)
    skip = _L({"ru": "⏭ Пропустить", "en": "⏭ Skip", "he": "⏭ דלג"}, lang)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(back, callback_data="crm_back"),
        InlineKeyboardButton(skip, callback_data=skip_data),
    ]])


def _confirm_kb(ctx):
    lang = get_lang(ctx)
    yes = _L({"ru": "✅ Сохранить", "en": "✅ Save", "he": "✅ שמור"}, lang)
    no = _L({"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes, callback_data="crm_confirm_yes")],
        [InlineKeyboardButton(no, callback_data="back_to_menu")],
    ])


def _contact_actions_kb(ctx, contact_id):
    lang = get_lang(ctx)
    deal = _L({"ru": "➕ Добавить сделку", "en": "➕ Add deal", "he": "➕ הוסף עסקה"}, lang)
    deals = _L({"ru": "📋 Сделки", "en": "📋 Deals", "he": "📋 עסקאות"}, lang)
    note = _L({"ru": "📝 Заметка", "en": "📝 Note", "he": "📝 הערה"}, lang)
    deact = _L({"ru": "🗑 Деактивировать", "en": "🗑 Deactivate", "he": "🗑 השבת"}, lang)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(deal, callback_data=f"crm_deal_new_{contact_id}"),
         InlineKeyboardButton(deals, callback_data=f"crm_deals_{contact_id}")],
        [InlineKeyboardButton(note, callback_data=f"crm_note_{contact_id}"),
         InlineKeyboardButton(deact, callback_data=f"crm_deactivate_{contact_id}")],
        [InlineKeyboardButton(back, callback_data="crm_back")],
    ])


def _deal_status_kb(ctx):
    lang = get_lang(ctx)
    rows = [[InlineKeyboardButton(_L(DEAL_STATUSES[s], lang), callback_data=f"crm_deal_status_{s}")]
            for s in DEAL_STATUSES]
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    rows.append([InlineKeyboardButton(back, callback_data="crm_back")])
    return InlineKeyboardMarkup(rows)


def _back_kb(ctx):
    lang = get_lang(ctx)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
    menu = _L({"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}, lang)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(back, callback_data="crm_back"),
        InlineKeyboardButton(menu, callback_data="back_to_menu"),
    ]])


# ── Card formatter ────────────────────────────────────────────────────────────

def _format_contact(c, lang, deals=None, notes=None):
    ctype = CONTACT_TYPES.get(c.get("contact_type", ""), {}).get(lang, "")
    region_key = c.get("region", "")
    region = REGIONS.get(region_key, {}).get(lang, region_key) if region_key not in ("all", "") else {
        "ru": "Вся страна", "en": "All country", "he": "כל הארץ"
    }.get(lang, "All")
    city = c.get("city", "")
    location = city if city and city != "all" else region
    lines = [
        f"<b>{c.get('name', '')}</b>  <code>{ctype}</code>",
        f"📍 {location}" if location else "",
        f"📞 {c.get('phone', '')}" if c.get("phone") else "",
        f"✉️ {c.get('telegram', '')}" if c.get("telegram") else "",
        f"📝 {c.get('notes', '')}" if c.get("notes") else "",
        f"🗓 {c.get('date_added', '')}",
    ]
    if deals:
        open_deals = [d for d in deals if d.get("status") in ("new", "in_progress")]
        if open_deals:
            lines.append(f"\n⚡ Активных сделок: <b>{len(open_deals)}</b>")
    if notes:
        last = notes[-1]
        lines.append(f"\n💬 Последняя заметка ({last.get('date','')}):\n{last.get('text','')}")
    return "\n".join(l for l in lines if l)


# ── Handler ───────────────────────────────────────────────────────────────────

class CRMHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start, pattern="^crm$"),
            ],
            states={
                CRM_MENU: [
                    CallbackQueryHandler(self.handle_type, pattern="^crm_type_"),
                    CallbackQueryHandler(self.start_add, pattern="^crm_add$"),
                ],
                CRM_LIST: [
                    CallbackQueryHandler(self.show_contact, pattern="^crm_contact_"),
                    CallbackQueryHandler(self.start, pattern="^crm_back$"),
                ],
                CRM_VIEW: [
                    CallbackQueryHandler(self.start_add_deal, pattern="^crm_deal_new_"),
                    CallbackQueryHandler(self.show_deals, pattern="^crm_deals_"),
                    CallbackQueryHandler(self.start_add_note, pattern="^crm_note_"),
                    CallbackQueryHandler(self.deactivate_contact, pattern="^crm_deactivate_"),
                    CallbackQueryHandler(self.handle_type_back, pattern="^crm_back$"),
                ],
                CRM_ADD_TYPE: [
                    CallbackQueryHandler(self.add_set_type, pattern="^crm_add_type_"),
                    CallbackQueryHandler(self.start, pattern="^crm_back$"),
                ],
                CRM_ADD_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_set_name),
                    CallbackQueryHandler(self.start_add, pattern="^crm_back$"),
                ],
                CRM_ADD_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_set_phone),
                    CallbackQueryHandler(self.add_back_to_name, pattern="^crm_back$"),
                ],
                CRM_ADD_TELEGRAM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_set_telegram),
                    CallbackQueryHandler(self.add_set_phone_skip, pattern="^crm_skip_telegram$"),
                    CallbackQueryHandler(self.add_back_to_phone, pattern="^crm_back$"),
                ],
                CRM_ADD_REGION: [
                    CallbackQueryHandler(self.add_set_region, pattern="^crm_add_region_"),
                    CallbackQueryHandler(self.add_back_to_telegram, pattern="^crm_back$"),
                ],
                CRM_ADD_CITY: [
                    CallbackQueryHandler(self.add_set_city, pattern="^crm_add_city_"),
                    CallbackQueryHandler(self.add_back_to_region, pattern="^crm_back$"),
                ],
                CRM_ADD_NOTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_set_notes),
                    CallbackQueryHandler(self.add_set_notes_skip, pattern="^crm_skip_notes$"),
                    CallbackQueryHandler(self.add_back_to_city, pattern="^crm_back$"),
                ],
                CRM_ADD_CONFIRM: [
                    CallbackQueryHandler(self.add_confirm, pattern="^crm_confirm_yes$"),
                    CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                ],
                CRM_ADD_DEAL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_deal_amount),
                    CallbackQueryHandler(self.cancel, pattern="^crm_back$"),
                ],
                CRM_ADD_DEAL_DESC: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_deal_desc),
                    CallbackQueryHandler(self.add_deal_skip_desc, pattern="^crm_skip_desc$"),
                ],
                CRM_ADD_DEAL_STATUS: [
                    CallbackQueryHandler(self.add_deal_status, pattern="^crm_deal_status_"),
                ],
                CRM_ADD_DEAL_CONFIRM: [
                    CallbackQueryHandler(self.save_deal, pattern="^crm_deal_save$"),
                    CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                ],
                CRM_ADD_NOTE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_note),
                    CallbackQueryHandler(self.cancel, pattern="^crm_back$"),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.cancel),
            ],
            per_message=False,
            allow_reentry=True,
        )

    # ── Entry ──────────────────────────────────────────────────────────────

    async def start(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["crm"] = context.user_data.get("crm", {})
        text = _t(context,
            "👥 <b>CRM — Контакты</b>\n\nВыберите тип контакта для просмотра или добавьте новый:",
            "👥 <b>CRM — Contacts</b>\n\nSelect contact type or add new:",
            "👥 <b>CRM — אנשי קשר</b>\n\nבחר סוג איש קשר:"
        )
        await query.edit_message_text(text, reply_markup=_crm_main_kb(context), parse_mode="HTML")
        return CRM_MENU

    async def handle_type(self, update, context):
        query = update.callback_query
        await query.answer()
        ctype = query.data.replace("crm_type_", "")
        context.user_data["crm"]["filter_type"] = ctype
        lang = get_lang(context)
        contacts = db.get_crm_contacts(contact_type=ctype)
        type_name = CONTACT_TYPES.get(ctype, {}).get(lang, ctype)
        if not contacts:
            text = _t(context,
                f"👥 <b>{type_name}</b>\n\nКонтактов не найдено. Добавьте первый!",
                f"👥 <b>{type_name}</b>\n\nNo contacts found. Add the first one!",
                f"👥 <b>{type_name}</b>\n\nאין אנשי קשר. הוסף את הראשון!"
            )
            back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
            add = _L({"ru": "➕ Добавить", "en": "➕ Add", "he": "➕ הוסף"}, lang)
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(back, callback_data="crm_back"),
                InlineKeyboardButton(add, callback_data="crm_add"),
            ]])
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return CRM_MENU
        rows = []
        for c in contacts[:20]:
            city = c.get("city", "") or c.get("region", "")
            label = f"{c['name']} · {city}" if city and city != "all" else c["name"]
            rows.append([InlineKeyboardButton(label, callback_data=f"crm_contact_{c['id']}")])
        back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
        rows.append([InlineKeyboardButton(back, callback_data="crm_back")])
        text = _t(context,
            f"👥 <b>{type_name}</b> — {len(contacts)} контактов",
            f"👥 <b>{type_name}</b> — {len(contacts)} contacts",
            f"👥 <b>{type_name}</b> — {len(contacts)} אנשי קשר"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return CRM_LIST

    async def handle_type_back(self, update, context):
        return await self.handle_type_list(update, context)

    async def handle_type_list(self, update, context):
        ctype = context.user_data.get("crm", {}).get("filter_type", "agent")
        # fake callback data
        update.callback_query.data = f"crm_type_{ctype}"
        return await self.handle_type(update, context)

    async def show_contact(self, update, context):
        query = update.callback_query
        await query.answer()
        contact_id = int(query.data.replace("crm_contact_", ""))
        context.user_data["crm"]["current_contact_id"] = contact_id
        lang = get_lang(context)
        c = db.get_crm_contact(contact_id)
        if not c:
            await query.edit_message_text("Контакт не найден.")
            return CRM_LIST
        deals = db.get_crm_deals(contact_id=contact_id)
        notes = db.get_crm_notes(contact_id)
        text = _format_contact(c, lang, deals, notes)
        await query.edit_message_text(text, reply_markup=_contact_actions_kb(context, contact_id), parse_mode="HTML")
        return CRM_VIEW

    async def show_deals(self, update, context):
        query = update.callback_query
        await query.answer()
        contact_id = int(query.data.replace("crm_deals_", ""))
        lang = get_lang(context)
        deals = db.get_crm_deals(contact_id=contact_id)
        if not deals:
            text = _t(context, "Сделок пока нет.", "No deals yet.", "אין עסקאות.")
        else:
            lines = []
            for d in deals:
                status_icon = STATUS_ICONS.get(d.get("status", "new"), "🆕")
                amount = f"{d.get('amount', 0):,} ₪" if d.get("amount") else "—"
                desc = d.get("description", "")[:40]
                lines.append(f"{status_icon} <b>{amount}</b> — {desc}\n    📅 {d.get('date','')}")
            text = "\n\n".join(lines)
        back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה"}, lang)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data=f"crm_contact_{contact_id}")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return CRM_VIEW

    async def deactivate_contact(self, update, context):
        query = update.callback_query
        await query.answer()
        contact_id = int(query.data.replace("crm_deactivate_", ""))
        db.deactivate_crm_contact(contact_id)
        text = _t(context, "🗑 Контакт деактивирован.", "🗑 Contact deactivated.", "🗑 איש הקשר הושבת.")
        back = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[get_lang(context)]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="back_to_menu")]])
        await query.edit_message_text(text, reply_markup=kb)
        return ConversationHandler.END

    # ── Add contact flow ───────────────────────────────────────────────────

    async def start_add(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["crm_draft"] = {}
        text = _t(context,
            "➕ <b>Новый контакт</b>\n\nШаг 1: Тип контакта",
            "➕ <b>New contact</b>\n\nStep 1: Contact type",
            "➕ <b>איש קשר חדש</b>\n\nשלב 1: סוג"
        )
        await query.edit_message_text(text, reply_markup=_contact_type_kb(context), parse_mode="HTML")
        return CRM_ADD_TYPE

    async def add_set_type(self, update, context):
        query = update.callback_query
        await query.answer()
        ctype = query.data.replace("crm_add_type_", "")
        context.user_data["crm_draft"]["contact_type"] = ctype
        lang = get_lang(context)
        type_name = CONTACT_TYPES.get(ctype, {}).get(lang, ctype)
        await query.edit_message_text(f"✅ {type_name}", parse_mode="HTML")
        text = _t(context,
            "Шаг 2: Введите имя или название компании:",
            "Step 2: Enter name or company name:",
            "שלב 2: הזן שם או שם חברה:"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context))
        return CRM_ADD_NAME

    async def add_set_name(self, update, context):
        name = update.message.text.strip()
        context.user_data["crm_draft"]["name"] = name
        await update.message.reply_text(f"✅ <b>{name}</b>", parse_mode="HTML")
        text = _t(context,
            "Шаг 3: Номер телефона:",
            "Step 3: Phone number:",
            "שלב 3: מספר טלפון:"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_skip_back_kb(context, "crm_skip_phone")
        )
        return CRM_ADD_PHONE

    async def add_back_to_name(self, update, context):
        query = update.callback_query
        await query.answer()
        text = _t(context, "Шаг 2: Введите имя:", "Step 2: Enter name:", "שלב 2: הזן שם:")
        await query.edit_message_text(text, reply_markup=_back_kb(context))
        return CRM_ADD_NAME

    async def add_set_phone(self, update, context):
        phone = update.message.text.strip()
        context.user_data["crm_draft"]["phone"] = phone
        await update.message.reply_text(f"✅ {phone}")
        text = _t(context,
            "Шаг 4: Telegram @username (или пропустите):",
            "Step 4: Telegram @username (or skip):",
            "שלב 4: Telegram @username (או דלג):"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_skip_back_kb(context, "crm_skip_telegram")
        )
        return CRM_ADD_TELEGRAM

    async def add_back_to_phone(self, update, context):
        query = update.callback_query
        await query.answer()
        text = _t(context, "Шаг 3: Номер телефона:", "Step 3: Phone:", "שלב 3: טלפון:")
        await query.edit_message_text(text, reply_markup=_skip_back_kb(context, "crm_skip_phone"))
        return CRM_ADD_PHONE

    async def add_set_telegram(self, update, context):
        tg = update.message.text.strip()
        context.user_data["crm_draft"]["telegram"] = tg
        await update.message.reply_text(f"✅ {tg}")
        return await self._ask_region(update, context)

    async def add_set_phone_skip(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["crm_draft"]["telegram"] = ""
        await query.edit_message_text("⏭")
        return await self._ask_region(update, context)

    async def add_back_to_telegram(self, update, context):
        query = update.callback_query
        await query.answer()
        text = _t(context, "Шаг 4: Telegram:", "Step 4: Telegram:", "שלב 4: Telegram:")
        await query.edit_message_text(text, reply_markup=_skip_back_kb(context, "crm_skip_telegram"))
        return CRM_ADD_TELEGRAM

    async def _ask_region(self, update, context):
        text = _t(context,
            "Шаг 5: Выберите регион:",
            "Step 5: Select region:",
            "שלב 5: בחר אזור:"
        )
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id, text=text,
            reply_markup=_region_kb(context, "crm_add_region")
        )
        return CRM_ADD_REGION

    async def add_set_region(self, update, context):
        query = update.callback_query
        await query.answer()
        region = query.data.replace("crm_add_region_", "")
        context.user_data["crm_draft"]["region"] = region
        lang = get_lang(context)
        if region == "all":
            context.user_data["crm_draft"]["city"] = ""
            await query.edit_message_text("✅ " + _L({"ru": "Вся страна", "en": "All country", "he": "כל הארץ"}, lang))
            return await self._ask_notes(update, context)
        region_name = REGIONS.get(region, {}).get(lang, region)
        await query.edit_message_text(f"✅ {region_name}")
        text = _t(context, "Шаг 6: Выберите город:", "Step 6: Select city:", "שלב 6: בחר עיר:")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_city_kb(context, region, "crm_add_city")
        )
        return CRM_ADD_CITY

    async def add_back_to_region(self, update, context):
        query = update.callback_query
        await query.answer()
        text = _t(context, "Шаг 5: Регион:", "Step 5: Region:", "שלב 5: אזור:")
        await query.edit_message_text(text, reply_markup=_region_kb(context, "crm_add_region"))
        return CRM_ADD_REGION

    async def add_set_city(self, update, context):
        query = update.callback_query
        await query.answer()
        city = query.data.replace("crm_add_city_", "")
        context.user_data["crm_draft"]["city"] = "" if city == "all" else city
        lang = get_lang(context)
        await query.edit_message_text(f"✅ {city}" if city != "all" else "✅ " + _L({"ru": "Весь район", "en": "All region", "he": "כל האזור"}, lang))
        return await self._ask_notes(update, context)

    async def add_back_to_city(self, update, context):
        query = update.callback_query
        await query.answer()
        region = context.user_data.get("crm_draft", {}).get("region", "center")
        text = _t(context, "Шаг 6: Город:", "Step 6: City:", "שלב 6: עיר:")
        await query.edit_message_text(text, reply_markup=_city_kb(context, region, "crm_add_city"))
        return CRM_ADD_CITY

    async def _ask_notes(self, update, context):
        text = _t(context,
            "Шаг 7: Заметка (специализация, особенности — или пропустите):",
            "Step 7: Notes (specialization, features — or skip):",
            "שלב 7: הערות (התמחות, מאפיינים — או דלג):"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_skip_back_kb(context, "crm_skip_notes")
        )
        return CRM_ADD_NOTES

    async def add_set_notes(self, update, context):
        notes = update.message.text.strip()
        context.user_data["crm_draft"]["notes"] = notes
        await update.message.reply_text(f"✅ {notes[:40]}")
        return await self._show_confirm(update, context)

    async def add_set_notes_skip(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["crm_draft"]["notes"] = ""
        await query.edit_message_text("⏭")
        return await self._show_confirm(update, context)

    async def _show_confirm(self, update, context):
        lang = get_lang(context)
        d = context.user_data.get("crm_draft", {})
        ctype = CONTACT_TYPES.get(d.get("contact_type", ""), {}).get(lang, "")
        region_key = d.get("region", "")
        region = REGIONS.get(region_key, {}).get(lang, region_key) if region_key not in ("all", "") else {"ru": "Вся страна", "en": "All country", "he": "כל הארץ"}.get(lang)
        city = d.get("city", "")
        location = city if city else region
        lines = [
            f"📋 <b>Новый контакт</b>",
            f"Тип: {ctype}",
            f"Имя: {d.get('name', '')}",
        ]
        if d.get("phone"): lines.append(f"Тел: {d['phone']}")
        if d.get("telegram"): lines.append(f"TG: {d['telegram']}")
        if location: lines.append(f"Регион: {location}")
        if d.get("notes"): lines.append(f"Заметка: {d['notes'][:60]}")
        text = "\n".join(lines)
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=_confirm_kb(context), parse_mode="HTML")
        return CRM_ADD_CONFIRM

    async def add_confirm(self, update, context):
        query = update.callback_query
        await query.answer()
        d = context.user_data.get("crm_draft", {})
        d["added_by"] = update.effective_user.id
        contact_id = db.add_crm_contact(d)
        text = _t(context,
            f"✅ Контакт сохранён (ID: #{contact_id})",
            f"✅ Contact saved (ID: #{contact_id})",
            f"✅ איש קשר נשמר (ID: #{contact_id})"
        )
        back = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[get_lang(context)]
        crm = {"ru": "👥 CRM", "en": "👥 CRM", "he": "👥 CRM"}[get_lang(context)]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(crm, callback_data="crm"),
            InlineKeyboardButton(back, callback_data="back_to_menu"),
        ]])
        await query.edit_message_text(text, reply_markup=kb)
        return ConversationHandler.END

    # ── Add deal flow ──────────────────────────────────────────────────────

    async def start_add_deal(self, update, context):
        query = update.callback_query
        await query.answer()
        contact_id = int(query.data.replace("crm_deal_new_", ""))
        context.user_data["crm_deal_draft"] = {"contact_id": contact_id}
        text = _t(context,
            "💼 <b>Новая сделка</b>\n\nВведите сумму сделки в ₪ (или 0 если неизвестна):",
            "💼 <b>New deal</b>\n\nEnter deal amount in ₪ (or 0 if unknown):",
            "💼 <b>עסקה חדשה</b>\n\nהזן סכום עסקה ב-₪ (או 0 אם לא ידוע):"
        )
        await query.edit_message_text(text, parse_mode="HTML")
        return CRM_ADD_DEAL

    async def add_deal_amount(self, update, context):
        text = update.message.text.strip().replace(",", "").replace(" ", "")
        try:
            amount = int(text)
        except:
            amount = 0
        context.user_data["crm_deal_draft"]["amount"] = amount
        await update.message.reply_text(f"✅ {amount:,} ₪")
        desc_text = _t(context,
            "Описание сделки (или пропустите):",
            "Deal description (or skip):",
            "תיאור עסקה (או דלג):"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=desc_text,
            reply_markup=_skip_back_kb(context, "crm_skip_desc")
        )
        return CRM_ADD_DEAL_DESC

    async def add_deal_desc(self, update, context):
        context.user_data["crm_deal_draft"]["description"] = update.message.text.strip()
        await update.message.reply_text("✅")
        return await self._ask_deal_status(update, context)

    async def add_deal_skip_desc(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["crm_deal_draft"]["description"] = ""
        await query.edit_message_text("⏭")
        return await self._ask_deal_status(update, context)

    async def _ask_deal_status(self, update, context):
        text = _t(context, "Статус сделки:", "Deal status:", "סטטוס עסקה:")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_deal_status_kb(context)
        )
        return CRM_ADD_DEAL_STATUS

    async def add_deal_status(self, update, context):
        query = update.callback_query
        await query.answer()
        status = query.data.replace("crm_deal_status_", "")
        context.user_data["crm_deal_draft"]["status"] = status
        lang = get_lang(context)
        status_name = DEAL_STATUSES.get(status, {}).get(lang, status)
        await query.edit_message_text(f"✅ {status_name}")
        d = context.user_data["crm_deal_draft"]
        desc = d.get("description", "") or "—"
        summary = f"💼 <b>Сделка</b>\nСумма: {d.get('amount', 0):,} ₪\nОписание: {desc[:50]}\nСтатус: {status_name}"
        yes = _L({"ru": "✅ Сохранить", "en": "✅ Save", "he": "✅ שמור"}, lang)
        no = _L({"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}, lang)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(yes, callback_data="crm_deal_save")],
            [InlineKeyboardButton(no, callback_data="back_to_menu")],
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=summary,
            reply_markup=kb, parse_mode="HTML"
        )
        return CRM_ADD_DEAL_CONFIRM

    async def save_deal(self, update, context):
        query = update.callback_query
        await query.answer()
        d = context.user_data.get("crm_deal_draft", {})
        d["created_by"] = update.effective_user.id
        deal_id = db.add_crm_deal(d)
        text = _t(context,
            f"✅ Сделка добавлена (#{deal_id})",
            f"✅ Deal added (#{deal_id})",
            f"✅ עסקה נוספה (#{deal_id})"
        )
        contact_id = d.get("contact_id")
        back_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("👤 К контакту", callback_data=f"crm_contact_{contact_id}"),
            InlineKeyboardButton("🏠 Меню", callback_data="back_to_menu"),
        ]])
        await query.edit_message_text(text, reply_markup=back_kb)
        return ConversationHandler.END

    # ── Add note flow ──────────────────────────────────────────────────────

    async def start_add_note(self, update, context):
        query = update.callback_query
        await query.answer()
        contact_id = int(query.data.replace("crm_note_", ""))
        context.user_data["crm"]["note_contact_id"] = contact_id
        text = _t(context,
            "📝 Введите заметку:",
            "📝 Enter note:",
            "📝 הזן הערה:"
        )
        back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="crm_back")]])
        await query.edit_message_text(text, reply_markup=kb)
        return CRM_ADD_NOTE

    async def save_note(self, update, context):
        text = update.message.text.strip()
        contact_id = context.user_data.get("crm", {}).get("note_contact_id")
        if contact_id:
            db.add_crm_note(contact_id, text, update.effective_user.id)
        lang = get_lang(context)
        done = _L({"ru": "✅ Заметка сохранена", "en": "✅ Note saved", "he": "✅ הערה נשמרה"}, lang)
        back_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("👤 К контакту", callback_data=f"crm_contact_{contact_id}"),
            InlineKeyboardButton("🏠 Меню", callback_data="back_to_menu"),
        ]])
        await update.message.reply_text(done, reply_markup=back_kb)
        return ConversationHandler.END

    # ── Cancel ─────────────────────────────────────────────────────────────

    async def cancel(self, update, context):
        from keyboards import main_menu_keyboard
        from formatters import format_welcome
        if update.callback_query:
            await update.callback_query.answer()
        if update.message:
            await update.message.reply_text(
                format_welcome(update.effective_user.first_name, context),
                reply_markup=main_menu_keyboard(context),
                parse_mode="HTML",
            )
        return ConversationHandler.END
