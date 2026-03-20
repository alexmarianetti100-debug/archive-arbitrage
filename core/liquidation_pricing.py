"""
Conservative liquidation pricing helpers.

Turns sold comp distributions into a conservative resale anchor and a downside
anchor for margin-of-safety style deal evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Optional


@dataclass(frozen=True)
class LiquidationMetrics:
    median_price: float
    p25_price: float
    auth_median_price: float
    auth_p25_price: float
    liquidation_anchor: float
    downside_anchor: float
    pricing_method: str
    pricing_confidence: str
    haircut_pct: float


def _clean_prices(prices: list[float] | None) -> list[float]:
    if not prices:
        return []
    return sorted(float(p) for p in prices if p is not None and p > 0)


def _percentile(sorted_prices: list[float], percentile: float) -> float:
    if not sorted_prices:
        return 0.0
    if len(sorted_prices) == 1:
        return float(sorted_prices[0])
    percentile = min(1.0, max(0.0, percentile))
    idx = percentile * (len(sorted_prices) - 1)
    lo = floor(idx)
    hi = min(lo + 1, len(sorted_prices) - 1)
    if lo == hi:
        return float(sorted_prices[lo])
    frac = idx - lo
    return float(sorted_prices[lo] + (sorted_prices[hi] - sorted_prices[lo]) * frac)


def _median(sorted_prices: list[float]) -> float:
    return _percentile(sorted_prices, 0.5)


def _p25(sorted_prices: list[float]) -> float:
    return _percentile(sorted_prices, 0.25)


def _confidence_bucket(
    *,
    comp_count: int,
    auth_comp_count: int,
    cv: Optional[float],
    avg_days_to_sell: Optional[float],
) -> str:
    cv = 0.9 if cv is None else float(cv)
    avg_days = avg_days_to_sell if avg_days_to_sell is not None else 999

    if comp_count >= 8 and auth_comp_count >= 3 and cv <= 0.55 and avg_days <= 45:
        return "high"
    if comp_count >= 5 and cv <= 0.95:
        return "medium"
    return "low"


def _haircut_for_confidence(confidence: str, cv: Optional[float]) -> float:
    base = {
        "high": 0.07,
        "medium": 0.12,
        "low": 0.18,
    }.get(confidence, 0.15)

    cv = 0.0 if cv is None else float(cv)
    if cv >= 1.2:
        base += 0.05
    elif cv >= 0.8:
        base += 0.02
    return min(base, 0.35)


def compute_liquidation_metrics(
    *,
    sold_prices: list[float],
    authenticated_prices: list[float] | None = None,
    hyper_price: float | None = None,
    cv: float | None = None,
    comp_count: int = 0,
    auth_comp_count: int = 0,
    avg_days_to_sell: float | None = None,
) -> LiquidationMetrics:
    prices = _clean_prices(sold_prices)
    auth_prices = _clean_prices(authenticated_prices)

    if not prices:
        return LiquidationMetrics(
            median_price=0.0,
            p25_price=0.0,
            auth_median_price=0.0,
            auth_p25_price=0.0,
            liquidation_anchor=0.0,
            downside_anchor=0.0,
            pricing_method="no-comps",
            pricing_confidence="low",
            haircut_pct=0.25,
        )

    median_price = _median(prices)
    p25_price = _p25(prices)
    auth_median_price = _median(auth_prices) if auth_prices else 0.0
    auth_p25_price = _p25(auth_prices) if auth_prices else 0.0

    confidence = _confidence_bucket(
        comp_count=comp_count or len(prices),
        auth_comp_count=auth_comp_count or len(auth_prices),
        cv=cv,
        avg_days_to_sell=avg_days_to_sell,
    )
    haircut_pct = _haircut_for_confidence(confidence, cv)

    # Select liquidation anchor: prefer auth-p25 if available, fall back to p25,
    # then median-haircut. Use the BEST reliable source, not the absolute minimum.
    if len(auth_prices) >= 3 and auth_p25_price > 0:
        pricing_method = "auth-p25"
        liquidation_anchor = auth_p25_price
    elif p25_price > 0:
        pricing_method = "p25"
        liquidation_anchor = p25_price
    elif hyper_price and hyper_price > 0:
        pricing_method = "hyper-haircut"
        liquidation_anchor = float(hyper_price) * (1 - haircut_pct)
    elif median_price > 0:
        pricing_method = "median-haircut"
        liquidation_anchor = median_price * (1 - haircut_pct)
    else:
        pricing_method = "no-anchor"
        liquidation_anchor = 0.0

    # Downside anchor: use p25 directly with a reduced haircut (not double-haircutted)
    downside_anchor = p25_price * (1 - haircut_pct * 0.5) if p25_price > 0 else liquidation_anchor * 0.90

    return LiquidationMetrics(
        median_price=median_price,
        p25_price=p25_price,
        auth_median_price=auth_median_price,
        auth_p25_price=auth_p25_price,
        liquidation_anchor=liquidation_anchor,
        downside_anchor=downside_anchor,
        pricing_method=pricing_method,
        pricing_confidence=confidence,
        haircut_pct=haircut_pct,
    )
