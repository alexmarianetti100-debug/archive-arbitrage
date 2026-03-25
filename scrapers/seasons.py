"""
Iconic seasons and collections database.

These collections command significant premiums over generic pieces from the same brand.
Format: (pattern, multiplier, collection_name)
- pattern: regex pattern to match in title/description
- multiplier: price multiplier (1.5 = 50% premium, 2.0 = 100% premium, etc.)
- collection_name: human-readable name for logging
"""

import re
from typing import Optional, Tuple, List

# Iconic seasons by brand
# Structure: brand_key -> list of (pattern, multiplier, name)
ICONIC_SEASONS = {

    # =========================================================================
    # JAPANESE DESIGNERS (OG)
    # =========================================================================

    # === RAF SIMONS ===
    "raf simons": [
        # Holy grails - 3x+ multiplier
        (r"(aw|fw|fall.?winter).?01.*riot|riot.*(aw|fw).?01", 3.5, "AW01 Riot Riot Riot"),
        (r"(aw|fw).?01|fall.?winter.?2001|riot.?riot", 3.0, "AW01"),
        (r"(aw|fw).?02.*virginia|virginia.?creeper", 3.0, "AW02 Virginia Creeper"),
        (r"(ss|spring.?summer).?02.*woe", 2.5, "SS02 Woe Onto Those"),
        (r"consumed|ss.?03.?consumed", 2.5, "SS03 Consumed"),
        (r"(aw|fw).?03.*closer", 2.5, "AW03 Closer"),
        (r"peter.?saville|joy.?division|unknown.?pleasures", 2.5, "Peter Saville collab"),

        # Strong seasons - 2x multiplier
        (r"(aw|fw).?04|fall.?winter.?2004", 2.0, "AW04"),
        (r"(aw|fw).?05|fall.?winter.?2005", 2.0, "AW05"),
        (r"(aw|fw).?06|fall.?winter.?2006", 1.8, "AW06"),
        (r"(ss|spring.?summer).?04", 1.8, "SS04"),
        (r"(ss|spring.?summer).?05", 1.8, "SS05"),
        (r"parachute.?bomber|bondage", 2.5, "Parachute/Bondage piece"),

        # Archive indicators
        (r"(aw|fw|ss).?(9[89]|0[0-9])|199[89]|200[0-9]", 1.5, "Archive 1998-2009"),
    ],

    # === NUMBER (N)INE ===
    "number nine": [
        # Takahiro era grails
        (r"(aw|fw).?05.*high.?street|high.?street.*(aw|fw).?05", 3.5, "AW05 The High Streets"),
        (r"(aw|fw).?06.*noir|noir", 3.0, "AW06 A Closed Feeling/Noir"),
        (r"(aw|fw).?05|fall.?winter.?2005", 2.5, "AW05"),
        (r"(aw|fw).?06|fall.?winter.?2006", 2.5, "AW06"),
        (r"(aw|fw).?04|fall.?winter.?2004", 2.2, "AW04"),
        (r"(ss|spring.?summer).?06.*touch|touch.?me", 2.5, "SS06 Touch Me I'm Sick"),
        (r"(ss|spring.?summer).?05", 2.0, "SS05"),

        # Iconic pieces
        (r"marlboro|cigarette", 2.5, "Marlboro piece"),
        (r"kurt.?cobain|nirvana", 2.5, "Kurt Cobain tribute"),
        (r"skull.?pile|skull.?cashmere", 2.0, "Skull piece"),

        # General archive
        (r"(aw|fw|ss).?(0[0-9])|200[0-9]", 1.5, "Archive 2000s"),
    ],

    # === UNDERCOVER ===
    "undercover": [
        # Jun Takahashi grails
        (r"(ss|spring.?summer).?03.*scab|scab", 3.5, "SS03 Scab"),
        (r"(aw|fw).?02.*witch|witch", 3.0, "AW02 Witch's Cell Division"),
        (r"(aw|fw).?03.*paper.?doll|paper.?doll", 3.0, "AW03 Paper Doll"),
        (r"(ss|spring.?summer).?05.*but.?beautiful|but.?beautiful", 2.5, "SS05 But Beautiful"),
        (r"(aw|fw).?05.*arts.?crafts|arts.*crafts", 2.5, "AW05 Arts & Crafts"),
        (r"(aw|fw).?06.*guru.?guru|guru", 2.5, "AW06 Guru Guru"),
        (r"languid|ss.?04", 2.2, "SS04 Languid"),
        (r"(aw|fw).?09.*earmuff|earmuff.?maniac", 2.0, "AW09 Earmuff Maniac"),
        (r"(ss|spring.?summer).?09.*neoboy", 2.0, "SS09 Neoboy"),

        # Collaborations
        (r"supreme.*undercover|undercover.*supreme", 2.0, "Supreme collab"),

        # Archive era
        (r"(aw|fw|ss).?(9[89]|0[0-9])", 1.5, "Archive 1998-2009"),
    ],

    # === HELMUT LANG ===
    "helmut lang": [
        # Iconic pieces
        (r"astro.?(biker|jacket)|astro.?moto", 4.0, "Astro Biker Jacket"),
        (r"bondage|strap|harness", 2.5, "Bondage/Strap piece"),
        (r"flak.?jacket|flak.?vest", 3.0, "Flak Jacket"),
        (r"bulletproof|ballistic", 3.0, "Bulletproof Vest"),
        (r"painter.?jean|painter.?denim|paint.?splatter", 2.5, "Painter Jeans"),
        (r"reflective", 2.0, "Reflective piece"),
        (r"archive.?denim|raw.?denim", 1.8, "Archive Denim"),

        # Era multipliers (pre-2005 when he left)
        (r"(aw|fw|ss).?(9[789]|0[0-4])|199[789]|200[0-4]", 2.0, "Helmut Lang era (pre-2005)"),
    ],

    # === RICK OWENS ===
    "rick owens": [
        # Runway pieces
        (r"runway|mainline(?!.*drkshdw)", 1.5, "Mainline/Runway"),
        (r"moody|fw.?08.?moody", 2.0, "FW08 Moody"),
        (r"sphinx|ss.?15.?sphinx", 1.8, "SS15 Sphinx"),
        (r"faun|ss.?16.?faun", 1.8, "SS16 Faun"),
        (r"glitter|fw.?17.?glitter", 1.8, "FW17 Glitter"),
        (r"babel|fw.?19.?babel", 1.6, "FW19 Babel"),
        (r"gethsemane|ss.?21", 1.5, "SS21 Gethsemane"),

        # Iconic pieces
        (r"leather.?jacket|stooges|intarsia", 1.8, "Leather piece"),
        (r"dust.?bag|dust.?coat|dust.?long", 1.6, "Dust piece"),
        (r"memphis|mem", 1.5, "Memphis piece"),

        # Footwear
        (r"geobasket|geo", 1.4, "Geobasket"),
        (r"ramones|ramone", 1.3, "Ramones"),
        (r"kiss.?boot", 1.5, "Kiss Boots"),
    ],

    # === MAISON MARGIELA ===
    "margiela": [
        # Artisanal/couture
        (r"artisanal|line.?0|couture|haute", 3.0, "Artisanal/Line 0"),
        (r"replica|gat|german.?army", 1.8, "Replica/GAT"),

        # Martin era (pre-2009)
        (r"(aw|fw|ss).?(9[789]|0[0-8])|martin.?margiela", 2.0, "Martin era (pre-2009)"),
        (r"flat.?tabi|split.?toe|tabi(?!.*socks)", 1.8, "Tabi piece"),
        (r"deconstructed|deconstruct", 1.5, "Deconstructed"),
        (r"painted|hand.?painted", 1.6, "Hand-painted"),
    ],

    # === COMME DES GARCONS ===
    "comme des garcons": [
        # Bump collection
        (r"(ss|spring.?summer).?97.*bump|bump|lumps", 3.5, "SS97 Body Meets Dress/Lumps"),

        # Iconic collections
        (r"broken.?bride|ss.?05", 2.0, "SS05 Broken Bride"),
        (r"punk.?(aw|fw).?06|seditionaries.?06", 2.0, "AW06 Punk"),
        (r"(aw|fw|ss).?(8[0-9]|9[0-9])", 1.8, "1980s-1990s archive"),

        # Collaborations
        (r"supreme|sup.?cdg", 1.8, "Supreme collab"),
        (r"nike|air.?force", 1.5, "Nike collab"),
    ],

    # === YOHJI YAMAMOTO ===
    "yohji yamamoto": [
        # Pour Homme era
        (r"pour.?homme|y'?s.?for.?men", 1.5, "Pour Homme"),
        (r"(aw|fw|ss).?(8[0-9]|9[0-9])|198[0-9]|199[0-9]", 2.0, "1980s-1990s archive"),

        # Iconic elements
        (r"draped|drape|asymmetr", 1.4, "Draped piece"),
        (r"black.?crow", 1.5, "Black Crow era"),
    ],

    # === ISSEY MIYAKE ===
    "issey miyake": [
        (r"pleats.?please|pp", 1.3, "Pleats Please"),
        (r"homme.?pliss[eé]|hp", 1.4, "Homme Plissé"),
        (r"(aw|fw|ss).?(8[0-9]|9[0-9])", 1.8, "1980s-1990s archive"),
        (r"parachute|nylon.?bomber", 1.5, "Parachute/Bomber"),
    ],

    # === DIOR HOMME ===
    "dior homme": [
        # Hedi Slimane era (2000-2007) - all highly sought
        (r"(aw|fw).?04|fall.?winter.?2004", 2.5, "AW04 (Hedi)"),
        (r"(aw|fw).?05|fall.?winter.?2005", 2.5, "AW05 (Hedi)"),
        (r"(aw|fw).?06|fall.?winter.?2006", 2.5, "AW06 (Hedi)"),
        (r"(aw|fw).?07|fall.?winter.?2007", 2.5, "AW07 (Hedi)"),
        (r"(ss|spring.?summer).?0[4-7]", 2.2, "SS04-07 (Hedi)"),
        (r"hedi|slimane", 2.5, "Hedi Slimane era"),
        (r"navigate|victim.?fashion|victim|votc", 2.5, "Victim of the Crime"),

        # Iconic pieces
        (r"clawmark|claw.?mark", 3.0, "Clawmark"),
        (r"bee|bumble", 2.0, "Bee motif"),
        (r"safety.?pin", 2.2, "Safety pin piece"),
        (r"mij|made.?in.?japan", 1.5, "Made in Japan"),
    ],

    # === SAINT LAURENT ===
    "saint laurent": [
        # Hedi era (2012-2016)
        (r"hedi|slimane", 2.0, "Hedi Slimane era"),
        (r"(aw|fw|ss).?(1[2-6])|201[2-6]", 1.8, "Hedi era 2012-2016"),
        (r"wyatt|jodhpur|chelsea", 1.5, "Boots"),
        (r"teddy|varsity", 1.6, "Teddy/Varsity"),
        (r"l0[1-9]|l17", 1.8, "L01/Leather jacket"),
    ],

    # === JEAN PAUL GAULTIER ===
    "jean paul gaultier": [
        (r"cyber|cyb[eè]r", 2.5, "Cyber collection"),
        (r"mesh|tattoo|tribal", 2.0, "Mesh/Tattoo print"),
        (r"femme|homme", 1.5, "Gaultier Femme/Homme"),
        (r"(aw|fw|ss).?(8[0-9]|9[0-9])", 2.0, "1980s-1990s archive"),
        (r"face.?print|portrait", 2.0, "Face print"),
        (r"soleil|sol[eè]il|sun", 1.5, "Soleil line"),
    ],

    # === VIVIENNE WESTWOOD ===
    "vivienne westwood": [
        (r"sedition|seditionaries", 3.0, "Seditionaries"),
        (r"gold.?label", 1.8, "Gold Label"),
        (r"red.?label", 1.3, "Red Label"),
        (r"anglomania", 1.4, "Anglomania"),
        (r"worlds.?end|world'?s.?end", 2.5, "World's End"),
        (r"(aw|fw|ss).?(7[0-9]|8[0-9])", 2.5, "1970s-1980s archive"),
        (r"bondage|punk|safety", 2.0, "Punk/Bondage"),
    ],

    # === SUPREME ===
    "supreme": [
        (r"box.?logo|bogo", 2.0, "Box Logo"),
        (r"louis.?vuitton|lv", 3.0, "LV collab"),
        (r"comme|cdg", 1.8, "CDG collab"),
        (r"undercover|uc", 1.6, "Undercover collab"),
        (r"nike|air.?force|dunk", 1.5, "Nike collab"),
        (r"north.?face|tnf", 1.5, "TNF collab"),
        (r"(19)?9[0-9]|early.?2000", 1.8, "1990s-early 2000s"),
    ],

    # === CHROME HEARTS ===
    "chrome hearts": [
        (r"cemetery|cross", 1.3, "Cemetery/Cross"),
        (r"leather", 1.4, "Leather piece"),
        (r"japan|tokyo", 1.3, "Japan exclusive"),
        (r"vintage|90s|2000s", 1.5, "Vintage"),
    ],

    # =========================================================================
    # JAPANESE ARCHIVE
    # =========================================================================

    # === HYSTERIC GLAMOUR ===
    "hysteric glamour": [
        # Grails — 90s Courtney Love era and iconic graphics
        (r"courtney.?love|kinky", 3.5, "Courtney Love era piece"),
        (r"(19)?9[0-4].*hysteric|hysteric.*(19)?9[0-4]", 3.0, "Early 90s archive"),
        (r"guitar.?girl|his.?her|woman.?tongue", 2.8, "Iconic graphic"),

        # Strong vintage prints
        (r"(19)?9[5-9]|199[5-9]", 2.2, "Late 90s archive"),
        (r"skull|snake|dragon|devil|demon", 1.8, "Vintage graphic motif"),
        (r"sonic.?youth|iggy.?pop|joey.?ramone|ramones|blondie", 2.5, "Band collab/tribute"),

        # General archive
        (r"200[0-5]|(aw|fw|ss).?0[0-5]", 1.5, "Early 2000s archive"),
        (r"vintage|archive|og", 1.4, "Archive piece"),
    ],

    # === KAPITAL ===
    "kapital": [
        # Grail techniques and lines
        (r"century.?denim|century", 3.0, "Century Denim"),
        (r"boro|sashiko", 2.5, "Boro/Sashiko piece"),
        (r"kountry", 2.0, "Kountry line"),
        (r"bone", 2.0, "Bone piece"),
        (r"kakashi|ring.?coat", 2.0, "Kakashi/Ring Coat"),

        # Strong pieces
        (r"damask|patchwork", 1.8, "Patchwork piece"),
        (r"skeleton|skull", 1.6, "Skeleton motif"),
        (r"denim.?jacket|trucker|westerner", 1.5, "Denim outerwear"),

        # Rare/early
        (r"200[0-5]|(aw|fw|ss).?0[0-5]", 1.4, "Early 2000s Kapital"),
    ],

# === WTAPS ===
    "wtaps": [
        # Iconic lines
        (r"jungle|jgr|jngl", 2.5, "Jungle piece"),
        (r"desert|dsr", 2.0, "Desert piece"),
        (r"buds|bud.?ls|buds.?01", 2.0, "Buds shirt"),

        # Collaborations
        (r"vans.*wtaps|wtaps.*vans", 2.0, "Vans collab"),
        (r"bape.*wtaps|wtaps.*bape|apes", 2.2, "BAPE collab"),
        (r"supreme.*wtaps|wtaps.*supreme", 2.0, "Supreme collab"),
        (r"neighborhood.*wtaps|wtaps.*neighborhood", 1.8, "Neighborhood collab"),

        # Early archive
        (r"(19)?9[89]|199[89]|200[0-5]|(aw|fw|ss).?0[0-5]", 1.8, "Early archive (pre-2005)"),
        (r"200[6-9]|(aw|fw|ss).?0[6-9]", 1.3, "2000s archive"),
    ],

    # === NEIGHBORHOOD ===
    "neighborhood": [
        # Iconic motifs and lines
        (r"savage|svge", 2.5, "Savage piece"),
        (r"skull|skulls|skull.?and.?bones", 2.0, "Skulls piece"),
        (r"specimen|speci?men", 2.0, "Specimen piece"),
        (r"craft.?with.?pride|cwp", 1.6, "Craft With Pride"),

        # Collaborations
        (r"vans.*neighborhood|neighborhood.*vans|nbhd.*vans", 2.0, "Vans collab"),
        (r"adidas.*neighborhood|neighborhood.*adidas|nbhd.*adidas", 1.8, "adidas collab"),
        (r"wtaps.*neighborhood|neighborhood.*wtaps", 1.8, "WTAPS collab"),
        (r"bape.*neighborhood|neighborhood.*bape", 2.0, "BAPE collab"),

        # Early archive
        (r"(19)?9[89]|199[89]|200[0-5]|(aw|fw|ss).?0[0-5]", 1.8, "Early archive (pre-2005)"),
        (r"200[6-9]|(aw|fw|ss).?0[6-9]", 1.3, "2000s archive"),
    ],

    # === BAPE / A BATHING APE ===
    "bape": [
        # Grails — Nigo era and iconic collab
        (r"kaws.*bape|bape.*kaws", 3.5, "KAWS collab"),
        (r"1st.?camo|first.?camo|og.?camo", 2.5, "1st Camo (OG)"),
        (r"shark.?hood|shark.?full.?zip|wgm", 2.0, "Shark Hoodie"),
        (r"baby.?milo|milo", 1.8, "Baby Milo piece"),

        # Nigo era (pre-2013)
        (r"nigo|200[0-9]|199[89]", 2.0, "Nigo era"),
        (r"bapesta|bape.?sta", 1.8, "Bapesta"),
        (r"tiger|tiger.?hood", 1.6, "Tiger piece"),
        (r"abc.?camo", 1.5, "ABC Camo"),

        # Collabs
        (r"stussy.*bape|bape.*stussy", 1.8, "Stussy collab"),
        (r"undefeated|undftd", 1.5, "Undefeated collab"),
        (r"mastermind|mmj", 2.0, "Mastermind collab"),

        # General vintage
        (r"archive|vintage|90s|early", 1.5, "Vintage BAPE"),
    ],

    # === HUMAN MADE ===
    "human made": [
        # Early/Nigo era
        (r"nigo", 2.0, "Nigo era"),
        (r"200[0-9]|(aw|fw|ss).?0[0-9]", 1.8, "2000s archive"),
        (r"heart.?logo|heart", 1.4, "Heart logo piece"),

        # Collabs
        (r"girls.?don.?t.?cry|gdc|verdy", 2.0, "Girls Don't Cry collab"),
        (r"adidas.*human.?made|human.?made.*adidas", 1.6, "adidas collab"),
        (r"lil.?uzi|kid.?cudi|pharrell", 1.5, "Celebrity collab"),

        # General
        (r"vintage|archive|early", 1.4, "Archive piece"),
    ],

    # === JULIUS ===
    "julius": [
        # Gas mask era — the most sought-after
        (r"gas.?mask|gasmask", 3.5, "Gas Mask era piece"),
        (r"_7|_seven|seven.?line", 2.5, "_7 line"),

        # Strong archive seasons
        (r"(aw|fw).?0[5-9]|fall.?winter.?200[5-9]", 2.0, "AW05-09 archive"),
        (r"(ss|spring.?summer).?0[5-9]", 1.8, "SS05-09 archive"),
        (r"200[4-9]|201[0-2]", 1.5, "2000s-early 2010s archive"),

        # Iconic pieces
        (r"leather.?jacket|lamb|calf|horse", 1.8, "Leather piece"),
        (r"destroy|destruct|deconstr", 1.5, "Destroy/Deconstructed"),
        (r"cargo|tactical|military", 1.4, "Military/Tactical piece"),
        (r"twisted|spiral", 1.3, "Twisted/Spiral piece"),
    ],

    # === SACAI ===
    "sacai": [
        # Nike collabs — grail sneakers
        (r"ldwaffle|ld.?waffle", 2.5, "Nike LDWaffle"),
        (r"vaporwaffle|vapor.?waffle", 2.2, "Nike Vaporwaffle"),
        (r"blazer.*sacai|sacai.*blazer", 2.0, "Nike Blazer collab"),
        (r"nike.*sacai|sacai.*nike", 1.8, "Nike collab"),

        # Strong pieces
        (r"hybrid|layered|deconstr", 1.5, "Hybrid/Layered piece"),
        (r"early|200[0-9]|(aw|fw|ss).?0[0-9]", 1.5, "2000s archive"),
        (r"knit|knitwear|cable", 1.4, "Archive knit"),

        # Other collabs
        (r"undercover.*sacai|sacai.*undercover", 1.8, "Undercover collab"),
        (r"porter.*sacai|sacai.*porter", 1.5, "Porter collab"),
    ],

    # === JUNYA WATANABE ===
    "junya watanabe": [
        # Grails — patchwork and reconstructed
        (r"patchwork", 3.0, "Patchwork piece"),
        (r"levi.?s.*reconstruct|reconstruct.*levi|levi.*junya|junya.*levi", 2.8, "Levi's reconstructed"),
        (r"comme.*junya|junya.*comme|cdg.*junya", 1.8, "CdG collab piece"),

        # Iconic techniques
        (r"reconstruct|remade|rebuild", 2.5, "Reconstructed piece"),
        (r"cape|poncho|trench.*hybrid", 1.8, "Outerwear piece"),
        (r"camo|camouflage|military", 1.5, "Camo/Military piece"),

        # Archive
        (r"(aw|fw|ss).?(9[89]|0[0-9])|199[89]|200[0-9]", 1.8, "Archive (late 90s-2000s)"),
        (r"man|junya.*man", 1.3, "Junya Watanabe MAN"),

        # Collabs
        (r"carhartt.*junya|junya.*carhartt", 1.6, "Carhartt collab"),
        (r"brooks.?brothers|north.?face.*junya|junya.*north.?face", 1.6, "Brand collab"),
    ],

    # === WACKO MARIA ===
    "wacko maria": [
        # Grails — iconic prints
        (r"tim.?lehi", 2.5, "Tim Lehi collab"),
        (r"leopard|leopardo", 2.0, "Leopard piece"),
        (r"hawaiian|hawaii|aloha", 1.8, "Hawaiian shirt"),
        (r"guilty.?part", 1.8, "Guilty Parties piece"),

        # Collabs
        (r"neck.?face|neckface", 2.2, "Neckface collab"),
        (r"basquiat", 2.0, "Basquiat collab"),
        (r"larry.?clark", 2.0, "Larry Clark collab"),

        # Motifs
        (r"bob.?marley|tupac|biggie|notorious", 1.8, "Music tribute"),
        (r"wolf.?head|wolf's.?head", 1.5, "Wolf's Head piece"),
        (r"python|snakeskin|croc|alligator", 1.5, "Exotic material"),

        # Archive
        (r"200[0-9]|(aw|fw|ss).?0[0-9]", 1.4, "2000s archive"),
    ],

    # === CAV EMPT ===
    "cav empt": [
        # Early drops and graphic grails
        (r"201[3-6]|(aw|fw|ss).?1[3-6]", 2.0, "Early Cav Empt (2013-2016)"),
        (r"icon|overdye|heavy.?graph", 1.8, "Graphic heavy piece"),

        # Iconic pieces
        (r"pullover|pull.?over|anorak", 1.5, "Pullover/Anorak"),
        (r"fleece|boa", 1.4, "Fleece piece"),
        (r"noise|static|glitch", 1.5, "Noise/Static graphic"),

        # Collabs
        (r"nike.*c\.?e|c\.?e.*nike", 1.8, "Nike collab"),

        # General archive
        (r"archive|early|og", 1.3, "Archive piece"),
    ],

    # === KANSAI YAMAMOTO ===
    "kansai yamamoto": [
        # Ultra-rare — Bowie connection and 70s/80s
        (r"bowie|david.?bowie|ziggy|aladdin.?sane", 4.0, "Bowie collab/era piece"),
        (r"(19)?7[0-9]|197[0-9]", 3.5, "1970s piece"),
        (r"(19)?8[0-9]|198[0-9]", 3.0, "1980s piece"),

        # Iconic motifs
        (r"kabuki|samurai|koi|tiger|dragon", 2.5, "Traditional Japanese motif"),
        (r"jumpsuit|body.?suit|knit.?body", 2.5, "Bodysuit/Jumpsuit"),

        # General
        (r"(19)?9[0-9]|199[0-9]", 2.0, "1990s piece"),
        (r"vintage|archive|rare", 2.0, "Vintage Kansai"),
    ],

    # === NEEDLES ===
    "needles": [
        # Grails — rebuild and iconic pieces
        (r"rebuild|re.?build|reconstructed", 2.5, "Rebuild piece"),
        (r"track.?pant|track.?jacket|narrow.?track", 2.0, "Track pants/jacket"),
        (r"papillon|butterfly", 2.0, "Papillon/Butterfly piece"),

        # Iconic patterns
        (r"paisley|bandana.?print", 1.6, "Paisley/Bandana"),
        (r"leopard|animal.?print", 1.5, "Leopard/Animal print"),
        (r"7.?cut|seven.?cut", 2.2, "7 Cuts piece"),

        # Collabs
        (r"awge.*needles|needles.*awge|asap.?rocky", 2.0, "AWGE collab"),

        # Archive
        (r"200[0-9]|(aw|fw|ss).?0[0-9]", 1.5, "2000s archive"),
    ],

    # === TAKAHIROMIYASHITA THESOLOIST ===
    "takahiromiyashita thesoloist": [
        # s.0000 era grails
        (r"s\.?0+\d+|s\.?000", 3.0, "s.0000 era piece"),
        (r"number.?\(?n\)?ine.*soloist|soloist.*number", 2.5, "Number (N)ine crossover"),

        # Early pieces
        (r"201[0-5]|(aw|fw|ss).?1[0-5]", 2.0, "Early Soloist (2010-2015)"),
        (r"(aw|fw).?0[0-9]|200[0-9]", 2.5, "Pre-Soloist/N(N) era"),

        # Iconic details
        (r"musician|guitar|punk", 1.8, "Musician-inspired piece"),
        (r"leather|biker|rider", 1.6, "Leather piece"),
        (r"medical|cross.?patch", 1.5, "Medical motif"),

        # Collabs
        (r"converse.*soloist|soloist.*converse", 1.8, "Converse collab"),
    ],

    # =========================================================================
    # EUROPEAN AVANT-GARDE
    # =========================================================================

    # === ANN DEMEULEMEESTER ===
    "ann demeulemeester": [
        # Grails — 90s Ann era and signature pieces
        (r"(aw|fw|ss).?(9[1-9])|199[1-9]", 3.0, "1990s Ann era"),
        (r"200[0-3]|(aw|fw|ss).?0[0-3]", 2.5, "Early 2000s archive"),

        # Iconic pieces
        (r"lace.?up.*boot|back.?lace|triple.?lace", 2.8, "Lace-up boots"),
        (r"feather|plume", 2.5, "Feather piece"),
        (r"corset|laced.?corset", 2.2, "Corset piece"),

        # Signature details
        (r"drape|draped|asymmetr", 1.6, "Draped/Asymmetric piece"),
        (r"leather|suede.?jacket", 1.5, "Leather piece"),
        (r"ribbon|tie|poet", 1.4, "Ribbon/Poet detail"),

        # Archive
        (r"200[4-9]|(aw|fw|ss).?0[4-9]", 1.8, "Mid-2000s archive"),
        (r"201[0-3]|(aw|fw|ss).?1[0-3]", 1.5, "2010-2013 archive (Ann's last)"),
    ],

    # === DRIES VAN NOTEN ===
    "dries van noten": [
        # Grails — 90s floral and embroidered
        (r"(aw|fw|ss).?(9[0-9])|199[0-9]", 2.5, "1990s archive"),
        (r"floral|flower|botanical", 2.0, "Floral print piece"),
        (r"embroid|beaded|sequin", 2.2, "Embroidered/Beaded piece"),

        # Iconic motifs
        (r"velvet|brocade|jacquard", 1.8, "Velvet/Brocade piece"),
        (r"ethnic|tribal|ikat|paisley", 1.6, "Ethnic print piece"),
        (r"leopard|animal.?print", 1.5, "Animal print"),

        # Strong archive
        (r"200[0-5]|(aw|fw|ss).?0[0-5]", 1.8, "Early 2000s archive"),
        (r"200[6-9]|(aw|fw|ss).?0[6-9]", 1.4, "Late 2000s archive"),

        # Collabs
        (r"vans.*dries|dries.*vans", 1.6, "Vans collab"),
    ],

    # === CAROL CHRISTIAN POELL ===
    "carol christian poell": [
        # Nearly everything is grail-tier — CCP is ultra rare
        (r"object.?dye|cold.?dye|dip.?dye", 3.5, "Object-dyed piece"),
        (r"prosthetic|prosthe", 4.0, "Prosthetic piece"),
        (r"dead.?end|dead\.?end", 3.5, "Dead End piece"),

        # Iconic pieces
        (r"tornado|spiral.?zip", 3.0, "Tornado zip piece"),
        (r"leather|horse|kangaroo|bison", 2.5, "Leather piece"),
        (r"boot|derby|shoe|footwear", 2.5, "Footwear"),

        # All archive is valuable
        (r"(aw|fw|ss).?(9[89]|0[0-9])|199[89]|200[0-9]", 2.5, "Archive piece"),
        (r"ccp", 2.0, "CCP piece"),
    ],

    # === BORIS BIDJAN SABERI ===
    "boris bidjan saberi": [
        # Grails — blood and early archive
        (r"blood|blood.?stain|blood.?dye", 3.5, "Blood-stained/dyed piece"),
        (r"200[7-9]|201[0-3]|(aw|fw|ss).?0[7-9]|(aw|fw|ss).?1[0-3]", 2.2, "Early BBS archive"),

        # Iconic pieces
        (r"leather|horse|calf.?leather", 2.0, "Leather piece"),
        (r"object.?dye|hand.?dye|cold.?dye", 2.5, "Object-dyed piece"),
        (r"j[0-9]+|p[0-9]+|s[0-9]+", 1.5, "Numbered piece"),

        # Materials/details
        (r"vinyl|coated|wax", 1.6, "Coated/Waxed piece"),
        (r"knit|ribbed|ribbing", 1.4, "Knit piece"),
        (r"bbs|bbs11", 1.3, "BBS piece"),
    ],

    # === HUSSEIN CHALAYAN ===
    "hussein chalayan": [
        # Legendary conceptual pieces
        (r"coffee.?table|table.?dress", 4.0, "Coffee Table Dress"),
        (r"airmail|air.?mail|paper.?dress", 3.5, "Airmail dress"),
        (r"led|light.?up|illuminate", 3.0, "LED/Light-up piece"),
        (r"airplane|aeroplane.?dress", 3.5, "Airplane dress"),

        # Tech and conceptual pieces
        (r"dissolv|dissol|sugar.?glass", 3.0, "Dissolving piece"),
        (r"remote.?control|mechanical", 3.0, "Mechanical/Tech piece"),
        (r"video|screen", 2.5, "Video/Screen piece"),

        # Archive
        (r"(aw|fw|ss).?(9[5-9]|0[0-9])|199[5-9]|200[0-9]", 2.0, "Archive piece"),
        (r"runway|show.?piece", 2.0, "Runway piece"),
    ],

    # === WALTER VAN BEIRENDONCK ===
    "walter van beirendonck": [
        # Wild & Lethal Trash era
        (r"wild.?(?:&|and)?.?lethal.?trash|w\.?l\.?t|wlt", 3.0, "Wild & Lethal Trash"),
        (r"(aw|fw|ss).?(9[0-9])|199[0-9]", 2.5, "1990s archive"),

        # Iconic motifs
        (r"alien|monster|mutant|cyclops", 2.0, "Creature motif"),
        (r"print|graphic|all.?over", 1.6, "Graphic print piece"),

        # Archive
        (r"200[0-9]|(aw|fw|ss).?0[0-9]", 1.8, "2000s archive"),
    ],

    # === CRAIG GREEN ===
    "craig green": [
        # Iconic silhouettes
        (r"quilted|quilt", 2.0, "Quilted piece"),
        (r"laced|lacing|hole.?detail|cut.?out", 2.2, "Laced/Cut-out piece"),
        (r"worker|workwear", 1.5, "Worker piece"),

        # Early archive
        (r"201[2-6]|(aw|fw|ss).?1[2-6]", 1.8, "Early Craig Green (2012-2016)"),
        (r"201[7-9]|(aw|fw|ss).?1[7-9]", 1.4, "2017-2019 archive"),

        # Collabs
        (r"moncler.*craig|craig.*moncler", 1.6, "Moncler Genius collab"),
        (r"adidas.*craig|craig.*adidas", 1.5, "adidas collab"),
        (r"champion.*craig|craig.*champion", 1.4, "Champion collab"),
    ],

    # === PAUL HARNDEN ===
    "paul harnden": [
        # Everything Paul Harnden is rare/handmade — across the board premium
        (r"mac|macintosh|rain.?coat", 3.0, "Mac/Raincoat"),
        (r"shoe|boot|derby|oxford", 3.0, "Handmade footwear"),
        (r"blazer|jacket|coat", 2.8, "Handmade outerwear"),
        (r"shirt|trouser|pant", 2.5, "Handmade piece"),
        (r"linen|cotton|wool|tweed", 2.0, "Handmade fabric piece"),

        # Any Paul Harnden is a premium
        (r"paul.?harnden|harnden", 2.0, "Paul Harnden piece"),
    ],

    # === GEOFFREY B SMALL ===
    "geoffrey b small": [
        # Ultra limited handmade — everything commands premium
        (r"one.?of|1.?of|limited|handmade|hand.?made", 3.5, "Handmade limited piece"),
        (r"coat|jacket|blazer|overcoat", 3.0, "Handmade outerwear"),
        (r"shirt|trouser|pant|vest", 2.5, "Handmade piece"),
        (r"cashmere|silk|linen", 2.5, "Premium fabric piece"),

        # Any GBS is premium
        (r"geoffrey|gbs|g\.?b\.?s", 2.0, "Geoffrey B Small piece"),
    ],

    # =========================================================================
    # LUXURY HOUSES (Creative Director eras)
    # =========================================================================

    # === ALEXANDER MCQUEEN ===
    "alexander mcqueen": [
        # Lee McQueen era grails (pre-2010)
        (r"bumster|low.?rise.*mcqueen", 3.5, "Bumster"),
        (r"plato.?s?.?atlantis|atlantis", 3.5, "Plato's Atlantis (SS10)"),
        (r"savage.?beauty", 3.0, "Savage Beauty"),
        (r"skull.?scarf|skull.?silk", 2.5, "Skull Scarf"),
        (r"horn.?of.?plenty|horn", 2.5, "Horn of Plenty (AW09)"),
        (r"jack.?the.?ripper|ripper", 3.0, "Jack the Ripper (1992 MA)"),
        (r"highland.?rape", 3.0, "Highland Rape (AW95)"),

        # Lee McQueen era (pre-2010)
        (r"(aw|fw|ss).?(9[0-9])|199[0-9]", 3.0, "1990s McQueen"),
        (r"(aw|fw|ss).?0[0-9]|200[0-9]", 2.5, "2000s McQueen (Lee era)"),
        (r"lee.?mcqueen|lee.?alexander", 2.5, "Lee McQueen era"),

        # Iconic pieces
        (r"armadillo|alien.?shoe", 3.5, "Armadillo shoe"),
        (r"knuckle|clutch.*skull|skull.*clutch", 2.0, "Knuckle/Skull clutch"),
        (r"corset|lace.?up", 1.8, "Corset piece"),
        (r"runway|show.?piece|sample", 2.0, "Runway/Show piece"),
    ],

    # === THIERRY MUGLER ===
    "thierry mugler": [
        # Grails — power silhouettes and insects
        (r"insect|butterfly.*mugler|beetle|spider|chimera", 3.5, "Insect Collection"),
        (r"robot|metal|chrome|futur", 3.0, "Robot/Futuristic piece"),
        (r"power.?suit|structured.?shoulder", 2.8, "Power Suit"),
        (r"alien|angel", 2.0, "Alien/Angel motif"),
        (r"corset|bustier|bodysuit", 2.5, "Corset/Bustier"),

        # Vintage era
        (r"(19)?8[0-9]|198[0-9]|eighties", 3.0, "1980s archive"),
        (r"(19)?9[0-9]|199[0-9]", 2.5, "1990s archive"),
        (r"200[0-3]", 2.0, "Early 2000s archive"),
        (r"couture|haute", 3.0, "Couture piece"),

        # General
        (r"vintage|archive|og", 2.0, "Vintage Mugler"),
        (r"runway|show.?piece", 2.5, "Runway piece"),
    ],

    # === BALENCIAGA ===
    "balenciaga": [
        # Nicolas Ghesquiere era (1997-2012)
        (r"ghesqui[eè]re|nicolas", 2.5, "Nicolas Ghesquiere era"),
        (r"city.?bag|motorcycle.?bag|classic.?city", 2.0, "City/Motorcycle bag"),
        (r"lariat|le.?dix", 2.0, "Lariat/Le Dix piece"),
        (r"(aw|fw|ss).?(9[789]|0[0-9]|1[0-2])|199[789]|200[0-9]|201[0-2]", 2.0, "Ghesquiere era archive"),

        # Demna era (2015+) — iconic pieces
        (r"triple.?s", 2.0, "Triple S"),
        (r"track(?!.*suit)|track.?runner", 1.6, "Track Runner"),
        (r"speed.?trainer|speed.?sock|speed.?knit", 1.5, "Speed Trainer"),
        (r"destroyed|distressed.*sneaker|paris.?sneaker", 1.8, "Destroyed sneaker"),
        (r"demna|gvasalia", 1.8, "Demna era"),

        # Collabs
        (r"gucci.*balenciaga|balenciaga.*gucci|hacker", 2.0, "Gucci Hacker collab"),
        (r"adidas.*balenciaga|balenciaga.*adidas", 1.5, "adidas collab"),

        # Archive
        (r"cristobal|vintage.*balenciaga|195[0-9]|196[0-9]", 3.0, "Cristobal era vintage"),
    ],

    # === GIVENCHY ===
    "givenchy": [
        # Riccardo Tisci era (2005-2017) — peak hype
        (r"tisci|riccardo", 2.2, "Riccardo Tisci era"),
        (r"rottweiler|rottw", 2.5, "Rottweiler piece"),
        (r"shark|jaws", 2.0, "Shark piece"),
        (r"bambi|fawn|deer", 2.0, "Bambi piece"),
        (r"star|stars.*givenchy|givenchy.*star", 1.6, "Star motif"),

        # Tisci era seasons
        (r"(aw|fw|ss).?(0[5-9]|1[0-7])|200[5-9]|201[0-7]", 1.8, "Tisci era (2005-2017)"),

        # Iconic
        (r"nightingale|antigona|pandora", 1.5, "Iconic bag"),
        (r"runway|show.?piece|couture", 2.0, "Runway/Couture piece"),

        # Vintage Givenchy
        (r"audrey|vintage|196[0-9]|197[0-9]", 2.5, "Vintage Givenchy"),
    ],

    # === GUCCI ===
    "gucci": [
        # Tom Ford era (1994-2004) — insanely hyped
        (r"tom.?ford", 2.5, "Tom Ford era"),
        (r"(aw|fw|ss).?(9[4-9]|0[0-4]).*(?:gucci|ford)|(?:gucci|ford).*(aw|fw|ss).?(9[4-9]|0[0-4])", 2.2, "Tom Ford era collection"),
        (r"199[4-9].*(?:gucci|ford)|(?:gucci|ford).*199[4-9]", 2.2, "Tom Ford 90s"),
        (r"200[0-4].*(?:gucci|ford)|(?:gucci|ford).*200[0-4]", 2.0, "Tom Ford 2000s"),

        # Alessandro Michele era (2015-2022)
        (r"alessandro|michele", 1.8, "Alessandro Michele era"),
        (r"(aw|fw|ss).?(1[5-9]|2[0-2])", 1.5, "Michele era (2015-2022)"),

        # Iconic pieces
        (r"horse.?bit|horsebit|bamboo", 2.0, "Horsebit/Bamboo piece"),
        (r"jackie|jackie.?bag|jackie.?o", 1.8, "Jackie bag"),
        (r"web.?stripe|sherry", 1.3, "Web Stripe"),
        (r"flora|floral.*gucci|gucci.*flora", 1.5, "Flora print"),

        # Collabs
        (r"dapper.?dan|dapper", 2.0, "Dapper Dan collab"),
        (r"north.?face.*gucci|gucci.*north.?face|tnf.*gucci", 1.8, "TNF collab"),
        (r"palace.*gucci|gucci.*palace", 1.6, "Palace collab"),

        # Vintage
        (r"vintage|198[0-9]|197[0-9]|old.?gucci", 2.0, "Vintage Gucci"),
    ],

    # === PRADA ===
    "prada": [
        # 90s nylon era — the holy grail
        (r"linea.?rossa|red.?line|sport.*prada|prada.*sport", 2.5, "Linea Rossa/Sport"),
        (r"199[0-9].*nylon|nylon.*199[0-9]|90s.*nylon", 2.5, "90s Nylon"),
        (r"(fw|aw).?99.*flame|flame.*99|flame.?print", 3.0, "FW99 Flame"),

        # Strong archive
        (r"199[0-9]|(aw|fw|ss).?9[0-9]", 2.0, "1990s Prada"),
        (r"200[0-5]|(aw|fw|ss).?0[0-5]", 1.6, "Early 2000s archive"),

        # Iconic items
        (r"nylon|tessuto|vela", 1.5, "Nylon piece"),
        (r"re.?nylon|re.?edition|re-?edition", 1.4, "Re-Nylon/Re-Edition"),
        (r"bowling|frame.?bag|cleo|galleria", 1.3, "Iconic bag"),
        (r"cloudbust|thunder", 1.5, "Cloudbust/Thunder sneaker"),

        # Collabs
        (r"adidas.*prada|prada.*adidas", 1.5, "adidas collab"),

        # Vintage
        (r"vintage|archive|made.?in.?italy.*prada", 1.5, "Vintage Prada"),
    ],

    # === CELINE ===
    "celine": [
        # Phoebe Philo era (2008-2018) — insane demand
        (r"phoebe|philo|old.?c[eé]line|old.?celine", 3.0, "Phoebe Philo era"),
        (r"(aw|fw|ss).?(0[8-9]|1[0-8]).*(?:celine|philo)|(?:celine|philo).*(aw|fw|ss).?(0[8-9]|1[0-8])", 2.5, "Philo era collection"),

        # Iconic Philo bags
        (r"box.?bag|classic.?box", 2.5, "Box Bag"),
        (r"luggage.?tote|luggage.?bag|phantom", 2.2, "Luggage/Phantom"),
        (r"belt.?bag", 1.8, "Belt Bag"),
        (r"trapeze", 1.8, "Trapeze"),
        (r"trio|cabas", 1.5, "Trio/Cabas"),

        # Philo era RTW
        (r"200[8-9]|201[0-8]", 2.0, "Philo era (2008-2018)"),
        (r"fur.?coat|shearling|mink.*celine|celine.*mink", 2.0, "Fur piece"),
        (r"power|wide.?leg|minimal", 1.5, "Philo-era silhouette"),

        # Pre-Philo vintage
        (r"vintage|199[0-9]|198[0-9]|michael.?kors", 1.5, "Vintage Celine"),
    ],

    # === LOUIS VUITTON ===
    "louis vuitton": [
        # Virgil Abloh era (2018-2021) — significant posthumous premium
        (r"virgil|abloh", 2.5, "Virgil Abloh era"),
        (r"(aw|fw|ss).?(1[89]|2[01]).*(?:virgil|abloh|lv)|(?:virgil|abloh).*(aw|fw|ss).?(1[89]|2[01])", 2.2, "Virgil era collection"),
        (r"lv.?trainer|lv.?408", 2.0, "LV Trainer (Virgil)"),
        (r"millionaires?|sunglasses.*virgil|virgil.*sunglasses", 2.0, "Millionaire sunglasses"),

        # Kim Jones era (2011-2018)
        (r"kim.?jones", 2.0, "Kim Jones era"),
        (r"(aw|fw|ss).?(1[1-8]).*kim|kim.*(aw|fw|ss).?(1[1-8])", 1.8, "Kim Jones era collection"),
        (r"fragment.*lv|lv.*fragment|hiroshi.*lv", 2.5, "Fragment collab"),
        (r"chapman", 1.8, "Chapman Brothers collab"),
        (r"supreme.*lv|lv.*supreme|vuitton.*supreme", 3.0, "Supreme collab"),

        # Marc Jacobs era
        (r"marc.?jacobs.*lv|lv.*marc.?jacobs", 2.0, "Marc Jacobs era"),
        (r"murakami|cherry|takashi|multicolor|monogram.?multi", 2.0, "Murakami collab"),
        (r"sprouse|graffiti|stephen.?sprouse", 2.0, "Stephen Sprouse collab"),

        # Iconic pieces
        (r"trunk|malle|hard.?case", 2.5, "Monogram Trunk"),
        (r"keepall|speedy|neverfull|alma", 1.3, "Classic bag"),
        (r"monogram|damier", 1.2, "Monogram/Damier"),

        # Vintage
        (r"vintage|197[0-9]|198[0-9]|199[0-9]", 1.5, "Vintage LV"),
    ],

    # === BOTTEGA VENETA ===
    "bottega veneta": [
        # Daniel Lee era (2018-2021) — massive hype
        (r"daniel.?lee", 2.5, "Daniel Lee era"),
        (r"pouch|the.?pouch|clutch.?pouch", 2.2, "The Pouch"),
        (r"puddle.?boot|puddle", 2.0, "Puddle Boot"),
        (r"lug.?boot|tire.?boot", 1.8, "Lug/Tire Boot"),
        (r"cassette|padded.?cassette", 1.8, "Cassette bag"),
        (r"chain.?cassette", 2.0, "Chain Cassette"),
        (r"salon.?0[1-3]|salon", 1.8, "Salon collection"),

        # Iconic pieces
        (r"intrecciato|woven|weave", 1.5, "Intrecciato piece"),
        (r"cabat|arco", 1.4, "Cabat/Arco"),
        (r"knot|clutch.*knot|knot.*clutch", 1.5, "Knot clutch"),

        # Tomas Maier era (2001-2018)
        (r"tomas.?maier", 1.6, "Tomas Maier era"),
        (r"vintage|200[0-9]|199[0-9]|archive", 1.5, "Archive Bottega"),
    ],

    # === VALENTINO ===
    "valentino": [
        # Pierpaolo Piccioli era
        (r"piccioli|pierpaolo", 1.8, "Pierpaolo Piccioli era"),
        (r"couture|haute|atelier", 2.5, "Couture piece"),

        # Iconic pieces
        (r"rockstud|rock.?stud", 1.5, "Rockstud"),
        (r"lace|guipure|macram[eé]", 1.8, "Lace piece"),
        (r"red.?dress|rosso|valentino.?red", 1.5, "Valentino Red"),
        (r"camo|camouflage.*valentino|valentino.*camo", 1.6, "Camo piece"),

        # Vintage
        (r"vintage|197[0-9]|198[0-9]|199[0-9]", 2.0, "Vintage Valentino"),
        (r"garavani.*vintage|vintage.*garavani", 2.2, "Vintage Garavani"),
        (r"runway|show.?piece", 1.8, "Runway piece"),
    ],

    # === FENDI ===
    "fendi": [
        # Grails — Baguette and Karl era
        (r"baguette", 2.0, "Baguette bag"),
        (r"karl|lagerfeld", 1.8, "Karl Lagerfeld era"),
        (r"monster.?eye|bug.?eye|monster", 1.8, "Monster Eyes"),
        (r"fendace|fendi.*versace|versace.*fendi", 2.5, "Fendace collab"),

        # Iconic pieces
        (r"peekaboo|peek.?a.?boo", 1.6, "Peekaboo bag"),
        (r"spy.?bag|spy", 1.5, "Spy bag"),
        (r"zucca|ff.?logo|double.?f", 1.4, "Zucca/FF logo"),
        (r"selleria", 1.5, "Selleria"),
        (r"fur|mink|fox.*fendi|fendi.*fur", 1.8, "Fur piece"),

        # Vintage
        (r"vintage|199[0-9]|198[0-9]|197[0-9]", 1.8, "Vintage Fendi"),
        (r"runway|show.?piece|couture", 2.0, "Runway/Couture piece"),
    ],

    # === VERSACE ===
    "versace": [
        # Gianni era (pre-1997) — the holy grail
        (r"gianni|pre.?1997|pre.?97", 3.0, "Gianni Versace era"),
        (r"safety.?pin|pin.?dress|medusa.?pin", 3.5, "Safety Pin dress"),
        (r"199[0-7]|(aw|fw|ss).?9[0-7]", 2.5, "1990s Gianni era"),

        # Iconic motifs
        (r"medusa|medusa.?head", 1.8, "Medusa"),
        (r"baroque|gold.?print|scroll", 2.0, "Baroque print"),
        (r"miami|south.?beach|palm|tropical", 1.8, "Miami print"),
        (r"versailles|greek.?key|greca", 1.5, "Greek Key/Greca"),
        (r"jungle|jungle.?print|j.?lo|jennifer", 2.5, "Jungle print"),

        # Vintage
        (r"vintage|archive|198[0-9]", 2.2, "Vintage Versace"),
        (r"istante|versus.*vintage|vintage.*versus", 1.8, "Istante/Versus vintage"),
        (r"couture|atelier|haute", 2.5, "Couture piece"),
    ],

    # === BURBERRY ===
    "burberry": [
        # Riccardo Tisci era (2018-2022)
        (r"tisci|riccardo.*burberry|burberry.*riccardo", 1.6, "Riccardo Tisci era"),
        (r"tbm|tb.?monogram|thomas.*burberry.*monogram", 1.5, "TB Monogram"),

        # Prorsum
        (r"prorsum|burberry.?prorsum", 1.8, "Burberry Prorsum"),

        # Iconic vintage
        (r"nova.?check|nova|house.?check|haymarket", 1.8, "Nova/House Check"),
        (r"vintage.?trench|heritage.?trench|westminster|kensington", 1.6, "Vintage Trench"),
        (r"vintage|198[0-9]|199[0-9]|archive", 1.5, "Vintage Burberry"),

        # Collabs
        (r"vivienne.*burberry|burberry.*vivienne|westwood.*burberry", 2.0, "Vivienne Westwood collab"),
        (r"gosha.*burberry|burberry.*gosha", 1.8, "Gosha Rubchinskiy collab"),
        (r"supreme.*burberry|burberry.*supreme", 1.8, "Supreme collab"),
    ],

    # =========================================================================
    # STREETWEAR / CONTEMPORARY
    # =========================================================================

    # === VETEMENTS ===
    "vetements": [
        # Grails — early Demna and iconic pieces
        (r"dhl|dhl.*vetements|vetements.*dhl", 2.5, "DHL piece"),
        (r"champion.*vetements|vetements.*champion", 2.0, "Champion collab"),
        (r"oversiz|over.?siz", 1.5, "Oversized piece"),
        (r"demna|gvasalia", 2.0, "Demna era"),

        # Early pieces (2014-2019)
        (r"201[4-6]|(aw|fw|ss).?1[4-6]", 2.2, "Early Vetements (2014-2016)"),
        (r"201[7-9]|(aw|fw|ss).?1[7-9]", 1.6, "2017-2019 archive"),

        # Iconic pieces
        (r"total.?fucking.?darkness|tfd", 2.5, "Total Fucking Darkness"),
        (r"sexual.?fantasies|may.?the.?bridges", 2.0, "Graphic hoodie"),
        (r"polizei|police|euro.?print", 1.8, "Polizei/Euro piece"),
        (r"metal|snoop|logo.?tape", 1.5, "Graphic piece"),

        # Collabs
        (r"levi.*vetements|vetements.*levi", 1.8, "Levi's collab"),
        (r"reebok.*vetements|vetements.*reebok", 1.5, "Reebok collab"),
    ],

    # === OFF-WHITE ===
    "off-white": [
        # The Ten — Nike collab holy grails
        (r"the.?ten|\"the.?ten\"|nike.*off.?white.*ten|off.?white.*the.*ten", 3.0, "Nike The Ten"),
        (r"nike.*off.?white|off.?white.*nike|ow.*nike|nike.*ow", 2.0, "Nike collab"),
        (r"jordan.*off.?white|off.?white.*jordan|ow.*jordan", 2.5, "Jordan collab"),

        # Early Virgil (2013-2017)
        (r"201[3-5]|(aw|fw|ss).?1[3-5]", 2.2, "Early Off-White (2013-2015)"),
        (r"201[6-7]|(aw|fw|ss).?1[6-7]", 1.8, "2016-2017 archive"),
        (r"virgil|abloh", 1.8, "Virgil era"),

        # Iconic motifs
        (r"industrial.?belt|industrial|yellow.?belt", 1.8, "Industrial Belt"),
        (r"diagonal|stripe.*off|off.*stripe", 1.5, "Diagonal Stripes"),
        (r"caravaggio|painting.?print", 1.8, "Caravaggio/Painting print"),
        (r"seeing.?things|for.?all", 1.5, "Graphic piece"),

        # Collabs
        (r"ikea.*off|off.*ikea", 1.5, "IKEA collab"),
        (r"champion.*off|off.*champion", 1.5, "Champion collab"),
    ],

    # === FEAR OF GOD ===
    "fear of god": [
        # Mainline seasons (1-7) — the real deal
        (r"(season|collection|fourth|4th).?1\b|first.?collection", 3.0, "Mainline Season 1"),
        (r"(season|collection).?2\b|second.?collection", 2.5, "Mainline Season 2"),
        (r"(season|collection).?3\b|third.?collection", 2.5, "Mainline Season 3"),
        (r"(season|collection|fourth).?4\b", 2.2, "Mainline Season 4"),
        (r"(season|collection|fifth).?5\b", 2.0, "Mainline Season 5"),
        (r"(season|collection|sixth).?6\b", 1.8, "Mainline Season 6"),
        (r"(season|collection|seventh).?7\b", 1.6, "Mainline Season 7"),
        (r"mainline|main.?line(?!.*essentials)", 2.0, "Mainline piece"),

        # Iconic pieces
        (r"military|army|camo.*fog|fog.*camo", 1.8, "Military piece"),
        (r"denim|selvedge|selvage|vintage.?wash", 1.5, "Denim piece"),
        (r"bomber|satin.?bomb|ma-?1", 1.6, "Bomber"),
        (r"jerry.?lorenzo|jerry", 1.5, "Jerry Lorenzo design"),

        # Collabs
        (r"nike.*fear|fear.*nike|air.?fear|fog.*nike", 1.8, "Nike Air Fear of God"),
        (r"zegna.*fear|fear.*zegna", 1.5, "Zegna collab"),
    ],

    # === GALLERY DEPT ===
    "gallery dept": [
        # Grail pieces
        (r"painted|hand.?paint|paint.?splat", 2.0, "Painted piece"),
        (r"flare|flared|flar", 1.8, "Flared piece"),
        (r"art.?that.?kills|atk", 2.2, "Art That Kills"),
        (r"lanvin.*gallery|gallery.*lanvin", 2.0, "Lanvin collab"),

        # Early archive
        (r"201[4-8]|(aw|fw|ss).?1[4-8]", 1.8, "Early Gallery Dept"),
        (r"sample|1.?of.?1|one.?of", 2.5, "Sample/1-of-1"),

        # Iconic items
        (r"denim|vintage.*jean|jean.*vintage", 1.5, "Denim piece"),
        (r"logo|french.?logo", 1.3, "Logo piece"),
    ],

    # === AMIRI ===
    "amiri": [
        # Iconic pieces
        (r"mx1|mx-?1|leather.?insert.*denim|denim.*leather.?insert", 2.0, "MX1 Jeans"),
        (r"art.?patch|patchwork|patch.*jean", 1.8, "Art Patch piece"),
        (r"shotgun|distressed.*flanel|amiri.*flannel", 1.6, "Shotgun/Flannel"),
        (r"crystal|swarovski|rhinestone", 1.5, "Crystal piece"),

        # Early archive
        (r"201[4-7]|(aw|fw|ss).?1[4-7]", 1.8, "Early Amiri (2014-2017)"),
        (r"made.?to.?order|custom|bespoke", 2.0, "Made-to-order"),

        # Iconic items
        (r"bone|skeleton.?denim|bones.?jean", 1.6, "Bone piece"),
        (r"leather|biker|moto", 1.5, "Leather piece"),
        (r"bandana|paisley", 1.4, "Bandana piece"),
    ],

    # === RHUDE ===
    "rhude": [
        # Iconic pieces
        (r"bandana|traxedo|bandana.?short", 2.0, "Bandana piece"),
        (r"rhecess|rh.?ecess|rhude.*sneaker", 1.6, "Rhecess sneaker"),
        (r"rossa|racing|mclaren|f1", 1.8, "Rossa/McLaren"),
        (r"cigarette|marlboro|camel", 1.8, "Cigarette motif"),

        # Early archive
        (r"201[5-8]|(aw|fw|ss).?1[5-8]", 1.5, "Early Rhude (2015-2018)"),
        (r"rhuigi|villasenor", 1.3, "Rhuigi era"),

        # Iconic motifs
        (r"eagle|american|la.*sunset|sunset|moonlight", 1.4, "Graphic motif"),
        (r"puma.*rhude|rhude.*puma", 1.5, "Puma collab"),
    ],

    # === ENFANTS RICHES DEPRIMES ===
    "enfants riches deprimes": [
        # Everything ERD is limited — hand distressed pieces are grails
        (r"hand.?distress|hand.?destroy|hand.?made", 3.0, "Hand-distressed piece"),
        (r"henri|henri.?levy|alexander.*levy", 2.0, "Henri piece"),
        (r"cigarette|smoking|ash", 2.0, "Cigarette piece"),

        # Iconic items
        (r"leather|biker|moto", 2.0, "Leather piece"),
        (r"denim|jean|trouser", 1.8, "Denim piece"),
        (r"baby.?tee|tee|graphic", 1.5, "Graphic tee"),

        # Early archive
        (r"201[2-6]|(aw|fw|ss).?1[2-6]", 2.0, "Early ERD (2012-2016)"),
        (r"201[7-9]|(aw|fw|ss).?1[7-9]", 1.5, "ERD archive"),

        # General
        (r"sample|1.?of|one.?of", 2.5, "Sample/1-of-1"),
        # Piece-specific multipliers (March 2026 research)
        (r"classic.?logo", 2.2, "Classic Logo — most liquid ERD piece"),
        (r"benny.?s?.?video", 2.0, "Benny's Video — cult film reference"),
        (r"menendez", 2.0, "Menendez Murder Trial — trend-driven"),
        (r"viper.?room", 2.5, "Viper Room — C&D, extreme provenance"),
        (r"teenage.?snuff", 1.8, "Teenage Snuff — consistent seller"),
        (r"flowers?.?of.?anger", 1.8, "Flowers of Anger LS"),
        (r"god.?with.?revolver", 1.9, "God With Revolver zip"),
        (r"spanish.?elegy", 2.3, "Spanish Elegy moto — premium leather"),
        (r"rose.?buckle", 1.8, "Rose Buckle studded belt"),
        (r"frozen.?beaut", 2.8, "Frozen Beauties — only 50 made"),
        (r"le.?rosey", 2.5, "Le Rosey — first ERD design ever"),
        (r"bohemian.?scum", 1.6, "Bohemian Scum tee"),
    ],

    # === PALACE ===
    "palace": [
        # Grails — Tri-ferg and early drops
        (r"tri.?ferg|triferg", 1.8, "Tri-ferg piece"),
        (r"201[3-6]|(aw|fw|ss).?1[3-6]", 1.8, "Early Palace (2013-2016)"),

        # Collaborations
        (r"adidas.*palace|palace.*adidas", 1.8, "adidas collab"),
        (r"ralph.*palace|palace.*ralph|polo.*palace|palace.*polo", 2.5, "Ralph Lauren collab"),
        (r"moschino.*palace|palace.*moschino", 1.6, "Moschino collab"),
        (r"gucci.*palace|palace.*gucci", 2.0, "Gucci collab"),
        (r"arc.?teryx.*palace|palace.*arc.?teryx", 1.8, "Arc'teryx collab"),

        # Iconic items
        (r"gore.?tex|goretex|gtx", 1.5, "Gore-Tex piece"),
        (r"shell|jacket|windbreak", 1.3, "Outerwear"),

        # General archive
        (r"201[7-9]|(aw|fw|ss).?1[7-9]", 1.3, "2017-2019 archive"),
    ],

    # === STUSSY ===
    "stussy": [
        # Grails — 80s/90s archive and iconic motifs
        (r"(19)?8[0-9]|198[0-9]|80s", 2.5, "1980s Stussy"),
        (r"(19)?9[0-5]|199[0-5]|early.?90s", 2.0, "Early 1990s Stussy"),
        (r"8.?ball|eight.?ball", 2.2, "8-Ball piece"),
        (r"world.?tour|international|ist", 1.8, "World Tour piece"),
        (r"skull|skull.?bones|crossbones", 1.5, "Skull piece"),

        # Collaborations
        (r"nike.*stussy|stussy.*nike", 1.8, "Nike collab"),
        (r"dior.*stussy|stussy.*dior", 2.5, "Dior collab"),
        (r"cdg.*stussy|stussy.*cdg|comme.*stussy|stussy.*comme", 1.8, "CDG collab"),
        (r"cpfm.*stussy|stussy.*cpfm|cactus.*stussy", 1.6, "CPFM collab"),

        # Vintage
        (r"199[6-9]|late.?90s", 1.6, "Late 1990s Stussy"),
        (r"200[0-5]|early.?2000s", 1.3, "Early 2000s Stussy"),
        (r"vintage|archive|og|made.?in.?usa", 1.5, "Vintage Stussy"),
    ],
}


