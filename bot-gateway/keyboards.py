from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from i18n import t, get_lang, get_property_type_name, get_district_name, get_infra_name, LANGUAGES
from city_translations import get_city_name

PTYPE_KEYS = ["apartment","house","villa","penthouse","studio","duplex"]
DISTRICT_KEYS = ["tel_aviv","jerusalem","haifa","sharon","center","south"]
INFRA_KEYS = ["kindergarten","school","mall","park","gym","hospital","beach","transport","restaurant","synagogue","public_pool"]
ROOMS_OPTIONS = ["1","1.5","2","2.5","3","3.5","4","4.5","5","5+"]
FLOOR_OPTIONS = ["Подвал","1","2","3","4","5","6-10","11-20","21+","Пентхаус"]
DISTRICT_CITIES = {
    "tel_aviv":["Тель-Авив","Рамат-Ган","Гиватаим","Бней-Брак","Бат-Ям","Холон","Ор-Иегуда"],
    "jerusalem":["Иерусалим","Бейт-Шемеш","Маале-Адумим"],
    "haifa":["Хайфа","Кирьят-Ата","Кирьят-Бялик","Тиверия","Акко","Нагария","Хадера"],
    "sharon":["Нетания","Кфар-Саба","Раанана","Герцлия","Ход-ха-Шарон","Эвен-Иегуда","Рош-аин","Рамат-ха-Шарон"],
    "center":["Петах-Тиква","Ришон-ле-Цион","Реховот","Нес-Циона","Лод","Рамла","Модиин"],
    "south":["Ашдод","Ашкелон","Беэр-Шева","Эйлат","Нетивот","Сдерот"],
}
ALL_CITIES = ["Тель-Авив","Иерусалим","Хайфа","Ришон-ле-Цион","Петах-Тиква","Ашдод","Нетания","Беэр-Шева","Бней-Брак","Холон","Рамат-Ган","Реховот","Ашкелон","Бат-Ям","Кфар-Саба","Хадера","Эйлат","Герцлия","Раанана","Лод","Нес-Циона","Ор-Иегуда","Модиин"]

def join_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔔 Вступить в сообщество / Join / הצטרף", callback_data="join")
    ]])

def language_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(label,callback_data=f"setlang_{code}")] for code,label in LANGUAGES.items()])

def main_menu_keyboard(ctx):
    lang = get_lang(ctx)
    sub_label = {"ru": "★ Подписка", "en": "★ Subscribe", "he": "★ מנוי", "fr": "★ Abonnement"}.get(lang, "★ Подписка")
    svc_label = {"ru": "🚚 Услуги", "en": "🚚 Services", "he": "🚚 שירותים", "fr": "🚚 Services"}.get(lang, "🚚 Услуги")
    contact_label = {"ru": "✉️ Написать нам", "en": "✉️ Contact us", "he": "✉️ כתוב לנו", "fr": "✉️ Nous écrire"}.get(lang, "✉️ Написать нам")
    insta_label   = {"ru": "📸 Instagram", "en": "📸 Instagram", "he": "📸 אינסטגרם", "fr": "📸 Instagram"}.get(lang, "📸 Instagram")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_search", ctx), callback_data="search"), InlineKeyboardButton(t("btn_favorites", ctx), callback_data="favorites")],
        [InlineKeyboardButton(t("btn_commercial", ctx), callback_data="commercial"), InlineKeyboardButton(svc_label, callback_data="services")],
        [InlineKeyboardButton(t("btn_my_listings", ctx), callback_data="my_listings"), InlineKeyboardButton(t("btn_add_listing", ctx), callback_data="add_listing")],
        [InlineKeyboardButton(t("btn_all_listings", ctx), callback_data="all_listings"), InlineKeyboardButton(t("btn_help", ctx), callback_data="help")],
        [InlineKeyboardButton(sub_label, callback_data="subscription"), InlineKeyboardButton(t("btn_my_subscriptions", ctx), callback_data="my_subscriptions")],
        [InlineKeyboardButton(t("btn_cabinet", ctx), callback_data="cabinet"), InlineKeyboardButton(t("btn_language", ctx), callback_data="choose_lang")],
        [InlineKeyboardButton(contact_label, callback_data="contact_admin"), InlineKeyboardButton(insta_label, url="https://www.instagram.com/flatfinderil/")],
    ])

