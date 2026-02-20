"""
Exact Product Qualification — Phase 2A/2B Integration

Qualifies items using exact product matching from the product catalog.

This replaces fuzzy comp matching with:
1. Exact product identification (fingerprinting)
2. Price against exact product comps only
3. Velocity-based deal grading (guaranteed resale)
"""

import asyncio
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

from scrapers.product_fingerprint import (
    parse_title_to_fingerprint, 
    ProductFingerprint,
)
from db.sqlite_models import (
    get_product_by_fingerprint,
    get_product_price_stats,
    find_matching_products,
    update_item_product_match,
    Item,
)
from api.services.pricing import PricingService


@dataclass
class ExactProductQualification:
    """Qualification result using exact product matching."""
    grade: str  # A, B, C, D
    grade_reasoning: str
    
    # Product identification
    product_id: Optional[int]
    fingerprint: Optional[ProductFingerprint]
    match_confidence: str  # high, medium, low
    
    # Exact product comps
    exact_comp_count: int
    price_band_low: float
    price_band_high: float
    price_median: float
    price_confidence: str  # high, medium, low
    
    # Velocity metrics
    sales_30d: int
    sales_90d: int
    velocity_trend: str
    is_high_velocity: bool
    
    # Pricing
    market_price: float
    sell_price: float
    profit: float
    margin_percent: float
    
    # Risk assessment
    risk_level: str  # low, medium, high
    
    qualified_at: str = ""


