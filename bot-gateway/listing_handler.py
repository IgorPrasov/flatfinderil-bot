from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from i18n import t, get_lang
from city_translations import get_city_name
from keyboards import DISTRICT_CITIES, DISTRICT_KEYS, get_district_name, paywall_keyboard
import database as db
from subscription import has_access
import upload_handler as uploader

# States
(
    ADD_SELLER_TYPE,
    ADD_UPLOAD_FILE,
    ADD_DEAL_TYPE, ADD_PROPERTY_TYPE, ADD_DISTRICT, ADD_CITY,
    ADD_ADDRESS,
    ADD_ROOMS, ADD_FLOOR, ADD_AREA, ADD_PRICE,
    ADD_PARKING, ADD_POOL, ADD_SHELTER, ADD_ELEVATOR,
    ADD_INFRASTRUCTURE, ADD_DESCRIPTION, ADD_NAME, ADD_PHONE, ADD_CONTACT, ADD_EMAIL, ADD_PHOTOS, ADD_CONFIRM,
    ADD_AWAIT_PAYMENT,
) = range(24)

PROPERTY_TYPES = {
    "apartment": {"ru": "🏢 Квартира", "en": "🏢 Apartment", "he": "🏢 דירה", "fr": "🏢 Appartement"},
    "house": {"ru": "🏠 Дом", "en": "🏠 House", "he": "🏠 בית", "fr": "🏠 Maison"},
    "villa": {"ru": "🏡 Вилла", "en": "🏡 Villa", "he": "🏡 וילה", "fr": "🏡 Villa"},
    "penthouse": {"ru": "🌆 Пентхаус", "en": "🌆 Penthouse", "he": "🌆 פנטהאוס", "fr": "🌆 Penthouse"},
    "studio": {"ru": "🛋 Студия", "en": "🛋 Studio", "he": "🛋 סטודיו", "fr": "🛋 Studio"},
    "duplex": {"ru": "🏘 Дуплекс", "en": "🏘 Duplex", "he": "🏘 דופלקס", "fr": "🏘 Duplex"},
}

COMMERCIAL_TYPES = {
    "office": {"ru": "🏢 Офис", "en": "🏢 Office", "he": "🏢 משרד", "fr": "🏢 Bureau"},
    "retail": {"ru": "🏪 Магазин/Ретейл", "en": "🏪 Shop/Retail", "he": "🏪 חנות/קמעונאות", "fr": "🏪 Magasin/Commerce"},
    "warehouse": {"ru": "🏭 Склад", "en": "🏭 Warehouse", "he": "🏭 מחסן", "fr": "🏭 Entrepôt"},
    "coworking": {"ru": "💼 Коворкинг", "en": "💼 Coworking", "he": "💼 קוורקינג", "fr": "💼 Coworking"},
    "restaurant_space": {"ru": "🍽 Кафе/Ресторан", "en": "🍽 Cafe/Restaurant", "he": "🍽 קפה/מסעדה", "fr": "🍽 Café/Restaurant"},
    "other_commercial": {"ru": "🏗 Другое", "en": "🏗 Other", "he": "🏗 אחר", "fr": "🏗 Autre"},
}

COMMERCIAL_KEYS = list(COMMERCIAL_TYPES.keys())

INFRA_KEYS_ADD = [
    "school", "kindergarten", "transport", "mall",
    "park", "gym", "beach", "restaurant", "synagogue"
]


def _L(d: dict, lang: str) -> str:
    """Безопасный выбор перевода: lang → en → ru → первый доступный."""
    if not isinstance(d, dict):
        return str(d)
    return d.get(lang) or d.get("en") or d.get("ru") or next(iter(d.values()), "")

def _t(context, ru, en, he):
    lang = get_lang(context)
    return _L({"ru": ru, "en": en, "he": he}, lang)

def _confirmed(context, ru, en, he, value):
    label = _t(context, ru, en, he)
    return f"✅ <b>{label}:</b> {value}"

def _seller_type_keyboard(ctx):
    lang = get_lang(ctx)
    agent   = _L({"ru": "🏢 Агент / Риелтор", "en": "🏢 Agent / Realtor", "he": "🏢 סוכן / מתווך", "fr": "🏢 Agent / Courtier"}, lang)
    private = _L({"ru": "👤 Частное лицо",     "en": "👤 Private person",  "he": "👤 אדם פרטי", "fr": "👤 Personne privée"}, lang)
    cancel  = _L({"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול", "fr": "❌ Annuler"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(agent,   callback_data="add_seller_agent")],
        [InlineKeyboardButton(private, callback_data="add_seller_private")],
        [InlineKeyboardButton(cancel,  callback_data="add_cancel")],
    ])


def _agent_method_keyboard(ctx):
    """After agent is selected: choose manual entry or CSV upload."""
    lang = get_lang(ctx)
    manual   = _L({"ru": "✍️ Добавить вручную",      "en": "✍️ Add manually",      "he": "✍️ הוסף ידנית", "fr": "✍️ Ajouter manuellement"}, lang)
    upload   = _L({"ru": "📤 Загрузить CSV/XLSX",    "en": "📤 Upload CSV/XLSX",    "he": "📤 העלה CSV/XLSX", "fr": "📤 Téléverser CSV/XLSX"}, lang)
    template = _L({"ru": "📄 Скачать шаблон",         "en": "📄 Download template",  "he": "📄 הורד תבנית", "fr": "📄 Télécharger le modèle"}, lang)
    back     = _L({"ru": "« Назад",                   "en": "« Back",               "he": "« חזרה", "fr": "« Retour"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(manual,   callback_data="add_agent_manual")],
        [InlineKeyboardButton(upload,   callback_data="add_agent_upload")],
        [InlineKeyboardButton(template, callback_data="add_agent_template")],
        [InlineKeyboardButton(back,     callback_data="add_agent_back")],
    ])


def _deal_keyboard(ctx):
    lang = get_lang(ctx)
    rent = _L({"ru": "🔑 Аренда", "en": "🔑 Rent", "he": "🔑 השכרה", "fr": "🔑 Location"}, lang)
    buy = _L({"ru": "💰 Продажа", "en": "💰 Sale", "he": "💰 מכירה", "fr": "💰 Vente"}, lang)
    sublet = _L({"ru": "🔄 Сублет", "en": "🔄 Sublet", "he": "🔄 סאבלט", "fr": "🔄 Sous-location"}, lang)
    commercial = _L({"ru": "🏢 Коммерческая", "en": "🏢 Commercial", "he": "🏢 מסחרי", "fr": "🏢 Commercial"}, lang)
    back   = _L({"ru": "« Назад",   "en": "« Back",    "he": "« חזרה",   "fr": "« Retour"}, lang)
    cancel = _L({"ru": "❌ Отмена", "en": "❌ Cancel",  "he": "❌ ביטול",  "fr": "❌ Annuler"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(rent, callback_data="add_deal_rent"),
         InlineKeyboardButton(buy, callback_data="add_deal_buy")],
        [InlineKeyboardButton(sublet, callback_data="add_deal_sublet"),
         InlineKeyboardButton(commercial, callback_data="add_deal_commercial")],
        [InlineKeyboardButton(back, callback_data="add_back"),
         InlineKeyboardButton(cancel, callback_data="add_cancel")],
    ])

