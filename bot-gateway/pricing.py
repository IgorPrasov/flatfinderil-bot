"""
Pricing constants and helpers for FlatFinderIL.

Agents / Realtors
-----------------
  • 1st listing: FREE (one-time per account)
  • Packages (purchased listing slots):
      1  listing  →   70 ₪
      5  listings →  300 ₪  (60 ₪/ea)
     10  listings →  550 ₪  (55 ₪/ea)
     20  listings → 1200 ₪  (60 ₪/ea)

Movers / הובלות
---------------
  • Base: 150 ₪/week — entry in city database
  • TOP placement per city: +50 ₪/city/week

Cleaning / ניקיון
-----------------
  • Per-lead model: 40–60 ₪/lead

Packing / אריזה
---------------
  • Commission: 15% of order value
"""

from typing import Optional

# ── Agent packages ────────────────────────────────────────────────────────────

AGENT_FREE_COUNT = 1          # first listing is free, once per account

AGENT_PACKAGES = [
    {
        "key":       "agent_1",
        "count":     1,
        "price_ils": 70,
        "label": {"ru": "1 объявление",   "en": "1 listing",   "he": "מודעה אחת"},
        "note":  {"ru": "",                "en": "",             "he": ""},
    },
    {
        "key":       "agent_5",
        "count":     5,
        "price_ils": 300,
        "label": {"ru": "5 объявлений",   "en": "5 listings",  "he": "5 מודעות"},
        "note":  {"ru": "60 ₪/шт",        "en": "60 ₪/ea",     "he": "60 ₪ ליחידה"},
    },
    {
        "key":       "agent_10",
        "count":     10,
        "price_ils": 550,
        "label": {"ru": "10 объявлений",  "en": "10 listings", "he": "10 מודעות"},
        "note":  {"ru": "55 ₪/шт",        "en": "55 ₪/ea",     "he": "55 ₪ ליחידה"},
    },
    {
        "key":       "agent_20",
        "count":     20,
        "price_ils": 1200,
        "label": {"ru": "20 объявлений",  "en": "20 listings", "he": "20 מודעות"},
        "note":  {"ru": "60 ₪/шт",        "en": "60 ₪/ea",     "he": "60 ₪ ליחידה"},
    },
]

# ── Movers ────────────────────────────────────────────────────────────────────

MOVER_WEEKLY_BASE_ILS  = 150   # ₪/week — basic DB entry
MOVER_TOP_CITY_ILS     = 50    # ₪/week per city — TOP placement

MOVER_PACKAGES = [
    {
        "key":       "mover_base",
        "price_ils": MOVER_WEEKLY_BASE_ILS,
        "label": {
            "ru": "📋 База — присутствие в базе",
            "en": "📋 Base — listed in database",
            "he": "📋 בסיס — רישום במאגר",
        },
        "desc": {
            "ru": f"Ваша компания видна всем пользователям платформы · {MOVER_WEEKLY_BASE_ILS} ₪/нед",
            "en": f"Your company visible to all platform users · {MOVER_WEEKLY_BASE_ILS} ₪/week",
            "he": f"החברה שלך גלויה לכל משתמשי הפלטפורמה · {MOVER_WEEKLY_BASE_ILS} ₪/שבוע",
        },
    },
    {
        "key":       "mover_top",
        "price_ils": MOVER_WEEKLY_BASE_ILS + MOVER_TOP_CITY_ILS,
        "label": {
            "ru": "⭐ ТОП — первое место в городе",
            "en": "⭐ TOP — first place in city",
            "he": "⭐ TOP — מקום ראשון בעיר",
        },
        "desc": {
            "ru": f"База + ТОП-место в выбранном городе · {MOVER_WEEKLY_BASE_ILS + MOVER_TOP_CITY_ILS} ₪/нед",
            "en": f"Base + TOP placement in chosen city · {MOVER_WEEKLY_BASE_ILS + MOVER_TOP_CITY_ILS} ₪/week",
            "he": f"בסיס + מיקום TOP בעיר הנבחרת · {MOVER_WEEKLY_BASE_ILS + MOVER_TOP_CITY_ILS} ₪/שבוע",
        },
    },
]

# ── Cleaning ──────────────────────────────────────────────────────────────────

