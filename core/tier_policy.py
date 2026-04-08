from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, List


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "tier_rules.json"


DEFAULT_RULES = {
    "beginner": {
        "min_profit": 100,
        "min_margin": 0.25,
        "min_liquidity": 7.0,
        "max_price": 2500,
        "brands": [
            "chrome hearts", "louis vuitton", "prada",
            "rick owens", "maison margiela", "margiela",
            "balenciaga", "vivienne westwood",
            "acne studios", "sacai",
        ],
        "routing": ["beginner", "pro", "whale"],
    },
    "pro": {
        "min_profit": 300,
        "min_margin": 0.25,
        "min_liquidity": 5.5,
        "max_price": 10000,
        "min_auth": 0.72,
        "strict_auth_min": 0.82,
        "brands": [
            "chrome hearts", "louis vuitton", "prada",
            "rick owens", "maison margiela", "margiela",
            "chanel",
            "celine", "bottega veneta", "saint laurent", "yves saint laurent",
            "balenciaga", "dior", "dior homme",
            "jean paul gaultier", "gaultier",
            "enfants riches deprimes", "erd",
            "undercover", "kapital",
            "alexander mcqueen", "thierry mugler", "mugler",
            "vivienne westwood", "julius",
            "haider ackermann", "dries van noten", "sacai",
            "lemaire", "guidi", "acne studios",
            "simone rocha", "brunello cucinelli",
            "takahiromiyashita", "soloist",
        ],
        "routing": ["pro", "whale"],
    },
    "big_baller": {
        "min_profit": 500,
        "min_margin": 0.20,
        "min_liquidity": 5.0,
        "min_price": 1500,
        "min_auth": 0.80,
        "brands": [
            "chrome hearts", "louis vuitton", "prada",
            "rick owens", "maison margiela", "margiela",
            "chanel",
            "celine", "bottega veneta", "saint laurent", "yves saint laurent",
            "carol christian poell", "ccp", "number nine", "number (n)ine",
            "raf simons", "helmut lang",
            "balenciaga", "dior", "dior homme",
            "jean paul gaultier", "gaultier",
            "enfants riches deprimes", "erd",
            "undercover", "kapital",
            "alexander mcqueen", "thierry mugler", "mugler",
            "vivienne westwood", "julius",
            "boris bidjan saberi", "haider ackermann", "ann demeulemeester",
            "hysteric glamour",
            "dries van noten", "sacai", "lemaire", "guidi",
            "acne studios", "simone rocha", "brunello cucinelli",
            "takahiromiyashita", "soloist",
        ],
        "routing": ["whale"],
    },
    "strict_auth_brands": [
        "chanel", "louis vuitton", "gucci", "balenciaga", "bottega veneta", "prada",
    ],
    "strict_auth_categories": [
        "bag",
    ],
    "terms": {
        "jewelry": ["ring", "bracelet", "necklace", "pendant", "chain", "cross", "dagger", "hardware", "paper chain"],
        "shoe": ["geobasket", "replica", "gat", "sneaker", "sneakers", "boots", "boot", "tabi", "wyatt", "dunks", "america’s cup", "runner", "arena", "derby", "loafer", "chocolate loafers"],
        "archive": ["archive", "vintage", "raf simons", "helmut lang", "rick owens", "number nine", "ccp", "carol christian poell", "dior homme", "jean paul gaultier", "undercover", "enfants riches deprimes", "haider ackermann", "dries van noten", "guidi", "lemaire", "soloist", "takahiromiyashita", "hysteric glamour"]
    },
}


def _load_rules() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return DEFAULT_RULES


RULES = _load_rules()
BEGINNER_BRANDS = set(RULES.get("beginner", {}).get("brands", []))
PRO_BRANDS = set(RULES.get("pro", {}).get("brands", []))
BIG_BALLER_BRANDS = set(RULES.get("big_baller", {}).get("brands", []))
STRICT_AUTH_BRANDS = set(RULES.get("strict_auth_brands", []))
TERMS = RULES.get("terms", {})

