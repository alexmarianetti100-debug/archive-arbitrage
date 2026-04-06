"""
Discord Bot for Archive Arbitrage community management.

Runs alongside the existing webhook-based alert system. Adds:
- Auto-welcome DMs for new members
- #wins channel tracking with profit leaderboard
- Weekly market report auto-posted to #market-talk
- Subscription expiry reminder DMs
- Queue management commands for content review

Requires: DISCORD_BOT_TOKEN in .env
Install: pip install discord.py

Usage:
    python -m core.discord_bot          # Run the bot
    python -m core.discord_bot --test   # Send a test welcome message
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("discord_bot")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
WINS_CHANNEL_NAME = os.getenv("DISCORD_WINS_CHANNEL", "wins")
MARKET_TALK_CHANNEL_NAME = os.getenv("DISCORD_MARKET_CHANNEL", "market-talk")

# Leaderboard persistence
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LEADERBOARD_FILE = DATA_DIR / "discord_leaderboard.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Leaderboard tracking (works without discord.py for data collection) ──

def _load_leaderboard() -> dict:
    try:
        if LEADERBOARD_FILE.exists():
            return json.loads(LEADERBOARD_FILE.read_text())
    except Exception:
        pass
    return {"wins": {}, "monthly": {}, "all_time_profit": {}}


def _save_leaderboard(lb: dict) -> None:
    LEADERBOARD_FILE.write_text(json.dumps(lb, indent=2))


def parse_profit_from_message(text: str) -> Optional[float]:
    """Extract a profit amount from a win post message.

    Handles formats like:
        "$420 profit"
        "+$420"
        "made $420"
        "profit: $420"
        "$420"
    """
    patterns = [
        r'\+?\$?([\d,]+)\s*profit',
        r'profit[:\s]+\$?([\d,]+)',
        r'made\s+\$?([\d,]+)',
        r'flipped?\s+.*?for\s+\$?([\d,]+)\s*profit',
        r'\+\$?([\d,]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def record_win(user_id: str, username: str, profit: float) -> dict:
    """Record a win in the leaderboard. Returns updated stats for the user."""
    lb = _load_leaderboard()
    month_key = date.today().strftime("%Y-%m")

    # All-time wins
    wins = lb.setdefault("wins", {})
    wins[user_id] = wins.get(user_id, 0) + 1

    # Monthly profit
    monthly = lb.setdefault("monthly", {})
    month_data = monthly.setdefault(month_key, {})
    month_data[user_id] = month_data.get(user_id, 0) + profit

    # All-time profit
    all_time = lb.setdefault("all_time_profit", {})
    all_time[user_id] = all_time.get(user_id, 0) + profit

    # Username mapping
    names = lb.setdefault("usernames", {})
    names[user_id] = username

    _save_leaderboard(lb)

    return {
        "total_wins": wins[user_id],
        "monthly_profit": month_data[user_id],
        "all_time_profit": all_time[user_id],
    }


def get_leaderboard(period: str = "monthly", top_n: int = 10) -> list[dict]:
    """Get the top N users by profit.

    Args:
        period: "monthly" or "all_time"
        top_n: Number of entries to return.
    """
    lb = _load_leaderboard()
    names = lb.get("usernames", {})

    if period == "monthly":
        month_key = date.today().strftime("%Y-%m")
        data = lb.get("monthly", {}).get(month_key, {})
    else:
        data = lb.get("all_time_profit", {})

    sorted_users = sorted(data.items(), key=lambda x: -x[1])[:top_n]

    return [
        {
            "rank": i + 1,
            "user_id": uid,
            "username": names.get(uid, f"User#{uid[:6]}"),
            "profit": profit,
            "wins": lb.get("wins", {}).get(uid, 0),
        }
        for i, (uid, profit) in enumerate(sorted_users)
    ]


# ── Welcome message ──

WELCOME_MESSAGE = """Welcome to **Archive Arbitrage**!

You now have access to real-time deal alerts backed by sold comp data across 7 platforms.

