"""Helpers for canonicalizing and prioritizing query families."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("query_normalization")

from core.target_families import alias_to_canonical_map, family_id_map, family_policy_map

# Known malformed / duplicate query variants discovered in telemetry review.
QUERY_ALIASES: dict[str, str] = {
    **alias_to_canonical_map(),
    "helmut lang": "helmut lang",
    "Helmut Lang": "helmut lang",
    "jean paul gaultier": "jean paul gaultier",
    "Jean Paul Gaultier": "jean paul gaultier",
    "junya watanabe": "junya watanabe",
    "Junya Watanabe": "junya watanabe",
    "bottega veneta orbit sneakers": "bottega veneta orbit sneaker",
    "chrome hearts paperchain": "chrome hearts paper chain",
    "prada americas cup": "prada america's cup sneakers",
    "prada america's cup": "prada america's cup sneakers",
    # Curly quote variants that don't map through target_families
    "balenciaga 2000\u2019s classic city": "demoted_junk",
}

PROMOTED_LIQUIDITY_QUERIES: set[str] = {
    "chrome hearts cross pendant",
    "chrome hearts baby fat pendant",
    "chrome hearts paper chain",
    "chrome hearts tee",
    "chrome hearts neck logo long",
    "chrome hearts vagilante glasses",
    "chrome hearts trypoleagain glasses",
    "chrome hearts see you tea",
    "saint laurent wyatt boots",
    "saint laurent paris oil",
    "maison margiela gat",
    "maison margiela gat low",
    "prada america's cup sneakers",
    "dior homme luster denim",
    "dior homme jeans",
    "rick owens memphis",
    "rick owens creatch cargo",
    "rick owens grained leather sneakers",
    "bottega veneta intrecciato leather briefcase",
    "bottega veneta orbit sneaker",
    "undercover arts and crafts",
    "undercover bug denim",
    "raf simons sterling ruby",
    # High-volume sellers from sales data analysis
    "rick owens cargo",
    "kapital century denim",
}

DEMOTED_QUERY_FAMILIES: set[str] = {
    "maison margiela tabi",
    "rick owens leather jacket",
    "chrome hearts cemetery cross",
    "chrome hearts hoodie",
    "chrome hearts dagger pendant",
    "balenciaga defender",
    "rick owens ramones",
    "chrome hearts floral cross",
    "prada linea rossa",
    "saint laurent court classic",
    "rick owens bauhaus cargo",
    "rick owens ramones low",
    "prada sneakers",
    "prada cloudbust",
    "chrome hearts trucker hat",
    # 100% junk queries (demoted via performance data analysis)
    "balenciaga 2000s classic city",
    "balenciaga 2000's classic city",
    "balenciaga 2000's classic city",
    "balenciaga leather jacket",
    "balenciaga track",
    "balenciaga triple s",
    "saint laurent leather jacket",
    "saint laurent yves yves rive",
    "saint laurent paris paris d02",
    "saint laurent paris paris leather",
    "saint laurent yves ysl jacket",
    "saint laurent l01 leather jacket",
    "rick owens beatle bozo tractor",
    "rick owens cargo pants",
    "rick owens stooges leather jacket",
    "rick owens intarsia",
    "rick owens ramones high",
    "rick owens kiss boots",
    "helmut lang denim jacket",
    "vivienne westwood orb necklace",
    "undercover but beautiful",
    "undercover scab",
    "prada lace-up leather boots",
    "prada bomber jacket",
    "prada gabardine",
    "prada nylon bomber",
    "prada denim jacket",
    "chrome hearts ch logo hat",
    "chrome hearts zip up hoodie",
    "chrome hearts cross ring",
    "chrome hearts cox ucker",
    "dior homme leather jacket",
    "maison margiela gentle monster gentle",
    "raf simons knit sweater",
    "junya watanabe supreme cdg man",
    "alexander mcqueen skull scarf",
    "boris bidjan saberi leather",
    "number (n)ine jam home made",
    "balenciaga track sneaker",
    "rick owens dr. martens",
}

BROAD_FAMILY_UMBRELLAS: set[str] = {
    "rick owens",
    "chrome hearts",
    "saint laurent",
    "maison margiela",
    "jean paul gaultier",
    "helmut lang",
    "raf simons",
    "dior homme",
    "number nine",
    "bottega veneta",
}

BROAD_TRAILING_CATEGORIES: set[str] = {
    "jacket", "hoodie", "coat", "boots", "sneakers", "pants", "ring",
    "bag", "accessories", "hat", "tee", "shirt", "bracelet", "necklace",
}

FAMILY_IDS = family_id_map()
FAMILY_POLICIES = family_policy_map()


def normalize_query(query: str) -> str:
    if not query:
        return ""
    cleaned = re.sub(r"\s+", " ", query).strip()
    return QUERY_ALIASES.get(cleaned, QUERY_ALIASES.get(cleaned.lower(), cleaned.lower()))


def family_id_for_query(query: str) -> str:
    q = normalize_query(query)
    return FAMILY_IDS.get(q, q)


def family_policy_for_query(query: str) -> dict | None:
    q = normalize_query(query)
    return FAMILY_POLICIES.get(q)


def is_allowed_family_query(query: str) -> bool:
    q = normalize_query(query)
    policy = FAMILY_POLICIES.get(q)
    if not policy:
        return True
    if q in policy.get("demoted_queries", set()):
        return False
    allowed = policy.get("allowed_queries", set())
    if allowed:
        return q in allowed
    return False


def is_promoted_query(query: str) -> bool:
    return normalize_query(query) in PROMOTED_LIQUIDITY_QUERIES


def is_demoted_query(query: str) -> bool:
    normalized = normalize_query(query)
    # Check if explicitly demoted or mapped to demoted_junk family
    return normalized in DEMOTED_QUERY_FAMILIES or normalized == "demoted_junk"


def is_broad_query(query: str) -> bool:
    q = normalize_query(query)
    words = q.split()
    if q in BROAD_FAMILY_UMBRELLAS:
        return True
    if len(words) <= 2:
        return True
    if words[-1] in BROAD_TRAILING_CATEGORIES and len(words) <= 3:
        return True
    return False


def promoted_query_multiplier(query: str) -> float:
    q = normalize_query(query)
    if q in PROMOTED_LIQUIDITY_QUERIES:
        if q in DEMOTED_QUERY_FAMILIES:
            logger.warning("query %r is in BOTH promoted and demoted lists — treating as demoted", q)
            return 0.35
        return 1.35
    if q in DEMOTED_QUERY_FAMILIES:
        return 0.35
    return 1.0
