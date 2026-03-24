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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text))

    # Start background notification tasks
    from notifications import start_background_tasks
    start_background_tasks(app)

    # Start weekly email reporter (Sunday 10:00)
    _start_email_scheduler()

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json as json_module

DASHBOARD_FILE = os.path.join(os.path.dirname(__file__), "dashboard.html")

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/analytics":
            try:
                from analytics import get_analytics
                qs = parse_qs(parsed.query)
                date_from = (qs.get("from") or [None])[0]
                date_to   = (qs.get("to")   or [None])[0]
                data = get_analytics(date_from=date_from, date_to=date_to)
            except Exception as e:
                data = {"error": str(e)}
            body = json_module.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            try:
                with open(DASHBOARD_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(content))
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


def _email_scheduler_loop():
    """Background thread: every Sunday at 10:00 IL time send weekly reports."""
    import time
    from datetime import datetime, timezone, timedelta
    IL_TZ = timezone(timedelta(hours=3))  # Israel Standard Time (UTC+3)
    sent_this_week = None
    while True:
        now = datetime.now(IL_TZ)
        week_key = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
        # Sunday=6 in Python weekday(), 10:00–10:59
        if now.weekday() == 6 and now.hour == 10 and sent_this_week != week_key:
            try:
                from email_reporter import send_all_weekly_reports
                ok, total = send_all_weekly_reports()
                logger.info(f"Email scheduler: {ok}/{total} reports sent")
                sent_this_week = week_key
            except Exception as e:
                logger.error(f"Email scheduler error: {e}")
        time.sleep(60)   # check every minute


def _start_email_scheduler():
    t = threading.Thread(target=_email_scheduler_loop, daemon=True, name="email-scheduler")
    t.start()
    logger.info("Email scheduler started (runs every Sunday 10:00 IL)")

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
