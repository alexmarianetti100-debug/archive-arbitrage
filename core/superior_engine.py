"""Superior arbitrage engine - integrates all speed & quality improvements."""

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from core.redis_cache import get_cache
from core.hot_item_index import HotItemIndex
from core.fast_polling import FastPollingScheduler
from core.ml_scorer import get_scorer, DealFeatures

class SuperiorArbitrageEngine:
    """High-speed, ML-powered arbitrage engine."""
    
    def __init__(self):
        self.cache: Optional[Any] = None
        self.hot_index = HotItemIndex()
        self.scheduler = FastPollingScheduler()
        self.scorer = get_scorer()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        print("Initializing Superior Arbitrage Engine...")
        
        # Connect Redis
        self.cache = await get_cache()
        if self.cache._client:
            print("  ✓ Redis connected")
        else:
            print("  ⚠ Redis unavailable (using memory cache)")
        
        # Load hot items
        count = self.hot_index.load_from_catalog()
        print(f"  ✓ Hot item index: {count} items")
        
        # Setup high-priority polling
        high_priority = self.hot_index.get_high_priority(min_priority=7)
        for item in high_priority[:20]:  # Top 20
            self.scheduler.add_task(
                name=f"poll_{item.query[:30]}",
                query=item.query,
                callback=self._on_poll,
                base_interval=30 if item.priority >= 9 else 60,
                priority=item.priority,
            )
        
        print(f"  ✓ Polling scheduler: {len(self.scheduler.tasks)} tasks")
        print(f"    - Tier 1 (10): {sum(1 for t in self.scheduler.tasks.values() if t.priority == 10)}")
        print(f"    - Tier 2 (7-9): {sum(1 for t in self.scheduler.tasks.values() if 7 <= t.priority <= 9)}")
        
        self._initialized = True
        return True
    
    async def _on_poll(self, query: str) -> bool:
        """Callback when poll finds a potential deal."""
        # This would integrate with existing gap_hunter logic
        # For now, just return True to simulate finding deals
        return False
    
    async def process_listing(self, listing: Dict[str, Any]) -> Optional[Dict]:
        """Process a new listing through the fast pipeline."""
        start_time = datetime.now()
        
        # 1. O(1) hot item match
        title = listing.get("title", "")
        brand = listing.get("brand", "")
        
        match = self.hot_index.match(title, brand)
        if not match:
            return None  # Not a hot item
        
        # 2. Check cache (avoid duplicate processing)
        cache_key = f"listing:{listing.get('id', '')}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return None  # Already processed
            await self.cache.set(cache_key, True, ttl=300)  # 5 min TTL
        
        # 3. ML scoring
        features = DealFeatures(
            list_price=listing.get("price", 0),
            market_price=match.max_price * 1.33,  # Reverse engineer
            gap_percent=(match.max_price * 1.33 - listing.get("price", 0)) / (match.max_price * 1.33),
            profit_estimate=match.max_price * 1.33 - listing.get("price", 0),
            brand=brand,
            category=match.category,
            condition=listing.get("condition", "unknown"),
            has_box=listing.get("has_box", False),
            has_dustbag=listing.get("has_dustbag", False),
            seller_rating=listing.get("seller_rating", 0),
            seller_sales=listing.get("seller_sales", 0),
            seller_country=listing.get("seller_country", ""),
            days_since_last_sale=0,
            comps_count=0,
            price_trend=0,
            image_quality_score=0.8,
            condition_score=0.8,
            day_of_week=datetime.now().weekday(),
            hour_of_day=datetime.now().hour,
            is_weekend=datetime.now().weekday() >= 5,
        )
        
        score_result = self.scorer.score(features)
        
        # 4. Decision
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        if score_result["score"] >= 0.7:  # High confidence threshold
            return {
                "query": match.query,
                "title": title,
                "price": listing.get("price"),
                "max_price": match.max_price,
                "score": score_result["score"],
                "confidence": score_result["confidence"],
                "processing_time_ms": elapsed_ms,
                "action": "ALERT",
            }
        
        return None
    
    async def start(self):
        """Start the engine."""
        if not self._initialized:
            await self.initialize()
        
        await self.scheduler.start()
        print("\n✓ Superior Arbitrage Engine running")
        print(f"  Target latency: 30-60 seconds")
        print(f"  ML scoring: {'XGBoost' if self.scorer.model else 'rule-based'}")
    
    async def stop(self):
        """Stop the engine."""
        await self.scheduler.stop()
        if self.cache:
            await self.cache.close()
        print("✓ Engine stopped")
    
    def get_stats(self) -> Dict:
        """Get engine statistics."""
        return {
            "hot_items": len(self.hot_index.items),
            "polling_tasks": len(self.scheduler.tasks),
            "scheduler_stats": self.scheduler.get_stats(),
            "ml_model_loaded": self.scorer.model is not None,
        }
