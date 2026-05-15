"""
Stripe payment integration for FlatFinderIL subscription.

Flow:
  1. Bot creates a Stripe Checkout Session (hosted page).
  2. User clicks the URL, pays with card.
  3. Stripe POSTs a webhook to /webhook/stripe.
  4. We verify the signature, extract user_id + plan_key from metadata,
     call activate_subscription(), and send a Telegram confirmation message.

Required env vars:
  STRIPE_SECRET_KEY      — sk_live_... or sk_test_...
  STRIPE_WEBHOOK_SECRET  — whsec_... (from Stripe dashboard → webhooks)

Optional:
  STRIPE_SUCCESS_URL     — redirect URL after payment (defaults to bot deep-link)
  STRIPE_CANCEL_URL      — redirect URL on cancel    (defaults to bot deep-link)
"""

import os
import hmac
import hashlib
import json
import time
import logging
import requests

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY     = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

_BASE = "https://api.stripe.com/v1"

# ILS prices in *agorot* (smallest unit = 1/100 ₪).
# Mirror of config.py PLAN_PRICES_ILS × 100.
_PRICES_ILS_AGOROT = {
    "week":      1990,   # 19.90 ₪
    "two_weeks": 2990,   # 29.90 ₪
    "month":     3990,   # 39.90 ₪
}

# Plan display names
_PLAN_NAMES = {
    "week":      {"ru": "1 неделя",  "en": "1 week",   "he": "שבוע 1"},
    "two_weeks": {"ru": "2 недели",   "en": "2 weeks",  "he": "2 שבועות"},
    "month":     {"ru": "1 месяц",    "en": "1 month",  "he": "חודש 1"},
}

_BOT_LINK = "https://t.me/flatfinderil_bot"


def is_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY)


def _headers() -> dict:
    return {"Authorization": f"Bearer {STRIPE_SECRET_KEY}"}


def create_checkout_session(plan_key: str, user_id: int, lang: str = "ru") -> dict | None:
    """
    Create a Stripe Checkout Session for the given plan.

    Returns a dict with:
      url       — hosted checkout URL to send to user
      session_id — Stripe session ID
    Returns None on error.
    """
    if not STRIPE_SECRET_KEY:
        logger.warning("[STRIPE] STRIPE_SECRET_KEY not set")
        return None

    amount = _PRICES_ILS_AGOROT.get(plan_key)
    if not amount:
        logger.error(f"[STRIPE] Unknown plan_key={plan_key!r}")
        return None

    names = _PLAN_NAMES.get(plan_key, {})
    plan_name = names.get(lang) or names.get("ru", plan_key)

    descriptions = {
        "ru": f"Доступ к FlatFinderIL на {plan_key.replace('_', ' ')}",
        "en": f"FlatFinderIL access — {plan_key.replace('_', ' ')}",
        "he": f"גישה ל-FlatFinderIL — {plan_key.replace('_', ' ')}",
    }
    description = descriptions.get(lang, descriptions["ru"])

    success_url = os.environ.get(
        "STRIPE_SUCCESS_URL",
        f"{_BOT_LINK}?start=paid_{plan_key}",
    )
    cancel_url = os.environ.get(
        "STRIPE_CANCEL_URL",
        f"{_BOT_LINK}",
    )

    payload = {
        "mode": "payment",
        "line_items[0][price_data][currency]": "ils",
        "line_items[0][price_data][unit_amount]": str(amount),
        "line_items[0][price_data][product_data][name]": f"FlatFinderIL — {plan_name}",
        "line_items[0][price_data][product_data][description]": description,
        "line_items[0][quantity]": "1",
        "metadata[user_id]": str(user_id),
        "metadata[plan_key]": plan_key,
        "client_reference_id": str(user_id),
        "success_url": success_url,
        "cancel_url": cancel_url,
        "locale": "auto",
        # Collect email for receipt
        "customer_creation": "always",
    }

    try:
        resp = requests.post(
            f"{_BASE}/checkout/sessions",
            headers=_headers(),
            data=payload,
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200:
            session_id = data.get("id", "")
            url = data.get("url", "")
            logger.info(
                f"[STRIPE] Session created plan={plan_key} user={user_id} "
                f"amount={amount/100:.2f}₪ session={session_id}"
            )
            return {"url": url, "session_id": session_id}
        else:
            err = data.get("error", {})
            logger.error(f"[STRIPE] Session creation failed: {err.get('message', data)}")
            return None
    except Exception as e:
        logger.error(f"[STRIPE] create_checkout_session exception: {e}")
        return None


def verify_webhook(body: bytes, sig_header: str) -> dict | None:
    """
    Verify Stripe webhook signature and return the event dict, or None if invalid.

    Uses Stripe's v1 signature scheme:
    https://stripe.com/docs/webhooks/signatures
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("[STRIPE] STRIPE_WEBHOOK_SECRET not set — cannot verify webhook")
        return None

    try:
        # Parse t= and v1= from the header
        parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(","))}
        timestamp = parts.get("t")
        signature = parts.get("v1")
        if not timestamp or not signature:
            logger.warning("[STRIPE] Malformed Stripe-Signature header")
            return None

        # Replay attack protection: reject events older than 5 minutes
        age = abs(time.time() - int(timestamp))
        if age > 300:
            logger.warning(f"[STRIPE] Webhook timestamp too old ({age:.0f}s)")
            return None

        # Compute expected signature
        signed_payload = f"{timestamp}.{body.decode('utf-8')}"
        expected = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("[STRIPE] Webhook signature mismatch")
            return None

        event = json.loads(body)
        logger.info(f"[STRIPE] Verified webhook event type={event.get('type')}")
        return event

    except Exception as e:
        logger.error(f"[STRIPE] verify_webhook exception: {e}")
        return None


def extract_payment_info(event: dict) -> tuple[int | None, str | None]:
    """
    Extract (user_id, plan_key) from a checkout.session.completed event.
    Returns (None, None) if not applicable.
    """
    if event.get("type") != "checkout.session.completed":
        return None, None

    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata", {})

    try:
        user_id = int(metadata.get("user_id", 0))
    except (ValueError, TypeError):
        user_id = None

    plan_key = metadata.get("plan_key")
    return user_id or None, plan_key or None
