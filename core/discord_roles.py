"""
Discord role management for Archive Arbitrage.

Assigns/removes tier roles based on subscription events.
Uses the Discord REST API directly (no discord.py needed).

Called from stripe_billing.py on checkout.session.completed
and customer.subscription.deleted events.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("discord_roles")

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GUILD_ID = os.getenv("DISCORD_GUILD_ID", "1466241850099630123")

# Role IDs — from your Discord server
ROLE_IDS = {
    "starter": os.getenv("DISCORD_ROLE_STARTER", "1481007533085823118"),
    "pro": os.getenv("DISCORD_ROLE_PRO", "1481009179207532754"),
    "whale": os.getenv("DISCORD_ROLE_WHALE", "1481009618250502335"),
    "trial": os.getenv("DISCORD_ROLE_TRIAL", "1487535790748602578"),
}

TIER_ROLES = ["starter", "pro", "whale", "trial"]

HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
}


async def find_member_by_email(email: str) -> Optional[str]:
    """Try to find a Discord member by searching guild members.

    Note: This requires the Members intent and only works for members
    already in the server. Returns the user ID if found.

    For a more reliable flow, have users link their Discord ID during
    checkout (via metadata) or use Whop's built-in Discord integration.
    """
    # Discord API doesn't support email lookup directly.
    # This is a limitation — see note below about linking flow.
    return None


async def assign_role(discord_user_id: str, tier: str = "starter") -> bool:
    """Assign a tier role to a Discord user.

    Args:
        discord_user_id: The Discord user's ID (snowflake)
        tier: "starter", "pro", "whale", or "trial"
    """
    if not BOT_TOKEN or not discord_user_id:
        return False

    role_id = ROLE_IDS.get(tier)
    if not role_id:
        logger.warning(f"No role ID for tier '{tier}'")
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_user_id}/roles/{role_id}",
                headers=HEADERS,
            )
            if resp.status_code in (200, 204):
                logger.info(f"Assigned @{tier} role to user {discord_user_id}")
                return True
            elif resp.status_code == 404:
                logger.warning(f"User {discord_user_id} not found in guild — they may not have joined yet")
                return False
            else:
                logger.warning(f"Role assign failed: {resp.status_code} {resp.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"Role assign error: {e}")
        return False


async def remove_role(discord_user_id: str, tier: str = "starter") -> bool:
    """Remove a tier role from a Discord user."""
    if not BOT_TOKEN or not discord_user_id:
        return False

    role_id = ROLE_IDS.get(tier)
    if not role_id:
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_user_id}/roles/{role_id}",
                headers=HEADERS,
            )
            if resp.status_code in (200, 204):
                logger.info(f"Removed @{tier} role from user {discord_user_id}")
                return True
            else:
                logger.warning(f"Role remove failed: {resp.status_code}")
                return False
    except Exception as e:
        logger.error(f"Role remove error: {e}")
        return False


async def remove_all_tier_roles(discord_user_id: str) -> None:
    """Remove all tier roles from a user (on cancellation)."""
    for tier in TIER_ROLES:
        await remove_role(discord_user_id, tier)


async def upgrade_tier(discord_user_id: str, new_tier: str) -> bool:
    """Switch a user to a new tier (remove old roles, add new one)."""
    await remove_all_tier_roles(discord_user_id)
    return await assign_role(discord_user_id, new_tier)
