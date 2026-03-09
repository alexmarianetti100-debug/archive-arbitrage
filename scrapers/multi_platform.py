"""
eBay Sold Listings Scraper (HTML fallback)

Scrapes eBay sold/completed listings for market data.
Use this until Production API keys are approved.
"""

import re
from typing import List, Optional
from urllib.parse import quote
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class EbaySoldScraper(BaseScraper):
    """Scrape eBay sold listings for pricing data."""
    
    SOURCE_NAME = "ebay_sold"
    BASE_URL = "https://www.ebay.com"
    
    MIN_DELAY = 2.0
    MAX_DELAY = 5.0
    
    async def search_sold(
        self,
        query: str,
        max_results: int = 50,
        category: str = None,
    ) -> List[ScrapedItem]:
        """Search for sold items on eBay."""
        items = []
        seen_ids = set()
        
        # Build sold items search URL
        search_url = (
            f"{self.BASE_URL}/sch/i.html?"
            f"_nkw={quote(query)}&"
            f"_sacat={category or '11450'}&"  # Clothing category
            f"LH_Sold=1&"  # Sold items only
            f"LH_Complete=1&"  # Completed listings
            f"_ipg=200"  # 200 per page
        )
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  eBay returned {response.status_code}")
                return items
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Find sold items
            # eBay structure: each item is in a .s-item block
            listings = soup.select('.s-item')
            
            for listing in listings[:max_results]:
                try:
                    # Skip the first empty item (eBay's template)
                    item_id = listing.get('data-itemid', '')
                    if not item_id:
                        # Try to extract from URL
                        link = listing.select_one('.s-item__link')
                        if link:
                            href = link.get('href', '')
                            match = re.search(r'/itm/(\d+)', href)
                            if match:
                                item_id = match.group(1)
                    
                    if not item_id or item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    
                    # Title
                    title_el = listing.select_one('.s-item__title')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    
                    # Skip "Shop on eBay" placeholder
                    if "Shop on eBay" in title or title == "":
                        continue
                    
                    # Price - sold price
                    price = 0.0
                    price_el = listing.select_one('.s-item__price')
                    if price_el:
                        price_text = price_el.get_text(strip=True)
                        price = self.parse_price(price_text)
                    
                    if price <= 0:
                        continue
                    
                    # URL
                    url = ""
                    link = listing.select_one('.s-item__link')
                    if link:
                        url = link.get('href', '').split('?')[0]  # Remove tracking params
                    
                    # Image
                    images = []
                    img_el = listing.select_one('.s-item__image-img')
                    if img_el:
                        img_url = img_el.get('src', '')
                        if img_url and not img_url.startswith('data:'):
                            images.append(img_url)
                    
                    # Shipping cost (if shown)
                    shipping = 0.0
                    shipping_el = listing.select_one('.s-item__shipping')
                    if shipping_el:
                        shipping_text = shipping_el.get_text(strip=True)
                        if 'Free' in shipping_text:
                            shipping = 0.0
                        else:
                            shipping = self.parse_price(shipping_text)
                    
                    # Date sold (if available)
                    date_sold = None
                    date_el = listing.select_one('.s-item__endedDate')
                    if date_el:
                        date_text = date_el.get_text(strip=True)
                        try:
                            # Format: "Feb 9, 2026"
                            date_sold = datetime.strptime(date_text, "%b %d, %Y").isoformat()
                        except:
                            pass
                    
                    items.append(ScrapedItem(
                        source=self.SOURCE_NAME,
                        source_id=item_id,
                        url=url,
                        title=title[:200],
                        price=price,
                        currency="USD",
                        images=images,
                        is_auction=False,
                        # Store date in raw_data so temporal filtering in get_sold_data works
                        raw_data={"created_at": date_sold} if date_sold else {},
                    ))
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  eBay sold search failed: {e}")
        
        return items