# =========================================================================
# BRAND ALIASES — map variant names to canonical keys
# =========================================================================
BRAND_ALIASES = {
    # Original aliases
    "number (n)ine": "number nine",
    "n(n)": "number nine",
    "maison margiela": "margiela",
    "martin margiela": "margiela",
    "mmm": "margiela",
    "maison martin margiela": "margiela",
    "cdg": "comme des garcons",
    "comme des garçons": "comme des garcons",
    "slp": "saint laurent",
    "ysl": "saint laurent",
    "rick": "rick owens",
    "ro": "rick owens",
    "drkshdw": "rick owens",
    "jpg": "jean paul gaultier",
    "gaultier": "jean paul gaultier",
    "vw": "vivienne westwood",
    "sup": "supreme",

    # Japanese Archive aliases
    "hysteric": "hysteric glamour",
    "hys": "hysteric glamour",
    "hg": "hysteric glamour",
"nbhd": "neighborhood",
    "a bathing ape": "bape",
    "bathing ape": "bape",
    "ape": "bape",
    "nigo": "bape",
    "human": "human made",
    "hmmd": "human made",
    "cdg junya": "junya watanabe",
    "junya": "junya watanabe",
    "jwcdg": "junya watanabe",
    "junya watanabe man": "junya watanabe",
    "junya watanabe comme des garcons": "junya watanabe",
    "wm": "wacko maria",
    "c.e": "cav empt",
    "ce": "cav empt",
    "c.e.": "cav empt",
    "cav": "cav empt",
    "cavempt": "cav empt",
    "kansai": "kansai yamamoto",
    "soloist": "takahiromiyashita thesoloist",
    "the soloist": "takahiromiyashita thesoloist",
    "thesoloist": "takahiromiyashita thesoloist",
    "takahiromiyashita": "takahiromiyashita thesoloist",

    # European Avant-Garde aliases
    "ann d": "ann demeulemeester",
    "ann d.": "ann demeulemeester",
    "demeulemeester": "ann demeulemeester",
    "dvn": "dries van noten",
    "dries": "dries van noten",
    "ccp": "carol christian poell",
    "poell": "carol christian poell",
    "bbs": "boris bidjan saberi",
    "boris": "boris bidjan saberi",
    "chalayan": "hussein chalayan",
    "hussein": "hussein chalayan",
    "wvb": "walter van beirendonck",
    "walter": "walter van beirendonck",
    "van beirendonck": "walter van beirendonck",
    "craig": "craig green",
    "harnden": "paul harnden",
    "paul harnden shoemakers": "paul harnden",
    "gbs": "geoffrey b small",
    "geoffrey": "geoffrey b small",

    # Luxury House aliases
    "mcqueen": "alexander mcqueen",
    "amq": "alexander mcqueen",
    "mugler": "thierry mugler",
    "manfred mugler": "thierry mugler",
    "balenci": "balenciaga",
    "tisci": "givenchy",
    "givenchy tisci": "givenchy",
    "tom ford gucci": "gucci",
    "lv": "louis vuitton",
    "vuitton": "louis vuitton",
    "bv": "bottega veneta",
    "bottega": "bottega veneta",
    "old celine": "celine",
    "céline": "celine",
    "old céline": "celine",
    "philo celine": "celine",

    # Streetwear/Contemporary aliases
    "vet": "vetements",
    "ow": "off-white",
    "offwhite": "off-white",
    "off white": "off-white",
    "fog": "fear of god",
    "jerry lorenzo": "fear of god",
    "essentials": "fear of god",
    "gd": "gallery dept",
    "gallery": "gallery dept",
    "erd": "enfants riches deprimes",
    "enfants riches": "enfants riches deprimes",
    "enfants": "enfants riches deprimes",
    "stüssy": "stussy",
}


