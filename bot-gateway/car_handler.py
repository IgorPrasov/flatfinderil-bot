"""
car_handler.py — CarsFinderIL vertical inside the FlatFinderIL hub.

Two conversation flows:
  • Search  (car_search_start → …)   — filter by body type / city / price / year
  • Add     (car_add_start → …)      — post your own car for sale

Plus a lightweight, non-conversation "cabinet" for managing your own vehicles
(car_my_listings / car_manage_ / car_deact_ / car_react_ / car_delete_).

Vehicle data lives in its own `vehicle_listings` table (see schema.sql) —
completely separate from the housing `listings` table, so nothing here can
leak into or break real-estate / commercial search results.
"""
import re
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import (
    CAR_MENU, CAR_SEARCH_BODY, CAR_SEARCH_CITY, CAR_SEARCH_PRICE_MIN, CAR_SEARCH_PRICE_MAX, CAR_SEARCH_YEAR,
    CAR_ADD_MAKE, CAR_ADD_MODEL, CAR_ADD_YEAR, CAR_ADD_MILEAGE, CAR_ADD_TRANSMISSION,
    CAR_ADD_FUEL, CAR_ADD_HAND, CAR_ADD_BODY, CAR_ADD_PRICE, CAR_ADD_CITY,
    CAR_ADD_DESCRIPTION, CAR_ADD_CONTACT, CAR_ADD_PHOTOS, CAR_ADD_CONFIRM,
    CAR_BODY_TYPES, CAR_TRANSMISSION, CAR_FUEL,
)
from keyboards import (
    car_menu_keyboard, car_body_keyboard, car_make_keyboard, car_city_keyboard,
    car_price_keyboard, car_year_keyboard, car_transmission_keyboard, car_fuel_keyboard,
    car_hand_keyboard, car_body_single_keyboard, car_confirm_keyboard, car_skip_keyboard,
    car_photos_keyboard, car_cabinet_keyboard, car_manage_keyboard, back_to_menu_keyboard, main_menu_keyboard,
)
from formatters import format_welcome
import database as db

logger = logging.getLogger(__name__)


def _car_card_text(v: dict) -> str:
    status = "🟢 Активно" if v.get("active", True) else "🔴 Снято с публикации"
    trans = CAR_TRANSMISSION.get(v.get("transmission"), "")
    fuel = CAR_FUEL.get(v.get("fuel_type"), "")
    hand = v.get("hand")
    hand_line = f"👤 {hand}-я рука\n" if hand else ""
    desc = (v.get("description") or "").strip()[:500]
    desc_line = f"\n📝 {desc}" if desc else ""
    contact = v.get("contact") or ""
    contact_line = f"\n📞 <b>Контакт:</b> {contact}" if contact else ""
    return (
        f"🚗 <b>{v.get('make','')} {v.get('model','')}</b> {v.get('year') or ''}\n\n"
        f"💰 {v.get('price', 0):,} ₪\n".replace(",", " ") +
        f"📍 {v.get('city', '—')}\n"
        f"🛣 {v.get('mileage_km', 0):,} км\n".replace(",", " ") +
        f"⚙️ {trans}   {fuel}\n"
        f"{hand_line}"
        f"👁 {v.get('views', 0)} просмотров\n"
        f"Статус: {status}"
        f"{contact_line}"
        f"{desc_line}"
    )[:4000]


async def _send_car_card(context, chat_id, v: dict):
    """Send a vehicle card — as a photo with caption if it has photos, else plain text."""
    text = _car_card_text(v)
    photos = v.get("photos") or []
    if photos:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=photos[0], caption=text, parse_mode="HTML")
            return
        except Exception:
            pass  # fall through to plain text if the file_id is stale/invalid
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")


