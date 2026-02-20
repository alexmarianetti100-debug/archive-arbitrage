#!/usr/bin/env python3
"""
Telegram Bot for Archive Arbitrage.

Sends deal alerts to paying subscribers with brand/size/profit filtering.
Integrates with Stripe for subscription management.

Usage:
    # Run the bot standalone
    python telegram_bot.py

    # From pipeline - send deals to all matching subscribers
    from telegram_bot import send_deal_to_subscribers
    await send_deal_to_subscribers(scraped_item, price_info, brand="rick owens")
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from db.sqlite_models import _get_conn, _add_column_if_missing, get_items

logger = logging.getLogger("telegram_bot")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Alert thresholds (same as Discord)
GRAIL_PROFIT = float(os.getenv("ALERT_GRAIL_PROFIT", "500"))
FIRE_PROFIT = float(os.getenv("ALERT_FIRE_PROFIT", "300"))
MIN_PROFIT = float(os.getenv("ALERT_MIN_PROFIT", "150"))
MIN_MARGIN = float(os.getenv("ALERT_MIN_MARGIN", "0.40"))


# ---------------------------------------------------------------------------
# Database: telegram_users table
# ---------------------------------------------------------------------------

def init_telegram_db():
    """Create telegram_users table if it doesn't exist."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS telegram_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            subscribed INTEGER DEFAULT 0,
            brands_filter TEXT DEFAULT '[]',
            sizes_filter TEXT DEFAULT '[]',
            min_profit REAL DEFAULT 150,
            stripe_customer_id TEXT,
            subscription_status TEXT DEFAULT 'inactive',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_tg_users_telegram_id ON telegram_users(telegram_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tg_users_subscribed ON telegram_users(subscribed)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tg_users_stripe ON telegram_users(stripe_customer_id)")
    conn.commit()
    conn.close()


def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None) -> Dict[str, Any]:
    """Get or create a telegram user."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM telegram_users WHERE telegram_id = ?", (telegram_id,))
    row = c.fetchone()
    if row:
        user = dict(row)
        conn.close()
        return user

    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO telegram_users (telegram_id, username, first_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, username, first_name, now, now))
    conn.commit()
    c.execute("SELECT * FROM telegram_users WHERE telegram_id = ?", (telegram_id,))
    user = dict(c.fetchone())
    conn.close()
    return user


def update_user(telegram_id: int, **kwargs):
    """Update user fields."""
    conn = _get_conn()
    c = conn.cursor()
    sets = []
    params = []
    for key, val in kwargs.items():
        if key in ("brands_filter", "sizes_filter") and isinstance(val, list):
            val = json.dumps(val)
        sets.append(f"{key} = ?")
        params.append(val)
    sets.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(telegram_id)
    c.execute(f"UPDATE telegram_users SET {', '.join(sets)} WHERE telegram_id = ?", params)
    conn.commit()
    conn.close()


def get_active_subscribers() -> List[Dict[str, Any]]:
    """Get all active subscribers."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM telegram_users WHERE subscribed = 1")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users


def activate_user(telegram_id: int, stripe_customer_id: str = None):
    """Activate a user's subscription."""
    update_user(telegram_id, subscribed=1, subscription_status="active",
                stripe_customer_id=stripe_customer_id)


def deactivate_user(telegram_id: int):
    """Deactivate a user's subscription."""
    update_user(telegram_id, subscribed=0, subscription_status="inactive")


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