def normalize_brand(brand: str) -> str:
    """Normalize brand name for matching."""
    brand_lower = brand.lower().strip()
    return BRAND_ALIASES.get(brand_lower, brand_lower)


def detect_season(brand: str, title: str, description: str = "") -> Optional[Tuple[float, str]]:
    """
    Detect if an item is from an iconic season/collection.

    Args:
        brand: Brand name
        title: Item title
        description: Item description (optional)

    Returns:
        Tuple of (multiplier, season_name) or None if no match
    """
    brand_normalized = normalize_brand(brand)
    text = f"{title} {description}".lower()

    # Check brand-specific patterns
    if brand_normalized in ICONIC_SEASONS:
        patterns = ICONIC_SEASONS[brand_normalized]

        # Check patterns in order (highest multiplier first, so sort)
        sorted_patterns = sorted(patterns, key=lambda x: -x[1])

        for pattern, multiplier, name in sorted_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return (multiplier, name)

    # Also check for generic archive/vintage indicators
    generic_patterns = [
        (r"\b(19[89]\d)\b", 1.3, "1980s/1990s vintage"),
        (r"\b(200[0-9])\b", 1.2, "2000s archive"),
        (r"archive|vintage|grail|rare|sample", 1.2, "Archive/Vintage"),
        (r"deadstock|ds\b|nwt|bnwt", 1.1, "Deadstock/NWT"),
        (r"made.?in.?japan|mij", 1.15, "Made in Japan"),
        (r"made.?in.?italy", 1.1, "Made in Italy"),
        (r"runway|show.?piece|sample", 1.3, "Runway/Sample"),
    ]

    for pattern, multiplier, name in generic_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return (multiplier, name)

    return None


