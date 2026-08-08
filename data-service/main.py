"""
data-service — the only service with direct PostgreSQL access.
All other services (bot-gateway, notification-worker, backoffice) call this API.
"""

from fastapi import FastAPI, HTTPException, Query
from typing import Any
import db
import models

app = FastAPI(title="data-service", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------

@app.get("/listings")
def list_listings(
    deal_type: str | None = None,
    property_type: str | None = None,
    city: str | None = None,
    district: str | None = None,
    rooms_min: str | None = None,
    rooms_max: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    parking: int | None = None,
    pool: bool | None = None,
    shelter: str | None = None,
    elevator: bool | None = None,
    infrastructure: list[str] = Query(default=[]),
    active: bool | None = True,
    user_id: int | None = None,
    source: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    conditions = []
    params: list[Any] = []

    if active is not None:
        conditions.append("active = %s")
        params.append(active)
    if deal_type:
        conditions.append("deal_type = %s")
        params.append(deal_type)
    if property_type:
        conditions.append("property_type = %s")
        params.append(property_type)
    if city:
        conditions.append("city = %s")
        params.append(city)
    if district:
        conditions.append("district = %s")
        params.append(district)
    if price_min is not None:
        conditions.append("price >= %s")
        params.append(price_min)
    if price_max is not None:
        conditions.append("price <= %s")
        params.append(price_max)
    if parking is not None:
        conditions.append("parking >= %s")
        params.append(parking)
    if pool is not None:
        conditions.append("pool = %s")
        params.append(pool)
    if shelter:
        conditions.append("shelter = %s")
        params.append(shelter)
    if elevator is not None:
        conditions.append("elevator = %s")
        params.append(elevator)
    if infrastructure:
        conditions.append("infrastructure @> %s::text[]")
        params.append(infrastructure)
    if user_id is not None:
        conditions.append("user_id = %s")
        params.append(user_id)
    if source:
        conditions.append("source = %s")
        params.append(source)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])
    return db.execute(
        f"SELECT * FROM listings {where} ORDER BY date_added DESC LIMIT %s OFFSET %s",
        params,
    )


@app.get("/listings/{listing_id}")
def get_listing(listing_id: int):
    row = db.execute_one("SELECT * FROM listings WHERE id = %s", (listing_id,))
    if not row:
        raise HTTPException(404, "Listing not found")
    return row


