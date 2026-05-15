"""
PayPlus (formerly Cardcom) payment integration for FlatFinderIL.

Flow:
  1. Bot creates a PayPlus payment page link.
  2. User clicks URL, pays with card on PayPlus hosted page.
  3. PayPlus POSTs a callback to /webhook/payplus.
  4. We verify the payment by calling PayPlus API, extract user_id + plan_key
     from more_info fields, call activate_subscription(), notify user in Telegram.

Required env vars:
  PAYPLUS_API_KEY          — from PayPlus admin console
  PAYPLUS_SECRET_KEY       — from PayPlus admin console
  PAYPLUS_PAGE_UID         — UID of your payment page template (created in dashboard)

Optional:
  PAYPLUS_SUCCESS_URL      — redirect after success  (default: flatfinderil.com/stripe/success)
  PAYPLUS_CANCEL_URL       — redirect on cancel      (default: flatfinderil.com/stripe/cancel)
  PAYPLUS_WEBHOOK_URL      — public callback URL     (default: https://flatfinderil.com/webhook/payplus)

Setup checklist (PayPlus dashboard → restapi.payplus.co.il):
  1. Create a payment page, copy its UID → PAYPLUS_PAGE_UID
  2. Copy API key + Secret key → PAYPLUS_API_KEY / PAYPLUS_SECRET_KEY
  3. In payment page settings set "Callback URL" to PAYPLUS_WEBHOOK_URL
"""

import os
import json
import logging
import requests
import hmac
import hashlib

logger = logging.getLogger(__name__)

PAYPLUS_API_KEY    = os.environ.get("PAYPLUS_API_KEY", "")
PAYPLUS_SECRET_KEY = os.environ.get("PAYPLUS_SECRET_KEY", "")
PAYPLUS_PAGE_UID   = os.environ.get("PAYPLUS_PAGE_UID", "")

_BASE = "https://restapi.payplus.co.il/api/v1.0"

# ILS prices (same as config.py PLAN_PRICES_ILS)
_PRICES_ILS = {
    "week":      19.90,
    "two_weeks": 29.90,
    "month":     39.90,
}

_PLAN_NAMES = {
    "week":      {"ru": "1 неделя",  "en": "1 week",  "he": "שבוע 1"},
    "two_weeks": {"ru": "2 недели",   "en": "2 weeks", "he": "2 שבועות"},
    "month":     {"ru": "1 месяц",    "en": "1 month", "he": "חודש 1"},
}


def is_enabled() -> bool:
    return bool(PAYPLUS_API_KEY and PAYPLUS_SECRET_KEY and PAYPLUS_PAGE_UID)


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "api-key":    PAYPLUS_API_KEY,
        "secret-key": PAYPLUS_SECRET_KEY,
    }


def create_payment_link(plan_key: str, user_id: int, lang: str = "ru") -> dict | None:
    """
    Create a PayPlus hosted-page payment link.

    Returns:
      {"url": "https://payment.payplus.co.il/...", "uid": "..."}
    or None on error.
    """
    if not is_enabled():
        logger.warning("[PAYPLUS] credentials not set")
        return None

    amount = _PRICES_ILS.get(plan_key)
    if not amount:
        logger.error(f"[PAYPLUS] Unknown plan_key={plan_key!r}")
        return None

    names = _PLAN_NAMES.get(plan_key, {})
    plan_name = names.get(lang) or names.get("ru", plan_key)

    success_url = os.environ.get(
        "PAYPLUS_SUCCESS_URL",
        "https://flatfinderil.com/stripe/success",   # reuse the same success page
    )
    cancel_url = os.environ.get(
        "PAYPLUS_CANCEL_URL",
        "https://flatfinderil.com/stripe/cancel",
    )
    callback_url = os.environ.get(
        "PAYPLUS_WEBHOOK_URL",
        "https://flatfinderil.com/webhook/payplus",
    )

    payload = {
        "payment_page_uid": PAYPLUS_PAGE_UID,
        "amount": amount,
        "currency_code": "ILS",
        "refURL_success":  success_url,
        "refURL_failure":  cancel_url,
        "refURL_callback": callback_url,
        "send_failure_callback": False,
        # Metadata — up to 5 free-text fields, returned in the callback
        "more_info":   str(user_id),
        "more_info_1": plan_key,
        "more_info_2": lang,
        # Invoice / product line
        "items": [{
            "name":     f"FlatFinderIL — {plan_name}",
            "quantity": 1,
            "price":    amount,
            "vat_type": 1,  # 1 = VAT included
        }],
    }

    try:
        resp = requests.post(
            f"{_BASE}/PaymentPages/generateLink",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("results", {}).get("status") == "success":
            url = data["data"]["payment_page_link"]
            uid = data["data"].get("page_request_uid", "")
            logger.info(
                f"[PAYPLUS] Link created plan={plan_key} user={user_id} "
                f"amount={amount}₪ uid={uid}"
            )
            return {"url": url, "uid": uid}
        else:
            err = data.get("results", {})
            logger.error(f"[PAYPLUS] generateLink failed: {err}")
            return None
    except Exception as e:
        logger.error(f"[PAYPLUS] create_payment_link exception: {e}")
        return None


def verify_and_extract(callback_data: dict) -> tuple[int | None, str | None]:
    """
    Verify a PayPlus callback and extract (user_id, plan_key).

    PayPlus sends a POST with transaction details.
    We confirm by calling the PayPlus API with the transaction UID.

    Returns (user_id, plan_key) on success, (None, None) otherwise.
    """
    if not is_enabled():
        logger.error("[PAYPLUS] credentials not set — cannot verify callback")
        return None, None

    try:
        # PayPlus sends transaction_uid in the callback body
        txn_uid = (
            callback_data.get("transaction_uid")
            or callback_data.get("data", {}).get("transaction_uid")
        )
        if not txn_uid:
            logger.warning(f"[PAYPLUS] No transaction_uid in callback: {callback_data}")
            return None, None

        # Verify by fetching transaction from PayPlus
        resp = requests.get(
            f"{_BASE}/Transactions/{txn_uid}",
            headers=_headers(),
            timeout=10,
        )
        txn = resp.json()

        status = (
            txn.get("data", {}).get("status_code")
            or txn.get("results", {}).get("status")
        )
        logger.info(f"[PAYPLUS] Transaction {txn_uid} status={status}")

        # Accept only approved transactions
        if str(status) not in ("1", "approved", "success"):
            logger.warning(f"[PAYPLUS] Transaction not approved: status={status}")
            return None, None

        # Extract metadata from more_info fields
        txn_data = txn.get("data", {})
        # more_info fields can be on the transaction or on the page_request
        more_info   = txn_data.get("more_info")   or callback_data.get("more_info", "")
        more_info_1 = txn_data.get("more_info_1") or callback_data.get("more_info_1", "")

        user_id  = int(more_info) if more_info and str(more_info).isdigit() else None
        plan_key = more_info_1 if more_info_1 in ("week", "two_weeks", "month") else None

        if not user_id or not plan_key:
            logger.error(
                f"[PAYPLUS] Missing metadata: user_id={more_info!r} plan={more_info_1!r}"
            )
            return None, None

        logger.info(f"[PAYPLUS] Payment verified: user={user_id} plan={plan_key}")
        return user_id, plan_key

    except Exception as e:
        logger.error(f"[PAYPLUS] verify_and_extract exception: {e}")
        return None, None