def get_season_adjusted_price(
    brand: str,
    title: str,
    base_market_price: float,
    description: str = "",
) -> Tuple[float, Optional[str]]:
    """
    Get market price adjusted for iconic season/collection.

    Args:
        brand: Brand name
        title: Item title
        base_market_price: Base market price from comps
        description: Item description (optional)

    Returns:
        Tuple of (adjusted_price, season_name or None)
    """
    result = detect_season(brand, title, description)

    if result:
        multiplier, season_name = result
        adjusted_price = base_market_price * multiplier
        return (adjusted_price, season_name)

    return (base_market_price, None)


# Test function
if __name__ == "__main__":
    tests = [
        # === Original tests ===
        ("raf simons", "Raf Simons AW01 Riot Bomber Jacket"),
        ("raf simons", "Raf Simons SS02 Woe Onto Those Shirt"),
        ("raf simons", "Raf Simons regular sweater"),
        ("number nine", "Number Nine AW05 High Streets Leather"),
        ("number nine", "Number Nine Skull Cashmere Sweater"),
        ("undercover", "Undercover SS03 Scab Pants"),
        ("undercover", "Undercover But Beautiful hoodie"),
        ("helmut lang", "Helmut Lang Astro Biker Jacket"),
        ("helmut lang", "Helmut Lang Painter Jeans"),
        ("dior homme", "Dior Homme AW06 Hedi Slimane Clawmark Jeans"),
        ("rick owens", "Rick Owens Sphinx leather jacket runway"),
        ("maison margiela", "Margiela Artisanal Line 0 Painted Jacket"),
        ("supreme", "Supreme Box Logo Hoodie 2005"),
        # === Japanese Archive ===
        ("hysteric glamour", "Hysteric Glamour 1993 Courtney Love Guitar Girl tee"),
        ("kapital", "Kapital Century Denim 5P boro patchwork"),
("wtaps", "WTAPS Jungle LS 2003 olive"),
        ("neighborhood", "Neighborhood Savage skull tee 2004"),
        ("bape", "BAPE KAWS 1st Camo Shark Hoodie"),
        ("human made", "Human Made Nigo heart logo tee 2005"),
        ("julius", "Julius Gas Mask Leather Jacket _7"),
        ("sacai", "Sacai x Nike LDWaffle Green"),
        ("junya watanabe", "Junya Watanabe MAN Levi's Reconstructed Patchwork Jacket"),
        ("wacko maria", "Wacko Maria Tim Lehi Hawaiian Shirt Leopard"),
        ("cav empt", "C.E Cav Empt 2014 Graphic Pullover"),
        ("kansai yamamoto", "Kansai Yamamoto Bowie 1970s Kabuki Jumpsuit"),
        ("needles", "Needles Rebuild 7 Cuts flannel"),
        ("takahiromiyashita thesoloist", "TheSoloist s.0001 leather biker"),
        # === European Avant-Garde ===
        ("ann demeulemeester", "Ann Demeulemeester 1998 lace-up boots feather coat"),
        ("dries van noten", "Dries Van Noten SS97 floral embroidered jacket"),
        ("carol christian poell", "CCP Carol Christian Poell Object Dyed Prosthetic boot"),
        ("boris bidjan saberi", "BBS Boris Bidjan Saberi Blood Stained leather"),
        ("hussein chalayan", "Hussein Chalayan Coffee Table Dress LED"),
        ("walter van beirendonck", "Walter Van Beirendonck Wild & Lethal Trash 1996"),
        ("craig green", "Craig Green quilted laced jacket 2014"),
        ("paul harnden", "Paul Harnden Shoemakers Mac Coat linen"),
        ("geoffrey b small", "Geoffrey B Small handmade one of a kind coat"),
        # === Luxury Houses ===
        ("alexander mcqueen", "Alexander McQueen Plato's Atlantis SS10 bumster"),
        ("thierry mugler", "Thierry Mugler 1988 Insect Power Suit couture"),
        ("balenciaga", "Balenciaga Triple S Ghesquiere City Bag"),
        ("givenchy", "Givenchy Riccardo Tisci Rottweiler Shark tee"),
        ("gucci", "Gucci Tom Ford era 1996 Horsebit loafer"),
        ("prada", "Prada FW99 Flame Linea Rossa nylon"),
        ("celine", "Old Celine Phoebe Philo Box Bag 2015"),
        ("louis vuitton", "Louis Vuitton Virgil Abloh LV Trainer SS20"),
        ("bottega veneta", "Bottega Veneta Daniel Lee The Pouch puddle boot"),
        ("valentino", "Valentino couture lace Pierpaolo Piccioli rockstud"),
        ("fendi", "Fendi Baguette Monster Eyes Karl Fendace"),
        ("versace", "Gianni Versace 1994 Safety Pin Medusa baroque"),
        ("burberry", "Burberry Prorsum vintage Nova Check trench"),
        # === Streetwear/Contemporary ===
        ("vetements", "Vetements DHL 2015 Demna Total Fucking Darkness"),
        ("off-white", "Off-White Nike The Ten Jordan 2014"),
        ("fear of god", "Fear of God Season 1 Military bomber Jerry Lorenzo"),
        ("gallery dept", "Gallery Dept Art That Kills painted flare denim"),
        ("amiri", "Amiri MX1 Art Patch Crystal 2015"),
        ("rhude", "Rhude Bandana Rossa McLaren"),
        ("enfants riches deprimes", "ERD Enfants Riches Deprimes hand distressed cigarette leather"),
        ("palace", "Palace Ralph Lauren Tri-ferg 2014 adidas collab"),
        ("stussy", "Stussy 8-Ball World Tour 1988"),
        # === Alias tests ===
        ("ccp", "Carol Christian Poell Object Dyed Dead End boot"),
        ("bbs", "Boris Bidjan Saberi Blood Stained horse leather"),
        ("ann d", "Ann Demeulemeester 1995 feather lace-up"),
        ("ow", "Off-White Industrial Belt diagonal"),
        ("fog", "Fear of God Mainline Military Bomber"),
        ("gbs", "Geoffrey B Small handmade cashmere coat"),
        ("erd", "Enfants Riches Deprimes Henri cigarette tee"),
    ]

    print("Season Detection Tests")
    print("=" * 70)

    detected = 0
    total = len(tests)

    for brand, title in tests:
        result = detect_season(brand, title)
        if result:
            mult, name = result
            print(f"✓ [{brand}] {title[:50]}{'...' if len(title)>50 else ''}")
            print(f"  → {name} ({mult}x multiplier)")
            detected += 1
        else:
            print(f"✗ [{brand}] {title[:50]}{'...' if len(title)>50 else ''}")
            print(f"  → No season detected")
        print()

    print("=" * 70)
    print(f"Results: {detected}/{total} detected ({detected/total*100:.0f}%)")
    print(f"Brands in database: {len(ICONIC_SEASONS)}")
    print(f"Brand aliases: {len(BRAND_ALIASES)}")


