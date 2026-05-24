import os
import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Telegram Stars (XTR) — no provider token needed
PAYMENT_PROVIDER_TOKEN = ""  # legacy, kept for reference
from keyboards import (
    main_menu_keyboard, back_to_menu_keyboard,
    results_navigation_keyboard, language_keyboard, join_keyboard,
    subscription_keyboard, review_rating_keyboard, my_subscriptions_keyboard,
    cabinet_listings_keyboard, cabinet_listing_manage_keyboard,
    edit_listing_keyboard, confirm_delete_keyboard,
    close_deal_select_keyboard, deal_confirm_price_keyboard,
    tenant_deal_confirm_keyboard, owner_deal_confirm_keyboard,
    search_alert_confirm_keyboard,
    crypto_plan_keyboard, crypto_asset_keyboard,
    card_plan_keyboard,
)
import cryptopay
import paypal_payment as morning_payment
from formatters import format_welcome, format_listing_card
from i18n import t, LANGUAGES, get_lang
from subscription import (
    has_access, activate_subscription, get_status_text, is_trial_active, PLANS,
    days_left_trial, get_trial_warning, TRIAL_WARNING_THRESHOLDS,
)
from analytics import track_user, track_subscription, track_member, get_member_count
from display_utils import display_listing
import database as db
from datetime import datetime
import re as _re


