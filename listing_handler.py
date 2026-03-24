from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from i18n import t, get_lang
from city_translations import get_city_name
from keyboards import DISTRICT_CITIES, DISTRICT_KEYS, get_district_name, paywall_keyboard
import database as db
from subscription import has_access, is_trial_active
import upload_handler as uploader

# States
(
    ADD_SELLER_TYPE,
    ADD_UPLOAD_FILE,
    ADD_DEAL_TYPE, ADD_PROPERTY_TYPE, ADD_DISTRICT, ADD_CITY,
    ADD_ADDRESS,
    ADD_ROOMS, ADD_FLOOR, ADD_AREA, ADD_PRICE,
    ADD_PARKING, ADD_POOL, ADD_SHELTER, ADD_ELEVATOR,
    ADD_INFRASTRUCTURE, ADD_DESCRIPTION, ADD_NAME, ADD_PHONE, ADD_CONTACT, ADD_PHOTOS, ADD_CONFIRM
) = range(22)

PROPERTY_TYPES = {
    "apartment": {"ru": "🏢 Квартира", "en": "🏢 Apartment", "he": "🏢 דירה"},
    "house": {"ru": "🏠 Дом", "en": "🏠 House", "he": "🏠 בית"},
    "villa": {"ru": "🏡 Вилла", "en": "🏡 Villa", "he": "🏡 וילה"},
    "penthouse": {"ru": "🌆 Пентхаус", "en": "🌆 Penthouse", "he": "🌆 פנטהאוס"},
    "studio": {"ru": "🛋 Студия", "en": "🛋 Studio", "he": "🛋 סטודיו"},
    "duplex": {"ru": "🏘 Дуплекс", "en": "🏘 Duplex", "he": "🏘 דופלקס"},
}

COMMERCIAL_TYPES = {
    "office": {"ru": "🏢 Офис", "en": "🏢 Office", "he": "🏢 משרד"},
    "retail": {"ru": "🏪 Магазин/Ретейл", "en": "🏪 Shop/Retail", "he": "🏪 חנות/קמעונאות"},
    "warehouse": {"ru": "🏭 Склад", "en": "🏭 Warehouse", "he": "🏭 מחסן"},
    "coworking": {"ru": "💼 Коворкинг", "en": "💼 Coworking", "he": "💼 קוורקינג"},
    "restaurant_space": {"ru": "🍽 Кафе/Ресторан", "en": "🍽 Cafe/Restaurant", "he": "🍽 קפה/מסעדה"},
    "other_commercial": {"ru": "🏗 Другое", "en": "🏗 Other", "he": "🏗 אחר"},
}

COMMERCIAL_KEYS = list(COMMERCIAL_TYPES.keys())

INFRA_KEYS_ADD = [
    "school", "kindergarten", "transport", "mall",
    "park", "gym", "beach", "restaurant", "synagogue"
]

def _t(context, ru, en, he):
    lang = get_lang(context)
    return {"ru": ru, "en": en, "he": he}.get(lang, ru)

def _confirmed(context, ru, en, he, value):
    label = _t(context, ru, en, he)
    return f"✅ <b>{label}:</b> {value}"

def _seller_type_keyboard(ctx):
    lang = get_lang(ctx)
    agent   = {"ru": "🏢 Агент / Риелтор", "en": "🏢 Agent / Realtor", "he": "🏢 סוכן / מתווך"}[lang]
    private = {"ru": "👤 Частное лицо",     "en": "👤 Private person",  "he": "👤 אדם פרטי"}[lang]
    menu    = {"ru": "🏠 Главное меню",      "en": "🏠 Main menu",       "he": "🏠 תפריט ראשי"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(agent,   callback_data="add_seller_agent")],
        [InlineKeyboardButton(private, callback_data="add_seller_private")],
        [InlineKeyboardButton(menu,    callback_data="back_to_menu")],
    ])


def _agent_method_keyboard(ctx):
    """After agent is selected: choose manual entry or CSV upload."""
    lang = get_lang(ctx)
    manual   = {"ru": "✍️ Добавить вручную",      "en": "✍️ Add manually",      "he": "✍️ הוסף ידנית"}[lang]
    upload   = {"ru": "📤 Загрузить CSV/XLSX",    "en": "📤 Upload CSV/XLSX",    "he": "📤 העלה CSV/XLSX"}[lang]
    template = {"ru": "📄 Скачать шаблон",         "en": "📄 Download template",  "he": "📄 הורד תבנית"}[lang]
    back     = {"ru": "« Назад",                   "en": "« Back",               "he": "« חזרה"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(manual,   callback_data="add_agent_manual")],
        [InlineKeyboardButton(upload,   callback_data="add_agent_upload")],
        [InlineKeyboardButton(template, callback_data="add_agent_template")],
        [InlineKeyboardButton(back,     callback_data="add_agent_back")],
    ])


def _deal_keyboard(ctx):
    lang = get_lang(ctx)
    rent = {"ru": "🔑 Аренда", "en": "🔑 Rent", "he": "🔑 השכרה"}[lang]
    buy = {"ru": "💰 Продажа", "en": "💰 Sale", "he": "💰 מכירה"}[lang]
    sublet = {"ru": "🔄 Сублет", "en": "🔄 Sublet", "he": "🔄 סאבלט"}[lang]
    commercial = {"ru": "🏢 Коммерческая", "en": "🏢 Commercial", "he": "🏢 מסחרי"}[lang]
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    menu = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(rent, callback_data="add_deal_rent"),
         InlineKeyboardButton(buy, callback_data="add_deal_buy")],
        [InlineKeyboardButton(sublet, callback_data="add_deal_sublet"),
         InlineKeyboardButton(commercial, callback_data="add_deal_commercial")],
        [InlineKeyboardButton(back, callback_data="back_to_menu"),
         InlineKeyboardButton(menu, callback_data="back_to_menu")],
    ])

