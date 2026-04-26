from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
from config import COMMERCIAL_DEAL, COMMERCIAL_TYPE, COMMERCIAL_CITY, COMMERCIAL_PRICE_MIN, COMMERCIAL_PRICE_MAX, COMMERCIAL_CONFIRM
from keyboards import commercial_deal_keyboard, commercial_type_keyboard, commercial_city_keyboard, commercial_price_keyboard, back_to_menu_keyboard
from i18n import t, get_lang
from formatters import format_listing_card
import database as db


class CommercialHandler:
    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start, pattern="^commercial$"),
            ],
            states={
                COMMERCIAL_DEAL: [
                    CallbackQueryHandler(self.handle_deal, pattern="^comm_deal_"),
                    CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                ],
                COMMERCIAL_TYPE: [
                    CallbackQueryHandler(self.handle_type, pattern="^comm_type_"),
                    CallbackQueryHandler(self.handle_back, pattern="^comm_back$"),
                ],
                COMMERCIAL_CITY: [
                    CallbackQueryHandler(self.handle_city, pattern="^comm_city_"),
                    CallbackQueryHandler(self.handle_back, pattern="^comm_back$"),
                ],
                COMMERCIAL_PRICE_MIN: [
                    CallbackQueryHandler(self.handle_price_min, pattern="^comm_pricemin_"),
                    CallbackQueryHandler(self.handle_back, pattern="^comm_back$"),
                ],
                COMMERCIAL_PRICE_MAX: [
                    CallbackQueryHandler(self.handle_price_max, pattern="^comm_pricemax_"),
                    CallbackQueryHandler(self.handle_back, pattern="^comm_back$"),
                ],
                COMMERCIAL_CONFIRM: [
                    CallbackQueryHandler(self.do_search, pattern="^comm_search$"),
                    CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel, pattern="^back_to_menu$"),
                CommandHandler("start", self.cancel),
                CommandHandler("cancel", self.cancel),
            ],
            per_message=False, allow_reentry=True,
        )

    async def start(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["comm_filters"] = {}
        context.user_data["comm_state"] = COMMERCIAL_DEAL
        await query.edit_message_text(
            t("commercial_welcome", context),
            reply_markup=commercial_deal_keyboard(context),
            parse_mode="HTML"
        )
        return COMMERCIAL_DEAL

    async def handle_deal(self, update, context):
        query = update.callback_query
        await query.answer()
        deal_type = query.data.replace("comm_deal_", "")
        context.user_data["comm_filters"]["deal_type"] = deal_type
        context.user_data["comm_state"] = COMMERCIAL_TYPE
        await query.edit_message_text(
            t("commercial_step_type", context),
            reply_markup=commercial_type_keyboard(context),
            parse_mode="HTML"
        )
        return COMMERCIAL_TYPE

    async def handle_type(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("comm_type_", "")
        f = context.user_data["comm_filters"]
        if data == "all":
            f["property_types"] = []
            # Move to city
            context.user_data["comm_state"] = COMMERCIAL_CITY
            await query.edit_message_text(
                t("commercial_step_city", context),
                reply_markup=commercial_city_keyboard(context),
                parse_mode="HTML"
            )
            return COMMERCIAL_CITY
        else:
            selected = f.get("property_types", [])
            if data in selected:
                selected.remove(data)
            else:
                selected.append(data)
            f["property_types"] = selected
            # Update keyboard to show selection
            await query.edit_message_reply_markup(reply_markup=commercial_type_keyboard(context, selected))
            return COMMERCIAL_TYPE

    async def handle_city(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("comm_city_", "")
        f = context.user_data["comm_filters"]
        if data == "all":
            f["cities"] = []
        else:
            f["cities"] = [data]
        context.user_data["comm_state"] = COMMERCIAL_PRICE_MIN
        deal_type = f.get("deal_type", "rent")
        await query.edit_message_text(
            t("commercial_step_price", context) + "\n\n<b>Цена от:</b>",
            reply_markup=commercial_price_keyboard(context, "comm_pricemin", deal_type),
            parse_mode="HTML"
        )
        return COMMERCIAL_PRICE_MIN

    async def handle_price_min(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("comm_pricemin_", ""))
        f = context.user_data["comm_filters"]
        if val > 0:
            f["price_min"] = val
        deal_type = f.get("deal_type", "rent")
        context.user_data["comm_state"] = COMMERCIAL_PRICE_MAX
        await query.edit_message_text(
            t("commercial_step_price", context) + "\n\n<b>Цена до:</b>",
            reply_markup=commercial_price_keyboard(context, "comm_pricemax", deal_type),
            parse_mode="HTML"
        )
        return COMMERCIAL_PRICE_MAX

    async def handle_price_max(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("comm_pricemax_", ""))
        f = context.user_data["comm_filters"]
        if val > 0 and val < 999999999:
            f["price_max"] = val
        # Run search directly
        context.user_data["comm_state"] = COMMERCIAL_CONFIRM
        await self._show_results(update, context)
        return ConversationHandler.END

    async def handle_back(self, update, context):
        query = update.callback_query
        await query.answer()
        state = context.user_data.get("comm_state", COMMERCIAL_DEAL)
        f = context.user_data.get("comm_filters", {})
        if state == COMMERCIAL_TYPE:
            await query.edit_message_text(t("commercial_welcome", context), reply_markup=commercial_deal_keyboard(context), parse_mode="HTML")
            context.user_data["comm_state"] = COMMERCIAL_DEAL
            return COMMERCIAL_DEAL
        elif state == COMMERCIAL_CITY:
            await query.edit_message_text(t("commercial_step_type", context), reply_markup=commercial_type_keyboard(context, f.get("property_types", [])), parse_mode="HTML")
            context.user_data["comm_state"] = COMMERCIAL_TYPE
            return COMMERCIAL_TYPE
        elif state == COMMERCIAL_PRICE_MIN:
            await query.edit_message_text(t("commercial_step_city", context), reply_markup=commercial_city_keyboard(context), parse_mode="HTML")
            context.user_data["comm_state"] = COMMERCIAL_CITY
            return COMMERCIAL_CITY
        elif state == COMMERCIAL_PRICE_MAX:
            await query.edit_message_text(t("commercial_step_price", context) + "\n\n<b>Цена от:</b>", reply_markup=commercial_price_keyboard(context, "comm_pricemin", f.get("deal_type", "rent")), parse_mode="HTML")
            context.user_data["comm_state"] = COMMERCIAL_PRICE_MIN
            return COMMERCIAL_PRICE_MIN
        return COMMERCIAL_DEAL

    async def _show_results(self, update, context):
        query = update.callback_query
        f = context.user_data.get("comm_filters", {})
        from config import COMMERCIAL_TYPES
        comm_types = list(COMMERCIAL_TYPES.keys())
        selected_types = f.get("property_types") or comm_types
        filters = {
            "deal_type": f.get("deal_type", "rent"),
            "property_types": selected_types,
            "cities": f.get("cities", []),
            "price_min": f.get("price_min"),
            "price_max": f.get("price_max"),
        }
        results = db.search_listings(filters)
        if not results:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("commercial_no_results", context),
                reply_markup=back_to_menu_keyboard(context),
                parse_mode="HTML"
            )
            return
        context.user_data["results"] = results
        context.user_data["result_index"] = 0
        listing = results[0]
        from display_utils import display_listing
        await display_listing(update, context, listing, 0, len(results))

    async def do_search(self, update, context):
        await self._show_results(update, context)
        return ConversationHandler.END

    async def cancel(self, update, context):
        from keyboards import main_menu_keyboard
        from formatters import format_welcome
        text = format_welcome(update.effective_user.first_name, context)
        kb = main_menu_keyboard(context)
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
        context.user_data.pop("comm_filters", None)
        return ConversationHandler.END
