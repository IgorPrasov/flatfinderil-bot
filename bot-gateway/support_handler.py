"""
support_handler.py — allows any user to send a message to the administration.

Flow:
  1. User presses "✉️ Написать нам" button (or /contact command).
  2. Bot asks them to type their message.
  3. On receipt the message is forwarded to all admin chat IDs
     (env var ADMIN_CHAT_IDS — comma-separated list of Telegram chat IDs).
  4. User gets a confirmation.
  5. When an admin replies to the forwarded message the bot relays the reply
     back to the original user (optional — works if bot can resolve the user
     from the mapping stored in context.bot_data).
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
from i18n import t, get_lang
from keyboards import back_to_menu_keyboard

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
SUPPORT_WAITING_MSG = 200   # user is typing their message

# ── Admin chat IDs ────────────────────────────────────────────────────────────
def _get_admin_ids() -> list[int]:
    """Return list of admin chat IDs from environment (with hardcoded fallback)."""
    # Hardcoded defaults: IgorPrasov (668726316), tsarenko_alina (416049200)
    _DEFAULTS = "668726316,416049200"
    raw = os.environ.get("ADMIN_CHAT_IDS", _DEFAULTS)
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                logger.warning(f"[SUPPORT] Invalid admin chat ID: {part!r}")
    return ids


# ── Localised strings (inline to avoid touching i18n.py is optional,
#    but we also add the keys to i18n.py for consistency) ─────────────────────
_PROMPTS = {
    "ru": (
        "✉️ <b>Написать администрации</b>\n\n"
        "Введите ваше сообщение — мы ответим как можно скорее."
    ),
    "en": (
        "✉️ <b>Write to the administration</b>\n\n"
        "Type your message — we will reply as soon as possible."
    ),
    "he": (
        "✉️ <b>כתוב להנהלה</b>\n\n"
        "הקלד את הודעתך — נחזור אליך בהקדם האפשרי."
    ),
}

_CONFIRMS = {
    "ru": "✅ Ваше сообщение отправлено администрации. Мы ответим вам в ближайшее время.",
    "en": "✅ Your message has been sent to the administration. We will get back to you soon.",
    "he": "✅ ההודעה שלך נשלחה להנהלה. נחזור אליך בקרוב.",
}

_CANCELS = {
    "ru": "❌ Отменено.",
    "en": "❌ Cancelled.",
    "he": "❌ בוטל.",
}

_NO_ADMIN = {
    "ru": "⚠️ Не удалось отправить сообщение. Попробуйте позже.",
    "en": "⚠️ Could not send the message. Please try again later.",
    "he": "⚠️ לא ניתן לשלוח את ההודעה. נסה שוב מאוחר יותר.",
}

_ADMIN_REPLY_PREFIX = {
    "ru": "📩 <b>Ответ от администрации:</b>\n\n",
    "en": "📩 <b>Reply from the administration:</b>\n\n",
    "he": "📩 <b>תשובה מההנהלה:</b>\n\n",
}


def _cancel_keyboard(ctx):
    lang = get_lang(ctx)
    label = {"ru": "❌ Отмена", "en": "❌ Cancel", "he": "❌ ביטול"}.get(lang, "❌ Cancel")
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="support_cancel")]])


# ── Entry points ──────────────────────────────────────────────────────────────

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry via /contact command."""
    lang = get_lang(context)
    text = _PROMPTS.get(lang, _PROMPTS["ru"])
    await update.message.reply_text(text, reply_markup=_cancel_keyboard(context), parse_mode="HTML")
    return SUPPORT_WAITING_MSG


async def support_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry via inline button callback_data='contact_admin'."""
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    text = _PROMPTS.get(lang, _PROMPTS["ru"])
    await query.edit_message_text(text, reply_markup=_cancel_keyboard(context), parse_mode="HTML")
    return SUPPORT_WAITING_MSG


async def support_receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sent their message — forward to admins and confirm."""
    user = update.effective_user
    lang = get_lang(context)
    user_text = update.message.text or ""

    admin_ids = _get_admin_ids()

    # Build the admin notification
    name = " ".join(filter(None, [user.first_name, user.last_name])) or "—"
    username_str = f"@{user.username}" if user.username else "—"
    header = (
        f"📨 <b>Сообщение от пользователя</b>\n"
        f"👤 {name} ({username_str})\n"
        f"🆔 <code>{user.id}</code>\n"
        f"🌐 Язык: {lang}\n\n"
        f"💬 <i>{user_text}</i>"
    )

    sent_count = 0
    for admin_id in admin_ids:
        try:
            sent_msg = await context.bot.send_message(
                chat_id=admin_id,
                text=header,
                parse_mode="HTML",
            )
            sent_count += 1
            # Store mapping so admin can reply: forwarded_msg_id → user_id
            mapping = context.bot_data.setdefault("support_msg_map", {})
            mapping[f"{admin_id}:{sent_msg.message_id}"] = {
                "user_id": user.id,
                "lang": lang,
            }
        except Exception as e:
            logger.error(f"[SUPPORT] Failed to notify admin {admin_id}: {e}")

    if sent_count > 0 or not admin_ids:
        # If no admins configured — still confirm (message is logged)
        if not admin_ids:
            logger.warning(f"[SUPPORT] No ADMIN_CHAT_IDS configured. Message from uid={user.id}: {user_text!r}")
        confirm = _CONFIRMS.get(lang, _CONFIRMS["ru"])
        await update.message.reply_text(
            confirm, reply_markup=back_to_menu_keyboard(context), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            _NO_ADMIN.get(lang, _NO_ADMIN["ru"]),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML",
        )

    return ConversationHandler.END


async def support_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User cancelled via button."""
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
    """User cancelled via /cancel command."""
    lang = get_lang(context)
    from formatters import format_welcome
    from keyboards import main_menu_keyboard
    await update.message.reply_text(
        format_welcome(update.effective_user.first_name, context),
        reply_markup=main_menu_keyboard(context),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ── Admin reply relay ─────────────────────────────────────────────────────────

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    If an admin replies to a forwarded support message, relay it back to the user.
    Register this as a MessageHandler(filters.REPLY & filters.TEXT) at low priority.
    """
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    admin_id = update.effective_user.id if update.effective_user else None
    if admin_id not in _get_admin_ids():
        return  # only relay if the sender is an admin

    key = f"{msg.chat_id}:{msg.reply_to_message.message_id}"
    mapping = context.bot_data.get("support_msg_map", {})
    entry = mapping.get(key)
    if not entry:
        return  # not a support message

    target_uid = entry["user_id"]
    target_lang = entry.get("lang", "ru")
    prefix = _ADMIN_REPLY_PREFIX.get(target_lang, _ADMIN_REPLY_PREFIX["ru"])

    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=prefix + msg.text,
            parse_mode="HTML",
        )
        await msg.reply_text("✅ Ответ доставлен пользователю.")
    except Exception as e:
        logger.error(f"[SUPPORT] Failed to relay admin reply to uid={target_uid}: {e}")
        await msg.reply_text(f"❌ Не удалось доставить ответ: {e}")


# ── ConversationHandler factory ───────────────────────────────────────────────

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
    )
