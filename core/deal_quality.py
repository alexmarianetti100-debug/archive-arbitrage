#!/usr/bin/env python3
"""
Deal Quality Scorer — Combines all signal modules into a single quality score.

Integrates line detection, condition parsing, season detection, size scoring,
and auth confidence into a 0-100 quality score that determines:
1. Whether to send an alert at all
2. How to present/rank the deal (fire levels)
"""

import logging
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass, field

from core.line_detection import detect_line
from core.condition_parser import parse_condition
from core.season_detector import detect_season_value
from core.size_scorer import score_size

logger = logging.getLogger("deal_quality")

# ══════════════════════════════════════════════════════════════════════
# SCORE COMPONENT WEIGHTS (must sum to 100)
# ══════════════════════════════════════════════════════════════════════

WEIGHT_GAP = 25        # How far below market (bigger gap = better)
WEIGHT_LINE = 18       # Mainline > diffusion
WEIGHT_CONDITION = 12  # Better condition = more upside
WEIGHT_SEASON = 12     # Archive/grail seasons worth more
WEIGHT_SIZE = 8        # Popular sizes = faster flip
WEIGHT_AUTH = 10       # Higher auth score = safer bet
WEIGHT_LIQUIDITY = 15  # Proven liquidity signals (followers, days-to-sell, photo count)

# ══════════════════════════════════════════════════════════════════════
# THRESHOLDS
# ══════════════════════════════════════════════════════════════════════

THRESHOLD_FIRE_3 = 70   # 🔥🔥🔥 FIRE deal, send immediately
THRESHOLD_FIRE_2 = 50   # 🔥🔥 Good deal, send
THRESHOLD_FIRE_1 = 35   # 🔥 Decent deal, send
# Below 35: Don't send


@dataclass
class DealSignals:
    """All signals computed for a deal."""
    # Line detection
    line_name: str = "Unknown"
    line_multiplier: float = 1.0
    line_explanation: str = ""

    # Condition
    condition_tier: str = "GENTLY_USED"
    condition_multiplier: float = 0.70
    condition_explanation: str = ""

    # Season
    season_name: Optional[str] = None
    season_multiplier: float = 1.0
    season_explanation: str = ""

    # Size
    detected_size: Optional[str] = None
    size_multiplier: float = 1.0
    size_explanation: str = ""

    # Auth
    auth_confidence: float = 0.5

    # Liquidity
    follower_count: int = 0
    heat_score: float = 0.0  # Grailed's heat_f metric
    avg_days_to_sell: float = 0.0
    photo_count: int = 0
    liquidity_score: float = 0.0

    # Gap
    gap_percent: float = 0.0
    profit_estimate: float = 0.0

    # Final score
    quality_score: float = 0.0
    fire_level: int = 0  # 0=don't send, 1-3=fire emojis
    score_breakdown: Dict[str, float] = field(default_factory=dict)


