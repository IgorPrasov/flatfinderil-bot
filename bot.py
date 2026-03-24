import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)
from config import BOT_TOKEN
from handlers import start, handle_menu, my_listings, handle_unknown, agent_cabinet, refer_command, handle_edit_text
from search_handler import SearchHandler
from listing_handler import ListingHandler
from commercial_handler import CommercialHandler
from service_handler import ServiceHandler
from crm_handler import CRMHandler
from upload_handler import process_upload, get_csv_template_bytes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_city_migration():
    """Migration: re-detect city+district for ALL listings using description text."""
    try:
        import json
        from telegram_parser import detect_city, DISTRICT_MAP
        db_path = os.path.join(os.path.dirname(__file__), "listings_db.json")
        with open(db_path) as f:
            db = json.load(f)
        fixed = 0
        for listing in db.get("listings", {}).values():
            # Skip manually added listings (they have correct data)
            if listing.get("source") == "manual":
                continue
            city = listing.get("city", "")
            desc = listing.get("description", "") or listing.get("title", "")
            if desc:
                detected = detect_city(desc)
                if detected and detected != city:
                    listing["city"] = detected
                    city = detected
                    fixed += 1
            # Fix district to match city
            correct_district = DISTRICT_MAP.get(city)
            if correct_district and listing.get("district") != correct_district:
                listing["district"] = correct_district
                fixed += 1
        if fixed:
            with open(db_path, "w") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            logger.info(f"City/district migration: fixed {fixed} fields")
    except Exception as e:
        logger.warning(f"City migration failed: {e}")


async def handle_upload_command(update, context):
    """Send CSV template when user types /upload."""
    from telegram import InputFile
    import io
    tpl = get_csv_template_bytes()
    caption = (
        "📤 <b>Массовая загрузка объявлений</b>\n\n"
        "Скачайте шаблон, заполните и пришлите обратно боту.\n\n"
        "<b>Обязательные колонки:</b>\n"
        "• <code>deal_type</code> — rent / buy / sublet / commercial\n"
        "• <code>property_type</code> — apartment / house / villa / studio / duplex / penthouse / office / retail / warehouse / land\n"
        "• <code>city</code> — название города (например: Тель-Авив)\n"
        "• <code>price</code> — цена в ₪\n\n"
        "<b>Необязательные:</b> address, neighborhood, rooms, floor, area_sqm, "
        "parking, pool, shelter, elevator, infrastructure, description, contact, owner_name, owner_phone\n\n"
        "Поддерживаются форматы: <b>.csv</b> и <b>.xlsx</b>"
    )
    await update.message.reply_document(
        document=InputFile(io.BytesIO(tpl), filename="listings_template.csv"),
        caption=caption,
        parse_mode="HTML",
    )


async def handle_document_upload(update, context):
    """Handle CSV/XLSX file upload."""
    doc = update.message.document
    if not doc:
        return
    fname = doc.file_name or ""
    if not (fname.lower().endswith(".csv") or fname.lower().endswith(".xlsx") or fname.lower().endswith(".xls")):
        return  # ignore other document types

    user_id = update.effective_user.id
    wait_msg = await update.message.reply_text("⏳ Обрабатываю файл...")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        raw = bytes(await tg_file.download_as_bytearray())
    except Exception as e:
        await wait_msg.edit_text(f"❌ Не удалось скачать файл: {e}")
        return

    result = process_upload(raw, fname, user_id)

    ok = result["ok"]
    errors = result["errors"]
    total = result["total"]

    lines = [f"📊 <b>Результат загрузки</b>", ""]
    lines.append(f"✅ Добавлено: <b>{ok}</b> из {total}")

    if errors:
        lines.append(f"⚠️ Ошибок: <b>{len(errors)}</b>")
        for e in errors[:10]:
            lines.append(f"• {e}")
        if len(errors) > 10:
            lines.append(f"• ...и ещё {len(errors) - 10}")

    if ok > 0:
        lines.append("")
        lines.append("Объявления доступны через поиск 🔍")

    await wait_msg.edit_text("\n".join(lines), parse_mode="HTML")


def main():
    fix_city_migration()
    app = Application.builder().token(BOT_TOKEN).build()
    search = SearchHandler()
    listing = ListingHandler()
    commercial = CommercialHandler()
    services = ServiceHandler()
    crm = CRMHandler()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search.start_search))
    app.add_handler(CommandHandler("listings", my_listings))
    app.add_handler(CommandHandler("add", listing.start_add))
    app.add_handler(CommandHandler("help", handle_unknown))
    app.add_handler(CommandHandler("cabinet", agent_cabinet))
    app.add_handler(CommandHandler("refer", refer_command))
    app.add_handler(commercial.get_conversation_handler())
    app.add_handler(services.get_conversation_handler())
    app.add_handler(crm.get_conversation_handler())
    app.add_handler(search.get_conversation_handler())
    app.add_handler(listing.get_conversation_handler())
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.add_handler(CommandHandler("upload", handle_upload_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text))

    # Start background notification tasks
    from notifications import start_background_tasks
    start_background_tasks(app)

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json as json_module

DASHBOARD_FILE = os.path.join(os.path.dirname(__file__), "dashboard.html")

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/analytics":
            try:
                from analytics import get_analytics
                data = get_analytics()
            except Exception as e:
                data = {"error": str(e)}
            body = json_module.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            try:
                with open(DASHBOARD_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
    def log_message(self, *args): pass

def start_web_server():
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    logger.info(f"Web server on port {port}")
    server.serve_forever()

web_thread = threading.Thread(target=start_web_server, daemon=True)
web_thread.start()

def start_telegram_parser():
    try:
        from telegram_parser import run_parser
        asyncio.run(run_parser())
    except Exception as e:
        logger.error(f"Telegram parser error: {e}")

parser_thread = threading.Thread(target=start_telegram_parser, daemon=True)
parser_thread.start()

if __name__ == "__main__":
    main()
