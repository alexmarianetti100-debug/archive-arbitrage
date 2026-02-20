"""
Cross-Platform Arbitrage Detector — Phase 4

Finds the same item listed on multiple platforms at different prices.
Identifies opportunities to buy low on one platform and sell high on another.

Usage:
    python detect_arbitrage.py --brand "rick owens" --min-gap 30
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))

from db.sqlite_models import get_items, Item
from scrapers.product_fingerprint import parse_title_to_fingerprint


@dataclass
class ArbitrageOpportunity:
    """A cross-platform arbitrage opportunity."""
    fingerprint_hash: str
    canonical_name: str
    
    # Buy side (low price)
    buy_platform: str
    buy_item: Item
    buy_price: float
    buy_url: str
    
    # Sell side (high price reference)
    sell_platform: str
    sell_reference_price: float  # Median sold price
    sell_comp_count: int
    
    # Profit calc
    platform_fees: float  # % taken by sell platform
    net_profit: float
    net_margin: float
    
    # Confidence
    confidence: str  # high, medium, low
    reasoning: str


# Platform fee structures
PLATFORM_FEES = {
    "grailed": 0.09,      # 9% + payment processing
    "poshmark": 0.20,     # 20% flat
    "ebay": 0.13,         # ~13% avg (10% eBay + PayPal)
    "depop": 0.10,        # 10%
}


class ArbitrageDetector:
    """Detect cross-platform arbitrage opportunities."""
    
    def __init__(self):
        self.min_profit = 50       # Minimum $ profit after fees
        self.min_margin = 0.25     # Minimum 25% margin
        self.min_price_gap = 0.20  # At least 20% price difference
    
    async def find_arbitrage_opportunities(
        self,
        brand: str = None,
        max_items: int = 500,
    ) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities across platforms.
        
        Strategy:
        1. Get active items from our database (already scraped from multiple sources)
        2. Group by product fingerprint
        3. For each product with multiple listings, check for price gaps
        4. Cross-reference with sold comp data for sell price estimate
        """
        from db.sqlite_models import get_product_by_fingerprint, get_product_price_stats
        
        opportunities = []
        
        # Get active items
        items = get_items(status="active", brand=brand, limit=max_items)
        print(f"Checking {len(items)} items for arbitrage...")
        
        # Group by fingerprint
        fingerprint_groups: Dict[str, List[Item]] = {}
        for item in items:
            fp = parse_title_to_fingerprint(item.brand or "", item.title)
            if not fp.is_complete():
                continue
            
            if fp.fingerprint_hash not in fingerprint_groups:
                fingerprint_groups[fp.fingerprint_hash] = []
            fingerprint_groups[fp.fingerprint_hash].append(item)
        
        print(f"Found {len(fingerprint_groups)} unique products")
        
        # Check each product group
        for fp_hash, group_items in fingerprint_groups.items():
            # Need at least 2 listings to compare
            if len(group_items) < 2:
                continue
            
            # Get product data
            product = get_product_by_fingerprint(fp_hash)
            if not product or product.total_sales < 3:
                continue  # Need sold data to estimate sell price
            
            # Get price stats
            price_stats = get_product_price_stats(product.id, days=90)
            if price_stats["count"] < 3:
                continue
            
            sold_median = price_stats["avg"]
            
            # Find cheapest listing
            cheapest = min(group_items, key=lambda x: x.source_price + x.source_shipping)
            buy_price = cheapest.source_price + cheapest.source_shipping
            
            # Calculate potential profit selling at market rate
            for platform, fee_rate in PLATFORM_FEES.items():
                sell_price = sold_median * 0.95  # Price slightly below market
                platform_fee = sell_price * fee_rate
                net_revenue = sell_price - platform_fee
                net_profit = net_revenue - buy_price
                net_margin = net_profit / buy_price if buy_price > 0 else 0
                
                # Check if profitable
                if net_profit >= self.min_profit and net_margin >= self.min_margin:
                    # Check confidence
                    confidence = "low"
                    if product.is_high_velocity and price_stats["count"] >= 8:
                        confidence = "high"
                    elif product.sales_30d >= 3:
                        confidence = "medium"
                    
                    reasoning = (
                        f"Buy on {cheapest.source} for ${buy_price:.0f}, "
                        f"sell on {platform} at ${sell_price:.0f} (median). "
                        f"{price_stats['count']} sold comps, {product.sales_30d} sales/30d. "
                        f"After {fee_rate*100:.0f}% fees: ${net_profit:.0f} profit ({net_margin*100:.0f}% margin)"
                    )
                    
                    opp = ArbitrageOpportunity(
                        fingerprint_hash=fp_hash,
                        canonical_name=product.canonical_name,
                        buy_platform=cheapest.source,
                        buy_item=cheapest,
                        buy_price=buy_price,
                        buy_url=cheapest.source_url,
                        sell_platform=platform,
                        sell_reference_price=sold_median,
                        sell_comp_count=price_stats["count"],
                        platform_fees=fee_rate,
                        net_profit=net_profit,
                        net_margin=net_margin,
                        confidence=confidence,
                        reasoning=reasoning,
                    )
                    opportunities.append(opp)
        
        # Sort by net profit
        opportunities.sort(key=lambda x: -x.net_profit)
        return opportunities
    
    def detect_same_item(self, item1: Item, item2: Item) -> float:
        """
        Detect if two items are the same product.
        Returns similarity score 0.0 to 1.0.
        """
        # Parse both titles
        fp1 = parse_title_to_fingerprint(item1.brand or "", item1.title)
        fp2 = parse_title_to_fingerprint(item2.brand or "", item2.title)
        
        # Check fingerprint similarity
        if fp1.fingerprint_hash == fp2.fingerprint_hash:
            return 1.0
        
        # Check title similarity
        title_sim = SequenceMatcher(None, item1.title.lower(), item2.title.lower()).ratio()
        
        # Check image similarity (if available)
        image_sim = 0.0
        if item1.images and item2.images:
            # Could use perceptual hashing here
            pass
        
        # Weighted combination
        return (title_sim * 0.7) + (image_sim * 0.3)


