"""
support_handler.py — allows any user to send a message to the administration.

Flow:
  1. User presses "✉️ Написать нам" (callback contact_admin) or /contact.
  2. Bot asks them to type their message.
  3. Message is saved to DB and forwarded to admin chat IDs
     (env ADMIN_CHAT_IDS, comma-separated; defaults to built-in IDs).
  4. User receives confirmation.

Admin reply: use /reply <msg_id> <text> command in bot chat.
"""

import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from i18n import get_lang
from keyboards import back_to_menu_keyboard
import database as db

logger = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────
SUPPORT_WAITING_MSG = 200

# ── Admin IDs ─────────────────────────────────────────────────────────────────
# IgorPrasov=668726316, tsarenko_alina=416049200
_DEFAULT_ADMIN_IDS = "668726316,416049200"

def _get_admin_ids() -> list[int]:
    raw = os.environ.get("ADMIN_CHAT_IDS", _DEFAULT_ADMIN_IDS)
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                logger.warning(f"[SUPPORT] Invalid admin chat ID: {part!r}")
    return ids

# ── Strings ───────────────────────────────────────────────────────────────────
_PROMPTS = {
    "ru": "✉️ <b>Написать администрации</b>\n\nВведите ваше сообщение — мы ответим как можно скорее.\n\nДля отмены нажмите кнопку ниже.",
    "en": "✉️ <b>Write to the administration</b>\n\nType your message — we will reply as soon as possible.\n\nPress the button below to cancel.",
    "he": "✉️ <b>כתוב להנהלה</b>\n\nהקלד את הודעתך — נחזור אליך בהקדם האפשרי.\n\nלחץ על הכפתור לביטול.",
}
_CONFIRMS = {
    "ru": "✅ Сообщение отправлено! Мы ответим вам в ближайшее время.",
    "en": "✅ Message sent! We will get back to you soon.",
    "he": "✅ ההודעה נשלחה! נחזור אליך בקרוב.",
}
_CANCELS = {
    "ru": "❌ Отменено.",
    "en": "❌ Cancelled.",
    "he": "❌ בוטל.",
}
_ADMIN_REPLY_PREFIX = {
    "ru": "📩 <b>Ответ от администрации:</b>\n\n",
    "en": "📩 <b>Reply from the administration:</b>\n\n",
    "he": "📩 <b>תשובה מההנהלה:</b>\n\n",
}


def _cancel_keyboard(lang: str):
    label = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}.get(lang, "❌ Cancel")
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="support_cancel")]])


# ── Entry points ──────────────────────────────────────────────────────────────

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry via /contact command."""
    lang = get_lang(context)
    await update.message.reply_text(
        _PROMPTS.get(lang, _PROMPTS["ru"]),
        reply_markup=_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    return SUPPORT_WAITING_MSG


async def support_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry via inline button callback_data='contact_admin'."""
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    await query.edit_message_text(
        _PROMPTS.get(lang, _PROMPTS["ru"]),
        reply_markup=_cancel_keyboard(lang),
        parse_mode="HTML",
    )
    return SUPPORT_WAITING_MSG


# ── Receive message ───────────────────────────────────────────────────────────

async def support_receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sent their message — save to DB and notify admins."""
    user = update.effective_user
    lang = get_lang(context)
    user_text = (update.message.text or "").strip()
    if not user_text:
        return SUPPORT_WAITING_MSG   # wait for actual text

    name = (user.first_name or "").strip()
    username = user.username or ""

    # Save to DB
    msg_id = db.add_support_message(
        user_id=user.id,
        username=username,
        first_name=name,
        lang=lang,
        text=user_text,
    )

    # Message is saved to DB — visible in the dashboard (backoffice).
    # No Telegram group forwarding to avoid leaking messages to all group members.
    logger.info(f"[SUPPORT] msg #{msg_id} saved from user {user.id} (@{username})")

    confirm = _CONFIRMS.get(lang, _CONFIRMS["ru"])
    await update.message.reply_text(
        confirm, reply_markup=back_to_menu_keyboard(context), parse_mode="HTML"
    )
    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────────────

async def support_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    await query.edit_message_text(
        _CANCELS.get(lang, _CANCELS["ru"]),
        reply_markup=back_to_menu_keyboard(context),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def support_cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from formatters import format_welcome
    from keyboards import main_menu_keyboard
    await update.message.reply_text(
        format_welcome(update.effective_user.first_name, context),
        reply_markup=main_menu_keyboard(context),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ── Admin /reply command ──────────────────────────────────────────────────────

async def admin_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reply <msg_id> <text>
    Only works for admin IDs. Sends the reply to the user and saves it in DB.
    """
    user = update.effective_user
    if not user or user.id not in _get_admin_ids():
        return   # silently ignore for non-admins

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Использование: /reply <id_сообщения> <текст ответа>")
        return

    try:
        msg_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return

    reply_text = " ".join(args[1:])
    entry = db.reply_support_message(msg_id, reply_text)
    if not entry:
        await update.message.reply_text(f"❌ Сообщение #{msg_id} не найдено.")
        return

    target_uid = entry["user_id"]
    target_lang = entry.get("lang", "ru")
    prefix = _ADMIN_REPLY_PREFIX.get(target_lang, _ADMIN_REPLY_PREFIX["ru"])
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=prefix + reply_text,
            parse_mode="HTML",
        )
        await update.message.reply_text(f"✅ Ответ доставлен пользователю (msg #{msg_id}).")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отправить: {e}")


# ── ConversationHandler ───────────────────────────────────────────────────────

def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("contact", support_start),
            CallbackQueryHandler(support_start_callback, pattern="^contact_admin$"),
        ],
        states={
            SUPPORT_WAITING_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, support_receive_message),
                CallbackQueryHandler(support_cancel, pattern="^support_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", support_cancel_cmd),
        ],
        allow_reentry=True,
        name="support",
        per_message=False,
    )
