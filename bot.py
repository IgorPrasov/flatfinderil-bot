import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)
from config import BOT_TOKEN
from handlers import start, handle_menu, my_listings, handle_unknown
from search_handler import SearchHandler
from listing_handler import ListingHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    search = SearchHandler()
    listing = ListingHandler()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search.start_search))
    app.add_handler(CommandHandler("listings", my_listings))
    app.add_handler(CommandHandler("add", listing.start_add))
    app.add_handler(CommandHandler("help", handle_unknown))
    app.add_handler(search.get_conversation_handler())
    app.add_handler(listing.get_conversation_handler())
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))
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
