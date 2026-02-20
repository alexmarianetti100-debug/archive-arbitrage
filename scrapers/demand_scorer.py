"""
Demand Scorer — measures how fast items sell and how much competition exists.

Scores every item on a HOT → WARM → COLD scale based on:
1. Sold velocity — how many sold recently (Grailed sold index)
2. Active supply — how many are currently listed (Grailed active index)
3. Supply/demand ratio — few listings + lots of sales = HOT

This prevents us from alerting on high-margin items that sit for months.
"""

import asyncio
from typing import Optional, List
from dataclasses import dataclass, field

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from .grailed import GrailedScraper
except ImportError:
    from scrapers.grailed import GrailedScraper

try:
    from .comp_matcher import parse_title, build_search_queries, score_comp_similarity
except ImportError:
    from scrapers.comp_matcher import parse_title, build_search_queries, score_comp_similarity


@dataclass
class DemandResult:
    """Demand analysis for an item."""
    score: float              # 0.0 (dead) to 1.0 (fire)
    level: str                # "hot", "warm", "cold", "dead"
    sold_count: int           # Relevant sold items found
    active_count: int         # Competing active listings
    supply_demand_ratio: float  # active / sold (lower = better)
    avg_sold_price: float     # Average price of sold comps
    avg_active_price: float   # Average price of active listings
    undercut_pct: float       # How much cheaper active are vs sold (price pressure)
    sell_through_rate: float  # sold / (sold + active) — 0.0 to 1.0
    est_days_to_sell: float   # Estimated days to sell based on velocity (30 / sold_count)
    query_used: str           # Search query that found results
    reasoning: str            # Human-readable explanation


def _calculate_demand_score(
    sold_count: int,
    active_count: int,
    avg_sold_price: float,
    avg_active_price: float,
) -> tuple:
    """
    Calculate demand score from raw signals.
    
    Returns: (score, level, reasoning)
    """
    reasons = []
    score = 0.5  # Start neutral
    
    # === SOLD VELOCITY ===
    # More sold items = higher demand
    # Grailed sold index returns recent sales (roughly last 30-60 days)
    if sold_count >= 15:
        score += 0.25
        reasons.append(f"{sold_count} recent sales (high velocity)")
    elif sold_count >= 8:
        score += 0.15
        reasons.append(f"{sold_count} recent sales (good velocity)")
    elif sold_count >= 3:
        score += 0.05
        reasons.append(f"{sold_count} recent sales (moderate)")
    elif sold_count == 0:
        score -= 0.30
        reasons.append("No recent sales found (low demand)")
    else:
        score -= 0.10
        reasons.append(f"Only {sold_count} recent sales (slow)")
    
    # === SUPPLY PRESSURE ===
    # Fewer active listings = less competition
    if active_count == 0:
        score += 0.15
        reasons.append("No active listings (rare/scarce)")
    elif active_count <= 3:
        score += 0.10
        reasons.append(f"Only {active_count} active listings (low supply)")
    elif active_count <= 8:
        score += 0.0  # Neutral
        reasons.append(f"{active_count} active listings (moderate supply)")
    elif active_count <= 15:
        score -= 0.10
        reasons.append(f"{active_count} active listings (competitive)")
    else:
        score -= 0.20
        reasons.append(f"{active_count}+ active listings (saturated)")
    
    # === SUPPLY/DEMAND RATIO ===
    # sold_count / active_count — higher = better
    if sold_count > 0 and active_count > 0:
        ratio = sold_count / active_count
        if ratio >= 2.0:
            score += 0.15
            reasons.append(f"Sells {ratio:.1f}x faster than new listings appear")
        elif ratio >= 1.0:
            score += 0.05
            reasons.append("Balanced supply/demand")
        elif ratio >= 0.5:
            score -= 0.05
            reasons.append("Supply outpacing demand slightly")
        else:
            score -= 0.15
            reasons.append(f"Oversupplied ({1/ratio:.1f}x more listed than selling)")
    
    # === PRICE PRESSURE ===
    # If active listings are much cheaper than sold, market is dropping
    if avg_sold_price > 0 and avg_active_price > 0:
        undercut = (avg_active_price - avg_sold_price) / avg_sold_price
        if undercut < -0.20:
            score -= 0.10
            reasons.append(f"Active listings {abs(undercut)*100:.0f}% below sold prices (price dropping)")
        elif undercut > 0.10:
            score += 0.10
            reasons.append(f"Active listings {undercut*100:.0f}% above sold (prices rising)")
    
    # Clamp score to 0-1
    score = max(0.0, min(1.0, score))
    
    # Determine level
    if score >= 0.70:
        level = "hot"
    elif score >= 0.50:
        level = "warm"
    elif score >= 0.30:
        level = "cold"
    else:
        level = "dead"
    
    reasoning = " · ".join(reasons)
    return score, level, reasoning


