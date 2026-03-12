from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, List


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "tier_rules.json"


DEFAULT_RULES = {
    "beginner": {
        "min_profit": 150,
        "min_margin": 0.30,
        "min_liquidity": 8.0,
        "max_price": 2500,
        "brands": [
            "chrome hearts", "louis vuitton", "tiffany & co", "tiffany", "prada",
            "rick owens", "maison margiela", "margiela",
        ],
        "routing": ["beginner", "pro", "big_baller"],
    },
    "pro": {
        "min_profit": 300,
        "min_margin": 0.25,
        "min_liquidity": 6.5,
        "max_price": 10000,
        "min_auth": 0.72,
        "strict_auth_min": 0.82,
        "brands": [
            "chrome hearts", "louis vuitton", "tiffany & co", "tiffany", "prada",
            "rick owens", "maison margiela", "margiela", "rolex", "omega", "tudor",
            "cartier", "van cleef & arpels", "vca", "chanel", "hermès", "hermes",
            "celine", "bottega veneta", "saint laurent", "yves saint laurent",
        ],
        "routing": ["pro", "big_baller"],
    },
    "big_baller": {
        "min_profit": 500,
        "min_margin": 0.20,
        "min_liquidity": 5.0,
        "min_price": 5000,
        "min_auth": 0.80,
        "brands": [
            "chrome hearts", "louis vuitton", "tiffany & co", "tiffany", "prada",
            "rick owens", "maison margiela", "margiela", "rolex", "omega", "tudor",
            "cartier", "van cleef & arpels", "vca", "chanel", "hermès", "hermes",
            "celine", "bottega veneta", "saint laurent", "yves saint laurent",
            "patek philippe", "audemars piguet", "vacheron constantin",
            "carol christian poell", "ccp", "number nine", "number (n)ine",
            "raf simons", "helmut lang",
        ],
        "routing": ["big_baller"],
    },
    "strict_auth_brands": [
        "rolex", "omega", "tudor", "cartier", "van cleef & arpels", "vca", "chanel",
        "hermès", "hermes", "patek philippe", "audemars piguet", "vacheron constantin",
    ],
    "terms": {
        "watch": ["watch", "datejust", "daytona", "submariner", "gmt", "gmt master", "explorer", "speedmaster", "seamaster", "black bay", "pelagos", "tank", "santos", "nautilus", "aquanaut", "royal oak", "overseas", "patrimony", "calatrava"],
        "bag": ["bag", "handbag", "purse", "wallet on chain", "woc", "speedy", "neverfull", "pochette", "metis", "evelyne", "picotin", "garden party", "triomphe", "cassette", "jodie", "birkin", "kelly", "constance", "re-edition", "flap"],
        "jewelry": ["ring", "bracelet", "necklace", "pendant", "chain", "cross", "dagger", "alhambra", "love bracelet", "juste un clou", "keys", "hardware", "paper chain"],
        "shoe": ["geobasket", "replica", "gat", "sneaker", "sneakers", "boots", "boot", "tabi", "wyatt", "dunks", "america's cup", "america’s cup"],
        "archive": ["archive", "vintage", "raf simons", "helmut lang", "rick owens", "number nine", "ccp", "carol christian poell"]
    }
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

WATCH_TERMS = set(TERMS.get("watch", []))
BAG_TERMS = set(TERMS.get("bag", []))
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


def _is_watch(item: Any) -> bool:
    return _has_any(_title(item), WATCH_TERMS)


def _is_bag(item: Any) -> bool:
    return _has_any(_title(item), BAG_TERMS)


def _is_jewelry(item: Any) -> bool:
    return _has_any(_title(item), JEWELRY_TERMS)


def _is_shoe(item: Any) -> bool:
    return _has_any(_title(item), SHOE_TERMS)


def _is_archive(item: Any) -> bool:
    return _has_any(_title(item), ARCHIVE_TERMS)


def _requires_strict_auth(item: Any, brand: str) -> bool:
    return brand in STRICT_AUTH_BRANDS or _is_watch(item)


def classify_discord_tiers(
    item: Any,
    profit: float,
    margin: float,
    signals: Any = None,
    auth_result: Any = None,
) -> TierDecision:
    beginner = RULES["beginner"]
    pro = RULES["pro"]
    big = RULES["big_baller"]

    brand = _brand(item)
    price = float(getattr(item, "price", 0) or 0)
    liquidity = float(getattr(signals, "liquidity_score", 0) or 0)
    auth_conf = float(getattr(auth_result, "confidence", 0.0) or 0.0) if auth_result else 0.0
    strict_auth_required = _requires_strict_auth(item, brand)

    beginner_floor = (
        profit >= beginner.get("min_profit", 150)
        and margin >= beginner.get("min_margin", 0.30)
        and liquidity >= beginner.get("min_liquidity", 8.0)
        and price <= beginner.get("max_price", 2500)
    )
    pro_floor = (
        profit >= pro.get("min_profit", 300)
        and margin >= pro.get("min_margin", 0.25)
        and liquidity >= pro.get("min_liquidity", 6.5)
        and price < pro.get("max_price", 10000)
    )
    big_floor = (
        profit >= big.get("min_profit", 500)
        and margin >= big.get("min_margin", 0.20)
        and liquidity >= big.get("min_liquidity", 5.0)
        and price >= big.get("min_price", 5000)
    )

    if big_floor and brand in BIG_BALLER_BRANDS and (_is_watch(item) or _is_bag(item) or _is_archive(item)) and auth_conf >= big.get("min_auth", 0.80):
        return TierDecision(
            minimum_tier="big_baller",
            channel_tiers=list(big.get("routing", ["big_baller"])),
            reasons=["high-ticket", "strong auth", "big baller category", "tier-specific liquidity floor"],
        )

    if beginner_floor and brand in BEGINNER_BRANDS and (
        (brand == "chrome hearts" and _is_jewelry(item)) or
        (brand in {"tiffany", "tiffany & co"} and _is_jewelry(item)) or
        (brand == "louis vuitton" and _is_bag(item)) or
        (brand == "prada" and (_is_bag(item) or _is_shoe(item))) or
        (brand == "rick owens" and _is_shoe(item)) or
        (brand in {"maison margiela", "margiela"} and _is_shoe(item))
    ) and not strict_auth_required:
        return TierDecision(
            minimum_tier="beginner",
            channel_tiers=list(beginner.get("routing", ["beginner", "pro", "big_baller"])),
            reasons=["beginner-safe category", "high liquidity", "nested routing"],
        )

    pro_auth_floor = pro.get("strict_auth_min", 0.82) if strict_auth_required else pro.get("min_auth", 0.72)
    if pro_floor and brand in PRO_BRANDS and (_is_watch(item) or _is_jewelry(item) or _is_bag(item) or _is_archive(item)) and auth_conf >= pro_auth_floor:
        reasons = ["pro category", "nested routing", "tier-specific liquidity floor"]
        reasons.append("strict auth category" if strict_auth_required else "standard auth threshold")
        return TierDecision(
            minimum_tier="pro",
            channel_tiers=list(pro.get("routing", ["pro", "big_baller"])),
            reasons=reasons,
        )

    if big_floor and auth_conf >= big.get("min_auth", 0.80):
        return TierDecision("big_baller", list(big.get("routing", ["big_baller"])), ["threshold fallback", "high-ticket"])
    if pro_floor and auth_conf >= pro_auth_floor:
        return TierDecision("pro", list(pro.get("routing", ["pro", "big_baller"])), ["threshold fallback"])
    if beginner_floor:
        return TierDecision("beginner", list(beginner.get("routing", ["beginner", "pro", "big_baller"])), ["threshold fallback"])

    return TierDecision(None, [], ["no tier match"])
