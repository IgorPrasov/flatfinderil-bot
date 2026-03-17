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

if __name__ == "__main__":
    main()
