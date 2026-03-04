"""
Google Trends Source — Detect breakout searches in archive fashion.

Uses Google Trends' public API (no key needed) to check search interest
for archive fashion terms and detect spikes/breakouts.

Weight: 0.5 (strong signal when something is spiking in search volume).
"""

import asyncio
import json
import logging
import os
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import TrendSignal, TrendSource

logger = logging.getLogger("trend.google_trends")

# Terms to monitor — brand + popular item combos
# Google Trends allows up to 5 terms per request, so we batch
TREND_TERMS = [
    # Batch 1: Top archive brands
    ["rick owens", "raf simons", "chrome hearts", "helmut lang", "maison margiela"],
    # Batch 2: Japanese + streetwear
    ["undercover jun takahashi", "number nine", "comme des garcons", "yohji yamamoto", "issey miyake"],
    # Batch 3: Luxury archive
    ["balenciaga", "bottega veneta", "dior homme", "saint laurent", "prada"],
    # Batch 4: Specific items
    ["rick owens geobasket", "margiela tabi", "chrome hearts ring", "raf simons bomber", "helmut lang jacket"],
    # Batch 5: More items
    ["balenciaga triple s", "rick owens ramones", "vivienne westwood", "jean paul gaultier", "junya watanabe"],
]

# Map search terms to canonical brand names
TERM_TO_BRAND = {
    "rick owens": "Rick Owens",
    "rick owens geobasket": "Rick Owens",
    "rick owens ramones": "Rick Owens",
    "raf simons": "Raf Simons",
    "raf simons bomber": "Raf Simons",
    "chrome hearts": "Chrome Hearts",
    "chrome hearts ring": "Chrome Hearts",
    "helmut lang": "Helmut Lang",
    "helmut lang jacket": "Helmut Lang",
    "maison margiela": "Maison Margiela",
    "margiela tabi": "Maison Margiela",
    "undercover jun takahashi": "Undercover",
    "number nine": "Number (N)ine",
    "comme des garcons": "Comme Des Garcons",
    "yohji yamamoto": "Yohji Yamamoto",
    "issey miyake": "Issey Miyake",
    "balenciaga": "Balenciaga",
    "balenciaga triple s": "Balenciaga",
    "bottega veneta": "Bottega Veneta",
    "dior homme": "Dior Homme",
    "saint laurent": "Saint Laurent",
    "prada": "Prada",
    "vivienne westwood": "Vivienne Westwood",
    "jean paul gaultier": "Jean Paul Gaultier",
    "junya watanabe": "Junya Watanabe",
}

TERM_TO_ITEM_TYPE = {
    "rick owens geobasket": "boots",
    "rick owens ramones": "sneakers",
    "margiela tabi": "boots",
    "chrome hearts ring": "accessories",
    "raf simons bomber": "jacket",
    "helmut lang jacket": "leather jacket",
    "balenciaga triple s": "sneakers",
}

HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trends", "gtrends_history.json")

# Google Trends explore API endpoint (public, no auth)
GTRENDS_API = "https://trends.google.com/trends/api/dailytrends"
GTRENDS_INTEREST = "https://trends.google.com/trends/api/widgetdata/multiline"


def _load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"term_scores": {}, "last_updated": None}


