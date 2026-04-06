"""
Pipeline → Supabase deal sync.

Pushes qualified deals from local SQLite to Supabase Postgres
so the user dashboard can display them.

Runs:
  - After each pipeline cycle (called from gap_hunter.py)
  - On a cron schedule as fallback (every 15 min)

Handles deduplication via source + source_id unique constraint.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("supabase_sync")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


def sync_deal_to_supabase(
    source: str,
    source_id: str,
    source_url: str,
    title: str,
    brand: str = "",
    category: str = "",
    size: str = "",
    condition: str = "",
    buy_price: float = 0,
    market_price: float = 0,
    profit: float = 0,
    margin_percent: float = 0,
    grade: str = "",
    quality_score: float = 0,
    fire_level: int = 0,
    tier: str = "beginner",
    auth_confidence: float = 0,
    auth_grade: str = "",
    comp_count: int = 0,
    comp_snapshots: list = None,
    images: list = None,
    season_name: str = "",
    demand_level: str = "",
) -> bool:
    """Push a single deal to Supabase. Uses upsert (insert or update on conflict)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False

    payload = {
        "source": source,
        "source_id": source_id,
        "source_url": source_url,
        "title": title,
        "brand": brand or None,
        "category": category or None,
        "size": size or None,
        "condition": condition or None,
        "buy_price": buy_price,
        "market_price": market_price or None,
        "profit": profit or None,
        "margin_percent": margin_percent or None,
        "grade": grade or None,
        "quality_score": quality_score,
        "fire_level": fire_level,
        "tier": tier,
        "auth_confidence": auth_confidence,
        "auth_grade": auth_grade or None,
        "comp_count": comp_count,
        "comp_snapshots": json.dumps(comp_snapshots or []),
        "images": images or [],
        "season_name": season_name or None,
        "demand_level": demand_level or None,
    }

    try:
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/deals",
            headers=HEADERS,
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.debug(f"Synced deal: {brand} — {title[:40]}")
            return True
        elif resp.status_code == 409:
            logger.debug(f"Deal already exists: {source}/{source_id}")
            return True
        else:
            logger.warning(f"Supabase sync failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Supabase sync error: {e}")
        return False


def sync_deal_from_pipeline(
    item,
    deal=None,
    signals=None,
    auth_result=None,
    tier: str = "beginner",
) -> bool:
    """Convenience function called from gap_hunter.py after a deal is dispatched."""
    source_id = getattr(item, "source_id", "") or ""
    if not source_id:
        import hashlib
        url = getattr(item, "url", "") or ""
        source_id = f"gap_{hashlib.md5(url.encode()).hexdigest()[:12]}" if url else ""

    images = getattr(item, "images", []) or []
    comp_snapshots = []
    if deal and hasattr(deal, "comp_snapshots") and deal.comp_snapshots:
        comp_snapshots = [
            {"title": c.get("title", ""), "price": c.get("price", 0), "url": c.get("url", "")}
            for c in (deal.comp_snapshots if isinstance(deal.comp_snapshots, list) else [])
        ]

    return sync_deal_to_supabase(
        source=getattr(item, "source", "") or "",
        source_id=source_id,
        source_url=getattr(item, "url", "") or "",
        title=getattr(item, "title", "") or "",
        brand=getattr(item, "brand", "") or "",
        category=getattr(item, "category", "") or "",
        size=getattr(item, "size", "") or "",
        condition=getattr(item, "condition", "") or "",
        buy_price=float(getattr(item, "price", 0) or 0),
        market_price=float(getattr(deal, "sold_avg", 0) or 0) if deal else 0,
        profit=float(getattr(deal, "profit_estimate", 0) or 0) if deal else 0,
        margin_percent=float(getattr(deal, "gap_percent", 0) or 0) * 100 if deal else 0,
        grade="A" if signals and getattr(signals, "fire_level", 0) >= 3 else "B" if signals and getattr(signals, "fire_level", 0) >= 2 else "C",
        quality_score=float(getattr(signals, "quality_score", 0) or 0) if signals else 0,
        fire_level=int(getattr(signals, "fire_level", 0) or 0) if signals else 0,
        tier=tier,
        auth_confidence=float(getattr(auth_result, "confidence", 0) or 0) if auth_result else 0,
        auth_grade=getattr(auth_result, "grade", "") if auth_result else "",
        comp_count=int(getattr(deal, "sold_count", 0) or 0) if deal else 0,
        comp_snapshots=comp_snapshots,
        images=images[:5],
        season_name=getattr(signals, "season_name", "") if signals else "",
        demand_level=getattr(signals, "demand_level", "") if signals else "",
    )


