"""
morning_digest.py — Утренняя аналитическая сводка FlatFinderIL.

Формат:
  📊 Аналитика дня (Нетания)
  Сегодня появилось 15 новых квартир.
  Средняя цена выросла на 2%.
  Самый выгодный район сегодня — Агамим.

Запуск:
  • Автоматически: планировщик в bot.py запускает в 09:00 IL каждый день
  • Вручную:       python3 morning_digest.py --city "Нетания" --lang ru

Отправляет подписчикам через Telegram или выводит в консоль (--dry-run).
"""

import os
import sys
import logging
import statistics
from datetime import datetime, timedelta, date
from collections import defaultdict
from typing import Optional

log = logging.getLogger("morning_digest")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── i18n-метки для дайджеста ─────────────────────────────────────────────────

_LABELS = {
    "header": {
        "ru": "📊 <b>Аналитика дня</b>",
        "en": "📊 <b>Daily Analytics</b>",
        "he": "📊 <b>ניתוח יומי</b>",
        "fr": "📊 <b>Analyse du jour</b>",
    },
    "new_listings": {
        "ru": "🏠 Сегодня появилось <b>{n}</b> новых объявлений.",
        "en": "🏠 <b>{n}</b> new listings appeared today.",
        "he": "🏠 היום הופיעו <b>{n}</b> מודעות חדשות.",
        "fr": "🏠 <b>{n}</b> nouvelles annonces aujourd'hui.",
    },
    "new_private": {
        "ru": "👤 Из них <b>{n}</b> от частных лиц (без агентов).",
        "en": "👤 Of those, <b>{n}</b> from private owners.",
        "he": "👤 מתוכם <b>{n}</b> מבעלים פרטיים.",
        "fr": "👤 Dont <b>{n}</b> de particuliers.",
    },
    "avg_price": {
        "ru": "💰 Средняя цена аренды: <b>{price} ₪/мес</b>",
        "en": "💰 Average rent: <b>{price} ₪/mo</b>",
        "he": "💰 מחיר שכירות ממוצע: <b>{price} ₪/חודש</b>",
        "fr": "💰 Loyer moyen: <b>{price} ₪/mois</b>",
    },
    "price_up": {
        "ru": "📈 Цена выросла на <b>{pct}%</b> по сравнению со вчера.",
        "en": "📈 Price up <b>{pct}%</b> vs yesterday.",
        "he": "📈 המחיר עלה ב-<b>{pct}%</b> לעומת אתמול.",
        "fr": "📈 Prix en hausse de <b>{pct}%</b> par rapport à hier.",
    },
    "price_down": {
        "ru": "📉 Цена снизилась на <b>{pct}%</b> по сравнению со вчера.",
        "en": "📉 Price down <b>{pct}%</b> vs yesterday.",
        "he": "📉 המחיר ירד ב-<b>{pct}%</b> לעומת אתמול.",
        "fr": "📉 Prix en baisse de <b>{pct}%</b> par rapport à hier.",
    },
    "best_hood": {
        "ru": "🏆 Самый выгодный район сегодня — <b>{hood}</b>.",
        "en": "🏆 Best value area today — <b>{hood}</b>.",
        "he": "🏆 האזור המשתלם ביותר היום — <b>{hood}</b>.",
        "fr": "🏆 Le quartier le plus avantageux aujourd'hui — <b>{hood}</b>.",
    },
    "top_cities": {
        "ru": "📍 Больше всего объявлений: {cities}",
        "en": "📍 Most listings: {cities}",
        "he": "📍 הכי הרבה מודעות: {cities}",
        "fr": "📍 Le plus d'annonces: {cities}",
    },
    "datagov_avg": {
        "ru": "🏛 Реестр сделок (data.gov.il): ср. цена продажи {n}-комн. — <b>{price:,} ₪</b>",
        "en": "🏛 Transaction registry: avg {n}-room sale price — <b>{price:,} ₪</b>",
        "he": "🏛 רישום עסקאות: מחיר ממוצע {n} חדרים — <b>{price:,} ₪</b>",
        "fr": "🏛 Registre des transactions: prix moyen {n} pièces — <b>{price:,} ₪</b>",
    },
    "no_data": {
        "ru": "ℹ️ Новых объявлений по этому городу сегодня не найдено.",
        "en": "ℹ️ No new listings for this city today.",
        "he": "ℹ️ לא נמצאו מודעות חדשות לעיר זו היום.",
        "fr": "ℹ️ Aucune nouvelle annonce pour cette ville aujourd'hui.",
    },
    "footer": {
        "ru": "🤖 <i>FlatFinderIL — Умный поиск недвижимости в Израиле</i>",
        "en": "🤖 <i>FlatFinderIL — Smart Real Estate Search in Israel</i>",
        "he": "🤖 <i>FlatFinderIL — חיפוש נדל״ן חכם בישראל</i>",
        "fr": "🤖 <i>FlatFinderIL — Recherche immobilière intelligente en Israël</i>",
    },
}