def _save_history(history: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    history["last_updated"] = datetime.utcnow().isoformat()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


class GoogleTrendsSource(TrendSource):
    """
    Checks Google Trends for breakout interest in archive fashion terms.
    
    Uses the Google Trends daily trends + related queries to find spikes.
    Falls back to comparing current interest vs historical baseline.
    """

    @property
    def name(self) -> str:
        return "google_trends"

    @property
    def weight(self) -> float:
        return 0.5

    async def fetch_signals(self) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        history = _load_history()
        prev_scores = history.get("term_scores", {})
        current_scores: dict[str, float] = {}

        logger.info("🔍 Checking Google Trends for archive fashion interest...")

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
            timeout=15.0,
            follow_redirects=True,
        ) as client:

            # Method 1: Check daily trending searches for fashion-related terms
            fashion_trending = await self._check_daily_trending(client)
            for term, score in fashion_trending:
                brand = self._match_brand(term)
                if brand:
                    signals.append(TrendSignal(
                        brand=brand,
                        item_type=self._match_item_type(term),
                        specific_query=term,
                        trend_score=min(1.0, score),
                        trend_direction="rising",
                        signal_sources=[self.name],
                    ))

            # Method 2: Check interest over time for our specific terms
            for batch in TREND_TERMS:
                try:
                    interest = await self._check_interest(client, batch)
                    for term, score in interest.items():
                        current_scores[term] = score
                        prev = prev_scores.get(term, score)

                        # Detect spike
                        if prev > 0:
                            change = (score - prev) / prev
                        else:
                            change = 0.5 if score > 30 else 0

                        if change > 0.2 or score > 70:
                            direction = "rising"
                        elif change < -0.2:
                            direction = "falling"
                        else:
                            direction = "stable"

                        brand = TERM_TO_BRAND.get(term, term.title())
                        item_type = TERM_TO_ITEM_TYPE.get(term, "general")

                        # Score: high interest + rising = hot
                        interest_score = score / 100.0
                        spike_score = max(0, min(1.0, change))
                        trend_score = interest_score * 0.5 + spike_score * 0.5

                        if trend_score > 0.15:
                            signals.append(TrendSignal(
                                brand=brand,
                                item_type=item_type,
                                specific_query=term,
                                trend_score=min(1.0, trend_score),
                                trend_direction=direction,
                                signal_sources=[self.name],
                                velocity_change=change,
                            ))

                    await asyncio.sleep(1.0)  # Rate limit
                except Exception as e:
                    logger.warning(f"  Failed batch {batch[:2]}: {e}")
                    continue

        # Update history
        history["term_scores"] = current_scores
        _save_history(history)

        # Deduplicate by brand (keep highest score per brand)
        best_per_brand: dict[str, TrendSignal] = {}
        for sig in signals:
            key = sig.brand
            if key not in best_per_brand or sig.trend_score > best_per_brand[key].trend_score:
                best_per_brand[key] = sig
        
        result = sorted(best_per_brand.values(), key=lambda s: s.trend_score, reverse=True)
        logger.info(f"  Generated {len(result)} Google Trends signals")
        return result

    async def _check_daily_trending(self, client: httpx.AsyncClient) -> list[tuple[str, float]]:
        """
        Check Google's daily trending searches for anything fashion-related.
        Returns [(term, relevance_score), ...]
        """
        results = []
        try:
            resp = await client.get(
                GTRENDS_API,
                params={"hl": "en-US", "tz": "-480", "geo": "US", "ns": "15"},
            )
            # Google returns ")]}'" prefix before JSON
            text = resp.text
            if text.startswith(")]}'"):
                text = text[5:]
            data = json.loads(text)

            searches = data.get("default", {}).get("trendingSearchesDays", [])
            for day in searches[:2]:  # Today and yesterday
                for search in day.get("trendingSearches", []):
                    title = search.get("title", {}).get("query", "").lower()
                    traffic = search.get("formattedTraffic", "0")
                    # Check if fashion-related
                    if self._is_fashion_related(title):
                        # Parse traffic (e.g. "200K+" -> 200000)
                        score = self._parse_traffic(traffic)
                        results.append((title, min(1.0, score / 500000)))

        except Exception as e:
            logger.debug(f"  Daily trending check failed: {e}")

        return results

    async def _check_interest(self, client: httpx.AsyncClient, terms: list[str]) -> dict[str, float]:
        """
        Check relative search interest for a batch of terms.
        Returns {term: interest_score (0-100)}.
        
        Uses Google Trends explore page scraping as a lightweight approach.
        """
        results = {}
        try:
            # Build the comparison URL params
            params = {
                "hl": "en-US",
                "tz": "-480",
                "req": json.dumps({
                    "comparisonItem": [
                        {"keyword": t, "geo": "US", "time": "today 1-m"} for t in terms
                    ],
                    "category": 0,
                    "property": "",
                }),
            }
            resp = await client.get(
                "https://trends.google.com/trends/api/explore",
                params=params,
            )
            text = resp.text
            if text.startswith(")]}'"):
                text = text[5:]
            
            data = json.loads(text)
            
            # Extract the interest over time widget token
            widgets = data.get("widgets", [])
            for widget in widgets:
                if widget.get("id") == "TIMESERIES":
                    token = widget.get("token", "")
                    req = widget.get("request", {})
                    if token and req:
                        interest_data = await self._fetch_timeseries(client, token, req)
                        if interest_data:
                            # Get the most recent data point for each term
                            for i, term in enumerate(terms):
                                if i < len(interest_data):
                                    results[term] = interest_data[i]
                    break
            
            # Fallback: if we couldn't get timeseries, assign neutral scores
            if not results:
                for term in terms:
                    results[term] = 50  # neutral baseline

        except Exception as e:
            logger.debug(f"  Interest check failed for {terms[:2]}: {e}")
            for term in terms:
                results[term] = 50  # neutral on failure

        return results

    async def _fetch_timeseries(self, client: httpx.AsyncClient, token: str, req: dict) -> list[float]:
        """Fetch timeseries data and return most recent values per term."""
        try:
            resp = await client.get(
                GTRENDS_INTEREST,
                params={
                    "hl": "en-US",
                    "tz": "-480",
                    "req": json.dumps(req),
                    "token": token,
                },
            )
            text = resp.text
            if text.startswith(")]}'"):
                text = text[5:]
            data = json.loads(text)
            
            timeline = data.get("default", {}).get("timelineData", [])
            if timeline:
                # Get the last data point (most recent)
                last = timeline[-1]
                values = last.get("value", [])
                return [float(v) for v in values]
        except Exception as e:
            logger.debug(f"  Timeseries fetch failed: {e}")
        return []

    def _is_fashion_related(self, term: str) -> bool:
        """Check if a trending search is related to archive fashion."""
        term_lower = term.lower()
        fashion_keywords = set(TERM_TO_BRAND.keys()) | {
            "fashion", "designer", "runway", "archive", "vintage clothing",
            "grailed", "streetwear", "haute couture",
        }
        return any(kw in term_lower for kw in fashion_keywords)

    def _parse_traffic(self, traffic: str) -> float:
        """Parse Google's formatted traffic string like '200K+' to a number."""
        traffic = traffic.replace("+", "").replace(",", "").strip()
        multiplier = 1
        if traffic.endswith("K"):
            multiplier = 1000
            traffic = traffic[:-1]
        elif traffic.endswith("M"):
            multiplier = 1000000
            traffic = traffic[:-1]
        try:
            return float(traffic) * multiplier
        except ValueError:
            return 0

    def _match_brand(self, term: str) -> Optional[str]:
        """Match a trending term to a known brand."""
        term_lower = term.lower()
        for pattern, brand in TERM_TO_BRAND.items():
            if pattern in term_lower:
                return brand
        return None

    def _match_item_type(self, term: str) -> str:
        """Match a trending term to an item type."""
        term_lower = term.lower()
        for pattern, item_type in TERM_TO_ITEM_TYPE.items():
            if pattern in term_lower:
                return item_type
        return "general"