def bulk_sync_from_sqlite(limit: int = 100) -> int:
    """Sync recent deals from local SQLite to Supabase. Used for initial backfill."""
    from db.sqlite_models import _get_conn

    conn = _get_conn()
    cursor = conn.execute("""
        SELECT source, source_id, source_url, title, brand, category, size, condition,
               source_price, market_price, exact_profit, margin_percent,
               grade, demand_score, auth_confidence,
               comp_count, images, exact_season, demand_level
        FROM items
        WHERE grade IN ('A', 'B', 'C')
        AND market_price IS NOT NULL
        AND source_price IS NOT NULL
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    synced = 0
    for row in cursor.fetchall():
        (source, source_id, source_url, title, brand, category, size, condition,
         buy_price, market_price, profit, margin, grade, quality_score,
         auth_conf, comp_count, images_str, season, demand) = row

        images = []
        if images_str:
            try:
                images = json.loads(images_str) if isinstance(images_str, str) else images_str
            except (json.JSONDecodeError, TypeError):
                pass

        tier = "whale" if (profit or 0) >= 500 else "pro" if (profit or 0) >= 300 else "beginner"

        ok = sync_deal_to_supabase(
            source=source or "",
            source_id=source_id or f"legacy_{synced}",
            source_url=source_url or "",
            title=title or "",
            brand=brand or "",
            category=category or "",
            size=size or "",
            condition=condition or "",
            buy_price=float(buy_price or 0),
            market_price=float(market_price or 0),
            profit=float(profit or 0),
            margin_percent=float(margin or 0),
            grade=grade or "C",
            quality_score=float(quality_score or 0),
            fire_level=3 if grade == "A" else 2 if grade == "B" else 1,
            tier=tier,
            auth_confidence=float(auth_conf or 0),
            comp_count=int(comp_count or 0),
            images=images[:5] if isinstance(images, list) else [],
            season_name=season or "",
            demand_level=demand or "",
        )
        if ok:
            synced += 1

    conn.close()
    logger.info(f"Bulk synced {synced}/{limit} deals to Supabase")
    return synced


def update_user_subscription(
    email: str,
    tier: str = "starter",
    stripe_customer_id: str = "",
    stripe_subscription_id: str = "",
    status: str = "active",
) -> bool:
    """Update a user's subscription in Supabase profiles.

    Called from Stripe webhook on checkout.session.completed.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False

    try:
        # Find user by email
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/profiles?email=eq.{email}&select=id",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            timeout=10,
        )

        if resp.status_code != 200 or not resp.json():
            logger.warning(f"User not found in Supabase: {email}")
            return False

        user_id = resp.json()[0]["id"]

        # Update profile
        update_resp = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "tier": tier,
                "stripe_customer_id": stripe_customer_id or None,
                "stripe_subscription_id": stripe_subscription_id or None,
                "subscription_status": status,
            },
            timeout=10,
        )

        if update_resp.status_code in (200, 204):
            logger.info(f"Updated subscription for {email}: tier={tier}, status={status}")
            return True
        else:
            logger.warning(f"Profile update failed: {update_resp.status_code} {update_resp.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Subscription update error: {e}")
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if "--backfill" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--backfill") + 1]) if len(sys.argv) > sys.argv.index("--backfill") + 1 else 100
        synced = bulk_sync_from_sqlite(limit)
        print(f"Backfilled {synced} deals to Supabase")
    else:
        print("Usage:")
        print("  --backfill [N]   Sync N recent deals from SQLite to Supabase")