def _t(key: str, lang: str, **kwargs) -> str:
    tmpl = _LABELS.get(key, {}).get(lang) or _LABELS.get(key, {}).get("ru", "")
    return tmpl.format(**kwargs) if kwargs else tmpl


# ── Агрегация данных из БД ────────────────────────────────────────────────────

def _load_db():
    try:
        import database as db
        return db._load()
    except Exception:
        return {"listings": {}}


def get_daily_stats(city: str = None, deal_type: str = "rent") -> dict:
    """
    Собрать дневную статистику из listings_db.json.

    Возвращает:
      {
        "today_total":    15,     # новых объявлений за сегодня
        "today_private":  8,      # из них от частных лиц
        "avg_price_today": 5800,  # средняя цена аренды сегодня
        "avg_price_yday":  5700,  # средняя цена вчера
        "price_change_pct": 1.8,  # % изменения
        "best_neighborhood": "Агамим",  # район с лучшим соотношением цена/комнаты
        "top_cities": ["Нетания", "Тель-Авив", ...],
        "by_hood": {"Агамим": {"count":3, "avg":4900}, ...}
      }
    """
    data    = _load_db()
    today   = date.today().isoformat()
    yday    = (date.today() - timedelta(days=1)).isoformat()
    listings = list(data.get("listings", {}).values())

    # Фильтрация
    def _match(l):
        if not l.get("active"):
            return False
        if deal_type and l.get("deal_type") != deal_type:
            return False
        if city and l.get("city", "").lower() != city.lower():
            return False
        return True

    def _is_today(l):
        return l.get("date_added", "") == today

    def _is_yday(l):
        return l.get("date_added", "") == yday

    today_all     = [l for l in listings if _match(l) and _is_today(l)]
    today_private = [l for l in today_all if l.get("poster_type") in ("private", "unknown")]
    yday_all      = [l for l in listings if _match(l) and _is_yday(l)]

    def _avg_price(items):
        prices = [l["price"] for l in items if (l.get("price") or 0) > 0]
        return round(statistics.mean(prices)) if prices else 0

    avg_today = _avg_price(today_all)
    avg_yday  = _avg_price(yday_all)

    pct_change = 0.0
    if avg_yday > 0 and avg_today > 0:
        pct_change = round((avg_today - avg_yday) / avg_yday * 100, 1)

    # Лучший район: наибольший count + наименьшая цена/комнаты
    hood_data: dict[str, list] = defaultdict(list)
    for l in today_all:
        hood = l.get("neighborhood") or l.get("city") or "—"
        price = l.get("price") or 0
        rooms = l.get("rooms")
        if price > 0 and rooms:
            try:
                ppr = price / float(str(rooms).replace("+", ""))
                hood_data[hood].append(ppr)
            except Exception:
                pass

    by_hood = {}
    for hood, pprs in hood_data.items():
        by_hood[hood] = {
            "count": len(pprs),
            "avg":   round(statistics.mean(pprs)),
        }

    best_hood = None
    if by_hood:
        # Минимальная цена за комнату среди районов с ≥2 объявлениями
        candidates = {k: v for k, v in by_hood.items() if v["count"] >= 2}
        pool = candidates if candidates else by_hood
        best_hood = min(pool, key=lambda k: pool[k]["avg"])

    # Топ городов (если city не указан)
    city_counter: dict[str, int] = defaultdict(int)
    for l in today_all:
        c = l.get("city")
        if c:
            city_counter[c] += 1
    top_cities = [c for c, _ in sorted(city_counter.items(), key=lambda x: x[1], reverse=True)[:3]]

    return {
        "date":              today,
        "city":              city or "all",
        "deal_type":         deal_type,
        "today_total":       len(today_all),
        "today_private":     len(today_private),
        "avg_price_today":   avg_today,
        "avg_price_yday":    avg_yday,
        "price_change_pct":  pct_change,
        "best_neighborhood": best_hood,
        "top_cities":        top_cities,
        "by_hood":           by_hood,
    }


# ── Генерация текста дайджеста ────────────────────────────────────────────────