# ============================================================================
# EXACT SEASON/YEAR EXTRACTION (Quick Win Implementation)
# ============================================================================

# Season code normalization mapping
SEASON_ALIASES = {
    # Fall/Winter variants
    "aw": "FW",
    "fw": "FW", 
    "autumn": "FW",
    "autumnwinter": "FW",
    "fall": "FW",
    "fallwinter": "FW",
    "f/w": "FW",
    "a/w": "FW",
    "f.w": "FW",
    "a.w": "FW",
    # Spring/Summer variants
    "ss": "SS",
    "spring": "SS",
    "summerspring": "SS",
    "springsummer": "SS",
    "s/s": "SS",
    "s.s": "SS",
    # Resort/Cruise
    "resort": "RESORT",
    "cruise": "CRUISE",
    # Pre-fall
    "prefall": "PF",
    "pre-fall": "PF",
    "pf": "PF",
}


def normalize_season_code(season_str: str) -> Optional[str]:
    """Normalize season string to canonical code (FW, SS, etc.)."""
    if not season_str:
        return None
    season_clean = season_str.lower().replace(" ", "").replace("-", "").replace("/", "").replace(".", "")
    return SEASON_ALIASES.get(season_clean)


def extract_year(year_str: str) -> Optional[int]:
    """Extract 4-digit year from string, handling 2-digit conversions."""
    if not year_str:
        return None
    
    year_str = year_str.strip()
    
    # Handle 4-digit year
    if len(year_str) == 4 and year_str.isdigit():
        year = int(year_str)
        if 1970 <= year <= 2030:
            return year
    
    # Handle 2-digit year (convert to 1900s or 2000s)
    if len(year_str) == 2 and year_str.isdigit():
        year_int = int(year_str)
        if year_int >= 70:  # 70-99 -> 1970-1999
            return 1900 + year_int
        else:  # 00-69 -> 2000-2069
            return 2000 + year_int
    
    return None


