"""
Pricing constants and helpers for FlatFinderIL.

Agents / Realtors
-----------------
  • 1st listing: FREE (one-time per account)
  • Packages are valid for 1 month (30 days) from purchase date:
      1  listing  →   70 ₪/мес
      5  listings →  300 ₪/мес  (60 ₪/ea)
     10  listings →  550 ₪/мес  (55 ₪/ea)
     20  listings → 1200 ₪/мес  (60 ₪/ea)
      ♾  unlimited → 3000 ₪/мес

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

# ── Cleaning ──────────────────────────────────────────────────────────────────
# Model: lead-balance — provider tops up balance, pays per unlocked contact

CLEANING_LEAD_PRICE_ILS = 50   # ₪ per lead (fixed)

# ── Packing ───────────────────────────────────────────────────────────────────
# Model: lead-balance — same as cleaning

PACKING_LEAD_PRICE_ILS  = 30   # ₪ per lead (fixed)

# ── Lead balance top-up packages (for cleaning & packing) ────────────────────

LEAD_BALANCE_PACKAGES = [
    {
        "key":       "balance_100",
        "amount_ils": 100,
        "label": {"ru": "💳 100 ₪", "en": "💳 100 ₪", "he": "💳 100 ₪"},
    },
    {
        "key":       "balance_200",
        "amount_ils": 200,
        "label": {"ru": "💳 200 ₪", "en": "💳 200 ₪", "he": "💳 200 ₪"},
    },
    {
        "key":       "balance_500",
        "amount_ils": 500,
        "label": {"ru": "💳 500 ₪  (+50 ₪ бонус)", "en": "💳 500 ₪  (+50 ₪ bonus)", "he": "💳 500 ₪  (+50 ₪ בונוס)"},
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
    return {"cleaning": CLEANING_LEAD_PRICE_ILS, "packers": PACKING_LEAD_PRICE_ILS}.get(svc_type, 0)


def format_service_pricing(svc_type: str, lang: str = "ru") -> str:
    """Return pricing info block for service provider type."""
    if svc_type == "movers":
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

    elif svc_type == "cleaning":
        if lang == "he":
            return (
                "💳 <b>תמחור — מודל יתרת לידים:</b>\n"
                "  · רישום בחינם\n"
                f"  · לראות פרטי קשר של לקוח — <b>{CLEANING_LEAD_PRICE_ILS} ₪ ללידים</b>\n"
                "  · מטעינים יתרה מראש, משלמים רק על פניות אמיתיות"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing — lead balance model:</b>\n"
                "  · Registration is free\n"
                f"  · Unlock client contact — <b>{CLEANING_LEAD_PRICE_ILS} ₪/lead</b>\n"
                "  · Top up balance in advance, pay only for real enquiries"
            )
        else:
            return (
                "💳 <b>Тарифы — система баланса лидов:</b>\n"
                "  · Регистрация бесплатно\n"
                f"  · Открыть контакт клиента — <b>{CLEANING_LEAD_PRICE_ILS} ₪/лид</b>\n"
                "  · Пополняете баланс заранее, платите только за реальные заявки"
            )

    elif svc_type == "packers":
        if lang == "he":
            return (
                "💳 <b>תמחור — מודל יתרת לידים:</b>\n"
                "  · רישום בחינם\n"
                f"  · לראות פרטי קשר של לקוח — <b>{PACKING_LEAD_PRICE_ILS} ₪ ללידים</b>\n"
                "  · מטעינים יתרה מראש, משלמים רק על פניות אמיתיות"
            )
        elif lang == "en":
            return (
                "💳 <b>Pricing — lead balance model:</b>\n"
                "  · Registration is free\n"
                f"  · Unlock client contact — <b>{PACKING_LEAD_PRICE_ILS} ₪/lead</b>\n"
                "  · Top up balance in advance, pay only for real enquiries"
            )
        else:
            return (
                "💳 <b>Тарифы — система баланса лидов:</b>\n"
                "  · Регистрация бесплатно\n"
                f"  · Открыть контакт клиента — <b>{PACKING_LEAD_PRICE_ILS} ₪/лид</b>\n"
                "  · Пополняете баланс заранее, платите только за реальные заявки"
            )

    return ""
