"""
subscription_campaigner.py — Инструмент привлечения пользователей на подписку.

Запускается как фоновый поток из bot.py.
Каждые 6 часов проверяет пользователей и рассылает персональные офферы.

Кампании:
  day3  — пользователь использует бот 3 дня, ещё не подписан
  day7  — 7 дней без подписки → предлагает реферальную программу
  day14 — 14 дней без подписки → финальный оффер со скидкой

Реферальная программа:
  /start ref_USERID → +7 дней обоим
  /refer → показывает ссылку + статистику
"""

import logging
import os
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Сколько дней после регистрации отправлять каждое сообщение
CAMPAIGN_DAYS = {
    "day3":  3,
    "day7":  7,
    "day14": 14,
}

# ── Тексты кампаний ────────────────────────────────────────────────────────────

MESSAGES = {
    "day3": {
        "ru": (
            "🏠 <b>Привет, {name}!</b>\n\n"
            "Ты уже 3 дня ищешь жильё в Израиле через FlatFinderIL — "
            "и мы рады тебе помочь! 🎉\n\n"
            "✨ <b>Хочешь видеть больше объявлений?</b>\n"
            "Подпишись и получи доступ ко всем {total}+ объявлениям без ограничений.\n\n"
            "💡 Или пригласи друга — и получи <b>+7 дней бесплатно!</b>\n"
            "Твоя ссылка: <code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>"
        ),
        "en": (
            "🏠 <b>Hey, {name}!</b>\n\n"
            "You've been searching for housing in Israel with FlatFinderIL for 3 days — "
            "glad to have you! 🎉\n\n"
            "✨ <b>Want to see more listings?</b>\n"
            "Subscribe and get access to all {total}+ listings without limits.\n\n"
            "💡 Or invite a friend and get <b>+7 days free!</b>\n"
            "Your link: <code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>"
        ),
        "he": (
            "🏠 <b>היי, {name}!</b>\n\n"
            "כבר 3 ימים אתה מחפש דיור בישראל עם FlatFinderIL — "
            "שמחים שאתה איתנו! 🎉\n\n"
            "✨ <b>רוצה לראות יותר מודעות?</b>\n"
            "הירשם וקבל גישה לכל {total}+ המודעות ללא הגבלה.\n\n"
            "💡 או הזמן חבר וקבל <b>+7 ימים חינם!</b>\n"
            "הקישור שלך: <code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>"
        ),
    },
    "day7": {
        "ru": (
            "🎁 <b>{name}, у нас есть подарок!</b>\n\n"
            "Уже неделя как ты с нами — спасибо, что пользуешься FlatFinderIL!\n\n"
            "🤝 <b>Реферальная программа:</b>\n"
            "За каждого приглашённого друга — <b>+7 дней подписки</b> тебе и ему!\n\n"
            "Просто поделись ссылкой:\n"
            "<code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>\n\n"
            "📊 <b>Тарифы подписки:</b>\n"
            "• 1 неделя — 19.90 ₪\n"
            "• 2 недели — 29.90 ₪\n"
            "• 1 месяц — 39.90 ₪\n\n"
            "Нажми /subscribe чтобы оформить подписку 👇"
        ),
        "en": (
            "🎁 <b>{name}, we have a gift for you!</b>\n\n"
            "A whole week with us — thank you for using FlatFinderIL!\n\n"
            "🤝 <b>Referral program:</b>\n"
            "For every invited friend — <b>+7 days subscription</b> for you both!\n\n"
            "Just share your link:\n"
            "<code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>\n\n"
            "📊 <b>Subscription plans:</b>\n"
            "• 1 week — 19.90 ₪\n"
            "• 2 weeks — 29.90 ₪\n"
            "• 1 month — 39.90 ₪\n\n"
            "Tap /subscribe to activate 👇"
        ),
        "he": (
            "🎁 <b>{name}, יש לנו מתנה בשבילך!</b>\n\n"
            "שבוע שלם איתנו — תודה שאתה משתמש ב-FlatFinderIL!\n\n"
            "🤝 <b>תוכנית ההפניות:</b>\n"
            "על כל חבר שתזמין — <b>+7 ימי מנוי</b> לך ולו!\n\n"
            "פשוט שתף את הקישור:\n"
            "<code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>\n\n"
            "📊 <b>תוכניות מנוי:</b>\n"
            "• שבוע — 19.90 ₪\n"
            "• שבועיים — 29.90 ₪\n"
            "• חודש — 39.90 ₪\n\n"
            "לחץ /subscribe להפעלה 👇"
        ),
    },
    "day14": {
        "ru": (
            "⏰ <b>{name}, последний шанс!</b>\n\n"
            "Ты уже 2 недели ищешь жильё — мы уверены, ты найдёшь своё!\n\n"
            "🔥 <b>Специальное предложение:</b>\n"
            "Подпишись сегодня и получи первую неделю за полцены — всего <b>9.90 ₪</b>!\n"
            "Используй промокод: <b>WELCOME50</b>\n\n"
            "Или позови друга и получи неделю <b>бесплатно:</b>\n"
            "<code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>\n\n"
            "👉 /subscribe — оформить подписку"
        ),
        "en": (
            "⏰ <b>{name}, last chance!</b>\n\n"
            "You've been searching for 2 weeks — we're sure you'll find your home!\n\n"
            "🔥 <b>Special offer:</b>\n"
            "Subscribe today and get the first week at half price — just <b>9.90 ₪</b>!\n"
            "Use promo code: <b>WELCOME50</b>\n\n"
            "Or invite a friend and get a week <b>for free:</b>\n"
            "<code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>\n\n"
            "👉 /subscribe — activate subscription"
        ),
        "he": (
            "⏰ <b>{name}, הזדמנות אחרונה!</b>\n\n"
            "כבר שבועיים אתה מחפש דיור — אנחנו בטוחים שתמצא!\n\n"
            "🔥 <b>הצעה מיוחדת:</b>\n"
            "הירשם היום וקבל שבוע ראשון במחצית המחיר — רק <b>9.90 ₪</b>!\n"
            "השתמש בקוד: <b>WELCOME50</b>\n\n"
            "או הזמן חבר וקבל שבוע <b>חינם:</b>\n"
            "<code>https://t.me/flatfinderil_bot?start=ref_{user_id}</code>\n\n"
            "👉 /subscribe — הפעל מנוי"
        ),
    },
}

