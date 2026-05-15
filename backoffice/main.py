"""
backoffice — admin panel service.

Serves backoffice.html + dashboard.html as static files.
All data calls go through data-service (DATA_SERVICE_URL).
Admin sessions stored in data-service (backoffice_sessions table).
Triggers email reports via notification-worker (NOTIFICATION_WORKER_URL).
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

BACKOFFICE_PASSWORD = os.environ["BACKOFFICE_PASSWORD"]
DATA_URL = os.environ["DATA_SERVICE_URL"].rstrip("/")
NOTIFICATION_URL = os.environ.get("NOTIFICATION_WORKER_URL", "").rstrip("/")

SESSION_TTL_HOURS = 24

app = FastAPI(title="backoffice", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def ds(method: str, path: str, **kwargs) -> dict | list:
    async with httpx.AsyncClient(timeout=15, base_url=DATA_URL) as client:
        r = await getattr(client, method)(path, **kwargs)
        r.raise_for_status()
        return r.json()


async def check_auth(request: Request) -> bool:
    token = request.cookies.get("bo_session")
    if not token:
        return False
    result = await ds("get", f"/backoffice-sessions/{token}")
    return result.get("valid", False)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/backoffice", response_class=HTMLResponse)
async def backoffice_page(request: Request):
    if not await check_auth(request):
        return RedirectResponse("/backoffice/login")
    with open("static/backoffice.html") as f:
        return HTMLResponse(f.read())


@app.get("/backoffice/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse("""
    <html><body style="font-family:sans-serif;max-width:400px;margin:100px auto">
    <h2>Backoffice Login</h2>
    <form method="post" action="/backoffice/api/login">
      <input name="password" type="password" placeholder="Password" style="width:100%;padding:8px;margin:8px 0">
      <button type="submit" style="width:100%;padding:8px;background:#2563eb;color:white;border:none;cursor:pointer">Login</button>
    </form></body></html>
    """)


@app.post("/backoffice/api/login")
async def login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    if password != BACKOFFICE_PASSWORD:
        raise HTTPException(401, "Invalid password")
    token = secrets.token_hex(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
    await ds("post", "/backoffice-sessions", json={"token": token, "expires_at": expires_at})
    response = RedirectResponse("/backoffice", status_code=303)
    response.set_cookie("bo_session", token, httponly=True, max_age=SESSION_TTL_HOURS * 3600)
    return response


@app.post("/backoffice/api/logout")
async def logout(request: Request):
    token = request.cookies.get("bo_session")
    if token:
        await ds("delete", f"/backoffice-sessions/{token}")
    response = RedirectResponse("/backoffice/login", status_code=303)
    response.delete_cookie("bo_session")
    return response


# ---------------------------------------------------------------------------
# Analytics dashboard
# ---------------------------------------------------------------------------

@app.get("/analytics", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not await check_auth(request):
        return RedirectResponse("/backoffice/login")
    with open("static/dashboard.html") as f:
        return HTMLResponse(f.read())


@app.get("/analytics/api/summary")
async def analytics_summary(request: Request, from_date: str | None = None, to_date: str | None = None):
    if not await check_auth(request):
        raise HTTPException(401)
    params = {}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    return await ds("get", "/analytics/summary", params=params)


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------

@app.get("/backoffice/api/stats")
async def stats(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    summary = await ds("get", "/analytics/summary")
    listings = await ds("get", "/listings", params={"limit": 1000})
    return {
        "total_listings": len(listings),
        "active_listings": sum(1 for l in listings if l.get("active")),
        **summary,
    }


@app.get("/backoffice/api/listings")
async def list_listings(request: Request, active: str | None = None, limit: int = 100, offset: int = 0):
    if not await check_auth(request):
        raise HTTPException(401)
    params = {"limit": limit, "offset": offset}
    if active is not None:
        params["active"] = active
    return await ds("get", "/listings", params=params)


@app.get("/backoffice/api/listings/{listing_id}")
async def get_listing(request: Request, listing_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    return await ds("get", f"/listings/{listing_id}")


@app.patch("/backoffice/api/listings/{listing_id}/toggle")
async def toggle_listing(request: Request, listing_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    listing = await ds("get", f"/listings/{listing_id}")
    new_state = not listing.get("active", True)
    await ds("patch", f"/listings/{listing_id}", json={"active": new_state})
    return {"active": new_state}


@app.delete("/backoffice/api/listings/{listing_id}", status_code=204)
async def delete_listing(request: Request, listing_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    await ds("delete", f"/listings/{listing_id}")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/backoffice/api/users")
async def list_users(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    return await ds("get", "/agent-profiles")


@app.get("/backoffice/api/users/{user_id}")
async def get_user(request: Request, user_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    profile = await ds("get", f"/agent-profiles/{user_id}")
    listings = await ds("get", "/listings", params={"user_id": user_id, "limit": 100})
    return {"profile": profile, "listings": listings}


# ---------------------------------------------------------------------------
# Services (moving, packing, cleaning)
# ---------------------------------------------------------------------------

@app.get("/backoffice/api/services")
async def list_services(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    return await ds("get", "/service-providers", params={"active": "true"})


@app.patch("/backoffice/api/services/{provider_id}")
async def update_service(request: Request, provider_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    body = await request.json()
    await ds("patch", f"/service-providers/{provider_id}", json=body)
    return {"ok": True}


@app.delete("/backoffice/api/services/{provider_id}", status_code=204)
async def delete_service(request: Request, provider_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    await ds("delete", f"/service-providers/{provider_id}")


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

@app.get("/backoffice/api/crm/contacts")
async def crm_contacts(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    return await ds("get", "/crm/contacts")


@app.post("/backoffice/api/crm/contacts")
async def create_crm_contact(request: Request, user_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    body = await request.json()
    return await ds("post", "/crm/contacts", params={"user_id": user_id}, json=body)


@app.patch("/backoffice/api/crm/contacts/{contact_id}")
async def update_crm_contact(request: Request, contact_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    body = await request.json()
    await ds("patch", f"/crm/contacts/{contact_id}", json=body)
    return {"ok": True}


@app.delete("/backoffice/api/crm/contacts/{contact_id}", status_code=204)
async def delete_crm_contact(request: Request, contact_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    await ds("delete", f"/crm/contacts/{contact_id}")


@app.get("/backoffice/api/crm/deals")
async def crm_deals(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    return await ds("get", "/crm/deals")


@app.post("/backoffice/api/crm/deals")
async def create_crm_deal(request: Request, user_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    body = await request.json()
    return await ds("post", "/crm/deals", params={"user_id": user_id}, json=body)


@app.patch("/backoffice/api/crm/deals/{deal_id}")
async def update_crm_deal(request: Request, deal_id: int):
    if not await check_auth(request):
        raise HTTPException(401)
    body = await request.json()
    await ds("patch", f"/crm/deals/{deal_id}", json=body)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Email subscribers
# ---------------------------------------------------------------------------

@app.get("/backoffice/api/email-subscribers")
async def email_subscribers(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    return await ds("get", "/agent-profiles", params={"has_email": "true"})


@app.post("/backoffice/api/email-subscribers/send-now")
async def send_reports_now(request: Request):
    if not await check_auth(request):
        raise HTTPException(401)
    if not NOTIFICATION_URL:
        raise HTTPException(503, "NOTIFICATION_WORKER_URL not configured")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{NOTIFICATION_URL}/trigger/weekly-report")
        r.raise_for_status()
    return {"ok": True}


# ---------------------------------------------------------------------------
# DB Export / Import  (bulk sync with local parser output)
# ---------------------------------------------------------------------------

@app.get("/backoffice/api/db-export")
async def db_export(request: Request):
    """Download all listings as JSON for local sync."""
    if not await check_auth(request):
        raise HTTPException(401)
    all_listings = []
    offset = 0
    batch = 500
    async with httpx.AsyncClient(timeout=30, base_url=DATA_URL) as client:
        while True:
            r = await client.get("/listings", params={"limit": batch, "offset": offset, "active": "true"})
            r.raise_for_status()
            page = r.json()
            all_listings.extend(page)
            if len(page) < batch:
                break
            offset += batch
    import json
    from fastapi.responses import Response as FastResponse
    body = json.dumps({"listings": all_listings, "total": len(all_listings)}, ensure_ascii=False, default=str)
    return FastResponse(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="prod_listings.json"'},
    )


@app.post("/backoffice/api/db-import")
async def db_import(request: Request):
    """Import listings from local parser output, deduplicated by description fingerprint."""
    if not await check_auth(request):
        raise HTTPException(401)

    payload = await request.json()
    incoming = payload.get("listings", [])
    if isinstance(incoming, dict):
        incoming = list(incoming.values())

    # Fetch existing descriptions to deduplicate
    existing = []
    offset = 0
    batch = 500
    async with httpx.AsyncClient(timeout=60, base_url=DATA_URL) as client:
        while True:
            r = await client.get("/listings", params={"limit": batch, "offset": offset, "active": "true"})
            r.raise_for_status()
            page = r.json()
            existing.extend(page)
            if len(page) < batch:
                break
            offset += batch

    # Build fingerprint set: first 150 chars of description
    existing_fps = set()
    for l in existing:
        desc = (l.get("description") or "")[:150].strip()
        if desc:
            existing_fps.add(desc)

    added = 0
    skipped = 0
    errors = 0
    async with httpx.AsyncClient(timeout=60, base_url=DATA_URL) as client:
        for listing in incoming:
            desc = (listing.get("description") or "")[:150].strip()
            if desc and desc in existing_fps:
                skipped += 1
                continue

            # Map local format → data-service ListingCreate
            body = {
                "title":         listing.get("title"),
                "property_type": listing.get("property_type"),
                "deal_type":     listing.get("deal_type"),
                "city":          listing.get("city"),
                "district":      listing.get("district"),
                "neighborhood":  listing.get("neighborhood"),
                "rooms":         str(listing.get("rooms", "")) if listing.get("rooms") else None,
                "floor":         str(listing.get("floor", "")) if listing.get("floor") else None,
                "area_sqm":      listing.get("area_sqm") or None,
                "price":         listing.get("price") or None,
                "parking":       int(listing.get("parking", 0) or 0),
                "pool":          bool(listing.get("pool", False)),
                "infrastructure": listing.get("infrastructure", []),
                "description":   listing.get("description"),
                "photos":        [p for p in (listing.get("photos") or []) if isinstance(p, str) and p.startswith("http")],
                "active":        listing.get("active", True),
                "contact":       listing.get("contact"),
                "source":        listing.get("source", "parser"),
                "seller_type":   listing.get("seller_type"),
            }
            try:
                r = await client.post("/listings", json=body)
                r.raise_for_status()
                added += 1
                if desc:
                    existing_fps.add(desc)
            except Exception:
                errors += 1

    return {"ok": True, "added": added, "skipped": skipped, "errors": errors,
            "existing_total": len(existing)}
