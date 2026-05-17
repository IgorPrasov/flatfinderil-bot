import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8047585631:AAH9OTvRuJWEMBieIyaZRBPEalOda6nLo0Q")

# ─── PayPlus (Cardcom) payment settings ─────────────────────────────────────
PAYPLUS_API_KEY    = os.environ.get("PAYPLUS_API_KEY", "")
PAYPLUS_SECRET_KEY = os.environ.get("PAYPLUS_SECRET_KEY", "")
PAYPLUS_PAGE_UID   = os.environ.get("PAYPLUS_PAGE_UID", "")

# ─── Subscription pricing (env-overridable) ─────────────────────────────────
# Single source of truth for all subscription prices. Values can be overridden
# by environment variables for staging/A-B testing without a code deploy.
def _f(env, default):
    try:
        return float(os.environ.get(env, default))
    except (TypeError, ValueError):
        return float(default)

def _i(env, default):
    try:
        return int(os.environ.get(env, default))
    except (TypeError, ValueError):
        return int(default)

# Days per plan
SUB_DAYS_WEEK         = _i("SUB_DAYS_WEEK", 7)
SUB_DAYS_TWO_WEEKS    = _i("SUB_DAYS_TWO_WEEKS", 14)
SUB_DAYS_MONTH        = _i("SUB_DAYS_MONTH", 30)
SUB_DAYS_SEARCH_ALERT = _i("SUB_DAYS_SEARCH_ALERT", 7)

# ILS prices (used for Telegram card / Stars-as-ILS displays)
SUB_PRICE_WEEK_ILS         = _f("SUB_PRICE_WEEK_ILS", 19.90)
SUB_PRICE_TWO_WEEKS_ILS    = _f("SUB_PRICE_TWO_WEEKS_ILS", 29.90)
SUB_PRICE_MONTH_ILS        = _f("SUB_PRICE_MONTH_ILS", 39.90)
SUB_PRICE_SEARCH_ALERT_ILS = _f("SUB_PRICE_SEARCH_ALERT_ILS", 39.90)

# USD prices for CryptoPay (paid in USDT/TON/BTC/ETH equivalent)
SUB_PRICE_WEEK_USD      = os.environ.get("SUB_PRICE_WEEK_USD", "5.50")
SUB_PRICE_TWO_WEEKS_USD = os.environ.get("SUB_PRICE_TWO_WEEKS_USD", "8.00")
SUB_PRICE_MONTH_USD     = os.environ.get("SUB_PRICE_MONTH_USD", "11.00")

# Telegram Stars amount per plan (XTR currency)
SUB_STARS_WEEK         = _i("SUB_STARS_WEEK", 399)
SUB_STARS_TWO_WEEKS    = _i("SUB_STARS_TWO_WEEKS", 399)
SUB_STARS_MONTH        = _i("SUB_STARS_MONTH", 399)
SUB_STARS_SEARCH_ALERT = _i("SUB_STARS_SEARCH_ALERT", 399)
SUB_STARS_DEFAULT      = _i("SUB_STARS_DEFAULT", 399)

# Aggregated dictionaries — preferred for downstream consumers
PLAN_PRICES_ILS = {
    "week":         SUB_PRICE_WEEK_ILS,
    "two_weeks":    SUB_PRICE_TWO_WEEKS_ILS,
    "month":        SUB_PRICE_MONTH_ILS,
    "search_alert": SUB_PRICE_SEARCH_ALERT_ILS,
}
PLAN_PRICES_USD = {
    "week":            SUB_PRICE_WEEK_USD,
    "two_weeks":       SUB_PRICE_TWO_WEEKS_USD,
    "month":           SUB_PRICE_MONTH_USD,
    # Agent listing packages — ILS price / 3.65 (rounded)
    "agent_1":         "19",
    "agent_5":         "82",
    "agent_10":        "151",
    "agent_20":        "274",
    "agent_unlimited": "822",
}
PLAN_DAYS = {
    "week":         SUB_DAYS_WEEK,
    "two_weeks":    SUB_DAYS_TWO_WEEKS,
    "month":        SUB_DAYS_MONTH,
    "search_alert": SUB_DAYS_SEARCH_ALERT,
}
PLAN_STARS = {
    "week":         SUB_STARS_WEEK,
    "two_weeks":    SUB_STARS_TWO_WEEKS,
    "month":        SUB_STARS_MONTH,
    "search_alert": SUB_STARS_SEARCH_ALERT,
}


