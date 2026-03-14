"""
Pricing Engine - Centralized pricing logic with caching and statistics.

Manages sold price caching with:
- Cache statistics tracking
- Cache warming for high-velocity queries
- Manual cache management
- Performance metrics
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("pricing_engine")

DEFAULT_CACHE_FILE = Path(__file__).parent.parent / "data" / "sold_cache.json"
DEFAULT_TTL_SECONDS = 14400  # 4 hours — must exceed QUERY_COOLDOWN_MINUTES (120min) for cache hits


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    data: Any
    timestamp: float
    query: str
    hit_count: int = 0
    
    def is_expired(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.timestamp > ttl_seconds
    
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.timestamp
    
    def record_hit(self):
        """Record a cache hit."""
        self.hit_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics."""
    total_entries: int = 0
    expired_entries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    avg_hit_count: float = 0.0
    oldest_entry_age: float = 0.0
    newest_entry_age: float = 0.0
    memory_size_bytes: int = 0


class PricingEngine:
    """
    Centralized pricing engine with intelligent caching.
    
    Usage:
        engine = PricingEngine()
        
        # Get sold comps (uses cache)
        comps = engine.get_sold_comps("rick owens dunks")
        
        # Check cache stats
        stats = engine.get_cache_stats()
        print(f"Cache hit rate: {stats.hit_rate:.1%}")
        
        # Warm cache for important queries
        engine.warm_cache(["rick owens dunks", "raf simons bomber"])
        
        # Flush expired entries
        engine.flush_expired()
    """
    
    def __init__(self, cache_file: Optional[Path] = None, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.cache_file = cache_file or DEFAULT_CACHE_FILE
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "api_calls": 0,
            "api_calls_saved": 0,  # NEW: Track API calls saved by caching
            "last_saved": 0,
        }
        
        # Load existing cache
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk."""
        if not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            # Convert to CacheEntry objects
            for key, entry_data in data.items():
                if isinstance(entry_data, dict) and 'data' in entry_data:
                    self._cache[key] = CacheEntry(
                        data=entry_data['data'],
                        timestamp=entry_data.get('timestamp', 0),
                        query=entry_data.get('query', key),
                        hit_count=entry_data.get('hit_count', 0),
                    )
            
            logger.info(f"Loaded pricing cache: {len(self._cache)} entries")
            
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self._cache = {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Convert to serializable format
            data = {}
            for key, entry in self._cache.items():
                data[key] = {
                    'data': entry.data,
                    'timestamp': entry.timestamp,
                    'query': entry.query,
                    'hit_count': entry.hit_count,
                }
            
            # Atomic write
            temp_file = self.cache_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self.cache_file)
            
            self._stats["last_saved"] = time.time()
            logger.debug(f"Saved pricing cache: {len(self._cache)} entries")
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def get(self, query: str, fetch_func=None) -> Tuple[Any, bool]:
        """
        Get data from cache or fetch if missing/expired.
        
        Args:
            query: Cache key (e.g., search query)
            fetch_func: Function to fetch data if not in cache
            
        Returns:
            (data, was_cached)
        """
        key = query.lower().strip()
        
        # Check cache
        if key in self._cache:
            entry = self._cache[key]
            
            if not entry.is_expired(self.ttl_seconds):
                # Cache hit
                entry.record_hit()
                self._stats["hits"] += 1
                self._stats["api_calls_saved"] += 1  # Track API call saved
                logger.debug(f"Cache hit for '{query}' (age: {entry.age_seconds()/60:.0f}min, hits: {entry.hit_count}, api_saved: {self._stats['api_calls_saved']})")
                return entry.data, True
            else:
                # Expired
                logger.debug(f"Cache expired for '{query}' (age: {entry.age_seconds()/60:.0f}min)")
                del self._cache[key]
        
        # Cache miss - fetch if function provided
        self._stats["misses"] += 1
        
        if fetch_func:
            logger.debug(f"Cache miss for '{query}' - fetching...")
            data = fetch_func(query)
            self._stats["api_calls"] += 1
            
            # Store in cache
            self._cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                query=query,
            )
            
            # Save periodically (every 5 minutes)
            if time.time() - self._stats["last_saved"] > 300:
                self._save_cache()
            
            return data, False
        
        return None, False
    
    def get_price(self, query: str) -> Optional[CacheEntry]:
        """Get cached price data for a query (compatibility method)."""
        key = query.lower().strip()
        
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired(self.ttl_seconds):
                entry.record_hit()
                self._stats["hits"] += 1
                self._stats["api_calls_saved"] += 1
                return entry
            else:
                del self._cache[key]
        
        self._stats["misses"] += 1
        return None
    
    def set_price(self, query: str, price: float, source: str = "unknown"):
        """Set price in cache (compatibility method)."""
        key = query.lower().strip()
        
        self._cache[key] = CacheEntry(
            data={"price": price, "source": source},
            timestamp=time.time(),
            query=query,
        )
        
        self._stats["api_calls"] += 1
        
        # Save periodically
        if time.time() - self._stats["last_saved"] > 300:
            self._save_cache()
    
    def set(self, query: str, data: Any):
        """Manually set cache entry."""
        key = query.lower().strip()
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            query=query,
        )
    
    def warm_cache(self, queries: List[str], fetch_func):
        """
        Pre-fetch and cache data for important queries.
        
        Args:
            queries: List of queries to warm
            fetch_func: Function to fetch data
        """
        logger.info(f"Warming cache for {len(queries)} queries...")
        
        warmed = 0
        for query in queries:
            key = query.lower().strip()
            
            # Skip if already cached and not expired
            if key in self._cache and not self._cache[key].is_expired(self.ttl_seconds):
                continue
            
            try:
                data = fetch_func(query)
                self._cache[key] = CacheEntry(
                    data=data,
                    timestamp=time.time(),
                    query=query,
                )
                warmed += 1
                self._stats["api_calls"] += 1
            except Exception as e:
                logger.warning(f"Failed to warm cache for '{query}': {e}")
        
        if warmed > 0:
            self._save_cache()
            logger.info(f"Warmed cache: {warmed} queries")
    
    def flush_expired(self) -> int:
        """Remove expired entries from cache. Returns count removed."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired(self.ttl_seconds)
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._save_cache()
            logger.info(f"Flushed {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def clear(self):
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._save_cache()
        logger.info(f"Cleared cache: {count} entries removed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._cache:
            return {
                "entries": 0,
                "expired": 0,
                "hit_rate": 0.0,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "api_calls": self._stats["api_calls"],
                "api_calls_saved": self._stats.get("api_calls_saved", 0),
                "avg_hits_per_entry": 0,
                "oldest_entry_hours": 0,
                "newest_entry_hours": 0,
                "memory_size_kb": 0,
                "ttl_hours": self.ttl_seconds / 3600,
            }
        
        total_hits = sum(e.hit_count for e in self._cache.values())
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        ages = [e.age_seconds() for e in self._cache.values()]
        expired_count = sum(1 for e in self._cache.values() if e.is_expired(self.ttl_seconds))
        
        # Estimate memory size
        try:
            import sys
            memory_size = sum(
                sys.getsizeof(json.dumps(e.data))
                for e in self._cache.values()
            )
        except:
            memory_size = 0
        
        return {
            "entries": len(self._cache),
            "expired": expired_count,
            "hit_rate": hit_rate,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "api_calls": self._stats["api_calls"],
            "avg_hits_per_entry": total_hits / len(self._cache) if self._cache else 0,
            "oldest_entry_hours": max(ages) / 3600 if ages else 0,
            "newest_entry_hours": min(ages) / 3600 if ages else 0,
            "memory_size_kb": memory_size / 1024,
            "ttl_hours": self.ttl_seconds / 3600,
        }
    
    def get_popular_queries(self, min_hits: int = 2) -> List[Tuple[str, int]]:
        """Get most frequently accessed queries."""
        popular = [
            (entry.query, entry.hit_count)
            for entry in self._cache.values()
            if entry.hit_count >= min_hits
        ]
        popular.sort(key=lambda x: x[1], reverse=True)
        return popular[:20]  # Top 20


# Convenience functions for CLI usage

def show_cache_stats():
    """CLI helper to show cache statistics."""
    engine = PricingEngine()
    stats = engine.get_stats()
    
    print("\n📊 Pricing Cache Statistics\n")
    print(f"{'Metric':<25} {'Value':<20}")
    print("-" * 50)
    print(f"{'Cache entries':<25} {stats['entries']:<20}")
    print(f"{'Expired entries':<25} {stats['expired']:<20}")
    print(f"{'Hit rate':<25} {stats['hit_rate']:.1%}")
    print(f"{'Total hits':<25} {stats['hits']:<20}")
    print(f"{'Total misses':<25} {stats['misses']:<20}")
    print(f"{'API calls made':<25} {stats['api_calls']:<20}")
    print(f"{'API calls saved':<25} {stats.get('api_calls_saved', 0):<20}")
    print(f"{'Avg hits per entry':<25} {stats['avg_hits_per_entry']:.1f}")
    print(f"{'Oldest entry':<25} {stats['oldest_entry_hours']:.1f} hours")
    print(f"{'Newest entry':<25} {stats['newest_entry_hours']:.1f} hours")
    print(f"{'Memory size':<25} {stats['memory_size_kb']:.1f} KB")
    print(f"{'TTL':<25} {stats['ttl_hours']:.0f} hours")
    
    # Show popular queries
    popular = engine.get_popular_queries(min_hits=2)
    if popular:
        print(f"\n🔥 Popular Queries (2+ hits):\n")
        for query, hits in popular[:10]:
            print(f"  {hits:3d} hits: {query[:50]}")


def flush_cache():
    """CLI helper to flush expired cache entries."""
    engine = PricingEngine()
    removed = engine.flush_expired()
    print(f"\n🗑️  Flushed {removed} expired cache entries")


def clear_cache():
    """CLI helper to clear all cache entries."""
    engine = PricingEngine()
    
    confirm = input("\n⚠️  Clear ALL cache entries? Type 'CLEAR' to confirm: ")
    if confirm == "CLEAR":
        engine.clear()
        print("✅ Cache cleared")
    else:
        print("Cancelled")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pricing Engine Cache Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Stats command
    subparsers.add_parser("stats", help="Show cache statistics")
    
    # Flush command
    subparsers.add_parser("flush", help="Flush expired entries")
    
    # Clear command
    subparsers.add_parser("clear", help="Clear all entries")
    
    args = parser.parse_args()
    
    if args.command == "stats":
        show_cache_stats()
    elif args.command == "flush":
        flush_cache()
    elif args.command == "clear":
        clear_cache()
    else:
        show_cache_stats()
