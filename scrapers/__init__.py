"""
Scrapers for archive fashion marketplaces.
"""

from .base import BaseScraper, ScrapedItem
from .brands import ARCHIVE_BRANDS, PRIORITY_BRANDS, ARCHIVE_KEYWORDS, CATEGORIES

# Import all scrapers
from .ebay import EbayScraper
from .depop import DepopScraper
from .mercari import MercariScraper
from .poshmark import PoshmarkScraper
from .shopgoodwill import ShopGoodwillScraper
from .grailed import GrailedScraper
from .nobids import NoBidsScraper
from .gem import GemScraper

# API-based scrapers (more reliable, no blocking)
try:
    from .ebay_api import EbayApiScraper
except ImportError:
    EbayApiScraper = None

# Auction sniper
try:
    from .auction_sniper import AuctionSniper, AuctionItem
except ImportError:
    AuctionSniper = None
    AuctionItem = None

# Season detection
from .seasons import detect_season, get_season_adjusted_price

__all__ = [
    # Base
    "BaseScraper",
    "ScrapedItem",
    
    # Scrapers
    "EbayScraper",
    "DepopScraper", 
    "MercariScraper",
    "PoshmarkScraper",
    "ShopGoodwillScraper",
    "GrailedScraper",
    "NoBidsScraper",
    "GemScraper",
    
    # Brand data
    "ARCHIVE_BRANDS",
    "PRIORITY_BRANDS",
    "ARCHIVE_KEYWORDS",
    "CATEGORIES",
]