PROPERTY_TYPES = {
    "apartment": "🏢 Квартира",
    "house": "🏠 Дом",
    "villa": "🏡 Вилла",
    "penthouse": "🌆 Пентхаус",
    "studio": "🛋 Студия",
    "duplex": "🏘 Дуплекс",
}

DISTRICTS = {
    "tel_aviv": {"name": "Тель-Авив и центр", "cities": ["Тель-Авив","Рамат-Ган","Гиватаим","Бней-Брак","Бат-Ям","Холон","Ор-Иегуда","Азур","Яhуд-Моносон"]},
    "jerusalem": {"name": "Иерусалим", "cities": ["Иерусалим","Бейт-Шемеш","Маале-Адумим"]},
    "haifa": {"name": "Хайфа и север", "cities": ["Хайфа","Кирьят-Ата","Кирьят-Бялик","Тиверия","Акко","Нагария","Хадера","Пардес-Хана","Кирьят-Хаим","Кирьят-Ям"]},
    "sharon": {"name": "Sharon (Шарон)", "cities": ["Нетания","Кфар-Саба","Раанана","Герцлия","Ход-ха-Шарон","Эвен-Иегуда"]},
    "center": {"name": "Центральный округ", "cities": ["Петах-Тиква","Ришон-ле-Цион","Реховот","Нес-Циона","Лод","Рамла","Модиин","Рош-аин","Рош-ха-Аин","Гдера"]},
    "south": {"name": "Юг", "cities": ["Ашдод","Ашкелон","Беэр-Шева","Эйлат","Нетивот","Сдерот"]},
}

INFRASTRUCTURE = {
    "kindergarten": "🧒 Детский сад",
    "school": "🏫 Школа",
    "mall": "🛒 Торговый центр",
    "park": "🌳 Парк",
    "gym": "💪 Спортзал",
    "hospital": "🏥 Больница",
    "beach": "🏖 Пляж",
    "transport": "🚌 Общественный транспорт",
    "restaurant": "🍽 Рестораны",
    "synagogue": "🕍 Синагога",
}

