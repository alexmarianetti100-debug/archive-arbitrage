#!/usr/bin/env python3
"""
Discord Webhook Alerts for Archive Arbitrage.

Sends deal alerts to a Discord channel via webhook.
Formats deals as rich embeds with images, pricing, and auth info.

Setup:
    1. In Discord: Server Settings → Integrations → Webhooks → New Webhook
    2. Copy the webhook URL
    3. Add to .env: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
    4. Optional: DISCORD_WEBHOOK_URL_2 for a second channel
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("discord_alerts")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL_2 = os.getenv("DISCORD_WEBHOOK_URL_2", "")  # Optional second channel
DISCORD_ENABLED = bool(DISCORD_WEBHOOK_URL)

# Embed colors by fire level
EMBED_COLORS = {
    3: 0xFF4500,   # 🔥🔥🔥 — red-orange
    2: 0xFF8C00,   # 🔥🔥 — dark orange
    1: 0xFFD700,   # 🔥 — gold
    0: 0x808080,   # no fire — gray
}

BOT_NAME = "Archive Arbitrage"
BOT_AVATAR = "https://i.imgur.com/placeholder.png"  # Update with actual avatar


def _strip_html(text: str) -> str:
    """Strip HTML tags and convert to Discord markdown."""
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text)
    text = re.sub(r"<a href=\"(.*?)\">(.*?)</a>", r"[\2](\1)", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def build_embed(
    item: Any,
    message: str,
    fire_level: int = 0,
    signals: Any = None,
    auth_result: Any = None,
) -> Dict[str, Any]:
    """Build a Discord embed from a deal alert.

    Args:
        item: ScrapedItem with title, price, brand, url, images, etc.
        message: The formatted alert message (HTML from Telegram format).
        fire_level: 0-3 fire rating.
        signals: DealSignals object (optional).
        auth_result: AuthResult object (optional).

    Returns:
        Discord embed dict ready for webhook payload.
    """
    title = getattr(item, "title", "Deal Alert") or "Deal Alert"
    brand = getattr(item, "brand", "") or ""
    price = getattr(item, "price", 0) or 0
    url = getattr(item, "url", "") or ""
    source = getattr(item, "source", "") or ""
    size = getattr(item, "size", "") or ""

    # Fire emoji prefix
    fire_str = "🔥" * fire_level if fire_level > 0 else ""
    score_str = ""
    if signals:
        score = getattr(signals, "quality_score", 0)
        score_str = f" (Score: {score:.0f}/100)"

    # Build embed
    embed: Dict[str, Any] = {
        "title": f"{fire_str} {title[:200]}".strip(),
        "color": EMBED_COLORS.get(fire_level, 0x808080),
    }

    if url:
        embed["url"] = url

    # Fields
    fields: List[Dict[str, Any]] = []

    fields.append({
        "name": "💰 Price",
        "value": f"**${price:,.0f}**",
        "inline": True,
    })

    if signals:
        gap = getattr(signals, "gap_percent", 0)
        profit = getattr(signals, "profit_estimate", 0)
        fields.append({
            "name": "📉 Below Market",
            "value": f"{gap:.0f}%",
            "inline": True,
        })
        fields.append({
            "name": "💵 Est. Profit",
            "value": f"${profit:,.0f}",
            "inline": True,
        })

    if brand:
        fields.append({
            "name": "🏷️ Brand",
            "value": brand,
            "inline": True,
        })

    if size:
        fields.append({
            "name": "📏 Size",
            "value": str(size),
            "inline": True,
        })

    if source:
        fields.append({
            "name": "🌐 Platform",
            "value": source.capitalize(),
            "inline": True,
        })

    # Signal details
    if signals:
        signal_parts = []
        line_name = getattr(signals, "line_name", "")
        season_name = getattr(signals, "season_name", "")
        if line_name and line_name != "Unknown":
            line_mult = getattr(signals, "line_multiplier", 1.0)
            signal_parts.append(f"🏷️ {line_name} ({line_mult:.1f}x)")
        if season_name:
            season_mult = getattr(signals, "season_multiplier", 1.0)
            signal_parts.append(f"📅 {season_name} ({season_mult:.1f}x)")
        if signal_parts:
            fields.append({
                "name": "📊 Signals",
                "value": " | ".join(signal_parts),
                "inline": False,
            })

    # Auth info
    if auth_result:
        confidence = getattr(auth_result, "confidence", 0)
        filled = round(confidence * 5)
        bar = "🟢" * filled + "⚪" * (5 - filled)
        grade = getattr(auth_result, "grade", "?")
        fields.append({
            "name": "🔐 Authenticity",
            "value": f"{bar} {confidence*100:.0f}% — Grade {grade}",
            "inline": False,
        })

    embed["fields"] = fields

    # Score in footer
    if signals:
        score = getattr(signals, "quality_score", 0)
        embed["footer"] = {
            "text": f"Score: {score:.0f}/100 | Archive Arbitrage",
        }
    else:
        embed["footer"] = {"text": "Archive Arbitrage"}

    # Image
    images = getattr(item, "images", []) or []
    if images:
        embed["image"] = {"url": images[0]}

    # Thumbnail (brand logo could go here)
    embed["timestamp"] = __import__("datetime").datetime.utcnow().isoformat()

    return embed


async def send_discord_alert(
    item: Any,
    message: str,
    fire_level: int = 0,
    signals: Any = None,
    auth_result: Any = None,
) -> bool:
    """Send a deal alert to Discord via webhook.

    Returns True if sent successfully.
    """
    if not DISCORD_ENABLED:
        return False

    embed = build_embed(item, message, fire_level, signals, auth_result)

    payload = {
        "username": BOT_NAME,
        "embeds": [embed],
    }

    urls = [DISCORD_WEBHOOK_URL]
    if DISCORD_WEBHOOK_URL_2:
        urls.append(DISCORD_WEBHOOK_URL_2)

    success = False
    async with httpx.AsyncClient(timeout=10) as client:
        for webhook_url in urls:
            try:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    logger.info(f"✅ Discord alert sent: {item.title[:50] if hasattr(item, 'title') else 'deal'}")
                    success = True
                else:
                    logger.warning(f"Discord webhook returned {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.error(f"Discord webhook error: {e}")

    return success


async def send_discord_message(text: str, webhook_url: str = "") -> bool:
    """Send a plain text message to Discord (for status updates, etc.)."""
    url = webhook_url or DISCORD_WEBHOOK_URL
    if not url:
        return False

    payload = {
        "username": BOT_NAME,
        "content": text[:2000],  # Discord limit
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, json=payload)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Discord message error: {e}")
            return False