def back_to_menu_keyboard(ctx):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back_menu",ctx),callback_data="back_to_menu")]])

def deal_type_keyboard(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_deal_buy",ctx),callback_data="deal_buy"),InlineKeyboardButton(t("btn_deal_rent",ctx),callback_data="deal_rent")],
        [InlineKeyboardButton(t("btn_deal_sublet",ctx),callback_data="deal_sublet")],
        [InlineKeyboardButton(t("btn_back_menu",ctx),callback_data="back_to_menu")],
    ])

def property_type_keyboard(ctx,selected=None):
    if selected is None: selected=[]
    lang=get_lang(ctx)
    keyboard=[]
    row=[]
    for key in PTYPE_KEYS:
        name=get_property_type_name(key,lang)
        mark="✅ " if key in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{name}",callback_data=f"ptype_{key}"))
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_all_types",ctx),callback_data="ptype_all")])
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back"),InlineKeyboardButton(t("btn_done",ctx),callback_data="ptype_next")])
    return InlineKeyboardMarkup(keyboard)

def district_keyboard(ctx):
    lang=get_lang(ctx)
    keyboard=[[InlineKeyboardButton(get_district_name(k,lang),callback_data=f"district_{k}")] for k in DISTRICT_KEYS]
    keyboard.append([InlineKeyboardButton(t("btn_all_israel",ctx),callback_data="district_all")])
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def city_keyboard(ctx,district_key=None):
    lang=get_lang(ctx)
    cities=DISTRICT_CITIES.get(district_key,ALL_CITIES) if district_key else ALL_CITIES
    keyboard=[]
    row=[]
    for city in cities:
        display=get_city_name(city,lang)
        row.append(InlineKeyboardButton(display,callback_data=f"city_{city}"))
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_any_city",ctx),callback_data="city_any")])
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def rooms_keyboard(ctx,label_from="rooms_min"):
    keyboard=[]
    row=[]
    for r in ROOMS_OPTIONS:
        row.append(InlineKeyboardButton(r,callback_data=f"{label_from}_{r}"))
        if len(row)==5: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_any_rooms",ctx),callback_data=f"{label_from}_any")])
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def rooms_range_keyboard(ctx,selected_min=None):
    keyboard=[]
    row=[]
    for r in ROOMS_OPTIONS:
        mark="📌 " if r==selected_min else ""
        row.append(InlineKeyboardButton(f"{mark}{r}",callback_data=f"rooms_max_{r}"))
        if len(row)==5: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_no_limit",ctx),callback_data="rooms_max_any")])
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def price_keyboard(ctx,options,prefix):
    keyboard=[]
    row=[]
    for value,label in options:
        row.append(InlineKeyboardButton(label,callback_data=f"{prefix}_{value}"))
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def parking_keyboard(ctx,prefix="park"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_no_parking",ctx),callback_data=f"{prefix}_0"),InlineKeyboardButton("1 🚗",callback_data=f"{prefix}_1")],
        [InlineKeyboardButton("2 🚗🚗",callback_data=f"{prefix}_2"),InlineKeyboardButton("3+ 🚗",callback_data=f"{prefix}_3")],
        [InlineKeyboardButton(t("btn_any_parking",ctx),callback_data=f"{prefix}_any")],
        [InlineKeyboardButton(t("btn_back",ctx),callback_data="back")],
    ])

def pool_keyboard(ctx,prefix="pool"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_pool_yes",ctx),callback_data=f"{prefix}_yes"),InlineKeyboardButton(t("btn_pool_any",ctx),callback_data=f"{prefix}_any")],
        [InlineKeyboardButton(t("btn_back",ctx),callback_data="back")],
    ])

