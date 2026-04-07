#!/usr/bin/env python3
"""
Discord Webhook Alerts for Archive Arbitrage.

Sends deal alerts to a Discord channel via webhook.
Formats deals as rich embeds with images, pricing, and auth info.

Setup:
    1. In Discord: Create webhooks for #beginner-signals, #pro-signals, #whale-signals
    2. Add to .env:
        DISCORD_WEBHOOK_BEGINNER=https://discord.com/api/webhooks/...
        DISCORD_WEBHOOK_PRO=https://discord.com/api/webhooks/...
        DISCORD_WEBHOOK_WHALE=https://discord.com/api/webhooks/...
    3. Deals use nested entitlement: beginner→all channels, pro→pro+whale, whale→whale only
"""

import asyncio
import os
import re
import logging
import time
from typing import Optional, Dict, Any, List

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("discord_alerts")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Tier-specific webhook URLs (nested entitlement: deals fan out to qualifying channels)
DISCORD_WEBHOOK_BEGINNER = os.getenv("DISCORD_WEBHOOK_BEGINNER", "")
DISCORD_WEBHOOK_PRO = os.getenv("DISCORD_WEBHOOK_PRO", "")
DISCORD_WEBHOOK_WHALE = os.getenv("DISCORD_WEBHOOK_WHALE", "")

# Free deals channel — delayed public preview to drive conversions
DISCORD_WEBHOOK_FREE = os.getenv("DISCORD_WEBHOOK_FREE", "")
FREE_DEAL_DELAY_SECONDS = int(os.getenv("FREE_DEAL_DELAY_SECONDS", "2700"))  # 45 minutes

DISCORD_ENABLED = bool(DISCORD_WEBHOOK_BEGINNER or DISCORD_WEBHOOK_PRO or DISCORD_WEBHOOK_WHALE)

# Tier → webhook mapping
TIER_WEBHOOK_MAP = {
    "beginner": DISCORD_WEBHOOK_BEGINNER,
    "pro": DISCORD_WEBHOOK_PRO,
    "whale": DISCORD_WEBHOOK_WHALE,
}

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
            "value": f"{gap * 100:.0f}%",
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
    tier: str = "beginner",
    tiers: Optional[List[str]] = None,
) -> bool:
    """Send a deal alert to Discord channels using nested entitlement routing.

    Deals fan out to all channels at or above their minimum tier:
      beginner deal → beginner + pro + whale
      pro deal      → pro + whale
      whale deal    → whale only

    Args:
        tier: fallback tier label
        tiers: list of channel tiers to post to (from classify_discord_tiers)

    Returns True if at least one channel succeeded.
    """
    if not DISCORD_ENABLED:
        return False

    # Determine target channels
    target_tiers = tiers if tiers else [tier or "beginner"]
    # Map old "big_baller" references
    target_tiers = ["whale" if t == "big_baller" else t for t in target_tiers]

    if not target_tiers:
        target_tiers = ["beginner"]

    tier_labels = {"beginner": "beginner-signals", "pro": "pro-signals", "whale": "whale-signals"}
    any_sent = False

    async with httpx.AsyncClient(timeout=10) as client:
        for target_tier in target_tiers:
            webhook_url = TIER_WEBHOOK_MAP.get(target_tier, "")
            if not webhook_url:
                logger.warning(f"No webhook configured for tier '{target_tier}'")
                continue

            embed = build_embed(item, message, fire_level, signals, auth_result)
            channel_label = tier_labels.get(target_tier, target_tier)
            if signals:
                score = getattr(signals, "quality_score", 0)
                embed["footer"] = {"text": f"Score: {score:.0f}/100 | #{channel_label} | Archive Arbitrage"}
            else:
                embed["footer"] = {"text": f"#{channel_label} | Archive Arbitrage"}

            payload = {"username": BOT_NAME, "embeds": [embed]}

            try:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    logger.info(f"✅ Discord alert sent to #{channel_label}: {item.title[:50] if hasattr(item, 'title') else 'deal'}")
                    any_sent = True
                else:
                    logger.warning(f"Discord webhook returned {resp.status_code} for #{channel_label}: {resp.text[:200]}")
            except httpx.ConnectError as e:
                logger.error(f"Discord webhook ConnectError ({channel_label}): {e}")
            except httpx.TimeoutException as e:
                logger.error(f"Discord webhook timeout ({channel_label}): {e}")
            except Exception as e:
                logger.error(f"Discord webhook error ({channel_label}): {type(e).__name__}: {e}")

    return any_sent


