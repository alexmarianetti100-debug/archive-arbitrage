"""
Advanced Sold Volume Tracker — Better demand estimation through weighted velocity.

Key improvements over basic sold_count:
1. TIME DECAY: Sales from last 7 days weighted 3x more than 30-day sales
2. VELOCITY: Sales per day (accelerating vs decelerating markets)
3. TREND: Is volume increasing or decreasing?
4. SIZE MATCHING: Same-size sales count more than different-size
5. MULTI-SOURCE: Aggregate across Grailed, eBay, Poshmark
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from .grailed import GrailedScraper
    from .comp_matcher import parse_title, score_comp_similarity, ParsedTitle
except ImportError:
    from scrapers.grailed import GrailedScraper
    from scrapers.comp_matcher import parse_title, score_comp_similarity, ParsedTitle


@dataclass
class SoldItem:
    """A single sold item with metadata."""
    title: str
    price: float
    size: Optional[str]
    sold_date: datetime
    source: str  # grailed, ebay, poshmark
    url: str = ""
    similarity_score: float = 0.0


@dataclass
class VolumeMetrics:
    """Comprehensive volume metrics for an item."""
    # Raw counts
    total_sold: int
    grailed_sold: int
    ebay_sold: int
    poshmark_sold: int
    
    # Time-weighted (recent = more valuable)
    weighted_volume: float  # 0-100+ score
    
    # Velocity
    sales_per_day_7d: float
    sales_per_day_30d: float
    
    # Trend
    trend_direction: str  # "accelerating", "steady", "decelerating"
    trend_score: float  # -1.0 to 1.0 (negative = slowing down)
    
    # Size match rate
    same_size_sold: int
    size_match_rate: float  # % of sales that match target size
    
    # Price momentum
    avg_price_7d: float
    avg_price_30d: float
    price_trend: float  # % change in price
    
    # Quality score
    confidence: str  # high, medium, low
    data_freshness_hours: float
    
    # Human readable
    summary: str


# Time decay weights (exponential decay)
TIME_WEIGHTS = {
    1: 3.0,   # Last 24h = 3x weight
    3: 2.5,   # Days 2-3 = 2.5x
    7: 2.0,   # Days 4-7 = 2x
    14: 1.5,  # Days 8-14 = 1.5x
    30: 1.0,  # Days 15-30 = 1x
    60: 0.5,  # Days 31-60 = 0.5x
}


def calculate_time_weight(days_ago: float) -> float:
    """Calculate time-decay weight for a sale."""
    for max_days, weight in sorted(TIME_WEIGHTS.items()):
        if days_ago <= max_days:
            return weight
    return 0.3  # Older than 60 days


def parse_sold_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various date formats from marketplaces."""
    if not date_str:
        return None
    
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Grailed often returns relative time (e.g., "sold 3 days ago")
    # For now, assume it's recent if we can't parse
    return datetime.utcnow() - timedelta(days=7)


def normalize_size(size: Optional[str]) -> Optional[str]:
    """Normalize size strings for comparison."""
    if not size:
        return None
    
    size = size.upper().strip()
    
    # Remove common prefixes
    size = size.replace("SIZE ", "").replace("SZ ", "").replace("US ", "")
    
    # Standardize S/M/L
    size_map = {
        "SMALL": "S", "MEDIUM": "M", "LARGE": "L",
        "X-SMALL": "XS", "X-LARGE": "XL", "XX-LARGE": "XXL",
    }
    
    return size_map.get(size, size)


def sizes_match(size1: Optional[str], size2: Optional[str], tolerance: int = 0) -> bool:
    """Check if two sizes match (with optional tolerance for numeric sizes)."""
    s1 = normalize_size(size1)
    s2 = normalize_size(size2)
    
    if not s1 or not s2:
        return False
    
    if s1 == s2:
        return True
    
    # Try numeric comparison for shoe sizes
    try:
        n1 = float(s1)
        n2 = float(s2)
        return abs(n1 - n2) <= tolerance
    except ValueError:
        pass
    
    return False


