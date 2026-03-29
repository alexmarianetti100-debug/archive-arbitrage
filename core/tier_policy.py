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
        "routing": ["beginner"],
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
        "routing": ["pro"],
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


def classify_discord_tiers(
    item: Any,
    profit: float,
    margin: float,
    signals: Any = None,
    auth_result: Any = None,
) -> TierDecision:
    """Classify a deal into Discord channel tiers using brand-access routing.

    Whop tier structure (each tier includes everything below it):
    - Beginner ($30): 10 core brands, items up to $2,500
    - Pro ($80):      40+ brands, items up to $10,000, 72%+ auth
    - Whale ($400):   50+ brands, no price ceiling, 80%+ auth, Japan deals

    Routing logic — brand exclusivity determines the MINIMUM tier:
    1. Brand only in whale set → whale channel (CCP, Number Nine, BBS, etc.)
    2. Brand only in pro set → pro channel (ERD, Undercover, Kapital, Raf, etc.)
    3. Brand in beginner set → beginner channel
    4. High profit ($300+) on beginner brand → ALSO goes to pro
    5. Monster profit ($500+) on any brand → ALSO goes to whale
    6. Japan source deals → always whale (Japan is whale-exclusive feature)

    Returns TierDecision with channel_tiers list for multi-channel posting.
    """
    brand = _brand(item)
    price = float(getattr(item, "price", 0) or 0)
    source = (getattr(item, "source", "") or "").lower()
    auth_conf = float(getattr(auth_result, "confidence", 0.0) or 0.0) if auth_result else 0.0
    is_japan = source in {"japan_buyee", "rakuma", "mercari_jp", "yahoo_auctions_jp", "buyee"}

    channels = []
    reasons = []

    # ── Japan deals are whale-exclusive ──
    if is_japan:
        channels.append("whale")
        reasons.append("Japan cross-border (whale-exclusive)")
        return TierDecision(minimum_tier="whale", channel_tiers=channels, reasons=reasons)

    # ── Determine minimum tier by brand exclusivity ──
    # Whale-only brands: brands in whale set but NOT in pro set
    whale_only_brands = BIG_BALLER_BRANDS - PRO_BRANDS
    # Pro-only brands: brands in pro set but NOT in beginner set
    pro_only_brands = PRO_BRANDS - BEGINNER_BRANDS

    if brand in whale_only_brands:
        # CCP, Number Nine, BBS, Hysteric — whale-exclusive brands
        channels.append("whale")
        reasons.append(f"whale-exclusive brand: {brand}")
    elif brand in pro_only_brands:
        # ERD, Undercover, Kapital, Raf, SLP, Dior, etc. — pro-tier brands
        channels.append("pro")
        reasons.append(f"pro-tier brand: {brand}")
    elif brand in BEGINNER_BRANDS:
        # CH, RO, Margiela, Prada, Balenciaga, BV, JPG, Helmut — core brands
        channels.append("beginner")
        reasons.append(f"beginner brand: {brand}")
    else:
        # Unknown brand — route to beginner as default
        channels.append("beginner")
        reasons.append("default fallback")

    # ── Profit-based upgrades (high profit promotes to higher tiers too) ──
    if profit >= 500 and "whale" not in channels:
        channels.append("whale")
        reasons.append(f"${profit:.0f} profit → whale upgrade")
    if profit >= 300 and "pro" not in channels:
        channels.append("pro")
        reasons.append(f"${profit:.0f} profit → pro upgrade")

    # Determine minimum tier from highest channel
    if "whale" in channels:
        min_tier = "whale"
    elif "pro" in channels:
        min_tier = "pro"
    else:
        min_tier = "beginner"

    return TierDecision(minimum_tier=min_tier, channel_tiers=channels, reasons=reasons)
