from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from i18n import t, get_lang
from city_translations import get_city_name
from keyboards import DISTRICT_CITIES, DISTRICT_KEYS, get_district_name
import database as db

# States
(
    ADD_DEAL_TYPE, ADD_PROPERTY_TYPE, ADD_DISTRICT, ADD_CITY,
    ADD_ROOMS, ADD_FLOOR, ADD_AREA, ADD_PRICE,
    ADD_PARKING, ADD_POOL, ADD_SHELTER, ADD_ELEVATOR,
    ADD_INFRASTRUCTURE, ADD_DESCRIPTION, ADD_NAME, ADD_PHONE, ADD_CONTACT, ADD_CONFIRM
) = range(18)

PROPERTY_TYPES = {
    "apartment": {"ru": "🏢 Квартира", "en": "🏢 Apartment", "he": "🏢 דירה"},
    "house": {"ru": "🏠 Дом", "en": "🏠 House", "he": "🏠 בית"},
    "villa": {"ru": "🏡 Вилла", "en": "🏡 Villa", "he": "🏡 וילה"},
    "penthouse": {"ru": "🌆 Пентхаус", "en": "🌆 Penthouse", "he": "🌆 פנטהאוס"},
    "studio": {"ru": "🛋 Студия", "en": "🛋 Studio", "he": "🛋 סטודיו"},
    "duplex": {"ru": "🏘 Дуплекс", "en": "🏘 Duplex", "he": "🏘 דופלקס"},
}

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

def _deal_keyboard(ctx):
    lang = get_lang(ctx)
    rent = {"ru": "🔑 Аренда", "en": "🔑 Rent", "he": "🔑 השכרה"}[lang]
    buy = {"ru": "💰 Продажа", "en": "💰 Sale", "he": "💰 מכירה"}[lang]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(rent, callback_data="add_deal_rent"),
        InlineKeyboardButton(buy, callback_data="add_deal_buy"),
    ]])

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

def _confirm_keyboard(ctx):
    lang = get_lang(ctx)
    publish = {"ru": "✅ Опубликовать", "en": "✅ Publish", "he": "✅ פרסם"}[lang]
    cancel = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(publish, callback_data="add_confirm_yes")],
        [InlineKeyboardButton(cancel, callback_data="add_confirm_no")],
    ])

def _step_text(ctx, ru, en, he):
    lang = get_lang(ctx)
    return {"ru": ru, "en": en, "he": he}.get(lang, ru)


class ListingHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("add", self.start_add),
                CallbackQueryHandler(self.start_add, pattern="^add_listing$"),
            ],
            states={
                ADD_DEAL_TYPE: [CallbackQueryHandler(self.handle_deal, pattern="^add_deal_")],
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
        context.user_data["add_listing"] = {}
        context.user_data["add_state"] = ADD_DEAL_TYPE
        text = _step_text(context,
            "🏠 Добавление объявления\n\nШаг 1/14: Тип сделки",
            "🏠 Add listing\n\nStep 1/14: Deal type",
            "🏠 הוספת מודעה\n\nשלב 1/14: סוג עסקה"
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=_deal_keyboard(context), parse_mode="HTML")
        else:
            await update.message.reply_text(text, reply_markup=_deal_keyboard(context), parse_mode="HTML")
        return ADD_DEAL_TYPE

    async def handle_back(self, update, context):
        query = update.callback_query
        await query.answer()
        state = context.user_data.get("add_state", ADD_DEAL_TYPE)

        if state == ADD_PROPERTY_TYPE:
            text = _step_text(context, "Шаг 1/14: Тип сделки", "Step 1/14: Deal type", "שלב 1/14: סוג עסקה")
            await query.edit_message_text(text, reply_markup=_deal_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_DEAL_TYPE
            return ADD_DEAL_TYPE
        elif state == ADD_DISTRICT:
            text = _step_text(context, "Шаг 2/14: Тип жилья", "Step 2/14: Property type", "שלב 2/14: סוג נכס")
            await query.edit_message_text(text, reply_markup=_ptype_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_PROPERTY_TYPE
            return ADD_PROPERTY_TYPE
        elif state == ADD_CITY:
            text = _step_text(context, "Шаг 3/14: Округ", "Step 3/14: District", "שלב 3/14: מחוז")
            await query.edit_message_text(text, reply_markup=_district_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_DISTRICT
            return ADD_DISTRICT
        elif state == ADD_ROOMS:
            district = context.user_data["add_listing"].get("district", "tel_aviv")
            text = _step_text(context, "Шаг 4/14: Город", "Step 4/14: City", "שלב 4/14: עיר")
            await query.edit_message_text(text, reply_markup=_city_keyboard(context, district), parse_mode="HTML")
            context.user_data["add_state"] = ADD_CITY
            return ADD_CITY
        elif state == ADD_FLOOR:
            text = _step_text(context, "Шаг 5/14: Количество комнат", "Step 5/14: Number of rooms", "שלב 5/14: מספר חדרים")
            await query.edit_message_text(text, reply_markup=_rooms_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_ROOMS
            return ADD_ROOMS
        elif state == ADD_AREA:
            text = _step_text(context, "Шаг 6/14: Этаж", "Step 6/14: Floor", "שלב 6/14: קומה")
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
                callback_data="add_back"
            )]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode="HTML")
            context.user_data["add_state"] = ADD_FLOOR
            return ADD_FLOOR
        elif state == ADD_PRICE:
            text = _step_text(context, "Шаг 7/14: Площадь (кв.м)", "Step 7/14: Area (sqm)", "שלב 7/14: שטח (מ\"ר)")
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
                callback_data="add_back"
            )]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode="HTML")
            context.user_data["add_state"] = ADD_AREA
            return ADD_AREA
        elif state == ADD_PARKING:
            deal = context.user_data["add_listing"].get("deal_type", "rent")
            price_text = _step_text(context,
                f"Шаг 8/14: Цена ({'₪/мес' if deal=='rent' else '₪'})",
                f"Step 8/14: Price ({'₪/mo' if deal=='rent' else '₪'})",
                f"שלב 8/14: מחיר ({'₪/חודש' if deal=='rent' else '₪'})"
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
                callback_data="add_back"
            )]])
            await query.edit_message_text(price_text, reply_markup=back_kb, parse_mode="HTML")
            context.user_data["add_state"] = ADD_PRICE
            return ADD_PRICE
        elif state == ADD_POOL:
            text = _step_text(context, "Шаг 9/14: Парковка", "Step 9/14: Parking", "שלב 9/14: חניה")
            await query.edit_message_text(text, reply_markup=_yes_no_keyboard(context, "add_parking"), parse_mode="HTML")
            context.user_data["add_state"] = ADD_PARKING
            return ADD_PARKING
        elif state == ADD_SHELTER:
            text = _step_text(context, "Шаг 10/14: Бассейн", "Step 10/14: Pool", "שלב 10/14: בריכה")
            await query.edit_message_text(text, reply_markup=_yes_no_keyboard(context, "add_pool"), parse_mode="HTML")
            context.user_data["add_state"] = ADD_POOL
            return ADD_POOL
        elif state == ADD_ELEVATOR:
            text = _step_text(context, "Шаг 11/14: Мамад/Миклат", "Step 11/14: Mamad/Miklat", "שלב 11/14: ממ\"ד/מקלט")
            await query.edit_message_text(text, reply_markup=_shelter_keyboard(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_SHELTER
            return ADD_SHELTER
        elif state == ADD_INFRASTRUCTURE:
            text = _step_text(context, "Шаг 12/14: Лифт", "Step 12/14: Elevator", "שלב 12/14: מעלית")
            await query.edit_message_text(text, reply_markup=_yes_no_keyboard(context, "add_elevator"), parse_mode="HTML")
            context.user_data["add_state"] = ADD_ELEVATOR
            return ADD_ELEVATOR
        elif state == ADD_DESCRIPTION:
            selected = context.user_data["add_listing"].get("infrastructure", [])
            text = _step_text(context, "Шаг 13/14: Инфраструктура", "Step 13/14: Infrastructure", "שלב 13/14: תשתיות")
            await query.edit_message_text(text, reply_markup=_infra_keyboard(context, selected), parse_mode="HTML")
            context.user_data["add_state"] = ADD_INFRASTRUCTURE
            return ADD_INFRASTRUCTURE
        elif state == ADD_CONTACT:
            text = _step_text(context, "Шаг 14/14: Описание", "Step 14/14: Description", "שלב 14/14: תיאור")
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
                callback_data="add_back"
            )]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode="HTML")
            context.user_data["add_state"] = ADD_DESCRIPTION
            return ADD_DESCRIPTION
        return ConversationHandler.END

    async def handle_deal(self, update, context):
        query = update.callback_query
        await query.answer()
        deal = query.data.replace("add_deal_", "")
        context.user_data["add_listing"]["deal_type"] = deal
        context.user_data["add_state"] = ADD_PROPERTY_TYPE
        deal_label = _step_text(context, "Аренда" if deal=="rent" else "Продажа",
                                "Rent" if deal=="rent" else "Sale",
                                "השכרה" if deal=="rent" else "מכירה")
        await query.edit_message_text(_confirmed(context, "Тип сделки", "Deal type", "סוג עסקה", deal_label), parse_mode="HTML")
        text = _step_text(context, "Шаг 2/14: Тип жилья", "Step 2/14: Property type", "שלב 2/14: סוג נכס")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_ptype_keyboard(context), parse_mode="HTML")
        return ADD_PROPERTY_TYPE

    async def handle_ptype(self, update, context):
        query = update.callback_query
        await query.answer()
        ptype = query.data.replace("add_ptype_", "")
        context.user_data["add_listing"]["property_type"] = ptype
        context.user_data["add_state"] = ADD_DISTRICT
        lang = get_lang(context)
        ptype_label = PROPERTY_TYPES[ptype][lang]
        await query.edit_message_text(_confirmed(context, "Тип жилья", "Property type", "סוג נכס", ptype_label), parse_mode="HTML")
        text = _step_text(context, "Шаг 3/14: Округ", "Step 3/14: District", "שלב 3/14: מחוז")
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
        text = _step_text(context, "Шаг 4/14: Город", "Step 4/14: City", "שלב 4/14: עיר")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=_city_keyboard(context, district), parse_mode="HTML")
        return ADD_CITY

    async def handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        city = query.data.replace("add_city_", "")
        context.user_data["add_listing"]["city"] = city
        context.user_data["add_state"] = ADD_ROOMS
        lang = get_lang(context)
        city_label = get_city_name(city, lang)
        await query.edit_message_text(_confirmed(context, "Город", "City", "עיר", city_label), parse_mode="HTML")
        text = _step_text(context, "Шаг 5/14: Количество комнат", "Step 5/14: Number of rooms", "שלב 5/14: מספר חדרים")
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
            "Шаг 6/14: Этаж\n\nВведите номер этажа (например: 3)",
            "Step 6/14: Floor\n\nEnter floor number (e.g.: 3)",
            "שלב 6/14: קומה\n\nהזן מספר קומה (לדוגמה: 3)"
        )
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
            callback_data="add_back"
        )]])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
        return ADD_FLOOR

    async def handle_floor(self, update, context):
        floor = update.message.text.strip()
        context.user_data["add_listing"]["floor"] = floor
        context.user_data["add_state"] = ADD_AREA
        await update.message.reply_text(_confirmed(context, "Этаж", "Floor", "קומה", floor), parse_mode="HTML")
        text = _step_text(context,
            "Шаг 7/14: Площадь\n\nВведите площадь в кв.м (например: 85)",
            "Step 7/14: Area\n\nEnter area in sqm (e.g.: 85)",
            "שלב 7/14: שטח\n\nהזן שטח במ\"ר (לדוגמה: 85)"
        )
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
            callback_data="add_back"
        )]])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
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
            f"Шаг 8/14: Цена\n\nВведите цену в шекелях ({'в месяц' if deal=='rent' else 'полная стоимость'})",
            f"Step 8/14: Price\n\nEnter price in shekels ({'per month' if deal=='rent' else 'total price'})",
            f"שלב 8/14: מחיר\n\nהזן מחיר בשקלים ({'לחודש' if deal=='rent' else 'מחיר מלא'})"
        )
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
            callback_data="add_back"
        )]])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
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
        text = _step_text(context, "Шаг 9/14: Парковка", "Step 9/14: Parking", "שלב 9/14: חניה")
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
        text = _step_text(context, "Шаг 10/14: Бассейн", "Step 10/14: Pool", "שלב 10/14: בריכה")
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
        text = _step_text(context, "Шаг 11/14: Мамад/Миклат", "Step 11/14: Mamad/Miklat", "שלב 11/14: ממ\"ד/מקלט")
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
        text = _step_text(context, "Шаг 12/14: Лифт", "Step 12/14: Elevator", "שלב 12/14: מעלית")
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
        text = _step_text(context, "Шаг 13/14: Инфраструктура\n\nВыберите что есть рядом:",
                          "Step 13/14: Infrastructure\n\nSelect what's nearby:",
                          "שלב 13/14: תשתיות\n\nבחר מה קרוב:")
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
                "Шаг 14/14: Описание\n\nНапишите описание объявления (особенности квартиры, район, условия):",
                "Step 14/14: Description\n\nWrite a description (apartment features, neighborhood, terms):",
                "שלב 14/14: תיאור\n\nכתב תיאור (מאפייני הדירה, שכונה, תנאים):"
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
                callback_data="add_back"
            )]])
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
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
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
            callback_data="add_back"
        )]])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
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
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
            callback_data="add_back"
        )]])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
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
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            {"ru": "« Назад", "en": "« Back", "he": "« חזרה"}[get_lang(context)],
            callback_data="add_back"
        )]])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=back_kb, parse_mode="HTML")
        return ADD_CONTACT

    async def handle_contact(self, update, context):
        contact = update.message.text.strip()
        context.user_data["add_listing"]["contact"] = contact
        context.user_data["add_state"] = ADD_CONFIRM
        d = context.user_data["add_listing"]
        lang = get_lang(context)

        # Summary
        deal_label = {"ru": "Аренда" if d.get("deal_type")=="rent" else "Продажа",
                      "en": "Rent" if d.get("deal_type")=="rent" else "Sale",
                      "he": "השכרה" if d.get("deal_type")=="rent" else "מכירה"}[lang]
        ptype_label = PROPERTY_TYPES.get(d.get("property_type","apartment"), {}).get(lang, "")
        city_label = d.get("city", "")

        summary_title = _step_text(context, "📋 Проверьте объявление:", "📋 Review your listing:", "📋 בדוק את המודעה:")
        owner_name = d.get("owner_name", "")
        owner_phone = d.get("owner_phone", "")
        summary = f"""{summary_title}

{'Тип' if lang=='ru' else 'Type' if lang=='en' else 'סוג'}: {deal_label} · {ptype_label}
{'Город' if lang=='ru' else 'City' if lang=='en' else 'עיר'}: {city_label}
{'Комнат' if lang=='ru' else 'Rooms' if lang=='en' else 'חדרים'}: {d.get('rooms','')}
{'Этаж' if lang=='ru' else 'Floor' if lang=='en' else 'קומה'}: {d.get('floor','')}
{'Площадь' if lang=='ru' else 'Area' if lang=='en' else 'שטח'}: {d.get('area_sqm','')} м²
{'Цена' if lang=='ru' else 'Price' if lang=='en' else 'מחיר'}: {d.get('price',0):,} ₪
{'Парковка' if lang=='ru' else 'Parking' if lang=='en' else 'חניה'}: {'✅' if d.get('parking') else '❌'}
{'Бассейн' if lang=='ru' else 'Pool' if lang=='en' else 'בריכה'}: {'✅' if d.get('pool') else '❌'}
{'Лифт' if lang=='ru' else 'Elevator' if lang=='en' else 'מעלית'}: {'✅' if d.get('elevator')=='yes' else '❌'}
{'Имя' if lang=='ru' else 'Name' if lang=='en' else 'שם'}: {owner_name}
{'Телефон' if lang=='ru' else 'Phone' if lang=='en' else 'טלפון'}: {owner_phone}
{'Контакт' if lang=='ru' else 'Contact' if lang=='en' else 'קשר'}: {contact}"""

        await update.message.reply_text(summary, reply_markup=_confirm_keyboard(context), parse_mode="HTML")
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
        d["photos"] = ["🏠"]
        d["neighborhood"] = ""

        listing_id = db.add_listing(d)

        text = _step_text(context,
            f"✅ Объявление опубликовано!\n\nID: #{listing_id}\nПользователи уже могут его найти через поиск.",
            f"✅ Listing published!\n\nID: #{listing_id}\nUsers can already find it through search.",
            f"✅ המודעה פורסמה!\n\nID: #{listing_id}\nמשתמשים כבר יכולים למצוא אותה דרך החיפוש."
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    async def cancel(self, update, context):
        if update.callback_query:
            await update.callback_query.answer()
        return ConversationHandler.END