def _build_cabinet_listing_text(listing: dict) -> str:
    """Build the full listing card text for the cabinet (owner view)."""
    active = listing.get("active", True)
    status = "🟢 Активно" if active else "🔴 Снято с публикации"
    avg_r, cnt = db.get_average_rating(listing.get("id", 0))
    rating_str = f"⭐ {avg_r} ({cnt} отзывов)" if avg_r is not None else "⭐ —"

    # Extract contact from field or from description
    contact = listing.get("contact", "") or ""
    if not contact:
        phones = _re.findall(
            r'(?:\+972[-\s]?|0)(?:5[0-9]|7[23])[-\s]?\d{3}[-\s]?\d{4}',
            listing.get("description", "") or ""
        )
        if phones:
            contact = " / ".join(dict.fromkeys(phones))
    contact_line = f"\n📞 <b>Контакт:</b> {contact}" if contact else ""

    deal_emoji = "🔑" if listing.get("deal_type") == "rent" else "🏷"
    deal_label = {"rent": "Аренда", "buy": "Продажа"}.get(listing.get("deal_type", ""), "—")

    # Clean Facebook metadata noise from description (author/timestamp header lines)
    raw_desc = listing.get("description", "") or ""
    desc_lines = raw_desc.split("\n")
    clean_lines, skip_zone = [], True
    for ln in desc_lines:
        s = ln.strip()
        if skip_zone and (not s
                          or _re.match(r'^[\w\s]+ \d+ (ч|мин|дн|д)\.$', s)
                          or s in ("и", "·")
                          or _re.match(r'^\d+ (ч|мин|дн)\.?\s*·?$', s)):
            continue
        skip_zone = False
        clean_lines.append(ln)
    desc_clean = "\n".join(clean_lines).strip()[:800]
    desc_line = f"\n\n📝 {desc_clean}" if desc_clean else ""

    source_url = listing.get("source_url", "")
    source_line = f'\n🔗 <a href="{source_url}">Исходный пост</a>' if source_url else ""

    return (
        f"{deal_emoji} <b>{deal_label}</b>\n"
        f"<b>{(listing.get('title') or '—')[:200]}</b>\n\n"
        f"💰 {listing.get('price', 0):,} ₪\n"
        f"📍 {listing.get('city', '—')} · {listing.get('neighborhood', '—')}\n"
        f"🛏 {listing.get('rooms', '—')} комн. · {listing.get('area_sqm', '—')} м²\n"
        f"👁 {listing.get('views', 0)} просмотров · 📞 {listing.get('view_requests', 0)} запросов\n"
        f"{rating_str}\n"
        f"Статус: {status}"
        f"{contact_line}"
        f"{source_line}"
        f"{desc_line}"
    )[:4000]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []

    # Save user to DB on every /start
    try:
        lang = context.user_data.get("lang", "ru")
        if hasattr(db, "upsert_bot_user"):
            db.upsert_bot_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                lang=lang,
            )
    except Exception:
        pass

    # Handle referral link: /start ref_USERID
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].replace("ref_", ""))
            if referrer_id != user.id:
                added = db.add_referral(referrer_id, user.id)
                if added:
                    db.add_bonus_days(referrer_id, 7)
                    try:
                        await context.bot.send_message(chat_id=referrer_id, text=t("refer_bonus_referral", context), parse_mode="HTML")
                    except Exception:
                        pass
        except (ValueError, Exception):
            pass

    # New user: show join screen first
    if not context.user_data.get("joined"):
        text = (
            f"🏠 <b>FlatFinderIL</b>\n\n"
            f"Поиск недвижимости в Израиле — аренда и покупка.\n\n"
            f"✅ Актуальные объявления из Telegram-каналов\n"
            f"✅ Умный поиск по фильтрам\n"
            f"✅ Карты, фото, контакты\n"
            f"✅ Уведомления о новых объявлениях\n\n"
            f"Нажмите кнопку ниже, чтобы вступить:"
        )
        await update.message.reply_text(text, reply_markup=join_keyboard(), parse_mode="HTML")
        return

    if "lang" not in context.user_data:
        await update.message.reply_text(t("choose_language", context), reply_markup=language_keyboard())
        return
    context.user_data.pop("search_filters", None)
    context.user_data.pop("results", None)
    track_user(user.id, context.user_data.get("lang", "ru"), first_name=user.first_name, last_name=user.last_name, username=user.username)

    welcome_text = format_welcome(user.first_name, context)
    # Баннер о скором окончании триала — только пока триал активен
    try:
        if is_trial_active():
            days = days_left_trial()
            if days <= max(TRIAL_WARNING_THRESHOLDS):
                lang = context.user_data.get("lang", "ru")
                from subscription import get_expiry
                from datetime import datetime as _dt
                paid = get_expiry(user.id, "main")
                if not (paid and paid > _dt.now()):
                    banner = get_trial_warning(lang, days)
                    welcome_text = banner + "\n\n" + welcome_text
    except Exception:
        pass

    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard(context),
        parse_mode="HTML"
    )


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "join":
        user = update.effective_user
        context.user_data["joined"] = True
        track_member(user.id, first_name=user.first_name, last_name=user.last_name, username=user.username)
        # Proceed to language selection or main menu
        if "lang" not in context.user_data:
            await query.edit_message_text(t("choose_language", context), reply_markup=language_keyboard())
        else:
            track_user(user.id, context.user_data.get("lang", "ru"), first_name=user.first_name, last_name=user.last_name, username=user.username)
            await query.edit_message_text(
                format_welcome(user.first_name, context),
                reply_markup=main_menu_keyboard(context),
                parse_mode="HTML"
            )
        return

    if data == "choose_lang":
        await query.edit_message_text(t("choose_language", context), reply_markup=language_keyboard())
        return

    if data.startswith("setlang_"):
        lang = data.replace("setlang_", "")
        if lang in LANGUAGES:
            context.user_data["lang"] = lang
            user = update.effective_user
            db.set_setting(f"user_lang_{user.id}", lang)  # persist for delayed triggers
            track_user(user.id, lang, first_name=user.first_name, last_name=user.last_name, username=user.username)
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
        from config import PLAN_PRICES_ILS
        w = PLAN_PRICES_ILS.get("week", 19.9)
        tw = PLAN_PRICES_ILS.get("two_weeks", 29.9)
        m = PLAN_PRICES_ILS.get("month", 39.9)
        descs = {
            "ru": (
                f"<b>{t('sub_title', context)}</b>\n\n"
                f"{status}\n\n"
                f"Выберите тариф — оплата через PayPal:\n\n"
                f"• 1 неделя — <b>{w:.0f}₪</b>\n"
                f"• 2 недели — <b>{tw:.0f}₪</b>\n"
                f"• 1 месяц — <b>{m:.0f}₪</b>"
            ),
            "en": (
                f"<b>{t('sub_title', context)}</b>\n\n"
                f"{status}\n\n"
                f"Choose a plan — payment via PayPal:\n\n"
                f"• 1 week — <b>{w:.0f}₪</b>\n"
                f"• 2 weeks — <b>{tw:.0f}₪</b>\n"
                f"• 1 month — <b>{m:.0f}₪</b>"
            ),
            "he": (
                f"<b>{t('sub_title', context)}</b>\n\n"
                f"{status}\n\n"
                f"בחרו תוכנית — תשלום דרך PayPal:\n\n"
                f"• שבוע 1 — <b>{w:.0f}₪</b>\n"
                f"• 2 שבועות — <b>{tw:.0f}₪</b>\n"
                f"• חודש 1 — <b>{m:.0f}₪</b>"
            ),
        }
        text = descs.get(lang, descs["ru"])
        await query.edit_message_text(
            text,
            reply_markup=subscription_keyboard(context),
            parse_mode="HTML"
        )

    elif data.startswith("sub_") and not data.startswith("sub_crypto"):
        # sub_search_alert and sub_search_alert_confirm are handled by handle_stars_invoice (group=-1)
        # which runs before handle_menu. We skip them here to avoid double-handling.
        pass

    # ── Crypto payments ──────────────────────────────────────────────────
    elif data == "sub_crypto":
        if not cryptopay.is_enabled():
            await query.edit_message_text(
                "⚠️ Крипто-платежи пока не настроены. Используйте оплату картой.",
                reply_markup=subscription_keyboard(context),
                parse_mode="HTML",
            )
        else:
            from config import PLAN_PRICES_USD
            await query.edit_message_text(
                "₿ <b>Оплата криптовалютой</b>\n\n"
                "Выберите тариф:\n"
                f"• Неделя — <b>${PLAN_PRICES_USD['week']}</b>\n"
                f"• 2 недели — <b>${PLAN_PRICES_USD['two_weeks']}</b>\n"
                f"• Месяц — <b>${PLAN_PRICES_USD['month']}</b>\n\n"
                "💡 Оплата через @CryptoBot — внутри Telegram",
                reply_markup=crypto_plan_keyboard(context),
                parse_mode="HTML",
            )

    elif data.startswith("crypto_plan_"):
        plan_key = data.replace("crypto_plan_", "")
        await query.edit_message_text(
            f"₿ <b>Выберите валюту</b>\n\nТариф: <b>{plan_key.replace('_', ' ')}</b>",
            reply_markup=crypto_asset_keyboard(plan_key),
            parse_mode="HTML",
        )

    elif data.startswith("crypto_pay_"):
        parts = data.split("_", 3)  # crypto_pay_PLAN_ASSET
        if len(parts) == 4:
            _, _, plan_key, asset = parts
            user_id = update.effective_user.id
            await query.answer("Создаём счёт...", show_alert=False)
            invoice = cryptopay.create_invoice(plan_key, user_id, asset)
            if invoice:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                pay_url = invoice.get("pay_url", "")
                inv_id  = invoice.get("invoice_id", "?")
                amount  = invoice.get("amount", "?")
                plan = PLANS.get(plan_key, {})
                lang = get_lang(context)
                plan_name = plan.get(f"name_{lang}") or plan.get("name_ru", plan_key)
                await query.edit_message_text(
                    f"₿ <b>Счёт создан!</b>\n\n"
                    f"Тариф: <b>{plan_name}</b>\n"
                    f"Сумма: <b>{amount} {asset}</b>\n"
                    f"ID счёта: <code>{inv_id}</code>\n\n"
                    f"Нажмите кнопку ниже для оплаты через @CryptoBot.\n"
                    f"Подписка активируется автоматически после оплаты.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"💳 Оплатить {amount} {asset}", url=pay_url)],
                        [InlineKeyboardButton("◀ Назад", callback_data="sub_crypto")],
                    ]),
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text(
                    "❌ Не удалось создать счёт. Попробуйте позже.",
                    reply_markup=subscription_keyboard(context),
                    parse_mode="HTML",
                )

    # ── Morning card payments ─────────────────────────────────────────────
    elif data == "sub_card":
        if not morning_payment.is_enabled():
            await query.edit_message_text(
                "⚠️ Оплата картой временно недоступна. Используйте другой способ.",
                reply_markup=subscription_keyboard(context),
                parse_mode="HTML",
            )
        else:
            lang = get_lang(context)
            titles = {"ru": "💳 Оплата картой", "en": "💳 Card payment", "he": "💳 תשלום בכרטיס"}
            descs  = {
                "ru": "Выберите тариф — оплата через PayPal:",
                "en": "Choose a plan — pay via PayPal:",
                "he": "בחרו תוכנית — תשלום דרך PayPal:",
            }
            await query.edit_message_text(
                f"<b>{titles.get(lang, titles['ru'])}</b>\n\n{descs.get(lang, descs['ru'])}",
                reply_markup=card_plan_keyboard(context),
                parse_mode="HTML",
            )

    elif data.startswith("card_plan_"):
        plan_key = data.replace("card_plan_", "")
        lang     = get_lang(context)
        user_id  = update.effective_user.id

        await query.answer("Создаём ссылку для оплаты...", show_alert=False)

        result = morning_payment.create_payment_link(plan_key, user_id, lang)
        if result and result.get("url"):
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            plan = PLANS.get(plan_key, {})
            plan_name = plan.get(f"name_{lang}") or plan.get("name_ru", plan_key)
            pay_url = result["url"]

            pay_labels  = {"ru": f"💳 Оплатить — {plan_name}", "en": f"💳 Pay — {plan_name}", "he": f"💳 לתשלום — {plan_name}"}
            back_labels = {"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}
            msgs = {
                "ru": (
                    f"💳 <b>Оплата — {plan_name}</b>\n\n"
                    "Нажмите кнопку ниже — откроется страница PayPal.\n\n"
                    "✅ После оплаты подписка активируется автоматически."
                ),
                "en": (
                    f"💳 <b>Payment — {plan_name}</b>\n\n"
                    "Click below to open the PayPal payment page.\n\n"
                    "✅ Your subscription will activate automatically after payment."
                ),
                "he": (
                    f"💳 <b>תשלום — {plan_name}</b>\n\n"
                    "לחצו על הכפתור למטה לדף תשלום של PayPal.\n\n"
                    "✅ המנוי יופעל אוטומטית לאחר התשלום."
                ),
            }
            await query.edit_message_text(
                msgs.get(lang, msgs["ru"]),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(pay_labels.get(lang, pay_labels["ru"]), url=pay_url)],
                    [InlineKeyboardButton(back_labels.get(lang, back_labels["ru"]), callback_data="subscription")],
                ]),
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(
                "❌ Не удалось создать ссылку для оплаты. Попробуйте позже.",
                reply_markup=subscription_keyboard(context),
                parse_mode="HTML",
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
        try:
            await display_listing(query, context, results[new_index], new_index, len(results))
        except Exception as _nav_err:
            logger.error(f"[NAV] display_listing failed idx={new_index}: {_nav_err!r}", exc_info=True)
            lang = get_lang(context)
            err = {"ru": "⚠️ Не удалось загрузить объявление. Попробуйте следующее.", "en": "⚠️ Couldn't load listing. Try the next one.", "he": "⚠️ לא ניתן לטעון מודעה. נסה את הבאה."}.get(lang, "⚠️ Error loading listing.")
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=err)
            except Exception:
                pass

    elif data.startswith("fav_"):
        listing_id = int(data.split("_")[1])
        added = db.toggle_favorite(update.effective_user.id, listing_id)
        await query.answer(t("fav_added", context) if added else t("fav_removed", context))

    elif data.startswith("show_phone_"):
        listing_id = int(data.split("_")[2])
        listing = db.get_listing(listing_id)
        lang = get_lang(context)
        if not listing:
            await query.answer(t("contact_none", context), show_alert=True)
            return
        phone = listing.get("owner_phone", "") or ""
        if not phone:
            # Try extracting from description
            import re
            desc = listing.get("description", "") or ""
            phones = _re.findall(r'(?:\+972[-\s]?|0)(?:5[0-9]|7[23])[-\s]?\d{3}[-\s]?\d{4}', desc)
            phone = " / ".join(dict.fromkeys(phones)) if phones else ""
        if not phone:
            no_phone = {"ru": "Номер телефона не указан.", "en": "Phone number not provided.", "he": "מספר טלפון לא צוין."}.get(lang, "Phone not provided.")
            await query.answer(no_phone, show_alert=True)
        else:
            phone_msg = {"ru": f"📞 Телефон: {phone}", "en": f"📞 Phone: {phone}", "he": f"📞 טלפון: {phone}"}.get(lang, f"📞 {phone}")
            await query.answer(phone_msg[:200], show_alert=True)

    elif data.startswith("contact_"):
        listing_id = int(data.split("_")[1])
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer(t("contact_none", context), show_alert=True)
            return
        contact = listing.get("contact", "") or ""
        # If contact field is empty, try to extract phone from description
        if not contact:
            import re
            desc = listing.get("description", "") or ""
            phones = re.findall(r'(?:\+972[-\s]?|0)(?:5[0-9]|7[23])[-\s]?\d{3}[-\s]?\d{4}', desc)
            if phones:
                contact = " / ".join(dict.fromkeys(phones))  # deduplicate, keep order
        if not contact:
            # Fallback: show source URL so user can visit original post
            source_url = listing.get("source_url", "")
            lang = get_lang(context)
            if source_url:
                no_contact_msg = {"ru": f"Контакт не указан. Исходный пост:\n{source_url}",
                                  "en": f"No contact. Original post:\n{source_url}",
                                  "he": f"אין פרטי קשר. פוסט מקורי:\n{source_url}"}.get(lang, source_url)
                await query.answer(no_contact_msg[:200], show_alert=True)
            else:
                await query.answer(t("contact_none", context), show_alert=True)
            return
        msg = t("contact_info", context, contact=contact)[:200]
        await query.answer(msg, show_alert=True)

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

    # ── Mover subscription — handled in group=-1 by _handle_mover_subscribe ──
    elif data.startswith("mover_subscribe_"):
        pass  # already handled before handle_menu runs

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
            db.record_view_requester(listing_id, user.id,
                                     username=user.username or "",
                                     name=user.first_name or str(user.id))
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
            # ── Email notification to owner ──────────────────────────────────
            try:
                owner_email = db.get_agent_email(owner_id)
                if owner_email:
                    from email_reporter import send_contact_request_email
                    import threading
                    threading.Thread(
                        target=send_contact_request_email,
                        args=(owner_email, title, username, user.id),
                        daemon=True,
                    ).start()
            except Exception:
                pass
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
        lang = get_lang(context)
        select_hint = {"ru": "\n📋 <b>Выберите объявление для управления:</b>",
                       "en": "\n📋 <b>Select a listing to manage:</b>",
                       "he": "\n📋 <b>בחר מודעה לניהול:</b>"}.get(lang, "\n📋 Select a listing:")
        await query.edit_message_text(
            (title + stats + select_hint)[:4000],
            reply_markup=cabinet_listings_keyboard(context, listings),
            parse_mode="HTML"
        )

    # ── Cabinet: single listing view ────────────────────────────────────────
    elif data.startswith("cab_listing_"):
        listing_id = int(data.replace("cab_listing_", ""))
        listing = db.get_listing(listing_id)
        if not listing:
            await query.edit_message_text("❌ Объявление не найдено.", reply_markup=back_to_menu_keyboard(context))
            return
        deal_closed = listing.get("deal_closed", False)
        await query.edit_message_text(
            _build_cabinet_listing_text(listing),
            reply_markup=cabinet_listing_manage_keyboard(context, listing_id, listing.get("active", True), deal_closed),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    # ── Edit listing: choose field ──────────────────────────────────────────
    elif data.startswith("edit_listing_"):
        listing_id = int(data.replace("edit_listing_", ""))
        lang = get_lang(context)
        hint = {"ru": "✏️ Что редактируем?", "en": "✏️ What to edit?", "he": "✏️ מה לערוך?"}.get(lang, "✏️ Edit")
        await query.edit_message_text(hint, reply_markup=edit_listing_keyboard(context, listing_id))

    # ── Edit field: price ───────────────────────────────────────────────────
    elif data.startswith("editfield_price_"):
        listing_id = int(data.replace("editfield_price_", ""))
        lang = get_lang(context)
        context.user_data["editing_listing_id"] = listing_id
        context.user_data["editing_field"] = "price"
        prompt = {"ru": "💰 Введите новую цену (число, ₪):",
                  "en": "💰 Enter new price (number, ₪):",
                  "he": "💰 הזן מחיר חדש (מספר, ₪):"}.get(lang, "💰 New price:")
        await query.edit_message_text(prompt)

    # ── Edit field: description ─────────────────────────────────────────────
    elif data.startswith("editfield_desc_"):
        listing_id = int(data.replace("editfield_desc_", ""))
        lang = get_lang(context)
        context.user_data["editing_listing_id"] = listing_id
        context.user_data["editing_field"] = "description"
        prompt = {"ru": "📝 Введите новое описание:",
                  "en": "📝 Enter new description:",
                  "he": "📝 הזן תיאור חדש:"}.get(lang, "📝 New description:")
        await query.edit_message_text(prompt)

    # ── Toggle active ───────────────────────────────────────────────────────
    elif data.startswith("toggle_active_"):
        listing_id = int(data.replace("toggle_active_", ""))
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer("Объявление не найдено", show_alert=True)
            return
        new_active = not listing.get("active", True)
        db.update_listing(listing_id, {"active": new_active})
        lang = get_lang(context)
        msg = {"ru": "🟢 Объявление опубликовано!" if new_active else "🔴 Объявление снято с публикации.",
               "en": "🟢 Listing activated!" if new_active else "🔴 Listing deactivated.",
               "he": "🟢 המודעה פורסמה!" if new_active else "🔴 המודעה הוסרה."}.get(lang, "Done")
        await query.answer(msg, show_alert=True)
        # Refresh listing and redraw
        listing["active"] = new_active
        deal_closed = listing.get("deal_closed", False)
        await query.edit_message_text(
            _build_cabinet_listing_text(listing),
            reply_markup=cabinet_listing_manage_keyboard(context, listing_id, new_active, deal_closed),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    # ── Confirm delete ──────────────────────────────────────────────────────
    elif data.startswith("confirm_delete_"):
        listing_id = int(data.replace("confirm_delete_", ""))
        lang = get_lang(context)
        warn = {"ru": f"⚠️ Вы уверены, что хотите <b>удалить</b> объявление #{listing_id}?\nЭто действие нельзя отменить.",
                "en": f"⚠️ Are you sure you want to <b>delete</b> listing #{listing_id}?\nThis cannot be undone.",
                "he": f"⚠️ האם אתה בטוח שאתה רוצה <b>למחוק</b> מודעה #{listing_id}?"}.get(lang, f"Delete #{listing_id}?")
        await query.edit_message_text(warn, reply_markup=confirm_delete_keyboard(context, listing_id), parse_mode="HTML")

    # ── Do delete ───────────────────────────────────────────────────────────
    elif data.startswith("do_delete_"):
        listing_id = int(data.replace("do_delete_", ""))
        user_id = update.effective_user.id
        ok = db.delete_listing(listing_id, user_id)
        lang = get_lang(context)
        if ok:
            msg = {"ru": "✅ Объявление удалено.", "en": "✅ Listing deleted.", "he": "✅ המודעה נמחקה."}.get(lang, "✅ Deleted.")
        else:
            msg = {"ru": "❌ Объявление не найдено.", "en": "❌ Listing not found.", "he": "❌ לא נמצא."}.get(lang, "❌ Not found.")
        # Return to cabinet
        listings = db.get_user_listings(user_id)
        title = t("cabinet_title", context)
        if not listings:
            await query.edit_message_text(
                msg + "\n\n" + title + t("cabinet_no_listings", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
            return
        total_views = sum(l.get("views", 0) for l in listings)
        total_requests = sum(l.get("view_requests", 0) for l in listings)
        stats = t("cabinet_stats", context, count=len(listings), views=total_views, requests=total_requests)
        select_hint = {"ru": "\n📋 <b>Выберите объявление для управления:</b>",
                       "en": "\n📋 <b>Select a listing to manage:</b>",
                       "he": "\n📋 <b>בחר מודעה לניהול:</b>"}.get(lang, "\n📋 Select:")
        await query.edit_message_text(
            (msg + "\n\n" + title + stats + select_hint)[:4000],
            reply_markup=cabinet_listings_keyboard(context, listings),
            parse_mode="HTML"
        )


    # ── Close deal: owner initiates ────────────────────────────────────────
    elif data.startswith("close_deal_"):
        listing_id = int(data.replace("close_deal_", ""))
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer("Объявление не найдено", show_alert=True)
            return
        requesters = db.get_view_requesters(listing_id)
        if requesters:
            await query.edit_message_text(
                t("deal_select_tenant", context),
                reply_markup=close_deal_select_keyboard(context, listing_id, requesters),
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text(
                t("deal_no_requesters", context),
                reply_markup=close_deal_select_keyboard(context, listing_id, []),
                parse_mode="HTML"
            )

    # ── Close deal: owner selected tenant → ask price ──────────────────────
    elif data.startswith("deal_tenant_"):
        parts = data.split("_")
        listing_id = int(parts[2])
        tenant_id = int(parts[3])
        context.user_data["closing_listing_id"] = listing_id
        context.user_data["closing_tenant_id"] = tenant_id
        context.user_data["editing_field"] = "deal_price"
        await query.edit_message_text(t("deal_enter_price", context), parse_mode="HTML")

    # ── Close deal: final confirm from owner ───────────────────────────────
    elif data.startswith("deal_confirm_"):
        parts = data.split("_")
        listing_id = int(parts[2])
        tenant_id = int(parts[3])
        deal_price = context.user_data.pop("closing_deal_price", 0)
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer("Объявление не найдено", show_alert=True)
            return
        owner_id = update.effective_user.id
        listed_price = listing.get("price", 0)
        deal_id = db.close_deal(listing_id, owner_id, tenant_id, listed_price, deal_price)
        # Give bonus days to owner
        db.add_bonus_days(owner_id, 3)
        title = listing.get("title", "")[:50]
        final_price = deal_price if deal_price > 0 else listed_price
        msg = t("deal_closed_owner", context, title=title, price=f"{final_price:,}")
        await query.edit_message_text(msg, reply_markup=back_to_menu_keyboard(context), parse_mode="HTML")
        # Notify tenant if selected
        if tenant_id > 0:
            try:
                await context.bot.send_message(
                    chat_id=tenant_id,
                    text=t("deal_notify_tenant", context, title=title),
                    parse_mode="HTML"
                )
            except Exception:
                pass
        # Notify other requesters
        requesters = db.get_view_requesters(listing_id)
        for r in requesters:
            uid = r.get("user_id")
            if uid and uid != tenant_id:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=t("deal_notify_others", context, title=title),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        # ── Email to owner/agent about closed deal ───────────────────────────
        try:
            owner_email = db.get_agent_email(owner_id)
            if owner_email:
                from email_reporter import send_deal_closed_email
                tenant_info = next((r for r in requesters if r.get("user_id") == tenant_id), {})
                tenant_name = tenant_info.get("username") or tenant_info.get("name") or f"ID {tenant_id}"
                import threading
                threading.Thread(
                    target=send_deal_closed_email,
                    args=(owner_email, title, final_price, listed_price,
                          tenant_name, listing.get("deal_type", "rent")),
                    daemon=True,
                ).start()
        except Exception:
            pass

        # ── Trigger packing offer to the tenant too ──────────────────────────
        if tenant_id > 0:
            try:
                from datetime import datetime as _dt, timedelta as _td, timezone as _tz
                tenant_lang = db.get_setting(f"user_lang_{tenant_id}") or "ru"
                _city = listing.get("city", "")
                _pack_msg = {
                    "ru": (
                        "🎉 <b>Поздравляем с новой квартирой!</b>\n\n"
                        "📦 <b>Нужны коробки и упаковка для переезда?</b>\n"
                        "Нажмите кнопку — лучшие поставщики в вашем городе свяжутся с вами."
                    ),
                    "en": (
                        "🎉 <b>Congrats on your new place!</b>\n\n"
                        "📦 <b>Need packing boxes for the move?</b>\n"
                        "Tap below — top suppliers in your city will reach out."
                    ),
                    "he": (
                        "🎉 <b>מזל טוב על הדירה החדשה!</b>\n\n"
                        "📦 <b>צריך קופסאות לעברה?</b>\n"
                        "לחץ למטה — הספקים הטובים ביותר בעירך ייצרו קשר."
                    ),
                }.get(tenant_lang, "🎉 Congrats!\n\n📦 Need packing boxes?")
                _pack_lbl = {"ru": "📦 Да, нужны коробки", "en": "📦 Yes, need boxes", "he": "📦 כן, צריך קופסאות"}.get(tenant_lang, "📦 Need boxes?")
                _skip_lbl = {"ru": "Пропустить", "en": "Skip", "he": "דלג"}.get(tenant_lang, "Skip")
                from telegram import InlineKeyboardButton as _IKB, InlineKeyboardMarkup as _IKM
                await context.bot.send_message(
                    chat_id=tenant_id,
                    text=_pack_msg,
                    reply_markup=_IKM([[_IKB(_pack_lbl, callback_data="request_packing")], [_IKB(_skip_lbl, callback_data="back_to_menu")]]),
                    parse_mode="HTML",
                )
                _send_after = (_dt.now(_tz.utc) + _td(days=3)).isoformat()
                db.add_pending_lead_trigger(tenant_id, "cleaning", _city, _send_after)
            except Exception:
                pass

    # ── Tenant: "I rented/bought this" button ──────────────────────────────
    elif data.startswith("irented_") and not data.startswith("irented_confirm_"):
        listing_id = int(data.replace("irented_", ""))
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer("Объявление не найдено", show_alert=True)
            return
        title = listing.get("title", "")[:50]
        await query.edit_message_text(
            t("deal_irented_confirm", context, title=title),
            reply_markup=tenant_deal_confirm_keyboard(context, listing_id),
            parse_mode="HTML"
        )

    # ── Tenant confirms: send request to owner ─────────────────────────────
    elif data.startswith("irented_confirm_"):
        listing_id = int(data.replace("irented_confirm_", ""))
        listing = db.get_listing(listing_id)
        if not listing:
            await query.answer("Объявление не найдено", show_alert=True)
            return
        user = update.effective_user
        owner_id = listing.get("user_id")
        title = listing.get("title", "")[:50]
        name = user.first_name or user.username or str(user.id)
        # Record requester
        db.record_view_requester(listing_id, user.id,
                                 username=user.username or "",
                                 name=name)
        await query.edit_message_text(
            t("deal_irented_sent", context),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML"
        )
        if owner_id:
            try:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=t("deal_owner_confirm_req", context, name=name, title=title),
                    reply_markup=owner_deal_confirm_keyboard(context, listing_id, user.id),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # ── Trigger packing offer immediately ─────────────────────────────
        city = listing.get("city", "")
        lang = get_lang(context)
        packing_msg = {
            "ru": (
                "🎉 <b>Поздравляем с выбором квартиры!</b>\n\n"
                "Переезд — это хлопотно, но мы поможем.\n\n"
                "📦 <b>Вам понадобятся коробки и упаковка?</b>\n"
                "Нажмите кнопку ниже — лучшие поставщики в вашем городе свяжутся с вами."
            ),
            "en": (
                "🎉 <b>Congrats on your new apartment!</b>\n\n"
                "Moving is a lot of work — let us help.\n\n"
                "📦 <b>Need packing boxes and supplies?</b>\n"
                "Tap the button below — top suppliers in your city will contact you."
            ),
            "he": (
                "🎉 <b>מזל טוב על הדירה החדשה!</b>\n\n"
                "מעבר דירה זה הרבה עבודה — נשמח לעזור.\n\n"
                "📦 <b>צריך קופסאות ואריזה?</b>\n"
                "לחץ על הכפתור — הספקים הטובים ביותר בעירך ייצרו קשר."
            ),
        }.get(lang, "🎉 Congrats! Need packing boxes?")

        pack_btn_label = {"ru": "📦 Нужны коробки и упаковка", "en": "📦 Yes, I need packing boxes", "he": "📦 כן, אני צריך קופסאות"}.get(lang, "📦 Need boxes?")
        skip_label = {"ru": "Пропустить", "en": "Skip", "he": "דלג"}.get(lang, "Skip")
        pack_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(pack_btn_label, callback_data="request_packing")],
            [InlineKeyboardButton(skip_label, callback_data="back_to_menu")],
        ])
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=packing_msg,
                reply_markup=pack_kb,
                parse_mode="HTML",
            )
        except Exception:
            pass

        # ── Schedule cleaning offer in 3 days ─────────────────────────────
        from datetime import datetime, timedelta, timezone
        send_after = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        db.add_pending_lead_trigger(user.id, "cleaning", city, send_after)

    else:
        # ── Orphan-callback fallback ─────────────────────────────────────
        # Stale inline buttons (sent before a deploy that changed callback_data)
        # would otherwise hit no branch, leaving the user with an infinite
        # spinner. Log it for ops visibility and bring the user back to the
        # main menu in their language.
        try:
            user_id = update.effective_user.id if update.effective_user else "?"
        except Exception:
            user_id = "?"
        logger.warning(
            "[ORPHAN_CALLBACK] unhandled callback_data=%r user_id=%s",
            data, user_id,
        )
        try:
            user = update.effective_user
            first = (user.first_name if user else "") or ""
            # Replace the old message so the stale buttons don't linger.
            try:
                await query.edit_message_text(
                    format_welcome(first, context),
                    reply_markup=main_menu_keyboard(context),
                    parse_mode="HTML",
                )
            except Exception:
                if query.message:
                    await query.message.reply_text(
                        format_welcome(first, context),
                        reply_markup=main_menu_keyboard(context),
                        parse_mode="HTML",
                    )
        except Exception as _orphan_err:
            logger.error("[ORPHAN_CALLBACK] failed to recover: %s", _orphan_err)


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
    lang = get_lang(context)
    total_views = sum(l.get("views", 0) for l in listings)
    total_requests = sum(l.get("view_requests", 0) for l in listings)
    stats = t("cabinet_stats", context, count=len(listings), views=total_views, requests=total_requests)
    select_hint = {"ru": "\n📋 <b>Выберите объявление для управления:</b>",
                   "en": "\n📋 <b>Select a listing to manage:</b>",
                   "he": "\n📋 <b>בחר מודעה לניהול:</b>"}.get(lang, "\n📋 Select a listing:")
    await update.message.reply_text(
        (title + stats + select_hint)[:4000],
        reply_markup=cabinet_listings_keyboard(context, listings),
        parse_mode="HTML"
    )


async def handle_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input when user is editing a listing field (price / description)."""
    editing_id = context.user_data.get("editing_listing_id")
    editing_field = context.user_data.get("editing_field")

    # Deal price input (closing a deal)
    closing_id = context.user_data.get("closing_listing_id")
    closing_tenant = context.user_data.get("closing_tenant_id")
    if editing_field == "deal_price" and closing_id:
        text_input = update.message.text.strip()
        lang = get_lang(context)
        try:
            deal_price = int(text_input.replace(",", "").replace("₪", "").replace(" ", ""))
        except ValueError:
            deal_price = 0
        context.user_data["closing_deal_price"] = deal_price
        context.user_data.pop("editing_field", None)
        listing = db.get_listing(closing_id)
        listed_price = listing.get("price", 0) if listing else 0
        final_price = deal_price if deal_price > 0 else listed_price
        lang = get_lang(context)
        summary = {"ru": f"💰 Цена сделки: <b>{final_price:,} ₪</b>\n\nПодтвердить закрытие сделки?",
                   "en": f"💰 Deal price: <b>{final_price:,} ₪</b>\n\nConfirm closing the deal?",
                   "he": f"💰 מחיר עסקה: <b>{final_price:,} ₪</b>\n\nלאשר סגירת עסקה?"}.get(lang, f"{final_price:,} ₪")
        await update.message.reply_text(
            summary,
            reply_markup=deal_confirm_price_keyboard(context, closing_id, closing_tenant),
            parse_mode="HTML"
        )
        return

    if not editing_id or not editing_field:
        await handle_unknown(update, context)
        return

    text = update.message.text.strip()
    lang = get_lang(context)

    if editing_field == "price":
        try:
            new_price = int(text.replace(",", "").replace("₪", "").replace(" ", ""))
        except ValueError:
            err = {"ru": "❌ Введите число (например: 5500)",
                   "en": "❌ Enter a number (e.g. 5500)",
                   "he": "❌ הזן מספר (לדוגמה: 5500)"}.get(lang, "❌ Number only")
            await update.message.reply_text(err)
            return
        db.update_listing(editing_id, {"price": new_price})
        ok = {"ru": f"✅ Цена обновлена: {new_price:,} ₪",
              "en": f"✅ Price updated: {new_price:,} ₪",
              "he": f"✅ המחיר עודכן: {new_price:,} ₪"}.get(lang, f"✅ {new_price:,} ₪")

    elif editing_field == "description":
        db.update_listing(editing_id, {"description": text})
        ok = {"ru": "✅ Описание обновлено.",
              "en": "✅ Description updated.",
              "he": "✅ התיאור עודכן."}.get(lang, "✅ Done.")
    else:
        ok = "✅"

    context.user_data.pop("editing_listing_id", None)
    context.user_data.pop("editing_field", None)

    back_label = {"ru": "« К кабинету", "en": "« Back to cabinet", "he": "« חזרה"}.get(lang, "« Back")
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(back_label, callback_data=f"cab_listing_{editing_id}")]])
    await update.message.reply_text(ok, reply_markup=kb, parse_mode="HTML")


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


# ── Telegram Payments ─────────────────────────────────────────────────────────

async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обязательный ответ на pre-checkout запрос в течение 10 секунд."""
    query = update.pre_checkout_query
    logger.info(f"[PAYMENT] pre_checkout_query uid={update.effective_user.id} payload={query.invoice_payload!r} amount={query.total_amount} currency={query.currency}")
    # Always answer ok=True — never let a crash cause a timeout ("произошла ошибка")
    try:
        plan_key, uid_str = query.invoice_payload.split(":", 1)
        if plan_key not in PLANS:
            logger.warning(f"[PAYMENT] Unknown plan in payload: {plan_key!r} — approving anyway")
        logger.info(f"[PAYMENT] pre_checkout answered ok=True for plan={plan_key}")
    except Exception as e:
        logger.error(f"[PAYMENT] pre_checkout parse error (still approving): {e}")
    await query.answer(ok=True)


def _send_payment_receipt(email: str, buyer_name: str, plan_name_he: str, amount_ils: float,
                           days: int, expiry_str: str, charge_id: str):
    """Отправляет квитанцию (קבלה) на иврите через Resend API."""
    import requests as _req
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key or not email:
        return
    date_he = datetime.now().strftime("%d/%m/%Y")
    amount_str = f"₪{amount_ils:.2f}"
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="UTF-8"><style>
  body{{font-family:Arial,sans-serif;direction:rtl;background:#f5f5f0;margin:0;padding:20px}}
  .wrap{{max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
  .head{{background:#2AABEE;padding:28px 32px;text-align:center;color:#fff}}
  .head h1{{margin:0;font-size:22px;letter-spacing:.5px}}
  .head p{{margin:6px 0 0;font-size:13px;opacity:.85}}
  .body{{padding:28px 32px}}
  .label{{font-size:11px;color:#999;margin-bottom:2px;text-transform:uppercase}}
  .value{{font-size:15px;color:#222;margin-bottom:18px;font-weight:500}}
  .divider{{border:none;border-top:1px solid #eee;margin:20px 0}}
  .total-row{{display:flex;justify-content:space-between;align-items:center;background:#f0faf5;padding:14px 18px;border-radius:8px;margin-top:8px}}
  .total-label{{font-size:14px;color:#333;font-weight:600}}
  .total-amount{{font-size:22px;font-weight:700;color:#4CAF8A}}
  .footer{{background:#f8f8f4;padding:16px 32px;text-align:center;font-size:11px;color:#aaa}}
  .badge{{display:inline-block;background:#4CAF8A22;color:#4CAF8A;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;margin-top:4px}}
</style></head>
<body>
<div class="wrap">
  <div class="head">
    <h1>🏠 FlatFinderIL</h1>
    <p>קבלה על תשלום</p>
  </div>
  <div class="body">
    <div class="label">מספר קבלה</div>
    <div class="value" style="font-family:monospace;font-size:13px;color:#888">{charge_id}</div>

    <div class="label">תאריך</div>
    <div class="value">{date_he}</div>

    <div class="label">שם הלקוח</div>
    <div class="value">{buyer_name or '—'}</div>

    <div class="label">כתובת דואר אלקטרוני</div>
    <div class="value" style="direction:ltr;text-align:right">{email}</div>

    <hr class="divider">

    <div class="label">שירות</div>
    <div class="value">גישה ל-FlatFinderIL — {plan_name_he} ({days} ימים)</div>

    <div class="label">תוקף המנוי עד</div>
    <div class="value"><span class="badge">✅ {expiry_str}</span></div>

    <div class="total-row">
      <span class="total-label">סה"כ שולם</span>
      <span class="total-amount">{amount_str}</span>
    </div>
  </div>
  <div class="footer">FlatFinderIL · תשלום בוצע דרך Telegram Payments · תודה שבחרת בנו!</div>
</div>
</body></html>"""

    from_addr = os.environ.get("RESEND_FROM", "FlatFinderIL <info@flatfinderil.com>")
    try:
        resp = _req.post(
            "https://api.resend.com/emails",
            json={
                "from": from_addr,
                "to": [email],
                "subject": f"קבלה על תשלום — FlatFinderIL {date_he}",
                "html": html,
            },
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            timeout=10,
        )
        import logging as _log
        _log.getLogger(__name__).info(f"[EMAIL] Resend status={resp.status_code} body={resp.text[:200]}")
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f"[EMAIL] Resend error: {e}")


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активирует подписку после успешной оплаты."""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", "ru")
    logger.info(f"[PAYMENT] successful_payment uid={user_id} amount={payment.total_amount} currency={payment.currency} payload={payment.invoice_payload!r}")

    try:
        plan_key, _ = payment.invoice_payload.split(":", 1)
        expiry = activate_subscription(user_id, plan_key)
        track_subscription(user_id, plan_key)

        plan = PLANS[plan_key]
        plan_name = plan.get(f"name_{lang}") or plan["name_ru"]
        stars = plan.get("stars", 0)
        expiry_str = expiry.strftime("%d.%m.%Y")
        charge_id = payment.telegram_payment_charge_id or "—"
        logger.info(f"[PAYMENT] Stars charge_id={charge_id} stars={stars} plan={plan_key} uid={user_id}")

        msgs = {
            "ru": f"✅ <b>Оплата прошла успешно!</b>\n\nПодписка <b>{plan_name}</b> активна до <b>{expiry_str}</b>.\n\n⭐ Списано {stars} Stars\n\nСпасибо! 🏠",
            "en": f"✅ <b>Payment successful!</b>\n\n<b>{plan_name}</b> subscription active until <b>{expiry_str}</b>.\n\n⭐ {stars} Stars charged\n\nThank you! 🏠",
            "he": f"✅ <b>התשלום בוצע בהצלחה!</b>\n\nמנוי <b>{plan_name}</b> פעיל עד <b>{expiry_str}</b>.\n\n⭐ {stars} Stars נגבו\n\nתודה! 🏠",
        }
        await update.message.reply_text(
            msgs.get(lang, msgs["ru"]),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML",
        )
    except Exception as e:
        # CRITICAL: оплата прошла, но активация подписки упала
        charge_id = (payment.telegram_payment_charge_id if payment else None) or "—"
        logger.error(
            f"[PAYMENT][CRITICAL] activate_subscription FAILED after successful payment: "
            f"uid={user_id} payload={payment.invoice_payload!r} "
            f"amount={payment.total_amount} charge_id={charge_id} error={e!r}"
        )
        # Уведомляем админов
        try:
            for admin_username in ADMIN_USERNAMES:
                pass  # username->id mapping unknown, fallback only via logs
        except Exception:
            pass
        msgs = {
            "ru": (
                "⚠️ <b>Оплата получена, но не удалось активировать подписку.</b>\n\n"
                f"Charge ID: <code>{charge_id}</code>\n"
                "Сохраните это сообщение и напишите в поддержку — подписка будет активирована вручную в течение часа."
            ),
            "en": (
                "⚠️ <b>Payment received but subscription activation failed.</b>\n\n"
                f"Charge ID: <code>{charge_id}</code>\n"
                "Save this message and contact support — subscription will be activated manually within an hour."
            ),
            "he": (
                "⚠️ <b>התשלום התקבל אך הפעלת המנוי נכשלה.</b>\n\n"
                f"Charge ID: <code>{charge_id}</code>\n"
                "שמרו הודעה זו ופנו לתמיכה — המנוי יופעל ידנית תוך שעה."
            ),
        }
        await update.message.reply_text(
            msgs.get(lang, msgs["ru"]),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML",
        )


# ── Admin test command ─────────────────────────────────────────────────────────

ADMIN_USERNAMES = {"IgorPr", "IgorPrasov", "alinatsarenko"}  # only these users can run /testpay

async def cmd_testpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulate a successful payment (admin only). Usage: /testpay [plan] [email]
    Plans: week, two_weeks, month. Example: /testpay week test@example.com"""
    user = update.effective_user
    logger.info(f"[TESTPAY] called by uid={user.id if user else None} username={user.username if user else None!r}")
    if not user or (user.username or "").lower() not in {u.lower() for u in ADMIN_USERNAMES}:
        await update.message.reply_text(f"⛔ Нет доступа. Username: @{user.username if user else '?'}")
        return

    args = context.args or []
    plan_key = args[0] if args else "week"
    test_email = args[1] if len(args) > 1 else None

    if plan_key not in PLANS:
        await update.message.reply_text(f"❌ Неверный план. Варианты: {', '.join(PLANS.keys())}")
        return

    lang = context.user_data.get("lang", "ru")
    expiry = activate_subscription(user.id, plan_key)
    track_subscription(user.id, plan_key)

    plan = PLANS[plan_key]
    plan_name = plan.get(f"name_{lang}") or plan["name_ru"]
    plan_name_he = plan.get("name_he") or plan["name_ru"]
    expiry_str = expiry.strftime("%d.%m.%Y")
    amount_ils = plan.get("price", 0)
    charge_id = f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    buyer_name = " ".join(filter(None, [user.first_name, user.last_name])) or "Test User"

    logger.info(f"[TESTPAY] uid={user.id} plan={plan_key} email={test_email} expiry={expiry_str}")

    if test_email:
        import threading
        threading.Thread(
            target=_send_payment_receipt,
            args=(test_email, buyer_name, plan_name_he, amount_ils, plan.get("days", 7), expiry_str, charge_id),
            daemon=True,
        ).start()

    await update.message.reply_text(
        f"✅ <b>[TEST] Симуляция платежа</b>\n\n"
        f"План: <b>{plan_name}</b>\n"
        f"Активна до: <b>{expiry_str}</b>\n"
        f"Charge ID: <code>{charge_id}</code>\n"
        f"{'📧 Квитанция отправлена на ' + test_email if test_email else '📧 Email не указан — квитанция не отправлена'}\n\n"
        f"Запись в дашборд добавлена ✓",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(context),
    )


async def cmd_grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant bonus days to a user by @username (admin only).
    Usage: /grant @username [days]   — default 5 days.
    Example: /grant @anastasiavaar 5
    """
    user = update.effective_user
    if not user or (user.username or "").lower() not in {u.lower() for u in ADMIN_USERNAMES}:
        await update.message.reply_text("⛔ Нет доступа.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Использование: <code>/grant @username [days]</code>\n"
            "Пример: <code>/grant @anastasiavaar 5</code>",
            parse_mode="HTML",
        )
        return

    target_username = args[0].lstrip("@").strip()
    try:
        days = int(args[1]) if len(args) > 1 else 5
    except ValueError:
        days = 5

    # Look up user_id by username in bot_users table
    target_id = None
    try:
        users_list = db.get_all_bot_users(limit=5000)
        for u in users_list:
            if (u.get("username") or "").lower() == target_username.lower():
                target_id = u["user_id"]
                break
    except Exception as e:
        logger.error(f"[GRANT] Error looking up username: {e}")

    if not target_id:
        await update.message.reply_text(
            f"❌ Пользователь @{target_username} не найден в базе.\n"
            "Пользователь должен был хотя бы раз запустить бота (/start).",
        )
        return

    try:
        db.add_bonus_days(target_id, days)
        from datetime import datetime, timedelta, timezone
        expiry = (datetime.now(tz=timezone.utc) + timedelta(days=days)).strftime("%d.%m.%Y")
        await update.message.reply_text(
            f"✅ Пользователю @{target_username} (id={target_id}) добавлено <b>{days} дней</b> доступа.\n"
            f"Действует до: <b>{expiry}</b>",
            parse_mode="HTML",
        )
        logger.info(f"[GRANT] admin={user.username} → @{target_username}({target_id}) +{days}d")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        logger.error(f"[GRANT] Failed to add bonus days: {e}")


# ── Card payment handler — registered at group=-1 (highest priority) ──────────
# Runs BEFORE any ConversationHandler so it works even mid-conversation.

PAYMENT_PROVIDER_TOKEN = os.environ.get("PAYMENT_PROVIDER_TOKEN", "")

async def handle_stars_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sub_week / sub_two_weeks / sub_month / sub_search_alert callbacks.
    Registered at group=-1 so ConversationHandlers can't swallow them."""
    query = update.callback_query
    data = query.data or ""
    plan_key = data.replace("sub_", "", 1)

    # Show description page for search_alert
    if plan_key == "search_alert":
        await query.answer()
        from keyboards import search_alert_confirm_keyboard
        await query.edit_message_text(
            t("sub_search_alert_desc", context),
            reply_markup=search_alert_confirm_keyboard(context),
            parse_mode="HTML",
        )
        return

    # Direct activate for search_alert_confirm
    if plan_key == "search_alert_confirm":
        await query.answer()
        lang = get_lang(context)
        expiry = activate_subscription(update.effective_user.id, "search_alert")
        plan = PLANS["search_alert"]
        plan_name = plan.get(f"name_{lang}") or plan["name_ru"]
        await query.edit_message_text(
            t("sub_activated", context, plan=plan_name, expiry=expiry.strftime("%d.%m.%Y")),
            reply_markup=back_to_menu_keyboard(context),
            parse_mode="HTML",
        )
        return

    if plan_key not in PLANS:
        await query.answer()
        return

    # Redirect old sub_* buttons to PayPal (same as card_plan_*)
    await query.answer("Создаём ссылку для оплаты...", show_alert=False)
    lang = get_lang(context)
    user_id = update.effective_user.id
    result = morning_payment.create_payment_link(plan_key, user_id, lang)
    if result and result.get("url"):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        plan = PLANS.get(plan_key, {})
        plan_name = plan.get(f"name_{lang}") or plan.get("name_ru", plan_key)
        pay_url = result["url"]
        msgs = {
            "ru": f"💳 <b>Оплата — {plan_name}</b>\n\nНажмите кнопку ниже — откроется страница PayPal.\n\n✅ После оплаты подписка активируется автоматически.",
            "en": f"💳 <b>Payment — {plan_name}</b>\n\nClick below to open the PayPal payment page.\n\n✅ Your subscription will activate automatically after payment.",
            "he": f"💳 <b>תשלום — {plan_name}</b>\n\nלחצו על הכפתור למטה לדף תשלום של PayPal.\n\n✅ המנוי יופעל אוטומטית לאחר התשלום.",
        }
        await query.edit_message_text(
            msgs.get(lang, msgs["ru"]),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton({"ru": f"💳 Оплатить — {plan_name}", "en": f"💳 Pay — {plan_name}", "he": f"💳 לתשלום — {plan_name}"}.get(lang, f"💳 Pay — {plan_name}"), url=pay_url)],
                [InlineKeyboardButton({"ru": "◀ Назад", "en": "◀ Back", "he": "◀ חזרה"}.get(lang, "◀ Back"), callback_data="subscription")],
            ]),
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text(
            {"ru": "⚠️ Не удалось создать ссылку для оплаты. Попробуйте позже.", "en": "⚠️ Failed to create payment link. Try again later.", "he": "⚠️ לא ניתן ליצור קישור לתשלום. נסה שוב מאוחר יותר."}.get(lang, "⚠️ Payment error."),
            reply_markup=subscription_keyboard(context),
            parse_mode="HTML",
        )
