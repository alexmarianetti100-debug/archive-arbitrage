"""Hot item index for O(1) deal matching."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path

@dataclass
class HotItem:
    """Pre-computed hot item for fast matching."""
    query: str
    brand: str
    category: str
    max_price: float  # Alert if below this
    min_profit: float
    priority: int  # 1-10, higher = check more frequently

class HotItemIndex:
    """O(1) lookup index for high-probability items."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.items: Dict[str, HotItem] = {}  # query -> HotItem
        self.brand_index: Dict[str, Set[str]] = {}  # brand -> set of queries
        self.category_index: Dict[str, Set[str]] = {}  # category -> set of queries
        self._loaded = False
    
    def load_from_catalog(self, catalog_path: Optional[str] = None) -> int:
        """Load hot items from golden catalog."""
        if catalog_path is None:
            catalog_path = self.data_dir / "trends" / "golden_catalog.json"
        
        if not Path(catalog_path).exists():
            return 0
        
        with open(catalog_path) as f:
            catalog = json.load(f)
        
        count = 0
        # Load from all tiers, prioritize by tier
        for tier_name, tier_items in [
            ("tier1", catalog.get("tier1", [])),
            ("tier2", catalog.get("tier2", [])),
            ("tier3", catalog.get("tier3", [])),
        ]:
            priority = {"tier1": 10, "tier2": 7, "tier3": 5}[tier_name]
            
            for entry in tier_items:
                query = entry.get("query", "")
                if not query:
                    continue
                
                # Parse brand from query
                brand = entry.get("brand", "")
                if not brand:
                    brand = query.split()[0] if query else ""
                
                # Determine category from query
                category = self._detect_category(query)
                
                # Calculate max price (75% of avg sold price for profit)
                avg_price = entry.get("avg_sold_price", 0)
                max_price = avg_price * 0.75 if avg_price > 0 else 999999
                
                # Min profit target
                min_profit = avg_price * 0.25 if avg_price > 0 else 100
                
                item = HotItem(
                    query=query,
                    brand=brand.lower(),
                    category=category,
                    max_price=max_price,
                    min_profit=min_profit,
                    priority=priority,
                )
                
                self.items[query.lower()] = item
                
                # Index by brand
                if item.brand:
                    if item.brand not in self.brand_index:
                        self.brand_index[item.brand] = set()
                    self.brand_index[item.brand].add(query.lower())
                
                # Index by category
                if item.category:
                    if item.category not in self.category_index:
                        self.category_index[item.category] = set()
                    self.category_index[item.category].add(query.lower())
                
                count += 1
        
        self._loaded = True
        return count
    
    def _detect_category(self, query: str) -> str:
        """Detect item category from query."""
        q = query.lower()
        if any(x in q for x in ["ring", "pendant", "chain", "bracelet", "necklace"]):
            return "jewelry"
        if any(x in q for x in ["boots", "sneaker", "shoes", "runner", "gat", "tabi"]):
            return "footwear"
        if any(x in q for x in ["jacket", "coat", "hoodie", "tee", "shirt"]):
            return "apparel"
        if any(x in q for x in ["belt", "hat", "scarf"]):
            return "accessories"
        return "other"
    
    def match(self, title: str, brand: Optional[str] = None) -> Optional[HotItem]:
        """O(1) match against hot items. Returns HotItem if matched."""
        if not self._loaded:
            return None
        
        title_lower = title.lower()
        
        # Direct match
        if title_lower in self.items:
            return self.items[title_lower]
        
        # Check if any hot item query is in the title
        for query, item in self.items.items():
            if query in title_lower:
                return item
        
        # Brand + category match
        if brand:
            brand_lower = brand.lower()
            if brand_lower in self.brand_index:
                # Return highest priority item for this brand
                brand_items = [
                    self.items[q] for q in self.brand_index[brand_lower]
                    if q in self.items
                ]
                if brand_items:
                    return max(brand_items, key=lambda x: x.priority)
        
        return None
    
    def get_by_brand(self, brand: str) -> List[HotItem]:
        """Get all hot items for a brand."""
        brand_lower = brand.lower()
        if brand_lower not in self.brand_index:
            return []
        return [
            self.items[q] for q in self.brand_index[brand_lower]
            if q in self.items
        ]
    
    def get_high_priority(self, min_priority: int = 7) -> List[HotItem]:
        """Get high priority items for frequent polling."""
        return [
            item for item in self.items.values()
            if item.priority >= min_priority
        ]
