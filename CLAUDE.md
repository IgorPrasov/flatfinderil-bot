# CLAUDE.md — flatfinderil-bot

## Project Overview

A Telegram bot for searching and listing real estate properties in Israel. Supports rental and purchase searches with multi-step filtering, user-submitted listings, favorites, multilingual UI (Russian, English, Hebrew), subscription management, and an analytics dashboard.

## Architecture

- **Language**: Python 3.11.6
- **Bot framework**: `python-telegram-bot==20.7` with `ConversationHandler` for multi-step flows
- **Database**: JSON file (`listings_db.json`) — no external DB
- **Analytics**: JSON file (`stats.json`) + HTTP server on port 8080
- **Dashboard**: Static HTML (`dashboard.html`) served on port 3000
- **Deployment**: Railway (cloud)

## Key Files

| File | Purpose |
|------|---------|
| `bot.py` | Entry point — initializes bot, launches background servers |
| `search_handler.py` | 10-step property search conversation flow |
| `listing_handler.py` | 12-step add-listing conversation flow |
| `handlers.py` | Main menu, favorites, navigation |
| `database.py` | JSON persistence layer (listings, favorites, user_listings) |
| `keyboards.py` | Inline keyboard builders |
| `formatters.py` | Message text formatting |
| `config.py` | Constants: property types, districts, cities, price ranges |
| `i18n.py` | Translations for Russian, English, Hebrew |
| `city_translations.py` | City name translations |
| `analytics.py` | Usage tracking (users, searches, subscriptions) |
| `analytics_server.py` | HTTP server exposing `GET /analytics` endpoint |
| `analytics_api.py` | Analytics API helpers |
| `serve_dashboard.py` | Serves `dashboard.html` |
| `subscription.py` | Subscription tiers and trial logic |
| `yad2_parser.py` | Scraper for Yad2.co.il listings |
| `telegram_parser.py` | Parser for Telegram channels |
| `facebook_parser.py` | Parser for Facebook groups |

## Running Locally

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_telegram_bot_token"
python bot.py
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `BOT_TOKEN` | Telegram bot token | Hardcoded fallback (insecure — set explicitly) |
| `ANALYTICS_PORT` | Analytics API server port | 8080 |
| `PORT` | Dashboard server port | 3000 |

Note: `API_ID` and `API_HASH` for Telegram parsers are currently hardcoded in `telegram_parser.py` — move to env vars if enabling parsers.

## Bot Commands

- `/start` — Main menu
- `/search` — Begin property search
- `/add` — Add a new listing
- `/listings` — View your own listings
- `/help` — Help message

## Conversation Flows

**Search** (10 steps): Deal type → Property type → District → City → Rooms min/max → Price min/max → Parking → Pool → Infrastructure → Results

**Add Listing** (multi-step): Deal type → Property type → District → City → Neighborhood → Rooms → Floor → Area → Price → Parking → Pool → Shelter → Elevator → Infrastructure → Description → Owner name → Phone → Contact → Confirmation → Publish

## Data Model (`listings_db.json`)

```json
{
  "listings": {
    "<id>": {
      "id", "title", "property_type", "city", "district", "neighborhood",
      "rooms", "floor", "area_sqm", "price", "deal_type",
      "parking", "pool", "infrastructure", "description",
      "contact", "photos", "date_added", "active"
    }
  },
  "favorites": { "<user_id>": ["<listing_id>"] },
  "user_listings": { "<user_id>": ["<listing_id>"] },
  "next_id": 11
}
```

## Multilingual Support

All UI strings go through `i18n.py`. Use the `t(key, lang)` helper. Supported languages: `ru`, `en`, `he` (Hebrew with RTL). Language is stored per-user in conversation context.

## Subscription System (`subscription.py`)

- Trial period: free until **April 15, 2026**
- Paid plans: 19.90₪ / week, 29.90₪ / 2 weeks, 39.90₪ / month
- Subscriptions are in-memory only (not persisted across restarts)

## Analytics

- Tracks: user sessions, search queries with all filter params, subscription activations, daily stats
- Data written to `stats.json`
- API: `GET http://localhost:8080/analytics` → JSON
- Dashboard: `http://localhost:3000` — Chart.js visualizations

## Notes

- JSON database has no concurrency control — avoid concurrent writes
- No test suite exists currently
- Parsers (`yad2_parser.py`, `telegram_parser.py`, `facebook_parser.py`) are standalone scripts, not integrated into the live bot flow
