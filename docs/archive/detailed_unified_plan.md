# Unified Archive Arbitrage System - Detailed Implementation Plan

## 🎯 Project Overview

**Goal**: Merge gap_hunter.py with main pipeline to create one comprehensive archive arbitrage system

**Current Status**: 
- ✅ Main pipeline working with Whop integration
- ✅ gap_hunter.py working separately
- ✅ Whop alerts functional for both systems

**Target**: Single integrated pipeline that runs both standard and gap detection

## 📋 Phase 1: Database Schema Unification (Week 1)

### 1.1 Database Model Updates
File: `db/sqlite_models.py`

**Add/modify `Item` class:**
```python
class Item(Base):
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    source = Column(String)
    source_id = Column(String)
    source_url = Column(String)
    title = Column(String)
    brand = Column(String)
    category = Column(String)
    size = Column(String)
    condition = Column(String)
    source_price = Column(Float)
    market_price = Column(Float)  # From pricing
    our_price = Column(Float)  # Recommended price
    profit = Column(Float)  # Profit estimate
    margin_percent = Column(Float)
    images = Column(Text)
    is_auction = Column(Boolean, default=False)
    status = Column(String, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # NEW FIELDS FOR GAP HUNTER INTEGRATION
    deal_type = Column(String, default='standard')  # 'standard' or 'gap'
    
    # GAP-SPECIFIC FIELDS  
    gap_percent = Column(Float, default=0.0)
    proven_sold_price = Column(Float, default=0.0)
    gap_amount = Column(Float, default=0.0)
    
    # QUALITY FIELDS - UNIFIED
    quality_grade = Column(String, default='C')  # A/B/C grades
    grade_reasoning = Column(Text)  # For qualification notes
```

### 1.2 Migration Script
File: `db/migrate_unified.py`
```python
#!/usr/bin/env python3
"""
Migration script to add new fields to existing database
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from db.sqlite_models import Item

def migrate_database():
    engine = create_engine('sqlite:///data/archive.db')
    Base = declarative_base()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Add new columns to existing table
    # Note: This is simplified - real migration requires more complex ALTER TABLE
    print("Migration script ready for unified schema")
    print("Run migration with proper SQLite ALTER statements")

if __name__ == '__main__':
    migrate_database()
```

## 🏗️ Phase 2: Common Alerting Framework (Week 2)

### 2.1 Unified Alert System
File: `core/unified_alerts.py`

