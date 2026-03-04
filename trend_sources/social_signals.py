"""
Reddit Social Signal Source — Detect hype from fashion subreddits.

Monitors archive fashion subreddits for mention frequency.
When a brand/item is mentioned significantly more than usual, it's a signal.

Weight: 0.4 (social signals are noisy, but useful for catching emerging hype).
"""

import asyncio
import json
import logging
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import TrendSignal, TrendSource

logger = logging.getLogger("trend.reddit")

# Subreddits to monitor
SUBREDDITS = [
    "malefashion",
    "japanesestreetwear",
    "rickowens",
    "QualityReps",
    "avantgardefashion",
    "malefashionadvice",
    "streetwear",
]

# Brand detection patterns (lowercase)
# Maps pattern -> canonical brand name
BRAND_PATTERNS: dict[str, str] = {
    "rick owens": "Rick Owens",
    "rick": "Rick Owens",
    "rickowens": "Rick Owens",
    "drkshdw": "Rick Owens",
    "geobasket": "Rick Owens",
    "ramones": "Rick Owens",
    "raf simons": "Raf Simons",
    "raf": "Raf Simons",
    "chrome hearts": "Chrome Hearts",
    "helmut lang": "Helmut Lang",
    "margiela": "Maison Margiela",
    "maison margiela": "Maison Margiela",
    "mmm": "Maison Margiela",
    "tabi": "Maison Margiela",
    "comme des garcons": "Comme Des Garcons",
    "cdg": "Comme Des Garcons",
    "undercover": "Undercover",
    "jun takahashi": "Undercover",
    "number nine": "Number (N)ine",
    "number (n)ine": "Number (N)ine",
    "n(n)": "Number (N)ine",
    "yohji": "Yohji Yamamoto",
    "yohji yamamoto": "Yohji Yamamoto",
    "balenciaga": "Balenciaga",
    "saint laurent": "Saint Laurent",
    "slp": "Saint Laurent",
    "prada": "Prada",
    "dior homme": "Dior Homme",
    "hedi slimane": "Dior Homme",
    "vivienne westwood": "Vivienne Westwood",
    "jean paul gaultier": "Jean Paul Gaultier",
    "jpg": "Jean Paul Gaultier",
    "issey miyake": "Issey Miyake",
    "homme plisse": "Issey Miyake",
    "julius": "Julius",
    "julius_7": "Julius",
    "bottega veneta": "Bottega Veneta",
    "bottega": "Bottega Veneta",
    "celine": "Celine",
    "junya watanabe": "Junya Watanabe",
    "junya": "Junya Watanabe",
    "kapital": "Kapital",
    "visvim": "Visvim",
    "hysteric glamour": "Hysteric Glamour",
    "needles": "Needles",
}

# Item-type patterns to detect specific items being discussed
ITEM_PATTERNS: dict[str, str] = {
    "geobasket": "boots",
    "dunks": "sneakers",
    "ramones": "sneakers",
    "kiss boots": "boots",
    "stooges": "leather jacket",
    "cargo": "pants",
    "bomber": "jacket",
    "leather jacket": "leather jacket",
    "hoodie": "hoodie",
    "sweater": "sweater",
    "triple s": "sneakers",
    "track": "sneakers",
    "speed trainer": "sneakers",
    "tabi": "boots",
    "pendant": "accessories",
    "ring": "accessories",
    "cross": "accessories",
    "sneakers": "sneakers",
    "boots": "boots",
    "jacket": "jacket",
    "pants": "pants",
    "jeans": "jeans",
    "bag": "bag",
}

BASELINE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trends", "reddit_baseline.json")
REDDIT_USER_AGENT = "ArchiveArbitrage/1.0 (trend analysis)"


def _load_baseline() -> dict:
    if os.path.exists(BASELINE_FILE):
        try:
            with open(BASELINE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"brand_counts": {}, "last_updated": None}


def _save_baseline(baseline: dict):
    os.makedirs(os.path.dirname(BASELINE_FILE), exist_ok=True)
    baseline["last_updated"] = datetime.utcnow().isoformat()
    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)