def extract_exact_season(title: str) -> Optional[Tuple[str, int]]:
    """
    Extract exact season (FW/SS) and year from title.
    
    Args:
        title: Item title to parse
        
    Returns:
        Tuple of (season_code, year) or None if not found
        Season code is normalized: "FW", "SS", "RESORT", "CRUISE", "PF"
        Year is always 4-digit (e.g., 2018, 2005, 1998)
        
    Examples:
        "Rick Owens FW18 Leather Jacket" -> ("FW", 2018)
        "Raf Simons AW01 Riot Bomber" -> ("FW", 2001)
        "Number Nine SS05 Tee" -> ("SS", 2005)
        "Dior Homme FW 2005 Clawmark" -> ("FW", 2005)
    """
    if not title:
        return None
    
    text = title.lower()
    
    # Pattern 1: Season abbreviation + 2-digit year (most common in archive fashion)
    # Matches: FW18, SS05, AW01, F/W 18, A/W '01, etc.
    pattern1 = re.compile(
        r'\b(aw|fw|ss|f/w|a/w|s/s|autumn|fall|spring)[\s\-\.]?(\'|\'\')?(\d{2,4})\b',
        re.IGNORECASE
    )
    
    # Pattern 2: Full season name + year
    # Matches: Fall Winter 2018, Spring Summer 2005, etc.
    pattern2 = re.compile(
        r'\b(fall[\s\-]+winter|autumn[\s\-]+winter|spring[\s\-]+summer)[\s\-\.]?(\'|\'\')?(\d{2,4})\b',
        re.IGNORECASE
    )
    
    # Pattern 3: Year + season (less common but exists)
    # Matches: 2018 FW, 2005 Fall/Winter, etc.
    pattern3 = re.compile(
        r'\b(\d{4})[\s\-\.]?(fall[\s\-]?winter|autumn[\s\-]?winter|spring[\s\-]?summer|fw|ss)\b',
        re.IGNORECASE
    )
    
    # Try patterns in order of reliability
    for pattern in [pattern1, pattern2, pattern3]:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            
            if pattern == pattern3:
                # Pattern 3: year first
                year = extract_year(groups[0])
                season = normalize_season_code(groups[1])
            else:
                # Pattern 1 & 2: season first
                season = normalize_season_code(groups[0])
                year = extract_year(groups[-1])  # Last group is the year
            
            if season and year:
                return (season, year)
    
    # Pattern 4: Standalone 4-digit year that looks like a fashion season (not a price)
    # Avoid matching prices like "$2000" or "selling for 1500"
    year_pattern = re.compile(r'\b(19[8-9]\d|20[0-2]\d)\b(?!\s*(usd|\$|dollars|€|£|price))')
    year_match = year_pattern.search(text)
    if year_match:
        year = extract_year(year_match.group(1))
        if year:
            # Return just year, season unknown
            return (None, year)
    
    return None