def build_digest_text(
    city: str = None,
    lang: str = "ru",
    include_datagov: bool = True,
    datagov_rooms: int = 3,
) -> str:
    """
    Сгенерировать текст утренней сводки.

    Параметры:
      city            — фильтр по городу (None = по всем)
      lang            — язык (ru/en/he/fr)
      include_datagov — добавить данные data.gov.il
      datagov_rooms   — кол-во комнат для запроса в реестр (по умолчанию 3)
    """
    stats = get_daily_stats(city=city)
    lines = []

    # Заголовок
    city_str = f" ({city})" if city else ""
    lines.append(_t("header", lang) + city_str)
    lines.append("")

    if stats["today_total"] == 0:
        lines.append(_t("no_data", lang))
    else:
        lines.append(_t("new_listings", lang, n=stats["today_total"]))

        if stats["today_private"] > 0:
            lines.append(_t("new_private", lang, n=stats["today_private"]))

        if stats["avg_price_today"] > 0:
            price_fmt = f"{stats['avg_price_today']:,}".replace(",", " ")
            lines.append(_t("avg_price", lang, price=price_fmt))

        pct = stats["price_change_pct"]
        if abs(pct) >= 0.5:
            key  = "price_up" if pct > 0 else "price_down"
            lines.append(_t(key, lang, pct=abs(pct)))

        if stats["best_neighborhood"]:
            lines.append(_t("best_hood", lang, hood=stats["best_neighborhood"]))

        if stats["top_cities"] and not city:
            cities_str = ", ".join(stats["top_cities"])
            lines.append(_t("top_cities", lang, cities=cities_str))

    # data.gov.il блок
    if include_datagov and city:
        try:
            from datagov_api import get_market_overview
            overview = get_market_overview(city, last_days=30)
            rooms_data = overview["by_rooms"].get(str(datagov_rooms))
            if rooms_data and rooms_data.get("avg"):
                price_fmt = f"{rooms_data['avg']:,}".replace(",", " ")
                lines.append("")
                lines.append(_t("datagov_avg", lang, n=datagov_rooms, price=rooms_data["avg"]))
        except Exception as e:
            log.debug(f"datagov skip: {e}")

    lines.append("")
    lines.append(_t("footer", lang))

    return "\n".join(lines)


# ── Отправка дайджеста подписчикам ────────────────────────────────────────────

async def send_digest_to_subscribers(
    bot,
    city: str = None,
    target_lang: str = None,
):
    """
    Отправить дайджест всем пользователям из stats.json.

    Параметры:
      bot         — экземпляр telegram.Bot
      city        — фильтровать по городу (None = общий дайджест)
      target_lang — None = каждому на его языке; "ru" = всем на русском
    """
    import json as _json

    _DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    stats_file = os.path.join(_DATA_DIR, "stats.json")

    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = _json.load(f)
    except Exception:
        log.warning("stats.json not found — cannot send digest")
        return

    users = stats.get("users", {})
    sent, failed = 0, 0

    # Кешируем тексты по языку
    texts: dict[str, str] = {}

    for uid, info in users.items():
        lang = target_lang or info.get("lang", "ru")
        if lang not in ("ru", "en", "he", "fr"):
            lang = "ru"

        if lang not in texts:
            texts[lang] = build_digest_text(city=city, lang=lang)

        try:
            await bot.send_message(
                chat_id=int(uid),
                text=texts[lang],
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            log.debug(f"Digest send failed {uid}: {e}")
            failed += 1

    log.info(f"📊 Digest sent: {sent} ok, {failed} failed")
    return {"sent": sent, "failed": failed}


def schedule_daily_digest(bot, hour: int = 9, minute: int = 0,
                          city: str = None, tz_offset: int = 3):
    """
    Запланировать отправку дайджеста каждый день в HH:MM по Израильскому времени.

    Вызвать один раз при старте бота:
        from morning_digest import schedule_daily_digest
        schedule_daily_digest(application.bot, hour=9)
    """
    import threading
    import asyncio
    from datetime import timezone, timedelta as _td

    IL_TZ = timezone(_td(hours=tz_offset))

    def _worker():
        import time as _time
        while True:
            now = datetime.now(IL_TZ)
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_s = (target - now).total_seconds()
            log.info(f"⏰ Next digest at {target.strftime('%Y-%m-%d %H:%M')} IL (in {wait_s/3600:.1f}h)")
            _time.sleep(wait_s)

            # Запускаем отправку
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(send_digest_to_subscribers(bot, city=city))
                loop.close()
            except Exception as e:
                log.error(f"Digest error: {e}")

    t = threading.Thread(target=_worker, daemon=True, name="morning-digest")
    t.start()
    log.info(f"📅 Morning digest scheduler started (every day at {hour:02d}:{minute:02d} IL)")


# ── Точка входа ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="FlatFinderIL — Утренняя сводка")
    ap.add_argument("--city",    default=None,  help="Город (по умолч. — все)")
    ap.add_argument("--lang",    default="ru",  choices=["ru","en","he","fr"])
    ap.add_argument("--rooms",   type=int, default=3, help="Комнат для data.gov.il")
    ap.add_argument("--no-gov",  action="store_true", help="Без data.gov.il")
    args = ap.parse_args()

    text = build_digest_text(
        city=args.city,
        lang=args.lang,
        include_datagov=not args.no_gov,
        datagov_rooms=args.rooms,
    )
    print(text)
