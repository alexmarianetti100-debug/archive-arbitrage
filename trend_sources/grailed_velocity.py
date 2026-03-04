"""
Grailed Velocity Source — The primary trend signal.

Analyzes Grailed sold data to detect:
1. Items selling faster than their 30-day average (velocity spikes)
2. Items whose sold price is rising (price momentum)
3. New items that just started selling (emerging trends)

Stores historical data in data/trends/trend_history.json for comparisons.
"""

import asyncio
import json
import logging
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Optional

from .base import TrendSignal, TrendSource

logger = logging.getLogger("trend.grailed_velocity")

# How many items to sample per query
ITEMS_PER_QUERY = 60

# Broad queries to sample general market movement
SAMPLE_QUERIES = [
    "",           # recent sold across everything
    "archive",
    "vintage",
    "rare",
    "grail",
]

# Category queries for breadth
CATEGORY_QUERIES = [
    "leather jacket", "cargo pants", "boots", "sneakers",
    "hoodie", "knit sweater", "denim jacket", "coat",
    "bag", "t-shirt", "shirt", "shorts",
]

# Archive brand queries — focused on the big movers
BRAND_QUERIES = [
    "rick owens", "raf simons", "chrome hearts", "helmut lang",
    "maison margiela", "comme des garcons", "undercover",
    "number nine", "yohji yamamoto", "balenciaga",
    "saint laurent", "prada", "dior homme", "vivienne westwood",
    "jean paul gaultier", "issey miyake", "julius",
    "bottega veneta", "celine", "junya watanabe",
]

HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trends", "trend_history.json")
HISTORY_MAX_DAYS = 30


def _load_history() -> dict:
    """Load trend history from disk."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Corrupt trend_history.json, starting fresh")
    return {"snapshots": [], "last_updated": None}


def _save_history(history: dict):
    """Save trend history to disk."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    # Prune old snapshots
    cutoff = (datetime.utcnow() - timedelta(days=HISTORY_MAX_DAYS)).isoformat()
    history["snapshots"] = [s for s in history["snapshots"] if s.get("timestamp", "") > cutoff]
    history["last_updated"] = datetime.utcnow().isoformat()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def _extract_item_key(title: str, brand: str) -> str:
    """Normalize an item into a groupable key like 'rick owens:geobasket'."""
    title_lower = title.lower()
    brand_lower = brand.lower()

    # Remove brand name from title to get the item descriptor
    descriptor = title_lower
    for token in brand_lower.split():
        descriptor = descriptor.replace(token, "")
    descriptor = " ".join(descriptor.split())  # collapse whitespace

    # Extract the most meaningful 2-3 words as the item key
    # Skip filler words
    filler = {"size", "sz", "us", "eu", "uk", "mens", "womens", "vintage",
              "authentic", "nwt", "bnwt", "pre-owned", "used", "new", "the",
              "a", "an", "in", "for", "with", "and", "or", "from", "by",
              "ss", "fw", "aw", "ss24", "fw24", "ss23", "fw23", "ss25", "fw25",
              "black", "white", "grey", "gray", "red", "blue", "brown", "green"}
    words = [w for w in descriptor.split() if w not in filler and len(w) > 1]

    # Take first 3 meaningful words
    key_words = words[:3]
    if not key_words:
        key_words = ["general"]

    return f"{brand_lower}:{' '.join(key_words)}"


def _detect_category(title: str) -> str:
    """Detect item category from title."""
    title_lower = title.lower()
    categories = {
        "leather jacket": ["leather jacket", "stooges", "intarsia", "riders jacket"],
        "jacket": ["jacket", "blazer", "bomber", "varsity", "trucker"],
        "coat": ["coat", "overcoat", "trench", "parka", "puffer"],
        "pants": ["pants", "trousers", "cargos", "cargo"],
        "jeans": ["jeans", "denim"],
        "boots": ["boots", "boot", "geobasket", "dunks", "ramones", "kiss boot", "tabi"],
        "sneakers": ["sneakers", "shoes", "runners", "trainers", "triple s", "track", "speed"],
        "hoodie": ["hoodie", "hooded"],
        "sweater": ["sweater", "knit", "cardigan"],
        "t-shirt": ["t-shirt", "tee", "tshirt"],
        "shirt": ["shirt", "button"],
        "bag": ["bag", "backpack", "tote"],
        "accessories": ["pendant", "ring", "bracelet", "necklace", "chain", "glasses", "hat", "cap"],
    }
    for cat, keywords in categories.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    return "other"