async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Find cross-platform arbitrage opportunities")
    parser.add_argument("--brand", type=str, help="Filter by brand")
    parser.add_argument("--min-profit", type=float, default=50, help="Minimum profit")
    parser.add_argument("--min-margin", type=float, default=0.25, help="Minimum margin")
    parser.add_argument("--max-items", type=int, default=500, help="Max items to check")
    parser.add_argument("--authenticated-only", action="store_true", help="Only include authenticated items")
    
    args = parser.parse_args()
    
    detector = ArbitrageDetector()
    detector.min_profit = args.min_profit
    detector.min_margin = args.min_margin
    
    print("🔍 Cross-Platform Arbitrage Scanner")
    print("=" * 70)
    
    opportunities = await detector.find_arbitrage_opportunities(
        brand=args.brand,
        max_items=args.max_items,
    )
    
    print(f"\n✅ Found {len(opportunities)} arbitrage opportunities\n")
    
    # Group by confidence
    high_conf = [o for o in opportunities if o.confidence == "high"]
    med_conf = [o for o in opportunities if o.confidence == "medium"]
    low_conf = [o for o in opportunities if o.confidence == "low"]
    
    if high_conf:
        print(f"\n🔥 HIGH CONFIDENCE ({len(high_conf)}):")
        print("-" * 70)
        for opp in high_conf[:5]:
            print(f"\n{opp.canonical_name}")
            print(f"  Buy: ${opp.buy_price:.0f} on {opp.buy_platform}")
            print(f"  Sell: ${opp.sell_reference_price:.0f} on {opp.sell_platform}")
            print(f"  Net Profit: ${opp.net_profit:.0f} ({opp.net_margin*100:.0f}% margin)")
            print(f"  {opp.reasoning[:100]}...")
    
    if med_conf:
        print(f"\n\n📊 MEDIUM CONFIDENCE ({len(med_conf)}):")
        print("-" * 70)
        for opp in med_conf[:5]:
            print(f"\n{opp.canonical_name}")
            print(f"  Profit: ${opp.net_profit:.0f} ({opp.net_margin*100:.0f}% margin)")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
