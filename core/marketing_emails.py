"""
Automated marketing email system for Archive Arbitrage.

Sends:
- Welcome email when someone subscribes via landing page
- Weekly market report every Monday (top deals, trending brands, pricing shifts)

Uses Resend API (same as onboarding.py).
Run weekly: python -m core.marketing_emails --weekly
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("marketing_emails")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("ONBOARDING_FROM_EMAIL", "deals@archivearbitrage.com")
FROM_NAME = os.getenv("ONBOARDING_FROM_NAME", "Archive Arbitrage")
APP_URL = os.getenv("APP_URL", "https://archivearbitrage.com")
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "archive.db"


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def _send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via Resend API."""
    if not RESEND_API_KEY:
        logger.info(f"[EMAIL LOG] To: {to} | Subject: {subject} | Body: {body[:200]}...")
        return True

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{FROM_NAME} <{FROM_EMAIL}>",
                "to": [to],
                "subject": subject,
                "html": body,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"Email sent: {subject} -> {to}")
            return True
        else:
            logger.warning(f"Resend error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Email send failed: {e}")
    return False


def _get_subscribers() -> list[dict]:
    """Get all active email subscribers."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM email_subscribers WHERE status='active'")
        rows = [dict(r) for r in c.fetchall()]
    except Exception:
        rows = []
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Welcome email (sent on subscribe)
# ---------------------------------------------------------------------------

def send_welcome_email(email: str) -> bool:
    """Send welcome email to new subscriber."""
    subject = "Welcome to Archive Arbitrage"
    body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #e5e5e5; background: #0a0a0a; padding: 40px 24px;">
        <h1 style="font-size: 24px; font-weight: 700; margin-bottom: 16px; color: #f5f5f5;">You're on the list.</h1>
        <p style="color: #a3a3a3; line-height: 1.7; margin-bottom: 24px;">
            Every Monday you'll get our free market report: top deals from last week,
            which brands are trending, and pricing shifts across platforms.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; margin-bottom: 24px;">
            Want real-time deal alerts instead of a weekly summary? Our subscribers get
            20-40+ verified deals pushed to Telegram every week — with comp data, auth
            scores, and direct links to buy.
        </p>
        <a href="{APP_URL}" style="display: inline-block; padding: 14px 28px; background: #f5f5f5; color: #0a0a0a; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px;">
            Start Free Trial
        </a>
        <p style="color: #555; font-size: 12px; margin-top: 32px;">
            $39/mo after 7-day trial. Cancel anytime.
        </p>
        <div style="background: #111; border: 1px solid #222; border-radius: 8px; padding: 20px; margin-top: 32px; text-align: center;">
            <p style="color: #d4a853; font-size: 13px; font-weight: 600; margin-bottom: 6px;">Know someone who flips?</p>
            <p style="color: #737373; font-size: 12px; margin-bottom: 12px;">Share your link — you both get a free week when they sign up.</p>
            <a href="{APP_URL}/refer" style="color: #d4a853; font-size: 12px; text-decoration: underline;">Get your referral link</a>
        </div>
        <hr style="border: none; border-top: 1px solid #222; margin: 32px 0;">
        <p style="color: #444; font-size: 11px;">
            <a href="{APP_URL}/api/unsubscribe?email={email}" style="color: #444;">Unsubscribe</a>
        </p>
    </div>
    """
    return _send_email(email, subject, body)


# ---------------------------------------------------------------------------
# Weekly market report
# ---------------------------------------------------------------------------

