# Archive Arbitrage — Liquidity-First Search Strategy Plan

_Date: 2026-03-12_

## Goal

Shift Archive Arbitrage from broad archive hunting toward a liquidity-first system that prioritizes:
- exact, high-confidence targets
- fast sell-through
- conservative resale assumptions
- strong margin of safety
- low-noise public alerts

This does **not** create guaranteed profit, but it should move the system toward higher-certainty deals that are easier and faster to flip.

---

## Core Strategic Principles

### 1. Favor liquid winners over interesting items
The system should prioritize items with:
- high sold volume
- low variance in sold price
- fast average / median days-to-sell
- exact queryable identity
- low junk-query rate

### 2. Use conservative liquidation pricing
Do not assume median/average sold is fully realizable.
Use a conservative liquidation anchor based on the lower end of trustworthy comps.

### 3. Separate candidate hunting from public alerting
Broad hunting is acceptable internally.
Discord/public output should require a much cleaner confidence profile.

### 4. Track query quality explicitly
Every target/query should earn its place based on outcomes, not instinct.

---

## Implementation Roadmap

## Phase 1 — Improve Target Intelligence

### 1A. Query junk-ratio tracking
Track per query:
- raw listings found
- listings after prefilters
- listings rejected for mismatch/category/auth/implausible gap
- final deals passed
- public alerts sent

Derived metrics:
- `junk_ratio`
- `pass_ratio`
- `alert_ratio`

Use these to demote or rewrite bad queries.

### 1B. A-tier / B-tier / trap-tier targets
Classify queries into:
- **A-tier** — exact model, liquid, low-junk
- **B-tier** — promising but noisier
- **Trap-tier** — broad, messy, low-confidence

### 1C. Query families
For each target, maintain:
- canonical query
- marketplace-native phrasing
- shorthand / typo variants
- seller-blind fallback descriptors

---

## Phase 2 — Improve Pricing Certainty

### 2A. Conservative liquidation price
Use a conservative resale anchor rather than flattering average sold prices.
Preferred anchors:
- authenticated comp median
- p25 sold price
- conservative platform-adjusted floor
- high-confidence hyper-price only when CV is low

### 2B. Margin-of-safety scoring
Rank deals by:
- liquidation price minus all-in cost
- profit after fees and shipping
- resilience to a downside haircut

---

## Phase 3 — Liquidity-First Ranking

Promote targets with:
- strong sold volume
- low price dispersion
- fast sell-through
- high alert conversion
- low junk rate

Demote targets with:
- broad category bleed
- high implausible-gap rate
- low pass rate
- weak authenticated comp support

---

## Phase 4 — Better Sourcing

Prioritize sources where:
- mispricing happens frequently
- seller sophistication is lower
- authentication risk is manageable
- resale path is liquid and proven

Likely buy-side focus:
- Poshmark
- eBay
- Mercari
- Japan sources
- Vinted once stable again

Likely sell-side focus:
- Grailed
- eBay by category

---

## Immediate Build Order

### Build next
1. Query junk-ratio tracking
2. A-tier / B-tier / trap-tier target scoring inputs
3. Conservative liquidation pricing
4. Margin-of-safety deal ranking

### Already completed today
- stricter query/category matching
- stricter public alert quality gating
- repo cleanup and docs reset

---

## Success Criteria

We should consider this strategy working when:
- fewer junk candidates survive filters
- Discord alerts become rarer but higher quality
- more alerts are for exact, liquid, fast-selling items
- target rotation increasingly favors proven winners
- profit estimates are more conservative and reliable
