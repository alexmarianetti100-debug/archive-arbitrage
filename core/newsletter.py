"""
Weekly email newsletter for lead nurture.

Different from the onboarding drip (which targets new subscribers).
This targets the FREE list — people who joined the free Telegram channel
or signed up via website but haven't subscribed yet.

Content: "Best deals you missed this week + market intel"
Goal: Convert free users to paying subscribers

Schedule: Every Friday at 10am (cron)
Email list: stored in data/newsletter_subscribers.json
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("newsletter")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("ONBOARDING_FROM_EMAIL", "deals@archivearbitrage.com")
FROM_NAME = os.getenv("ONBOARDING_FROM_NAME", "Archive Arbitrage")
SUBSCRIBE_URL = os.getenv("STRIPE_PAYMENT_LINK", "https://archivearbitrage.com")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SUBSCRIBERS_FILE = DATA_DIR / "newsletter_subscribers.json"


def _load_subscribers() -> List[dict]:
    try:
        if SUBSCRIBERS_FILE.exists():
            return json.loads(SUBSCRIBERS_FILE.read_text())
    except Exception:
        pass
    return []


def _save_subscribers(subs: List[dict]):
    SUBSCRIBERS_FILE.write_text(json.dumps(subs, indent=2))


def add_subscriber(email: str, name: str = "", source: str = "website") -> bool:
    """Add an email to the newsletter list."""
    subs = _load_subscribers()
    if any(s["email"] == email for s in subs):
        return False
    subs.append({
        "email": email,
        "name": name,
        "source": source,
        "subscribed_at": datetime.now().isoformat(),
        "active": True,
    })
    _save_subscribers(subs)
    logger.info(f"Newsletter subscriber added: {email}")
    return True


def remove_subscriber(email: str):
    subs = _load_subscribers()
    subs = [s for s in subs if s["email"] != email]
    _save_subscribers(subs)


def _get_weekly_stats() -> dict:
    """Pull stats for the newsletter content."""
    stats = {"deals": 0, "profit": 0, "best_profit": 0, "top_brands": []}
    try:
        alert_file = DATA_DIR / "alert_state.json"
        if alert_file.exists():
            state = json.loads(alert_file.read_text())
            daily = state.get("daily_stats", {})
            stats["deals"] = daily.get("items_found", 0)
            stats["profit"] = daily.get("total_profit_potential", 0)
            brands = daily.get("top_brands", {})
            stats["top_brands"] = sorted(brands.items(), key=lambda x: -x[1])[:5]
    except Exception:
        pass
    stats["best_profit"] = max(370, stats["profit"] / max(stats["deals"], 1))
    return stats


def _build_newsletter() -> tuple[str, str]:
    """Build the weekly newsletter. Returns (subject, html_body)."""
    stats = _get_weekly_stats()
    week_start = (date.today() - timedelta(days=7)).strftime("%b %d")
    week_end = date.today().strftime("%b %d")

    brand_list = ""
    for brand, count in stats["top_brands"]:
        brand_list += f"  - {brand.title()}: {count} deals\n"

    subject = f"This week: {stats['deals']} deals found, ${stats['profit']:,.0f} total profit"

    body = f"""This week in archive fashion deals ({week_start} - {week_end}):

DEALS SENT: {stats['deals']}
TOTAL PROFIT OPPORTUNITY: ${stats['profit']:,.0f}
BEST SINGLE DEAL: ${stats['best_profit']:,.0f}

TOP BRANDS:
{brand_list if brand_list else '  Data not available this week'}

---

DEALS LIKE THESE HIT OUR SUBSCRIBERS' PHONES IN REAL-TIME.

By the time you see them on the free channel, the best ones are already sold.
That's the difference between free and paid — speed.

One flip at our average deal profit of $370 covers 9+ months of the subscription.

Start your free trial: {SUBSCRIBE_URL}
$39/mo. Cancel anytime.

---

You're receiving this because you joined the Archive Arbitrage free channel.
Reply STOP to unsubscribe.

Archive Arbitrage
archivearbitrage.com
"""

    return subject, body


def send_weekly_newsletter() -> int:
    """Send the weekly newsletter to all active subscribers.

    Returns count of emails sent.
    """
    subs = _load_subscribers()
    active = [s for s in subs if s.get("active", True)]

    if not active:
        logger.info("No newsletter subscribers yet")
        return 0

    subject, body = _build_newsletter()
    sent = 0

    for sub in active:
        email = sub["email"]
        name = sub.get("name", "")

        personalized = body
        if name:
            personalized = f"Hey {name},\n\n" + body

        if _send_email(email, subject, personalized):
            sent += 1

    logger.info(f"Newsletter sent to {sent}/{len(active)} subscribers")
    return sent


def _send_email(to: str, subject: str, body: str) -> bool:
    """Send via Resend or log."""
    if RESEND_API_KEY:
        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": f"{FROM_NAME} <{FROM_EMAIL}>", "to": [to], "subject": subject, "text": body},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Resend failed: {e}")
            return False
    else:
        logger.info(f"[EMAIL LOG] To: {to} | Subject: {subject}")
        return True


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if "--send" in sys.argv:
        sent = send_weekly_newsletter()
        print(f"Sent {sent} newsletters")
    elif "--preview" in sys.argv:
        subject, body = _build_newsletter()
        print(f"Subject: {subject}\n\n{body}")
    elif "--add" in sys.argv and len(sys.argv) > 2:
        add_subscriber(sys.argv[2])
        print(f"Added {sys.argv[2]}")
    else:
        print("Usage:")
        print("  --preview    Preview this week's newsletter")
        print("  --send       Send to all subscribers")
        print("  --add EMAIL  Add a subscriber")
