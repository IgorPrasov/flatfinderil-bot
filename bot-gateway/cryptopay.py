"""
CryptoPay integration via @CryptoBot / pay.crypt.bot
Testnet: @CryptoTestnetBot / testnet-pay.crypt.bot
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

CRYPTOPAY_TOKEN = os.environ.get("CRYPTOPAY_TOKEN", "")
_TESTNET = os.environ.get("CRYPTOPAY_TESTNET", "").lower() in ("1", "true", "yes")
CRYPTOPAY_BASE = "https://testnet-pay.crypt.bot/api" if _TESTNET else "https://pay.crypt.bot/api"

# USD prices for crypto payments (ILS equivalent)
# week=19.90₪≈$5.50  two_weeks=29.90₪≈$8.00  month=39.90₪≈$11.00
CRYPTO_PRICES_USD = {
    "week":       "5.50",
    "two_weeks":  "8.00",
    "month":      "11.00",
}

SUPPORTED_ASSETS = ["USDT", "TON", "BTC", "ETH"]


def is_enabled() -> bool:
    return bool(CRYPTOPAY_TOKEN)


def _headers() -> dict:
    return {"Crypto-Pay-API-Token": CRYPTOPAY_TOKEN}


def create_invoice(plan_key: str, user_id: int, asset: str = "USDT") -> dict | None:
    """Create a CryptoPay invoice. Returns invoice dict with pay_url, or None on error."""
    if not CRYPTOPAY_TOKEN:
        logger.warning("[CRYPTOPAY] CRYPTOPAY_TOKEN not set")
        return None
    amount = CRYPTO_PRICES_USD.get(plan_key, "5.50")
    payload = f"{plan_key}:{user_id}"
    try:
        resp = requests.post(
            f"{CRYPTOPAY_BASE}/createInvoice",
            headers=_headers(),
            json={
                "asset": asset,
                "amount": amount,
                "description": f"FlatFinderIL — {plan_key.replace('_', ' ')}",
                "payload": payload,
                "expires_in": 3600,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            inv = data["result"]
            logger.info(f"[CRYPTOPAY] Invoice created id={inv['invoice_id']} asset={asset} amount={amount} uid={user_id}")
            return inv
        logger.error(f"[CRYPTOPAY] createInvoice failed: {data}")
        return None
    except Exception as e:
        logger.error(f"[CRYPTOPAY] createInvoice exception: {e}")
        return None


def get_paid_invoices_since(last_checked_ids: set) -> list:
    """Poll for newly paid invoices not in last_checked_ids."""
    if not CRYPTOPAY_TOKEN:
        return []
    try:
        resp = requests.get(
            f"{CRYPTOPAY_BASE}/getInvoices",
            headers=_headers(),
            params={"status": "paid", "count": 100},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            return []
        items = data["result"].get("items", [])
        new_paid = [inv for inv in items if inv["invoice_id"] not in last_checked_ids]
        return new_paid
    except Exception as e:
        logger.error(f"[CRYPTOPAY] getInvoices exception: {e}")
        return []