```python
#!/usr/bin/env python3
"""
Unified alerting system for both standard and gap deals
"""

import os
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Import existing components
from core.whop_alerts import send_whop_alert, format_whop_deal_content
from core.alerts import AlertService
from telegram_bot import send_deal_to_subscribers

@dataclass
class UnifiedAlert:
    """Unified alert data structure for all deal types"""
    deal_type: str  # 'standard' or 'gap'
    title: str
    brand: str
    source: str
    source_url: str
    source_price: float
    sell_price: float
    profit: float
    margin_percent: float
    images: Optional[List[str]] = None
    size: Optional[str] = None
    category: Optional[str] = None
    
    # GAP-SPECIFIC FIELDS
    gap_percent: Optional[float] = None
    proven_sold_price: Optional[float] = None
    gap_amount: Optional[float] = None
    
    # QUALITY FIELDS
    quality_grade: str = 'C'
    grade_reasoning: str = ''
    
    # ALERT-SPECIFIC FIELDS
    timestamp: str = None

class UnifiedAlertService:
    """Unified alert sending system"""
    
    def __init__(self):
        self.discord_alerts = AlertService()
        self.whop_enabled = os.getenv("WHOP_ENABLED", "false").lower() == "true"
        
    async def send_unified_alert(self, alert_data: UnifiedAlert):
        """Send alerts to all channels"""
        
        # Send to Discord (existing system)
        await self._send_discord_alert(alert_data)
        
        # Send to Telegram (existing system) 
        await self._send_telegram_alert(alert_data)
        
        # Send to Whop (new)
        if self.whop_enabled:
            await self._send_whop_alert(alert_data)
            
    async def _send_discord_alert(self, alert_data: UnifiedAlert):
        """Send to Discord using existing system"""
        try:
            # Convert our unified format to Discord format
            from core.alerts import AlertItem
            discord_alert = AlertItem(
                title=alert_data.title,
                brand=alert_data.brand,
                source=alert_data.source,
                source_url=alert_data.source_url,
                source_price=alert_data.source_price,
                market_price=alert_data.sell_price,  # Simple mapping
                recommended_price=alert_data.sell_price,
                profit=alert_data.profit,
                margin_percent=alert_data.margin_percent,
                image_url=alert_data.images[0] if alert_data.images else None,
                size=alert_data.size,
                demand_level="unknown",  # Could be enhanced
                demand_score=0.0,
            )
            
            # Use existing Discord alert system
            await self.discord_alerts.send_item_alert(discord_alert)
        except Exception as e:
            print(f"Discord alert error: {e}")
    
    async def _send_telegram_alert(self, alert_data: UnifiedAlert):
        """Send to Telegram - requires existing function"""
        # This will use the existing telegram_bot logic
        # Implementation depends on how telegram alerts work in existing system
        pass
        
    async def _send_whop_alert(self, alert_data: UnifiedAlert):
        """Send to Whop"""
        try:
            # Format content for Whop
            if alert_data.deal_type == 'gap':
                # Gap deal specific formatting
                title = f"📊 Gap Alert: {alert_data.brand} - {alert_data.title[:50]} | Gap: {alert_data.gap_percent:.0f}%"
                
                content = f"""
## 📉 Gap Deal: {alert_data.brand} - {alert_data.title}

**💰 The Opportunity:**
- Listed for: ${alert_data.source_price:.2f}
- Proven sold price: ${alert_data.proven_sold_price:.2f}
- Gap: **{alert_data.gap_percent:.0f}%** ({alert_data.gap_amount:.0f} profit)
- Source: {alert_data.source}

**📊 Data:**
- Quality Grade: {alert_data.quality_grade}
- Grade Reasoning: {alert_data.grade_reasoning}
- Margin: {alert_data.margin_percent*100:.0f}%

[View Listing]({alert_data.source_url})
"""
            else:
                # Standard deal formatting
                title = f"💰 Deal Alert: {alert_data.brand} - {alert_data.title[:50]} | Profit: ${alert_data.profit:.0f}"
                
                content = f"""
## **{alert_data.brand}** - {alert_data.title}

**💰 The Numbers:**
- Buy For: ${alert_data.source_price:.2f}
- Sell At: ${alert_data.sell_price:.2f} 
- Estimated Profit: **${alert_data.profit:.2f}** ({alert_data.margin_percent*100:.0f}% margin)

**📊 Data:**
- Quality Grade: {alert_data.quality_grade}
- Grade Reasoning: {alert_data.grade_reasoning}
- Margin: {alert_data.margin_percent*100:.0f}%

[View Listing]({alert_data.source_url})
"""
                
            # Send to Whop if enabled
            if os.getenv("WHOP_ENABLED", "false").lower() == "true":
                await send_whop_alert(title, content)
                print(f"✅ Sent to Whop: {title}")
                
        except Exception as e:
            print(f"Whop alert error: {e}")
```

## 🔄 Phase 3: Unified Pipeline Integration (Week 3)

### 3.1 Modify main pipeline to include gap detection
File: `pipeline.py` (modified sections)

```python
# Import new components
from core.unified_alerts import UnifiedAlertService, UnifiedAlert

# Existing imports...
from gap_hunter import GapHunter  # New import for gap detection

async def run_unified_scrape(
    brands: List[str] = None,
    sources: dict = None,
    max_per_source: int = 10,
):
    """Unified scraping function that includes gap detection"""
    
    # Run standard pipeline first (existing)
    standard_items = await run_standard_scrape(brands, sources, max_per_source)
    
    # Run gap hunter second (new addition)
    gap_items = []  # This will call gap hunter 
   
    # Combine items from both sources
    all_items = standard_items + gap_items
    
    # Process all items with unified workflow
    processed_items = await process_unified_deals(all_items)
    
    # Send unified alerts for all items
    await send_unified_alerts(processed_items)
    
    return len(processed_items)

async def process_unified_deals(items):
    """Process items from both sources with consistent workflow"""
    processed = []
    
    for item in items:
        # Determine deal type and process accordingly
        if hasattr(item, 'gap_percent') and item.gap_percent > 0:
            # Handle gap deals
            processed.append(await process_gap_deal(item))
        else:
            # Handle standard deals  
            processed.append(await process_standard_deal(item))
            
    return processed

async def process_gap_deal(gap_item):
    """Process gap-specific deal data"""
    # Extract gap data and create unified structure
    return UnifiedAlert(
        deal_type='gap',
        title=gap_item.title,
        brand=gap_item.brand,
        source=gap_item.source,
        source_url=gap_item.source_url,
        source_price=gap_item.source_price,
        sell_price=gap_item.proven_sold_price,  # For gap deals, we use proven price
        profit=gap_item.gap_amount,
        margin_percent=gap_item.gap_percent / 100,
        gap_percent=gap_item.gap_percent,
        proven_sold_price=gap_item.proven_sold_price,
        gap_amount=gap_item.gap_amount,
        quality_grade=gap_item.quality_grade,
        grade_reasoning=gap_item.grade_reasoning,
        images=gap_item.images,
        size=gap_item.size
    )

async def process_standard_deal(standard_item):
    """Process standard deal data"""  
    # Convert standard item to unified format
    return UnifiedAlert(
        deal_type='standard',
        title=standard_item.title,
        brand=standard_item.brand,
        source=standard_item.source,
        source_url=standard_item.source_url,
        source_price=standard_item.source_price,
        sell_price=standard_item.our_price,
        profit=standard_item.profit,
        margin_percent=standard_item.margin_percent,
        quality_grade=standard_item.quality_grade,
        grade_reasoning=standard_item.grade_reasoning,
        images=standard_item.images,
        size=standard_item.size
    )

async def send_unified_alerts(alert_items):
    """Send alerts using unified system"""
    service = UnifiedAlertService()
    
    for alert in alert_items:
        await service.send_unified_alert(alert)
```

