from telegram import Update
from telegram.ext import ContextTypes
from keyboards import (
    main_menu_keyboard, back_to_menu_keyboard,
    results_navigation_keyboard, language_keyboard,
    subscription_keyboard, review_rating_keyboard, my_subscriptions_keyboard,
)
from formatters import format_welcome, format_listing_card
from i18n import t, LANGUAGES, get_lang
from subscription import has_access, activate_subscription, get_status_text, is_trial_active, PLANS
from analytics import track_user, track_subscription
from display_utils import display_listing
import database as db
from datetime import datetime


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []

    # Handle referral link: /start ref_USERID
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].replace("ref_", ""))
            if referrer_id != user.id:
                added = db.add_referral(referrer_id, user.id)
                if added:
                    # Give referrer bonus days
                    db.add_bonus_days(referrer_id, 7)
                    # Notify referrer
                    try:
                        lang_ref = "ru"
                        msg = t("refer_bonus_referral", context)
                        await context.bot.send_message(chat_id=referrer_id, text=msg, parse_mode="HTML")
                    except Exception:
                        pass
        except (ValueError, Exception):
            pass

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
            await display_listing(query, context, favorites[0], 0, len(favorites))

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
        await display_listing(query, context, listings[0], 0, len(listings))

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
        await display_listing(query, context, results[new_index], new_index, len(results))

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
            await display_listing(query, context, listings[0], 0, len(listings))

    elif data == "add_listing":
        await query.answer(t("add_use_cmd", context))

    elif data == "search":
        await query.answer(t("search_use_cmd", context))

    elif data == "noop":
        pass

    # ── Subscribe to search ────────────────────────────────────────────────
    elif data == "subscribe_search":
        filters = context.user_data.get("search_filters", {})
        if not filters:
            lang = get_lang(context)
            msg = {"ru": "Сначала выполните поиск.", "en": "Please run a search first.", "he": "בצע חיפוש תחילה."}.get(lang, "Run a search first.")
            await query.answer(msg, show_alert=True)
            return
        user_id = update.effective_user.id
        db.add_search_subscription(user_id, filters)
        await query.answer(t("sub_search_added", context), show_alert=True)

    # ── My subscriptions ───────────────────────────────────────────────────
    elif data == "my_subscriptions":
        user_id = update.effective_user.id
        subs = db.get_user_subscriptions(user_id)
        title = t("my_subscriptions_title", context)
        if not subs:
            await query.edit_message_text(
                title + t("no_subscriptions", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
            return
        lang = get_lang(context)
        lines = [title]
        for i, sub in enumerate(subs):
            filters = sub.get("filters", {})
            deal = filters.get("deal_type", "—")
            city = filters.get("city") or filters.get("cities", ["—"])[0] if filters.get("cities") else "—"
            rooms_min = filters.get("rooms_min", "")
            rooms_max = filters.get("rooms_max", "")
            rooms_str = f"{rooms_min}-{rooms_max}" if rooms_min and rooms_max else rooms_min or rooms_max or "—"
            rooms_word = {"ru": "комнат", "en": "rooms", "he": "חדרים"}.get(lang, "rooms")
            lines.append(f"📋 #{i+1}: {deal}, {city}, {rooms_word}: {rooms_str}")
        text = "\n".join(lines)
        await query.edit_message_text(
            text,
            reply_markup=my_subscriptions_keyboard(context, subs),
            parse_mode="HTML"
        )

    elif data.startswith("unsub_"):
        sub_index = int(data.split("_")[1])
        user_id = update.effective_user.id
        db.remove_search_subscription(user_id, sub_index)
        await query.answer(t("sub_removed", context), show_alert=True)
        # Refresh subscriptions list
        subs = db.get_user_subscriptions(user_id)
        title = t("my_subscriptions_title", context)
        if not subs:
            await query.edit_message_text(
                title + t("no_subscriptions", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
        else:
            lang = get_lang(context)
            lines = [title]
            for i, sub in enumerate(subs):
                filters = sub.get("filters", {})
                deal = filters.get("deal_type", "—")
                city = filters.get("city") or (filters.get("cities", ["—"])[0] if filters.get("cities") else "—")
                lines.append(f"📋 #{i+1}: {deal}, {city}")
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=my_subscriptions_keyboard(context, subs),
                parse_mode="HTML"
            )

    # ── Request viewing ────────────────────────────────────────────────────
    elif data.startswith("reqview_"):
        listing_id = int(data.split("_")[1])
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer("Объявление не найдено.", show_alert=True)
            return
        user = update.effective_user
        owner_id = listing.get("user_id")
        if owner_id and str(owner_id) != str(user.id):
            # Send request to owner
            db.increment_view_requests(listing_id)
            username = user.username or user.first_name or str(user.id)
            title = listing.get("title", "")
            msg = t("view_request_owner_msg", context, title=title, username=username)
            try:
                await context.bot.send_message(chat_id=owner_id, text=msg, parse_mode="HTML")
                await query.answer(t("view_request_sent", context), show_alert=True)
            except Exception:
                # Can't reach owner, show contact
                contact = listing.get("contact") or t("contact_none", context)
                await query.answer(t("view_request_contact", context, contact=contact), show_alert=True)
        else:
            # External listing — show contact
            contact = listing.get("contact") or t("contact_none", context)
            lang = get_lang(context)
            msg = t("view_request_no_owner", context, contact=contact)
            await query.answer(msg, show_alert=True)

    # ── Reviews ────────────────────────────────────────────────────────────
    elif data.startswith("review_"):
        listing_id = int(data.split("_")[1])
        user_id = update.effective_user.id
        if db.user_has_reviewed(listing_id, user_id):
            await query.answer(t("review_already", context), show_alert=True)
            return
        context.user_data["review_listing_id"] = listing_id
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=t("review_prompt", context),
            reply_markup=review_rating_keyboard(listing_id),
            parse_mode="HTML"
        )

    elif data.startswith("rate_"):
        # rate_{listing_id}_{stars}
        parts = data.split("_")
        listing_id = int(parts[1])
        stars = int(parts[2])
        user_id = update.effective_user.id
        if db.user_has_reviewed(listing_id, user_id):
            await query.answer(t("review_already", context), show_alert=True)
            return
        # Save review with just rating (no comment flow for simplicity)
        db.add_review(listing_id, user_id, stars, "")
        await query.edit_message_text(
            t("review_saved", context),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML"
        )

    # ── Agent cabinet ──────────────────────────────────────────────────────
    elif data == "cabinet":
        user_id = update.effective_user.id
        listings = db.get_user_listings(user_id)
        title = t("cabinet_title", context)
        if not listings:
            await query.edit_message_text(
                title + t("cabinet_no_listings", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
            return
        total_views = sum(l.get("views", 0) for l in listings)
        total_requests = sum(l.get("view_requests", 0) for l in listings)
        stats = t("cabinet_stats", context, count=len(listings), views=total_views, requests=total_requests)
        rows = []
        for l in listings:
            avg_r, cnt = db.get_average_rating(l["id"])
            rating_str = f"{avg_r} ({cnt})" if avg_r is not None else "—"
            row = t("cabinet_listing_row", context,
                    title=l.get("title", "")[:30],
                    views=l.get("views", 0),
                    requests=l.get("view_requests", 0),
                    rating=rating_str)
            rows.append(row)
        text = title + stats + "\n".join(rows)
        await query.edit_message_text(
            text[:4000],
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML"
        )


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
            reply_markup=results_navigation_keyboard(context, 0, len(listings), listing["id"], listing=listing),
            parse_mode="HTML"
        )


async def agent_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /cabinet command."""
    user_id = update.effective_user.id
    listings = db.get_user_listings(user_id)
    title = t("cabinet_title", context)
    if not listings:
        await update.message.reply_text(
            title + t("cabinet_no_listings", context),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML"
        )
        return
    total_views = sum(l.get("views", 0) for l in listings)
    total_requests = sum(l.get("view_requests", 0) for l in listings)
    stats = t("cabinet_stats", context, count=len(listings), views=total_views, requests=total_requests)
    rows = []
    for l in listings:
        avg_r, cnt = db.get_average_rating(l["id"])
        rating_str = f"{avg_r} ({cnt})" if avg_r is not None else "—"
        row = t("cabinet_listing_row", context,
                title=l.get("title", "")[:30],
                views=l.get("views", 0),
                requests=l.get("view_requests", 0),
                rating=rating_str)
        rows.append(row)
    text = title + stats + "\n".join(rows)
    await update.message.reply_text(
        text[:4000],
        reply_markup=back_to_menu_keyboard(context),
        parse_mode="HTML"
    )


async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /refer command — generates referral link."""
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    count = db.get_referral_count(user_id)
    bonus_days = db.get_bonus_days(user_id)
    text = t("refer_title", context) + t("refer_text", context, link=link, count=count)
    if bonus_days > 0:
        lang = get_lang(context)
        bonus_str = {"ru": f"\n\n🎁 Накоплено бонусных дней: {bonus_days}", "en": f"\n\n🎁 Accumulated bonus days: {bonus_days}", "he": f"\n\n🎁 ימי בונוס שנצברו: {bonus_days}"}.get(lang, "")
        text += bonus_str
    await update.message.reply_text(
        text,
        reply_markup=back_to_menu_keyboard(context),
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