async def score_demand(
    brand: str,
    title: str,
    max_results: int = 20,
) -> DemandResult:
    """
    Score demand for an item by checking sold velocity and active supply.
    
    Uses the smart query builder to search for relevant items.
    """
    parsed = parse_title(brand, title)
    queries = build_search_queries(parsed)
    
    # Use a mid-specificity query (not too broad, not too narrow)
    # Pick the first query with quality >= 0.7, or the best available
    search_query = queries[0][0]
    for q, quality in queries:
        if 0.6 <= quality <= 0.85:
            search_query = q
            break
    
    sold_items = []
    active_items = []
    
    async with GrailedScraper() as scraper:
        # Fetch sold items (demand signal)
        try:
            sold_raw = await scraper.search_sold(search_query, max_results=max_results)
            # Score similarity and keep relevant ones
            for item in sold_raw:
                sim = score_comp_similarity(parsed, item.title)
                if sim >= 0.3:  # Loose threshold — we want volume signal
                    sold_items.append((item, sim))
        except Exception:
            pass
        
        # Fetch active listings (supply signal)
        try:
            active_raw = await scraper.search(search_query, max_results=max_results)
            for item in active_raw:
                sim = score_comp_similarity(parsed, item.title)
                if sim >= 0.3:
                    active_items.append((item, sim))
        except Exception:
            pass
    
    # Calculate stats
    sold_count = len(sold_items)
    active_count = len(active_items)
    
    sold_prices = [item.price for item, _ in sold_items if item.price > 0]
    active_prices = [item.price for item, _ in active_items if item.price > 0]
    
    avg_sold = sum(sold_prices) / len(sold_prices) if sold_prices else 0
    avg_active = sum(active_prices) / len(active_prices) if active_prices else 0
    
    # Supply/demand ratio
    sd_ratio = active_count / sold_count if sold_count > 0 else 999
    
    # Undercut percentage
    undercut = 0.0
    if avg_sold > 0 and avg_active > 0:
        undercut = (avg_active - avg_sold) / avg_sold
    
    # Sell-through rate: sold / (sold + active) — higher = items move vs sit
    total_market = sold_count + active_count
    sell_through = sold_count / total_market if total_market > 0 else 0.0
    
    # Estimated days to sell: Grailed sold index ≈ 30-60 day window
    # Conservative estimate using 45-day window
    SOLD_WINDOW_DAYS = 45
    est_days = SOLD_WINDOW_DAYS / sold_count if sold_count > 0 else 999.0
    # Cap at 999 days (effectively "won't sell")
    est_days = min(est_days, 999.0)
    
    # Calculate score
    score, level, reasoning = _calculate_demand_score(
        sold_count, active_count, avg_sold, avg_active
    )
    
    return DemandResult(
        score=score,
        level=level,
        sold_count=sold_count,
        active_count=active_count,
        supply_demand_ratio=sd_ratio,
        avg_sold_price=avg_sold,
        avg_active_price=avg_active,
        undercut_pct=undercut,
        sell_through_rate=sell_through,
        est_days_to_sell=est_days,
        query_used=search_query,
        reasoning=reasoning,
    )


# CLI test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    tests = [
        ("rick owens", "Rick Owens DRKSHDW Cargo Pants Black"),
        ("rick owens", "Rick Owens Mainline Leather Stooges Jacket"),
        ("maison margiela", "Maison Margiela Tabi Boots"),
        ("raf simons", "Raf Simons x Fred Perry Polo Shirt"),
        ("helmut lang", "Helmut Lang Painter Denim Jeans"),
        ("number nine", "Number Nine Skull Cashmere Sweater"),
        ("chrome hearts", "Chrome Hearts Cemetery Cross Hoodie"),
    ]
    
    async def test():
        print("Demand Scorer Test")
        print("=" * 70)
        
        for brand, title in tests:
            result = await score_demand(brand, title)
            
            emoji = {"hot": "🔥", "warm": "🟡", "cold": "🔵", "dead": "💀"}[result.level]
            
            print(f"\n{emoji} {result.level.upper()} ({result.score:.0%}) — {title[:45]}...")
            print(f"   Sold: {result.sold_count} | Active: {result.active_count} | Ratio: {result.supply_demand_ratio:.1f}")
            print(f"   Avg sold: ${result.avg_sold_price:.0f} | Avg active: ${result.avg_active_price:.0f}")
            print(f"   {result.reasoning}")
    
    asyncio.run(test())