class ExactProductQualifier:
    """Qualifies items using exact product matching."""
    
    # Grade thresholds
    MIN_PROFIT_FOR_ALERT = 150
    MIN_MARGIN_PERCENT = 0.40
    
    # Velocity thresholds
    HIGH_VELOCITY_MIN_SALES = 5  # 5+ sales in 30 days
    MEDIUM_VELOCITY_MIN_SALES = 3  # 3+ sales in 30 days
    
    # Price confidence thresholds
    HIGH_CONFIDENCE_MIN_COMPS = 8
    MEDIUM_CONFIDENCE_MIN_COMPS = 4
    HIGH_CONFIDENCE_MAX_SPREAD = 0.30  # Max 30% spread between low/high
    
    def __init__(self):
        self.pricing_service = PricingService()
    
    async def qualify_item(self, item: Item) -> ExactProductQualification:
        """Qualify an item using exact product matching."""
        
        # Step 1: Extract product fingerprint
        fingerprint = parse_title_to_fingerprint(item.brand or "", item.title)
        
        if not fingerprint.is_complete():
            # Fall back to legacy qualification
            return await self._legacy_qualify(item, fingerprint)
        
        # Step 2: Look up exact product in catalog
        product = get_product_by_fingerprint(fingerprint.fingerprint_hash)
        
        if not product:
            # Product not in catalog yet — try to find similar products
            return await self._qualify_with_similar(item, fingerprint)
        
        # Step 3: Get exact product price data
        price_stats = get_product_price_stats(product.id, days=90)
        
        # Step 4: Calculate grades and risk
        return self._calculate_exact_qualification(
            item, fingerprint, product, price_stats
        )
    
    def _calculate_exact_qualification(
        self,
        item: Item,
        fingerprint: ProductFingerprint,
        product,
        price_stats: dict,
    ) -> ExactProductQualification:
        """Calculate qualification using exact product data."""
        
        comp_count = price_stats.get("count", 0)
        price_median = price_stats.get("avg", 0)  # Use avg as median proxy
        price_low = price_stats.get("min", price_median * 0.8)
        price_high = price_stats.get("max", price_median * 1.2)
        
        # Calculate price confidence
        price_confidence = "low"
        if comp_count >= self.HIGH_CONFIDENCE_MIN_COMPS:
            spread = (price_high - price_low) / price_median if price_median > 0 else 1
            if spread <= self.HIGH_CONFIDENCE_MAX_SPREAD:
                price_confidence = "high"
            else:
                price_confidence = "medium"
        elif comp_count >= self.MEDIUM_CONFIDENCE_MIN_COMPS:
            price_confidence = "medium"
        
        # Determine match confidence
        match_confidence = fingerprint.confidence
        
        # Calculate pricing
        total_cost = item.source_price + item.source_shipping
        
        # Use conservative estimate (price_band_low) for safety
        market_price = price_median
        sell_price = price_low * 0.90  # Price 10% below band low for quick sale
        
        # Ensure minimum margin
        min_sell_price = total_cost * 1.35  # 35% margin minimum
        if sell_price < min_sell_price:
            sell_price = min_sell_price
        
        profit = sell_price - total_cost
        margin = profit / sell_price if sell_price > 0 else 0
        
        # Determine grade based on exact product velocity
        grade = "D"
        grade_reasoning = ""
        risk_level = "high"
        
        if product.is_high_velocity and price_confidence == "high":
            if profit >= self.MIN_PROFIT_FOR_ALERT and margin >= self.MIN_MARGIN_PERCENT:
                grade = "A"
                grade_reasoning = f"🔥 Guaranteed flip: {product.sales_30d} sales/30d, {comp_count} exact comps, ${profit:.0f} profit"
                risk_level = "low"
            else:
                grade = "B"
                grade_reasoning = f"High velocity ({product.sales_30d}/30d) but margin thin"
                risk_level = "low"
        elif product.sales_30d >= self.MEDIUM_VELOCITY_MIN_SALES and price_confidence in ("high", "medium"):
            if profit >= self.MIN_PROFIT_FOR_ALERT:
                grade = "B"
                grade_reasoning = f"Proven seller: {product.sales_30d} sales/30d, {comp_count} comps"
                risk_level = "medium"
            else:
                grade = "C"
                grade_reasoning = f"Proven seller but low profit (${profit:.0f})"
                risk_level = "medium"
        elif comp_count >= self.MEDIUM_CONFIDENCE_MIN_COMPS:
            grade = "C"
            grade_reasoning = f"Some data: {comp_count} comps, {product.sales_30d} sales/30d"
            risk_level = "medium"
        else:
            grade = "D"
            grade_reasoning = f"Insufficient data: {comp_count} comps, {product.sales_30d} sales/30d"
            risk_level = "high"
        
        now = datetime.utcnow().isoformat()
        
        # Update item with product match info
        update_item_product_match(
            item_id=item.id,
            product_id=product.id,
            fingerprint=fingerprint.fingerprint_hash,
            confidence=match_confidence,
            exact_comps=comp_count,
            price_confidence=price_confidence,
            price_low=price_low,
            price_high=price_high,
        )
        
        return ExactProductQualification(
            grade=grade,
            grade_reasoning=grade_reasoning,
            product_id=product.id,
            fingerprint=fingerprint,
            match_confidence=match_confidence,
            exact_comp_count=comp_count,
            price_band_low=price_low,
            price_band_high=price_high,
            price_median=price_median,
            price_confidence=price_confidence,
            sales_30d=product.sales_30d,
            sales_90d=product.sales_90d,
            velocity_trend=product.velocity_trend,
            is_high_velocity=product.is_high_velocity,
            market_price=market_price,
            sell_price=sell_price,
            profit=profit,
            margin_percent=margin,
            risk_level=risk_level,
            qualified_at=now,
        )
    
    async def _qualify_with_similar(
        self,
        item: Item,
        fingerprint: ProductFingerprint,
    ) -> ExactProductQualification:
        """Qualify using similar products in catalog."""
        
        # Find similar products
        similar = find_matching_products(
            brand=fingerprint.brand,
            model=fingerprint.model,
            item_type=fingerprint.item_type,
            min_sales=3,
            limit=5,
        )
        
        if not similar:
            # No similar products — fall back to legacy
            return await self._legacy_qualify(item, fingerprint)
        
        # Aggregate data from similar products
        total_sales_30d = sum(p.sales_30d for p in similar)
        total_sales_90d = sum(p.sales_90d for p in similar)
        avg_sell_through = sum(p.avg_sell_through_rate or 0 for p in similar) / len(similar)
        
        # Get price stats from first similar product
        price_stats = get_product_price_stats(similar[0].id, days=90)
        comp_count = price_stats.get("count", 0)
        price_median = price_stats.get("avg", 0)
        
        # Conservative qualification
        total_cost = item.source_price + item.source_shipping
        market_price = price_median
        sell_price = market_price * 0.90 if market_price > 0 else total_cost * 1.35
        profit = sell_price - total_cost
        margin = profit / sell_price if sell_price > 0 else 0
        
        now = datetime.utcnow().isoformat()
        
        return ExactProductQualification(
            grade="C",
            grade_reasoning=f"Similar products exist ({len(similar)}), no exact match",
            product_id=None,
            fingerprint=fingerprint,
            match_confidence="low",
            exact_comp_count=comp_count,
            price_band_low=price_stats.get("min", 0),
            price_band_high=price_stats.get("max", 0),
            price_median=price_median,
            price_confidence="low",
            sales_30d=total_sales_30d // len(similar),
            sales_90d=total_sales_90d // len(similar),
            velocity_trend="unknown",
            is_high_velocity=any(p.is_high_velocity for p in similar),
            market_price=market_price,
            sell_price=sell_price,
            profit=profit,
            margin_percent=margin,
            risk_level="high",
            qualified_at=now,
        )
    
    async def _legacy_qualify(
        self,
        item: Item,
        fingerprint: ProductFingerprint,
    ) -> ExactProductQualification:
        """Fall back to legacy qualification when exact matching fails."""
        
        # Use existing pricing service
        rec = await self.pricing_service.calculate_price_async(
            source_price=item.source_price,
            brand=item.brand,
            title=item.title,
            shipping_cost=item.source_shipping,
        )
        
        # Map legacy confidence to grade
        if rec.confidence == "skip":
            grade = "D"
        elif rec.confidence == "high" and rec.profit_estimate >= self.MIN_PROFIT_FOR_ALERT:
            grade = "B"  # Could be A if we had velocity data
        elif rec.confidence in ("high", "medium"):
            grade = "C"
        else:
            grade = "D"
        
        now = datetime.utcnow().isoformat()
        
        return ExactProductQualification(
            grade=grade,
            grade_reasoning=f"Legacy: {rec.reasoning}",
            product_id=None,
            fingerprint=fingerprint,
            match_confidence="none",
            exact_comp_count=rec.comps_count,
            price_band_low=float(rec.market_price or 0) * 0.8,
            price_band_high=float(rec.market_price or 0) * 1.2,
            price_median=float(rec.market_price or 0),
            price_confidence=rec.confidence,
            sales_30d=0,
            sales_90d=0,
            velocity_trend="unknown",
            is_high_velocity=False,
            market_price=float(rec.market_price or 0),
            sell_price=float(rec.recommended_price),
            profit=float(rec.profit_estimate),
            margin_percent=rec.margin_percent,
            risk_level="high",
            qualified_at=now,
        )


async def qualify_item_exact(item: Item) -> ExactProductQualification:
    """Convenience function to qualify an item with exact product matching."""
    qualifier = ExactProductQualifier()
    return await qualifier.qualify_item(item)


if __name__ == "__main__":
    # Test with sample items
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from db.sqlite_models import get_item_by_id
    
    async def test():
        # Test with a sample item
        item = get_item_by_id(1)
        if item:
            print(f"Testing with: {item.title}")
            result = await qualify_item_exact(item)
            print(f"\nGrade: {result.grade}")
            print(f"Reasoning: {result.grade_reasoning}")
            print(f"Product: {result.fingerprint.canonical_name if result.fingerprint else 'N/A'}")
            print(f"Exact comps: {result.exact_comp_count}")
            print(f"Price confidence: {result.price_confidence}")
            print(f"Velocity: {result.sales_30d} sales/30d")
            print(f"Profit: ${result.profit:.2f}")
    
    asyncio.run(test())
