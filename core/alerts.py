#!/usr/bin/env python3
"""
Discord Alert System for Archive Arbitrage.

Sends rich embed notifications to Discord when profitable items are found.

Features:
- Rich embeds with item image, prices, margin, source link
- Configurable thresholds (min profit, min margin, brands)
- Season/collection detection badges
- Auction urgency indicators
- Daily summary digests
- Rate limiting to avoid Discord spam

Usage:
    # Send a single item alert
    from alerts import AlertService
    alerts = AlertService()
    await alerts.send_item_alert(item, price_info)

    # Send daily summary
    await alerts.send_daily_summary()
"""

import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

# Discord webhook URL
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Alert thresholds — configurable via .env, sensible defaults
DEFAULT_MIN_PROFIT = float(os.getenv("ALERT_MIN_PROFIT", "150"))
DEFAULT_MIN_MARGIN = float(os.getenv("ALERT_MIN_MARGIN", "0.40"))
FIRE_PROFIT_THRESHOLD = float(os.getenv("ALERT_FIRE_PROFIT", "300"))
GRAIL_PROFIT_THRESHOLD = float(os.getenv("ALERT_GRAIL_PROFIT", "500"))

# Rate limiting — configurable via .env
MAX_ALERTS_PER_HOUR = int(os.getenv("ALERT_MAX_PER_HOUR", "15"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECS", "30"))

# Brand watchlist — comma-separated in .env, empty = all brands
_watchlist_raw = os.getenv("ALERT_BRAND_WATCHLIST", "")
DEFAULT_BRAND_WATCHLIST = [b.strip().lower() for b in _watchlist_raw.split(",") if b.strip()]

# State file for tracking sent alerts
STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "alert_state.json")


@dataclass
class AlertItem:
    """Item data for alert."""
    title: str
    brand: str
    source: str
    source_url: str
    source_price: float
    market_price: float
    recommended_price: float
    profit: float
    margin_percent: float
    image_url: Optional[str] = None
    size: Optional[str] = None
    season_name: Optional[str] = None
    season_multiplier: float = 1.0
    comps_count: int = 0
    is_auction: bool = False
    time_left_hours: Optional[float] = None
    bid_count: int = 0
    demand_level: str = "unknown"  # hot, warm, cold, dead
    demand_score: float = 0.0



# Optional: Whop integration for cross-posting profitable deals
try:
    from .whop_alerts import send_whop_alert, format_whop_deal_content  # type: ignore
except Exception:
    # If the module is unavailable or import fails, define fallbacks so alerts still work
    def send_whop_alert(*args, **kwargs):
        return False
    def format_whop_deal_content(*args, **kwargs):
        return ("Whop Post", "Content placeholder")
class AlertService:
    """Send alerts to Discord via webhooks."""

    def __init__(
        self,
        webhook_url: str = None,
        min_profit: float = DEFAULT_MIN_PROFIT,
        min_margin: float = DEFAULT_MIN_MARGIN,
        brand_watchlist: List[str] = None,
    ):
        self.webhook_url = webhook_url or WEBHOOK_URL
        self.min_profit = min_profit
        self.min_margin = min_margin
        # Use explicit watchlist if passed, otherwise fall back to .env list
        self.brand_watchlist = [b.lower() for b in (brand_watchlist or DEFAULT_BRAND_WATCHLIST)]
        self._state = self._load_state()
        self._client = None

    def _load_state(self) -> dict:
        """Load alert state (sent alerts, counts)."""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "sent_ids": [],       # Recently sent item IDs (avoid duplicates)
            "hourly_count": 0,
            "hourly_reset": None,
            "last_alert_time": None,
            "daily_stats": {
                "items_found": 0,
                "total_profit_potential": 0,
                "top_brands": {},
            },
        }

    def _save_state(self):
        """Save alert state."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(self._state, f, indent=2, default=str)
        except Exception:
            pass

    def _check_rate_limit(self) -> bool:
        """Check if we can send another alert."""
        now = datetime.utcnow()

        # Reset hourly counter
        reset_time = self._state.get("hourly_reset")
        if reset_time:
            reset_dt = datetime.fromisoformat(reset_time)
            if now > reset_dt:
                self._state["hourly_count"] = 0
                self._state["hourly_reset"] = (now + timedelta(hours=1)).isoformat()
        else:
            self._state["hourly_reset"] = (now + timedelta(hours=1)).isoformat()

        # Check hourly limit
        if self._state["hourly_count"] >= MAX_ALERTS_PER_HOUR:
            return False

        # Check cooldown
        last_time = self._state.get("last_alert_time")
        if last_time:
            last_dt = datetime.fromisoformat(last_time)
            if (now - last_dt).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return False

        return True

    def _is_duplicate(self, item_id: str) -> bool:
        """Check if we already sent an alert for this item."""
        return item_id in self._state.get("sent_ids", [])

    def _record_alert(self, item_id: str):
        """Record that we sent an alert."""
        now = datetime.utcnow()
        self._state["hourly_count"] = self._state.get("hourly_count", 0) + 1
        self._state["last_alert_time"] = now.isoformat()

        # Keep last 500 sent IDs
        sent = self._state.get("sent_ids", [])
        sent.append(item_id)
        self._state["sent_ids"] = sent[-500:]

        self._save_state()

    def should_alert(self, item: AlertItem) -> bool:
        """Determine if an item should trigger an alert."""
        # Basic thresholds
        if item.profit < self.min_profit:
            return False
        if item.margin_percent < self.min_margin:
            return False

        # Brand watchlist (if set, only alert for these brands)
        if self.brand_watchlist:
            if item.brand.lower() not in self.brand_watchlist:
                return False

        return True

    def _get_alert_tier(self, item: AlertItem) -> tuple:
        """Get alert tier (emoji, color, label) based on profit level."""
        if item.profit >= GRAIL_PROFIT_THRESHOLD:
            return ("🏆", 0xFFD700, "GRAIL ALERT")  # Gold
        elif item.profit >= FIRE_PROFIT_THRESHOLD:
            return ("🔥", 0xFF4500, "HOT DEAL")  # Orange-red
        else:
            return ("💰", 0x22C55E, "Deal Found")  # Green

    def _build_embed(self, item: AlertItem) -> dict:
        """Build a Discord embed for an item alert."""
        emoji, color, label = self._get_alert_tier(item)

        # Title
        title = f"{emoji} {label}: {item.brand.upper()}"

        # Description
        desc_lines = [f"**{item.title[:100]}**"]

        if item.season_name:
            desc_lines.append(f"🔥 **{item.season_name}** ({item.season_multiplier}x premium)")

        if item.is_auction and item.time_left_hours is not None:
            if item.time_left_hours < 2:
                desc_lines.append(f"⚡ **ENDING IN {item.time_left_hours:.0f}h** — {item.bid_count} bids")
            elif item.time_left_hours < 6:
                desc_lines.append(f"⏰ Ending in {item.time_left_hours:.1f}h — {item.bid_count} bids")
            else:
                desc_lines.append(f"🕐 {item.time_left_hours:.0f}h left — {item.bid_count} bids")

        description = "\n".join(desc_lines)

        # Fields
        fields = [
            {
                "name": "💵 Buy Price",
                "value": f"**${item.source_price:.0f}**\n{item.source}",
                "inline": True,
            },
            {
                "name": "📊 Market Price",
                "value": f"**${item.market_price:.0f}**\n{item.comps_count} comps",
                "inline": True,
            },
            {
                "name": "🎯 Sell At",
                "value": f"**${item.recommended_price:.0f}**",
                "inline": True,
            },
            {
                "name": "💰 Profit",
                "value": f"**${item.profit:.0f}**",
                "inline": True,
            },
            {
                "name": "📈 Margin",
                "value": f"**{item.margin_percent * 100:.0f}%**",
                "inline": True,
            },
        ]

        if item.size:
            fields.append({
                "name": "📐 Size",
                "value": item.size,
                "inline": True,
            })

        # Demand indicator
        demand_emoji = {
            "hot": "🔥 HOT",
            "warm": "🟡 WARM",
            "cold": "🔵 COLD",
            "dead": "💀 DEAD",
            "unknown": "❓",
        }.get(item.demand_level, "❓")
        
        if item.demand_level != "unknown":
            fields.append({
                "name": "📊 Demand",
                "value": f"**{demand_emoji}** ({item.demand_score:.0%})",
                "inline": True,
            })

        # Source link — always visible
        source_label = {
            "poshmark": "Poshmark",
            "grailed": "Grailed",
            "ebay": "eBay",
            "ebay_auction": "eBay Auction",
            "depop": "Depop",
            "mercari": "Mercari",
        }.get(item.source, item.source.title())

        fields.append({
            "name": "🔗 Link",
            "value": f"**[View on {source_label}]({item.source_url})**",
            "inline": False,
        })

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "url": item.source_url,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": f"Archive Arbitrage • {source_label}",
            },
        }

        # Add image if available
        if item.image_url:
            embed["thumbnail"] = {"url": item.image_url}

        return embed

    def _validate_url(self, url: str) -> str:
        """Validate and clean a source URL. Returns empty string if invalid."""
        if not url:
            return ""
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return ""
        # Must be a real marketplace URL, not a placeholder
        valid_domains = [
            "poshmark.com", "grailed.com", "ebay.com", "depop.com",
            "mercari.com", "shopgoodwill.com", "gem.app",
        ]
        if not any(domain in url for domain in valid_domains):
            return ""
        return url

    async def send_item_alert(self, item: AlertItem) -> bool:
        """Send a Discord alert for a profitable item."""
        if not self.webhook_url:
            return False

        # Validate source URL — don't send alerts with broken links
        valid_url = self._validate_url(item.source_url)
        if not valid_url:
            print(f"  ⚠ Skipping alert — invalid source URL: {item.source_url}")
            return False
        item.source_url = valid_url

        # Check if we should alert
        if not self.should_alert(item):
            return False

        # Check rate limit
        if not self._check_rate_limit():
            return False

        # Check duplicate
        item_id = f"{item.source}_{item.source_url}"
        if self._is_duplicate(item_id):
            return False

        # Build and send embed
        embed = self._build_embed(item)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self.webhook_url,
                    json={
                        "embeds": [embed],
                    },
                )

                if resp.status_code in (200, 204):
                    self._record_alert(item_id)
                    # Update daily stats
                    stats = self._state.setdefault("daily_stats", {
                        "items_found": 0,
                        "total_profit_potential": 0,
                        "top_brands": {},
                    })
                    stats["items_found"] = stats.get("items_found", 0) + 1
                    stats["total_profit_potential"] = stats.get("total_profit_potential", 0) + item.profit
                    brands = stats.get("top_brands", {})
                    brands[item.brand] = brands.get(item.brand, 0) + 1
                    stats["top_brands"] = brands
                    self._save_state()
                    return True
                else:
                    print(f"Discord webhook error: {resp.status_code} - {resp.text}")
                    return False

        except Exception as e:
            print(f"Discord alert failed: {e}")
            return False

    async def send_daily_summary(self) -> bool:
        """Send a daily summary of finds to Discord."""
        if not self.webhook_url:
            return False

        stats = self._state.get("daily_stats", {})
        items_found = stats.get("items_found", 0)
        total_profit = stats.get("total_profit_potential", 0)
        top_brands = stats.get("top_brands", {})

        if items_found == 0:
            return False

        # Sort brands by count
        sorted_brands = sorted(top_brands.items(), key=lambda x: -x[1])
        brand_list = "\n".join(
            f"• **{brand}** — {count} item{'s' if count > 1 else ''}"
            for brand, count in sorted_brands[:10]
        )

        embed = {
            "title": "📊 Daily Summary",
            "color": 0x3B82F6,  # Blue
            "fields": [
                {
                    "name": "Items Found",
                    "value": f"**{items_found}** profitable items",
                    "inline": True,
                },
                {
                    "name": "Total Profit Potential",
                    "value": f"**${total_profit:,.0f}**",
                    "inline": True,
                },
                {
                    "name": "Top Brands",
                    "value": brand_list or "No data",
                    "inline": False,
                },
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Archive Arbitrage • Daily Report",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self.webhook_url,
                    json={"embeds": [embed]},
                )

                if resp.status_code in (200, 204):
                    # Reset daily stats
                    self._state["daily_stats"] = {
                        "items_found": 0,
                        "total_profit_potential": 0,
                        "top_brands": {},
                    }
                    self._save_state()
                    return True

        except Exception as e:
            print(f"Discord summary failed: {e}")

        return False

    async def send_test_alert(self) -> bool:
        """Send a test alert to verify the webhook works."""
        if not self.webhook_url:
            print("No webhook URL configured")
            return False

        embed = {
            "title": "✅ Archive Arbitrage Connected",
            "description": "Discord alerts are working! You'll receive notifications here when profitable items are found.",
            "color": 0x22C55E,
            "fields": [
                {
                    "name": "Alert Thresholds",
                    "value": f"Min profit: **${self.min_profit:.0f}**\nMin margin: **{self.min_margin * 100:.0f}%**",
                    "inline": True,
                },
                {
                    "name": "Rate Limits",
                    "value": f"Max **{MAX_ALERTS_PER_HOUR}**/hour\n**{ALERT_COOLDOWN_SECONDS}s** cooldown",
                    "inline": True,
                },
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Archive Arbitrage • Alert System",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self.webhook_url,
                    json={"embeds": [embed]},
                )
                if resp.status_code in (200, 204):
                    print("✅ Test alert sent!")
                    return True
                else:
                    print(f"❌ Webhook error: {resp.status_code} - {resp.text}")
                    return False

        except Exception as e:
            print(f"❌ Failed: {e}")
            return False


# Convenience function for use in scrape pipelines
async def alert_if_profitable(
    scraped_item,
    price_info,
    brand: str = "",
    alerts: AlertService = None,
) -> bool:
    """
    Check if a scraped item should trigger a Discord alert.
    Call this from the scrape pipeline after pricing.
    """
    if alerts is None:
        alerts = AlertService()

    if price_info.confidence == "skip" or price_info.recommended_price == 0:
        return False

    # Don't alert on dead-demand items — high margin means nothing if it won't sell
    if getattr(price_info, "demand_level", "unknown") == "dead":
        return False

    alert_item = AlertItem(
        title=scraped_item.title,
        brand=brand or scraped_item.brand or "Unknown",
        source=scraped_item.source,
        source_url=scraped_item.url,
        source_price=scraped_item.price,
        market_price=float(price_info.market_price) if price_info.market_price else 0,
        recommended_price=float(price_info.recommended_price),
        profit=float(price_info.profit_estimate),
        margin_percent=price_info.margin_percent,
        image_url=scraped_item.images[0] if scraped_item.images else None,
        size=scraped_item.size,
        season_name=price_info.season_name,
        season_multiplier=price_info.season_multiplier,
        comps_count=price_info.comps_count,
        is_auction=getattr(scraped_item, "is_auction", False),
        time_left_hours=getattr(scraped_item, "time_left_hours", None),
        bid_count=getattr(scraped_item, "bid_count", 0),
        demand_level=getattr(price_info, "demand_level", "unknown"),
        demand_score=getattr(price_info, "demand_score", 0.0),
    )

    
    sent_discord = await alerts.send_item_alert(alert_item)
    
    # NEW: Send to Whop after pricing if it qualifies (A-grade only)
    is_a_grade = getattr(price_info, "deal_grade", getattr(price_info, "grade", "")) == "A"
    if is_a_grade:
        try:
            from core.whop_alerts import send_whop_alert, format_whop_deal_content
            title, content = format_whop_deal_content(
                scraped_item, price_info, price_info.margin_percent, float(price_info.profit_estimate)
            )
            await send_whop_alert(title, content)
        except Exception as e:
            print(f"  [Whop Hook] Failed to trigger Whop alert: {e}")
    else:
        print(f"  [Whop Hook] Skipped: Not an A-grade deal (Grade: {getattr(price_info, 'deal_grade', None) or getattr(price_info, 'grade', None)})")
        
    return sent_discord



# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Archive Arbitrage Alerts")
    parser.add_argument("--test", action="store_true", help="Send a test alert")
    parser.add_argument("--summary", action="store_true", help="Send daily summary")
    args = parser.parse_args()

    if args.test:
        asyncio.run(AlertService().send_test_alert())
    elif args.summary:
        asyncio.run(AlertService().send_daily_summary())
    else:
        parser.print_help()
