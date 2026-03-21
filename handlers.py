from telegram import Update
from telegram.ext import ContextTypes
from keyboards import (
    main_menu_keyboard, back_to_menu_keyboard,
    results_navigation_keyboard, language_keyboard,
    subscription_keyboard,
)
from formatters import format_welcome, format_listing_card
from i18n import t, LANGUAGES, get_lang
from subscription import has_access, activate_subscription, get_status_text, is_trial_active, PLANS
from analytics import track_user, track_subscription
import database as db
from datetime import datetime

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if "lang" not in context.user_data:
        await update.message.reply_text(t("choose_language", context), reply_markup=language_keyboard())
        return
    context.user_data.pop("search_filters", None)
    context.user_data.pop("results", None)
    track_user(user.id, context.user_data.get("lang", "ru"))
    await update.message.reply_text(
        format_welcome(user.first_name, context),
        reply_markup=main_menu_keyboard(context),
        parse_mode="HTML"
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "choose_lang":
        await query.edit_message_text(t("choose_language", context), reply_markup=language_keyboard())
        return

    if data.startswith("setlang_"):
        lang = data.replace("setlang_", "")
        if lang in LANGUAGES:
            context.user_data["lang"] = lang
            user = update.effective_user
            await query.edit_message_text(
                format_welcome(user.first_name, context),
                reply_markup=main_menu_keyboard(context),
                parse_mode="HTML"
            )
        return

    if data == "back_to_menu":
        user = update.effective_user
        await query.edit_message_text(
            format_welcome(user.first_name, context),
            reply_markup=main_menu_keyboard(context),
            parse_mode="HTML"
        )

    elif data == "help":
        await query.edit_message_text(
            t("help_text", context),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML"
        )

    elif data == "subscription":
        lang = get_lang(context)
        user_id = update.effective_user.id
        status = get_status_text(user_id, lang)
        trial_text = t("sub_trial", context) if is_trial_active() else t("sub_choose", context)
        text = (
            f"<b>{t('sub_title', context)}</b>\n\n"
            f"{status}\n\n"
            f"{trial_text}\n\n"
            f"{t('btn_sub_week', context)} \n"
            f"{t('btn_sub_two_weeks', context)} \n"
            f"{t('btn_sub_month', context)}"
        )
        await query.edit_message_text(
            text,
            reply_markup=subscription_keyboard(context),
            parse_mode="HTML"
        )

    elif data.startswith("sub_"):
        plan_key = data.replace("sub_", "")
        if plan_key in PLANS:
            user_id = update.effective_user.id
            expiry = activate_subscription(user_id, plan_key)
            lang = get_lang(context)
            plan = PLANS[plan_key]
            plan_name = plan[f"name_{lang}"] if f"name_{lang}" in plan else plan["name_ru"]
            expiry_str = expiry.strftime("%d.%m.%Y")
            await query.edit_message_text(
                t("sub_activated", context, plan=plan_name, expiry=expiry_str),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )

    elif data == "favorites":
        user_id = update.effective_user.id
        favorites = db.get_favorites(user_id)
        if not favorites:
            await query.edit_message_text(
                t("fav_empty", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
        else:
            context.user_data["results"] = favorites
            listing = favorites[0]
            await query.edit_message_text(
                format_listing_card(listing, context, 0, len(favorites)),
                reply_markup=results_navigation_keyboard(context, 0, len(favorites), listing["id"]),
                parse_mode="HTML"
            )

    elif data == "all_listings":
        listings = db.get_all_listings()
        if not listings:
            await query.edit_message_text(
                t("no_listings_yet", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
            return
        context.user_data["results"] = listings
        listing = listings[0]
        await query.edit_message_text(
            format_listing_card(listing, context, 0, len(listings)),
            reply_markup=results_navigation_keyboard(context, 0, len(listings), listing["id"]),
            parse_mode="HTML"
        )

    elif data.startswith("result_next_") or data.startswith("result_prev_"):
        results = context.user_data.get("results", [])
        if not results:
            await query.edit_message_text(
                t("session_expired", context),
                reply_markup=main_menu_keyboard(context)
            )
            return
        current = int(data.split("_")[-1])
        new_index = min(current+1, len(results)-1) if "next" in data else max(current-1, 0)
        listing = results[new_index]
        await query.edit_message_text(
            format_listing_card(listing, context, new_index, len(results)),
            reply_markup=results_navigation_keyboard(context, new_index, len(results), listing["id"]),
            parse_mode="HTML"
        )

    elif data.startswith("fav_"):
        listing_id = int(data.split("_")[1])
        added = db.toggle_favorite(update.effective_user.id, listing_id)
        await query.answer(t("fav_added", context) if added else t("fav_removed", context))

    elif data.startswith("contact_"):
        listing_id = int(data.split("_")[1])
        listing = db.get_listing(listing_id)
        if listing:
            contact = listing.get("contact") or t("contact_none", context)
            await query.answer(t("contact_info", context, contact=contact), show_alert=True)

    elif data == "my_listings":
        listings = db.get_user_listings(update.effective_user.id)
        if not listings:
            await query.edit_message_text(
                t("no_listings", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
        else:
            context.user_data["results"] = listings
            listing = listings[0]
            await query.edit_message_text(
                format_listing_card(listing, context, 0, len(listings)),
                reply_markup=results_navigation_keyboard(context, 0, len(listings), listing["id"]),
                parse_mode="HTML"
            )

    elif data == "add_listing":
        await query.answer(t("add_use_cmd", context))

    elif data == "search":
        await query.answer(t("search_use_cmd", context))

    elif data == "noop":
        pass

async def my_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    listings = db.get_user_listings(update.effective_user.id)
    if not listings:
        await update.message.reply_text(
            t("no_listings", context),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML"
        )
    else:
        context.user_data["results"] = listings
        listing = listings[0]
        await update.message.reply_text(
            format_listing_card(listing, context, 0, len(listings)),
            reply_markup=results_navigation_keyboard(context, 0, len(listings), listing["id"]),
            parse_mode="HTML"
        )

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "lang" not in context.user_data:
        await update.message.reply_text(
            t("choose_language", context),
            reply_markup=language_keyboard()
        )
        return
    await update.message.reply_text(
        t("unknown_cmd", context),
        reply_markup=back_to_menu_keyboard(context)
    )