async def tg_request(method: str, data: dict = None) -> dict:
    """Make a request to the Telegram Bot API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{TELEGRAM_API}/{method}", json=data or {})
        result = resp.json()
        if not result.get("ok"):
            logger.error(f"Telegram API error: {result}")
        return result


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML",
                       reply_markup: dict = None, disable_preview: bool = False):
    """Send a text message."""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    return await tg_request("sendMessage", data)


async def send_photo(chat_id: int, photo_url: str, caption: str,
                     parse_mode: str = "HTML", reply_markup: dict = None):
    """Send a photo with caption."""
    data = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption[:1024],  # Telegram caption limit
        "parse_mode": parse_mode,
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    return await tg_request("sendPhoto", data)


# ---------------------------------------------------------------------------
# Deal formatting
# ---------------------------------------------------------------------------

def format_deal_message(item_data: dict) -> str:
    """Format a deal alert as a Telegram HTML message."""
    profit = item_data.get("profit", 0)
    margin = item_data.get("margin_percent", 0)

    # Tier emoji
    if profit >= GRAIL_PROFIT:
        tier = "🏆 GRAIL ALERT"
    elif profit >= FIRE_PROFIT:
        tier = "🔥 HOT DEAL"
    else:
        tier = "💰 Solid Flip"

    brand = item_data.get("brand", "Unknown").upper()
    title = item_data.get("title", "")[:80]
    source = item_data.get("source", "").title()
    source_price = item_data.get("source_price", 0)
    market_price = item_data.get("market_price", 0)
    sell_price = item_data.get("recommended_price", 0)
    size = item_data.get("size", "")
    season = item_data.get("season_name", "")
    demand = item_data.get("demand_level", "unknown")
    grade = item_data.get("grade", "")
    source_url = item_data.get("source_url", "")
    comps = item_data.get("comps_count", 0)

    # Demand emoji
    demand_map = {"hot": "🔥", "warm": "🟡", "cold": "🔵", "dead": "💀"}
    demand_emoji = demand_map.get(demand, "")

    lines = [
        f"<b>{tier}</b>",
        f"<b>{brand}</b>",
        f"{title}",
        "",
    ]

    if season:
        lines.append(f"✨ <b>{season}</b>")

    lines.extend([
        f"💵 Buy: <b>${source_price:.0f}</b> ({source})",
        f"📊 Market: <b>${market_price:.0f}</b> ({comps} comps)",
        f"🎯 Sell at: <b>${sell_price:.0f}</b>",
        "",
        f"💰 Profit: <b>${profit:.0f}</b>",
        f"📈 Margin: <b>{margin * 100:.0f}%</b>",
    ])

    if size:
        lines.append(f"📐 Size: {size}")
    if grade:
        lines.append(f"🏷 Grade: <b>{grade}</b>")
    if demand_emoji:
        lines.append(f"📊 Demand: {demand_emoji} {demand.upper()}")

    if source_url:
        lines.append(f"\n<a href=\"{source_url}\">🔗 View Listing</a>")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Send deals to subscribers
# ---------------------------------------------------------------------------

async def send_deal_to_subscribers(scraped_item, price_info, brand: str = ""):
    """
    Send a deal alert to all matching Telegram subscribers.
    Called from pipeline.py alongside Discord alerts.
    """
    if not BOT_TOKEN:
        return

    # Build item data dict
    profit = float(price_info.profit_estimate) if hasattr(price_info, 'profit_estimate') else 0
    margin = float(price_info.margin_percent) if hasattr(price_info, 'margin_percent') else 0

    if profit < MIN_PROFIT or margin < MIN_MARGIN:
        return

    # Don't send dead-demand items
    demand_level = getattr(price_info, "demand_level", "unknown")
    if demand_level == "dead":
        return

    item_data = {
        "title": scraped_item.title,
        "brand": brand or getattr(scraped_item, "brand", "Unknown"),
        "source": scraped_item.source,
        "source_url": scraped_item.url,
        "source_price": scraped_item.price,
        "market_price": float(price_info.market_price) if price_info.market_price else 0,
        "recommended_price": float(price_info.recommended_price),
        "profit": profit,
        "margin_percent": margin,
        "size": getattr(scraped_item, "size", ""),
        "season_name": getattr(price_info, "season_name", ""),
        "demand_level": demand_level,
        "grade": getattr(price_info, "grade", ""),
        "comps_count": getattr(price_info, "comps_count", 0),
        "image_url": scraped_item.images[0] if scraped_item.images else None,
    }

    message = format_deal_message(item_data)
    subscribers = get_active_subscribers()

    for user in subscribers:
        try:
            # Check brand filter
            brands_filter = json.loads(user.get("brands_filter", "[]") or "[]")
            if brands_filter:
                item_brand = item_data["brand"].lower()
                if not any(b.lower() in item_brand or item_brand in b.lower() for b in brands_filter):
                    continue

            # Check size filter
            sizes_filter = json.loads(user.get("sizes_filter", "[]") or "[]")
            if sizes_filter and item_data.get("size"):
                if item_data["size"].upper() not in [s.upper() for s in sizes_filter]:
                    continue

            # Check min profit
            user_min_profit = user.get("min_profit", MIN_PROFIT)
            if profit < user_min_profit:
                continue

            # Send with image if available
            view_btn = {
                "inline_keyboard": [[
                    {"text": "🔗 View Listing", "url": item_data["source_url"]}
                ]]
            } if item_data.get("source_url") else None

            if item_data.get("image_url"):
                await send_photo(
                    user["telegram_id"],
                    item_data["image_url"],
                    message,
                    reply_markup=view_btn,
                )
            else:
                await send_message(
                    user["telegram_id"],
                    message,
                    reply_markup=view_btn,
                )

        except Exception as e:
            logger.error(f"Failed to send to {user.get('telegram_id')}: {e}")

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Bot command handlers
# ---------------------------------------------------------------------------

async def handle_start(chat_id: int, user_data: dict):
    """Handle /start command."""
    user = get_or_create_user(
        chat_id,
        username=user_data.get("username"),
        first_name=user_data.get("first_name"),
    )

    if user.get("subscribed"):
        await send_message(chat_id, (
            "👋 Welcome back! You're an active subscriber.\n\n"
            "Use /help to see commands."
        ))
    else:
        await send_message(chat_id, (
            "🏴 <b>Archive Arbitrage</b>\n\n"
            "Real-time alerts for underpriced archive fashion.\n"
            "270+ brands tracked across Grailed, eBay, Poshmark & more.\n\n"
            "🔥 AI-powered pricing engine\n"
            "📊 Cross-platform arbitrage detection\n"
            "🏆 Grail alerts before anyone else\n\n"
            "Use /subscribe to get started — <b>$39/mo</b>\n"
            "Use /help for all commands."
        ))


async def handle_help(chat_id: int):
    """Handle /help command."""
    await send_message(chat_id, (
        "📋 <b>Commands</b>\n\n"
        "/subscribe — Subscribe ($39/mo)\n"
        "/status — Check your subscription\n"
        "/brands — Set brand filters\n"
        "/sizes — Set size filters\n"
        "/minprofit — Set min profit threshold\n"
        "/recent — Last 10 deals\n"
        "/help — This message"
    ))


async def handle_status(chat_id: int):
    """Handle /status command."""
    user = get_or_create_user(chat_id)

    brands = json.loads(user.get("brands_filter", "[]") or "[]")
    sizes = json.loads(user.get("sizes_filter", "[]") or "[]")
    min_p = user.get("min_profit", MIN_PROFIT)
    status = "✅ Active" if user.get("subscribed") else "❌ Inactive"

    text = (
        f"📊 <b>Your Status</b>\n\n"
        f"Subscription: {status}\n"
        f"Min Profit: <b>${min_p:.0f}</b>\n"
        f"Brand Filters: {', '.join(brands) if brands else 'All brands'}\n"
        f"Size Filters: {', '.join(sizes) if sizes else 'All sizes'}\n"
    )
    await send_message(chat_id, text)


async def handle_brands(chat_id: int, args: str):
    """Handle /brands command. Usage: /brands rick owens, raf simons, helmut lang"""
    user = get_or_create_user(chat_id)

    if not args.strip():
        brands = json.loads(user.get("brands_filter", "[]") or "[]")
        if brands:
            await send_message(chat_id, (
                f"🏷 <b>Your Brand Filters</b>\n\n"
                f"{chr(10).join('• ' + b for b in brands)}\n\n"
                "To change: /brands rick owens, raf simons, helmut lang\n"
                "To clear: /brands clear"
            ))
        else:
            await send_message(chat_id, (
                "🏷 No brand filters — you'll get alerts for all 270+ brands.\n\n"
                "To set filters: /brands rick owens, raf simons, helmut lang"
            ))
        return

    if args.strip().lower() == "clear":
        update_user(chat_id, brands_filter=[])
        await send_message(chat_id, "✅ Brand filters cleared — you'll get alerts for all brands.")
        return

    brands = [b.strip() for b in args.split(",") if b.strip()]
    update_user(chat_id, brands_filter=brands)
    await send_message(chat_id, (
        f"✅ Brand filters updated!\n\n"
        f"Watching: {', '.join(brands)}\n\n"
        "You'll only get alerts for these brands."
    ))


async def handle_sizes(chat_id: int, args: str):
    """Handle /sizes command. Usage: /sizes S, M, L or /sizes 30, 32, 34"""
    user = get_or_create_user(chat_id)

    if not args.strip():
        sizes = json.loads(user.get("sizes_filter", "[]") or "[]")
        if sizes:
            await send_message(chat_id, (
                f"📐 <b>Your Size Filters</b>\n\n"
                f"{', '.join(sizes)}\n\n"
                "To change: /sizes S, M, L\n"
                "To clear: /sizes clear"
            ))
        else:
            await send_message(chat_id, (
                "📐 No size filters set — you'll get alerts for all sizes.\n\n"
                "To set: /sizes S, M, L or /sizes 30, 32, 34"
            ))
        return

    if args.strip().lower() == "clear":
        update_user(chat_id, sizes_filter=[])
        await send_message(chat_id, "✅ Size filters cleared.")
        return

    sizes = [s.strip().upper() for s in args.split(",") if s.strip()]
    update_user(chat_id, sizes_filter=sizes)
    await send_message(chat_id, f"✅ Size filters: {', '.join(sizes)}")


async def handle_minprofit(chat_id: int, args: str):
    """Handle /minprofit command. Usage: /minprofit 200"""
    if not args.strip():
        user = get_or_create_user(chat_id)
        mp = user.get("min_profit", MIN_PROFIT)
        await send_message(chat_id, (
            f"💰 Min profit threshold: <b>${mp:.0f}</b>\n\n"
            "To change: /minprofit 200"
        ))
        return

    try:
        val = float(args.strip().replace("$", ""))
        if val < 0 or val > 10000:
            await send_message(chat_id, "❌ Enter a value between $0 and $10,000")
            return
        update_user(chat_id, min_profit=val)
        await send_message(chat_id, f"✅ Min profit set to <b>${val:.0f}</b>")
    except ValueError:
        await send_message(chat_id, "❌ Invalid number. Usage: /minprofit 200")


async def handle_recent(chat_id: int):
    """Handle /recent — show last 10 profitable items."""
    user = get_or_create_user(chat_id)
    if not user.get("subscribed"):
        await send_message(chat_id, "🔒 Subscribe to see recent deals. Use /subscribe")
        return

    items = get_items(status="active", sort="newest", limit=10)
    if not items:
        await send_message(chat_id, "No recent deals found.")
        return

    lines = ["<b>📋 Recent Deals</b>\n"]
    for item in items:
        profit = (item.our_price or 0) - item.source_price
        if profit <= 0:
            continue
        margin = item.margin_percent or 0
        tier = "🏆" if profit >= GRAIL_PROFIT else "🔥" if profit >= FIRE_PROFIT else "💰"
        brand = (item.brand or "?").upper()
        lines.append(
            f"{tier} <b>{brand}</b> — ${item.source_price:.0f} → ${item.our_price:.0f} "
            f"(+${profit:.0f}, {margin*100:.0f}%)"
        )
        if item.source_url:
            lines.append(f"   <a href=\"{item.source_url}\">View</a>")

    await send_message(chat_id, "\n".join(lines[:30]))  # Cap length


async def handle_subscribe(chat_id: int):
    """Handle /subscribe — generate Stripe checkout link."""
    try:
        from stripe_billing import create_checkout_session
        url = await create_checkout_session(chat_id)
        if url:
            await send_message(chat_id, (
                "💳 <b>Subscribe to Archive Arbitrage</b>\n\n"
                "✅ Real-time deal alerts\n"
                "✅ 270+ archive brands tracked\n"
                "✅ Custom brand & size filters\n"
                "✅ AI-powered pricing engine\n\n"
                f"<b>$39/mo</b> — Cancel anytime.\n"
            ), reply_markup={
                "inline_keyboard": [[
                    {"text": "💳 Subscribe — $39/mo", "url": url}
                ]]
            })
        else:
            await send_message(chat_id, "⚠️ Billing not configured yet. Contact @archivearbitrage")
    except ImportError:
        await send_message(chat_id, "⚠️ Billing system not available. Contact @archivearbitrage")
    except Exception as e:
        logger.error(f"Subscribe error: {e}")
        await send_message(chat_id, "⚠️ Something went wrong. Try again later.")


# ---------------------------------------------------------------------------
# Webhook / Polling handler
# ---------------------------------------------------------------------------

async def process_update(update: dict):
    """Process a single Telegram update."""
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user_data = message.get("from", {})

    if not text:
        return

    # Parse command and args
    if text.startswith("/"):
        parts = text.split(None, 1)
        command = parts[0].lower().split("@")[0]  # Strip @botname
        args = parts[1] if len(parts) > 1 else ""
    else:
        return  # Ignore non-commands

    # Route commands
    if command == "/start":
        await handle_start(chat_id, user_data)
    elif command == "/help":
        await handle_help(chat_id)
    elif command == "/status":
        await handle_status(chat_id)
    elif command == "/brands":
        await handle_brands(chat_id, args)
    elif command == "/sizes":
        await handle_sizes(chat_id, args)
    elif command == "/minprofit":
        await handle_minprofit(chat_id, args)
    elif command == "/recent":
        await handle_recent(chat_id)
    elif command == "/subscribe":
        await handle_subscribe(chat_id)
    else:
        await send_message(chat_id, "Unknown command. Use /help to see available commands.")


async def run_polling():
    """Run the bot using long polling (simple, no webhook needed)."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return

    init_telegram_db()
    print("🤖 Telegram bot starting (polling mode)...")

    # Set commands menu
    await tg_request("setMyCommands", {
        "commands": [
            {"command": "start", "description": "Get started"},
            {"command": "subscribe", "description": "Subscribe ($39/mo)"},
            {"command": "status", "description": "Check subscription status"},
            {"command": "brands", "description": "Set brand filters"},
            {"command": "sizes", "description": "Set size filters"},
            {"command": "minprofit", "description": "Set min profit threshold"},
            {"command": "recent", "description": "Last 10 deals"},
            {"command": "help", "description": "Show help"},
        ]
    })

    me = await tg_request("getMe")
    if me.get("ok"):
        bot_name = me["result"].get("username", "unknown")
        print(f"✅ Bot running as @{bot_name}")

    offset = 0
    while True:
        try:
            result = await tg_request("getUpdates", {
                "offset": offset,
                "timeout": 30,
            })
            if result.get("ok"):
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        await process_update(update)
                    except Exception as e:
                        logger.error(f"Update processing error: {e}")
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_polling())
