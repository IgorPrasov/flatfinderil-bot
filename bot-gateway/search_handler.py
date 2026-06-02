from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
from config import (
    SEARCH_TYPE, SEARCH_PROPERTY_TYPE, SEARCH_DISTRICT, SEARCH_CITY,
    SEARCH_ROOMS, SEARCH_ROOMS_MAX, SEARCH_PRICE_MIN, SEARCH_PRICE_MAX,
    SEARCH_PARKING, SEARCH_POOL, SEARCH_SHELTER, SEARCH_ELEVATOR, SEARCH_INFRASTRUCTURE, SEARCH_WITH_PHOTOS, SEARCH_CONFIRM,
    SEARCH_OWNER_TYPE,
    PRICE_RENT_MIN_OPTIONS_RU, PRICE_RENT_MIN_OPTIONS_EN, PRICE_RENT_MIN_OPTIONS_HE,
    PRICE_RENT_OPTIONS_RU, PRICE_RENT_OPTIONS_EN, PRICE_RENT_OPTIONS_HE,
    PRICE_BUY_MIN_OPTIONS_RU, PRICE_BUY_MIN_OPTIONS_EN, PRICE_BUY_MIN_OPTIONS_HE,
    PRICE_BUY_OPTIONS_RU, PRICE_BUY_OPTIONS_EN, PRICE_BUY_OPTIONS_HE,
)
from keyboards import (
    deal_type_keyboard, property_type_keyboard, district_keyboard, city_keyboard,
    rooms_keyboard, rooms_range_keyboard, parking_keyboard, pool_keyboard,
    infrastructure_keyboard, confirm_search_keyboard, results_navigation_keyboard,
    price_keyboard, back_to_menu_keyboard, shelter_keyboard,
    city_multi_keyboard, district_multi_keyboard, elevator_keyboard, with_photos_keyboard,
    owner_type_keyboard, paywall_keyboard,
)
from formatters import format_search_summary, format_listing_card
from i18n import t, get_lang, get_district_name
from display_utils import display_listing
import database as db
from analytics import track_search, track_user
from subscription import has_access, FREE_SEARCH_LIMIT, is_trial_active
from geocoding import get_city_coords, haversine, format_distance
from overpass import get_pois


def _price_label(value, deal_type, lang):
    if value == 0:
        return {"ru": "любая", "en": "any", "he": "כל מחיר", "fr": "tout"}.get(lang, "any")
    if value >= 999_000_000:
        return {"ru": "без лимита", "en": "no limit", "he": "ללא הגבלה", "fr": "sans limite"}.get(lang)
    if deal_type in ("rent", "sublet"):
        unit = {"ru": "₪/мес", "en": "₪/mo", "he": "₪/חודש", "fr": "₪/mois"}.get(lang, "₪")
        return f"{value:,} {unit}".replace(",", " ")
    if value >= 1_000_000:
        mln = {"ru": "млн ₪", "en": "M ₪", "he": "מיל' ₪", "fr": "M ₪"}.get(lang)
        return f"{value / 1_000_000:.1f} {mln}"
    return f"{value:,} ₪".replace(",", " ")


def _lbl(context, ru, en, he):
    lang = get_lang(context)
    return {"ru": ru, "en": en, "he": he}.get(lang, ru)


def _confirmed(context, ru, en, he, value):
    label = _lbl(context, ru, en, he)
    return "<b>" + label + ":</b> " + str(value)


def _get_price_options(deal_type, lang, is_min):
    if deal_type in ("rent", "sublet"):
        opts = {
            "ru": PRICE_RENT_MIN_OPTIONS_RU if is_min else PRICE_RENT_OPTIONS_RU,
            "en": PRICE_RENT_MIN_OPTIONS_EN if is_min else PRICE_RENT_OPTIONS_EN,
            "he": PRICE_RENT_MIN_OPTIONS_HE if is_min else PRICE_RENT_OPTIONS_HE,
        }
    else:
        opts = {
            "ru": PRICE_BUY_MIN_OPTIONS_RU if is_min else PRICE_BUY_OPTIONS_RU,
            "en": PRICE_BUY_MIN_OPTIONS_EN if is_min else PRICE_BUY_OPTIONS_EN,
            "he": PRICE_BUY_MIN_OPTIONS_HE if is_min else PRICE_BUY_OPTIONS_HE,
        }
    return opts.get(lang, opts["ru"])


class SearchHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("search", self.start_search),
                CallbackQueryHandler(self.start_search, pattern="^search$"),
                CallbackQueryHandler(self.start_search_rent, pattern="^search_rent$"),
                CallbackQueryHandler(self.start_search_sublet, pattern="^search_sublet$"),
                CallbackQueryHandler(self.start_search_buy, pattern="^search_buy$"),
            ],
            states={
                SEARCH_TYPE: [CallbackQueryHandler(self.handle_deal_type, pattern="^deal_")],
                SEARCH_PROPERTY_TYPE: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_property_type, pattern="^ptype_"),
                ],
                SEARCH_DISTRICT: [
                    CallbackQueryHandler(self.handle_back, pattern="^(back$|dist_back$)"),
                    CallbackQueryHandler(self.handle_district, pattern="^(district_|dist_done$)"),
                ],
                SEARCH_CITY: [
                    CallbackQueryHandler(self.handle_back, pattern="^(back$|cities_back$)"),
                    CallbackQueryHandler(self.handle_city, pattern="^(city_|cities_done$)"),
                ],
                SEARCH_ROOMS: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_rooms_min, pattern="^rooms_min_"),
                ],
                SEARCH_ROOMS_MAX: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_rooms_max, pattern="^rooms_max_"),
                ],
                SEARCH_PRICE_MIN: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_price_min, pattern="^pricemin_"),
                ],
                SEARCH_PRICE_MAX: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_price_max, pattern="^pricemax_"),
                ],
                SEARCH_PARKING: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_parking, pattern="^park_"),
                ],
                SEARCH_POOL: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_pool, pattern="^pool_"),
                ],
                SEARCH_SHELTER: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_shelter, pattern="^shelter_"),
                ],
                SEARCH_ELEVATOR: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_elevator, pattern="^elevator_"),
                ],
                SEARCH_INFRASTRUCTURE: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_infrastructure, pattern="^infra_"),
                ],
                SEARCH_WITH_PHOTOS: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_with_photos, pattern="^photos_"),
                ],
                SEARCH_OWNER_TYPE: [
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                    CallbackQueryHandler(self.handle_owner_type, pattern="^owner_"),
                ],
                SEARCH_CONFIRM: [
                    CallbackQueryHandler(self.do_search, pattern="^confirm_search$"),
                    CallbackQueryHandler(self.reset_search, pattern="^reset_search$"),
                    CallbackQueryHandler(self.handle_back, pattern="^back$"),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                CommandHandler("start", self.cancel),
                CommandHandler("cancel", self.cancel),
            ],
            per_message=False, allow_reentry=True,
        )

    async def handle_back(self, update, context):
        query = update.callback_query
        await query.answer()
        state = context.user_data.get("current_state", SEARCH_TYPE)
        f = context.user_data.get("search_filters", {})
        deal_type = f.get("deal_type", "rent")
        lang = get_lang(context)

        if state == SEARCH_PROPERTY_TYPE:
            await query.edit_message_text(t("step_deal", context), reply_markup=deal_type_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_TYPE
            return SEARCH_TYPE
        elif state == SEARCH_DISTRICT:
            await query.edit_message_text(t("step_ptype", context), reply_markup=property_type_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_PROPERTY_TYPE
            return SEARCH_PROPERTY_TYPE
        elif state == SEARCH_CITY:
            await query.edit_message_text(t("step_district", context), reply_markup=district_multi_keyboard(context, f.get("districts", [])), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_DISTRICT
            return SEARCH_DISTRICT
        elif state == SEARCH_ROOMS:
            await query.edit_message_text(t("step_city", context), reply_markup=city_multi_keyboard(context, f.get("cities", []), f.get("districts", [])), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_CITY
            return SEARCH_CITY
        elif state == SEARCH_ROOMS_MAX:
            await query.edit_message_text(t("step_rooms_min", context), reply_markup=rooms_keyboard(context, "rooms_min"), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_ROOMS
            return SEARCH_ROOMS
        elif state == SEARCH_PRICE_MIN:
            await query.edit_message_text(t("step_rooms_max", context), reply_markup=rooms_range_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_ROOMS_MAX
            return SEARCH_ROOMS_MAX
        elif state == SEARCH_PRICE_MAX:
            options = _get_price_options(deal_type, lang, True)
            unit = {"ru": "₪/мес", "en": "₪/mo", "he": "₪/חודש", "fr": "₪/mois"}.get(lang, "₪")
            await query.edit_message_text(t("step_price_min", context, unit=unit), reply_markup=price_keyboard(context, options, "pricemin"), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_PRICE_MIN
            return SEARCH_PRICE_MIN
        elif state == SEARCH_PARKING:
            options = _get_price_options(deal_type, lang, False)
            unit = {"ru": "₪/мес", "en": "₪/mo", "he": "₪/חודש", "fr": "₪/mois"}.get(lang, "₪")
            await query.edit_message_text(t("step_price_max", context, unit=unit), reply_markup=price_keyboard(context, options, "pricemax"), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_PRICE_MAX
            return SEARCH_PRICE_MAX
        elif state == SEARCH_POOL:
            await query.edit_message_text(t("step_parking", context), reply_markup=parking_keyboard(context, "park"), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_PARKING
            return SEARCH_PARKING
        elif state == SEARCH_SHELTER:
            ptypes = f.get("property_types", [])
            deal_type = f.get("deal_type", "rent")
            pool_types = ["house", "villa"]
            show_pool = deal_type in ("rent", "sublet") and ptypes and all(p in pool_types for p in ptypes)
            if show_pool:
                await query.edit_message_text(t("step_pool", context), reply_markup=pool_keyboard(context, "pool"), parse_mode="HTML")
                context.user_data["current_state"] = SEARCH_POOL
                return SEARCH_POOL
            else:
                await query.edit_message_text(t("step_parking", context), reply_markup=parking_keyboard(context, "park"), parse_mode="HTML")
                context.user_data["current_state"] = SEARCH_PARKING
                return SEARCH_PARKING
        elif state == SEARCH_ELEVATOR:
            await query.edit_message_text(t("step_shelter", context), reply_markup=shelter_keyboard(context, "shelter"), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_SHELTER
            return SEARCH_SHELTER
        elif state == SEARCH_INFRASTRUCTURE:
            await query.edit_message_text(t("step_elevator", context), reply_markup=elevator_keyboard(context, "elevator"), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_ELEVATOR
            return SEARCH_ELEVATOR
        elif state == SEARCH_WITH_PHOTOS:
            await query.edit_message_text(t("step_infra", context), reply_markup=infrastructure_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_INFRASTRUCTURE
            return SEARCH_INFRASTRUCTURE
        elif state == SEARCH_OWNER_TYPE:
            await query.edit_message_text(t("step_with_photos", context), reply_markup=with_photos_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_WITH_PHOTOS
            return SEARCH_WITH_PHOTOS
        elif state == SEARCH_CONFIRM:
            await query.edit_message_text(t("step_owner_type", context), reply_markup=owner_type_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_OWNER_TYPE
            return SEARCH_OWNER_TYPE
        else:
            await query.edit_message_text(t("step_deal", context), reply_markup=deal_type_keyboard(context), parse_mode="HTML")
            context.user_data["current_state"] = SEARCH_TYPE
            return SEARCH_TYPE

    async def start_search(self, update, context):
        context.user_data["search_filters"] = {}
        context.user_data["current_state"] = SEARCH_TYPE
        text = t("search_title", context) + "\n\n" + t("step_deal", context)
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=deal_type_keyboard(context), parse_mode="HTML")
        else:
            await update.message.reply_text(text, reply_markup=deal_type_keyboard(context), parse_mode="HTML")
        return SEARCH_TYPE

    async def _start_search_with_deal(self, update, context, deal_type: str):
        """Entry point from main menu rent/buy buttons — skips the deal type step."""
        query = update.callback_query
        await query.answer()
        context.user_data["search_filters"] = {"deal_type": deal_type}
        context.user_data["current_state"] = SEARCH_PROPERTY_TYPE
        deal_text = {"rent": t("deal_rent", context), "buy": t("deal_buy", context), "sublet": t("deal_sublet", context)}.get(deal_type, t("deal_rent", context))
        await query.edit_message_text(
            "✅ " + _confirmed(context, "Тип сделки", "Deal type", "סוג עסקה", deal_text),
            parse_mode="HTML"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("step_ptype", context),
            reply_markup=property_type_keyboard(context),
            parse_mode="HTML"
        )
        return SEARCH_PROPERTY_TYPE

    async def start_search_rent(self, update, context):
        return await self._start_search_with_deal(update, context, "rent")

    async def start_search_sublet(self, update, context):
        return await self._start_search_with_deal(update, context, "sublet")

    async def start_search_buy(self, update, context):
        return await self._start_search_with_deal(update, context, "buy")

    async def handle_deal_type(self, update, context):
        query = update.callback_query
        await query.answer()
        deal_type = query.data.replace("deal_", "")
        context.user_data["search_filters"]["deal_type"] = deal_type
        context.user_data["current_state"] = SEARCH_PROPERTY_TYPE
        if deal_type == "rent":
            deal_text = t("deal_rent", context)
        elif deal_type == "sublet":
            deal_text = t("deal_sublet", context)
        else:
            deal_text = t("deal_buy", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Тип сделки", "Deal type", "סוג עסקה", deal_text), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_ptype", context), reply_markup=property_type_keyboard(context), parse_mode="HTML")
        return SEARCH_PROPERTY_TYPE

    async def handle_property_type(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("ptype_", "")
        f = context.user_data.get("search_filters", {})
        selected = f.get("property_types", [])
        context.user_data["current_state"] = SEARCH_DISTRICT
        if data == "all":
            f["property_types"] = []
            context.user_data["search_filters"] = f
            all_text = _lbl(context, "Все типы", "All types", "כל הסוגים")
            await query.edit_message_text("✅ " + _confirmed(context, "Тип жилья", "Property type", "סוג נכס", all_text), parse_mode="HTML")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_district", context), reply_markup=district_multi_keyboard(context, []), parse_mode="HTML")
            return SEARCH_DISTRICT
        elif data == "next":
            context.user_data["search_filters"] = f
            lang = get_lang(context)
            from i18n import get_property_type_name
            sel_names = ", ".join([get_property_type_name(p, lang) for p in selected]) if selected else _lbl(context, "Все", "All", "הכל")
            await query.edit_message_text("✅ " + _confirmed(context, "Тип жилья", "Property type", "סוג נכס", sel_names), parse_mode="HTML")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_district", context), reply_markup=district_multi_keyboard(context, []), parse_mode="HTML")
            return SEARCH_DISTRICT
        else:
            context.user_data["current_state"] = SEARCH_PROPERTY_TYPE
            if data in selected: selected.remove(data)
            else: selected.append(data)
            f["property_types"] = selected
            context.user_data["search_filters"] = f
            n = len(selected) if selected else t("btn_all_types", context)
            await query.edit_message_text(t("confirmed_ptype_sel", context, n=n), reply_markup=property_type_keyboard(context, selected), parse_mode="HTML")
            return SEARCH_PROPERTY_TYPE

    async def handle_district(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data
        f = context.user_data.get("search_filters", {})
        selected_districts = f.get("districts", [])
        if data == "dist_done":
            f["districts"] = selected_districts
            f["district"] = selected_districts[0] if len(selected_districts) == 1 else None
            context.user_data["search_filters"] = f
            context.user_data["current_state"] = SEARCH_CITY
            lang = get_lang(context)
            dist_names = ", ".join([get_district_name(d, lang) for d in selected_districts]) if selected_districts else t("all_israel", context)
            await query.edit_message_text("✅ " + _confirmed(context, "Округ", "District", "מחוז", dist_names), parse_mode="HTML")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_city", context), reply_markup=city_multi_keyboard(context, [], selected_districts), parse_mode="HTML")
            return SEARCH_CITY
        district = data.replace("district_", "")
        if district in selected_districts: selected_districts.remove(district)
        else: selected_districts.append(district)
        f["districts"] = selected_districts
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_DISTRICT
        count_str = str(len(selected_districts)) if selected_districts else ""
        extra = ("\n\n" + _lbl(context, "Выбрано", "Selected", "נבחר") + ": " + count_str) if selected_districts else ""
        await query.edit_message_text(t("step_district", context) + extra, reply_markup=district_multi_keyboard(context, selected_districts), parse_mode="HTML")
        return SEARCH_DISTRICT

    async def handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data
        f = context.user_data.get("search_filters", {})
        selected_cities = f.get("cities", [])
        selected_districts = f.get("districts", [])
        if data == "cities_done":
            f["cities"] = selected_cities
            f["city"] = selected_cities[0] if len(selected_cities) == 1 else None
            context.user_data["search_filters"] = f
            context.user_data["current_state"] = SEARCH_ROOMS
            from city_translations import get_city_name
            lang = get_lang(context)
            cities_str = ", ".join([get_city_name(c, lang) for c in selected_cities]) if selected_cities else t("any_city", context)
            await query.edit_message_text("✅ " + _confirmed(context, "Город", "City", "עיר", cities_str), parse_mode="HTML")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_rooms_min", context), reply_markup=rooms_keyboard(context, "rooms_min"), parse_mode="HTML")
            return SEARCH_ROOMS
        if data == "city_any":
            f["cities"] = []
            f["city"] = None
            context.user_data["search_filters"] = f
            context.user_data["current_state"] = SEARCH_ROOMS
            await query.edit_message_text("✅ " + _confirmed(context, "Город", "City", "עיר", t("any_city", context)), parse_mode="HTML")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_rooms_min", context), reply_markup=rooms_keyboard(context, "rooms_min"), parse_mode="HTML")
            return SEARCH_ROOMS
        if data.startswith("city_"):
            city = data.replace("city_", "")
            if city in selected_cities: selected_cities.remove(city)
            else: selected_cities.append(city)
            f["cities"] = selected_cities
            context.user_data["search_filters"] = f
            context.user_data["current_state"] = SEARCH_CITY
            from city_translations import get_city_name
            lang = get_lang(context)
            sel_str = ", ".join([get_city_name(c, lang) for c in selected_cities]) if selected_cities else ""
            extra = ("\n\n" + sel_str) if sel_str else ""
            await query.edit_message_text(t("step_city", context) + extra, reply_markup=city_multi_keyboard(context, selected_cities, selected_districts), parse_mode="HTML")
            return SEARCH_CITY
        return SEARCH_CITY

    async def handle_rooms_min(self, update, context):
        query = update.callback_query
        await query.answer()
        rooms_min = query.data.replace("rooms_min_", "")
        f = context.user_data.get("search_filters", {})
        f["rooms_min"] = rooms_min if rooms_min != "any" else None
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_ROOMS_MAX
        rooms_display = rooms_min if rooms_min != "any" else t("rooms_not_imp", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Комнат от", "Rooms from", "חדרים מ", rooms_display), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_rooms_max", context), reply_markup=rooms_range_keyboard(context, rooms_min if rooms_min != "any" else None), parse_mode="HTML")
        return SEARCH_ROOMS_MAX

    async def handle_rooms_max(self, update, context):
        query = update.callback_query
        await query.answer()
        rooms_max = query.data.replace("rooms_max_", "")
        f = context.user_data.get("search_filters", {})
        f["rooms_max"] = rooms_max if rooms_max != "any" else None
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_PRICE_MIN
        rooms_display = rooms_max if rooms_max != "any" else t("btn_no_limit", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Комнат до", "Rooms up to", "חדרים עד", rooms_display), parse_mode="HTML")
        deal_type = f.get("deal_type", "rent")
        lang = get_lang(context)
        options = _get_price_options(deal_type, lang, True)
        unit = {"ru": "₪/мес", "en": "₪/mo", "he": "₪/חודש", "fr": "₪/mois"}.get(lang, "₪")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_price_min", context, unit=unit), reply_markup=price_keyboard(context, options, "pricemin"), parse_mode="HTML")
        return SEARCH_PRICE_MIN

    async def handle_price_min(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("pricemin_", ""))
        f = context.user_data.get("search_filters", {})
        f["price_min"] = val if val > 0 else None
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_PRICE_MAX
        deal_type = f.get("deal_type", "rent")
        lang = get_lang(context)
        options = _get_price_options(deal_type, lang, False)
        unit = {"ru": "₪/мес", "en": "₪/mo", "he": "₪/חודש", "fr": "₪/mois"}.get(lang, "₪")
        min_label = _price_label(val, deal_type, lang)
        await query.edit_message_text("✅ " + _confirmed(context, "Цена от", "Price from", "מחיר מ", min_label), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_price_max", context, unit=unit), reply_markup=price_keyboard(context, options, "pricemax"), parse_mode="HTML")
        return SEARCH_PRICE_MAX

    async def handle_price_max(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("pricemax_", ""))
        f = context.user_data.get("search_filters", {})
        f["price_max"] = val if val < 999_000_000 else None
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_PARKING
        deal_type = f.get("deal_type", "rent")
        lang = get_lang(context)
        max_label = _price_label(val, deal_type, lang)
        await query.edit_message_text("✅ " + _confirmed(context, "Цена до", "Price up to", "מחיר עד", max_label), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_parking", context), reply_markup=parking_keyboard(context, "park"), parse_mode="HTML")
        return SEARCH_PARKING

    async def handle_parking(self, update, context):
        query = update.callback_query
        await query.answer()
        park_val = query.data.replace("park_", "")
        f = context.user_data.get("search_filters", {})
        f["parking_min"] = None if park_val == "any" else int(park_val)
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_POOL
        park_label = park_val if park_val != "any" else t("btn_any_parking", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Парковка", "Parking", "חניה", park_label), parse_mode="HTML")
        ptypes = f.get("property_types", [])
        deal_type = f.get("deal_type", "rent")
        pool_types = ["house", "villa"]
        show_pool = deal_type in ("rent", "sublet") and ptypes and all(p in pool_types for p in ptypes)
        if show_pool:
            context.user_data["current_state"] = SEARCH_POOL
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_pool", context), reply_markup=pool_keyboard(context, "pool"), parse_mode="HTML")
            return SEARCH_POOL
        else:
            f["pool"] = None
            context.user_data["search_filters"] = f
            context.user_data["current_state"] = SEARCH_SHELTER
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_shelter", context), reply_markup=shelter_keyboard(context, "shelter"), parse_mode="HTML")
            return SEARCH_SHELTER

    async def handle_pool(self, update, context):
        query = update.callback_query
        await query.answer()
        pool_val = query.data.replace("pool_", "")
        f = context.user_data.get("search_filters", {})
        f["pool"] = True if pool_val == "yes" else None
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_SHELTER
        pool_label = t("btn_pool_yes", context) if pool_val == "yes" else t("btn_pool_any", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Бассейн", "Pool", "בריכה", pool_label), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_shelter", context), reply_markup=shelter_keyboard(context, "shelter"), parse_mode="HTML")
        return SEARCH_SHELTER

    async def handle_shelter(self, update, context):
        query = update.callback_query
        await query.answer()
        shelter_val = query.data.replace("shelter_", "")
        f = context.user_data.get("search_filters", {})
        f["shelter"] = None if shelter_val == "any" else shelter_val
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_ELEVATOR
        shelter_labels = {
            "mamad": t("btn_shelter_mamad", context),
            "miklat": t("btn_shelter_miklat", context),
            "none": t("btn_shelter_none", context),
            "any": t("btn_shelter_any", context),
        }
        shelter_label = shelter_labels.get(shelter_val, shelter_val)
        await query.edit_message_text("✅ " + _confirmed(context, "Защитное помещение", "Shelter", "מרחב מוגן", shelter_label), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_elevator", context), reply_markup=elevator_keyboard(context, "elevator"), parse_mode="HTML")
        return SEARCH_ELEVATOR

    async def handle_elevator(self, update, context):
        query = update.callback_query
        await query.answer()
        elevator_val = query.data.replace("elevator_", "")
        f = context.user_data.get("search_filters", {})
        f["elevator"] = None if elevator_val == "any" else elevator_val
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_INFRASTRUCTURE
        elevator_label = t("btn_elevator_yes", context) if elevator_val == "yes" else t("btn_elevator_any", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Лифт", "Elevator", "מעלית", elevator_label), parse_mode="HTML")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_infra", context), reply_markup=infrastructure_keyboard(context), parse_mode="HTML")
        return SEARCH_INFRASTRUCTURE

    async def handle_infrastructure(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("infra_", "")
        f = context.user_data.get("search_filters", {})
        selected = f.get("infrastructure", [])
        if data in ("skip", "done"):
            f["infrastructure"] = selected if selected else None
            context.user_data["search_filters"] = f
            context.user_data["current_state"] = SEARCH_WITH_PHOTOS
            lang = get_lang(context)
            from i18n import get_infra_name
            infra_str = ", ".join([get_infra_name(k, lang) for k in selected]) if selected else t("btn_skip", context)
            await query.edit_message_text("✅ " + _confirmed(context, "Инфраструктура", "Infrastructure", "תשתיות", infra_str), parse_mode="HTML")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=t("step_with_photos", context), reply_markup=with_photos_keyboard(context), parse_mode="HTML")
            return SEARCH_WITH_PHOTOS
        if data in selected: selected.remove(data)
        else: selected.append(data)
        f["infrastructure"] = selected
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_INFRASTRUCTURE
        await query.edit_message_text(t("infra_selected", context, n=len(selected)), reply_markup=infrastructure_keyboard(context, selected), parse_mode="HTML")
        return SEARCH_INFRASTRUCTURE


    async def handle_with_photos(self, update, context):
        query = update.callback_query
        await query.answer()
        f = context.user_data.get("search_filters", {})
        f["with_photos"] = (query.data == "photos_yes")
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_OWNER_TYPE
        label = t("sum_with_photos", context) if f["with_photos"] else t("btn_pool_any", context)
        await query.edit_message_text("✅ " + _confirmed(context, "Фото", "Photos", "תמונות", label), parse_mode="HTML")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("step_owner_type", context),
            reply_markup=owner_type_keyboard(context),
            parse_mode="HTML",
        )
        return SEARCH_OWNER_TYPE

    async def handle_owner_type(self, update, context):
        query = update.callback_query
        await query.answer()
        f = context.user_data.get("search_filters", {})
        data = query.data  # owner_private | owner_agent | owner_any
        if data == "owner_private":
            f["seller_type"] = "private"
            label = t("sum_owner_private", context)
        elif data == "owner_agent":
            f["seller_type"] = "agent"
            label = t("sum_owner_agent", context)
        else:
            f.pop("seller_type", None)
            label = t("btn_pool_any", context)
        context.user_data["search_filters"] = f
        context.user_data["current_state"] = SEARCH_CONFIRM
        await query.edit_message_text(
            "✅ " + _confirmed(context, "Продавец", "Seller", "מוכר", label),
            parse_mode="HTML",
        )
        summary = format_search_summary(f, context)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=summary + t("step_confirm", context),
            reply_markup=confirm_search_keyboard(context),
            parse_mode="HTML",
        )
        return SEARCH_CONFIRM

    async def do_search(self, update, context):
        import logging as _log
        _logger = _log.getLogger(__name__)
        query = update.callback_query
        await query.answer("🔍...")
        lang = get_lang(context)
        err_msg = {"ru": "⚠️ Ошибка поиска. Попробуйте ещё раз.", "en": "⚠️ Search error. Please try again.", "he": "⚠️ שגיאת חיפוש. נסה שוב."}.get(lang, "⚠️ Search error. Try again.")

        try:
            f = context.user_data.get("search_filters", {})
            track_search(update.effective_user.id, f)
            user_id = update.effective_user.id
            paid = is_trial_active() or has_access(user_id)
            db_limit = 100 if paid else FREE_SEARCH_LIMIT + 1

            results = db.search_listings(f, limit=db_limit)

            if not results:
                await query.edit_message_text(t("no_results", context), reply_markup=confirm_search_keyboard(context), parse_mode="HTML")
                return SEARCH_CONFIRM

            # Sort by proximity if infrastructure filter is active
            infra_filter = f.get("infrastructure") or []
            if infra_filter:
                results = _sort_by_proximity(results, infra_filter)

            # Paywall: limit to FREE_SEARCH_LIMIT after trial
            total_found = len(results)
            if not paid and total_found > FREE_SEARCH_LIMIT:
                results = results[:FREE_SEARCH_LIMIT]
                context.user_data["results"] = results
                await query.edit_message_text(t("found_n", context, n=total_found), parse_mode="HTML")
                await display_listing(query, context, results[0], 0, len(results))
                paywall_text = t("paywall_search", context, total=total_found)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=paywall_text,
                    reply_markup=paywall_keyboard(context),
                    parse_mode="HTML",
                )
                return ConversationHandler.END

            context.user_data["results"] = results
            await query.edit_message_text(t("found_n", context, n=total_found), parse_mode="HTML")
            await display_listing(query, context, results[0], 0, len(results))

            # For "buy" searches — offer mortgage broker button
            if f.get("deal_type") == "buy":
                lang = get_lang(context)
                broker_text = {
                    "ru": "💰 <b>Нужна ипотека?</b>\n\nНайдём кредитного брокера — специалиста по ипотеке в Израиле.",
                    "en": "💰 <b>Need a mortgage?</b>\n\nFind a mortgage broker — a specialist who will help you get the best loan.",
                    "he": "💰 <b>צריך משכנתא?</b>\n\nמצא יועץ משכנתאות — מומחה שיעזור לך לקבל את ההלוואה הטובה ביותר.",
                    "fr": "💰 <b>Besoin d'un crédit immobilier?</b>\n\nTrouvez un courtier en prêt — un spécialiste qui vous aidera à obtenir le meilleur taux.",
                }.get(lang, "💰 <b>Need a mortgage?</b>\n\nFind a mortgage broker.")
                broker_btn_label = {
                    "ru": "💰 Найти кредитного брокера",
                    "en": "💰 Find Mortgage Broker",
                    "he": "💰 מצא יועץ משכנתאות",
                    "fr": "💰 Trouver un courtier",
                }.get(lang, "💰 Find Mortgage Broker")
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton(broker_btn_label, callback_data="find_mortgage_broker")
                ]])
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=broker_text,
                    reply_markup=kb,
                    parse_mode="HTML",
                )

            return ConversationHandler.END

        except Exception as _e:
            _logger.error(f"[SEARCH] do_search error: {_e!r}", exc_info=True)
            try:
                await query.edit_message_text(err_msg, reply_markup=confirm_search_keyboard(context), parse_mode="HTML")
            except Exception:
                try:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=err_msg)
                except Exception:
                    pass
            return SEARCH_CONFIRM

    async def reset_search(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["search_filters"] = {}
        context.user_data["current_state"] = SEARCH_TYPE
        await query.edit_message_text(t("reset_done", context), reply_markup=deal_type_keyboard(context), parse_mode="HTML")
        return SEARCH_TYPE

    async def cancel(self, update, context):
        if update.callback_query:
            await update.callback_query.answer()
            from handlers import handle_menu
            await handle_menu(update, context)
        else:
            from handlers import start
            await start(update, context)
        return ConversationHandler.END


def _sort_by_proximity(results: list, infra_types: list) -> list:
    """
    Sort listings by distance to the nearest POI of the requested infrastructure types.
    Each listing gets a '_nearest_m' annotation for display.
    Listings without city coordinates go to the end.
    """
    if not infra_types or not results:
        return results

    # Collect unique cities to avoid duplicate Overpass queries
    poi_cache = {}  # (city_lower, infra_type) -> list of (lat, lng)

    def get_cached_pois(city: str, itype: str):
        key = (city.lower().strip(), itype)
        if key not in poi_cache:
            coords = get_city_coords(city)
            if coords:
                poi_cache[key] = get_pois(coords[0], coords[1], itype, radius=5000)
            else:
                poi_cache[key] = []
        return poi_cache[key]

    def listing_min_dist(listing: dict) -> float:
        city = listing.get("city", "")
        coords = get_city_coords(city)
        if not coords:
            return float("inf")

        # Use stored coordinates if available, otherwise fall back to city center
        lat = listing.get("lat") or coords[0]
        lng = listing.get("lng") or coords[1]

        min_d = float("inf")
        for itype in infra_types:
            pois = get_cached_pois(city, itype)
            for plat, plng in pois:
                d = haversine(lat, lng, plat, plng)
                if d < min_d:
                    min_d = d
        return min_d

    # Annotate each listing with distance
    annotated = []
    for listing in results:
        dist = listing_min_dist(listing)
        entry = dict(listing)
        entry["_nearest_m"] = dist
        annotated.append(entry)

    annotated.sort(key=lambda x: x["_nearest_m"])
    return annotated


