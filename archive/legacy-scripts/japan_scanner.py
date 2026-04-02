#!/usr/bin/env python3
"""
Japan Arbitrage Scanner

Run this script to scan Japanese auction sites for arbitrage opportunities.
Can be run manually or scheduled via cron.
"""

import asyncio
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from core.japan_integration import find_japan_arbitrage_deals, JapanArbitrageMonitor
from core.discord_alerts import send_discord_alert, DISCORD_ENABLED

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s'
)
logger = logging.getLogger("japan_scanner")


async def scan_and_alert(
    min_margin: float = 25.0,
    min_profit: float = 200.0,
    send_alerts: bool = True,
    output_file: str = None,
):
    """Scan for Japan arbitrage deals and optionally send alerts."""
    
    logger.info("🗾 Starting Japan Arbitrage Scan")
    logger.info(f"   Min Margin: {min_margin}%")
    logger.info(f"   Min Profit: ${min_profit}")
    
    # Find opportunities
    opportunities = await find_japan_arbitrage_deals(
        min_margin=min_margin,
        min_profit=min_profit,
    )
    
    if not opportunities:
        logger.info("No opportunities found this scan.")
        return []
    
    # Sort by net profit
    opportunities.sort(key=lambda x: x.net_profit, reverse=True)
    
    logger.info(f"\n🎯 Found {len(opportunities)} arbitrage opportunities")
    logger.info("=" * 70)
    
    # Display results
    for i, opp in enumerate(opportunities[:10], 1):  # Top 10
        logger.info(f"\n{i}. {opp.recommendation}: {opp.brand} {opp.title}")
        logger.info(f"   Japan: ¥{opp.item_price_jpy:,} → Landed: ${opp.total_landed_cost:,.0f}")
        logger.info(f"   US Market: ${opp.us_market_price:,.0f}")
        logger.info(f"   Profit: ${opp.net_profit:,.0f} ({opp.margin_percent:.1f}% margin)")
        logger.info(f"   Ends: {opp.end_time.strftime('%Y-%m-%d %H:%M') if opp.end_time else 'Unknown'}")
        logger.info(f"   URL: {opp.auction_url}")
        
        # Send Discord alert if enabled
        if send_alerts and DISCORD_ENABLED and opp.recommendation in ['STRONG_BUY', 'BUY']:
            try:
                # Create mock item for Discord alert
                class MockItem:
                    def __init__(self, opp):
                        self.title = f"{opp.brand} {opp.title}"
                        self.description = getattr(opp, 'description', '') or ''
                        self.price = opp.total_landed_cost
                        self.source = 'Japan (Buyee)'
                        self.url = opp.auction_url
                        self.images = [opp.image_url] if opp.image_url else []
                
                class MockSignals:
                    def __init__(self, opp):
                        self.fire_level = 3 if opp.recommendation == 'STRONG_BUY' else 2
                        self.quality_score = 85
                        self.gap_percent = opp.margin_percent / 100
                        self.profit_estimate = opp.net_profit
                        self.line_name = 'Japan Import'
                        self.season_name = opp.category
                        self.condition_tier = 'NEW'
                        self.detected_size = ''
                
                item = MockItem(opp)
                signals = MockSignals(opp)
                
                message = (
                    f"🗾 **Japan Arbitrage Opportunity**\n\n"
                    f"{opp.title_jp}\n"
                    f"Japan Price: ¥{opp.item_price_jpy:,}\n"
                    f"Landed Cost: ${opp.total_landed_cost:,.0f}\n"
                    f"US Market: ${opp.us_market_price:,.0f}\n"
                    f"**Net Profit: ${opp.net_profit:,.0f} ({opp.margin_percent:.1f}%)**\n\n"
                    f"Proxy: {opp.proxy_service} | Shipping: {opp.shipping_method}"
                )
                
                await send_discord_alert(
                    item=item,
                    message=message,
                    fire_level=signals.fire_level,
                    signals=signals,
                    auth_result=None,
                    tier='pro' if opp.net_profit >= 300 else 'beginner',
                )
                
                logger.info(f"   ✅ Discord alert sent")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to send Discord alert: {e}")
    
    # Save to file if specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(
                [opp.__dict__ for opp in opportunities],
                f,
                default=str,
                indent=2
            )
        logger.info(f"\n💾 Saved {len(opportunities)} opportunities to {output_file}")
    
    logger.info("\n✅ Scan complete!")
    return opportunities


def main():
    parser = argparse.ArgumentParser(
        description='Scan Japanese auctions for arbitrage opportunities'
    )
    parser.add_argument(
        '--min-margin',
        type=float,
        default=25.0,
        help='Minimum margin percentage (default: 25)'
    )
    parser.add_argument(
        '--min-profit',
        type=float,
        default=200.0,
        help='Minimum profit in USD (default: 200)'
    )
    parser.add_argument(
        '--no-alerts',
        action='store_true',
        help='Do not send Discord alerts'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Save results to JSON file'
    )
    
    args = parser.parse_args()
    
    # Run scan
    opportunities = asyncio.run(scan_and_alert(
        min_margin=args.min_margin,
        min_profit=args.min_profit,
        send_alerts=not args.no_alerts,
        output_file=args.output,
    ))
    
    # Exit code based on results
    return 0 if opportunities else 1


if __name__ == "__main__":
    exit(main())