def _ptype_keyboard(ctx):
    lang = get_lang(ctx)
    buttons = []
    row = []
    for key, names in PROPERTY_TYPES.items():
        row.append(InlineKeyboardButton(_L(names, lang), callback_data=f"add_ptype_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _comm_type_keyboard(ctx):
    lang = get_lang(ctx)
    buttons = []
    row = []
    for key, names in COMMERCIAL_TYPES.items():
        row.append(InlineKeyboardButton(_L(names, lang), callback_data=f"add_ptype_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _district_keyboard(ctx):
    lang = get_lang(ctx)
    buttons = [[InlineKeyboardButton(get_district_name(k, lang), callback_data=f"add_dist_{k}")] for k in DISTRICT_KEYS]
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
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
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
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
    back_label = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    buttons.append([InlineKeyboardButton(back_label, callback_data="add_back")])
    return InlineKeyboardMarkup(buttons)

def _yes_no_keyboard(ctx, prefix):
    lang = get_lang(ctx)
    yes = _L({"ru": "✅ Есть", "en": "✅ Yes", "he": "✅ יש", "fr": "✅ Oui"}, lang)
    no = _L({"ru": "❌ Нет", "en": "❌ No", "he": "❌ אין", "fr": "❌ Non"}, lang)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes, callback_data=f"{prefix}_yes"),
         InlineKeyboardButton(no, callback_data=f"{prefix}_no")],
        [InlineKeyboardButton(back, callback_data="add_back")],
    ])

def _shelter_keyboard(ctx):
    lang = get_lang(ctx)
    opts = {
        "mamad": {"ru": "🛡 Мамад", "en": "🛡 Mamad", "he": "🛡 ממ\"ד", "fr": "🛡 Mamad"},
        "miklat": {"ru": "🏗 Миклат", "en": "🏗 Miklat", "he": "🏗 מקלט", "fr": "🏗 Miklat"},
        "none": {"ru": "❌ Нет", "en": "❌ None", "he": "❌ אין", "fr": "❌ Aucun"},
    }
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_L(opts["mamad"], lang), callback_data="add_shelter_mamad"),
         InlineKeyboardButton(_L(opts["miklat"], lang), callback_data="add_shelter_miklat")],
        [InlineKeyboardButton(_L(opts["none"], lang), callback_data="add_shelter_none")],
        [InlineKeyboardButton(back, callback_data="add_back")],
    ])

def _infra_keyboard(ctx, selected=None):
    if selected is None:
        selected = []
    lang = get_lang(ctx)
    infra_names = {
        "school": {"ru": "🏫 Школа", "en": "🏫 School", "he": "🏫 בית ספר", "fr": "🏫 École"},
        "kindergarten": {"ru": "🎠 Садик", "en": "🎠 Kindergarten", "he": "🎠 גן ילדים", "fr": "🎠 École maternelle"},
        "transport": {"ru": "🚌 Транспорт", "en": "🚌 Transport", "he": "🚌 תחבורה", "fr": "🚌 Transport"},
        "mall": {"ru": "🛍 Торг.центр", "en": "🛍 Mall", "he": "🛍 קניון", "fr": "🛍 Centre commercial"},
        "park": {"ru": "🌳 Парк", "en": "🌳 Park", "he": "🌳 פארק", "fr": "🌳 Parc"},
        "gym": {"ru": "💪 Спортзал", "en": "💪 Gym", "he": "💪 חדר כושר", "fr": "💪 Salle de sport"},
        "beach": {"ru": "🏖 Пляж", "en": "🏖 Beach", "he": "🏖 חוף", "fr": "🏖 Plage"},
        "restaurant": {"ru": "🍽 Рестораны", "en": "🍽 Restaurants", "he": "🍽 מסעדות", "fr": "🍽 Restaurants"},
        "synagogue": {"ru": "✡️ Синагога", "en": "✡️ Synagogue", "he": "✡️ בית כנסת", "fr": "✡️ Synagogue"},
    }
    done = _L({"ru": "✅ Готово", "en": "✅ Done", "he": "✅ סיום", "fr": "✅ Terminé"}, lang)
    back = _L({"ru": "« Назад", "en": "« Back", "he": "« חזרה", "fr": "« Retour"}, lang)
    buttons = []
    row = []
    for key in INFRA_KEYS_ADD:
        name = _L(infra_names[key], lang)
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
        label = _L({"ru": f"✅ Готово ({count} фото)", "en": f"✅ Done ({count} photos)", "he": f"✅ סיום ({count} תמונות)"}, lang)
    else:
        label = _L({"ru": "⏭ Пропустить", "en": "⏭ Skip", "he": "⏭ דלג", "fr": "⏭ Passer"}, lang)
    back   = _L({"ru": "« Назад",   "en": "« Back",   "he": "« חזרה",  "fr": "« Retour"}, lang)
    cancel = _L({"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול", "fr": "❌ Annuler"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label,  callback_data="add_photos_done")],
        [InlineKeyboardButton(back,   callback_data="add_back"),
         InlineKeyboardButton(cancel, callback_data="add_cancel")],
    ])


def _confirm_keyboard(ctx):
    lang = get_lang(ctx)
    publish = _L({"ru": "✅ Опубликовать", "en": "✅ Publish", "he": "✅ פרסם", "fr": "✅ Publier"}, lang)
    cancel  = _L({"ru": "❌ Отмена",       "en": "❌ Cancel",  "he": "❌ ביטול", "fr": "❌ Annuler"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(publish, callback_data="add_confirm_yes")],
        [InlineKeyboardButton(cancel,  callback_data="add_cancel")],
    ])

def _step_text(ctx, ru, en, he):
    lang = get_lang(ctx)
    return {"ru": ru, "en": en, "he": he}.get(lang, ru)

def _back_kb(ctx):
    lang = get_lang(ctx)
    back   = _L({"ru": "« Назад",   "en": "« Back",   "he": "« חזרה",  "fr": "« Retour"}, lang)
    cancel = _L({"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול", "fr": "❌ Annuler"}, lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(back,   callback_data="add_back"),
         InlineKeyboardButton(cancel, callback_data="add_cancel")],
    ])


