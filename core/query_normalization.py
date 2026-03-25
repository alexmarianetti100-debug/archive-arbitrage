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
    "junya watanabe": "demoted_junk",
    "Junya Watanabe": "demoted_junk",
    "yohji yamamoto": "demoted_junk",
    "Yohji Yamamoto": "demoted_junk",
    "van cleef": "demoted_junk",
    "Van Cleef": "demoted_junk",
    "tiffany": "demoted_junk",
    "Tiffany": "demoted_junk",
    "hermes": "demoted_junk",
    "Hermes": "demoted_junk",
    "issey miyake": "demoted_junk",
    "Issey Miyake": "demoted_junk",
    "cartier": "demoted_junk",
    "Cartier": "demoted_junk",
    "bvlgari": "demoted_junk",
    "Bvlgari": "demoted_junk",
    # ERD piece-specific quirky aliases (structural aliases handled by target_families)
    "erd benny's video": "enfants riches deprimes bennys video hoodie",
    "erd safety pin": "enfants riches deprimes safety pin earring",
    "erd rose buckle": "enfants riches deprimes rose buckle belt",
    "erd menendez": "enfants riches deprimes menendez hoodie",
    "bottega veneta orbit sneakers": "bottega veneta orbit sneaker",
    "adidas raf simons ozweego": "raf simons ozweego",
    "raf simons ozweego": "raf simons ozweego",
    "chrome hearts paperchain": "chrome hearts paper chain",
    "prada americas cup": "prada america's cup sneakers",
    "prada america's cup": "prada america's cup sneakers",
    # Curly quote variants that don't map through target_families
    "balenciaga 2000\u2019s classic city": "demoted_junk",
}

