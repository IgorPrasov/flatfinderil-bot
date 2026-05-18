"""
Morning (Green Invoice) payment integration for FlatFinderIL.

Flow:
  1. Bot authenticates → JWT token via POST /v1/account/token
  2. Bot creates a payment document → POST /v1/documents → gets bill.url
  3. User clicks bill.url, pays via Morning hosted page (card / Bit / Apple Pay)
  4. Morning POSTs webhook to /webhook/morning on payment
  5. We parse user_id + plan_key from document description, activate subscription

Required env vars:
  MORNING_API_ID       — API Key ID from Morning → Settings → Developer Tools → API Keys
  MORNING_API_SECRET   — API Key Secret (same location)

Optional:
  MORNING_SUCCESS_URL  — redirect after payment  (default: https://flatfinderil.pages.dev)
  MORNING_CANCEL_URL   — redirect on cancel      (default: https://flatfinderil.pages.dev)
  MORNING_WEBHOOK_URL  — public callback URL     (default: https://flatfinderil-bot-production.up.railway.app/webhook/morning)

Setup checklist (Morning dashboard):
  1. Settings → Developer Tools → API Keys → create key → copy ID + Secret
  2. Settings → Developer Tools → Webhooks → Create → select "Document created" event
     → set URL to MORNING_WEBHOOK_URL
  3. Make sure "Digital Payments" add-on is enabled in your Morning account
"""

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

MORNING_API_ID     = os.environ.get("MORNING_API_ID", "")
MORNING_API_SECRET = os.environ.get("MORNING_API_SECRET", "")

_BASE = "https://api.greeninvoice.co.il/api/v1"

# Document type: 320 = חשבונית מס / קבלה (Tax Invoice + Receipt) — used for instant payments
_DOC_TYPE_PAYMENT = 320

# Cached JWT: (token_str, expires_at_unix)
_jwt_cache: tuple[str, float] = ("", 0.0)

# ILS prices
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

_SUCCESS_URL = os.environ.get("MORNING_SUCCESS_URL", "https://flatfinderil.pages.dev")
_CANCEL_URL  = os.environ.get("MORNING_CANCEL_URL",  "https://flatfinderil.pages.dev")
_WEBHOOK_URL = os.environ.get(
    "MORNING_WEBHOOK_URL",
    "https://flatfinderil-bot-production.up.railway.app/webhook/morning",
)


def is_enabled() -> bool:
    return bool(MORNING_API_ID and MORNING_API_SECRET)


# ── Authentication ────────────────────────────────────────────────────────────

