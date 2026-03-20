---
name: Query Expansion Research (March 2026)
description: Comprehensive deep-dive identifying missing queries, telemetry-driven promotions, new brands, query reformulations, and tier rule gaps across all covered brands
type: reference
---

## Key Findings (2026-03-15)

### Highest-Impact Promotions (already in system, just need PROMOTED status)
1. "balenciaga skater sweatpants" — 12 deals / 6 runs (2.0 ratio), 83.8% gap, 4 candidates
2. "carol christian poell leather jacket" — 7/7 runs (100%), 89.3% gap, tier A
3. "chrome hearts pony hair triple" — 13 deals / 10 runs, 80.6% gap
4. "chrome hearts paper jam triple" — 5/5 runs (100%), 77.8% gap
5. "chrome hearts gittin any frame" — 9 post-filter candidates, 84.9% gap
6. "raf simons 2002" — 8 deals / 4 runs (2.0 ratio)
7. "visvim bomber jacket" — 5 deals / 3 runs (1.67 ratio)
8. "kapital boro jacket" — 5 deals / 3 runs, 4 candidates
9. "thierry mugler leather jacket" — 2/2 runs (100%)
10. "number nine cargo pants" — 2/3 runs, 94.4% gap

### Critical New Queries
- Dior Homme: "dior homme fw07 navigate", "dior homme navigate"
- Raf Simons: "raf simons riot riot riot", "raf simons nebraska", "raf simons parka"
- Helmut Lang: "helmut lang 1998", "helmut lang bondage strap" (replace failing niche queries)
- Rick Owens: "rick owens stooges leather jacket", "rick owens biker jacket", "rick owens champion"
- Wacko Maria: "wacko maria hawaiian shirt" (brand needs tier_rules.json addition)

### Dead Queries to Demote
- "kapital jacket" — 35 runs, 0 deals
- "rick owens geobasket" — 146 runs, 1 deal (over-scanned)
- "raf simons ozweego" — 61 runs, 0 deals
- "balenciaga arena high top" — 64 runs, 1 deal
- "celine sneakers" — 29 runs, 0 deals

### Brands Needing tier_rules.json Addition
- wacko maria (pro + big_baller)
- neighborhood (pro + big_baller)
- wtaps (pro + big_baller)
- hysteric glamour (big_baller only)
- gallery dept (beginner + pro, with strict auth)
