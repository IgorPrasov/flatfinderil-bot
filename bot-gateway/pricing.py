"""
Pricing constants and helpers for FlatFinderIL.

Agents / Realtors
-----------------
  • 1st listing: FREE (one-time per account)
  • Packages are valid for 1 month (30 days) from purchase date:
      1  listing  →   70 ₪/мес
      5  listings →  300 ₪/мес  (60 ₪/ea)
     10  listings →  550 ₪/мес  (55 ₪/ea)
     20  listings → 1000 ₪/мес  (50 ₪/ea)
      ♾  unlimited → 3000 ₪/мес

Movers / הובלות
---------------
  • Base: 70 ₪/month — entry in city database
  • TOP placement per city: +100 ₪/city/week

Cleaning / ניקיון  |  Packing / אריזה
--------------------------------------
  • Presence in database: 70 ₪/month
  • Unlock client lead contact: 50 ₪/lead
"""

from typing import Optional

# ── Agent packages ────────────────────────────────────────────────────────────

AGENT_FREE_COUNT   = 1   # first listing is free, once per account
AGENT_PACKAGE_DAYS = 30  # all packages valid for 30 days from purchase

AGENT_PACKAGES = [
    {
        "key":          "agent_1",
        "count":        1,
        "price_ils":    70,
        "duration_days": AGENT_PACKAGE_DAYS,
        "label": {"ru": "1 объявление",   "en": "1 listing",   "he": "מודעה אחת"},
        "note":  {"ru": "на 1 месяц",     "en": "for 1 month", "he": "לחודש אחד"},
    },
    {
        "key":          "agent_5",
        "count":        5,
        "price_ils":    300,
        "duration_days": AGENT_PACKAGE_DAYS,
        "label": {"ru": "5 объявлений",   "en": "5 listings",  "he": "5 מודעות"},
        "note":  {"ru": "60 ₪/шт · 1 мес", "en": "60 ₪/ea · 1 mo", "he": "60 ₪ ליחידה · חודש"},
    },
    {
        "key":          "agent_10",
        "count":        10,
        "price_ils":    550,
        "duration_days": AGENT_PACKAGE_DAYS,
        "label": {"ru": "10 объявлений",  "en": "10 listings", "he": "10 מודעות"},
        "note":  {"ru": "55 ₪/шт · 1 мес", "en": "55 ₪/ea · 1 mo", "he": "55 ₪ ליחידה · חודש"},
    },
    {
        "key":          "agent_20",
        "count":        20,
        "price_ils":    1000,
        "duration_days": AGENT_PACKAGE_DAYS,
        "label": {"ru": "20 объявлений",  "en": "20 listings", "he": "20 מודעות"},
        "note":  {"ru": "50 ₪/шт · 1 мес", "en": "50 ₪/ea · 1 mo", "he": "50 ₪ ליחידה · חודש"},
    },
    {
        "key":          "agent_unlimited",
        "count":        999999,
        "price_ils":    3000,
        "duration_days": AGENT_PACKAGE_DAYS,
        "label": {"ru": "♾ Безлимит",     "en": "♾ Unlimited", "he": "♾ ללא הגבלה"},
        "note":  {"ru": "неограниченно · 1 мес", "en": "unlimited · 1 mo", "he": "ללא הגבלה · חודש"},
    },
]

# ── Movers ────────────────────────────────────────────────────────────────────
# Model: fixed monthly base + optional weekly TOP placement

MOVER_MONTHLY_BASE_ILS = 70    # ₪/month — basic DB entry
MOVER_TOP_WEEKLY_ILS   = 100   # ₪/week — TOP placement (first rows in city results)

MOVER_PACKAGES = [
    {
        "key":          "mover_base",
        "price_ils":    MOVER_MONTHLY_BASE_ILS,
        "duration_days": 30,
        "label": {
            "ru": "📋 База — присутствие в базе",
            "en": "📋 Base — listed in database",
            "he": "📋 בסיס — רישום במאגר",
        },
        "desc": {
            "ru": f"Компания видна всем пользователям платформы · {MOVER_MONTHLY_BASE_ILS} ₪/мес",
            "en": f"Your company visible to all platform users · {MOVER_MONTHLY_BASE_ILS} ₪/month",
            "he": f"החברה שלך גלויה לכל משתמשי הפלטפורמה · {MOVER_MONTHLY_BASE_ILS} ₪/חודש",
        },
    },
    {
        "key":          "mover_top",
        "price_ils":    MOVER_TOP_WEEKLY_ILS,
        "duration_days": 7,
        "label": {
            "ru": "⭐ ТОП — первые строчки в городе",
            "en": "⭐ TOP — first rows in city results",
            "he": "⭐ TOP — שורות ראשונות בתוצאות העיר",
        },
        "desc": {
            "ru": f"Первые строчки в выдаче бота по городу · {MOVER_TOP_WEEKLY_ILS} ₪/нед",
            "en": f"First rows in bot results for your city · {MOVER_TOP_WEEKLY_ILS} ₪/week",
            "he": f"שורות ראשונות בתוצאות הבוט בעיר · {MOVER_TOP_WEEKLY_ILS} ₪/שבוע",
        },
    },
]

# ── Cleaning & Packing ────────────────────────────────────────────────────────
# Model: monthly subscription (presence) + per-lead unlock fee

SERVICE_MONTHLY_BASE_ILS = 70   # ₪/month — to appear in the directory
CLEANING_LEAD_PRICE_ILS  = 50   # ₪ per lead unlock
PACKING_LEAD_PRICE_ILS   = 50   # ₪ per lead unlock

