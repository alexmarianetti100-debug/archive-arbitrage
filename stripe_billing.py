#!/usr/bin/env python3
"""
Stripe Subscription Billing for Archive Arbitrage.

Handles checkout sessions, webhook events, and subscription lifecycle.

Environment vars:
    STRIPE_SECRET_KEY — Stripe API secret key
    STRIPE_WEBHOOK_SECRET — Webhook signing secret
    STRIPE_PRICE_ID — Price ID for the $39/mo plan
    APP_URL — Base URL for redirects (e.g. https://archivearbitrage.com)
"""

import os
import logging
from datetime import datetime
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("stripe_billing")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
APP_URL = os.getenv("APP_URL", "https://archivearbitrage.com")

# Per-tier Stripe Price IDs (for multi-tier checkout)
STRIPE_PRICE_ID_STARTER = os.getenv("STRIPE_PRICE_ID_STARTER", "")
STRIPE_PRICE_ID_PRO = os.getenv("STRIPE_PRICE_ID_PRO", "")
STRIPE_PRICE_ID_WHALE = os.getenv("STRIPE_PRICE_ID_WHALE", "")

STRIPE_API = "https://api.stripe.com/v1"


# ---------------------------------------------------------------------------
# Stripe API helpers
# ---------------------------------------------------------------------------