def _get_weekly_stats() -> dict:
    """Pull deal stats from the past 7 days."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    # Total deals found
    try:
        c.execute("SELECT COUNT(*) as cnt FROM items WHERE grade IN ('A','B') AND created_at >= ?", (week_ago,))
        total_deals = c.fetchone()["cnt"]
    except Exception:
        total_deals = 0

    # Total profit opportunity
    try:
        c.execute("""
            SELECT COALESCE(SUM(exact_profit), 0) as total_profit,
                   COALESCE(MAX(exact_profit), 0) as best_profit
            FROM items WHERE grade IN ('A','B') AND created_at >= ? AND exact_profit > 0
        """, (week_ago,))
        row = c.fetchone()
        total_profit = row["total_profit"]
        best_profit = row["best_profit"]
    except Exception:
        total_profit = 0
        best_profit = 0

    # Top brands
    try:
        c.execute("""
            SELECT brand, COUNT(*) as cnt FROM items
            WHERE grade IN ('A','B') AND created_at >= ? AND brand IS NOT NULL
            GROUP BY brand ORDER BY cnt DESC LIMIT 5
        """, (week_ago,))
        top_brands = [(r["brand"], r["cnt"]) for r in c.fetchall()]
    except Exception:
        top_brands = []

    # Best individual deals
    try:
        c.execute("""
            SELECT brand, title, source_price, market_price, exact_profit
            FROM items WHERE grade IN ('A','B') AND created_at >= ? AND exact_profit > 0
            ORDER BY exact_profit DESC LIMIT 3
        """, (week_ago,))
        best_deals = [dict(r) for r in c.fetchall()]
    except Exception:
        best_deals = []

    conn.close()

    return {
        "total_deals": total_deals,
        "total_profit": total_profit,
        "best_profit": best_profit,
        "top_brands": top_brands,
        "best_deals": best_deals,
        "date_range": f"{(datetime.now() - timedelta(days=7)).strftime('%b %d')} - {datetime.now().strftime('%b %d')}",
    }


def _build_weekly_report(stats: dict) -> tuple[str, str]:
    """Build the weekly market report email."""
    subject = f"Weekly Market Report: ${stats['total_profit']:,.0f} in deals found ({stats['date_range']})"

    brands_html = ""
    for brand, cnt in stats["top_brands"]:
        brands_html += f'<tr><td style="padding:6px 0; color:#a3a3a3;">{brand}</td><td style="padding:6px 0; color:#f5f5f5; text-align:right;">{cnt} deals</td></tr>'

    deals_html = ""
    for deal in stats["best_deals"]:
        profit = deal.get("exact_profit", 0)
        deals_html += f"""
        <div style="padding:12px 0; border-bottom:1px solid #222;">
            <div style="color:#d4a853; font-size:12px; font-weight:600;">{deal.get('brand', '')}</div>
            <div style="color:#a3a3a3; font-size:13px;">{deal.get('title', '')}</div>
            <div style="margin-top:4px;">
                <span style="color:#737373; font-size:13px;">Buy: ${deal.get('source_price', 0):,.0f}</span>
                <span style="color:#737373; font-size:13px; margin:0 8px;">&rarr;</span>
                <span style="color:#22c55e; font-size:13px; font-weight:600;">+${profit:,.0f}</span>
            </div>
        </div>
        """

    body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #e5e5e5; background: #0a0a0a; padding: 40px 24px;">
        <div style="font-size: 14px; color: #737373; margin-bottom: 8px;">{stats['date_range']}</div>
        <h1 style="font-size: 22px; font-weight: 700; margin-bottom: 24px; color: #f5f5f5;">Weekly Market Report</h1>

        <div style="display: flex; gap: 16px; margin-bottom: 32px;">
            <div style="flex:1; background:#111; border:1px solid #222; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:24px; font-weight:800; color:#f5f5f5;">{stats['total_deals']}</div>
                <div style="font-size:11px; color:#737373; text-transform:uppercase;">Deals Found</div>
            </div>
            <div style="flex:1; background:#111; border:1px solid #222; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:24px; font-weight:800; color:#22c55e;">${stats['total_profit']:,.0f}</div>
                <div style="font-size:11px; color:#737373; text-transform:uppercase;">Total Profit</div>
            </div>
            <div style="flex:1; background:#111; border:1px solid #222; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:24px; font-weight:800; color:#d4a853;">${stats['best_profit']:,.0f}</div>
                <div style="font-size:11px; color:#737373; text-transform:uppercase;">Best Deal</div>
            </div>
        </div>

        <h2 style="font-size:16px; font-weight:600; margin-bottom:12px; color:#f5f5f5;">Top Brands This Week</h2>
        <table style="width:100%; margin-bottom:32px;">{brands_html}</table>

        <h2 style="font-size:16px; font-weight:600; margin-bottom:12px; color:#f5f5f5;">Best Deals</h2>
        <div style="margin-bottom:32px;">{deals_html}</div>

        <p style="color:#a3a3a3; font-size:14px; line-height:1.7; margin-bottom:24px;">
            These are just the highlights. Subscribers got all {stats['total_deals']} deals in real-time
            via Telegram — with comp data, auth scores, and direct links to buy.
        </p>

        <div style="text-align:center; margin:32px 0;">
            <a href="{APP_URL}" style="display:inline-block; padding:14px 32px; background:#f5f5f5; color:#0a0a0a; border-radius:8px; text-decoration:none; font-weight:700; font-size:15px;">
                Get Real-Time Alerts
            </a>
            <p style="color:#555; font-size:12px; margin-top:8px;">$39/mo &middot; 7-day free trial &middot; Cancel anytime</p>
        </div>

        <div style="background:#111; border:1px solid #222; border-radius:8px; padding:20px; margin:32px 0; text-align:center;">
            <p style="color:#d4a853; font-size:13px; font-weight:600; margin-bottom:6px;">Know someone who flips?</p>
            <p style="color:#737373; font-size:12px; margin-bottom:12px;">Share your link — you both get a free week when they sign up.</p>
            <a href="{APP_URL}/refer" style="color:#d4a853; font-size:12px; text-decoration:underline;">Get your referral link</a>
        </div>

        <hr style="border:none; border-top:1px solid #222; margin:32px 0;">
        <p style="color:#444; font-size:11px;">
            You signed up for the free weekly market report at archivearbitrage.com<br>
            <a href="{APP_URL}/api/unsubscribe?email={{{{email}}}}" style="color:#444;">Unsubscribe</a>
        </p>
    </div>
    """
    return subject, body