def calculate_deal_quality(
    item,
    brand: str,
    sold_data,
    gap_percent: float,
    profit: float,
    auth_confidence: float = 0.5,
    avg_days_to_sell: float = 0.0,
) -> Tuple[float, DealSignals]:
    """
    Calculate a comprehensive deal quality score (0-100).

    Args:
        item: ScrapedItem with title, description, price, etc.
        brand: Detected brand name
        sold_data: SoldData with avg_price, median_price, count
        gap_percent: How far below market (0.0-1.0)
        profit: Estimated profit in dollars
        auth_confidence: Auth checker confidence (0.0-1.0)

    Returns:
        (quality_score 0-100, DealSignals with full breakdown)
    """
    title = item.title or ""
    description = item.description or ""
    category = getattr(item, "category", "") or ""

    signals = DealSignals(
        gap_percent=gap_percent,
        profit_estimate=profit,
        auth_confidence=auth_confidence,
    )

    # ── 1. Line Detection ──
    try:
        line_name, line_mult, line_expl = detect_line(title, brand, description)
        signals.line_name = line_name
        signals.line_multiplier = line_mult
        signals.line_explanation = line_expl
    except Exception as e:
        logger.debug(f"Line detection error: {e}")

    # ── 2. Condition Parsing ──
    try:
        cond_tier, cond_mult, cond_expl = parse_condition(title, description, brand, category)
        signals.condition_tier = cond_tier
        signals.condition_multiplier = cond_mult
        signals.condition_explanation = cond_expl
    except Exception as e:
        logger.debug(f"Condition parsing error: {e}")

    # ── 3. Season Detection ──
    try:
        season_name, season_mult, season_expl = detect_season_value(title, brand, description)
        signals.season_name = season_name
        signals.season_multiplier = season_mult
        signals.season_explanation = season_expl
    except Exception as e:
        logger.debug(f"Season detection error: {e}")

    # ── 4. Size Scoring ──
    try:
        size_str, size_mult, size_expl = score_size(title, brand, category)
        signals.detected_size = size_str
        signals.size_multiplier = size_mult
        signals.size_explanation = size_expl
    except Exception as e:
        logger.debug(f"Size scoring error: {e}")

    # ══════════════════════════════════════════════════════════════
    # SCORE CALCULATION
    # ══════════════════════════════════════════════════════════════

    # Gap value (0-30): How far below market
    # 30% gap = 0 points, 50% gap = 15 points, 70%+ gap = 30 points
    gap_normalized = min(1.0, max(0.0, (gap_percent - 0.30) / 0.40))
    gap_score = gap_normalized * WEIGHT_GAP

    # Line value (0-20): Mainline = full points, diffusion = proportional
    # 1.0x = 20 points, 0.5x = 10 points, 0.1x = 2 points
    # Above 1.0x (archive eras) = bonus points
    line_score = min(WEIGHT_LINE, signals.line_multiplier * WEIGHT_LINE)

    # Condition value (0-15): Better condition = more points
    # Deadstock (1.0x) = 15, Near DS (0.9x) = 13.5, Used (0.5x) = 7.5
    condition_score = signals.condition_multiplier * WEIGHT_CONDITION

    # Season value (0-15): Higher tier season = more points
    # 1.0x (no special season) = 7.5 (baseline), 2.0x (S-tier) = 15
    season_normalized = min(1.0, (signals.season_multiplier - 1.0) / 1.0)  # 0-1 scale
    season_score = (0.5 + 0.5 * season_normalized) * WEIGHT_SEASON

    # Size value (0-10): Popular sizes = more points
    # 1.15x (M) = 10, 1.0x = 7, 0.75x (XS) = 4
    size_normalized = min(1.0, max(0.0, (signals.size_multiplier - 0.65) / 0.50))
    size_score = size_normalized * WEIGHT_SIZE

    # ── 5. Liquidity Scoring ──
    # Based on: heat_f (Grailed's own heat metric), follower count,
    # days-to-sell, photo count
    raw = item.raw_data if hasattr(item, "raw_data") and item.raw_data else {}
    follower_count = raw.get("followerno", 0) or 0
    heat_score_raw = raw.get("heat_f", 0) or 0  # Grailed's internal heat metric
    photos_list = raw.get("photos", [])
    photo_count = len(photos_list) if isinstance(photos_list, list) else 0

    signals.follower_count = follower_count
    signals.heat_score = heat_score_raw
    signals.avg_days_to_sell = avg_days_to_sell
    signals.photo_count = photo_count

    liq_score = 0.0

    # Heat score (0-4 points): Grailed's own demand signal
    # Higher heat_f = more views/saves/interest on the platform
    if heat_score_raw >= 10000:
        liq_score += 4.0  # Viral-level heat
    elif heat_score_raw >= 5000:
        liq_score += 3.0
    elif heat_score_raw >= 1000:
        liq_score += 2.0
    elif heat_score_raw >= 200:
        liq_score += 1.0

    # Followers (0-4 points): more followers = more demand for this listing
    if follower_count >= 10:
        liq_score += 4.0
    elif follower_count >= 5:
        liq_score += 3.0
    elif follower_count >= 2:
        liq_score += 2.0
    elif follower_count >= 1:
        liq_score += 1.0

    # Days-to-sell (0-5 points): faster sell = more liquid
    if avg_days_to_sell > 0:
        if avg_days_to_sell <= 7:
            liq_score += 5.0  # Sells within a week
        elif avg_days_to_sell <= 14:
            liq_score += 4.0
        elif avg_days_to_sell <= 30:
            liq_score += 2.5
        elif avg_days_to_sell <= 60:
            liq_score += 1.0
        # 60+ days = 0 points (illiquid)
    else:
        liq_score += 2.5  # Unknown = neutral

    # Photo count (0-2 points): more photos = more trustworthy listing
    if photo_count >= 8:
        liq_score += 2.0
    elif photo_count >= 5:
        liq_score += 1.5
    elif photo_count >= 3:
        liq_score += 1.0

    liquidity_score = min(WEIGHT_LIQUIDITY, liq_score)
    signals.liquidity_score = liquidity_score

    # Auth confidence (0-10)
    auth_score = auth_confidence * WEIGHT_AUTH

    # Total quality score
    quality_score = gap_score + line_score + condition_score + season_score + size_score + auth_score + liquidity_score
    quality_score = min(100.0, max(0.0, quality_score))

    # Apply hard penalty for very low-value diffusion lines
    # CDG Play (0.1x), MM6 (0.2x), Junior Gaultier (0.15x) etc.
    # These items are rarely worth flipping regardless of gap
    if signals.line_multiplier <= 0.25:
        diffusion_penalty = (0.25 - signals.line_multiplier) / 0.25  # 0-1 scale
        quality_score *= (1.0 - diffusion_penalty * 0.5)  # Up to 50% reduction

    signals.quality_score = quality_score
    signals.score_breakdown = {
        "gap": round(gap_score, 1),
        "line": round(line_score, 1),
        "condition": round(condition_score, 1),
        "season": round(season_score, 1),
        "size": round(size_score, 1),
        "auth": round(auth_score, 1),
        "liquidity": round(liquidity_score, 1),
    }

    # Determine fire level
    if quality_score >= THRESHOLD_FIRE_3:
        signals.fire_level = 3
    elif quality_score >= THRESHOLD_FIRE_2:
        signals.fire_level = 2
    elif quality_score >= THRESHOLD_FIRE_1:
        signals.fire_level = 1
    else:
        signals.fire_level = 0

    logger.info(
        f"Deal quality: {quality_score:.0f}/100 {'🔥' * signals.fire_level or '❌'} | "
        f"gap={gap_score:.0f} line={line_score:.0f} cond={condition_score:.0f} "
        f"season={season_score:.0f} size={size_score:.0f} auth={auth_score:.0f} liq={liquidity_score:.0f} "
        f"(heat={heat_score_raw} foll={follower_count} dts={avg_days_to_sell:.0f} photos={photo_count}) | "
        f"{title[:50]}"
    )

    return (quality_score, signals)


