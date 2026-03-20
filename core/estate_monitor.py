"""
Estate Sale Monitor

Finds estate sales, liquidations, and collection sales with luxury items.
These are often the best sources for bulk deals and rare finds.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("estate_sales")


@dataclass
class EstateSale:
    """Estate sale listing."""
    title: str
    location: str
    sale_date: Optional[str]
    description: str
    url: str
    source: str
    luxury_score: float  # 0-1, likelihood of luxury items
    images: List[str]
    found_at: datetime


@dataclass
class BulkDeal:
    """Bulk deal opportunity from estate sale."""
    sale: EstateSale
    estimated_items: int
    estimated_value: float
    asking_price: Optional[float]
    deal_score: float  # 0-100
    recommendation: str
    notes: List[str]


class EstateSaleMonitor:
    """Monitor estate sales and liquidations."""
    
    # Sources to monitor
    SOURCES = {
        'estatesales_net': {
            'name': 'EstateSales.net',
            'url': 'https://www.estatesales.net',
            'search_path': '/search?query={query}',
        },
        'maxsold': {
            'name': 'MaxSold',
            'url': 'https://www.maxsold.com',
            'search_path': '/auctions?search={query}',
        },
        'ebth': {
            'name': 'Everything But The House',
            'url': 'https://www.ebth.com',
            'search_path': '/search?query={query}',
        },
    }
    
    # Luxury indicators in sale descriptions
    LUXURY_KEYWORDS = [
        # Jewelry
        'chrome hearts', 'van cleef', 'cartier love', 'tiffany',
        'fine jewelry', 'estate jewelry', 'vintage jewelry',
        'gold jewelry', 'diamond', 'designer jewelry',

        # Fashion
        'rick owens', 'margiela', 'raf simons', 'archive fashion',
        'designer clothing', 'luxury fashion', 'vintage designer',
        'balenciaga', 'saint laurent', 'prada', 'gucci',

        # General
        'luxury', 'designer', 'high-end', 'couture', 'vintage luxury',
        'fashion collection', 'jewelry collection',
        'estate jewelry', 'liquidation', 'downsizing', 'moving sale',
        'divorce sale', 'inheritance', 'collection sale',
    ]
    
    # High-value location indicators
    HIGH_VALUE_LOCATIONS = [
        'beverly hills', 'bel air', 'malibu', 'manhattan', 'upper east side',
        'greenwich', 'hamptons', 'palm beach', 'napa', 'marin',
        'tokyo', 'ginza', 'roppongi', 'hong kong', 'central',
        'london', 'mayfair', 'kensington', 'paris', '8th arrondissement',
    ]
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.sales_file = self.data_dir / "estate_sales.jsonl"
        self.deals_file = self.data_dir / "bulk_deals.jsonl"
        self.seen_sales: set = self._load_seen()
    
    def _load_seen(self) -> set:
        """Load previously seen sale IDs."""
        seen = set()
        if self.sales_file.exists():
            with open(self.sales_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        seen.add(data.get('url', ''))
                    except:
                        continue
        return seen
    
    def calculate_luxury_score(self, text: str, location: str = "") -> float:
        """Calculate likelihood of luxury items (0-1)."""
        text_lower = text.lower()
        score = 0.0
        
        # Check for luxury keywords
        for keyword in self.LUXURY_KEYWORDS:
            if keyword in text_lower:
                score += 0.1
        
        # Check for high-value locations
        location_lower = location.lower()
        for loc in self.HIGH_VALUE_LOCATIONS:
            if loc in location_lower:
                score += 0.2
        
        # Bonus for collection mentions
        if 'collection' in text_lower:
            score += 0.15
        
        # Bonus for multiple luxury brands
        brand_count = sum(1 for brand in ['rolex', 'hermes', 'chanel', 'cartier'] 
                         if brand in text_lower)
        score += brand_count * 0.1
        
        return min(score, 1.0)
    
    async def scrape_estatesales_net(self, location: str = "") -> List[EstateSale]:
        """Scrape EstateSales.net."""
        sales = []
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Search for luxury-related sales
                url = "https://www.estatesales.net"
                if location:
                    url += f"/location/{location}"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    logger.warning(f"EstateSales.net returned {response.status_code}")
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse sale listings
                for sale_el in soup.select('.sale-listing')[:20]:
                    try:
                        title_el = sale_el.select_one('.sale-title')
                        title = title_el.get_text(strip=True) if title_el else "Unknown"
                        
                        location_el = sale_el.select_one('.sale-location')
                        sale_location = location_el.get_text(strip=True) if location_el else "Unknown"
                        
                        date_el = sale_el.select_one('.sale-date')
                        sale_date = date_el.get_text(strip=True) if date_el else None
                        
                        desc_el = sale_el.select_one('.sale-description')
                        description = desc_el.get_text(strip=True) if desc_el else ""
                        
                        link_el = sale_el.select_one('a')
                        url = link_el['href'] if link_el else ""
                        if url and not url.startswith('http'):
                            url = f"https://www.estatesales.net{url}"
                        
                        if url in self.seen_sales:
                            continue
                        
                        # Calculate luxury score
                        combined_text = f"{title} {description}"
                        luxury_score = self.calculate_luxury_score(combined_text, sale_location)
                        
                        # Only keep high-score sales
                        if luxury_score < 0.3:
                            continue
                        
                        sales.append(EstateSale(
                            title=title,
                            location=sale_location,
                            sale_date=sale_date,
                            description=description,
                            url=url,
                            source='estatesales_net',
                            luxury_score=luxury_score,
                            images=[],  # Would need to fetch detail page
                            found_at=datetime.now(),
                        ))
                        
                    except Exception as e:
                        logger.debug(f"Error parsing estate sale: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error scraping EstateSales.net: {e}")
        
        return sales
    
    async def analyze_sale(self, sale: EstateSale) -> Optional[BulkDeal]:
        """Analyze estate sale for bulk deal potential."""
        # This would ideally fetch the detail page and count items
        # For now, use heuristics
        
        description_lower = sale.description.lower()
        
        # Estimate number of items
        item_count = 0
        if 'collection' in description_lower:
            item_count += 20
        if any(word in description_lower for word in ['extensive', 'large', 'huge']):
            item_count += 30
        if any(brand in description_lower for brand in ['rolex', 'hermes', 'chanel']):
            item_count += 5
        
        if item_count == 0:
            item_count = 10  # Default estimate
        
        # Estimate value
        estimated_value = item_count * 500  # $500 avg per item
        
        # Calculate deal score
        deal_score = sale.luxury_score * 100
        
        # Adjust for location
        if any(loc in sale.location.lower() for loc in self.HIGH_VALUE_LOCATIONS):
            deal_score += 20
        
        # Generate recommendation
        if deal_score >= 80:
            recommendation = "MUST_VISIT"
        elif deal_score >= 60:
            recommendation = "HIGH_PRIORITY"
        elif deal_score >= 40:
            recommendation = "WORTH_CHECKING"
        else:
            recommendation = "LOW_PRIORITY"
        
        # Generate notes
        notes = []
        if sale.luxury_score > 0.7:
            notes.append("High luxury content")
        if 'collection' in description_lower:
            notes.append("Collection sale - bulk opportunity")
        if any(loc in sale.location.lower() for loc in self.HIGH_VALUE_LOCATIONS):
            notes.append("High-value location")
        
        return BulkDeal(
            sale=sale,
            estimated_items=item_count,
            estimated_value=estimated_value,
            asking_price=None,  # Would need to contact
            deal_score=min(deal_score, 100),
            recommendation=recommendation,
            notes=notes,
        )
    
    async def find_bulk_deals(self) -> List[BulkDeal]:
        """Find bulk deal opportunities from estate sales."""
        all_deals = []
        
        # Scrape multiple sources
        sources = [
            self.scrape_estatesales_net(),
            # Add more sources here
        ]
        
        results = await asyncio.gather(*sources, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Source error: {result}")
                continue
            
            for sale in result:
                try:
                    deal = await self.analyze_sale(sale)
                    if deal and deal.deal_score >= 50:
                        all_deals.append(deal)
                        self.seen_sales.add(sale.url)
                        self._save_sale(sale)
                        self._save_deal(deal)
                except Exception as e:
                    logger.error(f"Error analyzing sale: {e}")
        
        # Sort by deal score
        all_deals.sort(key=lambda x: x.deal_score, reverse=True)
        
        return all_deals[:15]  # Top 15
    
    def _save_sale(self, sale: EstateSale):
        """Save sale to file."""
        with open(self.sales_file, 'a') as f:
            f.write(json.dumps({
                'title': sale.title,
                'location': sale.location,
                'sale_date': sale.sale_date,
                'description': sale.description,
                'url': sale.url,
                'source': sale.source,
                'luxury_score': sale.luxury_score,
                'found_at': sale.found_at.isoformat(),
            }) + '\n')
    
    def _save_deal(self, deal: BulkDeal):
        """Save deal to file."""
        with open(self.deals_file, 'a') as f:
            f.write(json.dumps({
                'sale_title': deal.sale.title,
                'location': deal.sale.location,
                'estimated_items': deal.estimated_items,
                'estimated_value': deal.estimated_value,
                'deal_score': deal.deal_score,
                'recommendation': deal.recommendation,
                'notes': deal.notes,
                'url': deal.sale.url,
                'found_at': datetime.now().isoformat(),
            }) + '\n')
    
    def get_report(self) -> Dict:
        """Generate estate sale report."""
        if not self.deals_file.exists():
            return {'total': 0, 'deals': []}
        
        deals = []
        with open(self.deals_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    deals.append(data)
                except:
                    continue
        
        # Recent deals (last 7 days)
        recent = [
            d for d in deals
            if (datetime.now() - datetime.fromisoformat(d['found_at'])).days < 7
        ]
        
        must_visit = [d for d in recent if d['recommendation'] == 'MUST_VISIT']
        high_priority = [d for d in recent if d['recommendation'] == 'HIGH_PRIORITY']
        
        return {
            'total': len(deals),
            'recent': len(recent),
            'must_visit': len(must_visit),
            'high_priority': len(high_priority),
            'avg_deal_score': sum(d['deal_score'] for d in recent) / len(recent) if recent else 0,
            'top_deals': sorted(recent, key=lambda x: x['deal_score'], reverse=True)[:10],
        }


# Convenience functions
_monitor = None

def get_monitor() -> EstateSaleMonitor:
    """Get or create monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = EstateSaleMonitor()
    return _monitor


async def find_estate_deals() -> List[BulkDeal]:
    """Find estate sale bulk deals."""
    monitor = get_monitor()
    return await monitor.find_bulk_deals()


def get_estate_report() -> Dict:
    """Get estate sale report."""
    monitor = get_monitor()
    return monitor.get_report()


# CLI helper
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        report = get_estate_report()
        print("\n📊 Estate Sale Report\n")
        print(f"Total deals found: {report['total']}")
        print(f"Recent (7 days): {report['recent']}")
        print(f"MUST VISIT: {report['must_visit']}")
        print(f"HIGH PRIORITY: {report['high_priority']}")
        print(f"Avg deal score: {report['avg_deal_score']:.1f}")
        
        if report['top_deals']:
            print("\n🔥 Top Opportunities:")
            for deal in report['top_deals'][:5]:
                print(f"  {deal['sale_title'][:50]}...")
                print(f"    Location: {deal['location']}")
                print(f"    Est. items: {deal['estimated_items']} (${deal['estimated_value']:,.0f})")
                print(f"    Score: {deal['deal_score']:.0f} ({deal['recommendation']})")
    else:
        print("Usage: python estate_monitor.py --report")
