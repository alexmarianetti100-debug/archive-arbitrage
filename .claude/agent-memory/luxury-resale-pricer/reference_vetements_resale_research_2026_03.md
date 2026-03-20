---
name: Vetements Resale Market Research (March 2026)
description: Comprehensive Vetements resale research — most liquid pieces, avg sold prices, Grailed query optimization, authentication tells, Demna vs Guram era value split, and collab pricing data
type: reference
---

## Market Context

Vetements sits in an unusual position on the resale market. The brand was founded in 2014 by Demna Gvasalia and his brother Guram. Demna departed in September 2019, and Guram became creative director in 2021. This creates a clear **two-era value split**:
- **Demna era (2014-2019)**: Appreciating archival pieces, strong demand, higher floor prices
- **Guram era (2020-present)**: Depreciating/stable, lower demand, faster selling but at steep discounts from retail

The brand was declared "dead" by multiple fashion publications post-Demna departure, but continues to operate. Key dynamic: buyers shifted spending from Vetements to Demna-designed Balenciaga, which offered similar aesthetic at lower price with stronger brand cachet.

## Most Liquid Pieces (Ranked by Sell-Through)

### Tier 1 — High Liquidity (sells within 1-2 weeks)
1. **Polizei Hoodie** — $435-$1,484 (green), $300-$800 (other colors). Iconic institutional parody piece. High recognition factor drives consistent demand.
2. **Metal Logo Hoodie (OG AW15-AW17)** — $400-$600 (worn), $800-$1,200 (excellent/DS). The original Vetements hoodie design. OG versions with Demna wash tags command premium.
3. **DHL T-Shirt (SS16)** — $300-$500 (worn), $1,500-$3,300 (NWT original). The piece that made the brand viral. NWT SS16 originals are grails; later re-releases sell for much less.
4. **Total Fucking Darkness Hoodie (AW17)** — $800-$1,800 (used), $1,800-$2,500+ (DS). Retail was $1,265. Strong appreciation.
5. **Champion Collaboration Hoodie** — $195-$715 sold prices across platforms. Wide price range due to multiple seasons/colorways.

### Tier 2 — Medium Liquidity (2-4 weeks)
6. **Oversized Raincoat (various)** — $272-$504. Iconic silhouette. Polizei raincoat variant more desirable.
7. **Alpha Industries Bomber** — $477-$850. Decent demand but niche sizing.
8. **Staff Hoodie** — $340-$480. Lower demand than logo pieces but consistent.
9. **Tourist Hoodie** — ~$408 sold. Moderate demand.
10. **Snoop Dogg Oversized Tee** — $696-$920. Pop culture appeal drives sales.

### Tier 3 — Slower but Valuable
11. **Levi's Reworked Denim (jacket or jeans)** — $800-$1,350. Niche but dedicated buyer base.
12. **Tommy Hilfiger Collab Hoodie** — $200-$580. Depreciating. Sold for $200 from $1,150 retail.
13. **Reebok Instapump Fury** — $205-$398. Below retail ($880). Low demand on StockX.
14. **Lighter Heel Sock Boots** — $375-$600. Niche women's piece, below retail.
15. **Antwerpen Hoodie** — $458-$880. Moderate demand, deconstructed aesthetic.

## Authentication Notes

- **Most faked**: DHL tees, Champion hoodies, Total Darkness hoodies, logo tees
- **Wash tag tells**: Fake Vetements wash tags have inscription that isn't thin enough; gap between "E" and "T" in "VETEMENTS" text
- **Size label**: Must be printed on, not stitched — counterfeits often stitch the size indication
- **Embroidery**: Real pieces have very dense, high-quality stitching; fakes show loose embossment
- **Georgian text**: Printing thickness and fonts differ between auth/fake, noticeable in Georgian script
- **Patch details**: Demna signature patches — replicas often fail here
- **Price floor**: Authentic Vetements pieces rarely sell below $100-150 for any category

## Key Market Dynamics

- Vetements is NOT in tier_rules.json for any subscription tier — currently only in realtime_monitor.py as Tier C brand
- Brand is in gap_hunter.py with min thresholds of $150 (hoodie) and $200 (bomber)
- Only 2 queries in smart_scrape.py: "vetements champion" and "vetements total darkness"
- Demna era pieces are the only ones worth tracking for arbitrage — Guram era pieces depreciate from retail
- Heavy replica market means authentication gate should be strict (min_auth 0.75+)
- The Polizei and Metal Logo hoodies are the workhorses — consistent demand, recognizable, and authenticated more easily
