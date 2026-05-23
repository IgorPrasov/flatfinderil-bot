from telegram import InputMediaPhoto
from formatters import format_listing_card
from keyboards import results_navigation_keyboard
import database as db


def get_real_photos(listing):
    """Return Telegram file_ids from the listing (excludes emoji placeholders)."""
    return [p for p in listing.get("photos", []) if len(p) > 20]


async def _delete_prev_photos(context, chat_id):
    """Delete photo messages left over from the previous listing."""
    for msg_id in context.user_data.pop("_photo_msg_ids", []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass


async def display_listing(query, context, listing, index, total):
    """Display a listing card. Shows photo(s) if available, otherwise plain text.
    Also increments the view counter for the listing.
    """
    try:
        db.increment_views(listing["id"])
        fresh = db.get_listing(listing["id"])
        if fresh:
            listing = fresh
    except Exception:
        pass

    card_text = format_listing_card(listing, context, index, total)
    keyboard = results_navigation_keyboard(context, index, total, listing["id"], listing=listing)
    real_photos = get_real_photos(listing)

    chat_id = query.message.chat_id

    if real_photos:
        # Delete previous text message (the one with the keyboard)
        try:
            await query.message.delete()
        except Exception:
            pass
        # Delete any photo messages left from the previous listing
        await _delete_prev_photos(context, chat_id)

        photo_msg_ids = []
        try:
            if len(real_photos) == 1:
                msg = await context.bot.send_photo(chat_id=chat_id, photo=real_photos[0])
                photo_msg_ids = [msg.message_id]
            else:
                msgs = await context.bot.send_media_group(
                    chat_id=chat_id,
                    media=[InputMediaPhoto(pid) for pid in real_photos[:10]],
                )
                photo_msg_ids = [m.message_id for m in msgs]
        except Exception:
            pass

        context.user_data["_photo_msg_ids"] = photo_msg_ids

        # Text card + keyboard always as a separate message
        await context.bot.send_message(
            chat_id=chat_id,
            text=card_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        # No photos for this listing — delete any leftover photos from previous
        await _delete_prev_photos(context, chat_id)
        try:
            await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id, text=card_text, reply_markup=keyboard, parse_mode="HTML"
            )
