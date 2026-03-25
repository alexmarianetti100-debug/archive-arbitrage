"""Canonical target-family definitions for high-value query clusters."""

from __future__ import annotations

TARGET_FAMILIES: dict[str, dict] = {
    "saint_laurent_wyatt": {
        "canonical": "saint laurent wyatt boots",
        "aliases": [
            "saint laurent paris paris wyatt",
            "saint laurent wyatt boots",
            "saint laurent paris wyatt harness",
        ],
        "broad_allowed": False,
        "allowed_queries": ["saint laurent wyatt boots"],
        "demoted_queries": ["saint laurent paris paris wyatt"],
    },
    "saint_laurent_hedi": {
        "canonical": "saint laurent hedi slimane",
        "aliases": [
            "saint laurent hedi slimane paris",
            "saint laurent paris hedi slimane",
            "saint laurent hedi slimane",
        ],
        "broad_allowed": False,
        "allowed_queries": ["saint laurent hedi slimane"],
        "demoted_queries": [],
    },
    "saint_laurent_oil": {
        "canonical": "saint laurent paris oil",
        "aliases": [
            "saint laurent paris sz paris",
            "saint laurent paris paris oil",
            "saint laurent paris oil",
        ],
        "broad_allowed": False,
        "allowed_queries": ["saint laurent paris oil"],
        "demoted_queries": ["saint laurent paris sz paris"],
    },
    "margiela_gat": {
        "canonical": "maison margiela gat",
        "aliases": [
            "maison margiela gat",
            "maison margiela gats",
            "maison margiela replica",
        ],
        "broad_allowed": False,
        "allowed_queries": ["maison margiela gat"],
        "demoted_queries": ["maison margiela gats"],
    },
    "margiela_replica_gat": {
        "canonical": "maison margiela replica gat",
        "aliases": [
            "maison margiela replica gat",
            "maison martin margiela replica GAT",
        ],
        "broad_allowed": False,
        "allowed_queries": ["maison margiela replica gat"],
        "demoted_queries": ["maison martin margiela replica GAT"],
    },
    "margiela_gat_low": {
        "canonical": "maison margiela gat low",
        "aliases": [
            "maison margiela gat low",
            "maison margiela gat replica low",
            "maison margiela gat replica sneakers",
        ],
        "broad_allowed": False,
        "allowed_queries": ["maison margiela gat low"],
        "demoted_queries": ["maison margiela gat replica sneakers"],
    },
    "margiela_tabi": {
        "canonical": "maison margiela tabi",
        "aliases": [
            "maison margiela tabi",
            "margiela tabi",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": ["maison margiela tabi", "margiela tabi"],
    },
    "margiela_tabi_boots": {
        "canonical": "maison margiela tabi boots",
        "aliases": [
            "maison margiela tabi boots",
            "margiela tabi boots",
        ],
        "broad_allowed": False,
        "allowed_queries": ["maison margiela tabi boots"],
        "demoted_queries": [],
    },
    "rick_owens_dr_martens": {
        "canonical": "rick owens dr. martens",
        "aliases": [
            "rick owens dr. martens dr",
            "rick owens dr. martens dr.",
            "rick owens dr. martens doc",
            "rick owens dr. martens quad",
            "rick owens dr. martens",
        ],
        "broad_allowed": False,
        "allowed_queries": ["rick owens dr. martens"],
        "demoted_queries": [
            "rick owens dr. martens dr",
            "rick owens dr. martens dr.",
            "rick owens dr. martens quad",
        ],
    },
    "balenciaga_runner": {
        "canonical": "balenciaga runner",
        "aliases": [
            "balenciaga balenciaga runner",
            "balenciaga runner",
        ],
        "broad_allowed": False,
        "allowed_queries": ["balenciaga runner"],
        "demoted_queries": ["balenciaga balenciaga runner"],
    },
    "number_nine_cleanup": {
        "canonical": "number nine",
        "aliases": [
            "number (n)ine (n)ine supreme (n)ine",
            "number (n)ine (n)ine supreme®/ (n)ine®",
            "number (n)ine (n)ine (n)ine school",
            "number (n)ine (n)ine (n)ine logo",
            "number (n)ine (n)ine (n)ine double",
            "number nine",
        ],
        "broad_allowed": False,
        "allowed_queries": ["number nine"],
        "demoted_queries": [
            "number (n)ine (n)ine supreme (n)ine",
            "number (n)ine (n)ine supreme®/ (n)ine®",
            "number (n)ine (n)ine (n)ine school",
            "number (n)ine (n)ine (n)ine logo",
            "number (n)ine (n)ine (n)ine double",
        ],
    },
    "rick_owens_geobasket_legacy": {
        "canonical": "rick owens geobasket",
        "aliases": ["rick owens geobasket"],
        "broad_allowed": False,
        "allowed_queries": ["rick owens geobasket"],
        "demoted_queries": [],
    },
    "rick_owens_ramones_legacy": {
        "canonical": "rick owens ramones",
        "aliases": ["rick owens ramones", "rick owens ramones low"],
        "broad_allowed": False,
        "allowed_queries": ["rick owens ramones"],
        "demoted_queries": ["rick owens ramones low"],
    },
    "rick_owens_dunks": {
        "canonical": "rick owens dunks",
        "aliases": ["rick owens dunks"],
        "broad_allowed": False,
        "allowed_queries": ["rick owens dunks"],
        "demoted_queries": [],
    },
    "chrome_hearts_cross_pendant": {
        "canonical": "chrome hearts cross pendant",
        "aliases": ["chrome hearts cross pendant", "chrome hearts cemetery cross", "chrome hearts floral cross"],
        "broad_allowed": False,
        "allowed_queries": ["chrome hearts cross pendant", "chrome hearts cemetery cross", "chrome hearts floral cross"],
        "demoted_queries": [],
    },
    "chrome_hearts_matty_boy": {
        "canonical": "chrome hearts matty boy",
        "aliases": ["chrome hearts matty boy"],
        "broad_allowed": False,
        "allowed_queries": ["chrome hearts matty boy"],
        "demoted_queries": [],
    },
    "chrome_hearts_apparel": {
        "canonical": "chrome hearts tee",
        "aliases": [
            "chrome hearts tee", "chrome hearts long sleeve", "chrome hearts neck logo long",
            "chrome hearts hoodie", "chrome hearts horseshoe hoodie", "chrome hearts sweatpants",
            "chrome hearts zip up hoodie", "chrome hearts shorts", "chrome hearts thermal",
            "chrome hearts track pants",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts tee", "chrome hearts long sleeve", "chrome hearts neck logo long",
            "chrome hearts hoodie", "chrome hearts sweatpants",
            "chrome hearts zip up hoodie", "chrome hearts shorts", "chrome hearts thermal",
            "chrome hearts track pants",
        ],
        "demoted_queries": ["chrome hearts horseshoe hoodie"],
    },
    "chrome_hearts_denim": {
        "canonical": "chrome hearts cross patch jeans",
        "aliases": [
            "chrome hearts cross patch jeans",
            "chrome hearts jeans",
            "chrome hearts denim",
            "chrome hearts cross patch flannel",
            "chrome hearts flannel",
            "chrome hearts denim jacket",
            "chrome hearts trucker jacket",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts cross patch jeans",
            "chrome hearts cross patch flannel",
            "chrome hearts trucker jacket",
            "chrome hearts denim jacket",
        ],
        "demoted_queries": [
            "chrome hearts jeans",
            "chrome hearts denim",
            "chrome hearts flannel",
        ],
    },
    "chrome_hearts_deadly_doll": {
        "canonical": "chrome hearts deadly doll",
        "aliases": [
            "chrome hearts deadly doll",
            "chrome hearts deadly doll tank",
            "chrome hearts deadly doll tee",
            "chrome hearts deadly doll hoodie",
            "chrome hearts deadly doll thermal",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts deadly doll",
            "chrome hearts deadly doll tank",
            "chrome hearts deadly doll tee",
            "chrome hearts deadly doll hoodie",
            "chrome hearts deadly doll thermal",
        ],
        "demoted_queries": [],
    },
    "chrome_hearts_matty_boy_apparel": {
        "canonical": "chrome hearts matty boy hoodie",
        "aliases": [
            "chrome hearts matty boy hoodie",
            "chrome hearts matty boy tee",
            "chrome hearts matty boy long sleeve",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts matty boy hoodie",
            "chrome hearts matty boy tee",
            "chrome hearts matty boy long sleeve",
        ],
        "demoted_queries": [],
    },
    "chrome_hearts_necklaces": {
        "canonical": "chrome hearts paper chain",
        "aliases": [
            "chrome hearts paper chain",
            "chrome hearts cross pendant",
            "chrome hearts cemetery cross pendant",
            "chrome hearts floral cross pendant",
            "chrome hearts baby fat pendant",
            "chrome hearts dagger pendant",
            "chrome hearts scroll pendant",
            "chrome hearts horseshoe pendant",
            "chrome hearts ch cross pendant",
            "chrome hearts ch plus pendant",
            "chrome hearts mini cross pendant",
            "chrome hearts large cross pendant",
            "chrome hearts tiny ch cross",
            "chrome hearts double cross pendant",
            "chrome hearts maltese cross pendant",
            "chrome hearts filigree cross pendant",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts paper chain",
            "chrome hearts cross pendant",
            "chrome hearts cemetery cross pendant",
            "chrome hearts floral cross pendant",
            "chrome hearts baby fat pendant",
            "chrome hearts dagger pendant",
            "chrome hearts scroll pendant",
            "chrome hearts horseshoe pendant",
            "chrome hearts ch cross pendant",
            "chrome hearts ch plus pendant",
        ],
        "demoted_queries": [
            "chrome hearts mini cross pendant",
            "chrome hearts large cross pendant",
            "chrome hearts tiny ch cross",
            "chrome hearts double cross pendant",
            "chrome hearts maltese cross pendant",
            "chrome hearts filigree cross pendant",
        ],
    },
    "chrome_hearts_rings": {
        "canonical": "chrome hearts cross ring",
        "aliases": [
            "chrome hearts cross ring",
            "chrome hearts floral cross ring",
            "chrome hearts cemetery cross ring",
            "chrome hearts baby fat ring",
            "chrome hearts forever ring",
            "chrome hearts bubblegum ring",
            "chrome hearts ch plus ring",
            "chrome hearts scroll ring",
            "chrome hearts dagger ring",
            "chrome hearts horseshoe ring",
            "chrome hearts fuck you ring",
            "chrome hearts spinner ring",
            "chrome hearts keeper ring",
            "chrome hearts maltese cross ring",
            "chrome hearts filigree ring",
            "chrome hearts tiny cross ring",
            "chrome hearts mini plus ring",
            "chrome hearts spacer ring",
            "chrome hearts double floral ring",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts cross ring",
            "chrome hearts floral cross ring",
            "chrome hearts cemetery cross ring",
            "chrome hearts baby fat ring",
            "chrome hearts forever ring",
            "chrome hearts bubblegum ring",
            "chrome hearts ch plus ring",
            "chrome hearts scroll ring",
            "chrome hearts dagger ring",
            "chrome hearts horseshoe ring",
            "chrome hearts fuck you ring",
            "chrome hearts spinner ring",
            "chrome hearts keeper ring",
        ],
        "demoted_queries": [
            "chrome hearts maltese cross ring",
            "chrome hearts filigree ring",
            "chrome hearts tiny cross ring",
            "chrome hearts mini plus ring",
            "chrome hearts spacer ring",
            "chrome hearts double floral ring",
        ],
    },
    "chrome_hearts_bracelets": {
        "canonical": "chrome hearts paper chain bracelet",
        "aliases": [
            "chrome hearts paper chain bracelet",
            "chrome hearts cross bracelet",
            "chrome hearts cross ball bracelet",
            "chrome hearts rollercoaster bracelet",
            "chrome hearts tiny ch plus bracelet",
            "chrome hearts ch plus bracelet",
            "chrome hearts scroll bracelet",
            "chrome hearts dagger bracelet",
            "chrome hearts id bracelet",
            "chrome hearts link bracelet",
            "chrome hearts chain bracelet",
            "chrome hearts leather bracelet",
            "chrome hearts bead bracelet",
            "chrome hearts ball bracelet",
            "chrome hearts mini cross bracelet",
            "chrome hearts filigree bracelet",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts paper chain bracelet",
            "chrome hearts cross bracelet",
            "chrome hearts cross ball bracelet",
            "chrome hearts rollercoaster bracelet",
            "chrome hearts tiny ch plus bracelet",
            "chrome hearts ch plus bracelet",
            "chrome hearts scroll bracelet",
            "chrome hearts dagger bracelet",
            "chrome hearts id bracelet",
        ],
        "demoted_queries": [
            "chrome hearts link bracelet",
            "chrome hearts chain bracelet",
            "chrome hearts leather bracelet",
            "chrome hearts bead bracelet",
            "chrome hearts ball bracelet",
            "chrome hearts mini cross bracelet",
            "chrome hearts filigree bracelet",
        ],
    },
    "saint_laurent_outerwear": {
        "canonical": "saint laurent leather jacket",
        "aliases": ["saint laurent leather jacket", "saint laurent bomber jacket", "saint laurent teddy jacket", "saint laurent court classic"],
        "broad_allowed": False,
        "allowed_queries": ["saint laurent bomber jacket"],
        "demoted_queries": ["saint laurent leather jacket", "saint laurent teddy jacket", "saint laurent court classic"],
    },
    "prada_footwear": {
        "canonical": "prada america’s cup sneakers",
        "aliases": ["prada america’s cup sneakers", "prada americas cup", "prada sneakers", "prada cloudbust", "prada linea rossa"],
        "broad_allowed": False,
        "allowed_queries": ["prada america’s cup sneakers"],
        "demoted_queries": ["prada sneakers", "prada cloudbust", "prada linea rossa"],
    },
    "raf_footwear": {
        "canonical": "adidas raf simons ozweego",
        "aliases": ["adidas raf simons ozweego", "raf simons ozweego"],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": ["adidas raf simons ozweego", "raf simons ozweego"],
    },
    "rick_owens_bauhaus": {
        "canonical": "rick owens bauhaus",
        "aliases": ["rick owens bauhaus", "rick owens bauhaus cargo"],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": ["rick owens bauhaus", "rick owens bauhaus cargo"],
    },
    "margiela_paint_splatter": {
        "canonical": "maison margiela paint splatter",
        "aliases": ["maison margiela paint splatter"],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": ["maison margiela paint splatter"],
    },
    "balenciaga_cargo": {
        "canonical": "balenciaga cargo pants",
        "aliases": ["balenciaga cargo pants"],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": ["balenciaga cargo pants"],
    },
    "nike": {
        "canonical": "nike",
        "aliases": [
            "nike", "nike dunk", "nike sb", "nike air force", "nike af1",
            "nike jordan", "air jordan", "nike travis scott", "nike off white",
            "nike supreme", "nike acronym", "nike sacai", "nike undercover",
            "nike ambush", "nike stussy", "nike kith", "nike supreme dunk",
            "nike sb dunk", "nike air max", "nike am90", "nike am95",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "nike", "nike dunk", "nike sb", "nike air force", "nike af1",
            "nike jordan", "air jordan", "nike travis scott", "nike off white",
            "nike supreme", "nike acronym", "nike sacai", "nike undercover",
            "nike ambush", "nike stussy", "nike kith", "nike supreme dunk",
            "nike sb dunk", "nike air max", "nike am90", "nike am95",
        ],
    },
    "adidas": {
        "canonical": "adidas",
        "aliases": [
            "adidas", "adidas yeezy", "yeezy", "yeezy boost", "yeezy 350",
            "yeezy 700", "yeezy slide", "adidas forum", "adidas samba",
            "adidas gazelle", "adidas campus", "adidas spezial",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "adidas", "adidas yeezy", "yeezy", "yeezy boost", "yeezy 350",
            "yeezy 700", "yeezy slide", "adidas forum", "adidas samba",
            "adidas gazelle", "adidas campus", "adidas spezial",
        ],
    },
    "new_balance": {
        "canonical": "new balance",
        "aliases": [
            "new balance", "new balance 550", "new balance 990", "new balance 992",
            "new balance 993", "new balance 2002r", "new balance 9060",
            "new balance jjjjound", "new balance aime leon dore",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "new balance", "new balance 550", "new balance 990", "new balance 992",
            "new balance 993", "new balance 2002r", "new balance 9060",
            "new balance jjjjound", "new balance aime leon dore",
        ],
    },
    "asics": {
        "canonical": "asics",
        "aliases": [
            "asics", "asics gel lyte", "asics gel kayano", "asics kith",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "asics", "asics gel lyte", "asics gel kayano", "asics kith",
        ],
    },
    "converse": {
        "canonical": "converse",
        "aliases": [
            "converse", "converse chuck taylor", "converse 70s", "converse cdg",
            "converse comme des garcons", "converse rick owens",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "converse", "converse chuck taylor", "converse 70s", "converse cdg",
            "converse comme des garcons",
        ],
    },
    "vans": {
        "canonical": "vans",
        "aliases": [
            "vans", "vans vault", "vans og", "vans wtaps", "vans supreme",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "vans", "vans vault", "vans og", "vans wtaps", "vans supreme",
        ],
    },
    "broad_streetwear": {
        "canonical": "supreme",
        "aliases": [
            "supreme", "supreme box logo", "supreme bogo", "palace",
            "palace skateboards", "bape", "a bathing ape", "kith", "fear of god",
            "essentials", " Essentials", "off white", "off-white", "virgil abloh",
            "heron preston", "alyx", "1017 alyx 9sm", "stone island",
            "cp company", "c.p. company",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "supreme", "supreme box logo", "supreme bogo", "palace",
            "palace skateboards", "bape", "a bathing ape", "kith", "fear of god",
            "essentials", " Essentials", "off white", "off-white", "virgil abloh",
            "heron preston", "alyx", "1017 alyx 9sm", "stone island",
            "cp company", "c.p. company",
        ],
    },
    "demoted_misc": {
        "canonical": "misc_junk",
        "aliases": [
            "vintage", "rare", "deadstock", "ds", "bnwt", "nwt", "new with tags",
            "sample", "promo", "promotional", "employee", "friends and family",
            "f&f", "limited edition", "collab", "collaboration",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "vintage", "rare", "deadstock", "ds", "bnwt", "nwt", "new with tags",
            "sample", "promo", "promotional", "employee", "friends and family",
            "f&f", "limited edition", "collab", "collaboration",
        ],
    },
    "chrome_hearts_eyewear": {
        "canonical": "chrome hearts sunglasses",
        "aliases": [
            "chrome hearts sunglasses",
            "chrome hearts glasses",
            "chrome hearts optical",
            "chrome hearts trypoleagain",
            "chrome hearts eyewear",
            "chrome hearts grom",
            "chrome hearts grom sunglasses",
            "chrome hearts grom glasses",
            "chrome hearts sexcel",
            "chrome hearts sexcel sunglasses",
            "chrome hearts sexcel glasses",
            "chrome hearts vagasoreass",
            "chrome hearts vagasoreass sunglasses",
            "chrome hearts stick",
            "chrome hearts stick sunglasses",
            "chrome hearts stunner",
            "chrome hearts stunner sunglasses",
            "chrome hearts instabone",
            "chrome hearts instabone sunglasses",
            "chrome hearts bone polisher",
            "chrome hearts bone polisher sunglasses",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts sunglasses",
            "chrome hearts trypoleagain",
            "chrome hearts grom",
            "chrome hearts sexcel",
            "chrome hearts vagasoreass",
            "chrome hearts stunner",
            "chrome hearts instabone",
            "chrome hearts bone polisher",
        ],
        "demoted_queries": [
            "chrome hearts glasses",
            "chrome hearts optical",
            "chrome hearts eyewear",
            "chrome hearts grom sunglasses",
            "chrome hearts grom glasses",
            "chrome hearts sexcel sunglasses",
            "chrome hearts sexcel glasses",
            "chrome hearts vagasoreass sunglasses",
            "chrome hearts stick",
            "chrome hearts stick sunglasses",
        ],
    },
    "chrome_hearts_demoted_misc": {
        "canonical": "chrome hearts cox ucker",
        "aliases": [
            "chrome hearts cox ucker",
            "chrome hearts coxucker",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "chrome hearts cox ucker",
            "chrome hearts coxucker",
        ],
    },
    "margiela_outerwear": {
        "canonical": "maison margiela leather jacket",
        "aliases": [
            "maison margiela leather jacket",
            "maison margiela denim jacket",
            "maison margiela bomber jacket",
            "maison margiela coat",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "maison margiela leather jacket",
            "maison margiela denim jacket",
            "maison margiela bomber jacket",
        ],
        "demoted_queries": [
            "maison margiela coat",
        ],
    },
    "rick_owens_outerwear": {
        "canonical": "rick owens leather jacket",
        "aliases": [
            "rick owens leather jacket",
            "rick owens bomber jacket",
            "rick owens coat",
            "rick owens stooges",
            "rick owens stooges leather jacket",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "rick owens leather jacket",
            "rick owens stooges",
            "rick owens stooges leather jacket",
        ],
        "demoted_queries": [
            "rick owens bomber jacket",
            "rick owens coat",
        ],
    },
    "balenciaga_outerwear": {
        "canonical": "balenciaga leather jacket",
        "aliases": [
            "balenciaga leather jacket",
            "balenciaga bomber jacket",
            "balenciaga denim jacket",
            "balenciaga parka",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "balenciaga leather jacket",
            "balenciaga bomber jacket",
        ],
        "demoted_queries": [
            "balenciaga denim jacket",
            "balenciaga parka",
        ],
    },
    "dior_footwear": {
        "canonical": "dior b23",
        "aliases": [
            "dior b23",
            "dior b22",
            "dior sneakers",
            "dior shoes",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "dior b23",
            "dior b22",
        ],
        "demoted_queries": [
            "dior sneakers",
            "dior shoes",
        ],
    },
    "dior_outerwear": {
        "canonical": "dior denim jacket",
        "aliases": [
            "dior denim jacket",
            "dior leather jacket",
            "dior oblique jacket",
            "dior coat",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "dior denim jacket",
            "dior oblique jacket",
        ],
        "demoted_queries": [
            "dior leather jacket",
            "dior coat",
        ],
    },
    "gucci_footwear": {
        "canonical": "gucci loafers",
        "aliases": [
            "gucci loafers",
            "gucci jordaan",
            "gucci horsebit",
            "gucci sneakers",
            "gucci shoes",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "gucci loafers",
            "gucci jordaan",
            "gucci horsebit",
        ],
        "demoted_queries": [
            "gucci sneakers",
            "gucci shoes",
        ],
    },
    "gucci_accessories": {
        "canonical": "gucci belt",
        "aliases": [
            "gucci belt",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "gucci belt",
        ],
        "demoted_queries": [],
    },
    "lv_accessories": {
        "canonical": "louis vuitton belt",
        "aliases": [
            "louis vuitton belt",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "louis vuitton belt",
        ],
        "demoted_queries": [],
    },
    "demoted_junk_queries": {
        "canonical": "demoted_junk",
        "aliases": [
            "saint laurent yves yves rive",
            "balenciaga track",
            "saint laurent paris paris d02",
            "rick owens beatle bozo tractor",
            "balenciaga triple s",
            "prada lace-up leather boots",
            "rick owens cargo pants",
            "chrome hearts ch logo hat",
            "chrome hearts zip up hoodie",
            "maison margiela gentle monster gentle",
            "raf simons knit sweater",
            "saint laurent paris paris leather",
            "junya watanabe supreme cdg man",
            "prada bomber jacket",
            "prada gabardine",
            "prada nylon bomber",
            "rick owens ramones high",
            "saint laurent yves ysl jacket",
            "alexander mcqueen skull scarf",
            "balenciaga 2000’s classic city",
            "number (n)ine jam home made",
            "prada denim jacket",
            "saint laurent l01 leather jacket",
            "balenciaga track sneaker",
        ],
        "broad_allowed": False,
        "allowed_queries": [],
        "demoted_queries": [
            "saint laurent yves yves rive",
            "balenciaga track",
            "saint laurent paris paris d02",
            "rick owens beatle bozo tractor",
            "balenciaga triple s",
            "prada lace-up leather boots",
            "rick owens cargo pants",
            "chrome hearts ch logo hat",
            "chrome hearts zip up hoodie",
            "maison margiela gentle monster gentle",
            "raf simons knit sweater",
            "saint laurent paris paris leather",
            "junya watanabe supreme cdg man",
            "prada bomber jacket",
            "prada gabardine",
            "prada nylon bomber",
            "rick owens ramones high",
            "saint laurent yves ysl jacket",
            "alexander mcqueen skull scarf",
            "balenciaga 2000’s classic city",
            "number (n)ine jam home made",
            "prada denim jacket",
            "saint laurent l01 leather jacket",
            "balenciaga track sneaker",
        ],
    },
    # HIGH-VOLUME SELLERS (based on actual Grailed sales data)
    "rick_owens_cargo": {
        "canonical": "rick owens cargo",
        "aliases": [
            "rick owens cargo",
            "rick owens cargo pants",
            "rick owens drkshdw cargo",
            "rick owens creatch cargo",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "rick owens cargo",
            "rick owens creatch cargo",
        ],
        "demoted_queries": [
            "rick owens cargo pants",
            "rick owens drkshdw cargo",
        ],
    },
    "rick_owens_ramones": {
        "canonical": "rick owens ramones",
        "aliases": [
            "rick owens ramones",
            "rick owens drkshdw ramones",
            "rick owens ramones low",
            "rick owens ramones high",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "rick owens ramones",
        ],
        "demoted_queries": [
            "rick owens drkshdw ramones",
            "rick owens ramones low",
            "rick owens ramones high",
        ],
    },
    # Jean Paul Gaultier — new high-performing families
    "jpq_mesh": {
        "canonical": "jean paul gaultier mesh top",
        "aliases": [
            "jean paul gaultier mesh top",
            "jean paul gaultier mesh",
            "gaultier mesh top",
            "gaultier mesh",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "jean paul gaultier mesh top",
            "jean paul gaultier mesh",
        ],
        "demoted_queries": [],
    },
    "jpq_corset": {
        "canonical": "jean paul gaultier corset",
        "aliases": [
            "jean paul gaultier corset",
            "gaultier corset",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "jean paul gaultier corset",
        ],
        "demoted_queries": [],
    },
    # Enfants Riches Deprimes
    "erd_tops": {
        "canonical": "enfants riches deprimes hoodie",
        "aliases": [
            "enfants riches deprimes hoodie",
            "enfants riches deprimes tee",
            "enfants riches deprimes long sleeve",
            "enfants riches deprimes sweater",
            "enfants riches deprimes shirt",
            "enfants riches deprimes sweatpants",
            "erd hoodie",
            "erd tee",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes hoodie",
            "enfants riches deprimes tee",
            "enfants riches deprimes long sleeve",
            "enfants riches deprimes sweater",
            "enfants riches deprimes shirt",
            "enfants riches deprimes sweatpants",
        ],
        "demoted_queries": [],
    },
    "erd_outerwear": {
        "canonical": "enfants riches deprimes leather jacket",
        "aliases": [
            "enfants riches deprimes leather jacket",
            "enfants riches deprimes denim jacket",
            "enfants riches deprimes bomber",
            "enfants riches deprimes flannel",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes leather jacket",
            "enfants riches deprimes denim jacket",
            "enfants riches deprimes bomber",
            "enfants riches deprimes flannel",
        ],
        "demoted_queries": [],
    },
    "erd_bottoms": {
        "canonical": "enfants riches deprimes jeans",
        "aliases": [
            "enfants riches deprimes jeans",
            "enfants riches deprimes denim",
            "enfants riches deprimes menendez pants",
            "erd menendez pants",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes jeans",
            "enfants riches deprimes menendez pants",
        ],
        "demoted_queries": [
            "enfants riches deprimes denim",
        ],
    },
    "erd_accessories": {
        "canonical": "enfants riches deprimes hat",
        "aliases": [
            "enfants riches deprimes hat",
            "enfants riches deprimes belt",
            "enfants riches deprimes cap",
            "enfants riches deprimes rose buckle belt",
            "erd rose buckle belt",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes hat",
            "enfants riches deprimes belt",
            "enfants riches deprimes rose buckle belt",
        ],
        "demoted_queries": [
            "enfants riches deprimes cap",
        ],
    },
    "erd_grails_tier1": {
        "canonical": "enfants riches deprimes classic logo hoodie",
        "aliases": [
            "enfants riches deprimes classic logo hoodie",
            "enfants riches deprimes classic logo tee",
            "enfants riches deprimes safety pin earring",
            "enfants riches deprimes classic logo long sleeve",
            "erd classic logo hoodie",
            "erd classic logo tee",
            "erd safety pin earring",
            "erd classic logo long sleeve",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes classic logo hoodie",
            "enfants riches deprimes classic logo tee",
            "enfants riches deprimes safety pin earring",
            "enfants riches deprimes classic logo long sleeve",
        ],
        "demoted_queries": [],
    },
    "erd_trending": {
        "canonical": "enfants riches deprimes bennys video hoodie",
        "aliases": [
            "enfants riches deprimes bennys video hoodie",
            "enfants riches deprimes menendez hoodie",
            "enfants riches deprimes viper room hat",
            "enfants riches deprimes teenage snuff tee",
            "enfants riches deprimes flowers of anger",
            "enfants riches deprimes bohemian scum tee",
            "erd bennys video",
            "erd menendez hoodie",
            "erd viper room hat",
            "erd teenage snuff",
            "erd flowers of anger",
            "erd bohemian scum",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes bennys video hoodie",
            "enfants riches deprimes menendez hoodie",
            "enfants riches deprimes viper room hat",
            "enfants riches deprimes teenage snuff tee",
            "enfants riches deprimes flowers of anger",
            "enfants riches deprimes bohemian scum tee",
        ],
        "demoted_queries": [],
    },
    "erd_premium_outerwear": {
        "canonical": "enfants riches deprimes spanish elegy jacket",
        "aliases": [
            "enfants riches deprimes spanish elegy jacket",
            "enfants riches deprimes god with revolver",
            "erd spanish elegy",
            "erd god with revolver",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes spanish elegy jacket",
            "enfants riches deprimes god with revolver",
        ],
        "demoted_queries": [],
    },
    "erd_collector": {
        "canonical": "enfants riches deprimes frozen beauties flannel",
        "aliases": [
            "enfants riches deprimes frozen beauties flannel",
            "enfants riches deprimes le rosey tee",
            "erd frozen beauties",
            "erd le rosey",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes frozen beauties flannel",
            "enfants riches deprimes le rosey tee",
        ],
        "demoted_queries": [],
    },
    "rick_owens_geobasket": {
        "canonical": "rick owens geobasket",
        "aliases": [
            "rick owens geobasket",
            "rick owens geo basket",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "rick owens geobasket",
            "rick owens geo basket",
        ],
        "demoted_queries": [],
    },
    "margiela_painted": {
        "canonical": "maison margiela painted",
        "aliases": [
            "maison margiela painted",
            "maison margiela paint splatter",
            "margiela painted",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "maison margiela painted",
        ],
        "demoted_queries": [
            "maison margiela paint splatter",
            "margiela painted",
        ],
    },
    "margiela_tabi_sandal": {
        "canonical": "maison margiela tabi sandal",
        "aliases": [
            "maison margiela tabi sandal",
            "maison margiela tabi sandals",
            "margiela tabi sandal",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "maison margiela tabi sandal",
        ],
        "demoted_queries": [
            "maison margiela tabi sandals",
            "margiela tabi sandal",
        ],
    },
    "prada_loafer": {
        "canonical": "prada loafer",
        "aliases": [
            "prada loafer",
            "prada loafers",
            "prada leather loafer",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "prada loafer",
        ],
        "demoted_queries": [
            "prada loafers",
            "prada leather loafer",
        ],
    },
    "prada_derby": {
        "canonical": "prada derby",
        "aliases": [
            "prada derby",
            "prada derby shoes",
            "prada leather derby",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "prada derby",
        ],
        "demoted_queries": [
            "prada derby shoes",
            "prada leather derby",
        ],
    },
    # ── CELINE (Hedi Slimane era) ──
    "celine_outerwear": {
        "canonical": "celine leather jacket",
        "aliases": [
            "celine leather jacket", "celine teddy jacket", "celine varsity jacket",
            "celine denim jacket", "celine bomber jacket", "celine coat",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "celine leather jacket", "celine teddy jacket", "celine varsity jacket",
            "celine denim jacket", "celine bomber jacket",
        ],
        "demoted_queries": ["celine coat"],
    },
    "celine_footwear": {
        "canonical": "celine boots",
        "aliases": ["celine boots", "celine western boots", "celine chain boots"],
        "broad_allowed": False,
        "allowed_queries": ["celine boots", "celine western boots", "celine chain boots"],
        "demoted_queries": [],
    },
    "celine_accessories": {
        "canonical": "celine triomphe belt",
        "aliases": ["celine triomphe belt", "celine belt"],
        "broad_allowed": False,
        "allowed_queries": ["celine triomphe belt"],
        "demoted_queries": ["celine belt"],
    },
    # ── HAIDER ACKERMANN ──
    "haider_ackermann": {
        "canonical": "haider ackermann leather jacket",
        "aliases": [
            "haider ackermann leather jacket", "haider ackermann blazer",
            "haider ackermann velvet blazer", "haider ackermann silk bomber",
            "haider ackermann coat", "haider ackermann pants",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "haider ackermann leather jacket", "haider ackermann blazer",
            "haider ackermann velvet blazer", "haider ackermann silk bomber",
            "haider ackermann coat", "haider ackermann pants",
        ],
        "demoted_queries": [],
    },
    # ── DRIES VAN NOTEN ──
    "dries_van_noten": {
        "canonical": "dries van noten embroidered jacket",
        "aliases": [
            "dries van noten embroidered jacket", "dries van noten velvet blazer",
            "dries van noten printed shirt", "dries van noten floral jacket",
            "dries van noten coat", "dries van noten leather jacket",
            "dries van noten bomber",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "dries van noten embroidered jacket", "dries van noten velvet blazer",
            "dries van noten floral jacket", "dries van noten coat",
            "dries van noten leather jacket", "dries van noten bomber",
        ],
        "demoted_queries": ["dries van noten printed shirt"],
    },
    # ── SACAI ──
    "sacai": {
        "canonical": "sacai leather jacket",
        "aliases": [
            "sacai leather jacket", "sacai bomber jacket", "sacai blazer",
            "sacai coat", "sacai knit cardigan", "sacai deconstructed jacket",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "sacai leather jacket", "sacai bomber jacket", "sacai blazer",
            "sacai coat", "sacai deconstructed jacket",
        ],
        "demoted_queries": ["sacai knit cardigan"],
    },
    # ── MARGIELA ARTISANAL ──
    "margiela_artisanal": {
        "canonical": "margiela artisanal",
        "aliases": [
            "margiela artisanal", "margiela line 0", "margiela duvet coat",
            "margiela flat collection", "margiela white label jacket",
            "margiela deconstructed",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "margiela artisanal", "margiela duvet coat",
            "margiela white label jacket", "margiela deconstructed",
        ],
        "demoted_queries": ["margiela line 0", "margiela flat collection"],
    },
    # ── GUIDI ──
    "guidi_footwear": {
        "canonical": "guidi boots",
        "aliases": [
            "guidi boots", "guidi back zip boots", "guidi horse leather",
            "guidi jacket", "guidi 988", "guidi 995", "guidi 986",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "guidi boots", "guidi back zip boots", "guidi horse leather",
            "guidi jacket", "guidi 988", "guidi 995", "guidi 986",
        ],
        "demoted_queries": [],
    },
    # ── LEMAIRE ──
    "lemaire": {
        "canonical": "lemaire jacket",
        "aliases": [
            "lemaire jacket", "lemaire coat", "lemaire leather jacket",
            "lemaire twisted shirt", "lemaire boots",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "lemaire jacket", "lemaire coat", "lemaire leather jacket",
            "lemaire twisted shirt", "lemaire boots",
        ],
        "demoted_queries": [],
    },
    # ── ACNE STUDIOS ──
    "acne_studios": {
        "canonical": "acne studios leather jacket",
        "aliases": [
            "acne studios leather jacket", "acne studios velocite jacket",
            "acne studios shearling", "acne studios boots", "acne studios max jeans",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "acne studios leather jacket", "acne studios velocite jacket",
            "acne studios shearling", "acne studios boots",
        ],
        "demoted_queries": ["acne studios max jeans"],
    },
    # ── SIMONE ROCHA ──
    "simone_rocha": {
        "canonical": "simone rocha pearl",
        "aliases": [
            "simone rocha dress", "simone rocha jacket",
            "simone rocha pearl", "simone rocha embellished",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "simone rocha dress", "simone rocha jacket",
            "simone rocha pearl", "simone rocha embellished",
        ],
        "demoted_queries": [],
    },
    # ── BRUNELLO CUCINELLI ──
    "brunello_cucinelli": {
        "canonical": "brunello cucinelli cashmere jacket",
        "aliases": [
            "brunello cucinelli cashmere jacket", "brunello cucinelli leather jacket",
            "brunello cucinelli cashmere sweater", "brunello cucinelli coat",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "brunello cucinelli cashmere jacket", "brunello cucinelli leather jacket",
            "brunello cucinelli cashmere sweater", "brunello cucinelli coat",
        ],
        "demoted_queries": [],
    },
    # ── THE SOLOIST / TAKAHIROMIYASHITA ──
    "soloist": {
        "canonical": "soloist jacket",
        "aliases": [
            "soloist jacket", "soloist leather jacket",
            "takahiromiyashita soloist", "soloist boots",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "soloist jacket", "soloist leather jacket",
            "takahiromiyashita soloist", "soloist boots",
        ],
        "demoted_queries": [],
    },
    # ── RAF SIMONS FOOTWEAR (reformulated) ──
    "raf_simons_footwear": {
        "canonical": "raf simons ozweego",
        "aliases": [
            "raf simons ozweego", "raf simons response trail",
            "raf simons detroit runner", "adidas raf simons ozweego",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "raf simons ozweego", "raf simons response trail",
            "raf simons detroit runner",
        ],
        "demoted_queries": ["adidas raf simons ozweego"],
    },
    # ── HYSTERIC GLAMOUR ──
    "hysteric_glamour": {
        "canonical": "hysteric glamour leather jacket",
        "aliases": [
            "hysteric glamour leather jacket", "hysteric glamour denim jacket",
            "hysteric glamour jeans", "hysteric glamour tee",
            "hysteric glamour kurt cobain", "hysteric glamour knit",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "hysteric glamour leather jacket", "hysteric glamour denim jacket",
            "hysteric glamour jeans", "hysteric glamour tee",
            "hysteric glamour kurt cobain",
        ],
        "demoted_queries": ["hysteric glamour knit"],
    },
    # ── BOTTEGA VENETA (no bags) ──
    "bottega_veneta_leather": {
        "canonical": "bottega veneta leather jacket",
        "aliases": ["bottega veneta leather jacket"],
        "broad_allowed": False,
        "allowed_queries": ["bottega veneta leather jacket"],
        "demoted_queries": [],
    },
    "bottega_veneta_boots": {
        "canonical": "bottega veneta haddock leather boots",
        "aliases": [
            "bottega veneta haddock leather boots", "bottega veneta chelsea boots",
            "bottega veneta tire boots", "bottega veneta lug boots",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "bottega veneta haddock leather boots", "bottega veneta chelsea boots",
            "bottega veneta tire boots", "bottega veneta lug boots",
        ],
        "demoted_queries": [],
    },
    # ── RAF SIMONS SEASONS ──
    "raf_simons_seasons": {
        "canonical": "raf simons 2002",
        "aliases": [
            "raf simons 2002", "raf simons 2001",
            "raf simons riot riot riot", "raf simons nebraska",
            "raf simons parka", "raf simons fishtail parka",
            "raf simons power corruption lies", "raf simons aw03",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "raf simons 2002", "raf simons 2001",
            "raf simons riot riot riot", "raf simons nebraska",
            "raf simons parka", "raf simons fishtail parka",
            "raf simons power corruption lies",
        ],
        "demoted_queries": ["raf simons aw03"],
    },
    # ── DIOR HOMME SEASONS ──
    "dior_homme_seasons": {
        "canonical": "dior homme navigate",
        "aliases": [
            "dior homme navigate", "dior homme fw03", "dior homme fw07",
            "dior homme kris van assche", "dior homme bee embroidered",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "dior homme navigate", "dior homme fw03", "dior homme fw07",
            "dior homme kris van assche", "dior homme bee embroidered",
        ],
        "demoted_queries": [],
    },
    # ── HELMUT LANG (reformulated) ──
    "helmut_lang_archive": {
        "canonical": "helmut lang 1998",
        "aliases": [
            "helmut lang 1998", "helmut lang 1999",
            "helmut lang bondage strap", "helmut lang reflective",
            "helmut lang raw denim", "helmut lang transparent",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "helmut lang 1998", "helmut lang 1999",
            "helmut lang bondage strap", "helmut lang reflective",
            "helmut lang raw denim",
        ],
        "demoted_queries": ["helmut lang transparent"],
    },
    # ── CHROME HEARTS ACCESSORIES ──
    "chrome_hearts_accessories": {
        "canonical": "chrome hearts belt",
        "aliases": [
            "chrome hearts belt",
            "chrome hearts diamond", "chrome hearts cemetery cross",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "chrome hearts belt",
            "chrome hearts diamond", "chrome hearts cemetery cross",
        ],
        "demoted_queries": [],
    },
    # ── LOUIS VUITTON (no bags — clothing/shoes only) ──
    "louis_vuitton": {
        "canonical": "louis vuitton murakami",
        "aliases": [
            "louis vuitton murakami",
            "louis vuitton trainer",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "louis vuitton murakami",
            "louis vuitton trainer",
        ],
        "demoted_queries": [],
    },
    # ── BALENCIAGA (no bags — clothing/shoes only) ──
    "balenciaga_demna": {
        "canonical": "balenciaga demna archive",
        "aliases": [
            "balenciaga demna archive", "balenciaga paris sneaker",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "balenciaga demna archive", "balenciaga paris sneaker",
        ],
        "demoted_queries": [],
    },
    # ── PRADA LOAFERS ──
    "prada_loafers": {
        "canonical": "prada chocolate loafers",
        "aliases": [
            "prada chocolate loafers", "prada leather loafers",
        ],
        "broad_allowed": False,
        "allowed_queries": ["prada chocolate loafers", "prada leather loafers"],
        "demoted_queries": [],
    },
    # ── MARGIELA EXPANDED FOOTWEAR ──
    "margiela_tabi_loafers": {
        "canonical": "maison margiela tabi loafers",
        "aliases": [
            "maison margiela tabi loafers", "maison margiela tabi babouche",
        ],
        "broad_allowed": False,
        "allowed_queries": ["maison margiela tabi loafers"],
        "demoted_queries": ["maison margiela tabi babouche"],
    },
    "margiela_future": {
        "canonical": "maison margiela future",
        "aliases": ["maison margiela future", "margiela future high", "margiela future low"],
        "broad_allowed": False,
        "allowed_queries": ["maison margiela future"],
        "demoted_queries": ["margiela future high", "margiela future low"],
    },
    # ── RICK OWENS SEASON-SPECIFIC ──
    "rick_owens_seasons": {
        "canonical": "rick owens fogachine",
        "aliases": [
            "rick owens fogachine", "rick owens tecuatl",
            "rick owens dustulator", "rick owens tractor boots",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "rick owens fogachine", "rick owens tecuatl",
            "rick owens dustulator", "rick owens tractor boots",
        ],
        "demoted_queries": [],
    },
}


def alias_to_canonical_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family in TARGET_FAMILIES.values():
        canonical = family["canonical"].lower().strip()
        mapping[canonical] = canonical
        for alias in family.get("aliases", []):
            mapping[alias.lower().strip()] = canonical
            mapping[alias.strip()] = canonical
    return mapping


def family_id_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family_id, family in TARGET_FAMILIES.items():
        canonical = family["canonical"].lower().strip()
        mapping[canonical] = family_id
        for alias in family.get("aliases", []):
            mapping[alias.lower().strip()] = family_id
            mapping[alias.strip()] = family_id
    return mapping


def family_policy_map() -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for family_id, family in TARGET_FAMILIES.items():
        policy = {
            "family_id": family_id,
            "canonical": family["canonical"].lower().strip(),
            "broad_allowed": family.get("broad_allowed", True),
            "allowed_queries": {q.lower().strip() for q in family.get("allowed_queries", [])},
            "demoted_queries": {q.lower().strip() for q in family.get("demoted_queries", [])},
        }
        mapping[policy["canonical"]] = policy
        for alias in family.get("aliases", []):
            mapping[alias.lower().strip()] = policy
            mapping[alias.strip()] = policy
    return mapping
