"""
Database module.

Uses sqlite_models (lightweight, no dependencies) by default.
The SQLAlchemy models in models.py are optional and only loaded if sqlalchemy is installed.
"""

try:
    from .models import (
        Base,
        Item,
        ItemStatus,
        Order,
        OrderStatus,
        Source,
        PriceHistory,
        MarketPriceCache,
        ScrapeJob,
    )

    __all__ = [
        "Base",
        "Item",
        "ItemStatus",
        "Order",
        "OrderStatus",
        "Source",
        "PriceHistory",
        "MarketPriceCache",
        "ScrapeJob",
    ]
except ImportError:
    # SQLAlchemy not installed — sqlite_models is the primary DB layer
    __all__ = []
