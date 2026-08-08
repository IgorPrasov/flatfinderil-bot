"""
notification-worker — background task service.

Responsibilities:
- Subscription match alerts (every 30 min, or instantly on new_listing NOTIFY)
- Price-drop notifications (every 60 min)
- Stale listing reminders (every 24 hr)
- Weekly email reports (Sunday 10:00 Israel time)
- HTTP endpoint: POST /trigger/weekly-report (called by backoffice on demand)

Sends Telegram messages via bot-gateway POST /send-message (no Telegram credentials needed).
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_URL = os.environ["DATA_SERVICE_URL"].rstrip("/")
BOT_GATEWAY_URL = os.environ["BOT_GATEWAY_URL"].rstrip("/")
DB_URL = os.environ["DATABASE_URL"]
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

app = FastAPI(title="notification-worker", version="1.0.0")


# ---------------------------------------------------------------------------
# Telegram helpers — routed through bot-gateway
# ---------------------------------------------------------------------------

async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> None:
    """Send a Telegram message via the bot-gateway /send-message endpoint."""
    headers = {}
    if INTERNAL_API_KEY:
        headers["X-Internal-Key"] = INTERNAL_API_KEY
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{BOT_GATEWAY_URL}/send-message",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            headers=headers,
        )
        if r.status_code != 200:
            log.warning("send-message returned %s: %s", r.status_code, r.text)


# ---------------------------------------------------------------------------
# Data-service helpers
# ---------------------------------------------------------------------------

async def ds_get(path: str, params: dict | None = None) -> list | dict:
    async with httpx.AsyncClient(timeout=15, base_url=DATA_URL) as client:
        r = await client.get(path, params=params)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Subscription checker — matches active saved searches against new listings
# ---------------------------------------------------------------------------

def _listing_matches(listing: dict, filters: dict) -> bool:
    if filters.get("deal_type") and listing.get("deal_type") != filters["deal_type"]:
        return False
    if filters.get("property_type") and listing.get("property_type") != filters["property_type"]:
        return False
    if filters.get("city") and listing.get("city") != filters["city"]:
        return False
    if filters.get("district") and listing.get("district") != filters["district"]:
        return False
    if filters.get("price_max") and listing.get("price", 0) > filters["price_max"]:
        return False
    if filters.get("price_min") and listing.get("price", 0) < filters["price_min"]:
        return False
    return True


async def check_subscriptions_for_listing(listing_id: int) -> None:
    """Check a single new listing against all active subscriptions."""
    try:
        listing = await ds_get(f"/listings/{listing_id}")
        if not listing or not listing.get("active"):
            return
        subs = await ds_get("/subscriptions", {"active": "true"})
        for sub in subs:
            if listing_id in (sub.get("last_result_ids") or []):
                continue
            if _listing_matches(listing, sub.get("filters") or {}):
                user_id = sub["user_id"]
                text = (
                    f"<b>New listing matching your search!</b>\n\n"
                    f"{listing.get('title', 'No title')}\n"
                    f"{listing.get('city', '')} · {listing.get('rooms', '')} rooms · "
                    f"₪{listing.get('price', 0):,}"
                )
                await send_message(user_id, text)
                log.info("Alerted user %s for listing %s", user_id, listing_id)
    except Exception as e:
        log.error("check_subscriptions_for_listing(%s): %s", listing_id, e)


async def subscription_check_loop() -> None:
    """Poll all subscriptions every 30 minutes as a fallback."""
    while True:
        await asyncio.sleep(30 * 60)
        try:
            log.info("Running subscription poll loop")
            subs = await ds_get("/subscriptions", {"active": "true"})
            all_listings = await ds_get("/listings", {"active": "true", "limit": 500})
            for sub in subs:
                matched_ids = []
                for listing in all_listings:
                    if _listing_matches(listing, sub.get("filters") or {}):
                        matched_ids.append(listing["id"])
                new_ids = [i for i in matched_ids if i not in (sub.get("last_result_ids") or [])]
                if new_ids:
                    user_id = sub["user_id"]
                    text = f"<b>{len(new_ids)} new listing(s) matching your saved search!</b>"
                    await send_message(user_id, text)
        except Exception as e:
            log.error("subscription_check_loop: %s", e)


# ---------------------------------------------------------------------------
# Price-drop checker
# ---------------------------------------------------------------------------

async def price_drop_loop() -> None:
    while True:
        await asyncio.sleep(60 * 60)
        try:
            log.info("Running price-drop check")
            # Get all users with favorites and check for price changes
            async with httpx.AsyncClient(timeout=15, base_url=DATA_URL) as client:
                # Get all listings with recent price changes (last 2 hours)
                listings = await ds_get("/listings", {"active": "true", "limit": 500})
                # TODO: track previous prices in analytics_events and compare
        except Exception as e:
            log.error("price_drop_loop: %s", e)


# ---------------------------------------------------------------------------
# Stale listing reminder (> 30 days inactive)
# ---------------------------------------------------------------------------

async def stale_listing_loop() -> None:
    while True:
        await asyncio.sleep(24 * 60 * 60)
        try:
            log.info("Running stale listing check")
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            listings = await ds_get("/listings", {"active": "true", "limit": 500})
            for listing in listings:
                date_added = listing.get("date_added", "")
                if date_added and date_added < cutoff and listing.get("user_id"):
                    text = (
                        f"Reminder: your listing <b>{listing.get('title', '')}</b> "
                        f"has been active for over 30 days. Is it still available?"
                    )
                    await send_message(listing["user_id"], text)
        except Exception as e:
            log.error("stale_listing_loop: %s", e)


# ---------------------------------------------------------------------------
# Weekly email report
# ---------------------------------------------------------------------------

async def send_weekly_reports() -> None:
    """Send weekly reports to all agents with email. Import email_reporter logic here."""
    try:
        log.info("Sending weekly email reports")
        # email_reporter logic will be ported here in full implementation
        # For now: placeholder that calls the email_reporter module
        from email_reporter import send_all_reports
        await asyncio.get_event_loop().run_in_executor(None, send_all_reports)
    except Exception as e:
        log.error("send_weekly_reports: %s", e)


async def weekly_report_scheduler() -> None:
    """Fire every Sunday at 10:00 Israel time (UTC+3)."""
    while True:
        now = datetime.now(timezone.utc)
        # Next Sunday 07:00 UTC (= 10:00 IST)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 7:
            days_until_sunday = 7
        next_run = now.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
        wait_seconds = (next_run - now).total_seconds()
        log.info("Next weekly report in %.0f seconds", wait_seconds)
        await asyncio.sleep(wait_seconds)
        await send_weekly_reports()


# ---------------------------------------------------------------------------
# PostgreSQL LISTEN for new_listing events
# ---------------------------------------------------------------------------

async def listen_new_listings() -> None:
    """Listen for pg_notify('new_listing', ...) from data-service."""
    while True:
        try:
            conn = await asyncpg.connect(DB_URL)
            log.info("LISTEN new_listing: connected")

            async def on_notify(conn, pid, channel, payload):
                log.info("NOTIFY %s: %s", channel, payload)
                try:
                    listing_id = int(payload)
                    await check_subscriptions_for_listing(listing_id)
                except ValueError:
                    pass

            await conn.add_listener("new_listing", on_notify)
            # Keep the connection alive
            while True:
                await asyncio.sleep(60)
                await conn.execute("SELECT 1")  # keepalive
        except Exception as e:
            log.error("LISTEN connection dropped: %s — reconnecting in 10s", e)
            await asyncio.sleep(10)


# ---------------------------------------------------------------------------
# FastAPI HTTP endpoint for on-demand report trigger
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/trigger/weekly-report")
async def trigger_weekly_report():
    asyncio.create_task(send_weekly_reports())
    return {"ok": True, "message": "Weekly report triggered"}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    asyncio.create_task(listen_new_listings())
    asyncio.create_task(subscription_check_loop())
    asyncio.create_task(price_drop_loop())
    asyncio.create_task(stale_listing_loop())
    asyncio.create_task(weekly_report_scheduler())
    log.info("notification-worker started")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), log_level="info")