PRICE_RENT_MIN_OPTIONS_RU = [
    ("0", "от любой"), ("2000", "от 2 000 ₪"), ("3000", "от 3 000 ₪"),
    ("5000", "от 5 000 ₪"), ("8000", "от 8 000 ₪"), ("12000", "от 12 000 ₪"),
    ("20000", "от 20 000 ₪"),
]
PRICE_RENT_MIN_OPTIONS_EN = [
    ("0", "Any"), ("2000", "from 2,000 ₪"), ("3000", "from 3,000 ₪"),
    ("5000", "from 5,000 ₪"), ("8000", "from 8,000 ₪"), ("12000", "from 12,000 ₪"),
    ("20000", "from 20,000 ₪"),
]
PRICE_RENT_MIN_OPTIONS_HE = [
    ("0", "כל מחיר"), ("2000", "מ 2,000 ₪"), ("3000", "מ 3,000 ₪"),
    ("5000", "מ 5,000 ₪"), ("8000", "מ 8,000 ₪"), ("12000", "מ 12,000 ₪"),
    ("20000", "מ 20,000 ₪"),
]
PRICE_RENT_MIN_OPTIONS = PRICE_RENT_MIN_OPTIONS_RU
PRICE_RENT_OPTIONS_RU = [
    ("0", "Любая"), ("2000", "до 2 000 ₪"), ("3000", "до 3 000 ₪"),
    ("5000", "до 5 000 ₪"), ("8000", "до 8 000 ₪"), ("12000", "до 12 000 ₪"),
    ("20000", "до 20 000 ₪"), ("999999999", "без лимита"),
]
PRICE_RENT_OPTIONS_EN = [
    ("0", "Any"), ("2000", "up to 2,000 ₪"), ("3000", "up to 3,000 ₪"),
    ("5000", "up to 5,000 ₪"), ("8000", "up to 8,000 ₪"), ("12000", "up to 12,000 ₪"),
    ("20000", "up to 20,000 ₪"), ("999999999", "no limit"),
]
PRICE_RENT_OPTIONS_HE = [
    ("0", "כל מחיר"), ("2000", "עד 2,000 ₪"), ("3000", "עד 3,000 ₪"),
    ("5000", "עד 5,000 ₪"), ("8000", "עד 8,000 ₪"), ("12000", "עד 12,000 ₪"),
    ("20000", "עד 20,000 ₪"), ("999999999", "ללא הגבלה"),
]
PRICE_RENT_OPTIONS = PRICE_RENT_OPTIONS_RU
PRICE_BUY_MIN_OPTIONS_RU = [
    ("0", "от любой"), ("500000", "от 500 тыс."), ("1000000", "от 1 млн"),
    ("2000000", "от 2 млн"), ("3000000", "от 3 млн"), ("5000000", "от 5 млн"),
    ("8000000", "от 8 млн"),
]
PRICE_BUY_MIN_OPTIONS_EN = [
    ("0", "Any"), ("500000", "from 500K"), ("1000000", "from 1M"),
    ("2000000", "from 2M"), ("3000000", "from 3M"), ("5000000", "from 5M"),
    ("8000000", "from 8M"),
]
PRICE_BUY_MIN_OPTIONS_HE = [
    ("0", "כל מחיר"), ("500000", "מ 500K"), ("1000000", "מ 1M"),
    ("2000000", "מ 2M"), ("3000000", "מ 3M"), ("5000000", "מ 5M"),
    ("8000000", "מ 8M"),
]
PRICE_BUY_MIN_OPTIONS = PRICE_BUY_MIN_OPTIONS_RU
PRICE_BUY_OPTIONS_RU = [
    ("0", "Любая"), ("500000", "до 500 тыс."), ("1000000", "до 1 млн"),
    ("2000000", "до 2 млн"), ("3000000", "до 3 млн"), ("5000000", "до 5 млн"),
    ("8000000", "до 8 млн"), ("999999999", "без лимита"),
]
PRICE_BUY_OPTIONS_EN = [
    ("0", "Any"), ("500000", "up to 500K"), ("1000000", "up to 1M"),
    ("2000000", "up to 2M"), ("3000000", "up to 3M"), ("5000000", "up to 5M"),
    ("8000000", "up to 8M"), ("999999999", "no limit"),
]
PRICE_BUY_OPTIONS_HE = [
    ("0", "כל מחיר"), ("500000", "עד 500K"), ("1000000", "עד 1M"),
    ("2000000", "עד 2M"), ("3000000", "עד 3M"), ("5000000", "עד 5M"),
    ("8000000", "עד 8M"), ("999999999", "ללא הגבלה"),
]
PRICE_BUY_OPTIONS = PRICE_BUY_OPTIONS_RU

ROOMS_OPTIONS = ["1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5", "5+"]
FLOOR_OPTIONS = ["Подвал", "1", "2", "3", "4", "5", "6-10", "11-20", "21+", "Пентхаус"]

(
    SEARCH_TYPE, SEARCH_PROPERTY_TYPE, SEARCH_DISTRICT, SEARCH_CITY,
    SEARCH_ROOMS, SEARCH_ROOMS_MAX, SEARCH_PRICE_MIN, SEARCH_PRICE_MAX,
    SEARCH_PARKING, SEARCH_POOL, SEARCH_SHELTER, SEARCH_ELEVATOR, SEARCH_INFRASTRUCTURE, SEARCH_WITH_PHOTOS, SEARCH_CONFIRM,
    ADD_TITLE, ADD_PROPERTY_TYPE, ADD_CITY, ADD_DISTRICT_AREA,
    ADD_ROOMS, ADD_PRICE, ADD_PARKING, ADD_POOL, ADD_FLOOR,
    ADD_INFRASTRUCTURE, ADD_DESCRIPTION, ADD_CONTACT, ADD_CONFIRM
) = range(28)

SHELTER_OPTIONS = {
    "mamad": "🛡 Мамад (комната безопасности)",
    "miklat": "🏛 Миклат (бомбоубежище)",
    "none": "❌ Нет",
    "any": "🔄 Неважно",
}

COMMERCIAL_TYPES = {
    "office": "🏢 Офис",
    "retail": "🏪 Магазин/Ретейл",
    "warehouse": "🏭 Склад",
    "coworking": "💼 Коворкинг",
    "restaurant_space": "🍽 Помещение под кафе/ресторан",
    "other_commercial": "🏗 Другое",
}

COMMERCIAL_DEAL, COMMERCIAL_TYPE, COMMERCIAL_CITY, COMMERCIAL_PRICE_MIN, COMMERCIAL_PRICE_MAX, COMMERCIAL_CONFIRM = range(28, 34)
