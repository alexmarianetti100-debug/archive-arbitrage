"""
Automated onboarding email sequence triggered by Stripe subscription events.

Sends a timed drip sequence to new subscribers:
- Day 0: Welcome + setup guide
- Day 3: How to read comp data
- Day 7: First week recap (personalized with their deal stats)
- Day 25: Renewal nudge with ROI summary

Supports multiple backends:
- Resend API (recommended — simple, developer-friendly)
- SMTP (fallback — works with any provider)
- Log-only (default — logs what would be sent, for testing)

Trigger: Call on_new_subscription() from the Stripe webhook handler.
Drip runner: Call run_drip_check() on a schedule (e.g., every hour via cron).
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("onboarding")

# ── Config ──
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("ONBOARDING_FROM_EMAIL", "deals@archivearbitrage.com")
FROM_NAME = os.getenv("ONBOARDING_FROM_NAME", "Archive Arbitrage")

# State file
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ONBOARDING_STATE_FILE = DATA_DIR / "onboarding_state.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Email templates ──

def _welcome_email(name: str, tier: str) -> tuple[str, str]:
    """Day 0: Welcome + setup."""
    subject = "Welcome to Archive Arbitrage"
    body = f"""Hey {name},

You're in. Here's how to start catching deals immediately.

SETUP (2 minutes):
1. Join the Telegram alert channel — check your Whop dashboard for the invite link
2. Join Discord for community + market talk: [link in your Whop dashboard]
3. Set your filters (brand, size, min profit) by messaging the Telegram bot

HOW IT WORKS:
Our system scans 7 platforms 24/7 — Grailed, Poshmark, eBay, Depop, Mercari, Vinted, and Japan sources.

Every listing goes through:
- Comp matching (we find what it actually sold for)
- Authentication scoring (7-signal verification)
- Deal quality grading (A/B/C based on profit, comps, demand)

You only see deals that pass all filters for your {tier} tier.

WHAT TO DO WHEN YOU GET AN ALERT:
1. Check the listing link immediately — good deals move fast
2. Verify the photos match the description
3. Buy if the comps check out (we show you the comp data)
4. List on Grailed/eBay at our recommended sell price

One good flip pays for months of the subscription.

Questions? Reply to this email or ask in #general on Discord.

— Archive Arbitrage
"""
    return subject, body


def _comp_guide_email(name: str) -> tuple[str, str]:
    """Day 3: How to read comp data."""
    subject = "How to read comp data (and why it matters)"
    body = f"""Hey {name},

Quick guide on the comp data we include with every deal alert.

WHAT ARE COMPS?
Comps = comparable sold items. When we say "market value: $650 based on 8 comps,"
we mean 8 similar items sold recently for an average of $650.

