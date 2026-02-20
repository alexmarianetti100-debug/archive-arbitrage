"""
Trending Analyzer — Discover what's selling fast on Grailed.

Scrapes Grailed's sold index to find:
1. Which brands are moving the most
2. Which item types/categories are hot
3. Specific items that keep reselling

Uses this to generate focused search queries for sourcing.
"""

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json
import re

from .grailed import GrailedScraper

# Categories to analyze
CATEGORIES = [
    "jacket", "pants", "jeans", "hoodie", "t-shirt", "sweater",
    "boots", "sneakers", "bag", "coat", "shirt", "shorts"
]

# Broad queries to capture general market movement
BROAD_QUERIES = [
    "",  # Empty = recent sold across everything
    "vintage",
    "archive",
    "rare",
    "grail",
]

# Non-brand entries to filter out
IGNORED_BRANDS = {
    "grailed", "vintage", "other", "unknown", "n/a", "na", "none",
    "unbranded", "no brand", "various", "custom", "handmade",
}


@dataclass
class TrendingItem:
    """A trending item/style detected from sold data."""
    query: str          # Search query to find similar items
    brand: str
    category: Optional[str]
    sold_count: int     # How many similar items sold
    avg_price: float
    price_range: tuple  # (min, max)
    sample_titles: list # Example titles
    score: float        # Trending score (0-1)


@dataclass
class TrendingReport:
    """Full trending analysis report."""
    timestamp: datetime
    hot_brands: list[tuple[str, int]]     # (brand, sold_count)
    hot_categories: list[tuple[str, int]] # (category, sold_count)
    hot_items: list[TrendingItem]         # Specific trending items
    recommended_queries: list[str]         # Top queries to use for sourcing
    total_items_analyzed: int


def extract_brand(title: str, raw_data: dict = None) -> str:
    """Extract brand from item."""
    if raw_data:
        # Try 'designers' array first (Algolia format)
        designers = raw_data.get("designers", [])
        if designers and isinstance(designers, list) and len(designers) > 0:
            first = designers[0]
            if isinstance(first, dict):
                return first.get("name", "")
            elif isinstance(first, str):
                return first
        # Fallback to 'designer' field
        designer = raw_data.get("designer", {})
        if isinstance(designer, dict):
            return designer.get("name", "")
        if designer:
            return str(designer)
    # Fallback: first word often is brand
    return title.split()[0] if title else ""


def extract_category(title: str) -> Optional[str]:
    """Detect category from title."""
    title_lower = title.lower()
    
    category_keywords = {
        "jacket": ["jacket", "blazer", "bomber", "varsity", "trucker", "denim jacket"],
        "coat": ["coat", "overcoat", "trench", "parka", "puffer", "down"],
        "pants": ["pants", "trousers", "cargos", "cargo"],
        "jeans": ["jeans", "denim", "selvedge"],
        "hoodie": ["hoodie", "hooded", "zip-up hoodie", "pullover hoodie"],
        "sweater": ["sweater", "knit", "cardigan", "crewneck"],
        "t-shirt": ["t-shirt", "tee", "tshirt"],
        "shirt": ["shirt", "button up", "flannel", "oxford"],
        "shorts": ["shorts"],
        "boots": ["boots", "boot"],
        "sneakers": ["sneakers", "shoes", "runners", "trainers"],
        "bag": ["bag", "backpack", "tote", "messenger"],
    }
    
    for category, keywords in category_keywords.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return None