## 🧪 Phase 4: Testing Framework (Week 4)

### 4.1 Integration Testing
File: `test_unified_integration.py`

```python
#!/usr/bin/env python3
"""
Test unified system integration
"""
import asyncio
from core.unified_alerts import UnifiedAlert, UnifiedAlertService

async def test_unified_alerting():
    """Test unified alert system"""
    
    # Test standard deal alert
    standard_alert = UnifiedAlert(
        deal_type='standard',
        title='Test Standard Item',
        brand='Test Brand',
        source='grailed',
        source_url='https://grailed.com/test',
        source_price=100,
        sell_price=200,
        profit=100,
        margin_percent=0.5,
        quality_grade='A',
        grade_reasoning='High-quality item with strong demand'
    )
    
    # Test gap deal alert  
    gap_alert = UnifiedAlert(
        deal_type='gap',
        title='Test Gap Item',
        brand='Test Brand',
        source='grailed',
        source_url='https://grailed.com/test',
        source_price=100,
        sell_price=200,
        profit=100,  # Gap amount
        margin_percent=0.5,  # Gap percentage
        gap_percent=50,
        proven_sold_price=200,
        gap_amount=100,
        quality_grade='B',
        grade_reasoning='Proven gap opportunity',
        images=['https://example.com/image.jpg']
    )
    
    # Create service and test
    service = UnifiedAlertService()
    
    print("Testing standard deal alert...")
    await service.send_unified_alert(standard_alert)
    
    print("Testing gap deal alert...") 
    await service.send_unified_alert(gap_alert)
    
    print("✅ Unified alerting test completed")

if __name__ == '__main__':
    asyncio.run(test_unified_alerting())
```

## 🛠️ Phase 5: Configuration & Deployment

### 5.1 Updated Environment File
File: `.env` (additional fields needed)
```
# UNIFIED ALERT SETTINGS
UNIFIED_ALERT_ENABLED=true
UNIFIED_ALERT_DEAL_TYPES=standard,gap

# QUALITY SCORING
STANDARD_MIN_PROFIT=50
STANDARD_MIN_MARGIN=0.25
GAP_MIN_GAP_PERCENT=30
GAP_MIN_GAP_AMOUNT=50

# ALERT CHANNELS - ALL ENABLED BY DEFAULT
DISCORD_ALERTS_ENABLED=true
TELEGRAM_ALERTS_ENABLED=true 
WHOP_ALERTS_ENABLED=true
```

### 5.2 Pipeline Command Integration
Add to `pipeline.py` command parser:
```python
# Add unified options
run_parser = subparsers.add_parser("unified", help="Run unified pipeline with gap hunting")
run_parser.add_argument("--gap-only", action="store_true", help="Only run gap detection")
run_parser.add_argument("--standard-only", action="store_true", help="Only run standard detection")
run_parser.add_argument("--gap-targets", help="Comma-separated gap targets")
```

## ⚡ Implementation Steps Summary

**Week 1**: Database schema changes, basic model updates
**Week 2**: Unified alert system implementation, quality grading standardization  
**Week 3**: Pipeline integration, gap hunting integration, shared processing logic
**Week 4**: Testing, optimization, deployment configuration

This detailed plan provides the exact file changes, code modifications, and implementation steps needed to create your unified archive arbitrage system.