def with_photos_keyboard(ctx):
    lang = get_lang(ctx)
    yes = {"ru": "📸 Только с фото", "en": "📸 With photos only", "he": "📸 עם תמונות בלבד", "fr": "📸 Avec photos uniquement"}.get(lang)
    any_ = {"ru": "🔄 Не важно", "en": "🔄 Any", "he": "🔄 לא משנה", "fr": "🔄 Peu importe"}.get(lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes, callback_data="photos_yes"),
         InlineKeyboardButton(any_, callback_data="photos_any")],
        [InlineKeyboardButton(t("btn_back", ctx), callback_data="back")],
    ])


def infrastructure_keyboard(ctx,selected=None):
    if selected is None: selected=[]
    lang=get_lang(ctx)
    keyboard=[]
    row=[]
    for key in INFRA_KEYS:
        name=get_infra_name(key,lang)
        mark="✅ " if key in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{name}",callback_data=f"infra_{key}"))
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_skip",ctx),callback_data="infra_skip"),InlineKeyboardButton(t("btn_done",ctx),callback_data="infra_done")])
    keyboard.append([InlineKeyboardButton(t("btn_back",ctx),callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def confirm_search_keyboard(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_find",ctx),callback_data="confirm_search"),InlineKeyboardButton(t("btn_reset",ctx),callback_data="reset_search")],
        [InlineKeyboardButton(t("btn_back_menu",ctx),callback_data="back_to_menu")],
    ])

def results_navigation_keyboard(ctx, current, total, listing_id, listing=None):
    nav_row = []
    if current > 0:
        nav_row.append(InlineKeyboardButton(t("btn_prev", ctx), callback_data=f"result_prev_{current}"))
    nav_row.append(InlineKeyboardButton(f"{current+1}/{total}", callback_data="noop"))
    if current < total - 1:
        nav_row.append(InlineKeyboardButton(t("btn_next", ctx), callback_data=f"result_next_{current}"))

    # Google Maps URL button — always use English city name for correct map resolution
    map_url = None
    if listing:
        import urllib.parse
        city_ru = listing.get("city", "")
        city_en = get_city_name(city_ru, "en")   # e.g. "Тель-Авив" → "Tel Aviv"
        neighborhood = listing.get("neighborhood", "")
        # Build query: neighborhood (if exists), English city, Israel
        query_parts = [p for p in [neighborhood, city_en, "Israel"] if p]
        map_query = ", ".join(query_parts)
        map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(map_query)}"

    lang = get_lang(ctx)
    show_phone_label = {"ru": "📞 Показать номер", "en": "📞 Show phone", "he": "📞 הצג מספר", "fr": "📞 Afficher le numéro"}.get(lang, "📞 Show phone")
    action_row = [
        InlineKeyboardButton(t("btn_to_fav", ctx), callback_data=f"fav_{listing_id}"),
        InlineKeyboardButton(t("btn_contact", ctx), callback_data=f"contact_{listing_id}"),
    ]
    phone_row = [
        InlineKeyboardButton(show_phone_label, callback_data=f"show_phone_{listing_id}"),
    ]
    if map_url:
        phone_row.append(InlineKeyboardButton(t("btn_map", ctx), url=map_url))

    extra_row = [
        InlineKeyboardButton(t("btn_request_view", ctx), callback_data=f"reqview_{listing_id}"),
        InlineKeyboardButton(t("btn_leave_review", ctx), callback_data=f"review_{listing_id}"),
    ]
    irented_label = {"ru": "🤝 Я снял/купил это", "en": "🤝 I rented/bought this", "he": "🤝 שכרתי/קניתי", "fr": "🤝 J'ai loué/acheté ceci"}.get(get_lang(ctx), "🤝 I rented this")
    irented_row = [InlineKeyboardButton(irented_label, callback_data=f"irented_{listing_id}")]
    sub_row = [
        InlineKeyboardButton(t("btn_subscribe_search", ctx), callback_data="subscribe_search"),
    ]
    return InlineKeyboardMarkup([
        nav_row,
        action_row,
        phone_row,
        extra_row,
        irented_row,
        sub_row,
        [InlineKeyboardButton(t("btn_new_search", ctx), callback_data="search")],
        [InlineKeyboardButton(t("btn_back_menu", ctx), callback_data="back_to_menu")],
    ])

def floor_keyboard(ctx):
    keyboard=[]
    row=[]
    for f in FLOOR_OPTIONS:
        row.append(InlineKeyboardButton(f,callback_data=f"floor_{f}"))
        if len(row)==3: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_cancel",ctx),callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def deal_type_add_keyboard(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_deal_buy",ctx),callback_data="add_deal_buy"),InlineKeyboardButton(t("btn_deal_rent",ctx),callback_data="add_deal_rent")],
        [InlineKeyboardButton(t("btn_cancel",ctx),callback_data="back_to_menu")],
    ])

