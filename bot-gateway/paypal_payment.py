"""
PayPal payment integration for FlatFinderIL.

Flow:
  1. Bot creates a PayPal order → POST /v2/checkout/orders → gets approve URL
  2. User clicks approve URL, pays via PayPal hosted page
  3. PayPal POSTs webhook PAYMENT.CAPTURE.COMPLETED to /webhook/paypal
  4. We parse user_id + plan_key from custom_id, activate subscription

Required env vars:
  PAYPAL_CLIENT_ID     — Live Client ID from developer.paypal.com
  PAYPAL_CLIENT_SECRET — Live Secret key from developer.paypal.com

Optional:
  PAYPAL_SUCCESS_URL   — redirect after payment  (default: https://flatfinderil.pages.dev)
  PAYPAL_CANCEL_URL    — redirect on cancel      (default: https://flatfinderil.pages.dev)
  PAYPAL_WEBHOOK_ID    — Webhook ID for signature verification (from PayPal dashboard)

Setup checklist (developer.paypal.com):
  1. Apps & Credentials → Live → FlatFinderIL → copy Client ID + Secret → env vars
  2. Apps & Credentials → Live → FlatFinderIL → Webhooks → Add Webhook
     URL: https://flatfinderil-bot-production.up.railway.app/webhook/paypal
     Events: PAYMENT.CAPTURE.COMPLETED
     → copy Webhook ID → PAYPAL_WEBHOOK_ID env var
"""

import os
import time
import logging
import requests
from base64 import b64encode

logger = logging.getLogger(__name__)

PAYPAL_CLIENT_ID     = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID    = os.environ.get("PAYPAL_WEBHOOK_ID", "")

_BASE        = "https://api-m.paypal.com"
_SUCCESS_URL = os.environ.get("PAYPAL_SUCCESS_URL", "https://flatfinderil.pages.dev")
_CANCEL_URL  = os.environ.get("PAYPAL_CANCEL_URL",  "https://flatfinderil.pages.dev")

# Cached OAuth token: (token_str, expires_at_unix)
_token_cache: tuple[str, float] = ("", 0.0)

_PRICES_USD = {
    "week":      5.49,
    "two_weeks": 8.29,
    "month":     10.99,
    "alerts":    10.99,
}

_PRICES_ILS = {
    "week":      19.90,
    "two_weeks": 29.90,
    "month":     39.90,
    "alerts":    39.90,
}

_PLAN_NAMES = {
    "week":      {"ru": "1 неделя",   "en": "1 week",   "he": "שבוע 1"},
    "two_weeks": {"ru": "2 недели",   "en": "2 weeks",  "he": "2 שבועות"},
    "month":     {"ru": "1 месяц",    "en": "1 month",  "he": "חודש 1"},
    "alerts":    {"ru": "🔔 Уведомления — 1 месяц", "en": "🔔 Alerts — 1 month", "he": "🔔 התראות — חודש 1"},
}


def is_enabled() -> bool:
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)


# ── OAuth ─────────────────────────────────────────────────────────────────────

