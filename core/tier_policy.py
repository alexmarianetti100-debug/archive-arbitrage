from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class TierDecision:
    minimum_tier: str | None
    channel_tiers: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


BEGINNER_BRANDS = {
    "chrome hearts", "louis vuitton", "tiffany & co", "tiffany", "prada",
    "rick owens", "maison margiela", "margiela",
}

PRO_BRANDS = BEGINNER_BRANDS | {
    "rolex", "omega", "tudor", "cartier", "van cleef & arpels", "vca",
    "chanel", "hermès", "hermes", "celine", "bottega veneta", "saint laurent",
}

BIG_BALLER_BRANDS = PRO_BRANDS | {
    "patek philippe", "audemars piguet", "vacheron constantin",
    "carol christian poell", "ccp", "number nine", "number (n)ine",
    "raf simons", "helmut lang",
}

WATCH_TERMS = {"watch", "datejust", "daytona", "submariner", "gmt", "explorer", "speedmaster", "seamaster", "black bay", "pelagos", "tank", "santos", "nautilus", "aquanaut", "royal oak", "overseas"}
BAG_TERMS = {"bag", "handbag", "purse", "wallet on chain", "woc", "speedy", "neverfull", "pochette", "metis", "evelyne", "picotin", "garden party", "triomphe", "cassette", "jodie", "birkin", "kelly", "constance", "re-edition"}
JEWELRY_TERMS = {"ring", "bracelet", "necklace", "pendant", "chain", "cross", "dagger", "alhambra", "love bracelet", "juste un clou", "keys", "hardware"}
SHOE_TERMS = {"geobasket", "replica", "gat", "sneaker", "sneakers", "boots", "boot", "tabi", "wyatt", "dunks"}
ARCHIVE_TERMS = {"archive", "vintage", "raf simons", "helmut lang", "rick owens", "number nine", "ccp", "carol christian poell"}


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


def classify_discord_tiers(
    item: Any,
    profit: float,
    margin: float,
    signals: Any = None,
    auth_result: Any = None,
) -> TierDecision:
    title = _title(item)
    brand = _brand(item)
    price = float(getattr(item, "price", 0) or 0)
    liquidity = float(getattr(signals, "liquidity_score", 0) or 0)
    auth_conf = float(getattr(auth_result, "confidence", 0.0) or 0.0) if auth_result else 0.0

    beginner_floor = profit >= 150 and margin >= 0.30 and liquidity >= 8
    pro_floor = profit >= 300 and margin >= 0.25 and price < 10000
    big_floor = profit >= 500 and margin >= 0.20 and price >= 5000

    if big_floor and brand in BIG_BALLER_BRANDS and (
        _is_watch(item) or _is_bag(item) or _is_archive(item)
    ) and auth_conf >= 0.80:
        return TierDecision(
            minimum_tier="big_baller",
            channel_tiers=["big_baller"],
            reasons=["high-ticket", "strong auth", "big baller category"],
        )

    if beginner_floor and brand in BEGINNER_BRANDS and (
        (brand == "chrome hearts" and _is_jewelry(item)) or
        (brand in {"tiffany", "tiffany & co"} and _is_jewelry(item)) or
        (brand == "louis vuitton" and _is_bag(item)) or
        (brand == "prada" and (_is_bag(item) or _is_shoe(item))) or
        (brand == "rick owens" and _is_shoe(item)) or
        (brand in {"maison margiela", "margiela"} and _is_shoe(item))
    ):
        return TierDecision(
            minimum_tier="beginner",
            channel_tiers=["beginner", "pro", "big_baller"],
            reasons=["beginner-safe category", "high liquidity", "nested routing"],
        )

    if pro_floor and brand in PRO_BRANDS and (
        _is_watch(item) or _is_jewelry(item) or _is_bag(item) or _is_archive(item)
    ) and auth_conf >= 0.72:
        return TierDecision(
            minimum_tier="pro",
            channel_tiers=["pro", "big_baller"],
            reasons=["pro category", "auth-eligible", "nested routing"],
        )

    # Fallback to threshold-only routing for simple cases so we don't drop obvious wins.
    if big_floor:
        return TierDecision("big_baller", ["big_baller"], ["threshold fallback"])
    if pro_floor:
        return TierDecision("pro", ["pro", "big_baller"], ["threshold fallback"])
    if beginner_floor:
        return TierDecision("beginner", ["beginner", "pro", "big_baller"], ["threshold fallback"])

    return TierDecision(None, [], ["no tier match"])