class GrailedVelocitySource(TrendSource):
    """
    Analyzes Grailed sold data velocity to find what's trending.
    
    Primary signal source — weight 1.0.
    """

    @property
    def name(self) -> str:
        return "grailed_velocity"

    @property
    def weight(self) -> float:
        return 1.0

    async def fetch_signals(self) -> list[TrendSignal]:
        """
        Fetch Grailed sold data, compare to historical baselines,
        and return trend signals for items with unusual velocity or price movement.
        """
        # Import here to avoid circular imports
        from scrapers.grailed import GrailedScraper

        history = _load_history()
        today_snapshot = {"timestamp": datetime.utcnow().isoformat(), "items": {}}
        signals: list[TrendSignal] = []

        # Build historical baselines from past snapshots
        baselines = self._build_baselines(history)

        logger.info("🔍 Fetching Grailed sold data for velocity analysis...")

        async with GrailedScraper() as scraper:
            # Sample sold items across brands
            all_items = []
            queries = BRAND_QUERIES + SAMPLE_QUERIES + CATEGORY_QUERIES[:6]

            for query in queries:
                try:
                    items = await scraper.search_sold(query, max_results=ITEMS_PER_QUERY)
                    all_items.extend(items)
                    logger.debug(f"  '{query}': {len(items)} sold items")
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"  Failed to fetch '{query}': {e}")
                    continue

        # Deduplicate
        seen_ids = set()
        unique = []
        for item in all_items:
            if item.source_id not in seen_ids:
                seen_ids.add(item.source_id)
                unique.append(item)

        logger.info(f"  Fetched {len(unique)} unique sold items")

        # Group by item key
        item_groups: dict[str, list] = defaultdict(list)
        for item in unique:
            brand = (item.brand or "").strip()
            if not brand or len(brand) < 2:
                # Try extracting from raw_data
                raw = item.raw_data or {}
                designers = raw.get("designers", [])
                if designers:
                    d = designers[0]
                    brand = d.get("name", "") if isinstance(d, dict) else str(d)
                if not brand:
                    continue

            key = _extract_item_key(item.title, brand)
            item_groups[key].append(item)

        # Analyze each group
        for key, items in item_groups.items():
            if len(items) < 2:
                continue

            brand = key.split(":")[0]
            item_desc = key.split(":", 1)[1] if ":" in key else "general"
            category = _detect_category(items[0].title)

            # Current metrics
            current_count = len(items)
            prices = [i.price for i in items if i.price > 0]
            avg_price = sum(prices) / len(prices) if prices else 0

            # Save to today's snapshot
            today_snapshot["items"][key] = {
                "count": current_count,
                "avg_price": avg_price,
                "sample_title": items[0].title[:80],
            }

            # Compare to baseline
            baseline = baselines.get(key, {})
            baseline_count = baseline.get("avg_count", 0)
            baseline_price = baseline.get("avg_price", 0)

            # Calculate velocity change
            velocity_change = 0.0
            if baseline_count > 0:
                velocity_change = (current_count - baseline_count) / baseline_count
            
            # Calculate price change
            price_change = 0.0
            if baseline_price > 0 and avg_price > 0:
                price_change = (avg_price - baseline_price) / baseline_price

            # Determine trend direction
            if velocity_change > 0.3 or price_change > 0.15:
                direction = "rising"
            elif velocity_change < -0.3 or price_change < -0.15:
                direction = "falling"
            else:
                direction = "stable"

            # Score: combine volume, velocity spike, and price momentum
            volume_score = min(1.0, current_count / 15)  # 15+ items = max volume score
            velocity_score = max(0, min(1.0, velocity_change))  # Positive velocity = good
            price_score = max(0, min(1.0, price_change * 2))  # Price rising = good
            # Emerging bonus: if no baseline exists, this is new/emerging
            emerging_bonus = 0.2 if not baseline else 0.0

            trend_score = (
                volume_score * 0.4
                + velocity_score * 0.35
                + price_score * 0.15
                + emerging_bonus * 0.1
            )

            # Only emit signal if it's worth searching
            if trend_score < 0.15 and direction != "rising":
                continue

            # Build a good search query from the key
            search_query = f"{brand} {item_desc}".strip()

            signals.append(TrendSignal(
                brand=brand.title(),
                item_type=category,
                specific_query=search_query,
                trend_score=min(1.0, trend_score),
                trend_direction=direction,
                signal_sources=[self.name],
                est_sold_volume=current_count,
                avg_sold_price=avg_price,
                velocity_change=velocity_change,
                price_change=price_change,
            ))

        # Save today's snapshot to history
        history["snapshots"].append(today_snapshot)
        _save_history(history)

        # Sort by score
        signals.sort(key=lambda s: s.trend_score, reverse=True)
        logger.info(f"  Generated {len(signals)} trend signals (top: {signals[0].specific_query if signals else 'none'})")
        return signals

    def _build_baselines(self, history: dict) -> dict:
        """
        Build baseline metrics from historical snapshots.
        Returns {item_key: {"avg_count": float, "avg_price": float}}
        """
        baselines: dict[str, dict] = defaultdict(lambda: {"counts": [], "prices": []})

        for snapshot in history.get("snapshots", []):
            for key, data in snapshot.get("items", {}).items():
                baselines[key]["counts"].append(data.get("count", 0))
                baselines[key]["prices"].append(data.get("avg_price", 0))

        result = {}
        for key, data in baselines.items():
            counts = data["counts"]
            prices = [p for p in data["prices"] if p > 0]
            result[key] = {
                "avg_count": sum(counts) / len(counts) if counts else 0,
                "avg_price": sum(prices) / len(prices) if prices else 0,
            }
        return result
