"""
Database models for Archive Arbitrage.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid

from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, Text, 
    ForeignKey, Enum as SQLEnum, JSON, Integer, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ItemStatus(str, Enum):
    ACTIVE = "active"          # Available on our storefront
    PENDING = "pending"        # Being reviewed
    SOLD = "sold"              # Sold through our store
    SOURCE_SOLD = "source_sold"  # No longer available at source
    EXPIRED = "expired"        # Auction ended without us winning


class OrderStatus(str, Enum):
    PENDING = "pending"        # Customer ordered, not yet purchased from source
    PURCHASING = "purchasing"  # In process of buying from source
    PURCHASED = "purchased"    # Bought from source
    SHIPPING = "shipping"      # On the way to customer
    DELIVERED = "delivered"    # Complete
    CANCELLED = "cancelled"    # Cancelled (refunded)
    FAILED = "failed"          # Failed to purchase from source


class Source(str, Enum):
    EBAY = "ebay"
    SHOPGOODWILL = "shopgoodwill"
    GEM = "gem"
    BUYEE = "buyee"
    OTHER = "other"


class Item(Base):
    """A scraped item available for sale."""
    __tablename__ = "items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source info
    source = Column(SQLEnum(Source), nullable=False)
    source_id = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    
    # Item details
    title = Column(String(500), nullable=False)
    description = Column(Text)
    brand = Column(String(255), index=True)
    category = Column(String(255))
    size = Column(String(50))
    condition = Column(String(100))
    
    # Pricing
    source_price = Column(Numeric(10, 2), nullable=False)  # What it costs at source
    source_shipping = Column(Numeric(10, 2), default=0)
    source_currency = Column(String(3), default="USD")
    
    market_price = Column(Numeric(10, 2))  # Estimated market value (from Grailed)
    our_price = Column(Numeric(10, 2))     # What we're selling it for
    
    # Media
    images = Column(JSON, default=list)  # List of image URLs
    
    # Auction info
    is_auction = Column(Boolean, default=False)
    auction_ends_at = Column(DateTime)
    
    # Status
    status = Column(SQLEnum(ItemStatus), default=ItemStatus.PENDING, index=True)
    last_checked_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Raw data for debugging
    raw_data = Column(JSON)
    
    # Relationships
    price_history = relationship("PriceHistory", back_populates="item")
    orders = relationship("Order", back_populates="item")
    
    def __repr__(self):
        return f"<Item {self.brand} - {self.title[:50]}>"


class PriceHistory(Base):
    """Track price changes over time."""
    __tablename__ = "price_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    
    source_price = Column(Numeric(10, 2))
    market_price = Column(Numeric(10, 2))
    our_price = Column(Numeric(10, 2))
    
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    item = relationship("Item", back_populates="price_history")


class Order(Base):
    """Customer order."""
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    
    # Customer info
    customer_email = Column(String(255), nullable=False)
    customer_name = Column(String(255))
    shipping_address = Column(JSON)  # Street, city, state, zip, country
    
    # Pricing at time of order
    sale_price = Column(Numeric(10, 2), nullable=False)  # What customer paid
    source_price = Column(Numeric(10, 2), nullable=False)  # What we paid at source
    shipping_charged = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    profit = Column(Numeric(10, 2))  # Calculated: sale - source - shipping
    
    # Payment
    stripe_payment_id = Column(String(255))
    stripe_refund_id = Column(String(255))
    
    # Status
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, index=True)
    
    # Source purchase info
    source_order_id = Column(String(255))  # Order ID on eBay/Goodwill/etc
    source_tracking = Column(String(255))
    
    # Customer shipping
    customer_tracking = Column(String(255))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    purchased_at = Column(DateTime)  # When we bought from source
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)
    
    # Notes
    notes = Column(Text)
    
    item = relationship("Item", back_populates="orders")
    
    def __repr__(self):
        return f"<Order {self.id} - {self.status.value}>"


class MarketPriceCache(Base):
    """Cache Grailed market prices to reduce scraping."""
    __tablename__ = "market_price_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Search params
    brand = Column(String(255), nullable=False, index=True)
    category = Column(String(255))  # jacket, pants, etc
    size = Column(String(50))
    
    # Price data
    avg_price = Column(Numeric(10, 2))
    min_price = Column(Numeric(10, 2))
    max_price = Column(Numeric(10, 2))
    median_price = Column(Numeric(10, 2))
    sample_size = Column(Integer)
    
    # Cache metadata
    cached_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Typically 24-48 hours


class ScrapeJob(Base):
    """Track scraping jobs for monitoring."""
    __tablename__ = "scrape_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    source = Column(SQLEnum(Source), nullable=False)
    query = Column(String(500))
    
    status = Column(String(50), default="running")  # running, completed, failed
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error = Column(Text)