def single_property_type_keyboard(ctx):
    lang=get_lang(ctx)
    keyboard=[]
    row=[]
    for key in PTYPE_KEYS:
        name=get_property_type_name(key,lang)
        row.append(InlineKeyboardButton(name,callback_data=f"add_ptype_{key}"))
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("btn_cancel",ctx),callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def add_confirm_keyboard(ctx):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_publish",ctx),callback_data="confirm_add"),InlineKeyboardButton(t("btn_cancel",ctx),callback_data="cancel_add")]])

def shelter_keyboard(ctx, prefix="shelter"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_shelter_mamad", ctx), callback_data=f"{prefix}_mamad"),
            InlineKeyboardButton(t("btn_shelter_miklat", ctx), callback_data=f"{prefix}_miklat"),
        ],
        [
            InlineKeyboardButton(t("btn_shelter_none", ctx), callback_data=f"{prefix}_none"),
            InlineKeyboardButton(t("btn_shelter_any", ctx), callback_data=f"{prefix}_any"),
        ],
        [InlineKeyboardButton(t("btn_back", ctx), callback_data="back")],
    ])

def district_multi_keyboard(ctx, selected=None):
    if selected is None: selected = []
    lang = get_lang(ctx)
    keyboard = []
    for k in DISTRICT_KEYS:
        name = get_district_name(k, lang)
        mark = "✅ " if k in selected else ""
        keyboard.append([InlineKeyboardButton(f"{mark}{name}", callback_data=f"district_{k}")])
    keyboard.append([
        InlineKeyboardButton(t("btn_all_israel", ctx), callback_data="district_all"),
        InlineKeyboardButton(t("btn_done", ctx), callback_data="dist_done"),
    ])
    keyboard.append([InlineKeyboardButton(t("btn_back", ctx), callback_data="dist_back")])
    return InlineKeyboardMarkup(keyboard)

def city_multi_keyboard(ctx, selected=None, districts=None):
    if selected is None: selected = []
    if districts is None: districts = []
    cities = []
    if districts:
        for d in districts:
            for c in DISTRICT_CITIES.get(d, []):
                if c not in cities:
                    cities.append(c)
    else:
        cities = ALL_CITIES
    keyboard = []
    row = []
    lang=get_lang(ctx)
    for city in cities:
        display=get_city_name(city,lang)
        mark = "✅ " if city in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{display}", callback_data=f"city_{city}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton(t("btn_any_city", ctx), callback_data="city_any"),
    ])
    keyboard.append([
        InlineKeyboardButton(t("btn_back", ctx), callback_data="cities_back"),
        InlineKeyboardButton(t("btn_done", ctx), callback_data="cities_done"),
    ])
    return InlineKeyboardMarkup(keyboard)