def _get_token() -> str | None:
    """Return a valid JWT token, refreshing if expired."""
    global _jwt_cache
    token, expires = _jwt_cache
    if token and time.time() < expires - 60:
        return token

    if not is_enabled():
        logger.warning("[MORNING] credentials not set")
        return None

    try:
        resp = requests.post(
            f"{_BASE}/account/token",
            json={"id": MORNING_API_ID, "secret": MORNING_API_SECRET},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("token"):
            token = data["token"]
            # Morning tokens expire in 24h; cache for 23h
            _jwt_cache = (token, time.time() + 23 * 3600)
            logger.info("[MORNING] JWT token refreshed")
            return token
        logger.error(f"[MORNING] Auth failed: {data}")
        return None
    except Exception as e:
        logger.error(f"[MORNING] Auth exception: {e}")
        return None


def _headers() -> dict | None:
    token = _get_token()
    if not token:
        return None
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


# ── Document / payment link creation ─────────────────────────────────────────

def _build_description(user_id: int, plan_key: str) -> str:
    """Encode metadata into document description for webhook extraction."""
    return f"flatfinderil|{user_id}|{plan_key}"


def _create_document(amount: float, item_name: str, description: str) -> dict | None:
    """POST /v1/documents and return the response dict, or None on error."""
    hdrs = _headers()
    if not hdrs:
        return None

    payload = {
        "type": _DOC_TYPE_PAYMENT,
        "lang": "he",
        "currency": "ILS",
        "vatType": 1,          # VAT included
        "rounding": False,
        "signed": True,
        "attachment": True,
        "description": description,
        "client": {
            "name": "FlatFinderIL Customer",
            "emails": [],
        },
        "income": [
            {
                "description": item_name,
                "quantity": 1,
                "price": amount,
                "currency": "ILS",
                "vatType": 1,
            }
        ],
        "payment": [
            {
                "type": 4,         # 4 = credit card (Morning code)
                "price": amount,
                "currency": "ILS",
                "date": time.strftime("%Y-%m-%d"),
            }
        ],
    }

    try:
        resp = requests.post(
            f"{_BASE}/documents",
            headers=hdrs,
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            return data
        logger.error(f"[MORNING] Create document failed {resp.status_code}: {data}")
        return None
    except Exception as e:
        logger.error(f"[MORNING] Create document exception: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def create_payment_link(plan_key: str, user_id: int, lang: str = "ru") -> dict | None:
    """
    Create a Morning payment link for a subscription plan.

    Returns {"url": "https://...", "id": "doc-uuid"} or None.
    """
    if not is_enabled():
        logger.warning("[MORNING] credentials not set — cannot create payment link")
        return None

    amount = _PRICES_ILS.get(plan_key)
    if not amount:
        logger.error(f"[MORNING] Unknown plan_key={plan_key!r}")
        return None

    names = _PLAN_NAMES.get(plan_key, {})
    plan_name = names.get(lang) or names.get("ru", plan_key)
    item_name = f"FlatFinderIL — {plan_name}"
    description = _build_description(user_id, plan_key)

    doc = _create_document(amount, item_name, description)
    if not doc:
        return None

    bill_url = doc.get("bill", {}).get("url") or doc.get("url")
    doc_id   = doc.get("id", "")

    if not bill_url:
        logger.error(f"[MORNING] No bill.url in response: {list(doc.keys())}")
        return None

    logger.info(f"[MORNING] Payment link created plan={plan_key} user={user_id} amount={amount}₪ id={doc_id}")
    return {"url": bill_url, "id": doc_id}


def create_agent_package_link(package_key: str, user_id: int, lang: str = "ru") -> dict | None:
    """Create a Morning payment link for an agent listing package."""
    if not is_enabled():
        return None

    from pricing import get_agent_package
    pkg = get_agent_package(package_key)
    if not pkg:
        logger.error(f"[MORNING] Unknown agent package key={package_key!r}")
        return None

    label     = pkg["label"].get(lang) or pkg["label"]["ru"]
    item_name = f"FlatFinderIL — {label}"
    description = _build_description(user_id, f"agent_pkg_{package_key}")

    doc = _create_document(pkg["price_ils"], item_name, description)
    if not doc:
        return None

    bill_url = doc.get("bill", {}).get("url") or doc.get("url")
    doc_id   = doc.get("id", "")
    if not bill_url:
        logger.error(f"[MORNING] No bill.url for agent pkg {package_key}")
        return None

    logger.info(f"[MORNING] Agent pkg link created pkg={package_key} user={user_id} amount={pkg['price_ils']}₪")
    return {"url": bill_url, "id": doc_id}


def create_mover_subscription_link(package_key: str, user_id: int, lang: str = "ru") -> dict | None:
    """Create a Morning payment link for a mover weekly subscription."""
    if not is_enabled():
        return None

    from pricing import get_mover_package
    pkg = get_mover_package(package_key)
    if not pkg:
        logger.error(f"[MORNING] Unknown mover package key={package_key!r}")
        return None

    label       = pkg["label"].get(lang) or pkg["label"]["ru"]
    item_name   = f"FlatFinderIL — {label}"
    description = _build_description(user_id, f"mover_pkg_{package_key}")

    doc = _create_document(pkg["price_ils"], item_name, description)
    if not doc:
        return None

    bill_url = doc.get("bill", {}).get("url") or doc.get("url")
    doc_id   = doc.get("id", "")
    if not bill_url:
        logger.error(f"[MORNING] No bill.url for mover pkg {package_key}")
        return None

    logger.info(f"[MORNING] Mover sub link created pkg={package_key} user={user_id} amount={pkg['price_ils']}₪")
    return {"url": bill_url, "id": doc_id}


def create_lead_topup_link(amount_ils: float, credits: int, user_id: int, lang: str = "ru") -> dict | None:
    """Create a Morning payment link for lead balance top-up."""
    if not is_enabled():
        return None

    labels = {
        "ru": f"FlatFinderIL — Лиды: {credits} шт.",
        "en": f"FlatFinderIL — Leads: {credits} pcs.",
        "he": f"FlatFinderIL — לידים: {credits} יח'",
    }
    item_name   = labels.get(lang, labels["ru"])
    description = _build_description(user_id, f"leads_{credits}")

    doc = _create_document(amount_ils, item_name, description)
    if not doc:
        return None

    bill_url = doc.get("bill", {}).get("url") or doc.get("url")
    doc_id   = doc.get("id", "")
    if not bill_url:
        logger.error(f"[MORNING] No bill.url for lead topup user={user_id}")
        return None

    logger.info(f"[MORNING] Lead topup link created user={user_id} credits={credits} amount={amount_ils}₪")
    return {"url": bill_url, "id": doc_id}


# ── Webhook verification ──────────────────────────────────────────────────────

def verify_and_extract(webhook_data: dict) -> tuple[int | None, str | None]:
    """
    Parse Morning webhook payload and extract (user_id, plan_key).

    Morning fires a webhook when a document is created/paid.
    We store metadata in the document description: "flatfinderil|{user_id}|{plan_key}"

    Returns (user_id, plan_key) on success, (None, None) otherwise.
    """
    try:
        description = webhook_data.get("description", "")
        if not description.startswith("flatfinderil|"):
            # Not our document
            return None, None

        parts = description.split("|")
        if len(parts) < 3:
            logger.warning(f"[MORNING] Malformed description: {description!r}")
            return None, None

        user_id_str = parts[1]
        plan_key    = parts[2]

        if not user_id_str.isdigit():
            logger.warning(f"[MORNING] Invalid user_id in description: {user_id_str!r}")
            return None, None

        user_id = int(user_id_str)

        # Verify payment exists — check transactions or document status
        transactions = webhook_data.get("transactions") or []
        status       = webhook_data.get("status")

        # Morning signed document = payment confirmed
        # transactions array populated = payment processed
        if not transactions and status not in ("signed", "paid", None):
            logger.warning(f"[MORNING] Document not paid: status={status} transactions={transactions}")
            return None, None

        logger.info(f"[MORNING] Webhook verified: user={user_id} plan={plan_key}")
        return user_id, plan_key

    except Exception as e:
        logger.error(f"[MORNING] verify_and_extract exception: {e}")
        return None, None
