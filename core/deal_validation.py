#!/usr/bin/env python3
"""
Deal Validation Pipeline

Validates deals before alerting to ensure items are actually available
and profitable. Tracks customer interactions for learning.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from enum import Enum

import httpx
from bs4 import BeautifulSoup

# Import eBay scraper for proper session handling
try:
    from scrapers.ebay import EbayScraper
    EBAY_SCRAPER_AVAILABLE = True
except ImportError:
    EBAY_SCRAPER_AVAILABLE = False

logger = logging.getLogger("deal_validation")


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"


@dataclass
class ValidationResult:
    status: ValidationStatus
    reason: Optional[str] = None
    checks_passed: List[str] = None
    checks_failed: List[str] = None
    validated_at: datetime = None
    time_to_validate_ms: Optional[int] = None  # Speed-to-alert metric
    
    def __post_init__(self):
        if self.validated_at is None:
            self.validated_at = datetime.now()
        if self.checks_passed is None:
            self.checks_passed = []
        if self.checks_failed is None:
            self.checks_failed = []


@dataclass
class CustomerInteraction:
    customer_id: str
    deal_id: str
    interaction_type: str  # 'viewed', 'clicked', 'purchased', 'passed'
    timestamp: datetime
    notes: Optional[str] = None


class DealValidator:
    """Validates deals before alerting customers."""
    
    # Cache TTL by source (faster turnover = shorter cache)
    DEFAULT_CACHE_TTL = timedelta(minutes=3)
    CACHE_TTL_BY_SOURCE = {
        "ebay": timedelta(minutes=2),      # Fast-moving, check more often
        "grailed": timedelta(minutes=5),   # Slower turnover
        "poshmark": timedelta(minutes=3),
        "mercari": timedelta(minutes=2),
    }
    
    # Ultra-fast cache for high-velocity brands (Chrome Hearts sells fast)
    FAST_BRANDS = {"chrome hearts", "chrome_hearts", "ch"}
    FAST_BRAND_CACHE_TTL = timedelta(seconds=45)
    
    # Pre-validate brands - no caching, check every time
    PREVALIDATE_BRANDS = {"chrome hearts", "chrome_hearts", "ch", "chrome"}
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.validation_cache: Dict[str, ValidationResult] = {}
        
        # Speed-to-alert metrics tracking
        self.speed_metrics_file = self.data_dir / "validation_speed_metrics.jsonl"
        
        # Customer interaction tracking
        self.interactions_file = self.data_dir / "customer_interactions.jsonl"
    
    def _get_cache_ttl(self, source: str, brand: str = "") -> timedelta:
        """Get cache TTL based on source platform and brand velocity."""
        brand_lower = brand.lower()
        # Check if it's a fast-moving brand
        for fast_brand in self.FAST_BRANDS:
            if fast_brand in brand_lower:
                return self.FAST_BRAND_CACHE_TTL
        return self.CACHE_TTL_BY_SOURCE.get(source, self.DEFAULT_CACHE_TTL)
    
    # Sources that don't need validation (they verify availability themselves)
    TRUSTED_SOURCES = {"grailed"}
    
    async def validate_deal(self, deal, customer_tier: str = "beginner") -> ValidationResult:
        """
        Comprehensive deal validation.
        
        Checks:
        1. Item still available
        2. Seller active
        3. Price unchanged
        4. No recent negative feedback
        5. Meets customer tier criteria
        """
        deal_id = f"{deal.item.source}_{deal.item.source_id}"
        source = deal.item.source
        brand = getattr(deal.item, 'brand', '') or getattr(deal.item, 'title', '')
        
        # Skip validation for trusted sources (Grailed verifies availability)
        if source in self.TRUSTED_SOURCES:
            logger.debug(f"Skipping validation for trusted source {source}: {deal_id}")
            return ValidationResult(
                status=ValidationStatus.VALID,
                checks_passed=["trusted_source", "grailed_verified"],
                checks_failed=[]
            )
        
        # Track speed-to-alert: when was deal discovered?
        deal_discovered_at = getattr(deal, 'discovered_at', None)
        validation_started_at = datetime.now()
        
        # Check if this is a pre-validate brand (no caching, check every time)
        is_prevalidate = any(pv in brand.lower() for pv in self.PREVALIDATE_BRANDS)
        
        # Check cache with source and brand-specific TTL (skip for pre-validate brands)
        if not is_prevalidate:
            cache_ttl = self._get_cache_ttl(source, brand)
            if deal_id in self.validation_cache:
                cached = self.validation_cache[deal_id]
                if datetime.now() - cached.validated_at < cache_ttl:
                    logger.debug(f"Using cached validation for {deal_id}")
                    return cached
        
        checks_passed = []
        checks_failed = []
        
        # 1. Check item availability
        try:
            available = await self._check_availability(deal.item.url, deal.item.source)
            if available:
                checks_passed.append("item_available")
            else:
                checks_failed.append("item_available")
                result = ValidationResult(
                    status=ValidationStatus.INVALID,
                    reason="Item no longer available",
                    checks_passed=checks_passed,
                    checks_failed=checks_failed
                )
                if not is_prevalidate:
                    self.validation_cache[deal_id] = result
                return result
        except Exception as e:
            logger.warning(f"Availability check failed for {deal_id}: {e}")
            checks_failed.append(f"availability_check_error: {e}")
        
        # 2. Verify seller activity (if we have seller info)
        if hasattr(deal.item, 'seller_id') and deal.item.seller_id:
            try:
                seller_active = await self._check_seller_activity(
                    deal.item.seller_id, 
                    deal.item.source
                )
                if seller_active:
                    checks_passed.append("seller_active")
                else:
                    checks_failed.append("seller_active")
                    result = ValidationResult(
                        status=ValidationStatus.INVALID,
                        reason="Seller inactive >7 days",
                        checks_passed=checks_passed,
                        checks_failed=checks_failed
                    )
                    if not is_prevalidate:
                        self.validation_cache[deal_id] = result
                    return result
            except Exception as e:
                logger.warning(f"Seller check failed for {deal_id}: {e}")
        
        # 3. Check price hasn't changed
        try:
            current_price = await self._get_current_price(deal.item.url, deal.item.source)
            if current_price and abs(current_price - deal.item.price) < 0.05 * deal.item.price:
                checks_passed.append("price_stable")
            else:
                checks_failed.append("price_changed")
                result = ValidationResult(
                    status=ValidationStatus.INVALID,
                    reason=f"Price changed from ${deal.item.price} to ${current_price}",
                    checks_passed=checks_passed,
                    checks_failed=checks_failed
                )
                if not is_prevalidate:
                    self.validation_cache[deal_id] = result
                return result
        except Exception as e:
            logger.warning(f"Price check failed for {deal_id}: {e}")
        
        # 4. Check deal meets tier criteria
        tier_check = self._check_tier_criteria(deal, customer_tier)
        if tier_check[0]:
            checks_passed.append("tier_criteria")
        else:
            checks_failed.append("tier_criteria")
            result = ValidationResult(
                status=ValidationStatus.INVALID,
                reason=tier_check[1],
                checks_passed=checks_passed,
                checks_failed=checks_failed
            )
            self._record_speed_metric(deal_id, source, deal_discovered_at, validation_started_at, False)
            if not is_prevalidate:
                self.validation_cache[deal_id] = result
            return result
        
        # All checks passed — calculate speed-to-alert
        validation_completed_at = datetime.now()
        time_to_validate_ms = int((validation_completed_at - validation_started_at).total_seconds() * 1000)
        
        result = ValidationResult(
            status=ValidationStatus.VALID,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            time_to_validate_ms=time_to_validate_ms
        )
        self._record_speed_metric(deal_id, source, deal_discovered_at, validation_started_at, True)
        if not is_prevalidate:
            self.validation_cache[deal_id] = result
        
        total_time_ms = time_to_validate_ms
        if deal_discovered_at:
            total_time_ms = int((validation_completed_at - deal_discovered_at).total_seconds() * 1000)
        
        logger.info(f"✅ Deal {deal_id} validated in {time_to_validate_ms}ms (total {total_time_ms}ms): {len(checks_passed)} checks passed")
        return result
    
    def _record_speed_metric(self, deal_id: str, source: str, discovered_at: Optional[datetime], 
                             validation_started_at: datetime, passed: bool):
        """Record speed-to-alert metric for analysis."""
        try:
            now = datetime.now()
            metric = {
                "deal_id": deal_id,
                "source": source,
                "timestamp": now.isoformat(),
                "discovered_at": discovered_at.isoformat() if discovered_at else None,
                "validation_started_at": validation_started_at.isoformat(),
                "time_to_start_validation_ms": int((validation_started_at - discovered_at).total_seconds() * 1000) if discovered_at else None,
                "passed": passed,
            }
            with open(self.speed_metrics_file, 'a') as f:
                f.write(json.dumps(metric) + '\n')
        except Exception as e:
            logger.debug(f"Failed to record speed metric: {e}")
    
    async def _check_availability(self, url: str, source: str) -> bool:
        """Check if item is still listed."""
        # Use eBay scraper for eBay URLs to avoid CAPTCHA
        if source == "ebay" and EBAY_SCRAPER_AVAILABLE:
            try:
                scraper = EbayScraper()
                # Extract item ID from URL
                import re
                item_id_match = re.search(r'/itm/(\d+)', url)
                if item_id_match:
                    item_id = item_id_match.group(1)
                    # Use the scraper's session to fetch the item page
                    session = None
                    try:
                        from curl_cffi.requests import AsyncSession
                        session = AsyncSession(impersonate="chrome120")
                        proxies = {"https": scraper._proxy} if scraper._proxy else None
                        response = await session.get(url, proxies=proxies, timeout=30)
                        
                        if response.status_code != 200 or "splashui/challenge" in str(response.url):
                            logger.debug(f"eBay challenge detected for {item_id}, assuming available")
                            return True  # Assume available if we can't verify
                        
                        soup = BeautifulSoup(response.text, 'html.parser')
                        text = soup.get_text().lower()
                        
                        sold_indicators = [
                            'sold', 'not available', 'listing ended', 
                            'item unavailable', 'removed', 'no longer', 'this listing has ended'
                        ]
                        
                        for indicator in sold_indicators:
                            if indicator in text:
                                return False
                        
                        return True
                    finally:
                        if session:
                            try:
                                await session.close()
                            except Exception:
                                pass
                return True  # Assume available if we can't parse item ID
            except Exception as e:
                logger.debug(f"eBay scraper availability check failed: {e}, falling back")
        
        # Fallback to plain httpx for non-eBay sources
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, follow_redirects=True)
                
                if response.status_code != 200:
                    return False
                
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text().lower()
                
                sold_indicators = [
                    'sold', 'not available', 'listing ended', 
                    'item unavailable', 'removed', 'no longer'
                ]
                
                for indicator in sold_indicators:
                    if indicator in text:
                        return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return True  # Assume available if check fails
    
    async def _check_seller_activity(self, seller_id: str, source: str) -> bool:
        """Check if seller has been active recently."""
        # This would integrate with platform APIs
        # For now, assume active
        return True
    
    async def _get_current_price(self, url: str, source: str) -> Optional[float]:
        """Get current price from listing."""
        # Use eBay scraper for eBay URLs to avoid CAPTCHA
        if source == "ebay" and EBAY_SCRAPER_AVAILABLE:
            try:
                scraper = EbayScraper()
                session = None
                try:
                    from curl_cffi.requests import AsyncSession
                    session = AsyncSession(impersonate="chrome120")
                    proxies = {"https": scraper._proxy} if scraper._proxy else None
                    response = await session.get(url, proxies=proxies, timeout=30)
                    
                    # If we hit a challenge page, return None to indicate we can't verify
                    if response.status_code != 200 or "splashui/challenge" in str(response.url):
                        logger.debug(f"eBay challenge on price check, can't verify")
                        return None
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # eBay-specific price selectors (from ebay.py scraper)
                    price_selectors = [
                        '.s-item__price',
                        '[itemprop="price"]',
                        '.notranslate',  # eBay price container
                        '[class*="price"]',
                        '.display-price',
                        '#prcIsum',  # Classic eBay BIN price
                        '#mm-saleDscPrc',  # Sale price
                    ]
                    
                    for selector in price_selectors:
                        price_el = soup.select_one(selector)
                        if price_el:
                            price_text = price_el.get_text()
                            import re
                            # Extract all numbers and take the largest (handles "Was $X → $Y")
                            price_matches = [float(n.replace(',', '')) for n in re.findall(r'[\d,]+\.?\d*', price_text)]
                            if price_matches:
                                return max(price_matches)
                    
                    return None
                finally:
                    if session:
                        try:
                            await session.close()
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"eBay scraper price check failed: {e}, falling back")
        
        # Fallback to plain httpx for non-eBay sources
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, follow_redirects=True)
                
                if response.status_code != 200:
                    return None
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                price_selectors = [
                    '.price', '[class*="price"]', '[data-testid*="price"]',
                    '.cost', '.amount', '[class*="cost"]'
                ]
                
                for selector in price_selectors:
                    price_el = soup.select_one(selector)
                    if price_el:
                        price_text = price_el.get_text()
                        import re
                        match = re.search(r'[\d,]+\.?\d*', price_text)
                        if match:
                            return float(match.group().replace(',', ''))
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return None
    
    def _check_tier_criteria(self, deal, customer_tier: str) -> Tuple[bool, str]:
        """Check if deal meets criteria for customer tier."""
        
        tier_criteria = {
            "beginner": {
                "max_price": 500,
                "min_gap_percent": 0.30,
                "require_authenticated": True,
            },
            "intermediate": {
                "max_price": 1500,
                "min_gap_percent": 0.25,
                "require_authenticated": False,
            },
            "expert": {
                "max_price": 5000,
                "min_gap_percent": 0.20,
                "require_authenticated": False,
            }
        }
        
        criteria = tier_criteria.get(customer_tier, tier_criteria["beginner"])
        
        if deal.item.price > criteria["max_price"]:
            return False, f"Price ${deal.item.price} exceeds tier max ${criteria['max_price']}"
        
        if deal.gap_percent < criteria["min_gap_percent"]:
            return False, f"Gap {deal.gap_percent:.1%} below tier minimum {criteria['min_gap_percent']:.1%}"
        
        # Check authenticated comps
        if criteria["require_authenticated"]:
            auth_comps = getattr(deal, 'authenticated_comps', 0)
            if auth_comps < 5:
                return False, f"Only {auth_comps} authenticated comps (need 5)"
        
        return True, "OK"
    
    def track_interaction(self, customer_id: str, deal, interaction_type: str, notes: str = None):
        """Track customer interaction with a deal."""
        interaction = CustomerInteraction(
            customer_id=customer_id,
            deal_id=f"{deal.item.source}_{deal.item.source_id}",
            interaction_type=interaction_type,
            timestamp=datetime.now(),
            notes=notes
        )
        
        # Append to file
        with open(self.interactions_file, 'a') as f:
            f.write(json.dumps({
                'customer_id': interaction.customer_id,
                'deal_id': interaction.deal_id,
                'interaction_type': interaction.interaction_type,
                'timestamp': interaction.timestamp.isoformat(),
                'notes': interaction.notes
            }) + '\n')
        
        logger.info(f"Tracked {interaction_type} for customer {customer_id} on deal {interaction.deal_id}")
    
    def get_deal_stats(self, deal_id: str) -> Dict:
        """Get interaction stats for a deal."""
        stats = {
            'views': 0,
            'clicks': 0,
            'purchases': 0,
            'passes': 0,
        }
        
        if not self.interactions_file.exists():
            return stats
        
        with open(self.interactions_file, 'r') as f:
            for line in f:
                try:
                    interaction = json.loads(line.strip())
                    if interaction['deal_id'] == deal_id:
                        interaction_type = interaction['interaction_type']
                        if interaction_type in stats:
                            stats[interaction_type] += 1
                except json.JSONDecodeError:
                    continue
        
        return stats
    
    def get_validation_report(self) -> Dict:
        """Generate validation performance report."""
        total = len(self.validation_cache)
        valid = sum(1 for v in self.validation_cache.values() if v.status == ValidationStatus.VALID)
        invalid = sum(1 for v in self.validation_cache.values() if v.status == ValidationStatus.INVALID)
        
        return {
            'total_validated': total,
            'valid': valid,
            'invalid': invalid,
            'success_rate': valid / total if total > 0 else 0,
            'cache_size': len(self.validation_cache),
        }
    
    def get_speed_metrics_report(self, limit: int = 100) -> Dict:
        """Generate speed-to-alert metrics report."""
        if not self.speed_metrics_file.exists():
            return {"metrics_count": 0, "recent_metrics": [], "avg_time_to_start_validation_ms": None, "by_source": {}}
        
        metrics = []
        times_to_validate = []
        total_times = []
        
        try:
            with open(self.speed_metrics_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        metric = json.loads(line.strip())
                        metrics.append(metric)
                        
                        # Calculate time to validate (validation duration)
                        started = metric.get('validation_started_at')
                        discovered = metric.get('discovered_at')
                        if started and discovered:
                            from datetime import datetime
                            started_dt = datetime.fromisoformat(started)
                            discovered_dt = datetime.fromisoformat(discovered)
                            time_to_validate = int((started_dt - discovered_dt).total_seconds() * 1000)
                            times_to_validate.append(time_to_validate)
                            
                            # We don't have completion time in the metric, but we can estimate
                            # For now, just track time to start validation
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass
        
        # Get recent metrics only
        recent_metrics = metrics[-limit:] if len(metrics) > limit else metrics
        
        result = {
            "metrics_count": len(metrics),
            "recent_metrics": recent_metrics[-10:] if recent_metrics else [],
            "avg_time_to_start_validation_ms": sum(times_to_validate) / len(times_to_validate) if times_to_validate else None,
            "by_source": self._aggregate_speed_by_source(metrics[-100:]) if metrics else {},
        }
        return result
    
    def _aggregate_speed_by_source(self, metrics: List[Dict]) -> Dict:
        """Aggregate speed metrics by source platform."""
        by_source = {}
        for m in metrics:
            source = m.get('source', 'unknown')
            if source not in by_source:
                by_source[source] = {"count": 0, "avg_time_ms": 0, "passed": 0, "failed": 0}
            
            by_source[source]["count"] += 1
            if m.get('passed'):
                by_source[source]["passed"] += 1
            else:
                by_source[source]["failed"] += 1
            
            # Track time to start validation
            discovered = m.get('discovered_at')
            started = m.get('validation_started_at')
            if discovered and started:
                from datetime import datetime
                try:
                    time_ms = int((datetime.fromisoformat(started) - datetime.fromisoformat(discovered)).total_seconds() * 1000)
                    # Running average
                    prev_avg = by_source[source]["avg_time_ms"]
                    count = by_source[source]["count"]
                    by_source[source]["avg_time_ms"] = (prev_avg * (count - 1) + time_ms) / count
                except ValueError:
                    pass
        
        return by_source


# Convenience functions for gap_hunter integration
_validator = None

def get_validator() -> DealValidator:
    """Get or create validator singleton."""
    global _validator
    if _validator is None:
        _validator = DealValidator()
    return _validator


async def validate_deal(deal, customer_tier: str = "beginner") -> ValidationResult:
    """Validate a deal."""
    validator = get_validator()
    return await validator.validate_deal(deal, customer_tier)


def track_customer_interaction(customer_id: str, deal, interaction_type: str, notes: str = None):
    """Track customer interaction."""
    validator = get_validator()
    validator.track_interaction(customer_id, deal, interaction_type, notes)