def subscription_keyboard(ctx):
    import payplus_payment
    rows = [
        [InlineKeyboardButton(t("btn_sub_week", ctx),         callback_data="sub_week")],
        [InlineKeyboardButton(t("btn_sub_two_weeks", ctx),    callback_data="sub_two_weeks")],
        [InlineKeyboardButton(t("btn_sub_month", ctx),        callback_data="sub_month")],
        [InlineKeyboardButton(t("btn_sub_search_alert", ctx), callback_data="sub_search_alert")],
    ]
    if payplus_payment.is_enabled():
        rows.append([InlineKeyboardButton("💳 Оплатить картой", callback_data="sub_card")])
    rows.append([InlineKeyboardButton("₿ Оплатить криптовалютой", callback_data="sub_crypto")])
    rows.append([InlineKeyboardButton(t("btn_back_menu", ctx),    callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def card_plan_keyboard(ctx):
    """Plan selection for PayPlus card payment."""
    from config import PLAN_PRICES_ILS
    week_price      = PLAN_PRICES_ILS.get("week", 19.9)
    two_weeks_price = PLAN_PRICES_ILS.get("two_weeks", 29.9)
    month_price     = PLAN_PRICES_ILS.get("month", 39.9)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"1 неделя — {week_price:.0f}₪",      callback_data="card_plan_week")],
        [InlineKeyboardButton(f"2 недели — {two_weeks_price:.0f}₪",  callback_data="card_plan_two_weeks")],
        [InlineKeyboardButton(f"1 месяц — {month_price:.0f}₪",       callback_data="card_plan_month")],
        [InlineKeyboardButton("◀ Назад",                              callback_data="subscription")],
    ])


def crypto_plan_keyboard(ctx):
    """Plan selection for crypto payment."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 неделя — $5.50 USDT",   callback_data="crypto_plan_week")],
        [InlineKeyboardButton("2 недели — $8.00 USDT",   callback_data="crypto_plan_two_weeks")],
        [InlineKeyboardButton("1 месяц — $11.00 USDT",   callback_data="crypto_plan_month")],
        [InlineKeyboardButton("◀ Назад",                  callback_data="subscription")],
    ])


def crypto_asset_keyboard(plan_key: str):
    """Currency selection for crypto payment."""
    assets = [("USDT (Tether)", "USDT"), ("TON (Toncoin)", "TON"),
              ("BTC (Bitcoin)", "BTC"),  ("ETH (Ethereum)", "ETH")]
    rows = [[InlineKeyboardButton(label, callback_data=f"crypto_pay_{plan_key}_{asset}")]
            for label, asset in assets]
    rows.append([InlineKeyboardButton("◀ Назад", callback_data="sub_crypto")])
    return InlineKeyboardMarkup(rows)


def paywall_keyboard(ctx):
    """Keyboard shown when user hits the paywall."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_subscribe_now", ctx), callback_data="subscription")],
        [InlineKeyboardButton(t("btn_back_menu", ctx),     callback_data="back_to_menu")],
    ])


def search_alert_confirm_keyboard(ctx):
    """Confirm screen for search_alert plan purchase."""
    lang = get_lang(ctx)
    confirm = {"ru": "✅ Активировать · 39.90 ₪/нед", "en": "✅ Activate · ₪39.90/wk", "he": "✅ הפעל · ₪39.90/שבוע", "fr": "✅ Activer · 39.90 ₪/sem"}.get(lang, "✅ Activate")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(confirm,                 callback_data="sub_search_alert_confirm")],
        [InlineKeyboardButton(t("btn_back_menu", ctx), callback_data="back_to_menu")],
    ])