CLEANING_LEAD_PRICE_MIN = 40   # ₪ per lead
CLEANING_LEAD_PRICE_MAX = 60   # ₪ per lead

# ── Packing ───────────────────────────────────────────────────────────────────

PACKING_COMMISSION_PCT = 15    # % of order value


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_agent_package(key: str) -> Optional[dict]:
    """Return package dict by key, or None."""
    return next((p for p in AGENT_PACKAGES if p["key"] == key), None)


def get_mover_package(key: str) -> Optional[dict]:
    """Return mover package dict by key, or None."""
    return next((p for p in MOVER_PACKAGES if p["key"] == key), None)


def format_agent_pricing(lang: str = "ru") -> str:
    """Return a human-readable pricing block for the agent paywall message."""
    lines = {
        "ru": [
            "💳 <b>Пакеты объявлений:</b>",
            "",
        ],
        "en": [
            "💳 <b>Listing packages:</b>",
            "",
        ],
        "he": [
            "💳 <b>חבילות מודעות:</b>",
            "",
        ],
    }.get(lang, ["💳 <b>Packages:</b>", ""])

    for pkg in AGENT_PACKAGES:
        label = pkg["label"].get(lang, pkg["label"]["ru"])
        note  = pkg["note"].get(lang, "")
        note_str = f" ({note})" if note else ""
        lines.append(f"  · {label} — <b>{pkg['price_ils']} ₪</b>{note_str}")

    return "\n".join(lines)


def format_service_pricing(svc_type: str, lang: str = "ru") -> str:
    """Return pricing info block for service provider type."""
    if svc_type == "movers":
        if lang == "he":
            return (
                "💳 <b>תמחור:</b>\n"
                f"  · רישום במאגר — <b>{MOVER_WEEKLY_BASE_ILS} ₪/שבוע</b>\n"
                f"  · + מיקום TOP בעיר — <b>+{MOVER_TOP_CITY_ILS} ₪/שבוע לעיר</b>"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing:</b>\n"
                f"  · Listed in database — <b>{MOVER_WEEKLY_BASE_ILS} ₪/week</b>\n"
                f"  · + TOP placement per city — <b>+{MOVER_TOP_CITY_ILS} ₪/week per city</b>"
            )
        else:
            return (
                "💳 <b>Тарифы:</b>\n"
                f"  · Присутствие в базе — <b>{MOVER_WEEKLY_BASE_ILS} ₪/неделя</b>\n"
                f"  · + ТОП-место в городе — <b>+{MOVER_TOP_CITY_ILS} ₪/нед за город</b>"
            )

    elif svc_type == "cleaning":
        if lang == "he":
            return (
                "💳 <b>תמחור:</b>\n"
                f"  · תשלום עבור ליד — <b>{CLEANING_LEAD_PRICE_MIN}–{CLEANING_LEAD_PRICE_MAX} ₪ ללידim</b>\n"
                "  · אין תשלום קבוע — משלמים רק על פניות אמיתיות"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing:</b>\n"
                f"  · Per lead — <b>{CLEANING_LEAD_PRICE_MIN}–{CLEANING_LEAD_PRICE_MAX} ₪/lead</b>\n"
                "  · No fixed fee — pay only for real enquiries"
            )
        else:
            return (
                "💳 <b>Тарифы:</b>\n"
                f"  · За лид — <b>{CLEANING_LEAD_PRICE_MIN}–{CLEANING_LEAD_PRICE_MAX} ₪/лид</b>\n"
                "  · Без абонплаты — платите только за реальные обращения"
            )

    elif svc_type == "packers":
        if lang == "he":
            return (
                "💳 <b>תמחור:</b>\n"
                f"  · עמלה — <b>{PACKING_COMMISSION_PCT}% מסכום ההזמנה</b>\n"
                "  · אין תשלום קבוע — עמלה רק על עסקאות מוצלחות"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing:</b>\n"
                f"  · Commission — <b>{PACKING_COMMISSION_PCT}% of order value</b>\n"
                "  · No fixed fee — commission on completed orders only"
            )
        else:
            return (
                "💳 <b>Тарифы:</b>\n"
                f"  · Комиссия — <b>{PACKING_COMMISSION_PCT}% от суммы заказа</b>\n"
                "  · Без абонплаты — процент только с выполненных заказов"
            )

    return ""