class MultiPlatformPricer:
    """
    Aggregate pricing data from multiple platforms.
    
    Combines:
    - Grailed (sold) — archive-specific, high accuracy
    - eBay (sold) — huge volume, market consensus
    - Poshmark (active) — supply side, price pressure
    """
    
    def __init__(self):
        self.platform_weights = {
            "grailed": 0.5,      # Most trusted for archive
            "ebay_sold": 0.4,    # High volume, good consensus
            "poshmark": 0.1,     # Active only, less weight
        }
    
    async def get_comprehensive_pricing(
        self,
        brand: str,
        title: str,
        max_results_per_platform: int = 20,
    ) -> dict:
        """
        Get pricing data from all available platforms.
        
        Returns:
            {
                "consensus_price": float,
                "price_range": (low, high),
                "confidence": "high" | "medium" | "low",
                "platforms": {
                    "grailed": {"count": int, "median": float, "items": []},
                    "ebay": {"count": int, "median": float, "items": []},
                    "poshmark": {"count": int, "median": float, "items": []},
                },
                "cross_platform_spread": float,  # % difference between platforms
            }
        """
        import asyncio
        from .comp_matcher import find_best_comps
        
        results = {
            "grailed": {"count": 0, "median": 0, "items": []},
            "ebay": {"count": 0, "median": 0, "items": []},
            "poshmark": {"count": 0, "median": 0, "items": []},
        }
        
        # Fetch from all platforms concurrently
        tasks = []
        
        # Grailed
        async def fetch_grailed():
            try:
                comp_result = await find_best_comps(brand, title, max_comps=max_results_per_platform)
                if comp_result.comps_count > 0:
                    results["grailed"]["count"] = comp_result.comps_count
                    results["grailed"]["median"] = float(comp_result.weighted_price)
                    results["grailed"]["items"] = [
                        {"title": c.title, "price": c.price, "similarity": c.similarity}
                        for c in comp_result.top_comps
                    ]
            except Exception as e:
                print(f"Grailed fetch failed: {e}")
        
        # eBay
        async def fetch_ebay():
            try:
                async with EbaySoldScraper() as scraper:
                    items = await scraper.search_sold(f"{brand} {title}", max_results=max_results_per_platform)
                    if items:
                        prices = [i.price for i in items]
                        results["ebay"]["count"] = len(items)
                        results["ebay"]["median"] = sorted(prices)[len(prices) // 2]
                        results["ebay"]["items"] = [
                            {"title": i.title, "price": i.price} for i in items[:5]
                        ]
            except Exception as e:
                print(f"eBay fetch failed: {e}")
        
        # Poshmark (active listings - supply indicator)
        async def fetch_poshmark():
            try:
                from .poshmark import PoshmarkScraper
                async with PoshmarkScraper() as scraper:
                    items = await scraper.search(f"{brand} {title}", max_results=max_results_per_platform)
                    if items:
                        prices = [i.price for i in items]
                        results["poshmark"]["count"] = len(items)
                        results["poshmark"]["median"] = sorted(prices)[len(prices) // 2] if prices else 0
            except Exception as e:
                print(f"Poshmark fetch failed: {e}")
        
        # Run all fetches
        await asyncio.gather(
            fetch_grailed(),
            fetch_ebay(),
            fetch_poshmark(),
            return_exceptions=True,
        )
        
        # Calculate consensus price
        total_weight = 0
        weighted_price = 0
        all_prices = []
        
        for platform, data in results.items():
            if data["count"] > 0 and data["median"] > 0:
                weight = self.platform_weights.get(platform, 0.1)
                weighted_price += data["median"] * weight
                total_weight += weight
                all_prices.append(data["median"])
        
        consensus_price = weighted_price / total_weight if total_weight > 0 else 0
        
        # Calculate confidence
        confidence = "low"
        total_comps = sum(d["count"] for d in results.values())
        if total_comps >= 20 and len([p for p in all_prices if p > 0]) >= 2:
            confidence = "high"
        elif total_comps >= 10:
            confidence = "medium"
        
        # Calculate cross-platform spread
        cross_platform_spread = 0
        if len(all_prices) >= 2:
            cross_platform_spread = (max(all_prices) - min(all_prices)) / consensus_price if consensus_price > 0 else 0
        
        return {
            "consensus_price": round(consensus_price, 2),
            "price_range": (round(min(all_prices), 2), round(max(all_prices), 2)) if all_prices else (0, 0),
            "confidence": confidence,
            "platforms": results,
            "cross_platform_spread": round(cross_platform_spread * 100, 1),
            "total_comps": total_comps,
        }


if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("Multi-Platform Pricing Test")
        print("=" * 70)
        
        pricer = MultiPlatformPricer()
        result = await pricer.get_comprehensive_pricing(
            brand="rick owens",
            title="geobasket",
        )
        
        print(f"\nConsensus Price: ${result['consensus_price']}")
        print(f"Price Range: ${result['price_range'][0]} - ${result['price_range'][1]}")
        print(f"Confidence: {result['confidence']}")
        print(f"Cross-Platform Spread: {result['cross_platform_spread']}%")
        print(f"\nPlatform Breakdown:")
        for platform, data in result['platforms'].items():
            if data['count'] > 0:
                print(f"  {platform}: {data['count']} comps, median ${data['median']}")
    
    asyncio.run(test())