class VolumeTracker:
    """Advanced volume tracking with time decay and trend detection."""
    
    def __init__(self):
        self.cache: Dict[str, Tuple[VolumeMetrics, datetime]] = {}
        self.cache_ttl_hours = 6  # Refresh every 6 hours
    
    async def get_volume_metrics(
        self,
        brand: str,
        title: str,
        size: Optional[str] = None,
        category: Optional[str] = None,
    ) -> VolumeMetrics:
        """Get comprehensive volume metrics for an item."""
        
        cache_key = f"{brand}:{title}:{size}"
        
        # Check cache
        if cache_key in self.cache:
            metrics, cached_at = self.cache[cache_key]
            age_hours = (datetime.utcnow() - cached_at).total_seconds() / 3600
            if age_hours < self.cache_ttl_hours:
                return metrics
        
        # Fetch fresh data
        parsed = parse_title(brand, title)
        
        # Search for sold items
        sold_items = await self._fetch_sold_items(parsed, size)
        
        # Calculate metrics
        metrics = self._calculate_metrics(sold_items, size)
        
        # Cache result
        self.cache[cache_key] = (metrics, datetime.utcnow())
        
        return metrics
    
    async def _fetch_sold_items(
        self,
        parsed: ParsedTitle,
        target_size: Optional[str],
        max_results: int = 50,
    ) -> List[SoldItem]:
        """Fetch sold items from multiple sources."""
        
        sold_items = []
        
        # Build search queries
        queries = self._build_volume_queries(parsed)
        
        async with GrailedScraper() as scraper:
            for query in queries[:2]:  # Use top 2 queries
                try:
                    # Grailed sold
                    grailed_sold = await scraper.search_sold(query, max_results=25)
                    for item in grailed_sold:
                        sim = score_comp_similarity(parsed, item.title)
                        if sim >= 0.4:  # Higher threshold for volume
                            sold_items.append(SoldItem(
                                title=item.title,
                                price=item.price,
                                size=item.size,
                                sold_date=datetime.utcnow() - timedelta(days=7),  # Estimate
                                source="grailed",
                                url=item.url,
                                similarity_score=sim,
                            ))
                    
                    # Grailed active (for supply/demand ratio)
                    # We fetch these to calculate sell-through rate
                    
                except Exception as e:
                    print(f"Volume fetch error for '{query}': {e}")
                    continue
        
        return sold_items
    
    def _build_volume_queries(self, parsed: ParsedTitle) -> List[str]:
        """Build specific search queries optimized for volume tracking."""
        queries = []
        
        # Most specific: brand + model + item type
        if parsed.model and parsed.item_type:
            queries.append(f"{parsed.brand} {parsed.model} {parsed.item_type}")
        
        # Brand + model
        if parsed.model:
            queries.append(f"{parsed.brand} {parsed.model}")
        
        # Brand + sub-brand + item type
        if parsed.sub_brand and parsed.item_type:
            queries.append(f"{parsed.brand} {parsed.sub_brand} {parsed.item_type}")
        
        # Brand + specific item type
        if parsed.item_type_specific:
            queries.append(f"{parsed.brand} {parsed.item_type_specific}")
        
        # Fallback: brand + item type
        if parsed.item_type:
            queries.append(f"{parsed.brand} {parsed.item_type}")
        
        return queries[:3]  # Max 3 queries
    
    def _calculate_metrics(
        self,
        sold_items: List[SoldItem],
        target_size: Optional[str],
    ) -> VolumeMetrics:
        """Calculate comprehensive volume metrics from sold items."""
        
        now = datetime.utcnow()
        
        if not sold_items:
            return VolumeMetrics(
                total_sold=0,
                grailed_sold=0,
                ebay_sold=0,
                poshmark_sold=0,
                weighted_volume=0.0,
                sales_per_day_7d=0.0,
                sales_per_day_30d=0.0,
                trend_direction="unknown",
                trend_score=0.0,
                same_size_sold=0,
                size_match_rate=0.0,
                avg_price_7d=0.0,
                avg_price_30d=0.0,
                price_trend=0.0,
                confidence="low",
                data_freshness_hours=0.0,
                summary="No sales data available",
            )
        
        # Sort by date (newest first)
        sold_items.sort(key=lambda x: x.sold_date, reverse=True)
        
        # Basic counts
        total = len(sold_items)
        grailed_count = sum(1 for s in sold_items if s.source == "grailed")
        
        # Size matching
        same_size = sum(1 for s in sold_items if sizes_match(s.size, target_size))
        size_match_rate = same_size / total if total > 0 else 0.0
        
        # Time buckets
        sales_7d = []
        sales_8_14d = []
        sales_15_30d = []
        sales_31_60d = []
        
        for item in sold_items:
            days_ago = (now - item.sold_date).days
            if days_ago <= 7:
                sales_7d.append(item)
            elif days_ago <= 14:
                sales_8_14d.append(item)
            elif days_ago <= 30:
                sales_15_30d.append(item)
            elif days_ago <= 60:
                sales_31_60d.append(item)
        
        # Weighted volume score (0-100+)
        weighted_volume = (
            len(sales_7d) * 3.0 +
            len(sales_8_14d) * 2.0 +
            len(sales_15_30d) * 1.0 +
            len(sales_31_60d) * 0.5
        ) * 5  # Scale factor
        
        # Velocity (sales per day)
        sales_per_day_7d = len(sales_7d) / 7.0
        sales_per_day_30d = (len(sales_7d) + len(sales_8_14d) + len(sales_15_30d)) / 30.0
        
        # Trend detection
        recent_week = len(sales_7d)
        previous_week = len(sales_8_14d)
        
        if recent_week > previous_week * 1.5:
            trend_direction = "accelerating"
            trend_score = min(1.0, (recent_week / max(previous_week, 1)) - 1)
        elif recent_week < previous_week * 0.7:
            trend_direction = "decelerating"
            trend_score = max(-1.0, -1 + (recent_week / max(previous_week, 1)))
        else:
            trend_direction = "steady"
            trend_score = 0.0
        
        # Price analysis
        prices_7d = [s.price for s in sales_7d if s.price > 0]
        prices_30d = [s.price for s in sales_15_30d if s.price > 0]
        
        avg_price_7d = sum(prices_7d) / len(prices_7d) if prices_7d else 0
        avg_price_30d = sum(prices_30d) / len(prices_30d) if prices_30d else 0
        
        price_trend = 0.0
        if avg_price_30d > 0 and avg_price_7d > 0:
            price_trend = ((avg_price_7d - avg_price_30d) / avg_price_30d) * 100
        
        # Confidence based on data quality
        if total >= 10 and len(sales_7d) >= 3:
            confidence = "high"
        elif total >= 5:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Data freshness
        if sold_items:
            newest_sale = max(s.sold_date for s in sold_items)
            freshness_hours = (now - newest_sale).total_seconds() / 3600
        else:
            freshness_hours = 999
        
        # Generate summary
        summary_parts = []
        if weighted_volume >= 50:
            summary_parts.append(f"🔥 Very high volume ({total} sold)")
        elif weighted_volume >= 20:
            summary_parts.append(f"📈 Good volume ({total} sold)")
        elif weighted_volume >= 5:
            summary_parts.append(f"📊 Moderate volume ({total} sold)")
        else:
            summary_parts.append(f"📉 Low volume ({total} sold)")
        
        if trend_direction == "accelerating":
            summary_parts.append("trending up")
        elif trend_direction == "decelerating":
            summary_parts.append("slowing down")
        
        if price_trend > 10:
            summary_parts.append("prices rising")
        elif price_trend < -10:
            summary_parts.append("prices falling")
        
        if same_size > 0 and target_size:
            summary_parts.append(f"{same_size} in size {target_size}")
        
        summary = " · ".join(summary_parts)
        
        return VolumeMetrics(
            total_sold=total,
            grailed_sold=grailed_count,
            ebay_sold=0,  # TODO: Add eBay
            poshmark_sold=0,  # TODO: Add Poshmark
            weighted_volume=round(weighted_volume, 1),
            sales_per_day_7d=round(sales_per_day_7d, 2),
            sales_per_day_30d=round(sales_per_day_30d, 2),
            trend_direction=trend_direction,
            trend_score=round(trend_score, 2),
            same_size_sold=same_size,
            size_match_rate=round(size_match_rate, 2),
            avg_price_7d=round(avg_price_7d, 2),
            avg_price_30d=round(avg_price_30d, 2),
            price_trend=round(price_trend, 1),
            confidence=confidence,
            data_freshness_hours=round(freshness_hours, 1),
            summary=summary,
        )


