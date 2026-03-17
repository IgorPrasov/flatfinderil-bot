from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import (
    ADD_TITLE, ADD_PROPERTY_TYPE, ADD_CITY, ADD_DISTRICT_AREA,
    ADD_ROOMS, ADD_PRICE, ADD_PARKING, ADD_POOL, ADD_FLOOR,
    ADD_INFRASTRUCTURE, ADD_DESCRIPTION, ADD_CONTACT, ADD_CONFIRM,
)
from keyboards import (
    city_keyboard, rooms_keyboard, parking_keyboard, pool_keyboard,
    infrastructure_keyboard, back_to_menu_keyboard,
    deal_type_add_keyboard, single_property_type_keyboard,
    floor_keyboard, add_confirm_keyboard, DISTRICT_CITIES,
)
from formatters import format_listing_card
from i18n import t, get_lang, get_property_type_name
import database as db

class ListingHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("add", self.start_add), CallbackQueryHandler(self.start_add, pattern="^add_listing$")],
            states={
                ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_title)],
                ADD_PROPERTY_TYPE: [
                    CallbackQueryHandler(self.handle_deal_type, pattern="^add_deal_"),
                    CallbackQueryHandler(self.handle_property_type, pattern="^add_ptype_"),
                ],
                ADD_CITY: [CallbackQueryHandler(self.handle_city, pattern="^city_")],
                ADD_DISTRICT_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_district_area)],
                ADD_ROOMS: [CallbackQueryHandler(self.handle_rooms, pattern="^rooms_min_")],
                ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_price)],
                ADD_PARKING: [CallbackQueryHandler(self.handle_parking, pattern="^park_")],
                ADD_POOL: [CallbackQueryHandler(self.handle_pool, pattern="^pool_")],
                ADD_FLOOR: [CallbackQueryHandler(self.handle_floor, pattern="^floor_")],
                ADD_INFRASTRUCTURE: [CallbackQueryHandler(self.handle_infrastructure, pattern="^infra_")],
                ADD_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_description)],
                ADD_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_contact)],
                ADD_CONFIRM: [
                    CallbackQueryHandler(self.confirm_add, pattern="^confirm_add$"),
                    CallbackQueryHandler(self.cancel_add, pattern="^cancel_add$"),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"), CommandHandler("start", self.cancel)],
            per_message=False, allow_reentry=True,
        )

    async def start_add(self, update, context):
        context.user_data["new_listing"] = {}
        text = t("add_title_step", context)
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
        return ADD_TITLE

    async def handle_title(self, update, context):
        context.user_data["new_listing"]["title"] = update.message.text
        await update.message.reply_text(t("add_deal_step", context), reply_markup=deal_type_add_keyboard(context), parse_mode="HTML")
        return ADD_PROPERTY_TYPE

    async def handle_deal_type(self, update, context):
        query = update.callback_query
        await query.answer()
        deal = query.data.replace("add_deal_", "")
        context.user_data["new_listing"]["deal_type"] = deal
        deal_text = t("deal_rent", context) if deal == "rent" else t("deal_buy", context)
        await query.edit_message_text(f"✅ {deal_text}\n\n" + t("add_ptype_step", context), reply_markup=single_property_type_keyboard(context), parse_mode="HTML")
        return ADD_PROPERTY_TYPE

    async def handle_property_type(self, update, context):
        query = update.callback_query
        await query.answer()
        ptype = query.data.replace("add_ptype_", "")
        context.user_data["new_listing"]["property_type"] = ptype
        lang = get_lang(context)
        await query.edit_message_text(f"✅ {get_property_type_name(ptype, lang)}\n\n" + t("add_city_step", context), reply_markup=city_keyboard(context), parse_mode="HTML")
        return ADD_CITY

    async def handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        city = query.data.replace("city_", "")
        if city == "any":
            await query.answer(t("add_city_specific", context), show_alert=True)
            return ADD_CITY
        context.user_data["new_listing"]["city"] = city
        for dist_key, cities in DISTRICT_CITIES.items():
            if city in cities:
                context.user_data["new_listing"]["district"] = dist_key
                break
        else:
            context.user_data["new_listing"]["district"] = "center"
        await query.edit_message_text(f"✅ {city}\n\n" + t("add_hood_step", context), parse_mode="HTML")
        return ADD_DISTRICT_AREA

    async def handle_district_area(self, update, context):
        context.user_data["new_listing"]["neighborhood"] = update.message.text
        await update.message.reply_text(t("add_rooms_step", context), reply_markup=rooms_keyboard(context, "rooms_min"), parse_mode="HTML")
        return ADD_ROOMS

    async def handle_rooms(self, update, context):
        query = update.callback_query
        await query.answer()
        rooms = query.data.replace("rooms_min_", "")
        if rooms == "any": rooms = "1"
        context.user_data["new_listing"]["rooms"] = rooms
        deal = context.user_data["new_listing"].get("deal_type", "rent")
        unit = {"ru":"₪/мес","en":"₪/mo","he":"₪/חודש"}.get(get_lang(context), "₪/мес") if deal == "rent" else "₪"
        await query.edit_message_text(f"✅ {rooms}\n\n" + t("add_price_step", context, unit=unit), parse_mode="HTML")
        return ADD_PRICE

    async def handle_price(self, update, context):
        try:
            price = int(update.message.text.replace(" ", "").replace(",", ""))
            context.user_data["new_listing"]["price"] = price
            await update.message.reply_text(t("add_parking_step", context), reply_markup=parking_keyboard(context, "park"), parse_mode="HTML")
            return ADD_PARKING
        except ValueError:
            await update.message.reply_text(t("add_price_err", context))
            return ADD_PRICE

    async def handle_parking(self, update, context):
        query = update.callback_query
        await query.answer()
        park = query.data.replace("park_", "")
        context.user_data["new_listing"]["parking"] = 0 if park == "any" else int(park)
        await query.edit_message_text(t("add_pool_step", context), reply_markup=pool_keyboard(context, "pool"), parse_mode="HTML")
        return ADD_POOL

    async def handle_pool(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["new_listing"]["pool"] = query.data.replace("pool_", "") == "yes"
        await query.edit_message_text(t("add_floor_step", context), reply_markup=floor_keyboard(context), parse_mode="HTML")
        return ADD_FLOOR

    async def handle_floor(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["new_listing"]["floor"] = query.data.replace("floor_", "")
        await query.edit_message_text(t("add_infra_step", context), reply_markup=infrastructure_keyboard(context), parse_mode="HTML")
        return ADD_INFRASTRUCTURE

    async def handle_infrastructure(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("infra_", "")
        listing = context.user_data.get("new_listing", {})
        selected = listing.get("infrastructure", [])
        if data in ("skip", "done"):
            listing["infrastructure"] = selected
            context.user_data["new_listing"] = listing
            await query.edit_message_text(t("add_desc_step", context), parse_mode="HTML")
            return ADD_DESCRIPTION
        if data in selected: selected.remove(data)
        else: selected.append(data)
        listing["infrastructure"] = selected
        context.user_data["new_listing"] = listing
        await query.edit_message_text(f"({len(selected)} ✅)\n" + t("add_infra_step", context), reply_markup=infrastructure_keyboard(context, selected), parse_mode="HTML")
        return ADD_INFRASTRUCTURE

    async def handle_description(self, update, context):
        context.user_data["new_listing"]["description"] = update.message.text
        await update.message.reply_text(t("add_contact_step", context))
        return ADD_CONTACT

    async def handle_contact(self, update, context):
        context.user_data["new_listing"]["contact"] = update.message.text
        context.user_data["new_listing"]["user_id"] = update.effective_user.id
        context.user_data["new_listing"]["photos"] = ["🏠"]
        context.user_data["new_listing"]["area_sqm"] = 0
        listing = context.user_data["new_listing"]
        preview = format_listing_card(listing, context)
        await update.message.reply_text(t("add_preview", context) + "\n\n" + preview, reply_markup=add_confirm_keyboard(context), parse_mode="HTML")
        return ADD_CONFIRM

    async def confirm_add(self, update, context):
        query = update.callback_query
        await query.answer()
        listing = context.user_data.get("new_listing", {})
        listing_id = db.add_listing(listing)
        await query.edit_message_text(t("add_published", context, id=listing_id), reply_markup=back_to_menu_keyboard(context), parse_mode="HTML")
        context.user_data.pop("new_listing", None)
        return ConversationHandler.END

    async def cancel_add(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data.pop("new_listing", None)
        await query.edit_message_text(t("add_cancelled", context), reply_markup=back_to_menu_keyboard(context))
        return ConversationHandler.END

    async def cancel(self, update, context):
        context.user_data.pop("new_listing", None)
        if update.callback_query:
            await update.callback_query.answer()
            from handlers import handle_menu
            await handle_menu(update, context)
        else:
            from handlers import start
            await start(update, context)
        return ConversationHandler.END
