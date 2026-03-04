"""
Editorial Source — Scrape fashion news sites for archive fashion mentions.

Monitors Highsnobiety, Hypebeast, and Grailed's editorial/blog for mentions
of archive designers and items. Celebrity sightings, collection drops, and
editorial features all drive demand spikes.

Weight: 0.3 (editorial is a leading indicator but noisy).
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import TrendSignal, TrendSource

logger = logging.getLogger("trend.editorial")

# RSS/JSON feeds to check
FEEDS = [
    {
        "name": "Highsnobiety",
        "url": "https://www.highsnobiety.com/feed/",
        "type": "rss",
    },
    {
        "name": "Hypebeast",
        "url": "https://hypebeast.com/feed",
        "type": "rss",
    },
    {
        "name": "Grailed Blog",
        "url": "https://www.grailed.com/drycleanonly/feed",
        "type": "rss",
    },
]

# Brand detection in article titles/descriptions
BRAND_KEYWORDS: dict[str, str] = {
    "rick owens": "Rick Owens",
    "raf simons": "Raf Simons",
    "chrome hearts": "Chrome Hearts",
    "helmut lang": "Helmut Lang",
    "maison margiela": "Maison Margiela",
    "margiela": "Maison Margiela",
    "comme des garcons": "Comme Des Garcons",
    "comme des garçons": "Comme Des Garcons",
    "cdg": "Comme Des Garcons",
    "undercover": "Undercover",
    "number (n)ine": "Number (N)ine",
    "number nine": "Number (N)ine",
    "yohji yamamoto": "Yohji Yamamoto",
    "balenciaga": "Balenciaga",
    "saint laurent": "Saint Laurent",
    "prada": "Prada",
    "dior": "Dior Homme",
    "dior homme": "Dior Homme",
    "bottega veneta": "Bottega Veneta",
    "bottega": "Bottega Veneta",
    "vivienne westwood": "Vivienne Westwood",
    "jean paul gaultier": "Jean Paul Gaultier",
    "gaultier": "Jean Paul Gaultier",
    "issey miyake": "Issey Miyake",
    "junya watanabe": "Junya Watanabe",
    "julius": "Julius",
    "celine": "Celine",
    "hedi slimane": "Dior Homme",  # maps to the designer era people care about
    "kapital": "Kapital",
    "visvim": "Visvim",
    "needles": "Needles",
    "sacai": "Sacai",
}

# Context keywords that indicate the article is about items people would buy
PURCHASE_INTENT_KEYWORDS = [
    "buy", "shop", "collection", "drop", "release", "lookbook", "runway",
    "archive", "vintage", "grail", "resale", "resell", "invest", "price",
    "wore", "wearing", "spotted in", "celebrity", "outfit", "style",
    "collaboration", "collab", "capsule", "limited", "exclusive",
    "restock", "sell out", "sold out",
]

HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trends", "editorial_history.json")
USER_AGENT = "ArchiveArbitrage/1.0 (editorial trend analysis)"


def _load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"seen_urls": [], "brand_mentions": {}, "last_updated": None}


def _save_history(history: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    # Keep only last 500 seen URLs
    history["seen_urls"] = history.get("seen_urls", [])[-500:]
    history["last_updated"] = datetime.utcnow().isoformat()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


class EditorialSource(TrendSource):
    """
    Scrapes fashion editorial sites for archive brand mentions.
    New coverage of a brand = potential demand spike.
    """

    @property
    def name(self) -> str:
        return "editorial"

    @property
    def weight(self) -> float:
        return 0.3

    async def fetch_signals(self) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        history = _load_history()
        seen_urls = set(history.get("seen_urls", []))
        prev_mentions = history.get("brand_mentions", {})
        current_mentions: dict[str, int] = {}

        logger.info("🔍 Scanning fashion editorial sites...")

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            for feed in FEEDS:
                try:
                    articles = await self._fetch_feed(client, feed)
                    new_articles = [a for a in articles if a.get("url") not in seen_urls]
                    logger.debug(f"  {feed['name']}: {len(new_articles)} new articles")

                    for article in new_articles:
                        brands = self._extract_brands(article)
                        has_intent = self._has_purchase_intent(article)

                        for brand in brands:
                            current_mentions[brand] = current_mentions.get(brand, 0) + 1
                            if has_intent:
                                current_mentions[brand] += 1  # Double weight for purchase intent

                        seen_urls.add(article.get("url", ""))

                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"  Failed {feed['name']}: {e}")
                    continue

        # Generate signals from mention counts
        for brand, count in current_mentions.items():
            prev_count = prev_mentions.get(brand, 0)

            # Spike detection
            if prev_count > 0:
                change = (count - prev_count) / prev_count
            else:
                change = 1.0 if count >= 2 else 0.3

            direction = "rising" if change > 0.3 else ("falling" if change < -0.3 else "stable")

            # Score: more mentions + spike = hotter
            volume_score = min(1.0, count / 5)
            spike_score = max(0, min(1.0, change))
            trend_score = volume_score * 0.6 + spike_score * 0.4

            if trend_score > 0.1:
                signals.append(TrendSignal(
                    brand=brand,
                    item_type="general",
                    specific_query=brand.lower(),
                    trend_score=min(1.0, trend_score),
                    trend_direction=direction,
                    signal_sources=[self.name],
                    velocity_change=change,
                ))

        # Update history
        history["seen_urls"] = list(seen_urls)
        # Rolling average for mention baseline
        for brand, count in current_mentions.items():
            old = prev_mentions.get(brand, count)
            prev_mentions[brand] = old * 0.7 + count * 0.3
        history["brand_mentions"] = prev_mentions
        _save_history(history)

        signals.sort(key=lambda s: s.trend_score, reverse=True)
        logger.info(f"  Generated {len(signals)} editorial signals")
        return signals

    async def _fetch_feed(self, client: httpx.AsyncClient, feed: dict) -> list[dict]:
        """Fetch and parse an RSS feed into article dicts."""
        resp = await client.get(feed["url"])
        resp.raise_for_status()
        return self._parse_rss(resp.text, feed["name"])

    def _parse_rss(self, xml_text: str, source: str) -> list[dict]:
        """Simple RSS parser — extracts title, description, link from <item> tags."""
        articles = []
        # Quick regex-based RSS parsing (no lxml dependency)
        items = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
        for item_xml in items[:30]:  # Max 30 articles per feed
            title = self._extract_tag(item_xml, "title")
            desc = self._extract_tag(item_xml, "description")
            link = self._extract_tag(item_xml, "link")
            pub_date = self._extract_tag(item_xml, "pubDate")

            if title:
                articles.append({
                    "title": title,
                    "description": desc or "",
                    "url": link or "",
                    "pub_date": pub_date or "",
                    "source": source,
                })
        return articles

    def _extract_tag(self, xml: str, tag: str) -> Optional[str]:
        """Extract content from an XML tag."""
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # Strip CDATA
            content = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", content, flags=re.DOTALL)
            # Strip HTML tags
            content = re.sub(r"<[^>]+>", " ", content)
            return content.strip()
        return None

    def _extract_brands(self, article: dict) -> list[str]:
        """Extract mentioned brands from article title + description."""
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        found = set()

        # Check longest patterns first
        sorted_keywords = sorted(BRAND_KEYWORDS.keys(), key=len, reverse=True)
        for pattern in sorted_keywords:
            if pattern in text:
                brand = BRAND_KEYWORDS[pattern]
                found.add(brand)

        return list(found)

    def _has_purchase_intent(self, article: dict) -> bool:
        """Check if article has purchase-intent keywords."""
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        return any(kw in text for kw in PURCHASE_INTENT_KEYWORDS)