**Quick start:**
1. Check your tier channel for deals (#{tier}-signals)
2. Post your flips in #wins — we track profits on a leaderboard
3. Ask auth questions in #legit-check
4. Market discussion goes in #market-talk

**How to read a deal alert:**
- **Listed price** = what you'd pay now
- **Market value** = weighted average of recent sold comps
- **Est. profit** = after platform fees and shipping
- **Auth confidence** = our 7-signal authenticity score

One good flip pays for months of the subscription. Happy hunting.
"""


# ── Weekly market report embed ──

def build_weekly_report_embed(
    top_brands: list[tuple[str, int]],
    total_deals: int,
    total_profit: float,
    avg_gap_percent: float,
    best_deal: Optional[dict] = None,
) -> dict:
    """Build a Discord embed for the weekly market report.

    This gets posted to #market-talk every Monday.
    """
    brand_list = "\n".join(
        f"**{i+1}.** {brand} — {count} deal{'s' if count > 1 else ''}"
        for i, (brand, count) in enumerate(top_brands[:10])
    )

    fields = [
        {
            "name": "Deals Sent",
            "value": f"**{total_deals}**",
            "inline": True,
        },
        {
            "name": "Total Profit Opportunity",
            "value": f"**${total_profit:,.0f}**",
            "inline": True,
        },
        {
            "name": "Avg Gap",
            "value": f"**{avg_gap_percent:.0f}%** below market",
            "inline": True,
        },
        {
            "name": "Top Brands This Week",
            "value": brand_list or "No data",
            "inline": False,
        },
    ]

    if best_deal:
        fields.append({
            "name": "Best Deal",
            "value": (
                f"**{best_deal.get('brand', '')} — {best_deal.get('title', '')[:60]}**\n"
                f"${best_deal.get('profit', 0):,.0f} profit | "
                f"{best_deal.get('gap', 0):.0f}% below market"
            ),
            "inline": False,
        })

    embed = {
        "title": "Weekly Market Report",
        "description": f"Week of {date.today().strftime('%B %d, %Y')}",
        "color": 0xD4AF37,  # Gold
        "fields": fields,
        "footer": {"text": "Archive Arbitrage — Weekly Intelligence"},
        "timestamp": datetime.utcnow().isoformat(),
    }

    return embed


def build_leaderboard_embed(period: str = "monthly") -> dict:
    """Build a Discord embed for the profit leaderboard."""
    entries = get_leaderboard(period)

    if not entries:
        return {
            "title": "Profit Leaderboard",
            "description": "No wins recorded yet. Post your flips in #wins!",
            "color": 0xD4AF37,
        }

    lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for entry in entries:
        medal = medals.get(entry["rank"], f"**{entry['rank']}.**")
        lines.append(
            f"{medal} **{entry['username']}** — "
            f"${entry['profit']:,.0f} profit ({entry['wins']} win{'s' if entry['wins'] != 1 else ''})"
        )

    title = "Monthly Profit Leaderboard" if period == "monthly" else "All-Time Profit Leaderboard"
    month_label = date.today().strftime("%B %Y") if period == "monthly" else "All Time"

    return {
        "title": title,
        "description": f"{month_label}\n\n" + "\n".join(lines),
        "color": 0xD4AF37,
        "footer": {"text": "Post your wins in #wins to get on the board!"},
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Subscription reminder (sent via webhook, no bot needed) ──

async def send_renewal_reminder(
    webhook_url: str,
    username: str,
    days_left: int,
    best_deal_profit: float = 0,
) -> bool:
    """Send a subscription renewal reminder via Discord webhook DM.

    Note: Webhook DMs require a DM-channel webhook. For broader use,
    this should be sent via the bot's DM capability instead.
    """
    import httpx

    message = (
        f"Hey {username} — your Archive Arbitrage subscription "
        f"{'expires today' if days_left <= 0 else f'expires in {days_left} day(s)'}.\n\n"
    )

    if best_deal_profit > 0:
        message += (
            f"Your best deal this month was **${best_deal_profit:,.0f} profit**. "
            f"That's {best_deal_profit / 30:.0f}x the subscription cost.\n\n"
        )

    message += "Renew to keep getting verified deals → link in #announcements"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                webhook_url,
                json={"content": message, "username": "Archive Arbitrage"},
            )
            return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Renewal reminder failed: {e}")
        return False


# ── Discord.py bot (only starts if token is configured) ──

def run_bot():
    """Start the Discord bot. Requires discord.py and DISCORD_BOT_TOKEN."""
    try:
        import discord
        from discord.ext import commands, tasks
    except ImportError:
        logger.error(
            "discord.py not installed. Run: pip install discord.py\n"
            "The bot is optional — webhook alerts work without it."
        )
        return

    intents = discord.Intents.default()
    # These require toggling in Developer Portal → Bot → Privileged Gateway Intents
    # Enable "Message Content Intent" for win tracking in #wins
    # Enable "Server Members Intent" for welcome DMs (optional)
    try:
        intents.message_content = True
    except Exception:
        logger.warning("Message Content intent not available — win tracking disabled")
    try:
        intents.members = True
    except Exception:
        logger.warning("Members intent not available — welcome DMs disabled")

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"Discord bot connected as {bot.user}")
        if not weekly_report_task.is_running():
            weekly_report_task.start()

    @bot.event
    async def on_member_join(member: discord.Member):
        """Auto-welcome new members via DM."""
        try:
            await member.send(WELCOME_MESSAGE.format(tier="beginner"))
            logger.info(f"Sent welcome DM to {member.name}")
        except discord.Forbidden:
            logger.warning(f"Cannot DM {member.name} — DMs disabled")

    @bot.event
    async def on_message(message: discord.Message):
        """Track wins posted in #wins channel."""
        if message.author.bot:
            return

        # Process commands first
        await bot.process_commands(message)

        # Track wins
        if message.channel.name == WINS_CHANNEL_NAME:
            profit = parse_profit_from_message(message.content)
            if profit and profit > 0:
                stats = record_win(
                    str(message.author.id),
                    message.author.display_name,
                    profit,
                )
                await message.add_reaction("💰")
                await message.reply(
                    f"**${profit:,.0f} profit recorded!** "
                    f"You're at ${stats['monthly_profit']:,.0f} this month "
                    f"({stats['total_wins']} total wins).",
                    mention_author=False,
                )

    @bot.command(name="leaderboard", aliases=["lb"])
    async def leaderboard_cmd(ctx, period: str = "monthly"):
        """Show the profit leaderboard."""
        if period not in ("monthly", "all_time"):
            period = "monthly"
        embed_data = build_leaderboard_embed(period)
        embed = discord.Embed.from_dict(embed_data)
        await ctx.send(embed=embed)

    @bot.command(name="activate")
    async def activate_cmd(ctx):
        """Assign the @Starter role to a new subscriber. DM or channel command."""
        guild = ctx.guild
        if not guild:
            # DM — find the guild
            for g in bot.guilds:
                member = g.get_member(ctx.author.id)
                if member:
                    guild = g
                    break

        if not guild:
            await ctx.send("Join the Archive Arbitrage Discord server first, then run !activate again.")
            return

        member = guild.get_member(ctx.author.id)
        if not member:
            await ctx.send("You need to be in the server to activate. Join via the invite link first.")
            return

        # Find the Starter role
        starter_role = discord.utils.get(guild.roles, name="Starter")
        if not starter_role:
            await ctx.send("Could not find the Starter role. Contact an admin.")
            return

        # Check if already has a tier role
        tier_names = {"Starter", "Pro", "Whale", "Trial"}
        existing = [r for r in member.roles if r.name in tier_names]
        if existing:
            role_names = ", ".join(f"@{r.name}" for r in existing)
            await ctx.send(f"You already have {role_names}. If you need a tier change, contact an admin.")
            return

        try:
            await member.add_roles(starter_role)
            await ctx.send(
                f"**Welcome!** You now have the @Starter role.\n"
                f"Check #starter-signals for deal alerts. Happy hunting. 🏴"
            )
            logger.info(f"Assigned @Starter to {member.display_name} ({member.id}) via !activate")
        except discord.Forbidden:
            await ctx.send("I don't have permission to assign roles. Ask an admin to check bot permissions.")
        except Exception as e:
            await ctx.send(f"Something went wrong. Contact an admin.")
            logger.error(f"Activate failed for {member.id}: {e}")

    @bot.command(name="mystats")
    async def mystats_cmd(ctx):
        """Show your personal stats."""
        lb = _load_leaderboard()
        uid = str(ctx.author.id)
        month_key = date.today().strftime("%Y-%m")

        wins = lb.get("wins", {}).get(uid, 0)
        monthly = lb.get("monthly", {}).get(month_key, {}).get(uid, 0)
        all_time = lb.get("all_time_profit", {}).get(uid, 0)

        embed = discord.Embed(
            title=f"Stats for {ctx.author.display_name}",
            color=0xD4AF37,
        )
        embed.add_field(name="Total Wins", value=str(wins), inline=True)
        embed.add_field(name="Monthly Profit", value=f"${monthly:,.0f}", inline=True)
        embed.add_field(name="All-Time Profit", value=f"${all_time:,.0f}", inline=True)

        await ctx.send(embed=embed)

    @tasks.loop(hours=168)  # Weekly
    async def weekly_report_task():
        """Post weekly market report to #market-talk."""
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=MARKET_TALK_CHANNEL_NAME)
            if not channel:
                continue

            # Pull stats from alert state
            alert_state_file = DATA_DIR / "alert_state.json"
            if alert_state_file.exists():
                try:
                    state = json.loads(alert_state_file.read_text())
                    stats = state.get("daily_stats", {})
                    brands = stats.get("top_brands", {})
                    top_brands = sorted(brands.items(), key=lambda x: -x[1])

                    embed_data = build_weekly_report_embed(
                        top_brands=top_brands,
                        total_deals=stats.get("items_found", 0),
                        total_profit=stats.get("total_profit_potential", 0),
                        avg_gap_percent=45,  # Approximate
                    )
                    embed = discord.Embed.from_dict(embed_data)
                    await channel.send(embed=embed)
                    logger.info(f"Posted weekly report to #{MARKET_TALK_CHANNEL_NAME}")
                except Exception as e:
                    logger.error(f"Weekly report failed: {e}")

    if not DISCORD_BOT_TOKEN:
        logger.warning(
            "DISCORD_BOT_TOKEN not set. Bot features disabled.\n"
            "Webhook alerts still work without the bot.\n"
            "To enable: add DISCORD_BOT_TOKEN to .env"
        )
        return

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Archive Arbitrage Discord Bot")
    parser.add_argument("--test-leaderboard", action="store_true", help="Print test leaderboard")
    args = parser.parse_args()

    if args.test_leaderboard:
        # Record some test data
        record_win("test_user_1", "ArchiveKing", 420)
        record_win("test_user_2", "GrailedHunter", 280)
        record_win("test_user_1", "ArchiveKing", 350)
        record_win("test_user_3", "FlipMaster", 600)

        entries = get_leaderboard("monthly")
        print("Monthly Leaderboard:")
        for e in entries:
            print(f"  #{e['rank']} {e['username']} — ${e['profit']:,.0f} ({e['wins']} wins)")
    else:
        run_bot()
