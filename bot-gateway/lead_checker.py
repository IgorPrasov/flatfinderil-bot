"""
Background scheduler for delayed lead triggers.

Runs every 30 minutes and sends cleaning offer to users who:
  - 3 days ago pressed "I rented/bought" (irented_confirm_)
  - Have not yet been prompted about cleaning
"""
import asyncio
import logging

import database as db

logger = logging.getLogger(__name__)

_CLEANING_MSG = {
    "ru": (
        "🧹 <b>Скоро въезд? Сделайте его идеальным!</b>\n\n"
        "Профессиональная уборка перед въездом — это не роскошь, это стандарт.\n"
        "Особенно если квартира пустая или после предыдущих жильцов.\n\n"
        "Оставьте заявку в 2 минуты — проверенные клининговые компании в вашем городе свяжутся с вами сами и предложат цену."
    ),
    "en": (
        "🧹 <b>Moving in soon? Make it spotless!</b>\n\n"
        "A professional clean before move-in isn't a luxury — it's the standard.\n"
        "Especially if the apartment is empty or after previous tenants.\n\n"
        "Submit a request in 2 minutes — verified cleaning companies in your city will call you with their best prices."
    ),
    "he": (
        "🧹 <b>עוברים בקרוב? תעשו את זה מושלם!</b>\n\n"
        "ניקיון מקצועי לפני הכניסה — זה לא מותרות, זה סטנדרט.\n"
        "במיוחד אם הדירה ריקה או אחרי דיירים קודמים.\n\n"
        "השאר בקשה תוך 2 דקות — חברות ניקיון מאומתות בעירך יתקשרו ויציעו מחיר."
    ),
}

_BTN_LABEL = {
    "ru": "🧹 Заказать клининг",
    "en": "🧹 Request cleaning",
    "he": "🧹 הזמן ניקיון",
}

_SKIP_LABEL = {
    "ru": "Не сейчас",
    "en": "Not now",
    "he": "לא עכשיו",
}


async def _send_cleaning_trigger(bot, user_id: int, lang: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    lang = lang or "ru"
    text = _CLEANING_MSG.get(lang, _CLEANING_MSG["ru"])
    btn_label = _BTN_LABEL.get(lang, _BTN_LABEL["ru"])
    skip_label = _SKIP_LABEL.get(lang, _SKIP_LABEL["ru"])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_label, callback_data="request_cleaning")],
        [InlineKeyboardButton(skip_label, callback_data="back_to_menu")],
    ])
    await bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="HTML")


async def run_lead_trigger_checker(bot):
    """Check for due triggers and send them. Also cleans up expired leads."""
    due = db.pop_due_lead_triggers()
    for trigger in due:
        user_id = trigger.get("user_id")
        trigger_type = trigger.get("type", "cleaning")
        if not user_id:
            continue
        try:
            if trigger_type == "cleaning":
                lang = db.get_setting(f"user_lang_{user_id}") or "ru"
                await _send_cleaning_trigger(bot, user_id, lang)
                logger.info(f"[LeadChecker] Sent cleaning trigger to user {user_id}")
        except Exception as e:
            logger.warning(f"[LeadChecker] Failed for user {user_id}: {e}")
    removed = db.cleanup_expired_leads(hours=72)
    if removed:
        logger.info(f"[LeadChecker] Cleaned up {removed} expired leads")


def start_lead_checker(bot):
    """Launch background loop that checks triggers every 30 minutes."""
    async def _loop():
        while True:
            try:
                await run_lead_trigger_checker(bot)
            except Exception as e:
                logger.warning(f"[LeadChecker] Loop error: {e}")
            await asyncio.sleep(30 * 60)

    import threading

    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_loop())

    t = threading.Thread(target=_thread, name="lead_checker", daemon=True)
    t.start()
    logger.info("[LeadChecker] Background trigger checker started (30 min interval)")