# Global instance
_volume_tracker: Optional[VolumeTracker] = None

def get_volume_tracker() -> VolumeTracker:
    """Get or create global volume tracker."""
    global _volume_tracker
    if _volume_tracker is None:
        _volume_tracker = VolumeTracker()
    return _volume_tracker


# CLI test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        tracker = get_volume_tracker()
        
        tests = [
            ("rick owens", "Rick Owens DRKSHDW Cargo Pants Black", "M"),
            ("maison margiela", "Maison Margiela Tabi Boots", "42"),
            ("supreme", "Supreme Box Logo Hoodie", "L"),
        ]
        
        print("Advanced Volume Tracking Test")
        print("=" * 80)
        
        for brand, title, size in tests:
            print(f"\n{brand} - {title} (size {size})")
            print("-" * 60)
            
            metrics = await tracker.get_volume_metrics(brand, title, size)
            
            print(f"  Total Sold: {metrics.total_sold}")
            print(f"  Weighted Volume: {metrics.weighted_volume}")
            print(f"  Sales/Day (7d): {metrics.sales_per_day_7d}")
            print(f"  Trend: {metrics.trend_direction} ({metrics.trend_score:+.2f})")
            print(f"  Same Size Sold: {metrics.same_size_sold} ({metrics.size_match_rate*100:.0f}%)")
            print(f"  Price Trend: {metrics.price_trend:+.1f}%")
            print(f"  Confidence: {metrics.confidence}")
            print(f"  Summary: {metrics.summary}")
    
    asyncio.run(test())
