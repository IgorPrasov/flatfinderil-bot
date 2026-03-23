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

def language_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(label,callback_data=f"setlang_{code}")] for code,label in LANGUAGES.items()])

def main_menu_keyboard(ctx):
    lang = get_lang(ctx)
    sub_label = {"ru": "★ Подписка", "en": "★ Subscribe", "he": "★ מנוי"}.get(lang, "★ Подписка")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_search", ctx), callback_data="search"), InlineKeyboardButton(t("btn_favorites", ctx), callback_data="favorites")],
        [InlineKeyboardButton(t("btn_my_listings", ctx), callback_data="my_listings"), InlineKeyboardButton(t("btn_add_listing", ctx), callback_data="add_listing")],
        [InlineKeyboardButton(t("btn_all_listings", ctx), callback_data="all_listings"), InlineKeyboardButton(t("btn_help", ctx), callback_data="help")],
        [InlineKeyboardButton(sub_label, callback_data="subscription"), InlineKeyboardButton(t("btn_my_subscriptions", ctx), callback_data="my_subscriptions")],
        [InlineKeyboardButton(t("btn_cabinet", ctx), callback_data="cabinet")],
        [InlineKeyboardButton(t("btn_language", ctx), callback_data="choose_lang")],
    ])

def back_to_menu_keyboard(ctx):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back_menu",ctx),callback_data="back_to_menu")]])

def deal_type_keyboard(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_deal_buy",ctx),callback_data="deal_buy"),InlineKeyboardButton(t("btn_deal_rent",ctx),callback_data="deal_rent")],
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
    yes = {"ru": "📸 Только с фото", "en": "📸 With photos only", "he": "📸 עם תמונות בלבד"}.get(lang)
    any_ = {"ru": "🔄 Не важно", "en": "🔄 Any", "he": "🔄 לא משנה"}.get(lang)
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

    # Google Maps URL button
    map_url = None
    if listing:
        neighborhood = listing.get("neighborhood", "")
        city = listing.get("city", "")
        query_parts = [p for p in [neighborhood, city, "Israel"] if p]
        map_query = ", ".join(query_parts)
        import urllib.parse
        map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(map_query)}"

    action_row = [
        InlineKeyboardButton(t("btn_to_fav", ctx), callback_data=f"fav_{listing_id}"),
        InlineKeyboardButton(t("btn_contact", ctx), callback_data=f"contact_{listing_id}"),
    ]
    if map_url:
        action_row.append(InlineKeyboardButton(t("btn_map", ctx), url=map_url))

    extra_row = [
        InlineKeyboardButton(t("btn_request_view", ctx), callback_data=f"reqview_{listing_id}"),
        InlineKeyboardButton(t("btn_leave_review", ctx), callback_data=f"review_{listing_id}"),
    ]
    sub_row = [
        InlineKeyboardButton(t("btn_subscribe_search", ctx), callback_data="subscribe_search"),
    ]
    return InlineKeyboardMarkup([
        nav_row,
        action_row,
        extra_row,
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_sub_week", ctx),      callback_data="sub_week")],
        [InlineKeyboardButton(t("btn_sub_two_weeks", ctx), callback_data="sub_two_weeks")],
        [InlineKeyboardButton(t("btn_sub_month", ctx),     callback_data="sub_month")],
        [InlineKeyboardButton(t("btn_back_menu", ctx),     callback_data="back_to_menu")],
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
        unsub_label = {"ru": f"❌ Отписаться #{i+1}", "en": f"❌ Unsubscribe #{i+1}", "he": f"❌ בטל מנוי #{i+1}"}.get(get_lang(ctx), f"❌ Unsubscribe #{i+1}")
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
    keyboard.append([InlineKeyboardButton(t("btn_back_menu", ctx), callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def cabinet_listing_manage_keyboard(ctx, listing_id, active=True):
    """Edit / Delete / Toggle buttons for a single listing."""
    lang = get_lang(ctx)
    edit_label   = {"ru": "✏️ Редактировать", "en": "✏️ Edit",   "he": "✏️ ערוך"}.get(lang, "✏️ Edit")
    delete_label = {"ru": "🗑️ Удалить",       "en": "🗑️ Delete", "he": "🗑️ מחק"}.get(lang, "🗑️ Delete")
    toggle_label = (
        {"ru": "🔴 Снять с публикации", "en": "🔴 Deactivate", "he": "🔴 כבה"}.get(lang, "🔴 Deactivate")
        if active else
        {"ru": "🟢 Опубликовать снова", "en": "🟢 Activate",   "he": "🟢 הפעל"}.get(lang, "🟢 Activate")
    )
    back_label   = {"ru": "« К списку",        "en": "« Back to list", "he": "« חזרה"}.get(lang, "« Back")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(edit_label,   callback_data=f"edit_listing_{listing_id}"),
         InlineKeyboardButton(delete_label, callback_data=f"confirm_delete_{listing_id}")],
        [InlineKeyboardButton(toggle_label, callback_data=f"toggle_active_{listing_id}")],
        [InlineKeyboardButton(back_label,   callback_data="cabinet")],
    ])


def edit_listing_keyboard(ctx, listing_id):
    """What field to edit."""
    lang = get_lang(ctx)
    price_label = {"ru": "💰 Изменить цену",     "en": "💰 Change price",       "he": "💰 שנה מחיר"}.get(lang, "💰 Change price")
    desc_label  = {"ru": "📝 Изменить описание", "en": "📝 Edit description",   "he": "📝 ערוך תיאור"}.get(lang, "📝 Edit")
    back_label  = {"ru": "« Назад",              "en": "« Back",                "he": "« חזרה"}.get(lang, "« Back")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(price_label, callback_data=f"editfield_price_{listing_id}")],
        [InlineKeyboardButton(desc_label,  callback_data=f"editfield_desc_{listing_id}")],
        [InlineKeyboardButton(back_label,  callback_data=f"cab_listing_{listing_id}")],
    ])


def confirm_delete_keyboard(ctx, listing_id):
    """Yes/No for deleting a listing."""
    lang = get_lang(ctx)
    yes_label = {"ru": "✅ Да, удалить",  "en": "✅ Yes, delete", "he": "✅ כן, מחק"}.get(lang, "✅ Delete")
    no_label  = {"ru": "❌ Нет, оставить","en": "❌ No, keep",    "he": "❌ לא"}.get(lang, "❌ No")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label, callback_data=f"do_delete_{listing_id}"),
        InlineKeyboardButton(no_label,  callback_data=f"cab_listing_{listing_id}"),
    ]])


def elevator_keyboard(ctx, prefix="elevator"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_elevator_yes", ctx), callback_data=f"{prefix}_yes"),
            InlineKeyboardButton(t("btn_elevator_any", ctx), callback_data=f"{prefix}_any"),
        ],
        [InlineKeyboardButton(t("btn_back", ctx), callback_data="back")],
    ])