def review_rating_keyboard(listing_id):
    """5-star rating keyboard for reviews."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐", callback_data=f"rate_{listing_id}_1"),
        InlineKeyboardButton("⭐⭐", callback_data=f"rate_{listing_id}_2"),
        InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate_{listing_id}_3"),
        InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate_{listing_id}_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate_{listing_id}_5"),
    ], [
        InlineKeyboardButton("« Назад / Back / חזרה", callback_data="back_to_menu"),
    ]])

def my_subscriptions_keyboard(ctx, subscriptions):
    """Shows list of subscriptions with unsubscribe buttons."""
    keyboard = []
    for i, sub in enumerate(subscriptions):
        label = f"📋 #{i+1}"
        keyboard.append([InlineKeyboardButton(label, callback_data="noop")])
        unsub_label = {"ru": f"❌ Отписаться #{i+1}", "en": f"❌ Unsubscribe #{i+1}", "he": f"❌ בטל מנוי #{i+1}", "fr": f"❌ Se désabonner #{i+1}"}.get(get_lang(ctx), f"❌ Unsubscribe #{i+1}")
        keyboard.append([InlineKeyboardButton(unsub_label, callback_data=f"unsub_{i}")])
    keyboard.append([InlineKeyboardButton(t("btn_back_menu", ctx), callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def cabinet_listings_keyboard(ctx, listings):
    """List of user listings with manage buttons."""
    lang = get_lang(ctx)
    keyboard = []
    for l in listings:
        title = l.get("title", f"#{l['id']}")[:30]
        active_mark = "🟢" if l.get("active", True) else "🔴"
        keyboard.append([InlineKeyboardButton(
            f"{active_mark} {title}",
            callback_data=f"cab_listing_{l['id']}"
        )])
    # Crypto payment button
    crypto_label = {"ru": "₿ Оплатить криптовалютой", "en": "₿ Pay with Crypto", "he": "₿ שלם בקריפטו", "fr": "₿ Payer en crypto"}.get(lang, "₿ Pay with Crypto")
    keyboard.append([InlineKeyboardButton(crypto_label, callback_data="sub_crypto")])
    keyboard.append([InlineKeyboardButton(t("btn_back_menu", ctx), callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def cabinet_listing_manage_keyboard(ctx, listing_id, active=True, deal_closed=False):
    """Edit / Delete / Toggle / Close deal buttons for a single listing."""
    lang = get_lang(ctx)
    edit_label   = {"ru": "✏️ Редактировать",   "en": "✏️ Edit",        "he": "✏️ ערוך",       "fr": "✏️ Modifier"}.get(lang, "✏️ Edit")
    delete_label = {"ru": "🗑️ Удалить",         "en": "🗑️ Delete",      "he": "🗑️ מחק",        "fr": "🗑️ Supprimer"}.get(lang, "🗑️ Delete")
    toggle_label = (
        {"ru": "🔴 Снять с публикации", "en": "🔴 Deactivate", "he": "🔴 כבה", "fr": "🔴 Désactiver"}.get(lang, "🔴 Deactivate")
        if active else
        {"ru": "🟢 Опубликовать снова", "en": "🟢 Activate",   "he": "🟢 הפעל", "fr": "🟢 Activer"}.get(lang, "🟢 Activate")
    )
    close_label  = {"ru": "✅ Сдано / Продано", "en": "✅ Deal closed",  "he": "✅ עסקה נסגרה", "fr": "✅ Loué / Vendu"}.get(lang, "✅ Deal closed")
    back_label   = {"ru": "« К списку",          "en": "« Back to list", "he": "« חזרה",        "fr": "« Retour à la liste"}.get(lang, "« Back")

    crypto_label = {"ru": "₿ Оплатить криптовалютой", "en": "₿ Pay with Crypto", "he": "₿ שלם בקריפטו", "fr": "₿ Payer en crypto"}.get(lang, "₿ Pay with Crypto")
    rows = [
        [InlineKeyboardButton(edit_label,   callback_data=f"edit_listing_{listing_id}"),
         InlineKeyboardButton(delete_label, callback_data=f"confirm_delete_{listing_id}")],
        [InlineKeyboardButton(toggle_label, callback_data=f"toggle_active_{listing_id}")],
        [InlineKeyboardButton(crypto_label, callback_data="sub_crypto")],
    ]
    if not deal_closed:
        rows.append([InlineKeyboardButton(close_label, callback_data=f"close_deal_{listing_id}")])
    rows.append([InlineKeyboardButton(back_label, callback_data="cabinet")])
    return InlineKeyboardMarkup(rows)


def edit_listing_keyboard(ctx, listing_id):
    """What field to edit."""
    lang = get_lang(ctx)
    price_label = {"ru": "💰 Изменить цену",     "en": "💰 Change price",       "he": "💰 שנה מחיר",    "fr": "💰 Modifier le prix"}.get(lang, "💰 Change price")
    desc_label  = {"ru": "📝 Изменить описание", "en": "📝 Edit description",   "he": "📝 ערוך תיאור",   "fr": "📝 Modifier la description"}.get(lang, "📝 Edit")
    back_label  = {"ru": "« Назад",              "en": "« Back",                "he": "« חזרה",           "fr": "« Retour"}.get(lang, "« Back")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(price_label, callback_data=f"editfield_price_{listing_id}")],
        [InlineKeyboardButton(desc_label,  callback_data=f"editfield_desc_{listing_id}")],
        [InlineKeyboardButton(back_label,  callback_data=f"cab_listing_{listing_id}")],
    ])


def confirm_delete_keyboard(ctx, listing_id):
    """Yes/No for deleting a listing."""
    lang = get_lang(ctx)
    yes_label = {"ru": "✅ Да, удалить",  "en": "✅ Yes, delete", "he": "✅ כן, מחק", "fr": "✅ Oui, supprimer"}.get(lang, "✅ Delete")
    no_label  = {"ru": "❌ Нет, оставить","en": "❌ No, keep",    "he": "❌ לא",      "fr": "❌ Non, conserver"}.get(lang, "❌ No")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label, callback_data=f"do_delete_{listing_id}"),
        InlineKeyboardButton(no_label,  callback_data=f"cab_listing_{listing_id}"),
    ]])


def close_deal_select_keyboard(ctx, listing_id, requesters):
    """Owner selects which requester they closed deal with."""
    lang = get_lang(ctx)
    keyboard = []
    for r in requesters[:8]:  # max 8 buttons
        uid = r.get("user_id")
        name = r.get("name") or r.get("username") or str(uid)
        keyboard.append([InlineKeyboardButton(
            f"👤 {name[:30]}",
            callback_data=f"deal_tenant_{listing_id}_{uid}"
        )])
    # Option: close without specifying tenant
    anyway_label = {"ru": "✅ Закрыть без выбора", "en": "✅ Close without selecting", "he": "✅ סגור ללא בחירה", "fr": "✅ Clôturer sans sélectionner"}.get(lang, "✅ Close")
    cancel_label = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול", "fr": "❌ Annuler"}.get(lang, "❌ Cancel")
    keyboard.append([InlineKeyboardButton(anyway_label, callback_data=f"deal_tenant_{listing_id}_0")])
    keyboard.append([InlineKeyboardButton(cancel_label, callback_data=f"cab_listing_{listing_id}")])
    return InlineKeyboardMarkup(keyboard)


def deal_confirm_price_keyboard(ctx, listing_id, tenant_id):
    """After owner entered price — final confirm."""
    lang = get_lang(ctx)
    yes_label    = {"ru": "✅ Подтвердить сделку", "en": "✅ Confirm deal",  "he": "✅ אשר עסקה", "fr": "✅ Confirmer la transaction"}.get(lang, "✅ Confirm")
    cancel_label = {"ru": "❌ Отмена",             "en": "❌ Cancel",        "he": "❌ ביטול",    "fr": "❌ Annuler"}.get(lang, "❌ Cancel")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes_label,    callback_data=f"deal_confirm_{listing_id}_{tenant_id}")],
        [InlineKeyboardButton(cancel_label, callback_data=f"cab_listing_{listing_id}")],
    ])


def tenant_deal_confirm_keyboard(ctx, listing_id):
    """Tenant confirms 'I rented/bought this'."""
    lang = get_lang(ctx)
    yes_label    = {"ru": "✅ Да, я снял/купил", "en": "✅ Yes, I did",  "he": "✅ כן, שכרתי/קניתי", "fr": "✅ Oui, j'ai loué/acheté"}.get(lang, "✅ Yes")
    cancel_label = {"ru": "❌ Нет",               "en": "❌ No",          "he": "❌ לא",               "fr": "❌ Non"}.get(lang, "❌ No")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label,    callback_data=f"irented_confirm_{listing_id}"),
        InlineKeyboardButton(cancel_label, callback_data="noop"),
    ]])


def owner_deal_confirm_keyboard(ctx, listing_id, tenant_id):
    """Owner confirms deal initiated by tenant."""
    lang = get_lang(ctx)
    yes_label = {"ru": "✅ Подтвердить", "en": "✅ Confirm", "he": "✅ אשר", "fr": "✅ Confirmer"}.get(lang, "✅ Yes")
    no_label  = {"ru": "❌ Отклонить",  "en": "❌ Decline",  "he": "❌ דחה", "fr": "❌ Refuser"}.get(lang, "❌ No")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label, callback_data=f"deal_tenant_{listing_id}_{tenant_id}"),
        InlineKeyboardButton(no_label,  callback_data="noop"),
    ]])


def elevator_keyboard(ctx, prefix="elevator"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_elevator_yes", ctx), callback_data=f"{prefix}_yes"),
            InlineKeyboardButton(t("btn_elevator_any", ctx), callback_data=f"{prefix}_any"),
        ],
        [InlineKeyboardButton(t("btn_back", ctx), callback_data="back")],
    ])


def commercial_deal_keyboard(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_deal_rent", ctx), callback_data="comm_deal_rent"),
         InlineKeyboardButton(t("btn_deal_buy", ctx), callback_data="comm_deal_buy")],
        [InlineKeyboardButton(t("btn_back_menu", ctx), callback_data="back_to_menu")],
    ])


def commercial_type_keyboard(ctx, selected=[]):
    from config import COMMERCIAL_TYPES
    rows = []
    for key, label in COMMERCIAL_TYPES.items():
        check = "✅ " if key in selected else ""
        rows.append([InlineKeyboardButton(check + label, callback_data=f"comm_type_{key}")])
    rows.append([
        InlineKeyboardButton(t("btn_skip", ctx), callback_data="comm_type_all"),
        InlineKeyboardButton(t("btn_back", ctx), callback_data="comm_back"),
    ])
    return InlineKeyboardMarkup(rows)


def commercial_city_keyboard(ctx):
    rows = []
    for i in range(0, len(ALL_CITIES), 2):
        row = [InlineKeyboardButton(ALL_CITIES[i], callback_data=f"comm_city_{ALL_CITIES[i]}")]
        if i + 1 < len(ALL_CITIES):
            row.append(InlineKeyboardButton(ALL_CITIES[i + 1], callback_data=f"comm_city_{ALL_CITIES[i + 1]}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("🌍 Весь Израиль", callback_data="comm_city_all"),
        InlineKeyboardButton(t("btn_back", ctx), callback_data="comm_back"),
    ])
    return InlineKeyboardMarkup(rows)


def commercial_price_keyboard(ctx, prefix, deal_type):
    if deal_type == "rent":
        options = [("0", "Любая"), ("3000", "от 3 000 ₪"), ("5000", "от 5 000 ₪"), ("10000", "от 10 000 ₪"), ("20000", "от 20 000 ₪"), ("50000", "от 50 000 ₪")]
        options_max = [("0", "Любая"), ("5000", "до 5 000 ₪"), ("10000", "до 10 000 ₪"), ("20000", "до 20 000 ₪"), ("50000", "до 50 000 ₪"), ("999999999", "без лимита")]
    else:
        options = [("0", "Любая"), ("500000", "от 500 тыс."), ("1000000", "от 1 млн"), ("2000000", "от 2 млн"), ("5000000", "от 5 млн"), ("10000000", "от 10 млн")]
        options_max = [("0", "Любая"), ("1000000", "до 1 млн"), ("2000000", "до 2 млн"), ("5000000", "до 5 млн"), ("10000000", "до 10 млн"), ("999999999", "без лимита")]
    opts = options if prefix == "comm_pricemin" else options_max
    rows = [[InlineKeyboardButton(label, callback_data=f"{prefix}_{val}")] for val, label in opts]
    rows.append([InlineKeyboardButton(t("btn_back", ctx), callback_data="comm_back")])
    return InlineKeyboardMarkup(rows)
