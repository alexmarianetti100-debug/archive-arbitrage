"""
Mercari Japan Scraper using mercapi library

Direct API access to Mercari Japan - no browser needed!
"""

import asyncio
import logging
from typing import List, Optional
from dataclasses import dataclass

from core.mercari_urls import mercari_item_url

logger = logging.getLogger("mercari_direct")

# mercapi import
try:
    from mercapi import Mercapi
    HAS_MERCAPI = True
except ImportError:
    HAS_MERCAPI = False
    logger.warning("mercapi not installed. Direct Mercari scraping disabled.")


@dataclass
class MercariDirectItem:
    """Mercari item from direct API."""
    title_jp: str
    title_en: str
    price_jpy: int
    item_id: str
    item_url: str
    image_url: Optional[str]
    status: str
    category: str
    brand: str
    weight_kg: float
    seller_id: str
    seller_name: str
    created_at: str


class MercariDirectScraper:
    """Scrape Mercari Japan directly using mercapi."""
    
    def __init__(self):
        self.client: Optional[Mercapi] = None
    
    async def __aenter__(self):
        if HAS_MERCAPI:
            self.client = Mercapi()
        return self
    
    async def __aexit__(self, *args):
        pass  # No cleanup needed
    
    async def search(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
        max_price_jpy: Optional[int] = None,
    ) -> List[MercariDirectItem]:
        """Search Mercari Japan directly."""
        
        if not HAS_MERCAPI or not self.client:
            logger.warning("mercapi not available")
            return []
        
        items = []
        
        try:
            logger.info(f"[Mercari Direct] Searching: {query_jp}")
            
            # Build search parameters
            search_params = {
                'query': query_jp,
                'price_min': min_price_jpy,
            }
            
            if max_price_jpy:
                search_params['price_max'] = max_price_jpy
            
            # Search
            logger.debug(f"Search params: {search_params}")
            results = await self.client.search(**search_params)
            logger.debug(f"Got {len(results.items)} raw results")
            
            # Parse results
            for item in results.items[:max_results]:
                try:
                    # Build item URL
                    item_url = mercari_item_url(item.id_)
                    
                    # Get first image
                    image_url = item.thumbnails[0] if item.thumbnails else None
                    
                    # seller is a coroutine that returns seller info - skip it for now
                    # seller_info = await item.seller() if callable(item.seller) else item.seller
                    seller_id = ""
                    seller_name = ""
                    
                    items.append(MercariDirectItem(
                        title_jp=item.name,
                        title_en=query_en,
                        price_jpy=item.price,
                        item_id=item.id_,
                        item_url=item_url,
                        image_url=image_url,
                        status=item.status,
                        category=category,
                        brand=brand,
                        weight_kg=weight_kg,
                        seller_id=seller_id,
                        seller_name=seller_name,
                        created_at=str(item.created) if item.created else "",
                    ))
                except Exception as e:
                    logger.debug(f"Error parsing item: {e}")
                    continue
            
            logger.info(f"[Mercari Direct] Found {len(items)} items for {query_en}")
            
        except Exception as e:
            logger.error(f"[Mercari Direct] Search error: {e}")
        
        return items


# Convenience function
async def search_mercari_direct(
    query_jp: str,
    query_en: str,
    category: str,
    brand: str,
    weight_kg: float = 0.5,
    max_results: int = 20,
    min_price_jpy: int = 10000,
) -> List[MercariDirectItem]:
    """Quick search Mercari Japan directly."""
    async with MercariDirectScraper() as scraper:
        return await scraper.search(
            query_jp=query_jp,
            query_en=query_en,
            category=category,
            brand=brand,
            weight_kg=weight_kg,
            max_results=max_results,
            min_price_jpy=min_price_jpy,
        )


if __name__ == "__main__":
    async def test():
        if not HAS_MERCAPI:
            print("mercapi not installed. Install with: pip install mercapi")
            return
        
        # Test search
        items = await search_mercari_direct(
            query_jp='クロムハーツ リング',
            query_en='chrome hearts ring',
            category='jewelry',
            brand='Chrome Hearts',
            weight_kg=0.1,
            max_results=10,
        )
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"\n{item.title_jp}")
            print(f"  Price: ¥{item.price_jpy:,}")
            print(f"  Seller: {item.seller_name}")
            print(f"  URL: {item.item_url}")
    
    asyncio.run(test())