# Inline-кнопки к каждой кампании
KEYBOARDS = {
    "day3": {
        "ru": [("🚀 Подписаться", "show_plans"), ("🎁 Пригласить друга", "show_referral")],
        "en": [("🚀 Subscribe", "show_plans"), ("🎁 Invite friend", "show_referral")],
        "he": [("🚀 הירשם", "show_plans"), ("🎁 הזמן חבר", "show_referral")],
    },
    "day7": {
        "ru": [("💳 Оформить подписку", "show_plans"), ("📤 Поделиться ссылкой", "show_referral")],
        "en": [("💳 Get subscription", "show_plans"), ("📤 Share link", "show_referral")],
        "he": [("💳 קנה מנוי", "show_plans"), ("📤 שתף קישור", "show_referral")],
    },
    "day14": {
        "ru": [("🔥 Активировать скидку", "promo_WELCOME50"), ("📤 Пригласить друга", "show_referral")],
        "en": [("🔥 Activate discount", "promo_WELCOME50"), ("📤 Invite friend", "show_referral")],
        "he": [("🔥 הפעל הנחה", "promo_WELCOME50"), ("📤 הזמן חבר", "show_referral")],
    },
}


def _load_sent(stats_data: dict) -> dict:
    """Возвращает dict {uid: [campaign_key, ...]} — какие кампании уже отправлены."""
    return stats_data.setdefault("sent_campaigns", {})