async def _show_agent_paywall(update, context, lang: str):
    """Show agent listing paywall with package selection buttons."""
    from pricing import AGENT_PACKAGES, format_agent_pricing

    credits = db.get_listing_credits(update.effective_user.id)
    pricing_text = format_agent_pricing(lang)

    msgs = {
        "ru": (
            f"🔒 <b>Лимит бесплатных объявлений исчерпан</b>\n\n"
            f"Первое объявление — бесплатно ✅\n"
            f"Выберите пакет на <b>1 месяц</b>:\n\n"
            f"{pricing_text}"
        ),
        "en": (
            f"🔒 <b>Free listing limit reached</b>\n\n"
            f"First listing — free ✅\n"
            f"Choose a <b>monthly</b> package:\n\n"
            f"{pricing_text}"
        ),
        "he": (
            f"🔒 <b>מכסת המודעות החינמיות הגיעה לסיומה</b>\n\n"
            f"מודעה ראשונה — חינם ✅\n"
            f"בחר חבילה ל<b>חודש אחד</b>:\n\n"
            f"{pricing_text}"
        ),
    }

    # Build package buttons
    rows = []
    for pkg in AGENT_PACKAGES:
        label = pkg["label"].get(lang, pkg["label"]["ru"])
        note  = pkg["note"].get(lang, "")
        note_str = f" ({note})" if note else ""
        btn_text = f"{label} — {pkg['price_ils']} ₪{note_str}"
        rows.append([InlineKeyboardButton(btn_text, callback_data=f"agent_pkg_{pkg['key']}")])

    # Crypto payment option
    crypto_label = {"ru": "₿ Оплатить криптовалютой", "en": "₿ Pay with crypto", "he": "₿ תשלום בקריפטו"}.get(lang, "₿ Pay with crypto")
    rows.append([InlineKeyboardButton(crypto_label, callback_data="agent_crypto")])

    cancel_label = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}.get(lang, "❌ Cancel")
    rows.append([InlineKeyboardButton(cancel_label, callback_data="add_cancel")])

    keyboard = InlineKeyboardMarkup(rows)
    query = update.callback_query
    await query.edit_message_text(
        msgs.get(lang, msgs["ru"]),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


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
                    CallbackQueryHandler(self.cancel, pattern="^add_cancel$"),
                ],
                ADD_UPLOAD_FILE: [
                    CallbackQueryHandler(self.handle_agent_method, pattern="^add_agent_"),
                    MessageHandler(filters.Document.ALL, self.handle_upload_document),
                ],
                ADD_DEAL_TYPE: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.handle_deal, pattern="^add_deal_"),
                    CallbackQueryHandler(self.cancel, pattern="^add_cancel$"),
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
                ADD_EMAIL: [
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_email),
                ],
                ADD_PHOTOS: [
                    MessageHandler(filters.PHOTO, self.handle_photo_message),
                    CallbackQueryHandler(self.handle_photos_done, pattern="^add_photos_done$"),
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                ],
                ADD_CONFIRM: [
                    CallbackQueryHandler(self.handle_confirm, pattern="^add_confirm_"),
                    CallbackQueryHandler(self.handle_back, pattern="^add_back$"),
                    CallbackQueryHandler(self.cancel, pattern="^add_cancel$"),
                ],
                ADD_AWAIT_PAYMENT: [
                    CallbackQueryHandler(self.handle_await_payment, pattern="^(agent_pkg_|agent_crypto|agent_check_payment|add_cancel|back_to_menu|agent_crypto_plan_|agent_crypto_pay_)"),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CallbackQueryHandler(self.cancel, pattern="^add_cancel$"),
                # Catch-all: block any other button/command during add flow
                # Exclude entry-points of other ConversationHandlers so they work normally
                CallbackQueryHandler(self._warn_navigation,
                    pattern="^(?!(contact_admin|back_to_menu|search|add_listing|commercial_add|service_add|crm_))"),
                CommandHandler("start",  self._warn_command),
                CommandHandler("search", self._warn_command),
                CommandHandler("help",   self._warn_command),
            ],
            per_message=False,
            allow_reentry=True,
        )

    async def start_add(self, update, context):
        # Agents are gated by listing credits (checked in handle_agent_method).
        # Private persons can always post for free.
        # No blanket subscription check here.
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
        label = _L({"ru": "👤 Частное лицо", "en": "👤 Private person", "he": "👤 אדם פרטי", "fr": "👤 Personne privée"}, lang)
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
            prompt = _L({
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
             "fr": "📤 <b>Téléversement groupé d'annonces</b>\n\nEnvoyez un fichier <b>CSV</b> ou <b>XLSX</b>.\nToutes les colonnes sont obligatoires — les fichiers incomplets sont rejetés.\n\nPas de modèle ? Appuyez sur «📄 Télécharger le modèle»."}, lang)
            await query.edit_message_text(prompt, reply_markup=_agent_method_keyboard(context), parse_mode="HTML")
            return ADD_UPLOAD_FILE

        if action == "add_agent_manual":
            lang = get_lang(context)
            user_id = update.effective_user.id
            has_credits = db.get_listing_credits(user_id) > 0
            free_ok = not db.has_used_free_listing(user_id)

            if not has_credits and not free_ok:
                # No credits and no free slot — show package selection before listing
                context.user_data["add_listing"] = {}
                await _show_agent_paywall(update, context, lang)
                return ADD_AWAIT_PAYMENT

            label = _L({"ru": "🏢 Агент / Риелтор", "en": "🏢 Agent / Realtor", "he": "🏢 סוכן / מתווך", "fr": "🏢 Agent / Courtier"}, lang)
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
                _L({"ru": "❌ Отправьте файл CSV или XLSX.",
                 "en": "❌ Please send a CSV or XLSX file.",
                 "he": "❌ שלח קובץ CSV או XLSX.", "fr": "❌ Veuillez envoyer un fichier CSV ou XLSX."}, lang),
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
            err_text = _L({
                "ru": f"❌ <b>Файл не принят</b>\n\n" + "\n".join(shown) + tail + "\n\nИсправьте ошибки и загрузите снова.",
                "en": f"❌ <b>File rejected</b>\n\n" + "\n".join(shown) + tail + "\n\nFix the errors and re-upload.",
                "he": f"❌ <b>הקובץ נדחה</b>\n\n" + "\n".join(shown) + tail + "\n\nתקן את השגיאות ושלח שוב.",
            }, lang)
            await update.message.reply_text(err_text, reply_markup=_agent_method_keyboard(context), parse_mode="HTML")
            return ADD_UPLOAD_FILE

        n = result["imported"]
        ok_text = _L({
            "ru": f"✅ <b>Загружено {n} объявлений!</b>\n\nОни уже доступны в поиске.",
            "en": f"✅ <b>{n} listings imported!</b>\n\nThey are now visible in search.",
            "he": f"✅ <b>{n} מודעות הועלו!</b>\n\nהן כבר זמינות בחיפוש.",
        }, lang)
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
        elif state == ADD_EMAIL:
            text = _step_text(context,
                "Контактная информация\n\nВведите ваш Telegram @username или дополнительный контакт:",
                "Contact information\n\nEnter your Telegram @username or additional contact:",
                "פרטי קשר\n\nהזן את ה-Telegram @username או פרטי קשר נוספים:"
            )
            await query.edit_message_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
            context.user_data["add_state"] = ADD_CONTACT
            return ADD_CONTACT
        elif state == ADD_PHOTOS:
            # If agent, go back to email; otherwise go back to contact
            if context.user_data["add_listing"].get("seller_type") == "agent":
                lang = get_lang(context)
                user_id = update.effective_user.id
                existing_email = db.get_agent_email(user_id)
                hint = f" (сохранён: {existing_email})" if existing_email else ""
                skip_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="add_email_skip")]])
                text = _step_text(context,
                    f"📧 Email для отчётов{hint}",
                    f"📧 Email for reports{hint}",
                    f"📧 אימייל לדוחות{hint}"
                )
                await query.edit_message_text(text, reply_markup=skip_btn, parse_mode="HTML")
                context.user_data["add_state"] = ADD_EMAIL
                return ADD_EMAIL
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
            "rent": {"ru": "Аренда", "en": "Rent", "he": "השכרה", "fr": "Location"},
            "buy": {"ru": "Продажа", "en": "Sale", "he": "מכירה", "fr": "Vente"},
            "sublet": {"ru": "Сублет", "en": "Sublet", "he": "סאבלט", "fr": "Sous-location"},
            "commercial": {"ru": "Коммерческая", "en": "Commercial", "he": "מסחרי", "fr": "Commercial"},
        }
        lang = get_lang(context)
        deal_label = _L(deal_labels.get(deal, deal_labels["rent"]), lang)
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
        map_label = {"ru": "🗺 Посмотреть на карте", "en": "🗺 View on map", "he": "🗺 הצג במפה", "fr": "🗺 Voir sur la carte"}.get(lang, "🗺 Map")
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
        price_text = update.message.text.strip().replace(",", "").replace(" ", "").replace("₪", "")
        try:
            price = int(price_text)
        except:
            price = 0
        if price <= 0:
            err = _step_text(context,
                "❌ Пожалуйста, введите цену в шекелях (только цифры, например: 4500)",
                "❌ Please enter the price in shekels (numbers only, e.g.: 4500)",
                "❌ אנא הכנס מחיר בשקלים (ספרות בלבד, לדוג׳: 4500)"
            )
            await update.message.reply_text(err, parse_mode="HTML")
            return ADD_PRICE
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
        labels = {"mamad": {"ru":"Мамад","en":"Mamad","he":"ממ\"ד", "fr": "Mamad"}, "miklat": {"ru":"Миклат","en":"Miklat","he":"מקלט", "fr": "Miklat"}, "none": {"ru":"Нет","en":"None","he":"אין", "fr": "Aucun"}}
        lang = get_lang(context)
        label = _L(labels[shelter], lang)
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

        # All users must provide email (required, no skip)
        context.user_data["add_state"] = ADD_EMAIL
        lang = get_lang(context)
        user_id = update.effective_user.id
        existing_email = db.get_agent_email(user_id)
        if existing_email:
            hint = _L({"ru": f"(сохранён: {existing_email})", "en": f"(saved: {existing_email})", "he": f"(שמור: {existing_email})"}, lang)
        else:
            hint = ""
        text = _step_text(context,
            f"📧 E-mail {hint}\n\nВведите ваш e-mail. Без e-mail объявление не будет опубликовано.",
            f"📧 E-mail {hint}\n\nEnter your e-mail. A valid e-mail is required to publish.",
            f"📧 אימייל {hint}\n\nהזן את האימייל שלך. אימייל נדרש לפרסום המודעה."
        )
        await update.message.reply_text(text, reply_markup=_back_kb(context), parse_mode="HTML")
        return ADD_EMAIL

    async def handle_email(self, update, context):
        email = update.message.text.strip().lower()
        import re
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            lang = get_lang(context)
            await update.message.reply_text(
                _L({"ru": "❌ Неверный формат e-mail. Попробуйте ещё раз.",
                 "en": "❌ Invalid e-mail format. Please try again.",
                 "he": "❌ כתובת אימייל שגויה. נסה שוב.", "fr": "❌ Format d'e-mail invalide. Réessayez."}, lang)
            )
            return ADD_EMAIL
        user_id = update.effective_user.id
        lang = get_lang(context)
        db.save_agent_email(user_id, email, lang)
        context.user_data["add_listing"]["agent_email"] = email
        await update.message.reply_text(
            _confirmed(context, "Email сохранён", "Email saved", "אימייל נשמר", f"📧 {email}"),
            parse_mode="HTML"
        )
        return await self._go_to_photos(update, context)

    async def handle_email_skip(self, update, context):
        query = update.callback_query
        await query.answer()
        return await self._go_to_photos(update, context, via_query=True)

    async def _go_to_photos(self, update, context, via_query=False):
        context.user_data["add_state"] = ADD_PHOTOS
        text = _step_text(context,
            "📸 Фотографии\n\nОтправьте фотографии объекта (до 10 штук).\nКогда закончите — нажмите кнопку ниже.",
            "📸 Photos\n\nSend photos of the property (up to 10).\nWhen done, press the button below.",
            "📸 תמונות\n\nשלח תמונות של הנכס (עד 10).\nכשתסיים, לחץ על הכפתור למטה."
        )
        if via_query:
            await update.callback_query.edit_message_text(text, reply_markup=_photos_keyboard(context, 0))
        else:
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

        deal_label = _L({"ru": "Аренда" if d.get("deal_type")=="rent" else "Продажа",
                      "en": "Rent" if d.get("deal_type")=="rent" else "Sale",
                      "he": "השכרה" if d.get("deal_type")=="rent" else "מכירה"}, lang)
        ptype_label = PROPERTY_TYPES.get(d.get("property_type","apartment"), {}).get(lang, "")
        photo_count = len(d.get("photos", []))
        photo_info = _L({"ru": f"{photo_count} фото" if photo_count else "нет фото",
                      "en": f"{photo_count} photo(s)" if photo_count else "no photos",
                      "he": f"{photo_count} תמונות" if photo_count else "אין תמונות"}, lang)

        summary_title = _step_text(context, "📋 Проверьте объявление:", "📋 Review your listing:", "📋 בדוק את המודעה:")
        owner_name = d.get("owner_name", "")
        owner_phone = d.get("owner_phone", "")
        contact = d.get("contact", "")
        seller_type = d.get("seller_type", "private")
        seller_label = {
            "agent":   {"ru": "🏢 Агент", "en": "🏢 Agent", "he": "🏢 סוכן", "fr": "🏢 Agent"},
            "private": {"ru": "👤 Частное лицо", "en": "👤 Private", "he": "👤 פרטי", "fr": "👤 Particulier"},
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
{'Телефон' if lang=='ru' else 'Phone' if lang=='en' else 'טלפון'}: {'скрыт' if lang=='ru' else 'hidden' if lang=='en' else 'מוסתר'} 🔒
{'Email' if True else ''}: {d.get('agent_email', '—')}
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
        lang = get_lang(context)
        user_id = update.effective_user.id

        # ── Required fields validation ────────────────────────────────────────
        required = ["deal_type", "property_type", "city", "rooms", "floor",
                    "area_sqm", "price", "owner_name", "owner_phone", "contact", "agent_email"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            field_names = {
                "deal_type": {"ru": "тип сделки", "en": "deal type", "he": "סוג עסקה"},
                "property_type": {"ru": "тип недвижимости", "en": "property type", "he": "סוג נכס"},
                "city": {"ru": "город", "en": "city", "he": "עיר"},
                "rooms": {"ru": "кол-во комнат", "en": "rooms", "he": "חדרים"},
                "floor": {"ru": "этаж", "en": "floor", "he": "קומה"},
                "area_sqm": {"ru": "площадь", "en": "area", "he": "שטח"},
                "price": {"ru": "цена", "en": "price", "he": "מחיר"},
                "owner_name": {"ru": "имя", "en": "name", "he": "שם"},
                "owner_phone": {"ru": "телефон", "en": "phone", "he": "טלפון"},
                "contact": {"ru": "контакт", "en": "contact", "he": "קשר"},
                "agent_email": {"ru": "e-mail", "en": "e-mail", "he": "אימייל"},
            }
            missing_str = ", ".join(field_names.get(f, {}).get(lang, f) for f in missing)
            msg = _L({
                "ru": f"⚠️ Не заполнены обязательные поля: {missing_str}.\n\nВернитесь и заполните их.",
                "en": f"⚠️ Required fields missing: {missing_str}.\n\nPlease go back and fill them in.",
                "he": f"⚠️ שדות חובה חסרים: {missing_str}.\n\nחזור ומלא אותם.",
            }, lang)
            await query.edit_message_text(msg, reply_markup=_confirm_keyboard(context))
            return ADD_CONFIRM

        d["user_id"] = user_id
        d["source"] = "user"
        d["title"] = f"{'Аренда' if d.get('deal_type')=='rent' else 'Продажа'}: {d.get('rooms','')} комн., {d.get('city','')}"
        if not d.get("photos"):
            d["photos"] = ["🏠"]
        d["neighborhood"] = d.get("neighborhood", "")

        # ── Agent paywall check ────────────────────────────────────────────────
        seller_type = d.get("seller_type", "private")

        # ── Private listing monthly limit ─────────────────────────────────────
        if seller_type == "private":
            count_this_month = db.count_user_private_listings_this_month(user_id)
            if count_this_month >= 1:
                msg = _L({
                    "ru": "⚠️ Частные лица могут публиковать <b>1 объявление в месяц</b>.\n\nВаш лимит на этот месяц исчерпан. Удалите старое объявление или подождите следующего месяца.",
                    "en": "⚠️ Private users may publish <b>1 listing per month</b>.\n\nYour monthly limit is reached. Delete your existing listing or wait for next month.",
                    "he": "⚠️ משתמשים פרטיים יכולים לפרסם <b>מודעה אחת בחודש</b>.\n\nהגעת למגבלה החודשית. מחק את המודעה הקיימת או המתן לחודש הבא.",
                }, lang)
                await query.edit_message_text(msg, parse_mode="HTML")
                return ConversationHandler.END

        if seller_type == "agent":
            # Free first listing — always granted once per account
            if not db.has_used_free_listing(user_id):
                db.mark_free_listing_used(user_id)
                # proceed to publish (fall through)
            elif db.get_listing_credits(user_id) > 0:
                # Purchased slot available
                db.use_listing_credit(user_id)
                # proceed to publish (fall through)
            else:
                # No free listing and no credits — show paywall
                # (works with or without PayPlus configured)
                await _show_agent_paywall(update, context, lang)
                return ADD_AWAIT_PAYMENT

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

        # ── Welcome message (Telegram + Email) ────────────────────────────
        lang = get_lang(context)
        try:
            await _send_welcome_message(context, update.effective_user.id, d, listing_id, lang)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Welcome message failed: {e}")

        return ConversationHandler.END

    async def handle_await_payment(self, update, context):
        """
        State: ADD_AWAIT_PAYMENT
        User is waiting to pay for an agent listing package.
        Callbacks:
          agent_pkg_{key}        — create PayPlus link and send it
          agent_check_payment    — check if credits arrived, publish if yes
          add_cancel             — cancel
        """
        query = update.callback_query
        await query.answer()
        lang = get_lang(context)
        data = query.data

        if data == "add_cancel":
            text = _step_text(context, "❌ Публикация отменена.", "❌ Publishing cancelled.", "❌ הפרסום בוטל.")
            await query.edit_message_text(text)
            return ConversationHandler.END

        if data == "agent_check_payment":
            user_id = update.effective_user.id
            if db.get_listing_credits(user_id) > 0:
                d = context.user_data.get("add_listing", {})

                if not d.get("deal_type"):
                    # Payment was upfront — listing not filled yet; proceed to deal type
                    label = _L({"ru": "🏢 Агент / Риелтор", "en": "🏢 Agent / Realtor", "he": "🏢 סוכן / מתווך"}, lang)
                    await query.edit_message_text(
                        _confirmed(context, "Тип продавца", "Seller type", "סוג המוכר", label),
                        parse_mode="HTML",
                    )
                    context.user_data["add_state"] = ADD_DEAL_TYPE
                    text = _step_text(context, "Шаг 2/16: Тип сделки", "Step 2/16: Deal type", "שלב 2/16: סוג עסקה")
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id, text=text,
                        reply_markup=_deal_keyboard(context), parse_mode="HTML"
                    )
                    return ADD_DEAL_TYPE

                # Listing already filled — publish now
                db.use_listing_credit(user_id)
                d["user_id"] = user_id
                if not d.get("photos"):
                    d["photos"] = ["🏠"]
                try:
                    from geocoding import get_city_coords
                    coords = get_city_coords(d.get("city", ""))
                    if coords:
                        d["lat"], d["lng"] = coords
                except Exception:
                    pass
                listing_id = db.add_listing(d)
                db.add_bonus_days(user_id, 3)
                credits_left = db.get_listing_credits(user_id)
                cr_msg = {"ru": f"Остаток слотов: {credits_left}", "en": f"Remaining slots: {credits_left}", "he": f"חריצים שנותרו: {credits_left}"}.get(lang, "")
                text = _step_text(context,
                    f"✅ Объявление опубликовано!\n\nID: #{listing_id}\n{cr_msg}",
                    f"✅ Listing published!\n\nID: #{listing_id}\n{cr_msg}",
                    f"✅ המודעה פורסמה!\n\nID: #{listing_id}\n{cr_msg}",
                )
                await query.edit_message_text(text)
                try:
                    await _send_welcome_message(context, user_id, d, listing_id, lang)
                except Exception:
                    pass
                return ConversationHandler.END
            else:
                # Still no credits
                msgs = {
                    "ru": "⏳ Оплата ещё не поступила. Завершите оплату и нажмите «✅ Я оплатил» снова.",
                    "en": "⏳ Payment not received yet. Complete payment and tap «✅ I paid» again.",
                    "he": "⏳ התשלום טרם התקבל. השלם את התשלום ולחץ שוב על «✅ שילמתי».",
                }
                await query.answer(msgs.get(lang, msgs["ru"]), show_alert=True)
                return ADD_AWAIT_PAYMENT

        if data.startswith("agent_pkg_"):
            pkg_key = data[len("agent_pkg_"):]
            import paypal_payment as _mp
            from pricing import get_agent_package
            pkg = get_agent_package(pkg_key)
            label = pkg["label"].get(lang, pkg["label"]["ru"]) if pkg else pkg_key
            price = pkg["price_ils"] if pkg else "?"
            cancel_btn = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}

            if _mp.is_enabled():
                result = _mp.create_agent_package_link(pkg_key, update.effective_user.id, lang)
                if result and result.get("url"):
                    check_btn = {
                        "ru": "✅ Я оплатил — опубликовать",
                        "en": "✅ I paid — publish",
                        "he": "✅ שילמתי — לפרסם",
                    }
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"💳 {label} — {price} ₪", url=result["url"])],
                        [InlineKeyboardButton(check_btn.get(lang, check_btn["ru"]), callback_data="agent_check_payment")],
                        [InlineKeyboardButton(cancel_btn.get(lang, cancel_btn["ru"]), callback_data="add_cancel")],
                    ])
                    msgs = {
                        "ru": f"💳 Нажмите кнопку ниже для оплаты <b>{label} — {price} ₪</b>.\n\nПосле оплаты нажмите «✅ Я оплатил — опубликовать».",
                        "en": f"💳 Tap the button below to pay for <b>{label} — {price} ₪</b>.\n\nAfter payment tap «✅ I paid — publish».",
                        "he": f"💳 לחץ על הכפתור למטה לתשלום <b>{label} — {price} ₪</b>.\n\nלאחר התשלום לחץ על «✅ שילמתי — לפרסם».",
                    }
                    await query.edit_message_text(msgs.get(lang, msgs["ru"]), reply_markup=keyboard, parse_mode="HTML")
                else:
                    err = {"ru": "⚠️ Ошибка создания ссылки. Попробуйте позже.", "en": "⚠️ Failed to create payment link. Try later.", "he": "⚠️ שגיאה ביצירת קישור. נסה שוב מאוחר יותר."}
                    await query.answer(err.get(lang, err["ru"]), show_alert=True)
            else:
                # PayPlus not yet configured — show "coming soon" info
                msgs = {
                    "ru": f"⏳ <b>Оплата картой скоро будет доступна!</b>\n\nВыбранный пакет: <b>{label} — {price} ₪</b>\n\nСвяжитесь с нами в Telegram для ручной активации слотов.",
                    "en": f"⏳ <b>Card payment coming soon!</b>\n\nSelected package: <b>{label} — {price} ₪</b>\n\nContact us in Telegram for manual slot activation.",
                    "he": f"⏳ <b>תשלום בכרטיס אשראי בקרוב!</b>\n\nחבילה נבחרת: <b>{label} — {price} ₪</b>\n\nצרו קשר בטלגרם להפעלה ידנית.",
                }
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Написать нам", url="https://t.me/flatfinderil_bot")],
                    [InlineKeyboardButton(cancel_btn.get(lang, cancel_btn["ru"]), callback_data="add_cancel")],
                ])
                await query.edit_message_text(msgs.get(lang, msgs["ru"]), reply_markup=keyboard, parse_mode="HTML")
            return ADD_AWAIT_PAYMENT

        # ── Crypto payment flow ──────────────────────────────────────────────
        if data == "agent_crypto":
            import cryptopay
            from pricing import AGENT_PACKAGES
            from config import PLAN_PRICES_USD
            if not cryptopay.is_enabled():
                msgs = {
                    "ru": "⏳ <b>Крипто-оплата скоро будет доступна!</b>\n\nСвяжитесь с нами в Telegram для ручной активации.",
                    "en": "⏳ <b>Crypto payment coming soon!</b>\n\nContact us in Telegram for manual activation.",
                    "he": "⏳ <b>תשלום בקריפטו בקרוב!</b>\n\nצרו קשר בטלגרם להפעלה ידנית.",
                }
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Написать нам", url="https://t.me/flatfinderil_bot")],
                    [InlineKeyboardButton({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}.get(lang, "◀ Back"), callback_data="add_cancel")],
                ])
                await query.edit_message_text(msgs.get(lang, msgs["ru"]), reply_markup=keyboard, parse_mode="HTML")
                return ADD_AWAIT_PAYMENT

            header = {"ru": "₿ Выберите пакет (цена в USD):", "en": "₿ Choose package (price in USD):", "he": "₿ בחר חבילה (מחיר ב-USD):"}.get(lang, "₿ Choose package:")
            rows = []
            for pkg in AGENT_PACKAGES:
                lbl = pkg["label"].get(lang, pkg["label"]["ru"])
                usd = PLAN_PRICES_USD.get(pkg["key"], "?")
                rows.append([InlineKeyboardButton(f"{lbl} — ${usd}", callback_data=f"agent_crypto_plan_{pkg['key']}")])
            rows.append([InlineKeyboardButton({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}.get(lang, "◀"), callback_data="add_cancel")])
            await query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(rows))
            return ADD_AWAIT_PAYMENT

        if data.startswith("agent_crypto_plan_"):
            pkg_key = data[len("agent_crypto_plan_"):]
            from pricing import get_agent_package
            from config import PLAN_PRICES_USD
            pkg = get_agent_package(pkg_key)
            label = pkg["label"].get(lang, pkg["label"]["ru"]) if pkg else pkg_key
            usd = PLAN_PRICES_USD.get(pkg_key, "?")
            header = {"ru": f"₿ {label} — ${usd}\n\nВыберите криптовалюту:", "en": f"₿ {label} — ${usd}\n\nChoose currency:", "he": f"₿ {label} — ${usd}\n\nבחר מטבע:"}.get(lang, f"₿ {label} — ${usd}\nChoose currency:")
            assets = [("USDT", "💵 USDT"), ("TON", "💎 TON"), ("BTC", "₿ BTC"), ("ETH", "Ξ ETH")]
            rows = [[InlineKeyboardButton(name, callback_data=f"agent_crypto_pay_{pkg_key}_{asset}")] for asset, name in assets]
            rows.append([InlineKeyboardButton({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}.get(lang, "◀"), callback_data="agent_crypto")])
            await query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(rows))
            return ADD_AWAIT_PAYMENT

        if data.startswith("agent_crypto_pay_"):
            # data = "agent_crypto_pay_agent_1_USDT" → strip prefix, rsplit once
            rest = data[len("agent_crypto_pay_"):]   # "agent_1_USDT"
            pkg_key, asset = rest.rsplit("_", 1)      # ("agent_1", "USDT")
            import cryptopay
            from pricing import get_agent_package
            from config import PLAN_PRICES_USD
            pkg = get_agent_package(pkg_key)
            label = pkg["label"].get(lang, pkg["label"]["ru"]) if pkg else pkg_key
            usd = PLAN_PRICES_USD.get(pkg_key, "?")
            invoice = cryptopay.create_invoice(pkg_key, update.effective_user.id, asset)
            if invoice and invoice.get("pay_url"):
                check_btn = {"ru": "✅ Я оплатил — опубликовать", "en": "✅ I paid — publish", "he": "✅ שילמתי — לפרסם"}.get(lang, "✅ I paid")
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"₿ Оплатить {usd} {asset}", url=invoice["pay_url"])],
                    [InlineKeyboardButton(check_btn, callback_data="agent_check_payment")],
                    [InlineKeyboardButton({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}.get(lang, "◀"), callback_data=f"agent_crypto_plan_{pkg_key}")],
                ])
                msgs = {
                    "ru": f"₿ Оплатите <b>{label}</b> — <b>${usd} {asset}</b> через @CryptoBot.\n\nПосле оплаты нажмите «✅ Я оплатил».",
                    "en": f"₿ Pay <b>{label}</b> — <b>${usd} {asset}</b> via @CryptoBot.\n\nAfter payment tap «✅ I paid».",
                    "he": f"₿ שלם עבור <b>{label}</b> — <b>${usd} {asset}</b> דרך @CryptoBot.\n\nלאחר התשלום לחץ «✅ שילמתי».",
                }
                await query.edit_message_text(msgs.get(lang, msgs["ru"]), reply_markup=keyboard, parse_mode="HTML")
            else:
                err = {"ru": "⚠️ Ошибка создания инвойса. Попробуйте позже.", "en": "⚠️ Invoice creation failed. Try later.", "he": "⚠️ שגיאה ביצירת חשבונית. נסה מאוחר יותר."}.get(lang, "⚠️ Error")
                await query.answer(err, show_alert=True)
            return ADD_AWAIT_PAYMENT

        # Unknown callback — re-show paywall
        await _show_agent_paywall(update, context, lang)
        return ADD_AWAIT_PAYMENT

    async def _warn_navigation(self, update, context):
        """Block any stray button press during the add-listing flow."""
        query = update.callback_query
        if query:
            lang = get_lang(context)
            msg = {
                "ru": "⚠️ Вы заполняете объявление.\nЧтобы выйти нажмите кнопку «❌ Отмена» или /cancel.",
                "en": "⚠️ You are filling in a listing.\nPress «❌ Cancel» or /cancel to exit.",
                "he": "⚠️ אתה ממלא מודעה כעת.\nלחץ «❌ ביטול» או /cancel כדי לצאת.",
                "fr": "⚠️ Vous remplissez une annonce.\nAppuyez sur «❌ Annuler» ou /cancel pour quitter.",
            }.get(lang, "⚠️ Listing in progress. Press ❌ Cancel to exit.")
            await query.answer(msg, show_alert=True)
        # Stay in current state
        return context.user_data.get("add_state", ADD_SELLER_TYPE)

    async def _warn_command(self, update, context):
        """Block commands like /start, /search during the add-listing flow."""
        lang = get_lang(context)
        msg = {
            "ru": "⚠️ Вы заполняете объявление. Сначала завершите его или отправьте /cancel для отмены.",
            "en": "⚠️ You are filling in a listing. Complete it or send /cancel to exit.",
            "he": "⚠️ אתה ממלא מודעה. השלם אותה או שלח /cancel לביטול.",
            "fr": "⚠️ Vous remplissez une annonce. Terminez-la ou envoyez /cancel pour annuler.",
        }.get(lang, "⚠️ Listing in progress. Send /cancel to exit.")
        await update.message.reply_text(msg)
        return context.user_data.get("add_state", ADD_SELLER_TYPE)

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
        # Очищаем недопечатанное добавление
        for k in ("new_listing", "add_state", "edit_listing"):
            context.user_data.pop(k, None)
        return ConversationHandler.END