def _get_token() -> str | None:
    global _token_cache
    token, expires = _token_cache
    if token and time.time() < expires - 60:
        return token

    if not is_enabled():
        logger.warning("[PAYPAL] credentials not set")
        return None

    creds = b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    try:
        resp = requests.post(
            f"{_BASE}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials",
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("access_token"):
            token = data["access_token"]
            expires_in = data.get("expires_in", 32400)
            _token_cache = (token, time.time() + expires_in)
            logger.info("[PAYPAL] OAuth token refreshed")
            return token
        logger.error(f"[PAYPAL] Auth failed: {data}")
        return None
    except Exception as e:
        logger.error(f"[PAYPAL] Auth exception: {e}")
        return None


def _headers() -> dict | None:
    token = _get_token()
    if not token:
        return None
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


# ── Order creation ────────────────────────────────────────────────────────────

def _create_order(amount_usd: float, item_name: str, custom_id: str) -> dict | None:
    hdrs = _headers()
    if not hdrs:
        return None

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "custom_id": custom_id,
            "description": item_name,
            "amount": {
                "currency_code": "USD",
                "value": f"{amount_usd:.2f}",
                "breakdown": {
                    "item_total": {
                        "currency_code": "USD",
                        "value": f"{amount_usd:.2f}",
                    }
                }
            },
            "items": [{
                "name": item_name,
                "quantity": "1",
                "unit_amount": {
                    "currency_code": "USD",
                    "value": f"{amount_usd:.2f}",
                },
                "category": "DIGITAL_GOODS",
            }],
        }],
        "application_context": {
            "brand_name": "FlatFinderIL",
            "landing_page": "BILLING",
            "user_action": "PAY_NOW",
            "return_url": _SUCCESS_URL,
            "cancel_url": _CANCEL_URL,
        },
    }

    try:
        resp = requests.post(
            f"{_BASE}/v2/checkout/orders",
            headers=hdrs,
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 201:
            return data
        logger.error(f"[PAYPAL] Create order failed {resp.status_code}: {data}")
        return None
    except Exception as e:
        logger.error(f"[PAYPAL] Create order exception: {e}")
        return None


def _get_approve_url(order: dict) -> str | None:
    for link in order.get("links", []):
        if link.get("rel") == "approve":
            return link["href"]
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def create_payment_link(plan_key: str, user_id: int, lang: str = "ru") -> dict | None:
    if not is_enabled():
        return None

    amount = _PRICES_USD.get(plan_key)
    if not amount:
        logger.error(f"[PAYPAL] Unknown plan_key={plan_key!r}")
        return None

    names     = _PLAN_NAMES.get(plan_key, {})
    plan_name = names.get(lang) or names.get("ru", plan_key)
    item_name = f"FlatFinderIL — {plan_name}"
    custom_id = f"{user_id}|{plan_key}"

    order = _create_order(amount, item_name, custom_id)
    if not order:
        return None

    url = _get_approve_url(order)
    if not url:
        logger.error(f"[PAYPAL] No approve URL in order: {order.get('id')}")
        return None

    logger.info(f"[PAYPAL] Order created plan={plan_key} user={user_id} ${amount} id={order.get('id')}")
    return {"url": url, "id": order.get("id")}


def create_agent_package_link(package_key: str, user_id: int, lang: str = "ru") -> dict | None:
    if not is_enabled():
        return None

    from pricing import get_agent_package
    pkg = get_agent_package(package_key)
    if not pkg:
        return None

    amount_ils = pkg["price_ils"]
    amount_usd = round(amount_ils / 3.7, 2)
    label      = pkg["label"].get(lang) or pkg["label"]["ru"]
    item_name  = f"FlatFinderIL — {label}"
    custom_id  = f"{user_id}|agent_pkg_{package_key}"

    order = _create_order(amount_usd, item_name, custom_id)
    if not order:
        return None

    url = _get_approve_url(order)
    if not url:
        return None

    logger.info(f"[PAYPAL] Agent pkg order created pkg={package_key} user={user_id}")
    return {"url": url, "id": order.get("id")}


def create_mover_subscription_link(package_key: str, user_id: int, lang: str = "ru") -> dict | None:
    if not is_enabled():
        return None

    from pricing import get_mover_package
    pkg = get_mover_package(package_key)
    if not pkg:
        return None

    amount_usd = round(pkg["price_ils"] / 3.7, 2)
    label      = pkg["label"].get(lang) or pkg["label"]["ru"]
    item_name  = f"FlatFinderIL — {label}"
    custom_id  = f"{user_id}|mover_pkg_{package_key}"

    order = _create_order(amount_usd, item_name, custom_id)
    if not order:
        return None

    url = _get_approve_url(order)
    if not url:
        return None

    logger.info(f"[PAYPAL] Mover sub order created pkg={package_key} user={user_id}")
    return {"url": url, "id": order.get("id")}


def create_service_subscription_link(package_key: str, svc_type: str, user_id: int, lang: str = "ru") -> dict | None:
    """Create PayPal order for cleaning/packing monthly presence subscription."""
    if not is_enabled():
        return None

    from pricing import get_service_package
    pkg = get_service_package(package_key)
    if not pkg:
        return None

    amount_usd = round(pkg["price_ils"] / 3.7, 2)
    label      = pkg["label"].get(lang) or pkg["label"]["ru"]
    item_name  = f"FlatFinderIL — {label}"
    custom_id  = f"{user_id}|svc_{svc_type}_{package_key}"

    order = _create_order(amount_usd, item_name, custom_id)
    if not order:
        return None

    url = _get_approve_url(order)
    if not url:
        return None

    logger.info(f"[PAYPAL] Service sub order created svc={svc_type} pkg={package_key} user={user_id}")
    return {"url": url, "id": order.get("id")}


def create_lead_topup_link(amount_ils: float, credits: int, user_id: int, lang: str = "ru") -> dict | None:
    if not is_enabled():
        return None

    amount_usd = round(amount_ils / 3.7, 2)
    labels = {
        "ru": f"FlatFinderIL — Лиды: {credits} шт.",
        "en": f"FlatFinderIL — Leads: {credits} pcs.",
        "he": f"FlatFinderIL — לידים: {credits} יח'",
    }
    item_name = labels.get(lang, labels["ru"])
    custom_id = f"{user_id}|leads_{credits}"

    order = _create_order(amount_usd, item_name, custom_id)
    if not order:
        return None

    url = _get_approve_url(order)
    if not url:
        return None

    logger.info(f"[PAYPAL] Lead topup order created user={user_id} credits={credits}")
    return {"url": url, "id": order.get("id")}


# ── Webhook ───────────────────────────────────────────────────────────────────

def verify_and_extract(webhook_data: dict) -> tuple[int | None, str | None]:
    """
    Parse PayPal PAYMENT.CAPTURE.COMPLETED webhook and extract (user_id, plan_key).
    custom_id format: "{user_id}|{plan_key}"
    """
    try:
        event_type = webhook_data.get("event_type", "")
        if event_type != "PAYMENT.CAPTURE.COMPLETED":
            logger.info(f"[PAYPAL] Ignoring event type: {event_type}")
            return None, None

        resource   = webhook_data.get("resource", {})
        custom_id  = (
            resource.get("custom_id")
            or resource.get("purchase_units", [{}])[0].get("custom_id", "")
            if resource else ""
        )

        if not custom_id or "|" not in custom_id:
            # Try nested purchase_units
            units = webhook_data.get("resource", {}).get("purchase_units", [])
            if units:
                custom_id = units[0].get("custom_id", "")

        if not custom_id or "|" not in custom_id:
            logger.warning(f"[PAYPAL] No custom_id in webhook: {list(webhook_data.keys())}")
            return None, None

        user_id_str, plan_key = custom_id.split("|", 1)
        if not user_id_str.isdigit():
            logger.warning(f"[PAYPAL] Invalid user_id: {user_id_str!r}")
            return None, None

        status = resource.get("status", "")
        if status != "COMPLETED":
            logger.warning(f"[PAYPAL] Capture status not COMPLETED: {status}")
            return None, None

        logger.info(f"[PAYPAL] Webhook verified: user={user_id_str} plan={plan_key}")
        return int(user_id_str), plan_key

    except Exception as e:
        logger.error(f"[PAYPAL] verify_and_extract exception: {e}")
        return None, None