# Subscription package shared by cleaning and packing
SERVICE_PACKAGES = [
    {
        "key":          "service_base",
        "price_ils":    SERVICE_MONTHLY_BASE_ILS,
        "duration_days": 30,
        "label": {
            "ru": "📋 Присутствие в базе — 1 месяц",
            "en": "📋 Listed in database — 1 month",
            "he": "📋 רישום במאגר — חודש 1",
        },
    },
]

# ── Lead balance top-up packages (for cleaning & packing) ────────────────────

LEAD_BALANCE_PACKAGES = [
    {
        "key":       "balance_100",
        "amount_ils": 100,
        "label": {"ru": "💳 100 ₪ (2 лида)", "en": "💳 100 ₪ (2 leads)", "he": "💳 100 ₪ (2 לידים)"},
    },
    {
        "key":       "balance_250",
        "amount_ils": 250,
        "label": {"ru": "💳 250 ₪ (5 лидов)", "en": "💳 250 ₪ (5 leads)", "he": "💳 250 ₪ (5 לידים)"},
    },
    {
        "key":       "balance_500",
        "amount_ils": 500,
        "label": {"ru": "💳 500 ₪ (10+ лидов)", "en": "💳 500 ₪ (10+ leads)", "he": "💳 500 ₪ (10+ לידים)"},
        "bonus_ils": 50,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_agent_package(key: str) -> Optional[dict]:
    """Return package dict by key, or None."""
    return next((p for p in AGENT_PACKAGES if p["key"] == key), None)


def get_mover_package(key: str) -> Optional[dict]:
    """Return mover package dict by key, or None."""
    return next((p for p in MOVER_PACKAGES if p["key"] == key), None)


def get_service_package(key: str) -> Optional[dict]:
    """Return cleaning/packing service package by key, or None."""
    return next((p for p in SERVICE_PACKAGES if p["key"] == key), None)


def format_agent_pricing(lang: str = "ru") -> str:
    """Return a human-readable pricing block for the agent paywall message."""
    lines = {
        "ru": [
            "💳 <b>Пакеты объявлений на 1 месяц:</b>",
            "",
        ],
        "en": [
            "💳 <b>Listing packages · 1 month:</b>",
            "",
        ],
        "he": [
            "💳 <b>חבילות מודעות לחודש אחד:</b>",
            "",
        ],
    }.get(lang, ["💳 <b>Packages:</b>", ""])

    for pkg in AGENT_PACKAGES:
        label = pkg["label"].get(lang, pkg["label"]["ru"])
        note  = pkg["note"].get(lang, "")
        note_str = f" ({note})" if note else ""
        lines.append(f"  · {label} — <b>{pkg['price_ils']} ₪/мес</b>{note_str}" if lang == "ru"
                     else f"  · {label} — <b>{pkg['price_ils']} ₪/mo</b>{note_str}" if lang == "en"
                     else f"  · {label} — <b>{pkg['price_ils']} ₪/חודש</b>{note_str}")

    return "\n".join(lines)


def get_lead_price(svc_type: str) -> int:
    """Return per-lead price in ₪ for lead-balance service types."""
    return {"cleaning": CLEANING_LEAD_PRICE_ILS, "packing": PACKING_LEAD_PRICE_ILS}.get(svc_type, 0)


def format_service_pricing(svc_type: str, lang: str = "ru") -> str:
    """Return pricing info block for service provider type."""
    if svc_type == "moving":
        if lang == "he":
            return (
                "💳 <b>תמחור:</b>\n"
                f"  · רישום בסיסי במאגר — <b>{MOVER_MONTHLY_BASE_ILS} ₪/חודש</b>\n"
                f"  · ⭐ TOP בעיר (שורות ראשונות) — <b>{MOVER_TOP_WEEKLY_ILS} ₪/שבוע</b>\n"
                "  · ניתן לשלם רק על הבסיס, TOP הוא אופציונלי"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing:</b>\n"
                f"  · Base listing — <b>{MOVER_MONTHLY_BASE_ILS} ₪/month</b>\n"
                f"  · ⭐ TOP in city (first rows) — <b>{MOVER_TOP_WEEKLY_ILS} ₪/week</b>\n"
                "  · Base only is fine, TOP is optional"
            )
        else:
            return (
                "💳 <b>Тарифы:</b>\n"
                f"  · Базовое присутствие в базе — <b>{MOVER_MONTHLY_BASE_ILS} ₪/мес</b>\n"
                f"  · ⭐ ТОП в городе (первые строчки) — <b>{MOVER_TOP_WEEKLY_ILS} ₪/нед</b>\n"
                "  · Можно только базу, ТОП — по желанию"
            )

    elif svc_type in ("cleaning", "packing"):
        lead_price = CLEANING_LEAD_PRICE_ILS  # same for both
        if lang == "he":
            return (
                "💳 <b>תמחור:</b>\n"
                f"  · נוכחות במאגר — <b>{SERVICE_MONTHLY_BASE_ILS} ₪/חודש</b>\n"
                f"  · פתיחת פרטי לקוח — <b>{lead_price} ₪/ליד</b>"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing:</b>\n"
                f"  · Listed in database — <b>{SERVICE_MONTHLY_BASE_ILS} ₪/month</b>\n"
                f"  · Unlock client contact — <b>{lead_price} ₪/lead</b>"
            )
        else:
            return (
                "💳 <b>Тарифы:</b>\n"
                f"  · Присутствие в базе — <b>{SERVICE_MONTHLY_BASE_ILS} ₪/мес</b>\n"
                f"  · Открытие контакта клиента — <b>{lead_price} ₪/лид</b>"
            )

    return ""
