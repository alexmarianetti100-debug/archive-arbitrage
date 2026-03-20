"""
Pricing service - calculates optimal prices based on LIVE market data.

Pricing Strategy:
- Fetches recently sold items from Grailed for real market prices
- Detects iconic seasons/collections for price multipliers
- Caches results to avoid API hammering (15 min TTL)
- Falls back to brand-based estimates when live data unavailable
- Minimum 25% margin on all items
- Prices slightly below market to encourage quick sales
"""

import asyncio
import time
from decimal import Decimal
from typing import Optional, Tuple
from dataclasses import dataclass
import json
import os

# Import season detection and smart comp matcher
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scrapers.seasons import detect_season, get_season_adjusted_price
from scrapers.comp_matcher import find_best_comps, CompResult
from scrapers.demand_scorer import score_demand, DemandResult

# Cache file for market prices
CACHE_FILE = os.path.join(os.path.dirname(__file__), "../../data/price_cache.json")
CACHE_TTL = 0  # Always recalculate — no caching


# Average market prices by brand (fallback estimates)
BRAND_MARKET_ESTIMATES = {
    # === JAPANESE ARCHIVE ===
    "number nine": {"jacket": 400, "pants": 200, "shirt": 150, "tee": 100, "hoodie": 250, "default": 200},
    "number (n)ine": {"jacket": 400, "pants": 200, "shirt": 150, "tee": 100, "hoodie": 250, "default": 200},
    "undercover": {"jacket": 450, "pants": 180, "shirt": 140, "tee": 90, "hoodie": 200, "default": 180},
    "hysteric glamour": {"jacket": 300, "pants": 150, "shirt": 120, "tee": 80, "hoodie": 180, "default": 150},
    "comme des garcons": {"jacket": 350, "pants": 200, "shirt": 180, "tee": 100, "hoodie": 200, "default": 200},
    "cdg": {"jacket": 350, "pants": 200, "shirt": 180, "tee": 100, "hoodie": 200, "default": 200},
    "yohji yamamoto": {"jacket": 500, "pants": 250, "shirt": 200, "tee": 120, "default": 250},
    "issey miyake": {"jacket": 350, "pants": 200, "shirt": 150, "tee": 100, "default": 200},
    "kapital": {"jacket": 400, "pants": 250, "shirt": 150, "tee": 100, "default": 200},
    "visvim": {"jacket": 600, "pants": 300, "shirt": 250, "tee": 150, "default": 300},
    "wtaps": {"jacket": 350, "pants": 200, "shirt": 150, "tee": 100, "hoodie": 200, "default": 180},
    "neighborhood": {"jacket": 350, "pants": 200, "shirt": 150, "tee": 90, "hoodie": 180, "default": 170},
    "bape": {"jacket": 400, "pants": 200, "shirt": 150, "tee": 120, "hoodie": 300, "default": 200},
    "human made": {"jacket": 350, "pants": 180, "shirt": 140, "tee": 100, "hoodie": 200, "default": 160},
    "cav empt": {"jacket": 350, "pants": 200, "shirt": 150, "tee": 100, "hoodie": 220, "default": 180},
    "wacko maria": {"jacket": 400, "pants": 220, "shirt": 200, "tee": 100, "default": 200},
    "sacai": {"jacket": 500, "pants": 300, "shirt": 250, "tee": 150, "default": 280},
    "junya watanabe": {"jacket": 450, "pants": 250, "shirt": 200, "tee": 120, "default": 230},
    
    # === EUROPEAN ARCHIVE ===
    "rick owens": {"jacket": 800, "pants": 400, "shirt": 300, "tee": 200, "boots": 600, "hoodie": 400, "default": 400},
    "drkshdw": {"jacket": 500, "pants": 300, "shirt": 200, "tee": 150, "default": 280},
    "raf simons": {"jacket": 600, "pants": 300, "shirt": 250, "tee": 150, "hoodie": 350, "default": 300},
    "maison margiela": {"jacket": 500, "pants": 300, "shirt": 250, "tee": 150, "boots": 400, "default": 300},
    "martin margiela": {"jacket": 600, "pants": 350, "shirt": 280, "tee": 180, "boots": 500, "default": 350},
    "margiela": {"jacket": 500, "pants": 300, "shirt": 250, "tee": 150, "boots": 400, "default": 300},
    "helmut lang": {"jacket": 400, "pants": 200, "shirt": 180, "tee": 100, "default": 200},
    "ann demeulemeester": {"jacket": 450, "pants": 250, "shirt": 200, "tee": 120, "default": 250},
    "dries van noten": {"jacket": 400, "pants": 250, "shirt": 200, "tee": 120, "default": 250},

    # === STREETWEAR / HYPE ===
    "supreme": {"jacket": 400, "pants": 200, "shirt": 180, "tee": 80, "hoodie": 250, "hat": 80, "default": 150},
    "palace": {"jacket": 300, "pants": 150, "shirt": 120, "tee": 60, "hoodie": 180, "default": 120},
    "off-white": {"jacket": 500, "pants": 250, "shirt": 200, "tee": 150, "hoodie": 300, "default": 220},
    "off white": {"jacket": 500, "pants": 250, "shirt": 200, "tee": 150, "hoodie": 300, "default": 220},
    "vetements": {"jacket": 600, "pants": 300, "shirt": 250, "tee": 200, "hoodie": 400, "default": 300},
    "balenciaga": {"jacket": 800, "pants": 400, "shirt": 350, "tee": 250, "hoodie": 500, "shoes": 500, "default": 400},
    "fear of god": {"jacket": 500, "pants": 250, "shirt": 180, "tee": 100, "hoodie": 300, "default": 220},
    "fog essentials": {"jacket": 150, "pants": 80, "shirt": 60, "tee": 40, "hoodie": 100, "default": 70},
    "gosha rubchinskiy": {"jacket": 300, "pants": 150, "shirt": 120, "tee": 80, "hoodie": 180, "default": 140},
    "alyx": {"jacket": 500, "pants": 300, "shirt": 200, "tee": 120, "default": 250},
    "gallery dept": {"jacket": 500, "pants": 350, "shirt": 250, "tee": 180, "hoodie": 400, "default": 300},
    "rhude": {"jacket": 400, "pants": 250, "shirt": 180, "tee": 100, "hoodie": 280, "default": 200},
    "amiri": {"jacket": 600, "pants": 400, "shirt": 300, "tee": 150, "default": 350},
    "kith": {"jacket": 300, "pants": 150, "shirt": 100, "tee": 60, "hoodie": 180, "default": 130},
    "stussy": {"jacket": 200, "pants": 100, "shirt": 80, "tee": 50, "hoodie": 120, "default": 90},
    
    # === LUXURY / DESIGNER ===
    "dior homme": {"jacket": 800, "pants": 400, "shirt": 350, "tee": 200, "default": 400},
    "dior": {"jacket": 700, "pants": 350, "shirt": 300, "tee": 180, "default": 350},
    "saint laurent": {"jacket": 700, "pants": 350, "shirt": 300, "tee": 180, "boots": 500, "default": 350},
    "slp": {"jacket": 700, "pants": 350, "shirt": 300, "tee": 180, "boots": 500, "default": 350},
    "gucci": {"jacket": 600, "pants": 300, "shirt": 280, "tee": 180, "default": 300},
    "prada": {"jacket": 600, "pants": 300, "shirt": 280, "tee": 180, "shoes": 400, "default": 300},
    "bottega veneta": {"jacket": 700, "pants": 350, "shirt": 300, "tee": 200, "default": 350},
    "louis vuitton": {"jacket": 800, "pants": 400, "shirt": 350, "tee": 250, "default": 400},
    "givenchy": {"jacket": 500, "pants": 280, "shirt": 250, "tee": 180, "default": 280},
    "alexander mcqueen": {"jacket": 500, "pants": 280, "shirt": 220, "tee": 150, "default": 280},
    "vivienne westwood": {"jacket": 350, "pants": 200, "shirt": 180, "tee": 100, "default": 200},
    "jean paul gaultier": {"jacket": 450, "pants": 250, "shirt": 200, "tee": 120, "default": 250},
    "acne studios": {"jacket": 400, "pants": 220, "shirt": 180, "tee": 100, "default": 200},
    "our legacy": {"jacket": 350, "pants": 200, "shirt": 150, "tee": 80, "default": 170},
    
    # === OTHER ===
    "enfants riches deprimes": {"jacket": 1500, "denim jacket": 800, "bomber": 1200, "pants": 400, "jeans": 500, "shirt": 400, "tee": 400, "long sleeve": 300, "hoodie": 500, "sweater": 600, "flannel": 400, "hat": 200, "belt": 500, "default": 400},
    "erd": {"jacket": 1500, "denim jacket": 800, "bomber": 1200, "pants": 400, "jeans": 500, "shirt": 400, "tee": 400, "long sleeve": 300, "hoodie": 500, "sweater": 600, "flannel": 400, "hat": 200, "belt": 500, "default": 400},
    "chrome hearts": {"jacket": 2000, "pants": 800, "shirt": 600, "tee": 400, "hoodie": 1000, "default": 800},
    "celine": {"jacket": 800, "leather jacket": 1200, "boots": 300, "belt": 200, "default": 400},
    "haider ackermann": {"jacket": 400, "leather jacket": 600, "blazer": 200, "coat": 350, "pants": 150, "default": 250},
    "dries van noten": {"jacket": 300, "leather jacket": 400, "coat": 300, "blazer": 200, "default": 200},
    "sacai": {"jacket": 300, "leather jacket": 500, "blazer": 200, "coat": 300, "default": 250},
    "guidi": {"boots": 300, "jacket": 400, "default": 300},
    "lemaire": {"jacket": 250, "leather jacket": 400, "coat": 300, "boots": 200, "default": 200},
    "acne studios": {"jacket": 250, "leather jacket": 350, "shearling": 400, "boots": 150, "default": 150},
    "simone rocha": {"dress": 200, "jacket": 200, "default": 180},
    "brunello cucinelli": {"jacket": 350, "leather jacket": 600, "sweater": 200, "coat": 400, "default": 250},
    "soloist": {"jacket": 300, "leather jacket": 500, "boots": 250, "default": 300},
    "takahiromiyashita": {"jacket": 300, "leather jacket": 500, "boots": 250, "default": 300},
    "hysteric glamour": {"jacket": 300, "leather jacket": 500, "denim jacket": 200, "jeans": 150, "tee": 100, "knit": 120, "default": 150},
    "louis vuitton": {"keepall": 800, "bag": 600, "wallet": 300, "trainer": 400, "default": 400},
    "chanel": {"classic flap": 4000, "bag": 2500, "espadrilles": 400, "slingbacks": 400, "default": 500},

    # Default for unknown brands
    "_default": {"jacket": 200, "pants": 120, "shirt": 100, "tee": 60, "hoodie": 150, "default": 100},
}


