#!/usr/bin/env python3
"""
Test with lower thresholds to find profitable items
"""
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def test_with_lower_thresholds():
    print("🔍 Testing with lower thresholds")
    print("=" * 40)
    
    # Let's run a quick test without being so strict about thresholds
    from core.alerts import AlertService
    from collections import namedtuple
    
    # Create mock objects that should pass the alert thresholds
    AlertItem = namedtuple('AlertItem', ['title', 'brand', 'source', 'source_url', 'source_price', 
                                         'market_price', 'recommended_price', 'profit', 'margin_percent',
                                         'image_url', 'size', 'season_name', 'season_multiplier',
                                         'comps_count', 'is_auction', 'time_left_hours', 'bid_count',
                                         'demand_level', 'demand_score'])
    
    # This should definitely trigger an alert 
    alert_item = AlertItem(
        title="High Profit Item",
        brand="Test Brand",
        source="grailed",
        source_url="https://example.com",
        source_price=100,
        market_price=250,
        recommended_price=300,
        profit=200,  # $200 profit
        margin_percent=0.67,  # 67% margin (well above 25%)
        image_url="https://example.com/image.jpg",
        size="M",
        season_name="Fall 2023",
        season_multiplier=1.2,
        comps_count=8,
        is_auction=False,
        time_left_hours=None,
        bid_count=0,
        demand_level="hot",
        demand_score=0.8
    )
    
    # Test with low thresholds
    alerts = AlertService(
        min_profit=50,  # Lower threshold
        min_margin=0.20  # Lower threshold
    )
    
    should_alert = alerts.should_alert(alert_item)
    print(f"Should alert: {should_alert}")
    
    # Show the thresholds
    print(f"Min profit check: {alert_item.profit} >= {alerts.min_profit} = {alert_item.profit >= alerts.min_profit}")
    print(f"Min margin check: {alert_item.margin_percent} >= {alerts.min_margin} = {alert_item.margin_percent >= alerts.min_margin}")
    
    if should_alert:
        print("✅ This item would trigger an alert with current settings")
    else:
        print("❌ This item would NOT trigger an alert")

if __name__ == "__main__":
    test_with_lower_thresholds()