PROMOTED_LIQUIDITY_QUERIES: set[str] = {
    # Chrome Hearts jewelry — most liquid segment
    "chrome hearts cross pendant",
    "chrome hearts baby fat pendant",
    "chrome hearts paper chain",
    "chrome hearts dagger pendant",
    "chrome hearts floral cross",
    "chrome hearts cross ring",
    "chrome hearts fuck you ring",
    "chrome hearts spinner ring",
    "chrome hearts keeper ring",
    "chrome hearts horseshoe ring",
    "chrome hearts morning star bracelet",
    # Chrome Hearts apparel
    "chrome hearts tee",
    "chrome hearts neck logo long",
    "chrome hearts hoodie",
    "chrome hearts zip up hoodie",
    "chrome hearts shorts",
    "chrome hearts thermal",
    "chrome hearts track pants",
    "chrome hearts sweatpants",
    # Chrome Hearts denim/outerwear
    "chrome hearts cross patch jeans",
    "chrome hearts cross patch flannel",
    "chrome hearts trucker jacket",
    "chrome hearts denim jacket",
    # Chrome Hearts graphics
    "chrome hearts deadly doll",
    "chrome hearts deadly doll tank",
    "chrome hearts matty boy",
    "chrome hearts matty boy hoodie",
    "chrome hearts matty boy tee",
    "chrome hearts leather cross patch",
    # Chrome Hearts eyewear
    "chrome hearts sunglasses",
    "chrome hearts trypoleagain glasses",
    "chrome hearts see you tea",
    # Saint Laurent
    "saint laurent wyatt boots",
    "saint laurent paris oil",
    # Margiela
    "maison margiela gat",
    "maison margiela gat low",
    "maison margiela tabi boots",
    # Prada
    "prada america's cup sneakers",
    # Dior Homme archive
    "dior homme luster denim",
    "dior homme jeans",
    "dior homme navigate bomber",
    "dior homme waxed jeans",
    "dior homme navigate",
    "dior homme fw03",
    "dior homme fw07",
    "dior homme kris van assche",
    "dior homme boots",
    # Rick Owens
    "rick owens memphis",
    "rick owens creatch cargo",
    "rick owens grained leather sneakers",
    "rick owens geobasket",
    "rick owens stooges",
    "rick owens cargo",
    "rick owens stooges leather jacket",
    "rick owens biker jacket",
    "rick owens champion",
    "rick owens drkshdw jumbo lace",
    "rick owens kiss boots",
    "rick owens denim jacket",
    "rick owens island dunk",
    # Jean Paul Gaultier
    "jean paul gaultier mesh top",
    "jean paul gaultier corset",
    "jean paul gaultier cyberbaba",
    "jean paul gaultier maille",
    "jean paul gaultier tattoo",
    "jean paul gaultier leather jacket",
    "jean paul gaultier leather pants",
    "jean paul gaultier jacket",
    "jean paul gaultier boots",
    # Enfants Riches Deprimes
    "enfants riches deprimes hoodie",
    "enfants riches deprimes tee",
    "enfants riches deprimes long sleeve",
    "enfants riches deprimes leather jacket",
    "enfants riches deprimes denim jacket",
    "enfants riches deprimes jeans",
    "enfants riches deprimes hat",
    "enfants riches deprimes belt",
    "enfants riches deprimes sweater",
    "enfants riches deprimes flannel",
    "enfants riches deprimes bomber",
    # ERD piece-specific (proven liquid, March 2026 research)
    "enfants riches deprimes classic logo hoodie",
    "enfants riches deprimes classic logo tee",
    "enfants riches deprimes safety pin earring",
    "enfants riches deprimes classic logo long sleeve",
    "enfants riches deprimes bennys video hoodie",
    "enfants riches deprimes menendez hoodie",
    "enfants riches deprimes viper room hat",
    "enfants riches deprimes teenage snuff tee",
    "enfants riches deprimes flowers of anger",
    "enfants riches deprimes bohemian scum tee",
    "enfants riches deprimes god with revolver",
    "enfants riches deprimes spanish elegy jacket",
    "enfants riches deprimes menendez pants",
    "enfants riches deprimes rose buckle belt",
    "enfants riches deprimes frozen beauties flannel",
    "enfants riches deprimes le rosey tee",
    # Balenciaga (proven performers)
    "balenciaga runner",
    "balenciaga lost tape flared",
    "balenciaga arena",
    "balenciaga hummer boots",
    "balenciaga lamborghini zip-up hoodie",
    "balenciaga skater sweatpants",
    "balenciaga arena high top",
    "balenciaga speedhunters",
    "balenciaga political campaign",
    "balenciaga destroyed hoodie",
    "balenciaga leather biker",
    # Raf Simons archive
    "raf simons sterling ruby",
    "raf simons peter saville",
    "raf simons consumed",
    "raf simons virginia creeper",
    "raf simons bomber jacket",
    "raf simons riot riot riot",
    "raf simons nebraska",
    "raf simons parka",
    "raf simons 2002",
    "raf simons 2001",
    "raf simons jacket",
    "raf simons fishtail parka",
    "raf simons power corruption lies",
    # Undercover archive
    "undercover arts and crafts",
    "undercover bug denim",
    "undercover scab",
    "undercover but beautiful",
    "undercover 85 bomber",
    "undercover bones",
    "undercover denim jacket",
    # Celine (Hedi era)
    "celine sneakers",
    "celine leather jacket",
    "celine teddy jacket",
    "celine boots",
    "celine western boots",
    "celine varsity jacket",
    "celine denim jacket",
    "celine bomber jacket",
    "celine triomphe belt",
    # Haider Ackermann
    "haider ackermann leather jacket",
    "haider ackermann blazer",
    "haider ackermann velvet blazer",
    "haider ackermann silk bomber",
    "haider ackermann coat",
    # Dries Van Noten
    "dries van noten embroidered jacket",
    "dries van noten velvet blazer",
    "dries van noten floral jacket",
    "dries van noten coat",
    "dries van noten leather jacket",
    # Sacai
    "sacai leather jacket",
    "sacai bomber jacket",
    "sacai blazer",
    "sacai deconstructed jacket",
    # Margiela artisanal
    "margiela artisanal",
    "margiela duvet coat",
    "margiela white label jacket",
    "margiela deconstructed",
    # Guidi
    "guidi boots",
    "guidi back zip boots",
    "guidi horse leather",
    "guidi 988",
    "guidi 995",
    "guidi 986",
    # Lemaire
    "lemaire jacket",
    "lemaire coat",
    "lemaire leather jacket",
    "lemaire twisted shirt",
    "lemaire boots",
    # Acne Studios
    "acne studios leather jacket",
    "acne studios velocite jacket",
    "acne studios shearling",
    # Simone Rocha
    "simone rocha pearl",
    "simone rocha embellished",
    "simone rocha dress",
    # Brunello Cucinelli
    "brunello cucinelli cashmere jacket",
    "brunello cucinelli leather jacket",
    "brunello cucinelli cashmere sweater",
    # The Soloist
    "soloist jacket",
    "soloist leather jacket",
    "takahiromiyashita soloist",
    # Raf Simons footwear (reformulated)
    "raf simons ozweego",
    "raf simons response trail",
    "raf simons detroit runner",
    # Helmut Lang (reformulated)
    "helmut lang 1998",
    "helmut lang 1999",
    "helmut lang bondage strap",
    "helmut lang reflective",
    "helmut lang raw denim",
    # Number Nine
    "number nine cargo pants",
    "number nine denim",
    "number nine hoodie",
    # Julius
    "julius leather jacket",
    "julius gas mask hoodie",
    "julius boots",
    "julius coat",
    # Kapital (telemetry-proven)
    "kapital boro jacket",
    "kapital denim jacket",
    "kapital kountry coat",
    # Thierry Mugler
    "thierry mugler leather jacket",
    "thierry mugler blazer",
    "thierry mugler dress",
    # CCP (100% deal rate)
    "carol christian poell leather jacket",
    "carol christian poell coat",
    "carol christian poell drip rubber",
    # Vivienne Westwood jewelry
    "vivienne westwood orb necklace",
    "vivienne westwood armor ring",
    "vivienne westwood corset",
    "vivienne westwood pearl necklace",
    # Ann Demeulemeester
    "ann demeulemeester leather jacket",
    "ann demeulemeester leather boots",
    "ann demeulemeester lace up boots",
    # Bottega Veneta (telemetry-proven)
    "bottega veneta orbit sneaker",
    "bottega veneta haddock leather boots",
    "bottega veneta chelsea boots",
    "bottega veneta tire boots",
    "bottega veneta leather jacket",
    # Alexander McQueen
    "alexander mcqueen leather jacket",
    "alexander mcqueen skull ring",
    "alexander mcqueen blazer",
    # Prada (telemetry-proven)
    "prada re-nylon",
    "prada cotton velvet blouson",
    # Celine (telemetry)
    "celine paris ribbed long",
    # Chrome Hearts (telemetry-proven eyewear/clothing)
    "chrome hearts pony hair triple",
    "chrome hearts paper jam triple",
    "chrome hearts gittin any frame",
    "chrome hearts glitter friends family",
    "chrome hearts vagilante glasses",
    "chrome hearts sneakers",
    "chrome hearts boots",
    "chrome hearts tiny ring",
    "chrome hearts cross patch hat",
    "chrome hearts baby rib tank",
    # Boris Bidjan Saberi
    "boris bidjan saberi jacket",
    # Hysteric Glamour
    "hysteric glamour leather jacket",
    "hysteric glamour denim jacket",
    "hysteric glamour jeans",
    "hysteric glamour tee",
    "hysteric glamour kurt cobain",
    # Chrome Hearts accessories
    "chrome hearts belt",
    "chrome hearts diamond",
    "chrome hearts cemetery cross",
    # Louis Vuitton (strict auth)
    "louis vuitton murakami",
    "louis vuitton trainer",
    # Chanel (strict auth)
    "balenciaga paris sneaker",
    "balenciaga demna archive",
    # Prada footwear
    "prada chocolate loafers",
    "prada leather loafers",
    # Margiela footwear
    "maison margiela tabi loafers",
    "maison margiela future",
    # Saint Laurent footwear
    "saint laurent leather boots",
    # Rick Owens season-specific
    "rick owens fogachine",
    "rick owens tecuatl",
    "rick owens dustulator",
    "rick owens tractor boots",
    # Dior Homme deep archive
    "dior homme fw03 leather",
    "dior homme jewelry hedi slimane",
    # Raf Simons archive
    "raf simons kollaps",
    # Helmut Lang
    "helmut lang painter jeans",
    # Kapital
    "kapital boro",
    "kapital century denim",
    # Number Nine
    "number nine skull",
    # Undercover
    "undercover twin peaks",
}