def format_signal_line(signals: DealSignals) -> str:
    """Format a compact signal summary line for alerts."""
    parts = []

    # Line tag
    if signals.line_multiplier != 1.0 or signals.line_name != "Unknown":
        parts.append(f"🏷️ {signals.line_name} ({signals.line_multiplier:.1f}x)")

    # Season tag
    if signals.season_name and signals.season_multiplier > 1.0:
        tier = "S-Tier" if signals.season_multiplier >= 1.8 else "A-Tier" if signals.season_multiplier >= 1.3 else ""
        if tier:
            parts.append(f"📅 {tier} Season (+{(signals.season_multiplier-1)*100:.0f}%)")
        else:
            parts.append(f"📅 {signals.season_name}")

    # Size tag
    if signals.detected_size:
        if signals.size_multiplier >= 1.05:
            parts.append(f"👟 Hot Size ({signals.detected_size})")
        elif signals.size_multiplier <= 0.85:
            parts.append(f"👟 Niche Size ({signals.detected_size})")
        else:
            parts.append(f"👟 {signals.detected_size}")

    # Heat/demand tag
    if signals.heat_score >= 5000:
        parts.append("🔥 High Demand")
    elif signals.heat_score >= 1000:
        parts.append("📈 Trending")

    # Days-to-sell tag
    if signals.avg_days_to_sell > 0 and signals.avg_days_to_sell <= 14:
        parts.append(f"⚡ Sells in ~{signals.avg_days_to_sell:.0f}d")

    return " | ".join(parts) if parts else ""


