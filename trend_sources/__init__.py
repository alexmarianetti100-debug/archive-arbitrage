"""
Trend Sources — Pluggable signal sources for the TrendEngine.

Each source discovers what's trending in archive fashion and returns
TrendSignal objects that the TrendEngine merges and ranks.
"""

from .base import TrendSignal, TrendSource
from .grailed_velocity import GrailedVelocitySource
from .social_signals import RedditSignalSource
from .google_trends import GoogleTrendsSource
from .editorial import EditorialSource

__all__ = [
    "TrendSignal",
    "TrendSource",
    "GrailedVelocitySource",
    "RedditSignalSource",
    "GoogleTrendsSource",
    "EditorialSource",
]