@dataclass
class PriceRecommendation:
    """Pricing recommendation for an item."""
    source_price: Decimal
    market_price: Optional[Decimal]
    recommended_price: Decimal
    margin_percent: float
    profit_estimate: Decimal
    confidence: str  # high, medium, low, skip
    reasoning: str
    comps_count: int = 0  # Number of sold comps used
    season_name: Optional[str] = None  # Detected iconic season
    season_multiplier: float = 1.0  # Price multiplier from season
    demand_level: str = "unknown"  # hot, warm, cold, dead
    demand_score: float = 0.0  # 0.0 to 1.0
    demand_reasoning: str = ""  # Human-readable demand explanation


class PriceCache:
    """Simple file-based cache for market prices."""
    
    def __init__(self, cache_file: str = CACHE_FILE, ttl: int = CACHE_TTL):
        self.cache_file = cache_file
        self.ttl = ttl
        self._cache = {}
        self._load()
    
    def _load(self):
        """Load cache from file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}
    
    def _save(self):
        """Save cache to file."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f)
        except Exception as e:
            print(f"Warning: Could not save price cache: {e}")
    
    def _make_key(self, brand: str, category: str = None) -> str:
        """Create cache key from brand and category."""
        key = brand.lower().strip()
        if category:
            key += f"_{category.lower().strip()}"
        return key
    
    def get(self, brand: str, category: str = None) -> Optional[dict]:
        """Get cached market data if not expired."""
        key = self._make_key(brand, category)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry.get("timestamp", 0) < self.ttl:
                return entry.get("data")
        return None
    
    def set(self, brand: str, category: str, data: dict):
        """Cache market data."""
        key = self._make_key(brand, category)
        self._cache[key] = {
            "timestamp": time.time(),
            "data": data,
        }
        self._save()


