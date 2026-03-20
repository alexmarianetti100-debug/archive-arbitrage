# Archive Arbitrage — Query Research Memo

_Date: 2026-03-13_

## Goal

Identify which queries should be:
- promoted into a liquidity-first A-tier working set
- kept but treated as efficient / lower-yield
- rewritten due to duplication or malformed structure
- demoted or killed due to persistent underperformance

This memo is based on current telemetry in:
- `data/trends/query_performance.json`
- `data/trends/golden_catalog.json`

---

## Important Caveat

Current telemetry is useful but imperfect:
- many entries are older run/deal counters without recent `junk_ratio` / `alert_ratio`
- several query families are fragmented across duplicates and malformed variants
- some broad brand-level queries still look strong numerically but may be too noisy for a strict liquidity-first system

So this memo should guide the next target refactor, not be treated as mathematically final truth.

---

## High-Level Findings

### 1. Some broad queries still "work," but are too coarse for the end-state system
Examples:
- `rick owens`
- `chrome hearts`
- `saint laurent`
- `maison margiela`
- `jean paul gaultier`

These queries produce deals, but they are too broad to be the final form of a liquidity-first target set. They should be treated as discovery/family umbrellas, not permanent exact-model A-tier targets.

### 2. A set of exact or semi-exact queries clearly outperform
These are the best candidates for a tighter liquidity-first hunting core.

### 3. Some high-opportunity catalog entries are actually dead or highly efficient
Examples:
- `rick owens geobasket`
- `rick owens ramones`
- `maison margiela tabi`
- `rick owens leather jacket`
- `chrome hearts cemetery cross`

These are important products in the resale market, but current query behavior shows the active marketplace is either too efficient or too noisy to justify heavy hunting time.

### 4. Duplicate / malformed query families are absolutely real
Examples:
- `rick owens dr. martens dr`
- `rick owens dr. martens dr.`
- `saint laurent hedi slimane paris`
- `saint laurent paris hedi slimane`
- `balenciaga balenciaga runner`
- `saint laurent paris sz paris`

These need normalization before telemetry can be fully trusted.

---

## Recommended Liquidity-First Core (Promote)

These queries look strong enough to keep or promote as the near-term exact-ish working set.

### Chrome Hearts
- `chrome hearts cross pendant`
- `chrome hearts baby fat pendant`
- `chrome hearts paper chain`
- `chrome hearts tee`
- `chrome hearts neck logo long`
- `chrome hearts vagilante glasses`
- `chrome hearts trypoleagain glasses`
- `chrome hearts see you tea`

Why:
- consistently productive
- specific enough to reduce broad junk
- multiple pendant / eyewear / apparel subfamilies show real deal yield

### Saint Laurent
- `saint laurent wyatt boots`
- `saint laurent paris paris oil`
- normalize / replace `saint laurent paris sz paris` with the real product identity

Why:
- SLP still produces, especially around boots and certain Hedi-era exact product patterns
- but the family needs query cleanup

### Maison Margiela
- `maison margiela gat`
- `maison margiela gat low`
- `maison margiela tabi boots`
- possibly `maison margiela replica`

Why:
- still productive enough to matter
- exact enough to fit a liquidity-first model better than broad Margiela brand hunting

### Rick Owens
- `rick owens dunks`
- `rick owens memphis`
- `rick owens creatch cargo`
- `rick owens grained leather sneakers`
- normalized RO x Dr. Martens family

Why:
- not all RO targets are equal
- some high-icon products still produce deals
- others are clearly too efficient and should be deprioritized

### Bottega Veneta
- `bottega veneta intrecciato leather briefcase`
- `bottega veneta orbit sneaker` / `orbit sneakers` (normalize to one family)

Why:
- very strong productivity on certain exact products
- current query family likely fragmented

### Dior Homme / Hedi-era Dior
- `dior homme luster denim`
- `dior homme hedi slimane clawmark`
- `dior homme jeans`

Why:
- historically productive in current telemetry
- strong archive resale appeal with recognizable product identities

### Other exact winners worth keeping in rotation
- `undercover arts and crafts`
- `undercover bug denim`
- `balenciaga 3xl`
- `balenciaga lost tape flared`
- `prada america’s cup sneakers`
- `raf simons sterling ruby`
- `kapital century denim`
- `carol christian poell leather jacket`

---

## Keep but Treat as Efficient / Secondary

These are not obvious kills, but they should not dominate a liquidity-first rotation because conversion is low relative to run volume.

- `rick owens geobasket`
- `maison margiela replica gat`
- `maison margiela paint splatter`
- `prada americas cup`
- `chrome hearts cross ring`
- `balenciaga 3xl`
- `saint laurent hedi slimane paris`
- `maison margiela gats`
- `margiela tabi boots`
- `dior homme hedi slimane jacket`
- `vivienne westwood`
- `margiela tabi`
- `number nine leather jacket`

Interpretation:
- these may still produce occasional wins
- but they look too efficient or too broad to deserve heavy run share
- use them as secondary rotation, not first-priority anchor hunting

---

## Demote / Kill / Rewrite Aggressively

