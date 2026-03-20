"""
Japan Auction Arbitrage System

Finds luxury items on Japanese auction sites selling 30-50% below US prices.
Japan is a major source for luxury arbitrage due to:
- Weak yen (favorable exchange rates)
- Strong auction culture
- Lower domestic demand for Western luxury
- Authentic items (Japan strict on counterfeits)
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("japan_arbitrage")


@dataclass
class JapanAuctionItem:
    """Item found on Japan auction site."""
    title: str
    price_jpy: int
    price_usd: float
    platform: str
    auction_id: str
    url: str
    image_url: Optional[str]
    end_time: Optional[datetime]
    seller_rating: Optional[float]
    bids: int
    query_matched: str
    
    @property
    def potential_margin(self) -> float:
        """Calculate potential margin if sold on Grailed."""
        # Assume Grailed price is 40% higher than Japan price
        grailed_price = self.price_usd * 1.4
        # Fees: 9% Grailed + 3% payment + shipping/auth
        fees = grailed_price * 0.15
        return grailed_price - self.price_usd - fees
    
    @property
    def roi_percent(self) -> float:
        """Return on investment percentage."""
        if self.price_usd == 0:
            return 0
        return (self.potential_margin / self.price_usd) * 100


@dataclass
class ArbitrageOpportunity:
    """Complete arbitrage opportunity with buy/sell details."""
    japan_item: JapanAuctionItem
    us_market_price: float
    margin_usd: float
    margin_percent: float
    recommendation: str  # 'STRONG_BUY', 'BUY', 'WATCH', 'SKIP'
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    notes: List[str]


class JapanAuctionScraper:
    """Scraper for Japanese auction platforms."""
    
    # Exchange rate (update periodically)
    JPY_TO_USD = 0.0067  # ~150 JPY = 1 USD
    
    # Platform configurations
    PLATFORMS = {
        'buyee_yahoo': {
            'name': 'Buyee (Yahoo Auctions)',
            'search_url': 'https://buyee.jp/item/search/query/{query}',
            'item_selector': '.item',
            'title_selector': '.itemTitle',
            'price_selector': '.itemPrice',
            'image_selector': '.itemImage img',
            'link_selector': '.itemTitle a',
        },
        'brand_auc': {
            'name': 'Brand-Auc',
            'search_url': 'https://www.brand-auc.com/en/search?keyword={query}',
            'item_selector': '.product-item',
            'title_selector': '.product-title',
            'price_selector': '.product-price',
            'image_selector': '.product-image img',
            'link_selector': '.product-title a',
        },
    }
    
    # High-value targets for Japan sourcing
    LUXURY_TARGETS = [
        # Watches - Best margins
        {'query': 'ロレックス デイトジャスト', 'en': 'rolex datejust', 'category': 'watch'},
        {'query': 'ロレックス サブマリーナ', 'en': 'rolex submariner', 'category': 'watch'},
        {'query': 'カルティエ タンク', 'en': 'cartier tank', 'category': 'watch'},
        {'query': 'カルティエ サントス', 'en': 'cartier santos', 'category': 'watch'},
        {'query': 'オメガ スピードマスター', 'en': 'omega speedmaster', 'category': 'watch'},
        
        # Bags - Good volume
        {'query': 'エルメス バーキン', 'en': 'hermes birkin', 'category': 'bag'},
        {'query': 'エルメス ケリー', 'en': 'hermes kelly', 'category': 'bag'},
        {'query': 'シャネル マトラッセ', 'en': 'chanel classic flap', 'category': 'bag'},
        {'query': 'ルイヴィトン スピーディ', 'en': 'louis vuitton speedy', 'category': 'bag'},
        {'query': 'ルイヴィトン ネヴァーフル', 'en': 'louis vuitton neverfull', 'category': 'bag'},
        
        # Jewelry - High margins
        {'query': 'クロムハーツ リング', 'en': 'chrome hearts ring', 'category': 'jewelry'},
        {'query': 'クロムハーツ ネックレス', 'en': 'chrome hearts necklace', 'category': 'jewelry'},
        
        # Fashion - Volume play
        {'query': 'リックオウエンス ダンク', 'en': 'rick owens dunks', 'category': 'fashion'},
        {'query': 'マルジェラ タビ', 'en': 'margiela tabi', 'category': 'fashion'},
    ]
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.opportunities_file = self.data_dir / "japan_arbitrage.jsonl"
        self.seen_auctions: set = self._load_seen()
    
    def _load_seen(self) -> set:
        """Load previously seen auction IDs."""
        seen = set()
        if self.opportunities_file.exists():
            with open(self.opportunities_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        seen.add(data['auction_id'])
                    except:
                        continue
        return seen
    
    async def search_buyee(self, query: str, en_query: str) -> List[JapanAuctionItem]:
        """Search Buyee (Yahoo Auctions Japan proxy)."""
        items = []
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"https://buyee.jp/item/search/query/{query}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    logger.warning(f"Buyee returned {response.status_code}")
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse items
                for item_el in soup.select('.item')[:15]:  # Top 15 results
                    try:
                        # Extract title
                        title_el = item_el.select_one('.itemTitle')
                        title = title_el.get_text(strip=True) if title_el else "Unknown"
                        
                        # Extract price
                        price_el = item_el.select_one('.itemPrice')
                        if not price_el:
                            continue
                        
                        price_text = price_el.get_text()
                        price_jpy = self._parse_jpy_price(price_text)
                        
                        if not price_jpy or price_jpy < 10000:  # Skip cheap items
                            continue
                        
                        price_usd = price_jpy * self.JPY_TO_USD
                        
                        # Extract auction ID and URL
                        link_el = item_el.select_one('.itemTitle a')
                        auction_id = ""
                        url = ""
                        if link_el and link_el.get('href'):
                            url = link_el['href']
                            if not url.startswith('http'):
                                url = f"https://buyee.jp{url}"
                            auction_id = url.split('/')[-1].split('?')[0]
                        
                        if auction_id in self.seen_auctions:
                            continue
                        
                        # Extract image
                        img_el = item_el.select_one('.itemImage img')
                        image_url = img_el.get('src') if img_el else None
                        
                        # Extract bids
                        bid_el = item_el.select_one('.bidCount')
                        bids = 0
                        if bid_el:
                            bid_text = bid_el.get_text()
                            bids = self._extract_number(bid_text) or 0
                        
                        items.append(JapanAuctionItem(
                            title=title,
                            price_jpy=price_jpy,
                            price_usd=price_usd,
                            platform='buyee_yahoo',
                            auction_id=auction_id,
                            url=url,
                            image_url=image_url,
                            end_time=None,
                            seller_rating=None,
                            bids=bids,
                            query_matched=en_query,
                        ))
                        
                    except Exception as e:
                        logger.debug(f"Error parsing Buyee item: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error searching Buyee: {e}")
        
        return items
    
    def _parse_jpy_price(self, price_text: str) -> Optional[int]:
        """Parse JPY price from text."""
        import re
        # Remove non-numeric characters
        numbers = re.findall(r'[\d,]+', price_text.replace(',', ''))
        if numbers:
            try:
                return int(numbers[0])
            except:
                pass
        return None
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text."""
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            try:
                return int(numbers[0])
            except:
                pass
        return None
    
    async def get_us_market_price(self, query: str) -> Optional[float]:
        """Get US market price for comparison."""
        # This would integrate with Grailed/eBay sold data
        # For now, use rough estimates based on category
        
        category_hints = {
            'rolex': 8000,
            'omega': 5000,
            'chanel': 6000,
            'lv': 2000,
            'chrome hearts': 800,
        }
        
        query_lower = query.lower()
        for brand, price in category_hints.items():
            if brand in query_lower:
                return price
        
        return None
    
    def calculate_arbitrage(self, japan_item: JapanAuctionItem, us_price: float) -> ArbitrageOpportunity:
        """Calculate arbitrage opportunity."""
        margin_usd = us_price - japan_item.price_usd
        margin_percent = (margin_usd / japan_item.price_usd) * 100 if japan_item.price_usd > 0 else 0
        
        # Determine recommendation
        if margin_percent >= 50:
            recommendation = 'STRONG_BUY'
        elif margin_percent >= 30:
            recommendation = 'BUY'
        elif margin_percent >= 20:
            recommendation = 'WATCH'
        else:
            recommendation = 'SKIP'
        
        # Determine risk level
        notes = []
        risk_level = 'LOW'
        
        if japan_item.bids > 10:
            notes.append(f"High competition ({japan_item.bids} bids)")
            risk_level = 'MEDIUM'
        
        if japan_item.price_usd > 5000:
            notes.append("High capital requirement")
            risk_level = 'MEDIUM'
        
        if 'rolex' in japan_item.query_matched.lower() or 'hermes' in japan_item.query_matched.lower():
            notes.append("Authentication required")
        
        return ArbitrageOpportunity(
            japan_item=japan_item,
            us_market_price=us_price,
            margin_usd=margin_usd,
            margin_percent=margin_percent,
            recommendation=recommendation,
            risk_level=risk_level,
            notes=notes,
        )
    
    async def find_arbitrage_opportunities(self, min_margin_percent: float = 30.0) -> List[ArbitrageOpportunity]:
        """Find all arbitrage opportunities across Japan auctions."""
        all_opportunities = []
        
        for target in self.LUXURY_TARGETS:
            logger.info(f"Searching Japan auctions for: {target['en']}")
            
            # Search Buyee
            try:
                items = await self.search_buyee(target['query'], target['en'])
                
                for item in items:
                    # Get US market price
                    us_price = await self.get_us_market_price(target['en'])
                    
                    if not us_price:
                        continue
                    
                    # Calculate arbitrage
                    opportunity = self.calculate_arbitrage(item, us_price)
                    
                    # Filter by margin
                    if opportunity.margin_percent >= min_margin_percent:
                        all_opportunities.append(opportunity)
                        self.seen_auctions.add(item.auction_id)
                        
                        # Save to file
                        self._save_opportunity(opportunity)
                
            except Exception as e:
                logger.error(f"Error processing {target['en']}: {e}")
            
            await asyncio.sleep(2)  # Rate limiting
        
        # Sort by margin
        all_opportunities.sort(key=lambda x: x.margin_percent, reverse=True)
        
        return all_opportunities[:20]  # Top 20
    
    def _save_opportunity(self, opportunity: ArbitrageOpportunity):
        """Save opportunity to file."""
        with open(self.opportunities_file, 'a') as f:
            f.write(json.dumps({
                'title': opportunity.japan_item.title,
                'price_jpy': opportunity.japan_item.price_jpy,
                'price_usd': opportunity.japan_item.price_usd,
                'platform': opportunity.japan_item.platform,
                'auction_id': opportunity.japan_item.auction_id,
                'url': opportunity.japan_item.url,
                'us_market_price': opportunity.us_market_price,
                'margin_usd': opportunity.margin_usd,
                'margin_percent': opportunity.margin_percent,
                'recommendation': opportunity.recommendation,
                'risk_level': opportunity.risk_level,
                'notes': opportunity.notes,
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
        
        # Recent opportunities (last 7 days)
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
            'avg_margin': sum(o['margin_percent'] for o in recent) / len(recent) if recent else 0,
            'top_opportunities': sorted(recent, key=lambda x: x['margin_percent'], reverse=True)[:10],
        }


# Convenience functions
_scraper = None

def get_scraper() -> JapanAuctionScraper:
    """Get or create scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = JapanAuctionScraper()
    return _scraper


async def find_japan_arbitrage(min_margin: float = 30.0) -> List[ArbitrageOpportunity]:
    """Find Japan arbitrage opportunities."""
    scraper = get_scraper()
    return await scraper.find_arbitrage_opportunities(min_margin)


def get_japan_arbitrage_report() -> Dict:
    """Get Japan arbitrage report."""
    scraper = get_scraper()
    return scraper.get_report()


# CLI helper
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        report = get_japan_arbitrage_report()
        print("\n📊 Japan Arbitrage Report\n")
        print(f"Total opportunities: {report['total']}")
        print(f"Recent (7 days): {report['recent']}")
        print(f"STRONG BUY: {report['strong_buy']}")
        print(f"BUY: {report['buy']}")
        print(f"Avg margin: {report['avg_margin']:.1f}%")
        
        if report['top_opportunities']:
            print("\n🔥 Top Opportunities:")
            for opp in report['top_opportunities'][:5]:
                print(f"  {opp['title'][:50]}...")
                print(f"    Japan: ${opp['price_usd']:.0f} → US: ${opp['us_market_price']:.0f}")
                print(f"    Margin: {opp['margin_percent']:.1f}% ({opp['recommendation']})")
    else:
        print("Usage: python japan_arbitrage.py --report")