HOW WE CALCULATE:
- We search Grailed's sold listings for the same brand + model + material
- Weight recent sales heavier (a sale last week matters more than 6 months ago)
- Adjust for condition (deadstock vs gently used)
- Remove outliers (one crazy auction doesn't skew the average)
- Require minimum 3 comps for "high confidence" pricing

WHAT THE CONFIDENCE LEVELS MEAN:
- High (5+ comps): Rock solid. Buy with confidence.
- Medium (3-4 comps): Good signal. Worth buying if other factors check out.
- Low (1-2 comps): Proceed with caution. Verify independently.

THE NUMBERS THAT MATTER:
- Gap %: How far below market the listing is priced (higher = better deal)
- Est. profit: After platform fees (Grailed 14.2%, Poshmark 20%, etc.) and shipping
- Auth confidence: 0-100% — we block anything below 65%

Pro tip: Focus on deals with high comp confidence AND high auth confidence.
That's the sweet spot — verified price, verified authenticity.

— Archive Arbitrage
"""
    return subject, body


def _week_recap_email(
    name: str,
    deals_sent: int,
    best_profit: float,
    top_brand: str,
) -> tuple[str, str]:
    """Day 7: First week recap with personalized stats."""
    subject = f"Your first week: {deals_sent} deals, ${best_profit:,.0f} best opportunity"
    body = f"""Hey {name},

Here's your first week recap:

YOUR NUMBERS:
- Deals sent to your tier: {deals_sent}
- Best single opportunity: ${best_profit:,.0f} profit
- Most active brand: {top_brand}

{"That best deal alone would cover " + str(int(best_profit / 30)) + "+ months of your subscription." if best_profit >= 30 else ""}

TIPS FROM OUR TOP MEMBERS:
1. Speed matters — the best deals sell within minutes
2. Enable push notifications on Telegram for instant alerts
3. Start with brands you know well, then expand
4. Post your wins in #wins on Discord — it helps the whole community

Questions or feedback? Reply here or ping us in Discord.

— Archive Arbitrage
"""
    return subject, body


def _renewal_email(
    name: str,
    days_left: int,
    total_deals: int,
    best_profit: float,
) -> tuple[str, str]:
    """Day 25: Renewal nudge with ROI summary."""
    subject = "Your subscription renews soon — here's what you'd miss"
    body = f"""Hey {name},

Your subscription {"renews in " + str(days_left) + " days" if days_left > 0 else "renews today"}.

THIS MONTH'S NUMBERS:
- Deals sent: {total_deals}
- Best opportunity: ${best_profit:,.0f} profit
{"- One flip would cover " + str(int(best_profit / 30)) + "+ months of the subscription" if best_profit >= 30 else ""}

The deals don't stop. Every day our system finds new opportunities that most
people miss because they aren't scanning 7 platforms simultaneously with
real-time comp pricing.

No action needed — your subscription auto-renews.
If you want to cancel, you can do so from your Whop dashboard.

— Archive Arbitrage
"""
    return subject, body


# ── Drip sequence definition ──

DRIP_SEQUENCE = [
    {"day": 0, "email_fn": "welcome", "sent_key": "welcome_sent"},
    {"day": 3, "email_fn": "comp_guide", "sent_key": "comp_guide_sent"},
    {"day": 7, "email_fn": "week_recap", "sent_key": "week_recap_sent"},
    {"day": 25, "email_fn": "renewal", "sent_key": "renewal_sent"},
]


# ── State management ──

def _load_state() -> dict:
    try:
        if ONBOARDING_STATE_FILE.exists():
            return json.loads(ONBOARDING_STATE_FILE.read_text())
    except Exception:
        pass
    return {"subscribers": {}}


def _save_state(state: dict) -> None:
    ONBOARDING_STATE_FILE.write_text(json.dumps(state, indent=2))


def on_new_subscription(
    email: str,
    name: str,
    tier: str = "beginner",
    stripe_customer_id: str = "",
) -> None:
    """Called when a new Stripe subscription is created.

    Registers the subscriber for the drip sequence.
    """
    state = _load_state()
    subs = state.setdefault("subscribers", {})

    subs[email] = {
        "name": name,
        "email": email,
        "tier": tier,
        "stripe_customer_id": stripe_customer_id,
        "subscribed_at": datetime.now().isoformat(),
        "welcome_sent": False,
        "comp_guide_sent": False,
        "week_recap_sent": False,
        "renewal_sent": False,
    }

    _save_state(state)
    logger.info(f"Registered {email} for onboarding drip sequence")

    # Send welcome immediately (day 0)
    _send_drip_email(email, "welcome")


def on_subscription_cancelled(email: str) -> None:
    """Called when a subscription is cancelled. Stops the drip sequence."""
    state = _load_state()
    subs = state.get("subscribers", {})
    if email in subs:
        del subs[email]
        _save_state(state)
        logger.info(f"Removed {email} from onboarding drip")


# ── Drip runner ──

def run_drip_check() -> int:
    """Check all subscribers and send any due drip emails.

    Call this on a schedule (e.g., every hour via cron).
    Returns the number of emails sent.
    """
    state = _load_state()
    subs = state.get("subscribers", {})
    sent_count = 0

    for email, sub_data in list(subs.items()):
        subscribed_at = datetime.fromisoformat(sub_data["subscribed_at"])
        days_since = (datetime.now() - subscribed_at).days

        for step in DRIP_SEQUENCE:
            if days_since >= step["day"] and not sub_data.get(step["sent_key"], False):
                if _send_drip_email(email, step["email_fn"]):
                    sub_data[step["sent_key"]] = True
                    sent_count += 1

    _save_state(state)
    return sent_count


def _send_drip_email(email: str, email_type: str) -> bool:
    """Send a specific drip email to a subscriber."""
    state = _load_state()
    sub_data = state.get("subscribers", {}).get(email, {})
    name = sub_data.get("name", "there")
    tier = sub_data.get("tier", "beginner")

    # Generate email content
    if email_type == "welcome":
        subject, body = _welcome_email(name, tier)
    elif email_type == "comp_guide":
        subject, body = _comp_guide_email(name)
    elif email_type == "week_recap":
        since = sub_data.get("subscribed_at", datetime.now().isoformat())
        subject, body = _week_recap_email(
            name,
            deals_sent=_get_deals_count(since),
            best_profit=_get_best_profit(since),
            top_brand=_get_top_brand(since),
        )
    elif email_type == "renewal":
        since = sub_data.get("subscribed_at", datetime.now().isoformat())
        subject, body = _renewal_email(
            name,
            days_left=5,
            total_deals=_get_deals_count(since),
            best_profit=_get_best_profit(since),
        )
    else:
        logger.warning(f"Unknown email type: {email_type}")
        return False

    return _send_email(email, subject, body)


# ── Email sending backends ──

def _send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via the configured backend."""

    if RESEND_API_KEY:
        return _send_via_resend(to, subject, body)
    elif SMTP_HOST:
        return _send_via_smtp(to, subject, body)
    else:
        # Log-only mode
        logger.info(
            f"[EMAIL LOG] To: {to}\n"
            f"  Subject: {subject}\n"
            f"  Body preview: {body[:200]}..."
        )
        return True


def _send_via_resend(to: str, subject: str, body: str) -> bool:
    """Send via Resend API."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{FROM_NAME} <{FROM_EMAIL}>",
                    "to": [to],
                    "subject": subject,
                    "text": body,
                },
            )
            if resp.status_code == 200:
                logger.info(f"Email sent via Resend: {subject} -> {to}")
                return True
            else:
                logger.warning(f"Resend API error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Resend send failed: {e}")
    return False


def _send_via_smtp(to: str, subject: str, body: str) -> bool:
    """Send via SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        logger.info(f"Email sent via SMTP: {subject} -> {to}")
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
    return False


# ── Stats helpers (query real deal data from DB) ──

def _get_db_conn():
    """Get a connection to the archive database."""
    import sqlite3
    conn = sqlite3.connect(str(DATA_DIR / "archive.db"))
    conn.row_factory = sqlite3.Row
    return conn


def _get_deals_count(since: str) -> int:
    """Count graded deals since a given ISO date."""
    try:
        conn = _get_db_conn()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM items WHERE grade IN ('A', 'B', 'C') AND created_at >= ?",
            (since,),
        )
        count = c.fetchone()[0]
        conn.close()
        return count or 0
    except Exception:
        return 0


