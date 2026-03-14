"""
Japan Arbitrage Cost Calculator

Calculates all-in costs for buying from Japan including:
- Item price in JPY
- Proxy service fees
- Domestic shipping (Japan)
- International shipping
- Import duties/taxes
- Payment processing fees
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("japan_arbitrage")


@dataclass
class ProxyService:
    """Configuration for a Japan proxy service."""
    name: str
    service_fee_percent: float  # e.g., 0.10 for 10%
    per_item_fee: float  # USD per item
    min_service_fee: float  # Minimum fee in USD
    domestic_shipping: float  # Average domestic shipping in USD
    intl_shipping_per_kg: float  # International shipping per kg
    consolidation_fee: float  # Fee to combine packages
    payment_fee_percent: float  # Credit card/PayPal fees


# Proxy service configurations (as of 2024-2025)
PROXY_SERVICES = {
    'buyee': ProxyService(
        name='Buyee',
        service_fee_percent=0.10,  # 10% of item price
        per_item_fee=0,
        min_service_fee=5.00,  # $5 minimum
        domestic_shipping=8.00,  # ~¥1,200
        intl_shipping_per_kg=25.00,  # EMS/DHL average
        consolidation_fee=3.00,
        payment_fee_percent=0.035,  # 3.5% for PayPal/credit card
    ),
    'neokyo': ProxyService(
        name='Neokyo',
        service_fee_percent=0.08,  # 8% (lower than Buyee)
        per_item_fee=0,
        min_service_fee=3.00,
        domestic_shipping=7.00,
        intl_shipping_per_kg=22.00,  # Slightly cheaper
        consolidation_fee=2.50,
        payment_fee_percent=0.035,
    ),
    'zenmarket': ProxyService(
        name='ZenMarket',
        service_fee_percent=0,  # No percentage fee
        per_item_fee=3.00,  # 300 yen per item (~$2)
        min_service_fee=3.00,
        domestic_shipping=7.50,
        intl_shipping_per_kg=24.00,
        consolidation_fee=0,  # Free consolidation
        payment_fee_percent=0.035,
    ),
    'sendico': ProxyService(
        name='Sendico',
        service_fee_percent=0.08,
        per_item_fee=0,
        min_service_fee=4.00,
        domestic_shipping=8.00,
        intl_shipping_per_kg=20.00,  # Good for heavy items
        consolidation_fee=2.00,
        payment_fee_percent=0.035,
    ),
    'fromjapan': ProxyService(
        name='From Japan',
        service_fee_percent=0.05,  # 5% (lowest percentage)
        per_item_fee=0,
        min_service_fee=5.00,
        domestic_shipping=8.50,
        intl_shipping_per_kg=26.00,
        consolidation_fee=3.50,
        payment_fee_percent=0.035,
    ),
}


@dataclass
class AllInCost:
    """Complete cost breakdown for Japan purchase."""
    # Item
    item_price_jpy: int
    item_price_usd: float
    
    # Fees
    service_fee: float
    per_item_fee: float
    domestic_shipping: float
    international_shipping: float
    import_duty: float
    import_vat: float
    payment_processing: float
    consolidation: float
    
    # Totals
    total_before_duty: float
    total_landed: float
    effective_margin: float
    
    # Metadata
    proxy_service: str
    shipping_method: str
    item_weight_kg: float


class JapanCostCalculator:
    """Calculate all-in costs for Japan purchases."""
    
    # Exchange rate (update regularly)
    JPY_TO_USD = 0.0067  # ~150 JPY = 1 USD
    
    # Import duty rates by category
    DUTY_RATES = {
        'watch': 0.045,  # 4.5% for watches
        'bag': 0.06,     # 6% for leather bags
        'jewelry': 0.055, # 5.5% for jewelry
        'fashion': 0.12,  # 12-16% for clothing
        'shoes': 0.08,    # 8% for footwear
        'default': 0.06,  # 6% default
    }
    
    # Item weight estimates (kg)
    WEIGHT_ESTIMATES = {
        'watch': 0.3,
        'bag_small': 0.5,
        'bag_medium': 0.8,
        'bag_large': 1.2,
        'jewelry': 0.1,
        'fashion': 0.5,
        'shoes': 1.0,
        'default': 0.5,
    }
    
    def __init__(self, proxy_service: str = 'buyee'):
        self.proxy = PROXY_SERVICES.get(proxy_service, PROXY_SERVICES['buyee'])
    
    def calculate(
        self,
        item_price_jpy: int,
        category: str = 'default',
        weight_kg: Optional[float] = None,
        shipping_method: str = 'ems',  # ems, dhl, sal, seamail
        consolidate: bool = False,
    ) -> AllInCost:
        """Calculate all-in cost for Japan purchase."""
        
        # Base item price
        item_price_usd = item_price_jpy * self.JPY_TO_USD
        
        # Estimate weight if not provided
        if weight_kg is None:
            weight_kg = self.WEIGHT_ESTIMATES.get(category, self.WEIGHT_ESTIMATES['default'])
        
        # Calculate proxy service fee
        service_fee = max(
            item_price_usd * self.proxy.service_fee_percent,
            self.proxy.min_service_fee
        )
        
        # Per-item fee
        per_item_fee = self.proxy.per_item_fee
        
        # Domestic shipping (within Japan)
        domestic_shipping = self.proxy.domestic_shipping
        
        # International shipping (with volumetric weight for bulky categories)
        intl_shipping = self._calculate_intl_shipping(weight_kg, shipping_method, category)
        
        # Payment processing
        subtotal = item_price_usd + service_fee + per_item_fee + domestic_shipping
        payment_fee = subtotal * self.proxy.payment_fee_percent
        
        # Consolidation fee
        consolidation = self.proxy.consolidation_fee if consolidate else 0
        
        # Total before duty
        total_before_duty = (
            item_price_usd + 
            service_fee + 
            per_item_fee + 
            domestic_shipping + 
            intl_shipping + 
            payment_fee +
            consolidation
        )
        
        # Import duty (on item price + shipping)
        duty_rate = self.DUTY_RATES.get(category, self.DUTY_RATES['default'])
        dutiable_value = item_price_usd + intl_shipping
        import_duty = dutiable_value * duty_rate
        
        # Import VAT (varies by state, use average 6%)
        import_vat = (dutiable_value + import_duty) * 0.06
        
        # Total landed cost
        total_landed = total_before_duty + import_duty + import_vat
        
        # Effective margin (what you need to sell for to break even)
        effective_margin = (total_landed / item_price_usd - 1) * 100
        
        return AllInCost(
            item_price_jpy=item_price_jpy,
            item_price_usd=item_price_usd,
            service_fee=service_fee,
            per_item_fee=per_item_fee,
            domestic_shipping=domestic_shipping,
            international_shipping=intl_shipping,
            import_duty=import_duty,
            import_vat=import_vat,
            payment_processing=payment_fee,
            consolidation=consolidation,
            total_before_duty=total_before_duty,
            total_landed=total_landed,
            effective_margin=effective_margin,
            proxy_service=self.proxy.name,
            shipping_method=shipping_method.upper(),
            item_weight_kg=weight_kg,
        )
    
    # Volumetric weight multipliers — carriers charge by dimensional weight
    # when the package is bulky relative to its actual weight.
    # Multiplier is applied to actual weight to approximate volumetric weight.
    VOLUMETRIC_MULTIPLIERS = {
        'shoes': 2.0,       # Shoe boxes are bulky (~40x30x15cm)
        'bag_large': 1.8,   # Large bags (Birkin, Keepall)
        'bag_medium': 1.5,  # Medium bags
        'bag_small': 1.3,   # Small bags / WOC
        'bag': 1.5,         # Generic bag fallback
    }

    def _calculate_intl_shipping(
        self, weight_kg: float, method: str, category: str = 'default'
    ) -> float:
        """Calculate international shipping cost with volumetric weight adjustment.

        Carriers (EMS, DHL, FedEx) charge by whichever is greater: actual weight
        or volumetric weight. Shoes and bags are significantly bulkier than their
        actual weight, causing shipping cost surprises.
        """
        base_rates = {
            'ems': 25.00,
            'dhl': 35.00,
            'fedex': 32.00,
            'sal': 15.00,  # Economy
            'seamail': 12.00,  # Slowest/cheapest
        }

        # Apply volumetric multiplier for bulky categories
        vol_mult = self.VOLUMETRIC_MULTIPLIERS.get(category, 1.0)
        billable_weight = weight_kg * vol_mult

        base = base_rates.get(method, base_rates['ems'])
        per_kg = self.proxy.intl_shipping_per_kg

        # First kg at base rate, additional at per-kg rate
        if billable_weight <= 1:
            return base
        else:
            return base + (billable_weight - 1) * per_kg
    
    def compare_proxies(
        self,
        item_price_jpy: int,
        category: str = 'default',
        weight_kg: Optional[float] = None,
    ) -> dict:
        """Compare costs across all proxy services."""
        results = {}
        
        for name, proxy in PROXY_SERVICES.items():
            calc = JapanCostCalculator(name)
            cost = calc.calculate(item_price_jpy, category, weight_kg)
            results[name] = {
                'total_landed': cost.total_landed,
                'service_fee': cost.service_fee,
                'shipping': cost.domestic_shipping + cost.international_shipping,
                'duties': cost.import_duty + cost.import_vat,
                'effective_markup': cost.effective_margin,
            }
        
        return results
    
    def get_arbitrage_threshold(
        self,
        us_market_price: float,
        category: str = 'default',
        min_profit_percent: float = 25.0,
    ) -> float:
        """Calculate maximum Japan price for profitable arbitrage."""
        # Work backwards from US price
        # Need: US_price - all_costs >= min_profit
        
        target_profit = us_market_price * (min_profit_percent / 100)
        max_total_cost = us_market_price - target_profit
        
        # Estimate fees (rough approximation)
        estimated_fees_percent = 0.25  # 25% for fees/shipping/duty
        
        max_japan_price = max_total_cost / (1 + estimated_fees_percent)
        
        return max_japan_price


# Convenience functions
def calculate_japan_cost(
    jpy_price: int,
    category: str = 'default',
    proxy: str = 'buyee',
    weight_kg: Optional[float] = None,
) -> AllInCost:
    """Quick calculate Japan purchase cost."""
    calc = JapanCostCalculator(proxy)
    return calc.calculate(jpy_price, category, weight_kg)


def is_arbitrage_profitable(
    jpy_price: int,
    us_market_price: float,
    category: str = 'default',
    proxy: str = 'buyee',
    min_margin_percent: float = 25.0,
) -> tuple[bool, float, AllInCost]:
    """Check if Japan arbitrage is profitable."""
    calc = JapanCostCalculator(proxy)
    cost = calc.calculate(jpy_price, category)
    
    profit = us_market_price - cost.total_landed
    margin_percent = (profit / cost.total_landed) * 100 if cost.total_landed > 0 else 0
    
    is_profitable = margin_percent >= min_margin_percent
    
    return is_profitable, margin_percent, cost


if __name__ == "__main__":
    # Example usage
    calc = JapanCostCalculator('buyee')
    
    # Example: Hermès Birkin 30 at ¥1,800,000
    cost = calc.calculate(1_800_000, 'bag', weight_kg=0.8)
    
    print("Japan Arbitrage Cost Calculation")
    print("=" * 50)
    print(f"Item Price: ¥{cost.item_price_jpy:,} (${cost.item_price_usd:,.0f})")
    print(f"Service Fee: ${cost.service_fee:.2f}")
    print(f"Domestic Shipping: ${cost.domestic_shipping:.2f}")
    print(f"International Shipping: ${cost.international_shipping:.2f}")
    print(f"Import Duty: ${cost.import_duty:.2f}")
    print(f"Import VAT: ${cost.import_vat:.2f}")
    print(f"Payment Fee: ${cost.payment_processing:.2f}")
    print("-" * 50)
    print(f"TOTAL LANDED: ${cost.total_landed:,.2f}")
    print(f"Effective Markup: {cost.effective_margin:.1f}%")
    print()
    
    # Compare proxies
    print("Proxy Service Comparison:")
    print("=" * 50)
    comparison = calc.compare_proxies(1_800_000, 'bag', 0.8)
    for name, data in sorted(comparison.items(), key=lambda x: x[1]['total_landed']):
        print(f"{name:12} | Total: ${data['total_landed']:>8,.0f} | Markup: {data['effective_markup']:>5.1f}%")