def extract_season(title: str) -> Optional[str]:
    """Extract season/year from title if present."""
    patterns = [
        r'(FW|SS|AW|PF)\s*\'?(\d{2})',  # FW21, SS'22
        r'(Fall|Spring|Autumn|Winter|Summer)\s*(\d{4}|\d{2})',
        r'(\d{4})\s*(Fall|Spring|Autumn|Winter|Summer)',
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


class TrendingAnalyzer:
    """Analyzes Grailed sold data to find trending items."""
    
    def __init__(self):
        self.scraper = None
    
    async def __aenter__(self):
        self.scraper = GrailedScraper()
        await self.scraper.__aenter__()
        return self
    
    async def __aexit__(self, *args):
        if self.scraper:
            await self.scraper.__aexit__(*args)
    
    async def fetch_recent_sold(self, query: str = "", max_results: int = 100) -> list:
        """Fetch recently sold items from Grailed."""
        try:
            return await self.scraper.search_sold(query, max_results=max_results)
        except Exception as e:
            print(f"Error fetching sold items for '{query}': {e}")
            return []
    
    async def analyze_trending(
        self,
        items_per_query: int = 50,
        min_brand_count: int = 3,
    ) -> TrendingReport:
        """
        Analyze what's trending on Grailed by sampling sold items.
        
        Returns a report with hot brands, categories, and recommended queries.
        """
        all_items = []
        brand_counter = Counter()
        category_counter = Counter()
        brand_items = defaultdict(list)
        brand_prices = defaultdict(list)
        
        print("📊 Analyzing Grailed trending...")
        
        # Fetch sold items across broad queries
        for query in BROAD_QUERIES:
            items = await self.fetch_recent_sold(query, items_per_query)
            print(f"   '{query or '(all)'}': {len(items)} sold items")
            all_items.extend(items)
            await asyncio.sleep(0.5)  # Rate limit
        
        # Also sample by category
        for category in CATEGORIES:
            items = await self.fetch_recent_sold(category, items_per_query // 2)
            print(f"   '{category}': {len(items)} sold items")
            all_items.extend(items)
            await asyncio.sleep(0.5)
        
        # Deduplicate by source_id
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.source_id not in seen_ids:
                seen_ids.add(item.source_id)
                unique_items.append(item)
        
        print(f"\n   Total unique sold items: {len(unique_items)}")
        
        # Analyze items
        for item in unique_items:
            brand = extract_brand(item.title, item.raw_data) or item.brand or ""
            if not brand or len(brand) < 2:
                continue
            
            # Normalize brand name
            brand = brand.strip().title()
            
            # Skip non-brand entries
            if brand.lower() in IGNORED_BRANDS:
                continue
            
            category = extract_category(item.title)
            
            brand_counter[brand] += 1
            if category:
                category_counter[category] += 1
            
            brand_items[brand].append(item)
            if item.price > 0:
                brand_prices[brand].append(item.price)
        
        # Get top brands (sorted by count)
        hot_brands = brand_counter.most_common(30)
        hot_categories = category_counter.most_common(15)
        
        # Build trending items from top brands
        hot_items = []
        for brand, count in hot_brands[:20]:
            if count < min_brand_count:
                continue
            
            items = brand_items[brand]
            prices = brand_prices[brand]
            
            # Find most common category for this brand
            brand_cats = Counter(extract_category(i.title) for i in items if extract_category(i.title))
            top_cat = brand_cats.most_common(1)[0][0] if brand_cats else None
            
            avg_price = sum(prices) / len(prices) if prices else 0
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0
            
            # Calculate trending score
            # More sales + higher prices = hotter
            score = min(1.0, (count / 20) * 0.6 + (avg_price / 500) * 0.4)
            
            # Build search query
            query = brand
            if top_cat:
                query = f"{brand} {top_cat}"
            
            hot_items.append(TrendingItem(
                query=query,
                brand=brand,
                category=top_cat,
                sold_count=count,
                avg_price=avg_price,
                price_range=(min_price, max_price),
                sample_titles=[i.title[:60] for i in items[:3]],
                score=score,
            ))
        
        # Sort by score
        hot_items.sort(key=lambda x: x.score, reverse=True)
        
        # Generate recommended queries
        # Mix of brand-only and brand+category queries
        recommended = []
        for item in hot_items[:15]:
            recommended.append(item.brand)  # Brand only
            if item.category:
                recommended.append(f"{item.brand} {item.category}")  # Brand + category
        
        # Add some category-only queries for variety
        for cat, _ in hot_categories[:5]:
            recommended.append(cat)
        
        # Deduplicate while preserving order
        seen = set()
        unique_recommended = []
        for q in recommended:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique_recommended.append(q)
        
        return TrendingReport(
            timestamp=datetime.utcnow(),
            hot_brands=hot_brands,
            hot_categories=hot_categories,
            hot_items=hot_items,
            recommended_queries=unique_recommended[:30],  # Top 30 queries
            total_items_analyzed=len(unique_items),
        )
    
    def print_report(self, report: TrendingReport):
        """Pretty print the trending report."""
        print("\n" + "=" * 60)
        print("🔥 GRAILED TRENDING REPORT")
        print(f"   Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"   Items analyzed: {report.total_items_analyzed}")
        print("=" * 60)
        
        print("\n📈 HOT BRANDS (by sold count):")
        for i, (brand, count) in enumerate(report.hot_brands[:15], 1):
            print(f"   {i:2}. {brand}: {count} sold")
        
        print("\n📦 HOT CATEGORIES:")
        for cat, count in report.hot_categories[:10]:
            print(f"   • {cat}: {count} sold")
        
        print("\n🎯 TRENDING ITEMS:")
        for item in report.hot_items[:10]:
            emoji = "🔥" if item.score > 0.7 else "🟡" if item.score > 0.4 else "🔵"
            print(f"   {emoji} {item.brand} {item.category or ''}")
            print(f"      {item.sold_count} sold | Avg ${item.avg_price:.0f} | Score: {item.score:.0%}")
        
        print("\n🔍 RECOMMENDED SEARCH QUERIES:")
        for i, q in enumerate(report.recommended_queries[:15], 1):
            print(f"   {i:2}. {q}")
        
        print("\n" + "=" * 60)


async def get_trending_queries(items_per_query: int = 30) -> list[str]:
    """
    Quick function to get trending search queries.
    
    Returns a list of search queries based on what's selling.
    """
    async with TrendingAnalyzer() as analyzer:
        report = await analyzer.analyze_trending(items_per_query=items_per_query)
        return report.recommended_queries


def save_report(report: TrendingReport, path: str = "data/trending_report.json"):
    """Save report to JSON file."""
    data = {
        "timestamp": report.timestamp.isoformat(),
        "hot_brands": report.hot_brands,
        "hot_categories": report.hot_categories,
        "hot_items": [
            {
                "query": i.query,
                "brand": i.brand,
                "category": i.category,
                "sold_count": i.sold_count,
                "avg_price": i.avg_price,
                "price_range": list(i.price_range),
                "sample_titles": i.sample_titles,
                "score": i.score,
            }
            for i in report.hot_items
        ],
        "recommended_queries": report.recommended_queries,
        "total_items_analyzed": report.total_items_analyzed,
    }
    
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Report saved to {path}")


# CLI test
if __name__ == "__main__":
    async def main():
        async with TrendingAnalyzer() as analyzer:
            report = await analyzer.analyze_trending(items_per_query=50)
            analyzer.print_report(report)
            save_report(report)
    
    asyncio.run(main())