class CarHandler:
    # ── Menu / cabinet (plain callbacks, outside conversation state) ────────

    async def open_menu(self, update, context):
        query = update.callback_query
        await query.answer()
        text = "🚗 <b>CarsFinderIL</b>\n\nПоиск и продажа авто в Израиле.\nЧто хотите сделать?"
        await query.edit_message_text(text, reply_markup=car_menu_keyboard(context), parse_mode="HTML")

    async def my_listings(self, update, context):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        vehicles = db.get_user_vehicles(user_id) if hasattr(db, "get_user_vehicles") else []
        if not vehicles:
            await query.edit_message_text(
                "У вас пока нет размещённых авто.",
                reply_markup=car_menu_keyboard(context), parse_mode="HTML"
            )
            return
        await query.edit_message_text(
            f"📋 Ваши авто ({len(vehicles)}):",
            reply_markup=car_cabinet_keyboard(context, vehicles), parse_mode="HTML"
        )

    async def manage_vehicle(self, update, context):
        query = update.callback_query
        await query.answer()
        vid = int(query.data.replace("car_manage_", ""))
        v = db.get_vehicle(vid)
        if not v or v.get("user_id") != update.effective_user.id:
            await query.edit_message_text("Объявление не найдено.", reply_markup=car_menu_keyboard(context))
            return
        await query.edit_message_text(
            _car_card_text(v), reply_markup=car_manage_keyboard(context, vid, v.get("active", True)),
            parse_mode="HTML"
        )

    async def deactivate_vehicle(self, update, context):
        query = update.callback_query
        await query.answer()
        vid = int(query.data.replace("car_deact_", ""))
        v = db.get_vehicle(vid)
        if v and v.get("user_id") == update.effective_user.id:
            db.set_vehicle_active(vid, False)
        await self.manage_vehicle_by_id(update, context, vid)

    async def reactivate_vehicle(self, update, context):
        query = update.callback_query
        await query.answer()
        vid = int(query.data.replace("car_react_", ""))
        v = db.get_vehicle(vid)
        if v and v.get("user_id") == update.effective_user.id:
            db.set_vehicle_active(vid, True)
        await self.manage_vehicle_by_id(update, context, vid)

    async def manage_vehicle_by_id(self, update, context, vid):
        v = db.get_vehicle(vid)
        query = update.callback_query
        await query.edit_message_text(
            _car_card_text(v), reply_markup=car_manage_keyboard(context, vid, v.get("active", True)),
            parse_mode="HTML"
        )

    async def delete_vehicle(self, update, context):
        query = update.callback_query
        await query.answer()
        vid = int(query.data.replace("car_delete_", ""))
        v = db.get_vehicle(vid)
        if v and v.get("user_id") == update.effective_user.id:
            db.delete_vehicle(vid)
        await self.my_listings(update, context)

    # ── Search flow ───────────────────────────────────────────────────────

    async def start_search(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["car_search"] = {}
        await query.edit_message_text(
            "🔍 <b>Поиск авто</b>\n\nШаг 1/4: Тип кузова (можно несколько)",
            reply_markup=car_body_keyboard(context, []), parse_mode="HTML"
        )
        return CAR_SEARCH_BODY

    async def handle_search_body(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("car_body_", "")
        f = context.user_data.setdefault("car_search", {})
        if data == "all":
            f["body_types"] = []
            await query.edit_message_text(
                "Шаг 2/4: Город", reply_markup=car_city_keyboard(context, "car_city"), parse_mode="HTML"
            )
            return CAR_SEARCH_CITY
        selected = f.get("body_types", [])
        if data in selected:
            selected.remove(data)
        else:
            selected.append(data)
        f["body_types"] = selected
        await query.edit_message_reply_markup(reply_markup=car_body_keyboard(context, selected))
        return CAR_SEARCH_BODY

    async def handle_search_city(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data.replace("car_city_", "")
        f = context.user_data.setdefault("car_search", {})
        f["cities"] = [] if data == "all" else [data]
        await query.edit_message_text(
            "Шаг 3/4: Цена от", reply_markup=car_price_keyboard(context, "car_pmin"), parse_mode="HTML"
        )
        return CAR_SEARCH_PRICE_MIN

    async def handle_search_price_min(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("car_pmin_", ""))
        f = context.user_data.setdefault("car_search", {})
        if val > 0:
            f["price_min"] = val
        await query.edit_message_text(
            "Цена до", reply_markup=car_price_keyboard(context, "car_pmax"), parse_mode="HTML"
        )
        return CAR_SEARCH_PRICE_MAX

    async def handle_search_price_max(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("car_pmax_", ""))
        f = context.user_data.setdefault("car_search", {})
        if 0 < val < 999999999:
            f["price_max"] = val
        await query.edit_message_text(
            "Шаг 4/4: Год выпуска — от какого года", reply_markup=car_year_keyboard(context, "car_year"), parse_mode="HTML"
        )
        return CAR_SEARCH_YEAR

    async def handle_search_year(self, update, context):
        query = update.callback_query
        await query.answer()
        val = int(query.data.replace("car_year_", ""))
        f = context.user_data.setdefault("car_search", {})
        if val > 0:
            f["year_min"] = val
        await self._show_results(update, context)
        return ConversationHandler.END

    async def _show_results(self, update, context):
        f = context.user_data.get("car_search", {})
        results = db.search_vehicles(f) if hasattr(db, "search_vehicles") else []
        chat_id = update.effective_chat.id
        if not results:
            await context.bot.send_message(
                chat_id=chat_id,
                text="😕 По вашим критериям авто не найдено. Попробуйте изменить фильтры.",
                reply_markup=car_menu_keyboard(context), parse_mode="HTML"
            )
            return
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Найдено {len(results)} авто:")
        for v in results[:10]:
            await _send_car_card(context, chat_id, v)
        await context.bot.send_message(
            chat_id=chat_id, text="Что дальше?", reply_markup=car_menu_keyboard(context), parse_mode="HTML"
        )

    # ── Add-listing flow ─────────────────────────────────────────────────

    async def start_add(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["car_add"] = {}
        await query.edit_message_text(
            "➕ <b>Разместить авто</b>\n\nШаг 1/12: Марка", reply_markup=car_make_keyboard(context), parse_mode="HTML"
        )
        return CAR_ADD_MAKE

    async def handle_add_make(self, update, context):
        query = update.callback_query
        await query.answer()
        make = query.data.replace("car_make_", "", 1)
        context.user_data.setdefault("car_add", {})["make"] = make
        await query.edit_message_text(
            f"✅ Марка: {make}\n\nШаг 2/12: Модель (напишите текстом)", parse_mode="HTML"
        )
        return CAR_ADD_MODEL

    async def handle_add_model(self, update, context):
        context.user_data.setdefault("car_add", {})["model"] = update.message.text.strip()[:80]
        await update.message.reply_text("Шаг 3/12: Год выпуска (например 2018)")
        return CAR_ADD_YEAR

    async def handle_add_year(self, update, context):
        txt = update.message.text.strip()
        if not re.fullmatch(r"(19|20)\d{2}", txt):
            await update.message.reply_text("Введите год цифрами, например 2018")
            return CAR_ADD_YEAR
        context.user_data["car_add"]["year"] = int(txt)
        await update.message.reply_text("Шаг 4/12: Пробег в км (например 85000)")
        return CAR_ADD_MILEAGE

    async def handle_add_mileage(self, update, context):
        txt = update.message.text.strip().replace(" ", "").replace(",", "")
        if not txt.isdigit():
            await update.message.reply_text("Введите пробег числом, например 85000")
            return CAR_ADD_MILEAGE
        context.user_data["car_add"]["mileage_km"] = int(txt)
        await update.message.reply_text(
            "Шаг 5/12: Коробка передач", reply_markup=car_transmission_keyboard(context), parse_mode="HTML"
        )
        return CAR_ADD_TRANSMISSION

    async def handle_add_transmission(self, update, context):
        query = update.callback_query
        await query.answer()
        val = query.data.replace("car_trans_", "")
        context.user_data["car_add"]["transmission"] = val
        await query.edit_message_text(
            "Шаг 6/12: Тип топлива", reply_markup=car_fuel_keyboard(context), parse_mode="HTML"
        )
        return CAR_ADD_FUEL

    async def handle_add_fuel(self, update, context):
        query = update.callback_query
        await query.answer()
        val = query.data.replace("car_fuel_", "")
        context.user_data["car_add"]["fuel_type"] = val
        await query.edit_message_text(
            "Шаг 7/12: Какая по счёту рука (владелец)", reply_markup=car_hand_keyboard(context), parse_mode="HTML"
        )
        return CAR_ADD_HAND

    async def handle_add_hand(self, update, context):
        query = update.callback_query
        await query.answer()
        val = query.data.replace("car_hand_", "")
        context.user_data["car_add"]["hand"] = val
        await query.edit_message_text(
            "Шаг 8/12: Тип кузова", reply_markup=car_body_single_keyboard(context), parse_mode="HTML"
        )
        return CAR_ADD_BODY

    async def handle_add_body(self, update, context):
        query = update.callback_query
        await query.answer()
        val = query.data.replace("car_addbody_", "")
        context.user_data["car_add"]["body_type"] = val
        await query.edit_message_text("Шаг 9/13: Цена в ₪ (например 65000)", parse_mode="HTML")
        return CAR_ADD_PRICE

    async def handle_add_price(self, update, context):
        txt = update.message.text.strip().replace(" ", "").replace(",", "").replace("₪", "")
        if not txt.isdigit():
            await update.message.reply_text("Введите цену числом, например 65000")
            return CAR_ADD_PRICE
        context.user_data["car_add"]["price"] = int(txt)
        await update.message.reply_text(
            "Шаг 10/13: Город", reply_markup=car_city_keyboard(context, "car_addcity"), parse_mode="HTML"
        )
        return CAR_ADD_CITY

    async def handle_add_city(self, update, context):
        query = update.callback_query
        await query.answer()
        val = query.data.replace("car_addcity_", "")
        context.user_data["car_add"]["city"] = "" if val == "all" else val
        await query.edit_message_text(
            "Шаг 11/13: Описание (состояние, комплектация и т.д.) — или нажмите «Пропустить»",
            reply_markup=car_skip_keyboard(context, "car_desc_skip"), parse_mode="HTML"
        )
        return CAR_ADD_DESCRIPTION

    async def handle_add_description(self, update, context):
        context.user_data["car_add"]["description"] = update.message.text.strip()[:1000]
        await update.message.reply_text("Шаг 12/13: Контакт (телефон или @username)")
        return CAR_ADD_CONTACT

    async def handle_add_description_skip(self, update, context):
        query = update.callback_query
        await query.answer()
        context.user_data["car_add"]["description"] = ""
        await query.edit_message_text("Шаг 12/13: Контакт (телефон или @username)", parse_mode="HTML")
        return CAR_ADD_CONTACT

    async def handle_add_contact(self, update, context):
        context.user_data["car_add"]["contact"] = update.message.text.strip()[:120]
        context.user_data["car_add"]["photos"] = []
        await update.message.reply_text(
            "Шаг 13/13: 📸 Отправьте фото авто (до 10 штук).\nКогда закончите — нажмите кнопку ниже.",
            reply_markup=car_photos_keyboard(context, 0), parse_mode="HTML"
        )
        return CAR_ADD_PHOTOS

    async def handle_add_photo_message(self, update, context):
        photos = context.user_data.setdefault("car_add", {}).setdefault("photos", [])
        if len(photos) < 10 and update.message.photo:
            file_id = update.message.photo[-1].file_id
            photos.append(file_id)
        await update.message.reply_text(
            f"📸 Получено {len(photos)} фото. Отправьте ещё или нажмите «Готово».",
            reply_markup=car_photos_keyboard(context, len(photos)), parse_mode="HTML"
        )
        return CAR_ADD_PHOTOS

    async def handle_add_photos_done(self, update, context):
        query = update.callback_query
        await query.answer()
        data = context.user_data.get("car_add", {})
        preview = _car_card_text({**data, "id": 0, "active": True, "views": 0})
        photos = data.get("photos") or []
        if photos:
            await query.message.reply_photo(
                photo=photos[0], caption="Проверьте объявление:\n\n" + preview,
                reply_markup=car_confirm_keyboard(context), parse_mode="HTML"
            )
        else:
            await query.message.reply_text(
                "Проверьте объявление:\n\n" + preview, reply_markup=car_confirm_keyboard(context), parse_mode="HTML"
            )
        return CAR_ADD_CONFIRM

    async def handle_publish(self, update, context):
        query = update.callback_query
        await query.answer()
        data = dict(context.user_data.get("car_add", {}))
        user = update.effective_user
        data["user_id"] = user.id
        data["poster_username"] = user.username or ""
        data["poster_name"] = user.first_name or ""
        data["source"] = "user"
        vid = db.add_vehicle(data)
        context.user_data.pop("car_add", None)
        chat_id = update.effective_chat.id
        try:
            await query.edit_message_caption(caption=f"✅ Авто размещено! (№{vid})\n\nОно уже видно в поиске.", parse_mode="HTML")
        except Exception:
            await query.edit_message_text(f"✅ Авто размещено! (№{vid})\n\nОно уже видно в поиске.", parse_mode="HTML")
        await context.bot.send_message(
            chat_id=chat_id, text="Что дальше?",
            reply_markup=car_menu_keyboard(context), parse_mode="HTML"
        )
        return ConversationHandler.END

    # ── Shared back / cancel ─────────────────────────────────────────────

    async def handle_back(self, update, context):
        # Simple: bounce back to the car menu — precise per-step back is a
        # nice-to-have, not required for a working MVP.
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🚗 <b>CarsFinderIL</b>\n\nЧто хотите сделать?",
            reply_markup=car_menu_keyboard(context), parse_mode="HTML"
        )
        return ConversationHandler.END

    async def cancel(self, update, context):
        text = format_welcome(update.effective_user.first_name, context)
        kb = main_menu_keyboard(context)
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
        context.user_data.pop("car_add", None)
        context.user_data.pop("car_search", None)
        return ConversationHandler.END

    # ── Registration ─────────────────────────────────────────────────────

    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start_search, pattern="^car_search_start$"),
                CallbackQueryHandler(self.start_add, pattern="^car_add_start$"),
            ],
            states={
                CAR_SEARCH_BODY: [
                    CallbackQueryHandler(self.handle_search_body, pattern="^car_body_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_SEARCH_CITY: [
                    CallbackQueryHandler(self.handle_search_city, pattern="^car_city_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_SEARCH_PRICE_MIN: [
                    CallbackQueryHandler(self.handle_search_price_min, pattern="^car_pmin_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_SEARCH_PRICE_MAX: [
                    CallbackQueryHandler(self.handle_search_price_max, pattern="^car_pmax_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_SEARCH_YEAR: [
                    CallbackQueryHandler(self.handle_search_year, pattern="^car_year_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_MAKE: [
                    CallbackQueryHandler(self.handle_add_make, pattern="^car_make_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_model)],
                CAR_ADD_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_year)],
                CAR_ADD_MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_mileage)],
                CAR_ADD_TRANSMISSION: [
                    CallbackQueryHandler(self.handle_add_transmission, pattern="^car_trans_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_FUEL: [
                    CallbackQueryHandler(self.handle_add_fuel, pattern="^car_fuel_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_HAND: [
                    CallbackQueryHandler(self.handle_add_hand, pattern="^car_hand_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_BODY: [
                    CallbackQueryHandler(self.handle_add_body, pattern="^car_addbody_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_price)],
                CAR_ADD_CITY: [
                    CallbackQueryHandler(self.handle_add_city, pattern="^car_addcity_"),
                    CallbackQueryHandler(self.handle_back, pattern="^car_back$"),
                ],
                CAR_ADD_DESCRIPTION: [
                    CallbackQueryHandler(self.handle_add_description_skip, pattern="^car_desc_skip$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_description),
                ],
                CAR_ADD_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_contact)],
                CAR_ADD_PHOTOS: [
                    MessageHandler(filters.PHOTO, self.handle_add_photo_message),
                    CallbackQueryHandler(self.handle_add_photos_done, pattern="^car_photos_done$"),
                ],
                CAR_ADD_CONFIRM: [
                    CallbackQueryHandler(self.handle_publish, pattern="^car_publish$"),
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
