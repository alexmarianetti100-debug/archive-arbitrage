"""
Cross-Platform Arbitrage Finder

Finds price gaps between platforms for the same items.
Buy low on one platform, sell high on another.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from pathlib import Path

import httpx

logger = logging.getLogger("platform_arbitrage")


@dataclass
class PlatformListing:
    """Item listing on a specific platform."""
    title: str
    price: float
    platform: str
    url: str
    item_id: str
    condition: Optional[str]
    seller_rating: Optional[float]
    images: List[str]
    listed_date: Optional[str]


@dataclass
class ArbitrageMatch:
    """Cross-platform arbitrage opportunity."""
    buy_listing: PlatformListing
    sell_platform: str
    sell_price_estimate: float
    buy_price: float
    gross_margin: float
    net_margin: float
    net_margin_percent: float
    fees_total: float
    recommendation: str
    confidence: str
    notes: List[str]


class PlatformArbitrageFinder:
    """Find arbitrage opportunities across platforms."""
    
    # Platform fee structures
    PLATFORM_FEES = {
        'grailed': {
            'seller_fee': 0.09,  # 9% commission
            'payment_fee': 0.029 + 0.30,  # 2.9% + $0.30
            'buyer_premium': 0.0,
            'avg_sell_premium': 1.40,  # Items sell 40% above Vinted/eBay
        },
        'therealreal': {
            'seller_fee': 0.30,  # 30% commission
            'payment_fee': 0,
            'buyer_premium': 0.0,
            'avg_sell_premium': 1.50,
        },
        'vestiaire': {
            'seller_fee': 0.15,
            'payment_fee': 0.03,
            'buyer_premium': 0.0,
            'avg_sell_premium': 1.35,
        },
        'fashionphile': {
            'seller_fee': 0.30,
            'payment_fee': 0,
            'buyer_premium': 0.0,
            'avg_sell_premium': 1.45,
        },
    }
    
    # Buy platforms (cheap sources)
    BUY_PLATFORMS = ['vinted', 'ebay', 'poshmark', 'depop', 'mercari']
    
    # Sell platforms (premium destinations)
    SELL_PLATFORMS = ['grailed', 'therealreal', 'vestiaire', 'fashionphile']
    
    # High-value targets for arbitrage
    ARBITRAGE_TARGETS = [
        # Jewelry - High margins
        {'name': 'Chrome Hearts Cross Pendant', 'keywords': ['chrome hearts', 'cross', 'pendant'], 'category': 'jewelry'},
        {'name': 'Chrome Hearts Forever Ring', 'keywords': ['chrome hearts', 'forever', 'ring'], 'category': 'jewelry'},

        # Fashion - Volume
        {'name': 'Rick Owens Geobasket', 'keywords': ['rick owens', 'geobasket'], 'category': 'fashion'},
        {'name': 'Margiela Tabi Boots', 'keywords': ['margiela', 'tabi'], 'category': 'fashion'},
    ]
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.opportunities_file = self.data_dir / "platform_arbitrage.jsonl"
        self.seen_matches: set = set()
    
    async def search_platform(self, platform: str, query: str) -> List[PlatformListing]:
        """Search a specific platform for items."""
        listings = []
        
        # This would integrate with existing scrapers
        # For now, return empty (would be populated by actual scraper calls)
        
        return listings
    
    def calculate_arbitrage(self, 
                          buy_listing: PlatformListing,
                          sell_platform: str) -> Optional[ArbitrageMatch]:
        """Calculate arbitrage opportunity."""
        
        # Get fee structure
        fees = self.PLATFORM_FEES.get(sell_platform)
        if not fees:
            return None
        
        # Estimate sell price
        sell_price = buy_listing.price * fees['avg_sell_premium']
        
        # Calculate fees
        seller_fee = sell_price * fees['seller_fee']
        payment_fee = sell_price * fees['payment_fee'] if fees['payment_fee'] < 1 else fees['payment_fee']
        total_fees = seller_fee + payment_fee
        
        # Calculate margins
        gross_margin = sell_price - buy_listing.price
        net_margin = gross_margin - total_fees
        net_margin_percent = (net_margin / buy_listing.price) * 100 if buy_listing.price > 0 else 0
        
        # Determine recommendation
        if net_margin_percent >= 50:
            recommendation = "STRONG_BUY"
            confidence = "HIGH"
        elif net_margin_percent >= 30:
            recommendation = "BUY"
            confidence = "MEDIUM"
        elif net_margin_percent >= 20:
            recommendation = "WATCH"
            confidence = "LOW"
        else:
            return None  # Not worth it
        
        # Generate notes
        notes = []
        notes.append(f"Buy on {buy_listing.platform} for ${buy_listing.price:.0f}")
        notes.append(f"Sell on {sell_platform} for ~${sell_price:.0f}")
        notes.append(f"Fees: ${total_fees:.0f} ({fees['seller_fee']:.0%} + payment)")
        
        if buy_listing.seller_rating and buy_listing.seller_rating < 4.5:
            notes.append("Low seller rating - verify authenticity")
            confidence = "LOW"
        
        return ArbitrageMatch(
            buy_listing=buy_listing,
            sell_platform=sell_platform,
            sell_price_estimate=sell_price,
            buy_price=buy_listing.price,
            gross_margin=gross_margin,
            net_margin=net_margin,
            net_margin_percent=net_margin_percent,
            fees_total=total_fees,
            recommendation=recommendation,
            confidence=confidence,
            notes=notes,
        )
    
    async def find_arbitrage_opportunities(self, min_margin: float = 25.0) -> List[ArbitrageMatch]:
        """Find cross-platform arbitrage opportunities."""
        opportunities = []
        
        for target in self.ARBITRAGE_TARGETS:
            logger.info(f"Searching arbitrage for: {target['name']}")
            
            # Search buy platforms
            for buy_platform in self.BUY_PLATFORMS:
                try:
                    listings = await self.search_platform(buy_platform, target['name'])
                    
                    for listing in listings:
                        # Check each sell platform
                        for sell_platform in self.SELL_PLATFORMS:
                            match = self.calculate_arbitrage(listing, sell_platform)
                            
                            if match and match.net_margin_percent >= min_margin:
                                opportunities.append(match)
                                
                                # Save opportunity
                                self._save_opportunity(match)
                
                except Exception as e:
                    logger.error(f"Error searching {buy_platform}: {e}")
                
                await asyncio.sleep(1)  # Rate limiting
        
        # Sort by margin
        opportunities.sort(key=lambda x: x.net_margin_percent, reverse=True)
        
        return opportunities[:20]
    
    def _save_opportunity(self, match: ArbitrageMatch):
        """Save arbitrage opportunity to file."""
        with open(self.opportunities_file, 'a') as f:
            f.write(json.dumps({
                'item_title': match.buy_listing.title,
                'buy_platform': match.buy_listing.platform,
                'buy_price': match.buy_price,
                'sell_platform': match.sell_platform,
                'sell_price_estimate': match.sell_price_estimate,
                'net_margin': match.net_margin,
                'net_margin_percent': match.net_margin_percent,
                'recommendation': match.recommendation,
                'confidence': match.confidence,
                'found_at': datetime.now().isoformat(),
            }) + '\n')
    
    def get_report(self) -> Dict:
        """Generate arbitrage report."""
        if not self.opportunities_file.exists():
            return {'total': 0, 'opportunities': []}
        
        opportunities = []
        with open(self.opportunities_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    opportunities.append(data)
                except:
                    continue
        
        # Recent opportunities
        recent = [
            o for o in opportunities
            if (datetime.now() - datetime.fromisoformat(o['found_at'])).days < 7
        ]
        
        strong_buy = [o for o in recent if o['recommendation'] == 'STRONG_BUY']
        buy = [o for o in recent if o['recommendation'] == 'BUY']
        
        return {
            'total': len(opportunities),
            'recent': len(recent),
            'strong_buy': len(strong_buy),
            'buy': len(buy),
            'avg_margin': sum(o['net_margin_percent'] for o in recent) / len(recent) if recent else 0,
            'top_opportunities': sorted(recent, key=lambda x: x['net_margin_percent'], reverse=True)[:10],
        }


# Convenience functions
_finder = None

def get_finder() -> PlatformArbitrageFinder:
    """Get or create finder singleton."""
    global _finder
    if _finder is None:
        _finder = PlatformArbitrageFinder()
    return _finder


async def find_platform_arbitrage(min_margin: float = 25.0) -> List[ArbitrageMatch]:
    """Find cross-platform arbitrage opportunities."""
    finder = get_finder()
    return await finder.find_arbitrage_opportunities(min_margin)


def get_arbitrage_report() -> Dict:
    """Get arbitrage report."""
    finder = get_finder()
    return finder.get_report()


# CLI helper
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        report = get_arbitrage_report()
        print("\n📊 Cross-Platform Arbitrage Report\n")
        print(f"Total opportunities: {report['total']}")
        print(f"Recent (7 days): {report['recent']}")
        print(f"STRONG BUY: {report['strong_buy']}")
        print(f"BUY: {report['buy']}")
        print(f"Avg margin: {report['avg_margin']:.1f}%")
        
        if report['top_opportunities']:
            print("\n🔥 Top Opportunities:")
            for opp in report['top_opportunities'][:5]:
                print(f"  {opp['item_title'][:50]}...")
                print(f"    Buy: ${opp['buy_price']:.0f} on {opp['buy_platform']}")
                print(f"    Sell: ~${opp['sell_price_estimate']:.0f} on {opp['sell_platform']}")
                print(f"    Net margin: {opp['net_margin_percent']:.1f}% ({opp['recommendation']})")
    else:
        print("Usage: python platform_arbitrage.py --report")