These are the strongest candidates for demotion or removal due to persistent underperformance.

### Hard demote / kill
- `maison margiela tabi`
- `rick owens leather jacket`
- `chrome hearts cemetery cross`
- `chrome hearts hoodie`
- `chrome hearts dagger pendant`
- `balenciaga defender`
- `rick owens ramones`
- `chrome hearts floral cross`
- `saint laurent paris paris wyatt`
- `prada linea rossa`
- `saint laurent court classic`
- `chrome hearts horseshoe hoodie`
- `rick owens bauhaus cargo`
- `rick owens ramones low`
- `prada sneakers`
- `chrome hearts trucker hat`
- `prada cloudbust`

### Probably kill as malformed / low-value legacy noise
- `balenciaga balenciaga runner` (rewrite, not literal keep)
- `saint laurent paris sz paris` (rewrite)
- `rick owens dr. martens dr`
- `rick owens dr. martens dr.`
- `number (n)ine ...` malformed repeated-token family entries

---

## Query Families That Need Normalization First

These should become canonical target families before any serious telemetry trust.

### Saint Laurent
Current variants include:
- `saint laurent`
- `saint laurent paris sz paris`
- `saint laurent paris paris oil`
- `saint laurent paris hedi slimane`
- `saint laurent hedi slimane paris`
- `saint laurent paris paris wyatt`

Action:
- split into actual product families (Wyatt, L01, D02, Oil, etc.)
- remove duplicated brand tokens and malformed suffixes

### Rick Owens x Dr. Martens
Current variants include:
- `rick owens dr. martens dr`
- `rick owens dr. martens dr.`
- `rick owens dr. martens doc`
- `rick owens dr. martens quad`

Action:
- canonicalize into real product/model families
- drop malformed string residue

### Balenciaga Runner family
Current variants include:
- `balenciaga balenciaga runner`
- likely plain `balenciaga runner`
- related but distinct footwear families nearby

Action:
- normalize to one canonical runner family

### Margiela GAT / Tabi family
Current variants include:
- `maison margiela gat`
- `maison margiela gats`
- `maison margiela gat low`
- `maison margiela replica gat`
- `maison martin margiela replica GAT`
- `margiela tabi`
- `maison margiela tabi`
- `margiela tabi boots`
- `maison margiela tabi boots`

Action:
- canonicalize by product line + silhouette
- separate broad family, low-top, high-confidence exact versions

### Number (N)ine malformed family
Current variants include multiple repeated-token strings that should not exist in a mature target set.

Action:
- rewrite from scratch around real product identities
- stop logging malformed token soup as distinct targets

---

## Suggested Near-Term Working Set

If the goal is to improve the quality of the next wave fast, a practical working set would emphasize:

### Jewelry / accessories
- `chrome hearts cross pendant`
- `chrome hearts baby fat pendant`
- `chrome hearts paper chain`
- `bottega veneta intrecciato leather briefcase`

### Footwear
- `saint laurent wyatt boots`
- `maison margiela gat`
- `maison margiela gat low`
- `prada america’s cup sneakers`
- normalized `rick owens dr. martens` family
- `bottega veneta orbit sneaker`

### Pants / denim
- `dior homme luster denim`
- `dior homme jeans`
- `rick owens memphis`
- `rick owens creatch cargo`
- `balenciaga lost tape flared`
- `kapital century denim`

### Apparel exacts
- `chrome hearts tee`
- `chrome hearts neck logo long`
- `undercover arts and crafts`
- `undercover bug denim`
- `raf simons sterling ruby`

This is not the final full target set — it is the cleaner near-term working core.

---

## Strategic Conclusions

1. **Broad brand hunting still finds deals, but should become secondary**
   - use it for exploration and family discovery
   - not as the long-term public-facing liquidity-first engine

2. **The best opportunities are increasingly in exact subfamilies**
   - specific Chrome Hearts jewelry / eyewear / apparel
   - exact Hedi-era Dior and SLP items
   - exact Margiela GAT / Tabi variants
   - exact Rick Owens bottoms / collabs / certain footwear

3. **Some iconic products are too efficient right now**
   - Geobasket, Ramones, Tabi broad family, RO leather jacket
   - these may be good products to flip, but not necessarily good search queries to hunt aggressively

4. **Query normalization is mandatory**
   - the system has too many malformed and duplicate strings
   - telemetry-driven strategy will stay partially distorted until those are cleaned up

---

## Recommended Next Build Work

### Immediate
1. create canonical target-family definitions
2. normalize obvious duplicate/malformed families
3. move strong exact winners into a promoted liquidity-first pool
4. demote hard traps and low-yield efficient queries

### After normalization
5. aggregate telemetry by target family
6. upgrade TrendEngine weighting to use family-level productivity rather than raw query strings

---

## Bottom Line

The current telemetry says:
- there are real winning query families
- broad hunting helped discover them
- but the next stage should be a much cleaner, more exact, more normalized target set

The biggest opportunity now is not "more queries."
It is:
- **better exact queries**
- **fewer malformed duplicates**
- **less time wasted on efficient icons that rarely misprice**