# ── Welcome message after listing published ────────────────────────────────────

async def _send_welcome_message(context, user_id: int, listing: dict, listing_id: int, lang: str):
    """Send Telegram + Email welcome after listing is published."""
    import database as db

    deal_label = {
        "rent":       {"ru": "Аренда",       "en": "Rent",       "he": "שכירות", "fr": "Location"},
        "buy":        {"ru": "Продажа",       "en": "Sale",       "he": "מכירה", "fr": "Vente"},
        "sublet":     {"ru": "Сублет",        "en": "Sublet",     "he": "סאבלט", "fr": "Sous-location"},
        "commercial": {"ru": "Коммерческая",  "en": "Commercial", "he": "מסחרי", "fr": "Commercial"},
    }.get(listing.get("deal_type","rent"), {}).get(lang, listing.get("deal_type",""))

    name = listing.get("owner_name") or ""
    city = listing.get("city","")
    price = listing.get("price",0)

    is_agent = listing.get("seller_type") == "agent"

    if is_agent:
        tg_text = {
            "ru": (
                f"🏢 <b>FlatFinderIL — Объявление опубликовано!</b>\n\n"
                f"{'Здравствуйте, ' + name + '!' if name else 'Здравствуйте!'} Ваше объявление уже доступно для поиска тысячам пользователей.\n\n"
                f"📋 ID: <b>#{listing_id}</b>\n"
                f"📍 <b>{city}</b> · {deal_label} · <b>{price:,} ₪</b>\n\n"
                f"<b>Что дальше?</b>\n"
                f"• Раз в неделю вы получите отчёт о просмотрах на email\n"
                f"• Заинтересованные покупатели свяжутся с вами напрямую\n"
                f"• Управляйте объявлением в разделе 📋 <b>Мои объявления</b>\n\n"
                f"Желаем успешной сделки! 🤝"
            ),
            "en": (
                f"🏢 <b>FlatFinderIL — Listing Published!</b>\n\n"
                f"{'Hello, ' + name + '!' if name else 'Hello!'} Your listing is now live and searchable by thousands of users.\n\n"
                f"📋 ID: <b>#{listing_id}</b>\n"
                f"📍 <b>{city}</b> · {deal_label} · <b>{price:,} ₪</b>\n\n"
                f"<b>What's next?</b>\n"
                f"• You'll receive a weekly views report to your email\n"
                f"• Interested buyers will contact you directly\n"
                f"• Manage your listing in 📋 <b>My Listings</b>\n\n"
                f"Wishing you a successful deal! 🤝"
            ),
            "he": (
                f"🏢 <b>FlatFinderIL — המודעה פורסמה!</b>\n\n"
                f"{'שלום, ' + name + '!' if name else 'שלום!'} המודעה שלך פעילה ומאות משתמשים יכולים למצוא אותה.\n\n"
                f"📋 מזהה: <b>#{listing_id}</b>\n"
                f"📍 <b>{city}</b> · {deal_label} · <b>{price:,} ₪</b>\n\n"
                f"<b>מה הלאה?</b>\n"
                f"• תקבל/י דוח שבועי על צפיות לאימייל שלך\n"
                f"• קונים מתעניינים יפנו אליך ישירות\n"
                f"• נהל/י את המודעה תחת 📋 <b>המודעות שלי</b>\n\n"
                f"בהצלחה בעסקה! 🤝"
            ),
        }.get(lang, "")
    else:
        tg_text = {
            "ru": (
                f"🏠 <b>FlatFinderIL — Объявление опубликовано!</b>\n\n"
                f"{'Привет, ' + name + '!' if name else 'Привет!'} Ваше объявление успешно размещено!\n\n"
                f"📋 ID: <b>#{listing_id}</b>\n"
                f"📍 <b>{city}</b> · {deal_label} · <b>{price:,} ₪</b>\n\n"
                f"Пользователи уже находят его в поиске. Как только кто-то захочет связаться — "
                f"мы пришлём вам уведомление.\n\n"
                f"Управляйте объявлением через 📋 <b>Мои объявления</b>.\n\n"
                f"Удачи! 🙌"
            ),
            "en": (
                f"🏠 <b>FlatFinderIL — Listing Published!</b>\n\n"
                f"{'Hi, ' + name + '!' if name else 'Hi!'} Your listing is now live!\n\n"
                f"📋 ID: <b>#{listing_id}</b>\n"
                f"📍 <b>{city}</b> · {deal_label} · <b>{price:,} ₪</b>\n\n"
                f"Users can already find your listing in search. We'll notify you as soon as someone wants to get in touch.\n\n"
                f"Manage your listing under 📋 <b>My Listings</b>.\n\n"
                f"Good luck! 🙌"
            ),
            "he": (
                f"🏠 <b>FlatFinderIL — המודעה פורסמה!</b>\n\n"
                f"{'היי, ' + name + '!' if name else 'היי!'} המודעה שלך עלתה לאוויר!\n\n"
                f"📋 מזהה: <b>#{listing_id}</b>\n"
                f"📍 <b>{city}</b> · {deal_label} · <b>{price:,} ₪</b>\n\n"
                f"משתמשים כבר יכולים למצוא את המודעה שלך. נשלח לך התראה כשמישהו ירצה ליצור קשר.\n\n"
                f"נהל/י את המודעה תחת 📋 <b>המודעות שלי</b>.\n\n"
                f"!בהצלחה 🙌"
            ),
        }.get(lang, "")

    # Send Telegram message
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=tg_text,
            parse_mode="HTML"
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Telegram welcome send failed: {e}")

    # Send Email if agent has one
    email = db.get_agent_email(user_id)
    if not email:
        return

    subject = {
        "ru": f"🏠 Объявление #{listing_id} опубликовано — FlatFinderIL",
        "en": f"🏠 Listing #{listing_id} is live — FlatFinderIL",
        "he": f"🏠 המודעה #{listing_id} פורסמה — FlatFinderIL",
    }.get(lang, f"🏠 Listing #{listing_id} published — FlatFinderIL")

    greeting = _L({
        "ru": f"{'Здравствуйте, ' + name + '!' if name else 'Здравствуйте!'}",
        "en": f"{'Hello, ' + name + '!' if name else 'Hello!'}",
        "he": f"{'שלום, ' + name + '!' if name else 'שלום!'}",
    }, lang)

    if is_agent:
        body_text = {
            "ru": (f"Ваше объявление успешно опубликовано на платформе <b>FlatFinderIL</b> и уже отображается "
                   f"в результатах поиска. Тысячи пользователей ищут недвижимость прямо сейчас — "
                   f"ваше предложение уже среди них.<br><br>"
                   f"Каждую неделю вы будете получать отчёт о просмотрах на этот email."),
            "en": (f"Your listing has been published on <b>FlatFinderIL</b> and is already appearing "
                   f"in search results. Thousands of users are searching for properties right now — "
                   f"your listing is among them.<br><br>"
                   f"You will receive a weekly views report to this email address."),
            "he": (f"המודעה שלך פורסמה בהצלחה ב-<b>FlatFinderIL</b> ומופיעה כעת בתוצאות החיפוש. "
                   f"אלפי משתמשים מחפשים נכסים ממש עכשיו — ההצעה שלך כבר ביניהם.<br><br>"
                   f"כל שבוע תקבל/י דוח על מספר הצפיות לכתובת אימייל זו."),
        }.get(lang, "")
    else:
        body_text = {
            "ru": (f"Ваше объявление успешно опубликовано на платформе <b>FlatFinderIL</b>. "
                   f"Пользователи уже могут найти его в поиске по всему Израилю.<br><br>"
                   f"Как только кто-то захочет связаться с вами — вы получите уведомление в Telegram."),
            "en": (f"Your listing has been published on <b>FlatFinderIL</b>. "
                   f"Users can now find it in search results across Israel.<br><br>"
                   f"As soon as someone wants to contact you, you'll receive a notification in Telegram."),
            "he": (f"המודעה שלך פורסמה ב-<b>FlatFinderIL</b>. "
                   f"משתמשים יכולים כעת למצוא אותה בתוצאות החיפוש ברחבי ישראל.<br><br>"
                   f"ברגע שמישהו ירצה ליצור איתך קשר, תקבל/י התראה בטלגרם."),
        }.get(lang, "")
    body = body_text

    rtl = 'direction:rtl;text-align:right;' if lang == "he" else ''
    header_icon = "🏢" if is_agent else "🏠"
    platform_sub = {"ru":"Поиск недвижимости в Израиле","en":"Real Estate Search in Israel","he":'חיפוש נדל"ן בישראל', "fr": "Recherche immobilière en Israël"}.get(lang,"")
    lbl_id    = {"ru":"Номер объявления","en":"Listing ID","he":"מזהה מודעה", "fr": "ID annonce"}.get(lang,"ID")
    lbl_city  = {"ru":"Город","en":"City","he":"עיר", "fr": "Ville"}.get(lang,"City")
    lbl_type  = {"ru":"Тип сделки","en":"Deal type","he":"סוג עסקה", "fr": "Type de transaction"}.get(lang,"Type")
    lbl_price = {"ru":"Цена","en":"Price","he":"מחיר", "fr": "Prix"}.get(lang,"Price")
    badge_agent   = {"ru":"🏢 Агент","en":"🏢 Agent","he":"🏢 סוכן", "fr": "🏢 Agent"}.get(lang,"")
    badge_private = {"ru":"👤 Частное лицо","en":"👤 Private","he":"👤 פרטי", "fr": "👤 Particulier"}.get(lang,"")
    seller_badge  = badge_agent if is_agent else badge_private

    if is_agent:
        tips_html = {
            "ru": ("<li>Раз в неделю вам придёт отчёт о просмотрах</li>"
                   "<li>Управляйте объявлением в разделе <b>Мои объявления</b> в боте</li>"
                   "<li>Загружайте несколько объявлений сразу через CSV в кабинете агента</li>"),
            "en": ("<li>You'll receive a weekly views report to this address</li>"
                   "<li>Manage your listing in <b>My Listings</b> in the bot</li>"
                   "<li>Upload multiple listings at once via CSV in your agent cabinet</li>"),
            "he": ("<li>תקבל/י דוח שבועי על צפיות לכתובת זו</li>"
                   "<li>נהל/י את המודעה תחת <b>המודעות שלי</b> בבוט</li>"
                   "<li>העלה/י מספר מודעות בבת אחת דרך CSV בלוח הסוכן</li>"),
         "fr": "<li>Vous recevrez un rapport hebdomadaire des vues à cette adresse</li><li>Gérez votre annonce dans <b>Mes annonces</b> dans le bot</li><li>Téléversez plusieurs annonces à la fois via CSV dans votre espace agent</li>"}.get(lang, "")
    else:
        tips_html = {
            "ru": ("<li>Вы получите уведомление когда кто-то захочет связаться</li>"
                   "<li>Управляйте объявлением в разделе <b>Мои объявления</b> в боте</li>"),
            "en": ("<li>You'll be notified when someone wants to contact you</li>"
                   "<li>Manage your listing in <b>My Listings</b> in the bot</li>"),
            "he": ("<li>תקבל/י התראה כשמישהו ירצה ליצור קשר</li>"
                   "<li>נהל/י את המודעה תחת <b>המודעות שלי</b> בבוט</li>"),
         "fr": "<li>Vous serez notifié lorsque quelqu'un voudra vous contacter</li><li>Gérez votre annonce dans <b>Mes annonces</b> dans le bot</li>"}.get(lang, "")

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif">
<div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.10)">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#2AABEE 0%,#1a8cc8 100%);padding:28px 32px">
    <div style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-.3px">{header_icon} FlatFinderIL</div>
    <div style="font-size:12px;color:rgba(255,255,255,.82);margin-top:5px">{platform_sub}</div>
  </div>

  <!-- Body -->
  <div style="padding:28px 32px;{rtl}">
    <p style="font-size:18px;font-weight:700;color:#1a1a2e;margin:0 0 10px">{greeting}</p>
    <p style="font-size:14px;color:#444;line-height:1.65;margin:0 0 24px">{body}</p>

    <!-- Listing card -->
    <div style="background:#f7f9fc;border:1px solid #e2e8f0;border-radius:10px;padding:18px 22px;margin-bottom:24px">
      <div style="font-size:11px;font-weight:700;color:#2AABEE;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px">
        ✅ {"Детали объявления" if lang=="ru" else ("פרטי המודעה" if lang=="he" else "Listing details")}
      </div>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="font-size:12px;color:#888;padding:5px 0;width:45%">{lbl_id}</td>
            <td style="font-size:13px;font-weight:700;color:#1a1a2e;padding:5px 0">#{listing_id}</td></tr>
        <tr><td style="font-size:12px;color:#888;padding:5px 0">{lbl_city}</td>
            <td style="font-size:13px;color:#333;padding:5px 0">{city}</td></tr>
        <tr><td style="font-size:12px;color:#888;padding:5px 0">{lbl_type}</td>
            <td style="font-size:13px;color:#333;padding:5px 0">{deal_label}</td></tr>
        <tr><td style="font-size:12px;color:#888;padding:5px 0">{lbl_price}</td>
            <td style="font-size:14px;font-weight:700;color:#2AABEE;padding:5px 0">{price:,} ₪</td></tr>
        <tr><td style="font-size:12px;color:#888;padding:5px 0">{"Тип" if lang=="ru" else ("סוג מוכר" if lang=="he" else "Seller")}</td>
            <td style="font-size:12px;padding:5px 0"><span style="background:#e8f4fd;color:#2AABEE;border-radius:20px;padding:2px 10px;font-weight:600">{seller_badge}</span></td></tr>
      </table>
    </div>

    <!-- Tips -->
    <div style="background:#f0fdf4;border-left:3px solid #27AE60;border-radius:0 8px 8px 0;padding:14px 18px;margin-bottom:24px">
      <div style="font-size:12px;font-weight:700;color:#27AE60;margin-bottom:8px">
        {"Что дальше?" if lang=="ru" else ("מה הלאה?" if lang=="he" else "What's next?")}
      </div>
      <ul style="margin:0;padding-left:18px;font-size:13px;color:#444;line-height:1.7">{tips_html}</ul>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#f7f9fc;padding:16px 32px;border-top:1px solid #e2e8f0;text-align:center">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Israel Real Estate · @FlatFinderIL</p>
  </div>
</div>
</body></html>"""

    # Send via welcome_emails (SMTP → Resend fallback)
    try:
        import welcome_emails as _we
        if is_agent:
            _we.send_agent_welcome(
                user_id=user_id,
                lang=lang,
                name=name,
                email=email,
                listing_id=listing_id,
                city=listing.get("city", ""),
                price=listing.get("price", 0),
                deal_label=deal_label,
                is_agent=True,
            )
        else:
            _we.send_private_welcome(
                user_id=user_id,
                lang=lang,
                name=name,
                email=email,
                listing_id=listing_id,
                city=listing.get("city", ""),
                price=listing.get("price", 0),
                deal_label=deal_label,
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[WELCOME] Email send failed: {e}")