JEWELRY_TERMS = set(TERMS.get("jewelry", []))
SHOE_TERMS = set(TERMS.get("shoe", []))
ARCHIVE_TERMS = set(TERMS.get("archive", []))


@dataclass
class TierDecision:
    minimum_tier: str | None
    channel_tiers: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


def _title(item: Any) -> str:
    return (getattr(item, "title", "") or "").lower()


def _brand(item: Any) -> str:
    brand = (getattr(item, "brand", "") or "").lower()
    if brand:
        return brand
    title = _title(item)
    for candidate in sorted(BIG_BALLER_BRANDS, key=len, reverse=True):
        if candidate in title:
            return candidate
    return ""


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _is_jewelry(item: Any) -> bool:
    return _has_any(_title(item), JEWELRY_TERMS)


def _is_shoe(item: Any) -> bool:
    return _has_any(_title(item), SHOE_TERMS)


def _is_archive(item: Any) -> bool:
    return _has_any(_title(item), ARCHIVE_TERMS)


def _requires_strict_auth(item: Any, brand: str) -> bool:
    """Require strict auth for high-counterfeit brands."""
    return brand in STRICT_AUTH_BRANDS


TIER_HIERARCHY = ["beginner", "pro", "whale"]


def _nested_tiers(minimum_tier: str) -> List[str]:
    """Return all tiers that should receive a deal at the given tier level.

    Nested entitlement: a beginner deal goes to all channels (beginner, pro,
    whale).  A pro deal goes to pro + whale.  A whale deal goes to whale only.
    """
    try:
        idx = TIER_HIERARCHY.index(minimum_tier)
    except ValueError:
        idx = 0
    return TIER_HIERARCHY[idx:]


def classify_discord_tiers(
    item: Any,
    profit: float,
    margin: float,
    signals: Any = None,
    auth_result: Any = None,
) -> TierDecision:
    """Classify a deal into a minimum tier and expand to nested entitlement channels.

    Nested entitlement routing — higher-tier subscribers see everything at or
    below their tier:
      beginner deal → [beginner, pro, whale]
      pro deal      → [pro, whale]
      whale deal    → [whale]

    Tier structure (by brand exclusivity):
    - Beginner: 10 core brands (CH, RO, Margiela, Prada, Balenciaga, BV, JPG, HL, Issey, DRKSHDW)
    - Pro:      30+ additional brands (ERD, Undercover, Kapital, Raf, SLP, Dior, etc.)
    - Whale:    Exclusive brands (CCP, Number Nine, BBS, Hysteric, Brunello) + Japan deals
    """
    brand = _brand(item)
    source = (getattr(item, "source", "") or "").lower()
    is_japan = source in {"japan_buyee", "rakuma", "mercari_jp", "yahoo_auctions_jp", "buyee"}

    reasons = []

    # ── Japan deals are whale-exclusive ──
    if is_japan:
        reasons.append("Japan cross-border (whale-exclusive)")
        return TierDecision(minimum_tier="whale", channel_tiers=["whale"], reasons=reasons)

    # ── Determine minimum tier by brand exclusivity ──
    whale_only_brands = BIG_BALLER_BRANDS - PRO_BRANDS
    pro_only_brands = PRO_BRANDS - BEGINNER_BRANDS

    if brand in whale_only_brands:
        tier = "whale"
        reasons.append(f"whale-exclusive brand: {brand}")
    elif brand in pro_only_brands:
        tier = "pro"
        reasons.append(f"pro-tier brand: {brand}")
    elif brand in BEGINNER_BRANDS:
        tier = "beginner"
        reasons.append(f"beginner brand: {brand}")
    else:
        tier = "beginner"
        reasons.append(f"unrecognized brand '{brand}' → beginner fallback")

    # Exclusive routing: each deal posts to its single tier channel only.
    # Discord permissions handle visibility (whale sees all channels,
    # pro sees pro+beginner, beginner sees beginner only).
    channels = [tier]
    reasons.append(f"exclusive routing → #{tier}-signals")
    return TierDecision(minimum_tier=tier, channel_tiers=channels, reasons=reasons)
