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
from http.server import HTTPServer, BaseHTTPRequestHandler
import json as json_module

class AnalyticsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
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
    def log_message(self, *args): pass

def start_analytics_server():
    import os
    port = int(os.environ.get("ANALYTICS_PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), AnalyticsHandler)
    server.serve_forever()

analytics_thread = threading.Thread(target=start_analytics_server, daemon=True)
analytics_thread.start()

if __name__ == "__main__":
    main()