def _ptype_keyboard(ctx):
    lang = get_lang(ctx)
    buttons = []
    row = []
    for key, names in PROPERTY_TYPES.items():
        row.append(InlineKeyboardButton(names[lang], callback_data=f"add_ptype_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _comm_type_keyboard(ctx):
    lang = get_lang(ctx)
    buttons = []
    row = []
    for key, names in COMMERCIAL_TYPES.items():
        row.append(InlineKeyboardButton(names[lang], callback_data=f"add_ptype_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _district_keyboard(ctx):
    lang = get_lang(ctx)
    buttons = [[InlineKeyboardButton(get_district_name(k, lang), callback_data=f"add_dist_{k}")] for k in DISTRICT_KEYS]
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _city_keyboard(ctx, district):
    lang = get_lang(ctx)
    cities = DISTRICT_CITIES.get(district, [])
    buttons = []
    row = []
    for city in cities:
        row.append(InlineKeyboardButton(get_city_name(city, lang), callback_data=f"add_city_{city}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _rooms_keyboard(ctx):
    lang = get_lang(ctx)
    rooms = ["1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5", "5+"]
    buttons = []
    row = []
    for r in rooms:
        row.append(InlineKeyboardButton(r, callback_data=f"add_rooms_{r}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _yes_no_keyboard(ctx, prefix):
    lang = get_lang(ctx)
    yes = {"ru": "✅ Есть", "en": "✅ Yes", "he": "✅ יש"}[lang]
    no = {"ru": "❌ Нет", "en": "❌ No", "he": "❌ אין"}[lang]
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes, callback_data=f"{prefix}_yes"),
         InlineKeyboardButton(no, callback_data=f"{prefix}_no")],
        [InlineKeyboardButton(back, callback_data="add_back")],
    ])

def _shelter_keyboard(ctx):
    lang = get_lang(ctx)
    opts = {
        "mamad": {"ru": "🛡 Мамад", "en": "🛡 Mamad", "he": "🛡 ממ\"ד"},
        "miklat": {"ru": "🏗 Миклат", "en": "🏗 Miklat", "he": "🏗 מקלט"},
        "none": {"ru": "❌ Нет", "en": "❌ None", "he": "❌ אין"},
    }
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(opts["mamad"][lang], callback_data="add_shelter_mamad"),
         InlineKeyboardButton(opts["miklat"][lang], callback_data="add_shelter_miklat")],
        [InlineKeyboardButton(opts["none"][lang], callback_data="add_shelter_none")],
        [InlineKeyboardButton(back, callback_data="add_back")],
    ])

def _infra_keyboard(ctx, selected=None):
    if selected is None:
        selected = []
    lang = get_lang(ctx)
    infra_names = {
        "school": {"ru": "🏫 Школа", "en": "🏫 School", "he": "🏫 בית ספר"},
        "kindergarten": {"ru": "🎠 Садик", "en": "🎠 Kindergarten", "he": "🎠 גן ילדים"},
        "transport": {"ru": "🚌 Транспорт", "en": "🚌 Transport", "he": "🚌 תחבורה"},
        "mall": {"ru": "🛍 Торг.центр", "en": "🛍 Mall", "he": "🛍 קניון"},
        "park": {"ru": "🌳 Парк", "en": "🌳 Park", "he": "🌳 פארק"},
        "gym": {"ru": "💪 Спортзал", "en": "💪 Gym", "he": "💪 חדר כושר"},
        "beach": {"ru": "🏖 Пляж", "en": "🏖 Beach", "he": "🏖 חוף"},
        "restaurant": {"ru": "🍽 Рестораны", "en": "🍽 Restaurants", "he": "🍽 מסעדות"},
        "synagogue": {"ru": "✡️ Синагога", "en": "✡️ Synagogue", "he": "✡️ בית כנסת"},
    }
    done = {"ru": "✅ Готово", "en": "✅ Done", "he": "✅ סיום"}[lang]
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    buttons = []
    row = []
    for key in INFRA_KEYS_ADD:
        name = infra_names[key][lang]
        mark = "✅ " if key in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{name}", callback_data=f"add_infra_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton(back, callback_data="add_back"),
        InlineKeyboardButton(done, callback_data="add_infra_done"),
    ])
    return InlineKeyboardMarkup(buttons)

def _photos_keyboard(ctx, count):
    lang = get_lang(ctx)
    if count:
        label = {"ru": f"✅ Готово ({count} фото)", "en": f"✅ Done ({count} photos)", "he": f"✅ סיום ({count} תמונות)"}[lang]
    else:
        label = {"ru": "⏭ Пропустить", "en": "⏭ Skip", "he": "⏭ דלג"}[lang]
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    menu = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="add_photos_done")],
        [InlineKeyboardButton(back, callback_data="add_back"),
         InlineKeyboardButton(menu, callback_data="back_to_menu")],
    ])


def _confirm_keyboard(ctx):
    lang = get_lang(ctx)
    publish = {"ru": "✅ Опубликовать", "en": "✅ Publish", "he": "✅ פרסם"}[lang]
    cancel = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}[lang]
    menu = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(publish, callback_data="add_confirm_yes")],
        [InlineKeyboardButton(cancel, callback_data="add_confirm_no")],
        [InlineKeyboardButton(menu, callback_data="back_to_menu")],
    ])

def _step_text(ctx, ru, en, he):
    lang = get_lang(ctx)
    return {"ru": ru, "en": en, "he": he}.get(lang, ru)

def _back_kb(ctx):
    lang = get_lang(ctx)
    back = {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[lang]
    menu = {"ru": "🏠 Главное меню", "en": "🏠 Main menu", "he": "🏠 תפריט ראשי"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(back, callback_data="add_back"),
         InlineKeyboardButton(menu, callback_data="back_to_menu")],
    ])


class ListingHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("add", self.start_add),
                CallbackQueryHandler(self.start_add, pattern="^add_listing$"),
            ],
            states={
                ADD_SELLER_TYPE: [
                    CallbackQueryHandler(self.handle_seller_type, pattern="^add_seller_"),
                    CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                ],
                ADD_UPLOAD_FILE: [
                    CallbackQueryHandler(self.handle_agent_method, pattern="^add_agent_"),
                    MessageHandler(filters.Document.ALL, self.handle_upload_document),
                ],
                ADD_DEAL_TYPE: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_deal, pattern="^add_deal_"),
                    CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                ],
                ADD_PROPERTY_TYPE: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_ptype, pattern="^add_ptype_"),
                ],
                ADD_DISTRICT: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_district, pattern="^add_dist_"),
                ],
                ADD_CITY: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_city, pattern="^add_city_"),
                ],
                ADD_ADDRESS: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_address),
                ],
                ADD_ROOMS: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_rooms, pattern="^add_rooms_"),
                ],
                ADD_FLOOR: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_floor),
                ],
                ADD_AREA: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_area),
                ],
                ADD_PRICE: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_price),
                ],
                ADD_PARKING: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_parking, pattern="^add_parking_"),
                ],
                ADD_POOL: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_pool, pattern="^add_pool_"),
                ],
                ADD_SHELTER: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_shelter, pattern="^add_shelter_"),
                ],
                ADD_ELEVATOR: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_elevator, pattern="^add_elevator_"),
                ],
                ADD_INFRASTRUCTURE: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_infra, pattern="^add_infra_"),
                ],
                ADD_DESCRIPTION: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_description),
                ],
                ADD_NAME: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_name),
                ],
                ADD_PHONE: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_phone),
                ],
                ADD_CONTACT: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_contact),
                ],
                ADD_PHOTOS: [
                    MessageHandler(filters.PHOTO, self.handle_photo_message),
                    CallbackQueryHandler(self.handle_photos_done, pattern="^add_photos_done$"),
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                ],
                ADD_CONFIRM: [
                    CallbackQueryHandler(self.handle_confirm, pattern="^add_confirm_"),
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                ],
            },
            fallbacks=[
                CommandHandler("start", self.cancel),
                CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
            ],
            per_message=False,
            allow_reentry=True,
        )

    async def start_add(self, update, context):
        user_id = update.effective_user.id
        # Block adding listings after trial ends for non-subscribers
        if not is_trial_active() and not has_access(user_id):
            lang = get_lang(context)
            paywall_text = {
                "ru": (
                    "🔒 <b>Тестовый период завершён</b>\n\n"
                    "Добавление объявлений доступно только по подписке.\n\n"
                    "• 1 неделя — 19.90 ₪\n"
                    "• 2 недели — 29.90 ₪ ⭐\n"
                    "• 1 месяц — 39.90 ₪\n"
                    "• 🔔 Подписка на поиск — 39.90 ₪/мес"
                ),
                "en": (
                    "🔒 <b>Trial period ended</b>\n\n"
                    "Adding listings requires an active subscription.\n\n"
                    "• 1 week — ₪19.90\n"
                    "• 2 weeks — ₪29.90 ⭐\n"
                    "• 1 month — ₪39.90\n"
                    "• 🔔 Search alerts — ₪39.90/mo"
                ),
                "he": (
                    "🔒 <b>תקופת הניסיון הסתיימה</b>\n\n"
                    "הוספת מודעות זמינה רק עם מנוי פעיל.\n\n"
                    "• שבוע — ₪19.90\n"
                    "• 2 שבועות — ₪29.90 ⭐\n"
                    "• חודש — ₪39.90\n"
                    "• 🔔 התראות חיפוש — ₪39.90/חודש"
                ),
            }.get(lang, "")
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(paywall_text, reply_markup=paywall_keyboard(context), parse_mode="HTML")
            else:
                await update.message.reply_text(paywall_text, reply_markup=paywall_keyboard(context), parse_mode="HTML")
            return ConversationHandler.END

        context.user_data["add_listing"] = {}
        context.user_data["add_state"] = ADD_SELLER_TYPE
        text = _step_text(context,
            "🏠 Добавление объявления\n\nШаг 1/16: Кто размещает объявление?",
            "🏠 Add listing\n\nStep 1/16: Who is posting the listing?",
            "🏠 הוספת מודעה\n\nשלב 1/16: מי מפרסם את המודעה?"
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=_seller_type_keyboard(context), parse_mode="HTML")
        else:
            await update.message.reply_text(text, reply_markup=_seller_type_keyboard(context), parse_mode="HTML")
        return ADD_SELLER_TYPE

    async def handle_seller_type(self, update, context):
        query = update.callback_query
        await query.answer()
        seller_type = query.data.replace("add_seller_", "")  # "agent" or "private"
        context.user_data["add_listing"]["seller_type"] = seller_type
        lang = get_lang(context)

        if seller_type == "agent":
            # Agent gets extra choice: manual or CSV upload
            text = _step_text(context,
                "🏢 Агент / Риелтор\n\nКак хотите добавить объявления?",
                "🏢 Agent / Realtor\n\nHow would you like to add listings?",
                "🏢 סוכן / מתווך\n\nכיצד תרצה להוסיף מודעות?"
            )
            await query.edit_message_text(text, reply_markup=_agent_method_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_UPLOAD_FILE
            return ADD_UPLOAD_FILE

        # Private person — go straight to deal type
        label = {"ru": "👤 Частное лицо", "en": "👤 Private person", "he": "👤 אדם פרטי"}[lang]
        await query.edit_message_text(
            _confirmed(context, "Тип продавца", "Seller type", "סוג המוכר", label),
            parse_mode="HTML"
        )
        context.user_data["add_state"] = ADD_DEAL_TYPE
        text = _step_text(context, "Шаг 2/16: Тип сделки", "Step 2/16: Deal type", "שלב 2/16: סוג עסקה")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_deal_keyboard(context), parse_mode="HTML"
        )
        return ADD_DEAL_TYPE

    async def handle_agent_method(self, update, context):
        query = update.callback_query
        await query.answer()
        action = query.data  # add_agent_manual | add_agent_upload | add_agent_template | add_agent_back

        if action == "add_agent_back":
            # Back to seller type selection
            text = _step_text(context,
                "Шаг 1/16: Кто размещает объявление?",
                "Step 1/16: Who is posting the listing?",
                "שלב 1/16: מי מפרסם את המודעה?"
            )
            await query.edit_message_text(text, reply_markup=_seller_type_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_SELLER_TYPE
            return ADD_SELLER_TYPE

        if action == "add_agent_template":
            # Send CSV template file
            csv_bytes = uploader.generate_template_bytes()
            await query.edit_message_text(
                _step_text(context,
                    "📄 Шаблон отправлен. Заполните все колонки и загрузите файл.",
                    "📄 Template sent. Fill all columns and upload the file.",
                    "📄 התבנית נשלחה. מלא את כל העמודות והעלה את הקובץ."
                ),
                reply_markup=_agent_method_keyboard(context), parse_mode="HTML"
            )
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=csv_bytes,
                filename="flatfinder_template.csv",
                caption=uploader.COLUMN_HINTS,
            )
            return ADD_UPLOAD_FILE

        if action == "add_agent_upload":
            lang = get_lang(context)
            prompt = {
                "ru": (
                    "📤 <b>Загрузка объявлений из файла</b>\n\n"
                    "Отправьте файл <b>CSV</b> или <b>XLSX</b>.\n"
                    "Все колонки обязательны — файл с пропусками не принимается.\n\n"
                    "Если у вас нет шаблона — нажмите «📄 Скачать шаблон»."
                ),
                "en": (
                    "📤 <b>Bulk listing upload</b>\n\n"
                    "Send a <b>CSV</b> or <b>XLSX</b> file.\n"
                    "All columns are required — incomplete files are rejected.\n\n"
                    "No template? Press «📄 Download template»."
                ),
                "he": (
                    "📤 <b>העלאת מודעות מקובץ</b>\n\n"
                    "שלח קובץ <b>CSV</b> או <b>XLSX</b>.\n"
                    "כל העמודות חובה — קבצים עם חוסרים נדחים.\n\n"
                    "אין תבנית? לחץ «📄 הורד תבנית»."
                ),
            }[lang]
            await query.edit_message_text(prompt, reply_markup=_agent_method_keyboard(context), parse_mode="HTML")
            return ADD_UPLOAD_FILE

        if action == "add_agent_manual":
            lang = get_lang(context)
            label = {"ru": "🏢 Агент / Риелтор", "en": "🏢 Agent / Realtor", "he": "🏢 סוכן / מתווך"}[lang]
            await query.edit_message_text(
                _confirmed(context, "Тип продавца", "Seller type", "סוג המוכר", label),
                parse_mode="HTML"
            )
            context.user_data["add_state"] = ADD_DEAL_TYPE
            text = _step_text(context, "Шаг 2/16: Тип сделки", "Step 2/16: Deal type", "שלב 2/16: סוג עסקה")
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=text,
                reply_markup=_deal_keyboard(context), parse_mode="HTML"
            )
            return ADD_DEAL_TYPE

    async def handle_upload_document(self, update, context):
        """Process uploaded CSV or XLSX file."""
        lang = get_lang(context)
        doc = update.message.document
        fname = doc.file_name or ""

        if not (fname.lower().endswith(".csv") or fname.lower().endswith(".xlsx")):
            await update.message.reply_text(
                {"ru": "❌ Отправьте файл CSV или XLSX.",
                 "en": "❌ Please send a CSV or XLSX file.",
                 "he": "❌ שלח קובץ CSV או XLSX."}[lang],
                reply_markup=_agent_method_keyboard(context)
            )
            return ADD_UPLOAD_FILE

        # Download file
        try:
            file_obj = await context.bot.get_file(doc.file_id)
            file_bytes = await file_obj.download_as_bytearray()
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка загрузки файла: {e}")
            return ADD_UPLOAD_FILE

        user_id = update.effective_user.id
        result = uploader.validate_and_import(bytes(file_bytes), fname, user_id)

        if not result["ok"]:
            errors = result["errors"]
            max_show = 10
            shown = errors[:max_show]
            tail = f"\n... и ещё {len(errors) - max_show} ошибок" if len(errors) > max_show else ""
            err_text = {
                "ru": f"❌ <b>Файл не принят</b>\n\n" + "\n".join(shown) + tail + "\n\nИсправьте ошибки и загрузите снова.",
                "en": f"❌ <b>File rejected</b>\n\n" + "\n".join(shown) + tail + "\n\nFix the errors and re-upload.",
                "he": f"❌ <b>הקובץ נדחה</b>\n\n" + "\n".join(shown) + tail + "\n\nתקן את השגיאות ושלח שוב.",
            }[lang]
            await update.message.reply_text(err_text, reply_markup=_agent_method_keyboard(context), parse_mode="HTML")
            return ADD_UPLOAD_FILE

        n = result["imported"]
        ok_text = {
            "ru": f"✅ <b>Загружено {n} объявлений!</b>\n\nОни уже доступны в поиске.",
            "en": f"✅ <b>{n} listings imported!</b>\n\nThey are now visible in search.",
            "he": f"✅ <b>{n} מודעות הועלו!</b>\n\nהן כבר זמינות בחיפוש.",
        }[lang]
        await update.message.reply_text(ok_text, parse_mode="HTML")
        return ConversationHandler.END

    async def handle_back(self, update, context):
        query = update.callback_query
        await query.answer()
        state = context.user_data.get("add_state", ADD_DEAL_TYPE)

        if state == ADD_DEAL_TYPE:
            text = _step_text(context,
                "Шаг 1/16: Кто размещает объявление?",
                "Step 1/16: Who is posting the listing?",
                "שלב 1/16: מי מפרסם את המודעה?"
            )
            await query.edit_message_text(text, reply_markup=_seller_type_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_SELLER_TYPE
            return ADD_SELLER_TYPE
        elif state == ADD_PROPERTY_TYPE:
            text = _step_text(context, "Шаг 2/16: Тип сделки", "Step 2/16: Deal type", "שלב 2/16: סוג עסקה")
            await query.edit_message_text(text, reply_markup=_deal_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_DEAL_TYPE
            return ADD_DEAL_TYPE
        elif state == ADD_DISTRICT:
            text = _step_text(context, "Шаг 3/16: Тип жилья", "Step 3/16: Property type", "שלב 3/16: סוג נכס")
            await query.edit_message_text(text, reply_markup=_ptype_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_PROPERTY_TYPE
            return ADD_PROPERTY_TYPE
        elif state == ADD_CITY:
            text = _step_text(context, "Шаг 4/16: Округ", "Step 4/16: District", "שלב 4/16: מחוז")
            await query.edit_message_text(text, reply_markup=_district_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_DISTRICT
            return ADD_DISTRICT
        elif state == ADD_ADDRESS:
            district = context.user_data["add_listing"].get("district", "tel_aviv")
            text = _step_text(context, "Шаг 5/16: Город", "Step 5/16: City", "שלב 5/16: עיר")
            await query.edit_message_text(text, reply_markup=_city_keyboard(context, district), parse_mode="HTML")
            context.user_data["add_state"] = ADD_CITY
            return ADD_CITY
        elif state == ADD_ROOMS:
            text = _step_text(context,
                "📍 Шаг 6/16: Адрес\n\nВведите улицу и номер дома.\nПример: <i>ул. Дизенгоф, 99</i>",
                "📍 Step 6/16: Address\n\nEnter street and house number.\nExample: <i>Dizengoff St, 99</i>",
                "📍 שלב 6/16: כתובת\n\nהזן את שם הרחוב ומספר הבית.\nדוגמה: <i>דיזנגוף 99</i>"
            )
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_ADDRESS
            return ADD_ADDRESS
        elif state == ADD_FLOOR:
            text = _step_text(context, "Шаг 7/16: Количество комнат", "Step 7/16: Number of rooms", "שלב 7/16: מספר חדרים")
            await query.edit_message_text(text, reply_markup=_rooms_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_ROOMS
            return ADD_ROOMS
        elif state == ADD_AREA:
            text = _step_text(context, "Шаг 8/16: Этаж", "Step 8/16: Floor", "שלב 8/16: קומה")
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_FLOOR
            return ADD_FLOOR
        elif state == ADD_PRICE:
            text = _step_text(context, "Шаг 9/16: Площадь (кв.м)", "Step 9/16: Area (sqm)", "שלב 9/16: שטח (מ\"ר)")
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_AREA
            return ADD_AREA
        elif state == ADD_PARKING:
            deal = context.user_data["add_listing"].get("deal_type", "rent")
            price_text = _step_text(context,
                f"Шаг 10/16: Цена ({'₪/мес' if deal=='rent' else '₪'})",
                f"Step 10/16: Price ({'₪/mo' if deal=='rent' else '₪'})",
                f"שלב 10/16: מחיר ({'₪/חודש' if deal=='rent' else '₪'})"
            )
            await query.edit_message_text(price_text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_PRICE
            return ADD_PRICE
        elif state == ADD_POOL:
            text = _step_text(context, "Шаг 11/16: Парковка", "Step 11/16: Parking", "שלב 11/16: חניה")
            await query.edit_message_text(text, reply_markup=_yes_no_keyboard(context, "add_parking"), parse_mode="HTML")
            context.user_data["add_state"] = ADD_PARKING
            return ADD_PARKING
        elif state == ADD_SHELTER:
            text = _step_text(context, "Шаг 12/16: Бассейн", "Step 12/16: Pool", "שלב 12/16: בריכה")
            await query.edit_message_text(text, reply_markup=_yes_no_keyboard(context, "add_pool"), parse_mode="HTML")
            context.user_data["add_state"] = ADD_POOL
            return ADD_POOL
        elif state == ADD_ELEVATOR:
            text = _step_text(context, "Шаг 13/16: Мамад/Миклат", "Step 13/16: Mamad/Miklat", "שלב 13/16: ממ\"ד/מקלט")
            await query.edit_message_text(text, reply_markup=_shelter_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_SHELTER
            return ADD_SHELTER
        elif state == ADD_INFRASTRUCTURE:
            text = _step_text(context, "Шаг 14/16: Лифт", "Step 14/16: Elevator", "שלב 14/16: מעלית")
            await query.edit_message_text(text, reply_markup=_yes_no_keyboard(context, "add_elevator"), parse_mode="HTML")
            context.user_data["add_state"] = ADD_ELEVATOR
            return ADD_ELEVATOR
        elif state == ADD_DESCRIPTION:
            selected = context.user_data["add_listing"].get("infrastructure", [])
            text = _step_text(context, "Шаг 15/16: Инфраструктура", "Step 15/16: Infrastructure", "שלב 15/16: תשתיות")
            await query.edit_message_text(text, reply_markup=_infra_keyboard(context, selected), parse_mode="HTML")
            context.user_data["add_state"] = ADD_INFRASTRUCTURE
            return ADD_INFRASTRUCTURE
        elif state == ADD_NAME:
            text = _step_text(context, "Шаг 16/16: Описание", "Step 16/16: Description", "שלב 16/16: תיאור")
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_DESCRIPTION
            return ADD_DESCRIPTION
        elif state == ADD_PHONE:
            text = _step_text(context,
                "Ваше имя\n\nВведите ваше имя:",
                "Your name\n\nEnter your name:",
                "השם שלך\n\nהזן את שמך:"
            )
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_NAME
            return ADD_NAME
        elif state == ADD_CONTACT:
            text = _step_text(context,
                "Номер телефона\n\nВведите ваш номер телефона:",
                "Phone number\n\nEnter your phone number:",
                "מספר טלפון\n\nהזן את מספר הטלפון שלך:"
            )
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_PHONE
            return ADD_PHONE
        elif state == ADD_PHOTOS:
            text = _step_text(context,
                "Контактная информация\n\nВведите ваш Telegram @username или дополнительный контакт:",
                "Contact information\n\nEnter your Telegram @username or additional contact:",
                "פרטי קשר\n\nהזן את ה-Telegram @username או פרטי קשר נוספים:"
            )
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_CONTACT
            return ADD_CONTACT
        return ConversationHandler.END

    async def handle_deal(self, update, context):
        query = update.callback_query
        await query.answer()
        deal = query.data.replace("add_deal_", "")
        context.user_data["add_listing"]["deal_type"] = deal
        context.user_data["add_state"] = ADD_PROPERTY_TYPE
        deal_labels = {
            "rent": {"ru": "Аренда", "en": "Rent", "he": "השכרה"},
            "buy": {"ru": "Продажа", "en": "Sale", "he": "מכירה"},
            "sublet": {"ru": "Сублет", "en": "Sublet", "he": "סאבלט"},
            "commercial": {"ru": "Коммерческая", "en": "Commercial", "he": "מסחרי"},
        }
        lang = get_lang(context)
        deal_label = deal_labels.get(deal, deal_labels["rent"])[lang]
        await query.edit_message_text(_confirmed(context, "Тип сделки", "Deal type", "סוג עסקה", deal_label), parse_mode="HTML")
        if deal == "commercial":
            text = _step_text(context, "Шаг 3/16: Тип помещения", "Step 3/16: Property type", "שלב 3/16: סוג נכס")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_comm_type_keyboard(context), parse_mode="HTML")
        else:
            text = _step_text(context, "Шаг 3/16: Тип жилья", "Step 3/16: Property type", "שלב 3/16: סוג נכס")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_ptype_keyboard(context), parse_mode="HTML")
        return ADD_PROPERTY_TYPE

    async def handle_ptype(self, update, context):
        query = update.callback_query
        await query.answer()
        ptype = query.data.replace("add_ptype_", "")
        context.user_data["add_listing"]["property_type"] = ptype
        context.user_data["add_state"] = ADD_DISTRICT
        lang = get_lang(context)
        all_types = {**PROPERTY_TYPES, **COMMERCIAL_TYPES}
        ptype_label = all_types.get(ptype, {}).get(lang, ptype)
        label_key = "Тип помещения" if ptype in COMMERCIAL_KEYS else "Тип жилья"
        await query.edit_message_text(_confirmed(context, label_key, "Property type", "סוג נכס", ptype_label), parse_mode="HTML")
        text = _step_text(context, "Шаг 4/16: Округ", "Step 4/16: District", "שלב 4/16: מחוז")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_district_keyboard(context), parse_mode="HTML")
        return ADD_DISTRICT

    async def handle_district(self, update, context):
        query = update.callback_query
        await query.answer()
        district = query.data.replace("add_dist_", "")
        context.user_data["add_listing"]["district"] = district
        context.user_data["add_state"] = ADD_CITY
        lang = get_lang(context)
        dist_label = get_district_name(district, lang)
        await query.edit_message_text(_confirmed(context, "Округ", "District", "מחוז", dist_label), parse_mode="HTML")
        text = _step_text(context, "Шаг 5/16: Город", "Step 5/16: City", "שלב 5/16: עיר")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_city_keyboard(context, district), parse_mode="HTML")
        return ADD_CITY

    async def handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        city = query.data.replace("add_city_", "")
        context.user_data["add_listing"]["city"] = city
        lang = get_lang(context)
        city_label = get_city_name(city, lang)
        await query.edit_message_text(_confirmed(context, "Город", "City", "עיר", city_label), parse_mode="HTML")
        context.user_data["add_state"] = ADD_ADDRESS
        text = _step_text(context,
            "📍 Шаг 6/16: Адрес\n\nВведите улицу и номер дома.\nПример: <i>ул. Дизенгоф, 99</i>",
            "📍 Step 6/16: Address\n\nEnter street and house number.\nExample: <i>Dizengoff St, 99</i>",
            "📍 שלב 6/16: כתובת\n\nהזן את שם הרחוב ומספר הבית.\nדוגמה: <i>דיזנגוף 99</i>"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_ADDRESS

    async def handle_address(self, update, context):
        import urllib.parse
        address = update.message.text.strip()
        city = context.user_data["add_listing"].get("city", "")
        context.user_data["add_listing"]["address"] = address

        # Build Google Maps link: city + address + Israel
        query_str = urllib.parse.quote(f"{address}, {city}, Israel")
        map_url = f"https://maps.google.com/?q={query_str}"
        context.user_data["add_listing"]["map_url"] = map_url

        lang = get_lang(context)
        map_label = {"ru": "🗺 Посмотреть на карте", "en": "🗺 View on map", "he": "🗺 הצג במפה"}.get(lang, "🗺 Map")
        confirmed_text = _confirmed(context, "Адрес", "Address", "כתובת", address)
        await update.message.reply_text(
            f"{confirmed_text}\n\n<a href=\"{map_url}\">{map_label}</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        ptype = context.user_data["add_listing"].get("property_type", "")
        # Skip rooms for commercial listings
        if ptype in COMMERCIAL_KEYS:
            context.user_data["add_listing"]["rooms"] = "0"
            context.user_data["add_state"] = ADD_FLOOR
            text = _step_text(context,
                "Шаг 7/16: Этаж\n\nВведите номер этажа (например: 1)",
                "Step 7/16: Floor\n\nEnter floor number (e.g.: 1)",
                "שלב 7/16: קומה\n\nהזן מספר קומה (לדוגמה: 1)"
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
            return ADD_FLOOR
        context.user_data["add_state"] = ADD_ROOMS
        text = _step_text(context, "Шаг 7/16: Количество комнат", "Step 7/16: Number of rooms", "שלב 7/16: מספר חדרים")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_rooms_keyboard(context), parse_mode="HTML")
        return ADD_ROOMS

    async def handle_rooms(self, update, context):
        query = update.callback_query
        await query.answer()
        rooms = query.data.replace("add_rooms_", "")
        context.user_data["add_listing"]["rooms"] = rooms
        context.user_data["add_state"] = ADD_FLOOR
        await query.edit_message_text(_confirmed(context, "Комнат", "Rooms", "חדרים", rooms), parse_mode="HTML")
        text = _step_text(context,
            "Шаг 8/16: Этаж\n\nВведите номер этажа (например: 3)",
            "Step 8/16: Floor\n\nEnter floor number (e.g.: 3)",
            "שלב 8/16: קומה\n\nהזן מספר קומה (לדוגמה: 3)"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_FLOOR

    async def handle_floor(self, update, context):
        floor = update.message.text.strip()
        context.user_data["add_listing"]["floor"] = floor
        context.user_data["add_state"] = ADD_AREA
        await update.message.reply_text(_confirmed(context, "Этаж", "Floor", "קומה", floor), parse_mode="HTML")
        text = _step_text(context,
            "Шаг 9/16: Площадь\n\nВведите площадь в кв.м (например: 85)",
            "Step 9/16: Area\n\nEnter area in sqm (e.g.: 85)",
            "שלב 9/16: שטח\n\nהזן שטח במ\"ר (לדוגמה: 85)"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_AREA

    async def handle_area(self, update, context):
        area = update.message.text.strip()
        try:
            context.user_data["add_listing"]["area_sqm"] = int(area)
        except:
            context.user_data["add_listing"]["area_sqm"] = 0
        context.user_data["add_state"] = ADD_PRICE
        await update.message.reply_text(_confirmed(context, "Площадь", "Area", "שטח", f"{area} м²"), parse_mode="HTML")
        deal = context.user_data["add_listing"].get("deal_type", "rent")
        text = _step_text(context,
            f"Шаг 10/16: Цена\n\nВведите цену в шекелях ({'в месяц' if deal=='rent' else 'полная стоимость'})",
            f"Step 10/16: Price\n\nEnter price in shekels ({'per month' if deal=='rent' else 'total price'})",
            f"שלב 10/16: מחיר\n\nהזן מחיר בשקלים ({'לחודש' if deal=='rent' else 'מחיר מלא'})"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_PRICE

    async def handle_price(self, update, context):
        price_text = update.message.text.strip().replace(",", "").replace(" ", "")
        try:
            price = int(price_text)
        except:
            price = 0
        context.user_data["add_listing"]["price"] = price
        context.user_data["add_state"] = ADD_PARKING
        await update.message.reply_text(_confirmed(context, "Цена", "Price", "מחיר", f"{price:,} ₪"), parse_mode="HTML")
        text = _step_text(context, "Шаг 11/16: Парковка", "Step 11/16: Parking", "שלב 11/16: חניה")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_yes_no_keyboard(context, "add_parking"), parse_mode="HTML")
        return ADD_PARKING

    async def handle_parking(self, update, context):
        query = update.callback_query
        await query.answer()
        has_parking = query.data == "add_parking_yes"
        context.user_data["add_listing"]["parking"] = 1 if has_parking else 0
        context.user_data["add_state"] = ADD_POOL
        label = _step_text(context, "Есть" if has_parking else "Нет",
                           "Yes" if has_parking else "No",
                           "יש" if has_parking else "אין")
        await query.edit_message_text(_confirmed(context, "Парковка", "Parking", "חניה", label), parse_mode="HTML")
        text = _step_text(context, "Шаг 12/16: Бассейн", "Step 12/16: Pool", "שלב 12/16: בריכה")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_yes_no_keyboard(context, "add_pool"), parse_mode="HTML")
        return ADD_POOL

    async def handle_pool(self, update, context):
        query = update.callback_query
        await query.answer()
        has_pool = query.data == "add_pool_yes"
        context.user_data["add_listing"]["pool"] = has_pool
        context.user_data["add_state"] = ADD_SHELTER
        label = _step_text(context, "Есть" if has_pool else "Нет",
                           "Yes" if has_pool else "No",
                           "יש" if has_pool else "אין")
        await query.edit_message_text(_confirmed(context, "Бассейн", "Pool", "בריכה", label), parse_mode="HTML")
        text = _step_text(context, "Шаг 13/16: Мамад/Миклат", "Step 13/16: Mamad/Miklat", "שלב 13/16: ממ\"ד/מקלט")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_shelter_keyboard(context), parse_mode="HTML")
        return ADD_SHELTER

    async def handle_shelter(self, update, context):
        query = update.callback_query
        await query.answer()
        shelter = query.data.replace("add_shelter_", "")
        context.user_data["add_listing"]["shelter"] = shelter if shelter != "none" else None
        context.user_data["add_state"] = ADD_ELEVATOR
        labels = {"mamad": {"ru":"Мамад","en":"Mamad","he":"ממ\"ד"}, "miklat": {"ru":"Миклат","en":"Miklat","he":"מקלט"}, "none": {"ru":"Нет","en":"None","he":"אין"}}
        lang = get_lang(context)
        label = labels[shelter][lang]
        await query.edit_message_text(_confirmed(context, "Мамад/Миклат", "Mamad/Miklat", "ממ\"ד/מקלט", label), parse_mode="HTML")
        text = _step_text(context, "Шаг 14/16: Лифт", "Step 14/16: Elevator", "שלב 14/16: מעלית")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_yes_no_keyboard(context, "add_elevator"), parse_mode="HTML")
        return ADD_ELEVATOR

    async def handle_elevator(self, update, context):
        query = update.callback_query
        await query.answer()
        has_elevator = query.data == "add_elevator_yes"
        context.user_data["add_listing"]["elevator"] = "yes" if has_elevator else "no"
        context.user_data["add_state"] = ADD_INFRASTRUCTURE
        label = _step_text(context, "Есть" if has_elevator else "Нет",
                           "Yes" if has_elevator else "No",
                           "יש" if has_elevator else "אין")
        await query.edit_message_text(_confirmed(context, "Лифт", "Elevator", "מעלית", label), parse_mode="HTML")
        text = _step_text(context, "Шаг 15/16: Инфраструктура\n\nВыберите что есть рядом:",
                          "Step 15/16: Infrastructure\n\nSelect what's nearby:",
                          "שלב 15/16: תשתיות\n\nבחר מה קרוב:")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_infra_keyboard(context, []), parse_mode="HTML")
        return ADD_INFRASTRUCTURE

    async def handle_infra(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("add_infra_", "")
        selected = context.user_data["add_listing"].get("infrastructure", [])
        if data == "done":
            context.user_data["add_listing"]["infrastructure"] = selected
            context.user_data["add_state"] = ADD_DESCRIPTION
            lang = get_lang(context)
            infra_str = ", ".join(selected) if selected else _step_text(context, "Не выбрано", "None selected", "לא נבחר")
            await query.edit_message_text(_confirmed(context, "Инфраструктура", "Infrastructure", "תשתיות", infra_str), parse_mode="HTML")
            text = _step_text(context,
                "Шаг 16/16: Описание\n\nНапишите описание объявления (особенности квартиры, район, условия):",
                "Step 16/16: Description\n\nWrite a description (apartment features, neighborhood, terms):",
                "שלב 16/16: תיאור\n\nכתב תיאור (מאפייני הדירה, שכונה, תנאים):"
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
            return ADD_DESCRIPTION
        if data in selected:
            selected.remove(data)
        else:
            selected.append(data)
        context.user_data["add_listing"]["infrastructure"] = selected
        context.user_data["add_state"] = ADD_INFRASTRUCTURE
        text = _step_text(context, f"Инфраструктура (выбрано: {len(selected)})",
                          f"Infrastructure (selected: {len(selected)})",
                          f"תשתיות (נבחר: {len(selected)})")
        await query.edit_message_text(text, reply_markup=_infra_keyboard(context, selected), parse_mode="HTML")
        return ADD_INFRASTRUCTURE

    async def handle_description(self, update, context):
        desc = update.message.text.strip()
        context.user_data["add_listing"]["description"] = desc
        context.user_data["add_state"] = ADD_CONTACT
        await update.message.reply_text(_confirmed(context, "Описание", "Description", "תיאור", "✓"), parse_mode="HTML")
        context.user_data["add_state"] = ADD_NAME
        text = _step_text(context,
            "Ваше имя\n\nВведите ваше имя (оно будет видно покупателям/арендаторам):",
            "Your name\n\nEnter your name (it will be visible to buyers/renters):",
            "השם שלך\n\nהזן את שמך (יהיה גלוי לקונים/שוכרים):"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_NAME

    async def handle_name(self, update, context):
        name = update.message.text.strip()
        context.user_data["add_listing"]["owner_name"] = name
        context.user_data["add_state"] = ADD_PHONE
        await update.message.reply_text(_confirmed(context, "Имя", "Name", "שם", name), parse_mode="HTML")
        text = _step_text(context,
            "Номер телефона\n\nВведите ваш номер телефона (например: +972501234567):",
            "Phone number\n\nEnter your phone number (e.g.: +972501234567):",
            "מספר טלפון\n\nהזן את מספר הטלפון שלך (לדוגמה: +972501234567):"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_PHONE

    async def handle_phone(self, update, context):
        phone = update.message.text.strip()
        context.user_data["add_listing"]["owner_phone"] = phone
        context.user_data["add_state"] = ADD_CONTACT
        await update.message.reply_text(_confirmed(context, "Телефон", "Phone", "טלפון", phone), parse_mode="HTML")
        # Сохраняем контакт в базу арендодателей
        import json, os
        owners_file = "owners_db.json"
        if os.path.exists(owners_file):
            with open(owners_file, "r", encoding="utf-8") as f:
                owners = json.load(f)
        else:
            owners = []
        owner_entry = {
            "telegram_id": str(update.effective_user.id),
            "telegram_username": update.effective_user.username or "",
            "name": context.user_data["add_listing"].get("owner_name", ""),
            "phone": phone,
            "city": context.user_data["add_listing"].get("city", ""),
            "deal_type": context.user_data["add_listing"].get("deal_type", ""),
        }
        # Обновляем если уже есть
        existing = next((o for o in owners if o["telegram_id"] == str(update.effective_user.id)), None)
        if existing:
            existing.update(owner_entry)
        else:
            owners.append(owner_entry)
        with open(owners_file, "w", encoding="utf-8") as f:
            json.dump(owners, f, ensure_ascii=False, indent=2)
        text = _step_text(context,
            "Контактная информация\n\nВведите ваш Telegram @username или дополнительный контакт для связи:",
            "Contact information\n\nEnter your Telegram @username or additional contact:",
            "פרטי קשר\n\nהזן את ה-Telegram @username או פרטי קשר נוספים:"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_CONTACT

    async def handle_contact(self, update, context):
        contact = update.message.text.strip()
        context.user_data["add_listing"]["contact"] = contact
        context.user_data["add_listing"]["photos"] = []
        context.user_data["add_state"] = ADD_PHOTOS

        text = _step_text(context,
            "📸 Фотографии\n\nОтправьте фотографии объекта (до 10 штук).\nКогда закончите — нажмите кнопку ниже.",
            "📸 Photos\n\nSend photos of the property (up to 10).\nWhen done, press the button below.",
            "📸 תמונות\n\nשלח תמונות של הנכס (עד 10).\nכשתסיים, לחץ על הכפתור למטה."
        )
        await update.message.reply_text(text, reply_markup=_photos_keyboard(context, 0))
        return ADD_PHOTOS

    async def handle_photo_message(self, update, context):
        photos = context.user_data["add_listing"].get("photos", [])
        if len(photos) < 10 and update.message.photo:
            file_id = update.message.photo[-1].file_id
            photos.append(file_id)
            context.user_data["add_listing"]["photos"] = photos
        count = len(photos)
        text = _step_text(context,
            f"📸 Получено {count} фото. Отправьте ещё или нажмите Готово.",
            f"📸 {count} photo(s) received. Send more or press Done.",
            f"📸 התקבלו {count} תמונות. שלח עוד או לחץ סיום."
        )
        await update.message.reply_text(text, reply_markup=_photos_keyboard(context, count))
        return ADD_PHOTOS

    async def handle_photos_done(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["add_state"] = ADD_CONFIRM
        d = context.user_data["add_listing"]
        lang = get_lang(context)

        deal_label = {"ru": "Аренда" if d.get("deal_type")=="rent" else "Продажа",
                      "en": "Rent" if d.get("deal_type")=="rent" else "Sale",
                      "he": "השכרה" if d.get("deal_type")=="rent" else "מכירה"}[lang]
        ptype_label = PROPERTY_TYPES.get(d.get("property_type","apartment"), {}).get(lang, "")
        photo_count = len(d.get("photos", []))
        photo_info = {"ru": f"{photo_count} фото" if photo_count else "нет фото",
                      "en": f"{photo_count} photo(s)" if photo_count else "no photos",
                      "he": f"{photo_count} תמונות" if photo_count else "אין תמונות"}[lang]

        summary_title = _step_text(context, "📋 Проверьте объявление:", "📋 Review your listing:", "📋 בדוק את המודעה:")
        owner_name = d.get("owner_name", "")
        owner_phone = d.get("owner_phone", "")
        contact = d.get("contact", "")
        seller_type = d.get("seller_type", "private")
        seller_label = {
            "agent":   {"ru": "🏢 Агент", "en": "🏢 Agent", "he": "🏢 סוכן"},
            "private": {"ru": "👤 Частное лицо", "en": "👤 Private", "he": "👤 פרטי"},
        }.get(seller_type, {}).get(lang, seller_type)

        summary = f"""{summary_title}

{'Продавец' if lang=='ru' else 'Seller' if lang=='en' else 'מוכר'}: {seller_label}
{'Тип' if lang=='ru' else 'Type' if lang=='en' else 'סוג'}: {deal_label} · {ptype_label}
{'Город' if lang=='ru' else 'City' if lang=='en' else 'עיר'}: {d.get('city','')}
{'Адрес' if lang=='ru' else 'Address' if lang=='en' else 'כתובת'}: {d.get('address', '—')}{f" — {d.get('map_url','')}" if d.get('map_url') else ''}
{'Комнат' if lang=='ru' else 'Rooms' if lang=='en' else 'חדרים'}: {d.get('rooms','')}
{'Этаж' if lang=='ru' else 'Floor' if lang=='en' else 'קומה'}: {d.get('floor','')}
{'Площадь' if lang=='ru' else 'Area' if lang=='en' else 'שטח'}: {d.get('area_sqm','')} м²
{'Цена' if lang=='ru' else 'Price' if lang=='en' else 'מחיר'}: {d.get('price',0):,} ₪
{'Парковка' if lang=='ru' else 'Parking' if lang=='en' else 'חניה'}: {'✅' if d.get('parking') else '❌'}
{'Бассейн' if lang=='ru' else 'Pool' if lang=='en' else 'בריכה'}: {'✅' if d.get('pool') else '❌'}
{'Лифт' if lang=='ru' else 'Elevator' if lang=='en' else 'מעלית'}: {'✅' if d.get('elevator')=='yes' else '❌'}
{'Фото' if lang=='ru' else 'Photos' if lang=='en' else 'תמונות'}: {photo_info}
{'Имя' if lang=='ru' else 'Name' if lang=='en' else 'שם'}: {owner_name}
{'Телефон' if lang=='ru' else 'Phone' if lang=='en' else 'טלפון'}: {owner_phone}
{'Контакт' if lang=='ru' else 'Contact' if lang=='en' else 'קשר'}: {contact}"""

        await query.message.reply_text(summary, reply_markup=_confirm_keyboard(context), parse_mode="HTML")
        return ADD_CONFIRM

    async def handle_confirm(self, update, context):
        query = update.callback_query
        await query.answer()

        if query.data == "add_confirm_no":
            text = _step_text(context, "❌ Объявление отменено.", "❌ Listing cancelled.", "❌ המודעה בוטלה.")
            await query.edit_message_text(text)
            return ConversationHandler.END

        d = context.user_data["add_listing"]
        d["user_id"] = update.effective_user.id
        d["source"] = "user"
        d["title"] = f"{'Аренда' if d.get('deal_type')=='rent' else 'Продажа'}: {d.get('rooms','')} комн., {d.get('city','')}"
        if not d.get("photos"):
            d["photos"] = ["🏠"]
        d["neighborhood"] = d.get("neighborhood", "")

        # Save city coordinates for proximity sorting
        try:
            from geocoding import get_city_coords
            coords = get_city_coords(d.get("city", ""))
            if coords:
                d["lat"], d["lng"] = coords
        except Exception:
            pass

        listing_id = db.add_listing(d)

        # Bonus days for adding a listing
        user_id_for_bonus = update.effective_user.id
        db.add_bonus_days(user_id_for_bonus, 3)
        bonus_msg = _step_text(context,
            "🎁 Бонус! +3 дня к подписке за добавление объявления",
            "🎁 Bonus! +3 days subscription for adding a listing",
            "🎁 בונוס! +3 ימי מנוי על הוספת מודעה"
        )

        text = _step_text(context,
            f"✅ Объявление опубликовано!\n\nID: #{listing_id}\nПользователи уже могут его найти через поиск.\n\n{bonus_msg}",
            f"✅ Listing published!\n\nID: #{listing_id}\nUsers can already find it through search.\n\n{bonus_msg}",
            f"✅ המודעה פורסמה!\n\nID: #{listing_id}\nמשתמשים כבר יכולים למצוא אותה דרך החיפוש.\n\n{bonus_msg}"
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    async def cancel(self, update, context):
        if update.callback_query:
            await update.callback_query.answer()
        return ConversationHandler.END