class RedditSignalSource(TrendSource):
    """
    Scans Reddit archive fashion subs for brand/item mentions.
    Compares to historical baseline to detect hype spikes.
    """

    @property
    def name(self) -> str:
        return "reddit"

    @property
    def weight(self) -> float:
        return 0.4

    async def fetch_signals(self) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        baseline = _load_baseline()
        baseline_brands = baseline.get("brand_counts", {})

        brand_mentions: Counter = Counter()
        brand_items: dict[str, Counter] = defaultdict(Counter)
        brand_contexts: dict[str, list[str]] = defaultdict(list)

        logger.info("🔍 Scanning Reddit for archive fashion mentions...")

        async with httpx.AsyncClient(
            headers={"User-Agent": REDDIT_USER_AGENT},
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            for sub in SUBREDDITS:
                try:
                    posts = await self._fetch_subreddit(client, sub)
                    for post in posts:
                        text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
                        self._extract_mentions(text, brand_mentions, brand_items, brand_contexts)
                    logger.debug(f"  r/{sub}: {len(posts)} posts")
                    await asyncio.sleep(0.5)  # Reddit rate limit
                except Exception as e:
                    logger.warning(f"  Failed r/{sub}: {e}")
                    continue

        logger.info(f"  Detected mentions for {len(brand_mentions)} brands")

        # Compare to baseline and generate signals
        for brand, count in brand_mentions.most_common(30):
            baseline_count = baseline_brands.get(brand, 0)

            # Calculate spike ratio
            if baseline_count > 0:
                spike = (count - baseline_count) / baseline_count
            else:
                spike = 1.0 if count >= 3 else 0.5  # New brand appearing

            # Determine direction
            if spike > 0.5:
                direction = "rising"
            elif spike < -0.3:
                direction = "falling"
            else:
                direction = "stable"

            # Score based on mention volume and spike
            volume_score = min(1.0, count / 20)
            spike_score = max(0, min(1.0, spike))
            trend_score = volume_score * 0.5 + spike_score * 0.5

            if trend_score < 0.1:
                continue

            # Find the most mentioned item type for this brand
            top_items = brand_items[brand].most_common(3)
            item_type = top_items[0][0] if top_items else "general"

            # Build query
            if item_type != "general":
                query = f"{brand} {item_type}"
            else:
                query = brand

            signals.append(TrendSignal(
                brand=brand,
                item_type=item_type,
                specific_query=query,
                trend_score=min(1.0, trend_score),
                trend_direction=direction,
                signal_sources=[self.name],
                est_sold_volume=0,  # Reddit doesn't tell us sales
                avg_sold_price=0,
                velocity_change=spike,
            ))

        # Update baseline (rolling average)
        for brand, count in brand_mentions.items():
            old = baseline_brands.get(brand, count)
            baseline_brands[brand] = old * 0.7 + count * 0.3  # Exponential moving avg
        baseline["brand_counts"] = baseline_brands
        _save_baseline(baseline)

        signals.sort(key=lambda s: s.trend_score, reverse=True)
        logger.info(f"  Generated {len(signals)} Reddit signals")
        return signals

    async def _fetch_subreddit(self, client: httpx.AsyncClient, subreddit: str, limit: int = 50) -> list[dict]:
        """Fetch recent posts from a subreddit via JSON API."""
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        resp = await client.get(url, params={"limit": limit, "raw_json": 1})
        resp.raise_for_status()
        data = resp.json()
        children = data.get("data", {}).get("children", [])
        return [c.get("data", {}) for c in children]

    def _extract_mentions(
        self,
        text: str,
        brand_counter: Counter,
        brand_items: dict[str, Counter],
        brand_contexts: dict[str, list[str]],
    ):
        """Extract brand and item mentions from text."""
        # Check brand patterns (longest match first to avoid "raf" matching before "raf simons")
        sorted_patterns = sorted(BRAND_PATTERNS.keys(), key=len, reverse=True)
        found_brands = set()

        for pattern in sorted_patterns:
            if pattern in text:
                brand = BRAND_PATTERNS[pattern]
                if brand not in found_brands:
                    found_brands.add(brand)
                    brand_counter[brand] += 1
                    brand_contexts[brand].append(text[:200])

        # Check item patterns for detected brands
        for brand in found_brands:
            for item_pattern, item_type in ITEM_PATTERNS.items():
                if item_pattern in text:
                    brand_items[brand][item_type] += 1