def send_weekly_report() -> int:
    """Send weekly market report to all active subscribers. Returns count sent."""
    stats = _get_weekly_stats()

    if stats["total_deals"] == 0:
        logger.info("No deals this week — skipping weekly report")
        return 0

    subject, body_template = _build_weekly_report(stats)
    subscribers = _get_subscribers()
    sent = 0

    for sub in subscribers:
        email = sub["email"]
        body = body_template.replace("{{email}}", email)
        if _send_email(email, subject, body):
            sent += 1

    logger.info(f"Weekly report sent to {sent}/{len(subscribers)} subscribers")
    return sent


# ---------------------------------------------------------------------------
# Prospect nurture drip (for newsletter signups who haven't converted)
# ---------------------------------------------------------------------------

NURTURE_STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "nurture_state.json"

NURTURE_SEQUENCE = [
    {"day": 2, "email_fn": "nurture_social_proof", "sent_key": "social_proof_sent"},
    {"day": 5, "email_fn": "nurture_conversion", "sent_key": "conversion_sent"},
]


def _load_nurture_state() -> dict:
    try:
        if NURTURE_STATE_FILE.exists():
            return json.loads(NURTURE_STATE_FILE.read_text())
    except Exception:
        pass
    return {"prospects": {}}


def _save_nurture_state(state: dict) -> None:
    NURTURE_STATE_FILE.write_text(json.dumps(state, indent=2))


def register_prospect(email: str) -> None:
    """Register a newsletter subscriber for the nurture drip.

    Called from /api/subscribe when someone enters their email on the landing page.
    """
    state = _load_nurture_state()
    prospects = state.setdefault("prospects", {})

    if email in prospects:
        return  # Already registered

    prospects[email] = {
        "email": email,
        "registered_at": datetime.now().isoformat(),
        "social_proof_sent": False,
        "conversion_sent": False,
    }
    _save_nurture_state(state)
    logger.info(f"Registered {email} for prospect nurture drip")


def unregister_prospect(email: str) -> None:
    """Remove a prospect from nurture drip (e.g. when they convert to paid)."""
    state = _load_nurture_state()
    if email in state.get("prospects", {}):
        del state["prospects"][email]
        _save_nurture_state(state)