def format_quality_header(signals: DealSignals) -> str:
    """Format the deal header with fire emojis and score."""
    fire = "🔥" * signals.fire_level
    if signals.fire_level == 3:
        label = "FIRE DEAL"
    elif signals.fire_level == 2:
        label = "GOOD DEAL"
    elif signals.fire_level == 1:
        label = "DEAL"
    else:
        label = "BELOW THRESHOLD"
    return f"{fire} <b>{label}</b> (Score: {signals.quality_score:.0f}/100)"


# ══════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from dataclasses import dataclass as dc

    @dc
    class MockItem:
        title: str = ""
        description: str = ""
        price: float = 0
        category: str = ""

    @dc
    class MockSold:
        avg_price: float = 0
        median_price: float = 0
        count: int = 5

    tests = [
        # (title, brand, price, sold_avg, gap%, profit, auth, expected_score_range, expected_fire)
        (
            "Rick Owens Geobasket Black EU 43 BNWT",
            "rick owens", 350, 750, 0.53, 332, 0.82,
            (60, 100), 2,  # Mainline, deadstock, hot size, decent gap
        ),
        (
            "Raf Simons Riot Riot Riot Bomber FW01 Size M VNDS",
            "raf simons", 1200, 3500, 0.66, 1985, 0.90,
            (75, 100), 3,  # S-tier season, mainline, near DS, huge gap
        ),
        (
            "CDG Play Heart Tee Size M",
            "comme des garcons", 30, 55, 0.45, 12, 0.70,
            (0, 35), 0,  # Play line (0.1x) should kill the score
        ),
        (
            "MM6 Maison Margiela Tote Bag Used",
            "maison margiela", 60, 120, 0.50, 37, 0.65,
            (30, 50), 1,  # MM6 (0.2x) marginal deal — low fire
        ),
        (
            "Rick Owens DRKSHDW Ramones Low Size 42",
            "rick owens", 150, 280, 0.46, 85, 0.75,
            (25, 55), 1,  # DRKSHDW (0.35x) medium-low
        ),
        (
            "Helmut Lang Vintage Bondage Jacket 1998 Size M Like New",
            "helmut lang", 400, 1200, 0.67, 692, 0.85,
            (65, 100), 2,  # Archive era (3.0x), great condition, big gap
        ),
    ]

    print(f"\n{'='*80}")
    print("DEAL QUALITY SCORER TEST")
    print(f"{'='*80}\n")

    passed = 0
    failed = 0

    for title, brand, price, sold_avg, gap, profit, auth, (low, high), expected_fire in tests:
        item = MockItem(title=title, price=price)
        sold = MockSold(avg_price=sold_avg, median_price=sold_avg)

        score, signals = calculate_deal_quality(item, brand, sold, gap, profit, auth)

        ok_score = low <= score <= high
        ok_fire = signals.fire_level >= expected_fire  # At least expected fire level
        status = "PASS" if (ok_score and ok_fire) else "FAIL"
        emoji = "✅" if status == "PASS" else "❌"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        fire_str = "🔥" * signals.fire_level or "❌"
        print(f"{emoji} {title[:60]:60s}")
        print(f"   Score: {score:.0f}/100 {fire_str} | Expected: {low}-{high}, fire>={expected_fire}")
        print(f"   Breakdown: {signals.score_breakdown}")
        print(f"   Line: {signals.line_name} ({signals.line_multiplier:.1f}x)")
        print(f"   Condition: {signals.condition_tier} ({signals.condition_multiplier:.2f}x)")
        print(f"   Season: {signals.season_name} ({signals.season_multiplier:.1f}x)")
        print(f"   Size: {signals.detected_size} ({signals.size_multiplier:.2f}x)")
        signal_line = format_signal_line(signals)
        if signal_line:
            print(f"   Signal: {signal_line}")

    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