def extract_season_with_confidence(title: str) -> Tuple[Optional[str], Optional[int], str]:
    """
    Extract season with confidence level.
    
    Returns:
        (season, year, confidence) where confidence is:
        - "confirmed": explicit season code found (FW18, SS05, etc.)
        - "inferred": year found but season not specified
        - "unknown": nothing found
    """
    result = extract_exact_season(title)
    
    if not result:
        return (None, None, "unknown")
    
    season, year = result
    
    if season:
        return (season, year, "confirmed")
    else:
        return (None, year, "inferred")


def aggregate_seasons_from_comps(comp_titles: List[str]) -> Tuple[Optional[str], Optional[int], str]:
    """
    Aggregate season data from multiple comp titles.
    Returns the most common season/year combination.
    
    Args:
        comp_titles: List of sold comp titles
        
    Returns:
        (season, year, confidence) where confidence reflects how many comps agreed
    """
    from collections import Counter
    
    seasons_found = []
    years_found = []
    
    for title in comp_titles:
        result = extract_exact_season(title)
        if result:
            season, year = result
            if season:
                seasons_found.append(season)
            if year:
                years_found.append(year)
    
    if not years_found:
        return (None, None, "unknown")
    
    # Find most common year
    year_counter = Counter(years_found)
    most_common_year, year_count = year_counter.most_common(1)[0]
    
    # Find most common season (if any)
    most_common_season = None
    if seasons_found:
        season_counter = Counter(seasons_found)
        most_common_season, season_count = season_counter.most_common(1)[0]
        # Only use season if it appears in at least 30% of comps with season data
        if season_count < len(seasons_found) * 0.3:
            most_common_season = None
    
    # Determine confidence based on agreement
    total_comps = len(comp_titles)
    year_agreement = year_count / total_comps
    
    if year_agreement >= 0.5:
        confidence = "confirmed"
    elif year_agreement >= 0.3:
        confidence = "inferred"
    else:
        confidence = "unknown"
    
    return (most_common_season, most_common_year, confidence)