DEMOTED_QUERY_FAMILIES: set[str] = {
    # Genuinely low-margin / trap queries
    "maison margiela tabi",
    "balenciaga defender",
    "prada linea rossa",
    "saint laurent court classic",
    "prada sneakers",
    "prada cloudbust",
    # Confirmed junk queries (0 deals, many runs, no margin potential)
    "balenciaga 2000s classic city",
    "balenciaga 2000's classic city",
    "balenciaga 2000's classic city",
    "balenciaga track",
    "balenciaga triple s",
    "balenciaga track sneaker",
    "saint laurent yves yves rive",
    "saint laurent paris paris d02",
    "saint laurent paris paris leather",
    "saint laurent yves ysl jacket",
    "saint laurent l01 leather jacket",
    "rick owens beatle bozo tractor",
    "rick owens cargo pants",
    "rick owens ramones low",
    "rick owens ramones high",
    "rick owens bauhaus cargo",
    "prada lace-up leather boots",
    "prada bomber jacket",
    "prada gabardine",
    "prada nylon bomber",
    "prada denim jacket",
    "chrome hearts ch logo hat",
    "chrome hearts cox ucker",
    "chrome hearts trucker hat",
    "maison margiela gentle monster gentle",
    "raf simons knit sweater",
    "junya watanabe supreme cdg man",
    "alexander mcqueen skull scarf",
    "number (n)ine jam home made",
    "rick owens dr. martens",
    # Fully depreciated / no-margin markets
    "adidas raf simons ozweego",  # adidas-prefixed version is dead; "raf simons ozweego" is promoted
    "amiri mx1 clay indigo",
    # Excluded brands — not scanning these
    "van cleef",
    "van cleef alhambra",
    "van cleef alhambra necklace",
    "van cleef alhambra bracelet",
    "van cleef vintage alhambra",
    "van cleef frivole",
    "van cleef bracelet",
    "junya watanabe",
    "junya watanabe man jacket",
    "junya watanabe denim jacket",
    "junya watanabe patchwork",
    "junya watanabe comme des garcons jacket",
    "junya watanabe reconstruction",
    "junya watanabe coat",
    "yohji yamamoto",
    "yohji yamamoto coat",
    "yohji yamamoto boots",
    "yohji yamamoto blazer",
    "yohji yamamoto y-3",
    "yohji yamamoto pour homme",
    "yohji yamamoto pour homme jacket",
    "yohji yamamoto coat black",
    "yohji yamamoto asymmetric",
    "y's yohji yamamoto jacket",
    "tiffany",
    "tiffany t bracelet",
    "tiffany hardwear",
    "tiffany return to tiffany",
    "tiffany keys",
    "hermes",
    "hermes clic h",
    "hermes clic clac",
    "hermes kelly bracelet",
    "cartier",
    "cartier love bracelet",
    "cartier love ring",
    "cartier juste un clou",
    "bvlgari",
    "bvlgari serpenti",
    "bvlgari b zero ring",
    # Dead queries (0 deals, many runs) — demoted 2026-03-15
    "kapital jacket",
    "issey miyake",
    "issey miyake sneakers",
    "issey miyake pants",
    "issey miyake homme plisse",
    "issey miyake bomber jacket",
    "prada hoodie",
    "saint laurent jacket",
    "saint laurent hedi slimane slp",
    "bottega veneta puddle boots",
    "kapital sneakers",
    "neighborhood ring",
    "neighborhood hoodie",
    "undercover coat",
    "rick owens ring",
    "rick owens slab denim",
    "chrome hearts box officer glasses",
    "chrome hearts bomber jacket",
    "chrome hearts hollywood trucker hat",
    "chrome hearts leather jacket",
    "raf simons boots",
"vivienne westwood coat",
    "vivienne westwood knit sweater",
    "vivienne westwood wallet",
    "helmut lang astro biker",
    "helmut lang bomber jacket",
    "helmut lang archive jacket",
    "dior homme sneakers",
    "needles track pants",
    "needles rebuild by needles",
    "wtaps bomber jacket",
    "grailed yeat zine",
    "prada",
    "hysteric glamour",
    # ALL CDG eliminated — margins not there, SHIRT polluted deals
    "comme des garcons play", "comme des garcons play heart",
    "comme des garcons shirt", "comme des garcons shirt jacket",
    "comme des garcons wallet", "comme des garcons converse",
    "comme des garcons nike", "comme des garcons homme plus",
    "cdg play", "cdg play heart", "cdg shirt", "cdg wallet",
    "cdg converse", "cdg nike", "cdg homme plus",
    "comme des garcons parfum", "cdg parfum",
    "comme des garcons junya", "cdg junya",
    # ALL bags eliminated — high counterfeit risk, inaccurate comps
    "gucci bag", "gucci marmont", "gucci dionysus", "gucci jackie",
    "gucci bamboo", "gucci ophidia", "gucci tote", "gucci handbag",
    "louis vuitton keepall", "louis vuitton neverfull", "louis vuitton speedy",
    "louis vuitton bag", "louis vuitton handbag",
    "chanel classic flap", "chanel bag", "chanel flap", "chanel boy bag",
    "balenciaga le city bag", "balenciaga hourglass bag", "balenciaga le cagole",
    "balenciaga city bag", "balenciaga bag",
    "bottega veneta cassette bag", "bottega veneta bag", "bottega veneta intrecciato bag",
    "bottega veneta intrecciato leather briefcase", "bottega veneta intrecciato wallet",
    "prada bag", "prada handbag", "prada tote",
    "chrome hearts wallet", "chrome hearts bag",
    "saint laurent bag",
    "celine bag", "celine luggage",
    "dior bag", "dior saddle", "dior book tote",
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
    "accessories", "hat", "tee", "shirt", "bracelet", "necklace",
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