def _get_best_profit(since: str) -> float:
    """Get the highest profit opportunity since a given ISO date."""
    try:
        conn = _get_db_conn()
        c = conn.cursor()
        c.execute(
            "SELECT MAX(exact_profit) FROM items "
            "WHERE grade IN ('A', 'B', 'C') AND exact_profit > 0 AND created_at >= ?",
            (since,),
        )
        row = c.fetchone()
        conn.close()
        return float(row[0]) if row and row[0] else 0.0
    except Exception:
        return 0.0


def _get_top_brand(since: str) -> str:
    """Get the most common brand in graded deals since a given ISO date."""
    try:
        conn = _get_db_conn()
        c = conn.cursor()
        c.execute(
            "SELECT brand, COUNT(*) as cnt FROM items "
            "WHERE grade IN ('A', 'B', 'C') AND brand IS NOT NULL AND brand != '' "
            "AND created_at >= ? GROUP BY brand ORDER BY cnt DESC LIMIT 1",
            (since,),
        )
        row = c.fetchone()
        conn.close()
        return row[0] if row else "N/A"
    except Exception:
        return "N/A"


# ── CLI ──

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Onboarding email system")
    parser.add_argument("--test", help="Send test sequence to this email")
    parser.add_argument("--drip", action="store_true", help="Run drip check")
    parser.add_argument("--status", action="store_true", help="Show subscriber status")
    args = parser.parse_args()

    if args.test:
        on_new_subscription(args.test, "Test User", "pro")
        print(f"Registered {args.test} and sent welcome email (check logs)")
    elif args.drip:
        sent = run_drip_check()
        print(f"Drip check complete: {sent} emails sent")
    elif args.status:
        state = _load_state()
        subs = state.get("subscribers", {})
        print(f"Subscribers in drip: {len(subs)}")
        for email, data in subs.items():
            days = (datetime.now() - datetime.fromisoformat(data["subscribed_at"])).days
            sent_steps = sum(1 for step in DRIP_SEQUENCE if data.get(step["sent_key"]))
            print(f"  {email} — day {days}, {sent_steps}/{len(DRIP_SEQUENCE)} emails sent")
    else:
        parser.print_help()