@app.post("/listings", status_code=201)
def create_listing(body: models.ListingCreate):
    row = db.execute_write(
        """
        INSERT INTO listings (title, property_type, deal_type, city, district,
            neighborhood, address, rooms, floor, area_sqm, price, parking, pool,
            shelter, elevator, infrastructure, description, photos, active,
            user_id, seller_type, source, contact, email)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            body.title, body.property_type, body.deal_type, body.city, body.district,
            body.neighborhood, body.address, body.rooms, body.floor, body.area_sqm,
            body.price, body.parking, body.pool, body.shelter, body.elevator,
            body.infrastructure, body.description, body.photos, body.active,
            body.user_id, body.seller_type, body.source, body.contact, body.email,
        ),
    )
    listing_id = row["id"]
    db.notify("new_listing", str(listing_id))
    return {"id": listing_id}


@app.patch("/listings/{listing_id}")
def update_listing(listing_id: int, body: models.ListingUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    params = list(updates.values()) + [listing_id]
    db.execute_write(f"UPDATE listings SET {set_clause} WHERE id = %s", params)
    return {"ok": True}


@app.delete("/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: int):
    db.execute_write("DELETE FROM listings WHERE id = %s", (listing_id,))


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

@app.get("/users/{user_id}/favorites")
def get_favorites(user_id: int):
    rows = db.execute(
        "SELECT listing_id, saved_price FROM favorites WHERE user_id = %s",
        (user_id,),
    )
    return rows


@app.post("/users/{user_id}/favorites/{listing_id}", status_code=201)
def add_favorite(user_id: int, listing_id: int, body: models.FavoriteCreate):
    price = body.saved_price
    if price is None:
        row = db.execute_one("SELECT price FROM listings WHERE id = %s", (listing_id,))
        price = row["price"] if row else None
    db.execute_write(
        "INSERT INTO favorites (user_id, listing_id, saved_price) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
        (user_id, listing_id, price),
    )
    return {"ok": True}


@app.delete("/users/{user_id}/favorites/{listing_id}", status_code=204)
def remove_favorite(user_id: int, listing_id: int):
    db.execute_write(
        "DELETE FROM favorites WHERE user_id = %s AND listing_id = %s",
        (user_id, listing_id),
    )


# ---------------------------------------------------------------------------
# Subscriptions (saved search alerts)
# ---------------------------------------------------------------------------

@app.get("/users/{user_id}/subscriptions")
def get_subscriptions(user_id: int, active: bool | None = None):
    cond = "WHERE user_id = %s"
    params: list[Any] = [user_id]
    if active is not None:
        cond += " AND active = %s"
        params.append(active)
    return db.execute(f"SELECT * FROM subscriptions {cond}", params)


@app.get("/subscriptions")
def list_subscriptions(active: bool | None = True):
    cond = ""
    params: list[Any] = []
    if active is not None:
        cond = "WHERE active = %s"
        params.append(active)
    return db.execute(f"SELECT * FROM subscriptions {cond}", params)


@app.post("/users/{user_id}/subscriptions", status_code=201)
def create_subscription(user_id: int, body: models.SubscriptionCreate):
    row = db.execute_write(
        "INSERT INTO subscriptions (user_id, filters) VALUES (%s, %s) RETURNING id",
        (user_id, db.psycopg2.extras.Json(body.filters)),
    )
    return {"id": row["id"]}


@app.patch("/subscriptions/{sub_id}")
def update_subscription(sub_id: int, body: models.SubscriptionUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    params = list(updates.values()) + [sub_id]
    db.execute_write(f"UPDATE subscriptions SET {set_clause} WHERE id = %s", params)
    return {"ok": True}


@app.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(sub_id: int):
    db.execute_write("DELETE FROM subscriptions WHERE id = %s", (sub_id,))


# ---------------------------------------------------------------------------
# Paid subscriptions
# ---------------------------------------------------------------------------

@app.get("/users/{user_id}/subscription/status")
def get_subscription_status(user_id: int):
    rows = db.execute(
        "SELECT plan_type, expires_at FROM paid_subscriptions WHERE user_id = %s",
        (user_id,),
    )
    return rows


@app.post("/users/{user_id}/subscription/activate")
def activate_subscription(user_id: int, body: models.PaidSubscriptionActivate):
    db.execute_write(
        """
        INSERT INTO paid_subscriptions (user_id, plan_type, expires_at)
        VALUES (%s, %s, NOW() + INTERVAL '1 day' * %s)
        ON CONFLICT (user_id, plan_type) DO UPDATE
          SET expires_at = GREATEST(paid_subscriptions.expires_at, NOW()) + INTERVAL '1 day' * %s
        """,
        (user_id, body.plan_type, body.days, body.days),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

@app.get("/crm/contacts")
def list_crm_contacts(user_id: int | None = None, active: bool | None = True):
    cond = []
    params: list[Any] = []
    if user_id is not None:
        cond.append("user_id = %s")
        params.append(user_id)
    if active is not None:
        cond.append("active = %s")
        params.append(active)
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return db.execute(f"SELECT * FROM crm_contacts {where}", params)


@app.post("/crm/contacts", status_code=201)
def create_crm_contact(user_id: int, body: models.CRMContactCreate):
    row = db.execute_write(
        """
        INSERT INTO crm_contacts (user_id, contact_type, name, phone, telegram, region, city, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        (user_id, body.contact_type, body.name, body.phone, body.telegram,
         body.region, body.city, body.notes),
    )
    return {"id": row["id"]}


@app.patch("/crm/contacts/{contact_id}")
def update_crm_contact(contact_id: int, body: models.CRMContactUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    params = list(updates.values()) + [contact_id]
    db.execute_write(f"UPDATE crm_contacts SET {set_clause} WHERE id = %s", params)
    return {"ok": True}


@app.delete("/crm/contacts/{contact_id}", status_code=204)
def delete_crm_contact(contact_id: int):
    db.execute_write("UPDATE crm_contacts SET active = FALSE WHERE id = %s", (contact_id,))


@app.get("/crm/deals")
def list_crm_deals(user_id: int | None = None, contact_id: int | None = None):
    cond = []
    params: list[Any] = []
    if user_id is not None:
        cond.append("user_id = %s")
        params.append(user_id)
    if contact_id is not None:
        cond.append("contact_id = %s")
        params.append(contact_id)
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return db.execute(f"SELECT * FROM crm_deals {where} ORDER BY created_at DESC", params)


@app.post("/crm/deals", status_code=201)
def create_crm_deal(user_id: int, body: models.CRMDealCreate):
    row = db.execute_write(
        "INSERT INTO crm_deals (user_id, contact_id, description, amount, status) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (user_id, body.contact_id, body.description, body.amount, body.status),
    )
    return {"id": row["id"]}


@app.patch("/crm/deals/{deal_id}")
def update_crm_deal(deal_id: int, body: models.CRMDealUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    db.execute_write(f"UPDATE crm_deals SET {set_clause} WHERE id = %s",
                     list(updates.values()) + [deal_id])
    return {"ok": True}


@app.post("/crm/notes", status_code=201)
def create_crm_note(user_id: int, body: models.CRMNoteCreate):
    row = db.execute_write(
        "INSERT INTO crm_notes (user_id, contact_id, text) VALUES (%s,%s,%s) RETURNING id",
        (user_id, body.contact_id, body.text),
    )
    return {"id": row["id"]}


@app.get("/crm/notes")
def list_crm_notes(contact_id: int | None = None, user_id: int | None = None):
    cond = []
    params: list[Any] = []
    if contact_id is not None:
        cond.append("contact_id = %s")
        params.append(contact_id)
    if user_id is not None:
        cond.append("user_id = %s")
        params.append(user_id)
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return db.execute(f"SELECT * FROM crm_notes {where} ORDER BY created_at", params)


# ---------------------------------------------------------------------------
# Agent profiles
# ---------------------------------------------------------------------------

@app.get("/agent-profiles/{user_id}")
def get_agent_profile(user_id: int):
    row = db.execute_one("SELECT * FROM agent_profiles WHERE user_id = %s", (user_id,))
    return row or {}


@app.post("/agent-profiles/{user_id}")
def upsert_agent_profile(user_id: int, body: models.AgentProfileUpsert):
    db.execute_write(
        """
        INSERT INTO agent_profiles (user_id, owner_name, owner_phone, email, lang)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE
          SET owner_name = COALESCE(EXCLUDED.owner_name, agent_profiles.owner_name),
              owner_phone = COALESCE(EXCLUDED.owner_phone, agent_profiles.owner_phone),
              email = COALESCE(EXCLUDED.email, agent_profiles.email),
              lang = COALESCE(EXCLUDED.lang, agent_profiles.lang)
        """,
        (user_id, body.owner_name, body.owner_phone, body.email, body.lang),
    )
    return {"ok": True}


@app.get("/agent-profiles")
def list_agent_profiles(has_email: bool | None = None):
    if has_email:
        return db.execute("SELECT * FROM agent_profiles WHERE email IS NOT NULL AND email != ''")
    return db.execute("SELECT * FROM agent_profiles")


# ---------------------------------------------------------------------------
# Service providers
# ---------------------------------------------------------------------------

@app.get("/service-providers")
def list_service_providers(service_type: str | None = None, region: str | None = None, active: bool | None = True):
    cond = []
    params: list[Any] = []
    if active is not None:
        cond.append("active = %s")
        params.append(active)
    if service_type:
        cond.append("service_type = %s")
        params.append(service_type)
    if region:
        cond.append("region = %s")
        params.append(region)
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return db.execute(f"SELECT * FROM service_providers {where}", params)


@app.post("/service-providers", status_code=201)
def create_service_provider(body: models.ServiceProviderCreate):
    row = db.execute_write(
        """
        INSERT INTO service_providers (service_type, region, city, description,
            price_description, name, phone, email, user_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        (body.service_type, body.region, body.city, body.description,
         body.price_description, body.name, body.phone, body.email, body.user_id),
    )
    return {"id": row["id"]}


@app.patch("/service-providers/{provider_id}")
def update_service_provider(provider_id: int, body: models.ServiceProviderUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    db.execute_write(f"UPDATE service_providers SET {set_clause} WHERE id = %s",
                     list(updates.values()) + [provider_id])
    return {"ok": True}


@app.delete("/service-providers/{provider_id}", status_code=204)
def delete_service_provider(provider_id: int):
    db.execute_write("UPDATE service_providers SET active = FALSE WHERE id = %s", (provider_id,))


# ---------------------------------------------------------------------------
# Referrals & bonuses
# ---------------------------------------------------------------------------

@app.post("/referrals", status_code=201)
def add_referral(body: models.ReferralCreate):
    db.execute_write(
        "INSERT INTO referrals (referrer_id, new_user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
        (body.referrer_id, body.new_user_id),
    )
    db.execute_write(
        "INSERT INTO referral_bonuses (user_id, bonus_days) VALUES (%s, 7) ON CONFLICT (user_id) DO UPDATE SET bonus_days = referral_bonuses.bonus_days + 7",
        (body.referrer_id,),
    )
    return {"ok": True}


@app.get("/users/{user_id}/bonus-days")
def get_bonus_days(user_id: int):
    row = db.execute_one("SELECT bonus_days FROM referral_bonuses WHERE user_id = %s", (user_id,))
    return {"bonus_days": row["bonus_days"] if row else 0}


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@app.get("/listings/{listing_id}/reviews")
def get_reviews(listing_id: int):
    return db.execute("SELECT * FROM reviews WHERE listing_id = %s ORDER BY date DESC", (listing_id,))


@app.post("/reviews", status_code=201)
def add_review(body: models.ReviewCreate):
    db.execute_write(
        "INSERT INTO reviews (listing_id, user_id, rating, comment) VALUES (%s,%s,%s,%s)",
        (body.listing_id, body.user_id, body.rating, body.comment),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# View requesters
# ---------------------------------------------------------------------------

@app.post("/view-requesters", status_code=201)
def add_view_requester(body: models.ViewRequesterCreate):
    db.execute_write(
        "INSERT INTO view_requesters (listing_id, user_id, username, name) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (body.listing_id, body.user_id, body.username, body.name),
    )
    db.execute_write("UPDATE listings SET view_requests = view_requests + 1 WHERE id = %s", (body.listing_id,))
    return {"ok": True}


@app.get("/listings/{listing_id}/view-requesters")
def get_view_requesters(listing_id: int):
    return db.execute("SELECT * FROM view_requesters WHERE listing_id = %s", (listing_id,))


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.post("/analytics/events", status_code=201)
def track_event(body: models.AnalyticsEvent):
    db.execute_write(
        "INSERT INTO analytics_events (user_id, event_type, payload) VALUES (%s,%s,%s)",
        (body.user_id, body.event_type, db.psycopg2.extras.Json(body.payload)),
    )
    return {"ok": True}


@app.get("/analytics/summary")
def analytics_summary(from_date: str | None = None, to_date: str | None = None):
    cond = ""
    params: list[Any] = []
    if from_date:
        cond += " AND created_at >= %s"
        params.append(from_date)
    if to_date:
        cond += " AND created_at <= %s"
        params.append(to_date)

    total_listings = db.execute_one("SELECT COUNT(*) AS n FROM listings WHERE active = TRUE")
    total_users = db.execute_one(f"SELECT COUNT(DISTINCT user_id) AS n FROM analytics_events WHERE event_type = 'user_seen' {cond}", params)
    total_searches = db.execute_one(f"SELECT COUNT(*) AS n FROM analytics_events WHERE event_type = 'search' {cond}", params)
    daily = db.execute(
        f"SELECT DATE(created_at) AS date, COUNT(DISTINCT user_id) AS active_users FROM analytics_events WHERE 1=1 {cond} GROUP BY DATE(created_at) ORDER BY date",
        params,
    )
    return {
        "total_active_listings": total_listings["n"] if total_listings else 0,
        "total_users": total_users["n"] if total_users else 0,
        "total_searches": total_searches["n"] if total_searches else 0,
        "daily": daily,
    }


# ---------------------------------------------------------------------------
# Backoffice sessions
# ---------------------------------------------------------------------------

@app.post("/backoffice-sessions", status_code=201)
def create_session(body: models.BackofficeSession):
    db.execute_write(
        "INSERT INTO backoffice_sessions (token, expires_at) VALUES (%s,%s) ON CONFLICT (token) DO UPDATE SET expires_at = EXCLUDED.expires_at",
        (body.token, body.expires_at),
    )
    return {"ok": True}


@app.get("/backoffice-sessions/{token}")
def check_session(token: str):
    row = db.execute_one(
        "SELECT token FROM backoffice_sessions WHERE token = %s AND expires_at > NOW()",
        (token,),
    )
    return {"valid": row is not None}


@app.delete("/backoffice-sessions/{token}", status_code=204)
def delete_session(token: str):
    db.execute_write("DELETE FROM backoffice_sessions WHERE token = %s", (token,))
