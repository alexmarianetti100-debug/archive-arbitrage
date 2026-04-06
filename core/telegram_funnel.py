"""
Free public Telegram channel — delayed deal funnel.

Posts 1-2 deals/day to a PUBLIC Telegram channel, delayed 30-60 minutes
behind subscriber alerts. This is the top-of-funnel growth engine:

1. People discover the free channel (via IG bio, Reddit, word of mouth)
2. They see real deals flowing with real comp data
3. They realize deals sell out before the delayed post arrives
4. They subscribe for real-time access via Whop

The delay is the conversion mechanism — free users see the deal was
already sold by the time they check, proving the value of real-time alerts.

Setup:
    1. Create a PUBLIC Telegram channel (e.g., @archivearbitrage_free)
    2. Add the bot as admin
    3. Set FREE_CHANNEL_ID in .env
    4. Deals auto-post with delay from the pipeline

Usage:
    # Called from gap_hunter.py after a deal is dispatched to subscribers
    await queue_free_channel_deal(item, signals, auth_result)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("telegram_funnel")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Public free channel — set this to your public channel's chat ID
FREE_CHANNEL_ID = os.getenv("TELEGRAM_FREE_CHANNEL_ID", "")

# Delay before posting to free channel (seconds)
# 30 min = 1800, 45 min = 2700, 60 min = 3600
FREE_CHANNEL_DELAY = int(os.getenv("TELEGRAM_FREE_DELAY", "2700"))  # 45 min default

# Max free posts per day (don't flood — scarcity drives conversion)
MAX_FREE_POSTS_PER_DAY = int(os.getenv("TELEGRAM_FREE_MAX_DAILY", "2"))

# Only post the best deals to the free channel
MIN_FIRE_LEVEL_FREE = 2
MIN_PROFIT_FREE = 200

# State
STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "free_channel_state.json"


def _load_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {"today": "", "count": 0, "posted_urls": []}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _check_daily_limit() -> bool:
    state = _load_state()
    today = date.today().isoformat()
    if state.get("today") != today:
        state = {"today": today, "count": 0, "posted_urls": []}
        _save_state(state)
        return True
    return state["count"] < MAX_FREE_POSTS_PER_DAY


def _record_post(source_url: str) -> None:
    state = _load_state()
    today = date.today().isoformat()
    if state.get("today") != today:
        state = {"today": today, "count": 0, "posted_urls": []}
    state["count"] += 1
    state["posted_urls"].append(source_url)
    state["posted_urls"] = state["posted_urls"][-50:]
    _save_state(state)


def _already_posted(source_url: str) -> bool:
    state = _load_state()
    return source_url in state.get("posted_urls", [])


def _format_free_deal_message(
    title: str,
    brand: str,
    price: float,
    market_price: float,
    profit: float,
    gap_percent: float,
    comp_count: int,
    source: str,
    source_url: str,
    fire_level: int = 0,
    auth_confidence: float = 0,
) -> str:
    """Format a deal message for the free public channel.

    Key difference from subscriber alerts: NO direct buy link.
    Instead, CTA drives to Whop for real-time access.
    """
    fire_str = "🔥" * min(fire_level, 3) if fire_level > 0 else ""
    source_label = {
        "grailed": "Grailed", "poshmark": "Poshmark", "ebay": "eBay",
        "depop": "Depop", "mercari": "Mercari", "vinted": "Vinted",
    }.get(source.lower(), source.title())

    # Auth bar
    if auth_confidence > 0:
        filled = round(auth_confidence * 5)
        auth_bar = "🟢" * filled + "⚪" * (5 - filled)
        auth_line = f"🔐 Auth: {auth_bar} {auth_confidence*100:.0f}%"
    else:
        auth_line = ""

    message = (
        f"{fire_str} <b>Deal Alert</b>\n"
        f"\n"
        f"<b>{brand}</b> — {title}\n"
        f"\n"
        f"💰 Listed: <b>${price:,.0f}</b> on {source_label}\n"
        f"📊 Market value: <b>${market_price:,.0f}</b> ({comp_count} sold comps)\n"
        f"📈 <b>{gap_percent*100:.0f}% below market</b>\n"
        f"💵 Est. profit: <b>${profit:,.0f}</b>\n"
    )

    if auth_line:
        message += f"{auth_line}\n"

    message += (
        f"\n"
        f"⏰ <i>This deal was sent to subscribers {FREE_CHANNEL_DELAY // 60} minutes ago.</i>\n"
        f"<i>Most deals at this level sell within 10-15 minutes.</i>\n"
        f"\n"
        f"⚡ Want real-time alerts before they sell out?\n"
        f"→ <b>7-day free trial</b> — link in bio\n"
    )

    return message


async def _send_to_free_channel(text: str, image_url: str = "") -> bool:
    """Send a message to the free public channel."""
    if not FREE_CHANNEL_ID:
        logger.debug("FREE_CHANNEL_ID not set — free channel disabled")
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if image_url:
                # Send with image
                resp = await client.post(
                    f"{TELEGRAM_API}/sendPhoto",
                    json={
                        "chat_id": FREE_CHANNEL_ID,
                        "photo": image_url,
                        "caption": text[:1024],  # Telegram caption limit
                        "parse_mode": "HTML",
                    },
                )
            else:
                resp = await client.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": FREE_CHANNEL_ID,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )

            if resp.status_code == 200 and resp.json().get("ok"):
                return True
            else:
                logger.warning(f"Free channel send failed: {resp.status_code} {resp.text[:200]}")
                return False

    except Exception as e:
        logger.error(f"Free channel send error: {e}")
        return False


async def queue_free_channel_deal(
    item: Any,
    signals: Any = None,
    auth_result: Any = None,
) -> bool:
    """Queue a deal for delayed posting to the free public channel.

    Called from gap_hunter.py after a deal is sent to paying subscribers.
    The deal posts to the free channel after a delay.

    Returns True if the deal was queued for free channel posting.
    """
    if not FREE_CHANNEL_ID:
        return False

    # Extract fields
    fire_level = int(getattr(signals, "fire_level", 0) or 0) if signals else 0
    profit = float(getattr(item, "profit", 0) or getattr(signals, "profit_estimate", 0) or 0)
    source_url = getattr(item, "source_url", "") or getattr(item, "url", "") or ""

    # Qualification check
    if fire_level < MIN_FIRE_LEVEL_FREE and profit < MIN_PROFIT_FREE:
        return False

    if not _check_daily_limit():
        logger.debug("Free channel daily limit reached")
        return False

    if _already_posted(source_url):
        return False

    # Build message
    title = getattr(item, "title", "") or ""
    brand = getattr(item, "brand", "") or ""
    price = float(getattr(item, "price", 0) or getattr(item, "source_price", 0) or 0)
    market_price = float(getattr(item, "market_price", 0) or 0)
    gap_percent = float(getattr(signals, "gap_percent", 0) or getattr(item, "margin_percent", 0) or 0)
    comp_count = int(getattr(signals, "comp_count", 0) or getattr(item, "comps_count", 0) or 0)
    source = getattr(item, "source", "") or ""
    auth_conf = float(getattr(auth_result, "confidence", 0) or 0) if auth_result else 0
    image_url = ""
    images = getattr(item, "images", []) or []
    if images:
        image_url = images[0]
    elif getattr(item, "image_url", None):
        image_url = item.image_url

    message = _format_free_deal_message(
        title=title,
        brand=brand,
        price=price,
        market_price=market_price,
        profit=profit,
        gap_percent=gap_percent,
        comp_count=comp_count,
        source=source,
        source_url=source_url,
        fire_level=fire_level,
        auth_confidence=auth_conf,
    )

    # Schedule delayed send
    async def _delayed_send():
        await asyncio.sleep(FREE_CHANNEL_DELAY)
        # Re-check daily limit (may have been hit during delay)
        if not _check_daily_limit():
            return
        ok = await _send_to_free_channel(message, image_url=image_url)
        if ok:
            _record_post(source_url)
            logger.info(f"Free channel: posted {brand} deal (delayed {FREE_CHANNEL_DELAY//60}min)")

    # Fire and forget — don't block the pipeline
    asyncio.create_task(_delayed_send())
    logger.info(f"Free channel: queued {brand} deal for {FREE_CHANNEL_DELAY//60}min delay")
    return True
