---
name: Brand Tier Configuration Gaps
description: Many deal-producing brands (Balenciaga, Dior Homme, JPG, ERD, Undercover, Kapital, Visvim) are NOT in tier_rules.json brands lists — deals from these brands cannot route to any Discord channel
type: project
---

Critical finding: 49+ queries for non-tier brands are finding deals but can never send alerts because classify_discord_tiers() checks brand membership.

Top offenders by deal volume:
- Jean Paul Gaultier: 41 deals (not in ANY tier)
- Balenciaga: 36+ deals across many queries (not in ANY tier)
- Dior Homme: 17+ deals (not in ANY tier — only "dior" would need to be added)
- Enfants Riches Deprimes: 8 deals (not in ANY tier)
- Undercover: 7+ deals
- Kapital: 5+ deals
- Visvim: 5+ deals

**Why:** tier_rules.json only has a small set of brands. Many archive/luxury brands with proven deal flow are excluded.

**How to apply:** Add balenciaga, dior, dior homme, jean paul gaultier, enfants riches deprimes, undercover, kapital, visvim, yohji yamamoto, junya watanabe, julius, boris bidjan saberi, alexander mcqueen, ann demeulemeester, haider ackermann, thierry mugler to pro/big_baller tier brand lists.