async def stripe_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make a request to the Stripe API."""
    if not STRIPE_SECRET_KEY:
        logger.error("STRIPE_SECRET_KEY not configured")
        return {}

    headers = {"Authorization": f"Bearer {STRIPE_SECRET_KEY}"}
    url = f"{STRIPE_API}/{endpoint}"

    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=data)
        else:
            resp = await client.post(url, headers=headers, data=data)

        if resp.status_code >= 400:
            logger.error(f"Stripe API error {resp.status_code}: {resp.text}")
        return resp.json()


# ---------------------------------------------------------------------------
# Tier resolution
# ---------------------------------------------------------------------------

def _build_price_tier_map() -> dict[str, str]:
    """Build a mapping of Stripe Price ID → tier name."""
    m = {}
    if STRIPE_PRICE_ID_STARTER:
        m[STRIPE_PRICE_ID_STARTER] = "starter"
    if STRIPE_PRICE_ID_PRO:
        m[STRIPE_PRICE_ID_PRO] = "pro"
    if STRIPE_PRICE_ID_WHALE:
        m[STRIPE_PRICE_ID_WHALE] = "whale"
    # Legacy single-plan price ID defaults to starter
    if STRIPE_PRICE_ID and STRIPE_PRICE_ID not in m:
        m[STRIPE_PRICE_ID] = "starter"
    return m


def _resolve_tier_from_amount(amount_cents: int) -> str:
    """Fallback: determine tier from checkout amount in cents.

    Thresholds are midpoints between actual price points so minor
    price changes don't break classification.
    Starter ~$30, Pro ~$80, Whale ~$400.
    """
    if amount_cents >= 20_000:   # >= $200
        return "whale"
    if amount_cents >= 5_000:    # >= $50
        return "pro"
    return "starter"


# ---------------------------------------------------------------------------
# Checkout Session
# ---------------------------------------------------------------------------

async def create_checkout_session(telegram_id: int) -> Optional[str]:
    """Create a Stripe Checkout session and return the URL."""
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        logger.warning("Stripe not configured (missing STRIPE_SECRET_KEY or STRIPE_PRICE_ID)")
        return None

    result = await stripe_request("POST", "checkout/sessions", {
        "mode": "subscription",
        "payment_method_types[0]": "card",
        "line_items[0][price]": STRIPE_PRICE_ID,
        "line_items[0][quantity]": "1",
        "success_url": f"{APP_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{APP_URL}/cancel",
        "client_reference_id": str(telegram_id),
        "metadata[telegram_id]": str(telegram_id),
        "subscription_data[metadata][telegram_id]": str(telegram_id),
    })

    return result.get("url")


# ---------------------------------------------------------------------------
# Webhook Event Handling
# ---------------------------------------------------------------------------

async def handle_checkout_completed(event_data: dict):
    """Handle successful checkout — activate the user."""
    session = event_data.get("object", {})
    telegram_id = session.get("client_reference_id") or session.get("metadata", {}).get("telegram_id")
    customer_id = session.get("customer")
    customer_email = session.get("customer_details", {}).get("email", "")
    customer_name = session.get("customer_details", {}).get("name", "")
    subscription_id = session.get("subscription", "")

    # Determine tier — prefer Price ID match, fall back to amount
    tier = None
    session_id = session.get("id", "")
    price_tier_map = _build_price_tier_map()
    if session_id and price_tier_map:
        line_items = await stripe_request("GET", f"checkout/sessions/{session_id}/line_items")
        for item in line_items.get("data", []):
            price_id = item.get("price", {}).get("id", "")
            if price_id in price_tier_map:
                tier = price_tier_map[price_id]
                break

    if not tier:
        tier = _resolve_tier_from_amount(session.get("amount_total", 0))

    logger.info(f"Checkout tier={tier} for session={session_id} (amount={session.get('amount_total', 0)}¢)")

    # ── Telegram activation (if telegram_id provided) ──
    if telegram_id:
        try:
            telegram_id = int(telegram_id)
            from telegram_bot import get_or_create_user, activate_user, send_message
            get_or_create_user(telegram_id)
            activate_user(telegram_id, stripe_customer_id=customer_id)
            logger.info(f"Activated Telegram subscription for telegram_id={telegram_id}")

            await send_message(telegram_id, (
                "🎉 <b>Welcome to Archive Arbitrage!</b>\n\n"
                "Your subscription is now active. You'll start receiving deal alerts.\n\n"
                "Quick setup:\n"
                "• /brands — Filter by brands you care about\n"
                "• /sizes — Filter by your sizes\n"
                "• /minprofit — Set minimum profit threshold\n"
                "• /recent — See latest deals\n\n"
                "Happy hunting! 🏴"
            ))
        except Exception as e:
            logger.error(f"Telegram activation failed: {e}")

    # ── Supabase dashboard activation ──
    if customer_email:
        try:
            from core.supabase_sync import update_user_subscription
            update_user_subscription(
                email=customer_email,
                tier=tier,
                stripe_customer_id=customer_id or "",
                stripe_subscription_id=subscription_id or "",
                status="active",
            )
            logger.info(f"Activated Supabase subscription for {customer_email} (tier={tier})")
        except Exception as e:
            logger.error(f"Supabase activation failed: {e}")

    # ── Onboarding email drip ──
    if customer_email:
        try:
            from core.onboarding import on_new_subscription
            on_new_subscription(
                email=customer_email,
                name=customer_name or "there",
                tier=tier,
                stripe_customer_id=customer_id or "",
            )
        except Exception as e:
            logger.error(f"Onboarding drip registration failed: {e}")

    # ── Referral tracking ──
    if customer_email:
        try:
            import sqlite3 as _sql
            db_path = os.path.join(os.path.dirname(__file__), "data", "archive.db")
            conn = _sql.connect(db_path)
            c = conn.cursor()
            # Check if this user was referred (ref_code stored at email capture)
            c.execute("SELECT ref_code FROM email_subscribers WHERE email=? AND ref_code IS NOT NULL AND ref_code != ''",
                      (customer_email.lower().strip(),))
            row = c.fetchone()
            if row:
                ref_code = row[0]
                c.execute("""
                    CREATE TABLE IF NOT EXISTS referral_conversions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ref_code TEXT NOT NULL,
                        referee_email TEXT NOT NULL,
                        converted_at TEXT DEFAULT (datetime('now')),
                        free_week_granted INTEGER DEFAULT 0
                    )
                """)
                c.execute("INSERT INTO referral_conversions (ref_code, referee_email) VALUES (?, ?)",
                          (ref_code, customer_email.lower().strip()))
                conn.commit()
                logger.info(f"Referral conversion tracked: {customer_email} via ref={ref_code}")
            conn.close()

            # Remove from prospect nurture drip (they converted)
            from core.marketing_emails import unregister_prospect
            unregister_prospect(customer_email.lower().strip())
        except Exception as e:
            logger.error(f"Referral tracking failed: {e}")


async def handle_subscription_deleted(event_data: dict):
    """Handle subscription cancellation."""
    subscription = event_data.get("object", {})
    telegram_id = subscription.get("metadata", {}).get("telegram_id")
    customer_id = subscription.get("customer")

    if not telegram_id:
        # Try to find by customer_id
        if customer_id:
            telegram_id = _find_user_by_customer(customer_id)
        if not telegram_id:
            logger.error("subscription.deleted — can't identify user")
            return

    telegram_id = int(telegram_id)

    from telegram_bot import deactivate_user, send_message

    deactivate_user(telegram_id)
    logger.info(f"Deactivated subscription for telegram_id={telegram_id}")

    try:
        await send_message(telegram_id, (
            "Your Archive Arbitrage subscription has been cancelled.\n\n"
            "You'll no longer receive deal alerts.\n"
            "Use /subscribe to reactivate anytime."
        ))
    except Exception:
        pass

    # Deactivate in Supabase
    try:
        # Find email by customer_id in Supabase
        import httpx as hx
        supa_url = os.getenv("SUPABASE_URL", "")
        supa_key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if supa_url and supa_key and customer_id:
            resp = hx.get(
                f"{supa_url}/rest/v1/profiles?stripe_customer_id=eq.{customer_id}&select=email",
                headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"},
                timeout=10,
            )
            if resp.status_code == 200 and resp.json():
                email = resp.json()[0]["email"]
                from core.supabase_sync import update_user_subscription
                update_user_subscription(email=email, status="cancelled")
                logger.info(f"Deactivated Supabase subscription for {email}")
    except Exception as e:
        logger.error(f"Supabase deactivation failed: {e}")


async def handle_payment_failed(event_data: dict):
    """Handle failed payment."""
    invoice = event_data.get("object", {})
    customer_id = invoice.get("customer")
    subscription_meta = invoice.get("subscription_details", {}).get("metadata", {})
    telegram_id = subscription_meta.get("telegram_id")

    if not telegram_id and customer_id:
        telegram_id = _find_user_by_customer(customer_id)

    if not telegram_id:
        return

    telegram_id = int(telegram_id)

    from telegram_bot import send_message

    try:
        await send_message(telegram_id, (
            "⚠️ <b>Payment Failed</b>\n\n"
            "We couldn't process your payment. Please update your payment method "
            "to keep receiving deal alerts.\n\n"
            "Your access will remain active for a few days while we retry."
        ))
    except Exception:
        pass


def _find_user_by_customer(customer_id: str) -> Optional[int]:
    """Look up telegram_id by Stripe customer_id."""
    from db.sqlite_models import _get_conn
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM telegram_users WHERE stripe_customer_id = ?", (customer_id,))
    row = c.fetchone()
    conn.close()
    return row["telegram_id"] if row else None


# ---------------------------------------------------------------------------
# Webhook dispatcher
# ---------------------------------------------------------------------------

async def process_webhook_event(event: dict) -> bool:
    """Process a Stripe webhook event. Returns True if handled."""
    event_type = event.get("type", "")
    data = event.get("data", {})

    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_failed": handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(data)
        return True

    return False


def verify_webhook_signature(payload: bytes, sig_header: str) -> Optional[dict]:
    """Verify Stripe webhook signature and return the event."""
    import hashlib
    import hmac
    import time
    import json as _json

    if not STRIPE_WEBHOOK_SECRET:
        # If no secret configured, parse without verification (dev mode)
        logger.warning("No STRIPE_WEBHOOK_SECRET — skipping signature verification")
        return _json.loads(payload)

    try:
        # Parse signature header
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")

        if not timestamp or not signature:
            return None

        # Check timestamp (reject events older than 5 minutes)
        if abs(time.time() - int(timestamp)) > 300:
            logger.error("Webhook timestamp too old")
            return None

        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.error("Webhook signature mismatch")
            return None

        return _json.loads(payload)

    except Exception as e:
        logger.error(f"Webhook verification failed: {e}")
        return None