class PricingService:
    """
    Calculates optimal selling prices based on:
    - Live sold comps from Grailed (primary)
    - Cached market data (to avoid API hammering)
    - Static brand estimates (fallback)
    """
    
    # Pricing strategy params
    MIN_MARGIN_PERCENT = 0.25  # At least 25% margin
    TARGET_MARGIN_PERCENT = 0.35  # Target 35% margin
    MAX_MARKUP = 2.5  # Don't price more than 2.5x source cost
    
    # Price relative to market
    MARKET_DISCOUNT = 0.10  # Price 10% below market for quick sales
    
    # Minimum profit threshold
    MIN_PROFIT = 20  # At least $20 profit per item
    
    def __init__(self, grailed_scraper=None):
        """
        Initialize pricing service.
        
        Args:
            grailed_scraper: Optional GrailedScraper instance for live comps.
                           If not provided, will create one when needed.
        """
        self._grailed = grailed_scraper
        self._cache = PriceCache()
    
    def _detect_category(self, title: str) -> str:
        """Detect item category from title."""
        title_lower = title.lower()
        
        if any(x in title_lower for x in ["jacket", "blazer", "coat", "bomber", "parka", "varsity"]):
            return "jacket"
        elif any(x in title_lower for x in ["pants", "trousers", "jeans", "denim", "cargo"]):
            return "pants"
        elif any(x in title_lower for x in ["shirt", "button"]):
            return "shirt"
        elif any(x in title_lower for x in ["tee", "t-shirt", "tshirt"]):
            return "tee"
        elif any(x in title_lower for x in ["hoodie", "hooded", "sweatshirt"]):
            return "hoodie"
        elif any(x in title_lower for x in ["boot", "shoe", "sneaker"]):
            return "boots"
        elif any(x in title_lower for x in ["bag", "backpack", "tote"]):
            return "bag"
        elif any(x in title_lower for x in ["hat", "cap", "beanie"]):
            return "hat"
        
        return "default"
    
    def _get_static_estimate(self, brand: str, category: str) -> tuple[Decimal, str]:
        """Get static price estimate as fallback."""
        brand_lower = brand.lower() if brand else ""
        
        # Find matching brand
        brand_data = None
        for key, data in BRAND_MARKET_ESTIMATES.items():
            if key in brand_lower:
                brand_data = data
                break
        
        if not brand_data:
            brand_data = BRAND_MARKET_ESTIMATES["_default"]
            confidence = "low"
        else:
            confidence = "medium"
        
        price = brand_data.get(category, brand_data["default"])
        return Decimal(str(price)), confidence
    
    async def get_live_market_price(
        self,
        brand: str,
        category: str = None,
        title: str = "",
    ) -> tuple[Optional[Decimal], int, str]:
        """
        Get live market price from Grailed sold comps.
        
        Returns: (median_price, comps_count, confidence)
        """
        # Check cache first
        cached = self._cache.get(brand, category)
        if cached:
            return (
                Decimal(str(cached["median_price"])) if cached.get("median_price") else None,
                cached.get("comps_count", 0),
                "high" if cached.get("comps_count", 0) >= 5 else "medium",
            )
        
        # Need to fetch live data
        try:
            # Import here to avoid circular imports
            from scrapers.grailed import GrailedScraper
            
            # Build search query
            query = brand
            if category and category != "default":
                query += f" {category}"
            
            async with GrailedScraper() as scraper:
                sold_items = await scraper.search_sold(query, max_results=20)
            
            if not sold_items:
                return None, 0, "low"
            
            # Extract valid prices
            prices = [item.price for item in sold_items if item.price and item.price > 0]
            
            if not prices:
                return None, 0, "low"
            
            # Calculate median
            prices.sort()
            median_idx = len(prices) // 2
            median_price = prices[median_idx]
            
            # Cache the result
            self._cache.set(brand, category, {
                "median_price": float(median_price),
                "avg_price": sum(prices) / len(prices),
                "min_price": min(prices),
                "max_price": max(prices),
                "comps_count": len(prices),
            })
            
            confidence = "high" if len(prices) >= 5 else "medium"
            return Decimal(str(median_price)), len(prices), confidence
            
        except Exception as e:
            print(f"    ⚠ Live comps failed for {brand}: {e}")
            return None, 0, "low"
    
    async def calculate_price_async(
        self,
        source_price: float,
        brand: Optional[str] = None,
        title: str = "",
        shipping_cost: float = 0,
    ) -> PriceRecommendation:
        """
        Calculate recommended selling price using smart comp matching.
        
        Priority:
        1. Smart comp matcher (title-specific, similarity-weighted)
        2. Generic live comps (brand + category)
        3. Static estimates (fallback)
        """
        total_cost = Decimal(str(source_price)) + Decimal(str(shipping_cost))
        category = self._detect_category(title)
        
        market_price = None
        comps_count = 0
        confidence = "low"
        price_source = ""
        
        # Try smart comp matching first (title-specific)
        if brand and title:
            try:
                comp_result = await asyncio.wait_for(
                    find_best_comps(brand, title),
                    timeout=30,
                )
                
                if comp_result.comps_count >= 3 and comp_result.weighted_price > 0:
                    market_price = Decimal(str(comp_result.weighted_price))
                    comps_count = comp_result.comps_count
                    confidence = comp_result.confidence
                    hq = comp_result.high_quality_count
                    price_source = f"smart comps ({comps_count} found, {hq} matched)"
                    
                    # Cache for sync fallback
                    self._cache.set(brand, category, {
                        "median_price": float(comp_result.weighted_price),
                        "avg_price": float(comp_result.simple_median),
                        "min_price": float(min(c.price for c in comp_result.top_comps)) if comp_result.top_comps else 0,
                        "max_price": float(max(c.price for c in comp_result.top_comps)) if comp_result.top_comps else 0,
                        "comps_count": comps_count,
                    })
            except Exception as e:
                pass  # Fall through to generic comps
        
        # Fallback: generic live comps (brand + category)
        if market_price is None:
            try:
                live_price, live_count, live_conf = await asyncio.wait_for(
                    self.get_live_market_price(brand or "", category, title),
                    timeout=20,
                )
            except asyncio.TimeoutError:
                live_price, live_count, live_conf = None, 0, "low"
            
            if live_price and live_count > 0:
                market_price = live_price
                comps_count = live_count
                confidence = live_conf
                price_source = f"generic comps ({live_count} sold)"
        
        # Fallback: static estimates
        if market_price is None:
            market_price, confidence = self._get_static_estimate(brand or "", category)
            price_source = "estimated"
            comps_count = 0
        
        # Apply season detection for iconic collections
        # If smart comps already found specific matches, reduce the multiplier
        # since the comps already reflect the item-specific premium
        season_result = detect_season(brand or "", title)
        season_multiplier = 1.0
        season_name = None
        
        if season_result:
            raw_multiplier, season_name = season_result
            
            if "smart comps" in price_source and confidence in ("high", "medium"):
                # Smart comps already found specific matches — the comp prices
                # already reflect the season/collection premium. Don't double-count.
                # Only apply a tiny nudge (5% of the raw multiplier) for edge cases
                # where comps might be slightly generic.
                season_multiplier = 1.0 + (raw_multiplier - 1.0) * 0.05
                if season_multiplier > 1.01:
                    price_source += f" + {season_name} (comps already reflect premium)"
                else:
                    season_multiplier = 1.0
                    price_source += f" + {season_name} (absorbed by comps)"
            elif "generic comps" in price_source:
                # Generic comps (brand + category) don't capture season premium.
                # Apply a moderate boost — not full, since generic comps give
                # a rough baseline that partially overlaps.
                season_multiplier = 1.0 + (raw_multiplier - 1.0) * 0.6
                price_source += f" + {season_name} ({season_multiplier:.2f}x)"
            else:
                # Static estimates — apply full multiplier
                season_multiplier = raw_multiplier
                price_source += f" + {season_name} ({season_multiplier}x)"
            
            if season_multiplier > 1.0:
                market_price = market_price * Decimal(str(season_multiplier))
        
        # Score demand (velocity + supply)
        demand_level = "unknown"
        demand_score = 0.0
        demand_reasoning = ""
        
        if brand and title:
            try:
                demand = await asyncio.wait_for(
                    score_demand(brand, title),
                    timeout=20,
                )
                demand_level = demand.level
                demand_score = demand.score
                demand_reasoning = demand.reasoning
            except asyncio.TimeoutError:
                pass  # Demand scoring timed out — continue without it
            except Exception:
                pass
        
        rec = self._calculate_recommendation(
            total_cost, market_price, confidence, price_source, comps_count,
            season_name=season_name, season_multiplier=season_multiplier
        )
        rec.demand_level = demand_level
        rec.demand_score = demand_score
        rec.demand_reasoning = demand_reasoning
        return rec
    
    def calculate_price(
        self,
        source_price: float,
        brand: Optional[str] = None,
        title: str = "",
        shipping_cost: float = 0,
    ) -> PriceRecommendation:
        """
        Synchronous price calculation (uses cached data or static estimates).
        
        For live comps, use calculate_price_async() instead.
        """
        total_cost = Decimal(str(source_price)) + Decimal(str(shipping_cost))
        category = self._detect_category(title)
        
        # Check cache for live data
        cached = self._cache.get(brand or "", category)
        
        if cached and cached.get("median_price"):
            market_price = Decimal(str(cached["median_price"]))
            comps_count = cached.get("comps_count", 0)
            confidence = "high" if comps_count >= 5 else "medium"
            price_source = f"cached comps ({comps_count} sold)"
        else:
            # Fallback to static estimates
            market_price, confidence = self._get_static_estimate(brand or "", category)
            price_source = "estimated"
            comps_count = 0
        
        # Apply season detection for iconic collections
        season_result = detect_season(brand or "", title)
        season_multiplier = 1.0
        season_name = None
        
        if season_result:
            season_multiplier, season_name = season_result
            market_price = market_price * Decimal(str(season_multiplier))
            price_source += f" + {season_name} ({season_multiplier}x)"
        
        return self._calculate_recommendation(
            total_cost, market_price, confidence, price_source, comps_count,
            season_name=season_name, season_multiplier=season_multiplier
        )
    
    def _calculate_recommendation(
        self,
        total_cost: Decimal,
        market_price: Decimal,
        confidence: str,
        price_source: str,
        comps_count: int,
        season_name: Optional[str] = None,
        season_multiplier: float = 1.0,
    ) -> PriceRecommendation:
        """Calculate the final price recommendation."""
        
        # Target price: slightly below market
        target_price = market_price * Decimal(str(1 - self.MARKET_DISCOUNT))
        
        # Ensure minimum margin
        min_price = total_cost / Decimal(str(1 - self.MIN_MARGIN_PERCENT))
        
        # Cap at max markup
        max_price = total_cost * Decimal(str(self.MAX_MARKUP))
        
        # Check if item is worth listing
        potential_profit = target_price - total_cost
        
        if total_cost >= market_price * Decimal("0.75"):
            # Source price too close to market - not worth it
            return PriceRecommendation(
                source_price=total_cost,
                market_price=market_price,
                recommended_price=Decimal("0"),
                margin_percent=0,
                profit_estimate=Decimal("0"),
                confidence="skip",
                reasoning=f"Source ${total_cost:.0f} too close to market ${market_price:.0f} ({price_source}). Skip.",
                comps_count=comps_count,
                season_name=season_name,
                season_multiplier=season_multiplier,
            )
        
        if potential_profit < self.MIN_PROFIT:
            # Not enough profit margin
            return PriceRecommendation(
                source_price=total_cost,
                market_price=market_price,
                recommended_price=Decimal("0"),
                margin_percent=0,
                profit_estimate=potential_profit,
                confidence="skip",
                reasoning=f"Profit ${potential_profit:.0f} below ${self.MIN_PROFIT} minimum ({price_source}). Skip.",
                comps_count=comps_count,
                season_name=season_name,
                season_multiplier=season_multiplier,
            )
        
        # Determine recommended price
        if target_price < min_price:
            recommended = min_price
            reasoning = f"Priced at min margin. Market ~${market_price:.0f} ({price_source})."
        elif target_price > max_price:
            recommended = max_price
            reasoning = f"Capped at {self.MAX_MARKUP}x. Market ~${market_price:.0f} ({price_source})."
        else:
            recommended = target_price
            reasoning = f"{self.MARKET_DISCOUNT*100:.0f}% below market ${market_price:.0f} ({price_source})."
        
        # Round to .99
        recommended = Decimal(str(int(recommended))) + Decimal("0.99")
        
        # Final margin check
        if recommended - total_cost < self.MIN_PROFIT:
            recommended = total_cost + Decimal(str(self.MIN_PROFIT + 5))
        
        margin = (recommended - total_cost) / recommended
        profit = recommended - total_cost
        
        return PriceRecommendation(
            source_price=total_cost,
            market_price=market_price,
            recommended_price=recommended,
            margin_percent=float(margin),
            profit_estimate=profit,
            confidence=confidence,
            reasoning=reasoning,
            comps_count=comps_count,
            season_name=season_name,
            season_multiplier=season_multiplier,
        )


# Convenience functions
def calculate_price(
    source_price: float,
    brand: Optional[str] = None,
    title: str = "",
    shipping_cost: float = 0,
) -> PriceRecommendation:
    """Quick synchronous pricing calculation (uses cache/estimates)."""
    service = PricingService()
    return service.calculate_price(source_price, brand, title, shipping_cost)


async def calculate_price_async(
    source_price: float,
    brand: Optional[str] = None,
    title: str = "",
    shipping_cost: float = 0,
) -> PriceRecommendation:
    """Quick async pricing calculation with live comps."""
    service = PricingService()
    return await service.calculate_price_async(source_price, brand, title, shipping_cost)