def _nurture_social_proof_email() -> tuple[str, str]:
    """Day 2: Show what subscribers saw this week."""
    stats = _get_weekly_stats()
    subject = f"This week's deals: ${stats['total_profit']:,.0f} in profit found"
    body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #e5e5e5; background: #0a0a0a; padding: 40px 24px;">
        <h1 style="font-size: 22px; font-weight: 700; margin-bottom: 16px; color: #f5f5f5;">Here's what subscribers saw this week.</h1>
        <p style="color: #a3a3a3; line-height: 1.7; margin-bottom: 24px;">
            While you were reading about deals, our subscribers were buying them.
        </p>

        <div style="background: #111; border: 1px solid #222; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <div style="font-size: 32px; font-weight: 800; color: #22c55e; margin-bottom: 4px;">{stats['total_deals']} deals</div>
            <div style="color: #737373; font-size: 13px;">pushed to subscriber phones in real-time this week</div>
        </div>

        <div style="background: #111; border: 1px solid #222; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <div style="font-size: 32px; font-weight: 800; color: #d4a853; margin-bottom: 4px;">${stats['best_profit']:,.0f}</div>
            <div style="color: #737373; font-size: 13px;">best single deal profit opportunity</div>
        </div>

        <p style="color: #a3a3a3; line-height: 1.7; margin-bottom: 24px;">
            Every alert included the exact sold comp data, authentication score, and a direct
            link to buy. By the time most people find these deals manually, they're already sold.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}" style="display: inline-block; padding: 14px 28px; background: #f5f5f5; color: #0a0a0a; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px;">
                Try It Free for 7 Days
            </a>
            <p style="color: #555; font-size: 12px; margin-top: 8px;">$39/mo after trial. Cancel anytime.</p>
        </div>

        <hr style="border: none; border-top: 1px solid #222; margin: 32px 0;">
        <p style="color: #444; font-size: 11px;">
            <a href="{APP_URL}/api/unsubscribe?email={{{{email}}}}" style="color: #444;">Unsubscribe</a>
        </p>
    </div>
    """
    return subject, body


def _nurture_conversion_email() -> tuple[str, str]:
    """Day 5: Conversion push with ROI math."""
    subject = "One flip pays for 6+ months"
    body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #e5e5e5; background: #0a0a0a; padding: 40px 24px;">
        <h1 style="font-size: 22px; font-weight: 700; margin-bottom: 16px; color: #f5f5f5;">The math is simple.</h1>

        <div style="background: #111; border: 1px solid #222; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #a3a3a3; font-size: 14px;">Subscription</td>
                    <td style="padding: 8px 0; color: #f5f5f5; font-size: 14px; text-align: right;">$39/mo</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #a3a3a3; font-size: 14px;">Average deal profit</td>
                    <td style="padding: 8px 0; color: #22c55e; font-size: 14px; text-align: right; font-weight: 600;">$370</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #a3a3a3; font-size: 14px;">ROI per flip</td>
                    <td style="padding: 8px 0; color: #d4a853; font-size: 14px; text-align: right; font-weight: 700;">9.5x</td>
                </tr>
                <tr style="border-top: 1px solid #333;">
                    <td style="padding: 12px 0 0; color: #a3a3a3; font-size: 14px;">Deals sent per week</td>
                    <td style="padding: 12px 0 0; color: #f5f5f5; font-size: 14px; text-align: right;">20-40+</td>
                </tr>
            </table>
        </div>

        <p style="color: #a3a3a3; line-height: 1.7; margin-bottom: 24px;">
            You don't need to buy every deal. One good flip per month covers the subscription
            for half a year. Our system does the hard part — scanning 7 platforms 24/7 and
            pricing everything against real Grailed sold comps.
        </p>

        <p style="color: #a3a3a3; line-height: 1.7; margin-bottom: 24px;">
            The free trial is 7 days. No card required. See real deals with real comp data
            before you commit.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}" style="display: inline-block; padding: 16px 32px; background: #22c55e; color: white; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 15px;">
                Start Free Trial
            </a>
        </div>

        <hr style="border: none; border-top: 1px solid #222; margin: 32px 0;">
        <p style="color: #444; font-size: 11px;">
            <a href="{APP_URL}/api/unsubscribe?email={{{{email}}}}" style="color: #444;">Unsubscribe</a>
        </p>
    </div>
    """
    return subject, body


def run_nurture_check() -> int:
    """Check all prospects and send due nurture emails.

    Call on a schedule (same cron as run_drip_check).
    Returns the number of emails sent.
    """
    state = _load_nurture_state()
    prospects = state.get("prospects", {})
    sent_count = 0

    for email, data in list(prospects.items()):
        registered_at = datetime.fromisoformat(data["registered_at"])
        days_since = (datetime.now() - registered_at).days

        for step in NURTURE_SEQUENCE:
            if days_since >= step["day"] and not data.get(step["sent_key"], False):
                if step["email_fn"] == "nurture_social_proof":
                    subject, body = _nurture_social_proof_email()
                elif step["email_fn"] == "nurture_conversion":
                    subject, body = _nurture_conversion_email()
                else:
                    continue

                body = body.replace("{{email}}", email)
                if _send_email(email, subject, body):
                    data[step["sent_key"]] = True
                    sent_count += 1

    _save_nurture_state(state)
    return sent_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Marketing email system")
    parser.add_argument("--weekly", action="store_true", help="Send weekly market report")
    parser.add_argument("--nurture", action="store_true", help="Run prospect nurture drip check")
    parser.add_argument("--test", help="Send test welcome email to this address")
    parser.add_argument("--stats", action="store_true", help="Show weekly stats without sending")
    parser.add_argument("--count", action="store_true", help="Show subscriber count")
    args = parser.parse_args()

    if args.weekly:
        sent = send_weekly_report()
        print(f"Weekly report sent to {sent} subscribers")
    elif args.nurture:
        sent = run_nurture_check()
        print(f"Nurture check complete: {sent} emails sent")
    elif args.test:
        ok = send_welcome_email(args.test)
        print(f"Welcome email {'sent' if ok else 'failed'}: {args.test}")
    elif args.stats:
        stats = _get_weekly_stats()
        print(f"Weekly stats ({stats['date_range']}):")
        print(f"  Deals: {stats['total_deals']}")
        print(f"  Total profit: ${stats['total_profit']:,.0f}")
        print(f"  Best deal: ${stats['best_profit']:,.0f}")
        for brand, cnt in stats["top_brands"]:
            print(f"  {brand}: {cnt} deals")
    elif args.count:
        subs = _get_subscribers()
        print(f"Active subscribers: {len(subs)}")
    else:
        parser.print_help()
