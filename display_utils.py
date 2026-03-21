from telegram import InputMediaPhoto
from formatters import format_listing_card
from keyboards import results_navigation_keyboard


def get_real_photos(listing):
    """Return Telegram file_ids from the listing (excludes emoji placeholders)."""
    return [p for p in listing.get("photos", []) if len(p) > 20]


async def display_listing(query, context, listing, index, total):
    """Display a listing card. Shows photo(s) if available, otherwise plain text."""
    card_text = format_listing_card(listing, context, index, total)
    keyboard = results_navigation_keyboard(context, index, total, listing["id"])
    real_photos = get_real_photos(listing)

    chat_id = query.message.chat_id

    if real_photos:
        try:
            await query.message.delete()
        except Exception:
            pass
        if len(real_photos) == 1:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=real_photos[0],
                caption=card_text[:1024],  # Telegram caption limit
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            media = [InputMediaPhoto(pid) for pid in real_photos[:10]]
            await context.bot.send_media_group(chat_id=chat_id, media=media)
            await context.bot.send_message(
                chat_id=chat_id,
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
    else:
        try:
            await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id, text=card_text, reply_markup=keyboard, parse_mode="HTML"
            )
