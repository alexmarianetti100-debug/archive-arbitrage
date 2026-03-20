---
name: ERD Enfants Riches Deprimes Query Research (March 2026)
description: Comprehensive ERD query research for Grailed arbitrage — includes pricing, liquidity, authentication notes, and implementation priority
type: reference
---

## Current System State (as of 2026-03-15)

**Existing ERD queries:**
- "enfants riches deprimes hoodie" (promoted, in target_families)
- "enfants riches deprimes leather jacket" (promoted, in target_families)
- "enfants riches deprimes jeans" (promoted, in target_families)
- "enfants riches deprimes tee" (in target_families)
- "enfants riches deprimes" (broad, in trend_engine — 2 runs, 8 deals, 97.5% best gap)
- "erd hoodie" (in smart_scrape)
- "erd tee" (in smart_scrape)

**Key finding:** The broad "enfants riches deprimes" query found 8 deals in only 2 runs with a 97.5% best gap — highest deal-rate of any brand query in the system. ERD is massively underserved with only 4 specific queries.

**Current pricing floors are WAY too low:**
- pricing.py: jacket=$500, pants=$300, shirt=$250, tee=$200, hoodie=$350
- gap_hunter.py: hoodie=$450, jacket=$500, tee=$200, jeans=$300, sweater=$350, hat=$150
- Actual market: tees=$400-$900 sold, hoodies=$450-$1,500 sold, jackets=$1,500-$4,000 sold

## Authentication Notes

ERD is increasingly counterfeited. Key tells:
- Real ERD prints look intentionally faded; fakes are too sharp/bold/crisp
- Tags are high-quality cotton/woven, brand name in all caps, stark minimalist font
- Fakes fail on: inconsistent wash tag text, overly bold prints, misaligned size labels, sloppy neck tag stitching
- Auth keywords: "erd", "henri alexander levy", "made in usa" (earlier pieces), "made in italy" (leather/newer)
- Common misspellings indicating reps: "enfant riche deprime"
- The Viper Room hats had a cease & desist from the actual club — adds provenance value

## Market Context (March 2026)

- ERD retail prices have climbed: tees $810-$1,680, hoodies $1,445-$4,000, leather jackets $2,700-$9,300
- Brand maintains artificial scarcity — micro-batches, hand-distressed 1-of-1 pieces
- Henri Alexander Levy's personal brand/celebrity connections drive demand
- ERD is in the "archive" tier recognition in the system alongside Raf, Helmut, Number Nine
- Grailed is the primary resale platform for ERD (more volume than eBay/TRR combined)
