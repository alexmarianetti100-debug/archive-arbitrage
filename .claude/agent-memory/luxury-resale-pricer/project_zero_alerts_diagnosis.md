---
name: Zero Alerts Pipeline Diagnosis
description: Root cause analysis of why the archive arbitrage system finds 921 deals but sends 0 public alerts — pipeline funnel bottlenecks identified 2026-03-15
type: project
---

Pipeline funnel as of 2026-03-15:
- 921 deals found across 311 queries and 4,941 runs
- Only 126 reach post_filter_candidates (14% passthrough)
- 69 killed by validation_engine (55% of candidates)
- 57 survive validation but ZERO become alerts

**Why:** The remaining 57 candidates are killed by the public-send gates in process_deal():
1. Quality score < 55 (DISCORD_MIN_QUALITY_SCORE default)
2. Medium comp confidence requires fire level 3 (DISCORD_ALLOW_MEDIUM_COMP_CONFIDENCE=0)
3. Weak sold-comp auth (<3 authenticated comps, <75% confidence)
4. Downside profit < $25 or MOS score < 35

The comp confidence gate is the likely killer — most deals have "medium" confidence because comps rarely perfectly match, and fire_level=3 (score >= 70) is very hard to hit.

**How to apply:** Recommend setting DISCORD_ALLOW_MEDIUM_COMP_CONFIDENCE=1 or lowering DISCORD_MIN_QUALITY_SCORE to 45 to unblock the pipeline. Also validation_engine kills 55% of candidates — many are false positives from overly strict diffusion matching.
