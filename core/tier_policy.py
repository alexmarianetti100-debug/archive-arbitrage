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
            "undercover", "kapital", "visvim",
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
            "undercover", "kapital", "visvim",
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
    """Classify a deal into exactly ONE Discord channel tier (exclusive routing).

    Checks from highest → lowest. First match wins.
    Deals that don't qualify for any tier default to beginner.

    Returns TierDecision with exactly one entry in channel_tiers.
    """
    big = RULES["big_baller"]
    pro = RULES["pro"]

    brand = _brand(item)
    price = float(getattr(item, "price", 0) or 0)
    liquidity = float(getattr(signals, "liquidity_score", 0) or 0)
    auth_conf = float(getattr(auth_result, "confidence", 0.0) or 0.0) if auth_result else 0.0

    # ── Whale (formerly big_baller) ──
    whale_floor = (
        profit >= big.get("min_profit", 500)
        and margin >= big.get("min_margin", 0.20)
        and liquidity >= big.get("min_liquidity", 5.0)
        and price >= big.get("min_price", 1500)
        and brand in BIG_BALLER_BRANDS
    )
    if whale_floor:
        return TierDecision(
            minimum_tier="whale",
            channel_tiers=["whale"],
            reasons=["whale-tier metrics", f"${profit:.0f} profit", f"{margin*100:.0f}% margin"],
        )

    # ── Pro ──
    pro_floor = (
        profit >= pro.get("min_profit", 300)
        and margin >= pro.get("min_margin", 0.25)
        and liquidity >= pro.get("min_liquidity", 5.5)
        and price < pro.get("max_price", 10000)
        and brand in PRO_BRANDS
    )
    if pro_floor:
        return TierDecision(
            minimum_tier="pro",
            channel_tiers=["pro"],
            reasons=["pro-tier metrics", f"${profit:.0f} profit", f"{margin*100:.0f}% margin"],
        )

    # ── Beginner (default) ──
    return TierDecision(
        minimum_tier="beginner",
        channel_tiers=["beginner"],
        reasons=["default beginner"],
    )
