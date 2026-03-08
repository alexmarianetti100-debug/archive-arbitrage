"""
Base classes and data structures for trend signal sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TrendSignal:
    """A single trend signal — something that's hot (or rising) in archive fashion."""
    brand: str
    item_type: str                          # "leather jacket", "cargo pants", etc.
    specific_query: str                     # "rick owens stooges leather jacket"
    trend_score: float                      # 0-1, composite heat score
    trend_direction: str = "stable"         # "rising", "stable", "falling"
    signal_sources: list[str] = field(default_factory=list)  # ["grailed_velocity", "reddit"]
    est_sold_volume: int = 0                # approx monthly sold count (30-day window)
    avg_sold_price: float = 0.0             # average sold price in USD
    opportunity_score: float = 0.0         # avg_sold_price × monthly_volume (dollar velocity)
    velocity_change: float = 0.0            # % change vs baseline (e.g. +1.8 = 180% faster)
    price_change: float = 0.0               # % change in avg price vs baseline
    detected_at: datetime = field(default_factory=datetime.utcnow)

    def merge(self, other: "TrendSignal") -> "TrendSignal":
        """Merge another signal into this one (same item from different sources)."""
        combined_score = max(self.trend_score, other.trend_score) + 0.1 * min(self.trend_score, other.trend_score)
        return TrendSignal(
            brand=self.brand,
            item_type=self.item_type or other.item_type,
            specific_query=self.specific_query or other.specific_query,
            trend_score=min(1.0, combined_score),
            trend_direction=self.trend_direction if self.trend_score >= other.trend_score else other.trend_direction,
            signal_sources=list(set(self.signal_sources + other.signal_sources)),
            est_sold_volume=max(self.est_sold_volume, other.est_sold_volume),
            avg_sold_price=max(self.avg_sold_price, other.avg_sold_price),
            opportunity_score=max(self.opportunity_score, other.opportunity_score),
            velocity_change=self.velocity_change or other.velocity_change,
            price_change=self.price_change or other.price_change,
        )

    @property
    def merge_key(self) -> str:
        """Key for deduplication/merging signals about the same item."""
        return f"{self.brand.lower()}:{self.item_type.lower()}"


class TrendSource(ABC):
    """Abstract base class for all trend signal sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Source identifier (e.g. 'grailed_velocity', 'reddit')."""
        ...

    @property
    @abstractmethod
    def weight(self) -> float:
        """How much to trust this source (0-1). Grailed=1.0, Reddit=0.4."""
        ...

    @abstractmethod
    async def fetch_signals(self) -> list[TrendSignal]:
        """Fetch and return trend signals from this source."""
        ...