def _mark_sent(stats_data: dict, uid: str, campaign: str):
    sent = _load_sent(stats_data)
    sent.setdefault(uid, [])
    if campaign not in sent[uid]:
        sent[uid].append(campaign)


def _get_listing_total() -> int:
    try:
        import database as db
        listings = db.get_all_listings()
        return len(listings)
    except Exception:
        return 1800


async def _send_campaign(bot, user_id: int, campaign: str, user_data: dict):
    """Отправить кампанию конкретному пользователю."""
    lang = user_data.get("lang", "ru")
    if lang not in ("ru", "en", "he"):
        lang = "ru"

    name = user_data.get("first_name") or user_data.get("username") or "👋"
    total = _get_listing_total()

    text = MESSAGES[campaign][lang].format(
        name=name,
        user_id=user_id,
        total=total,
    )

    # Build inline keyboard
    btns = KEYBOARDS[campaign].get(lang, KEYBOARDS[campaign]["ru"])
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=cb) for label, cb in btns]
    ])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=kb,
            parse_mode="HTML",
        )
        logger.info(f"[CAMPAIGN] Sent {campaign} → user {user_id} ({lang})")
        return True
    except Exception as e:
        logger.warning(f"[CAMPAIGN] Failed to send {campaign} → {user_id}: {e}")
        return False


async def run_campaigns(bot):
    """
    Основная функция: проверяет всех пользователей и отправляет нужные кампании.
    Вызывается раз в 6 часов из фонового потока.
    """
    from analytics import _load_stats, _save_stats
    from subscription import has_access, is_trial_active

    try:
        stats = _load_stats()
        users = stats.get("users", {})
        today = datetime.now().date()
        sent_count = 0

        for uid, user_data in users.items():
            try:
                user_id = int(uid)
            except ValueError:
                continue

            # Пропускаем уже подписанных
            if user_data.get("subscribed"):
                continue
            if is_trial_active() or has_access(user_id):
                continue

            first_seen_str = user_data.get("first_seen", "")
            if not first_seen_str:
                continue

            try:
                first_seen = datetime.strptime(first_seen_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            days_ago = (today - first_seen).days
            sent = _load_sent(stats).get(uid, [])

            for campaign, target_days in CAMPAIGN_DAYS.items():
                if campaign in sent:
                    continue  # уже отправлено
                if days_ago < target_days:
                    continue  # ещё рано
                if days_ago > target_days + 2:
                    # Пропустили окно (бот был выключен) — пометить как отправленное
                    _mark_sent(stats, uid, campaign)
                    continue

                # Время отправить!
                ok = await _send_campaign(bot, user_id, campaign, user_data)
                if ok:
                    _mark_sent(stats, uid, campaign)
                    sent_count += 1
                    await __import__("asyncio").sleep(0.1)  # rate limit

        if sent_count:
            _save_stats(stats)
            logger.info(f"[CAMPAIGN] Sent {sent_count} campaign messages total")

    except Exception as e:
        logger.error(f"[CAMPAIGN] Error: {e}", exc_info=True)


def start_campaign_loop(bot):
    """
    Запустить фоновый поток с кампанией.
    Первый запуск через 30 минут после старта бота (чтобы не спамить при перезапуске),
    потом каждые 6 часов.
    """
    import asyncio

    def _loop():
        # Первый запуск — через 30 минут
        time.sleep(30 * 60)
        while True:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_campaigns(bot))
                loop.close()
            except Exception as e:
                logger.error(f"[CAMPAIGN] Loop error: {e}")
            time.sleep(6 * 60 * 60)  # каждые 6 часов

    t = threading.Thread(target=_loop, daemon=True, name="subscription-campaigner")
    t.start()
    logger.info("[CAMPAIGN] Subscription campaigner started (first run in 30 min)")