async def send_discord_message(text: str, webhook_url: str = "") -> bool:
    """Send a plain text message to Discord (for status updates, etc.)."""
    url = webhook_url or DISCORD_WEBHOOK_BEGINNER
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


# ---------------------------------------------------------------------------
# Free Deals Channel — delayed, no buy links, CTA to subscribe
# ---------------------------------------------------------------------------

# In-memory queue of deals waiting to be posted to the free channel
_free_deal_queue: List[Dict[str, Any]] = []


def build_free_embed(
    item: Any,
    fire_level: int = 0,
    signals: Any = None,
) -> Dict[str, Any]:
    """Build a Discord embed for the free deals channel.

    Key differences from paid embeds:
    - No direct buy link (URL points to signup page)
    - Adds a subscribe CTA
    - Shows the deal is delayed
    """
    title = getattr(item, "title", "Deal Alert") or "Deal Alert"
    brand = getattr(item, "brand", "") or ""
    price = getattr(item, "price", 0) or 0
    source = getattr(item, "source", "") or ""
    size = getattr(item, "size", "") or ""

    fire_str = "🔥" * fire_level if fire_level > 0 else ""

    embed: Dict[str, Any] = {
        "title": f"{fire_str} {title[:200]}".strip(),
        "color": EMBED_COLORS.get(fire_level, 0x808080),
        "url": "https://app.archivearbitrage.com/signup",
    }

    fields: List[Dict[str, Any]] = []

    fields.append({
        "name": "💰 Listed Price",
        "value": f"**${price:,.0f}**",
        "inline": True,
    })

    if signals:
        gap = getattr(signals, "gap_percent", 0)
        profit = getattr(signals, "profit_estimate", 0)
        fields.append({
            "name": "📉 Below Market",
            "value": f"{gap * 100:.0f}%",
            "inline": True,
        })
        fields.append({
            "name": "💵 Est. Profit",
            "value": f"**${profit:,.0f}**",
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

    # Subscribe CTA field
    fields.append({
        "name": "⚡ Want real-time alerts?",
        "value": "Subscribers got this deal **45 min ago** with a direct buy link.\n[Start Free Trial →](https://app.archivearbitrage.com/signup)",
        "inline": False,
    })

    embed["fields"] = fields

    # Thumbnail from item images
    images = getattr(item, "images", []) or []
    if images and images[0]:
        embed["thumbnail"] = {"url": images[0]}

    embed["footer"] = {"text": "⏱️ Delayed 45 min | #free-deals | Archive Arbitrage"}

    return embed


def queue_free_deal(item: Any, fire_level: int = 0, signals: Any = None):
    """Queue a deal for delayed posting to the free channel."""
    if not DISCORD_WEBHOOK_FREE:
        return

    _free_deal_queue.append({
        "item": item,
        "fire_level": fire_level,
        "signals": signals,
        "send_at": time.time() + FREE_DEAL_DELAY_SECONDS,
    })
    logger.debug(f"Queued free deal: {getattr(item, 'title', '')[:50]} (sends in {FREE_DEAL_DELAY_SECONDS}s)")


async def flush_free_deals():
    """Send any queued free deals that have passed their delay window."""
    if not DISCORD_WEBHOOK_FREE or not _free_deal_queue:
        return

    now = time.time()
    ready = [d for d in _free_deal_queue if d["send_at"] <= now]

    if not ready:
        return

    sent_count = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for deal in ready:
            embed = build_free_embed(
                deal["item"],
                deal["fire_level"],
                deal["signals"],
            )
            payload = {"username": "Archive Arbitrage — Free Deals", "embeds": [embed]}

            try:
                resp = await client.post(DISCORD_WEBHOOK_FREE, json=payload)
                if resp.status_code in (200, 204):
                    sent_count += 1
                else:
                    logger.warning(f"Free deal webhook returned {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.error(f"Free deal webhook error: {e}")

            _free_deal_queue.remove(deal)

            # Rate limit: Discord allows 30 requests per minute per webhook
            await asyncio.sleep(2)

    if sent_count:
        logger.info(f"📢 Posted {sent_count} deal(s) to #free-deals")