# Test function for exact season extraction
if __name__ == "__main__":
    test_cases = [
        # Archive fashion examples
        ("Rick Owens FW18 Leather Jacket", ("FW", 2018)),
        ("Raf Simons AW01 Riot Bomber", ("FW", 2001)),
        ("Number Nine SS05 Tee", ("SS", 2005)),
        ("Dior Homme FW 2005 Clawmark", ("FW", 2005)),
        ("Helmut Lang AW99 Astro Biker", ("FW", 1999)),
        ("Undercover SS03 Scab Pants", ("SS", 2003)),
        ("Margiela FW08 Artisanal Coat", ("FW", 2008)),
        ("BAPE SS02 Shark Hoodie", ("SS", 2002)),
        ("Supreme FW14 Box Logo", ("FW", 2014)),
        # Variations
        ("Rick Owens F/W 18", ("FW", 2018)),
        ("Raf Simons A/W '01", ("FW", 2001)),
("WTAPS Fall-Winter 2008", ("FW", 2008)),
        ("Kapital Spring Summer 2015", ("SS", 2015)),
        ("Number (N)ine 2005", (None, 2005)),  # Year only
        ("Archive 1998 Helmut Lang", (None, 1998)),  # Year only
        # No season
        ("Regular Rick Owens Tee", None),
        ("", None),
    ]
    
    print("\n" + "=" * 70)
    print("Exact Season/Year Extraction Tests")
    print("=" * 70)
    
    passed = 0
    for title, expected in test_cases:
        result = extract_exact_season(title)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        print(f"{status} \"{title[:40]}...\" -> {result} (expected: {expected})")
    
    print("=" * 70)
    print(f"Results: {passed}/{len(test_cases)} passed ({passed/len(test_cases)*100:.0f}%)")
    
    # Test aggregation
    print("\n" + "=" * 70)
    print("Season Aggregation Tests")
    print("=" * 70)
    
    comp_titles = [
        "Rick Owens FW18 Leather Jacket",
        "Rick Owens FW18 Stooges Coat",
        "Rick Owens FW 2018 Bomber",
        "Rick Owens Fall Winter 18 Geobasket",
        "Rick Owens 2018 Mainline Tee",
    ]
    agg_result = aggregate_seasons_from_comps(comp_titles)
    print(f"Comps: {len(comp_titles)}")
    print(f"Aggregated: {agg_result}")
    print(f"Expected: ('FW', 2018, 'confirmed')")
