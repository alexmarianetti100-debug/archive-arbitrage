"""
Blue-Chip Luxury Targets Configuration

High-value items with proven liquidity and margins.
Based on market research and successful seller analysis.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class BlueChipTarget:
    """Configuration for a blue-chip luxury target."""
    query: str
    category: str  # 'jewelry', 'fashion'
    min_margin: float  # Minimum acceptable margin (0.20 = 20%)
    target_margin: float  # Ideal margin (0.30 = 30%)
    min_comps: int  # Minimum number of sold comps needed
    max_price: int  # Maximum price for beginner tier
    authentication_priority: str  # 'required', 'preferred', 'optional'
    liquidity_score: int  # 1-10, higher = faster sells
    notes: str = ""


# BLUE-CHIP WATCHES — removed (no resources to authenticate/value)
BLUE_CHIP_WATCHES: list[BlueChipTarget] = []

# BLUE-CHIP BAGS — removed (no resources to authenticate/value)
BLUE_CHIP_BAGS: list[BlueChipTarget] = []

# BLUE-CHIP JEWELRY
# High margins, small size, easy to authenticate
BLUE_CHIP_JEWELRY = [
    # Van Cleef & Arpels - Best performing jewelry 2024-2025
    BlueChipTarget("van cleef alhambra necklace", "jewelry", 0.25, 0.40, 8, 4000, "required", 9, "112% value retention"),
    BlueChipTarget("van cleef alhambra bracelet", "jewelry", 0.28, 0.45, 8, 3500, "required", 9, "Sweet Alhambra trending"),
    BlueChipTarget("van cleef vintage alhambra", "jewelry", 0.25, 0.40, 6, 5000, "required", 8, "Classic size"),
    BlueChipTarget("van cleef frivole", "jewelry", 0.20, 0.35, 6, 3000, "required", 8, "Floral design"),
    
    # Cartier - Always liquid
    BlueChipTarget("cartier love bracelet", "jewelry", 0.20, 0.35, 12, 6000, "required", 10, "Most iconic bracelet"),
    BlueChipTarget("cartier love ring", "jewelry", 0.18, 0.30, 15, 1500, "required", 10, "Entry Cartier"),
    BlueChipTarget("cartier juste un clou", "jewelry", 0.20, 0.35, 10, 3500, "required", 9, "Nail design"),
    BlueChipTarget("cartier trinity", "jewelry", 0.15, 0.25, 10, 1200, "required", 9, "Three gold bands"),
    
    # Chrome Hearts - Cult following, high margins
    BlueChipTarget("chrome hearts cross pendant", "jewelry", 0.35, 0.50, 8, 800, "preferred", 9, "Most popular CH"),
    BlueChipTarget("chrome hearts forever ring", "jewelry", 0.30, 0.45, 10, 600, "preferred", 9, "Classic band"),
    BlueChipTarget("chrome hearts dagger pendant", "jewelry", 0.35, 0.50, 6, 1000, "preferred", 8, "Statement piece"),
    BlueChipTarget("chrome hearts floral cross", "jewelry", 0.30, 0.45, 6, 1200, "preferred", 8, "Detailed design"),
    BlueChipTarget("chrome hearts scroll ring", "jewelry", 0.30, 0.45, 8, 700, "preferred", 9, "Entry ring"),
    BlueChipTarget("chrome hearts paperchain", "jewelry", 0.25, 0.40, 8, 1500, "preferred", 9, "Bracelet"),
    BlueChipTarget("chrome hearts tiny e", "jewelry", 0.30, 0.45, 10, 400, "preferred", 10, "Affordable entry"),
    BlueChipTarget("chrome hearts ch cross", "jewelry", 0.35, 0.50, 6, 900, "preferred", 8, "Large cross"),
    BlueChipTarget("chrome hearts babyfat", "jewelry", 0.30, 0.45, 8, 500, "preferred", 9, "Popular pendant"),
    BlueChipTarget("chrome hearts plus ring", "jewelry", 0.30, 0.45, 8, 550, "preferred", 9, "Plus design"),
    
    # Tiffany - Entry luxury
    BlueChipTarget("tiffany t bracelet", "jewelry", 0.18, 0.30, 12, 1500, "preferred", 9, "Modern design"),
    BlueChipTarget("tiffany hardwear", "jewelry", 0.20, 0.35, 10, 800, "preferred", 9, "Industrial chic"),
    BlueChipTarget("tiffany return to tiffany", "jewelry", 0.15, 0.25, 15, 400, "preferred", 10, "Classic heart"),
    BlueChipTarget("tiffany keys", "jewelry", 0.18, 0.28, 10, 1200, "preferred", 9, "Elegant"),
    
    # Bvlgari
    BlueChipTarget("bvlgari serpenti", "jewelry", 0.20, 0.35, 8, 3000, "required", 8, "Snake design"),
    BlueChipTarget("bvlgari b zero ring", "jewelry", 0.18, 0.30, 10, 1500, "required", 9, "Logo ring"),
    BlueChipTarget("bvlgari divas dream", "jewelry", 0.20, 0.35, 6, 2500, "required", 8, "Fan design"),
    
    # More Chrome Hearts variants
    BlueChipTarget("chrome hearts forever ring", "jewelry", 0.30, 0.45, 10, 400, "preferred", 9, "Classic band, crosses"),
    BlueChipTarget("chrome hearts cross pendant", "jewelry", 0.28, 0.42, 10, 350, "preferred", 9, "Bail cross, most popular"),
    BlueChipTarget("chrome hearts baby fat", "jewelry", 0.25, 0.40, 8, 450, "preferred", 9, "Cross pendant, small"),
    BlueChipTarget("chrome hearts tiny e", "jewelry", 0.25, 0.40, 8, 300, "preferred", 9, "E cross pendant"),
    BlueChipTarget("chrome hearts paperchain", "jewelry", 0.22, 0.35, 10, 800, "preferred", 9, "Bracelet, paperclip links"),
    BlueChipTarget("chrome hearts rollercross", "jewelry", 0.25, 0.40, 8, 600, "preferred", 8, "Bracelet, cross links"),
    BlueChipTarget("chrome hearts cemetery", "jewelry", 0.28, 0.42, 6, 1200, "preferred", 8, "Ring, crosses around band"),
    BlueChipTarget("chrome hearts floral cross", "jewelry", 0.25, 0.40, 6, 500, "preferred", 8, "Fleur details on cross"),
    BlueChipTarget("chrome hearts dagger", "jewelry", 0.22, 0.35, 8, 550, "preferred", 8, "Sword pendant"),
    BlueChipTarget("chrome hearts plus bracelet", "jewelry", 0.20, 0.32, 8, 700, "preferred", 8, "Plus sign links"),
    BlueChipTarget("chrome hearts scroll band", "jewelry", 0.20, 0.30, 10, 400, "preferred", 8, "Ring, engraved scroll"),
    BlueChipTarget("chrome hearts beverly hills", "jewelry", 0.22, 0.35, 6, 900, "preferred", 7, "Exclusive location piece"),
    
    # More Tiffany & Co
    BlueChipTarget("tiffany t bracelet", "jewelry", 0.20, 0.32, 10, 1200, "required", 9, "T wire design, iconic"),
    BlueChipTarget("tiffany hardwear", "jewelry", 0.18, 0.28, 10, 800, "required", 9, "Industrial, ball and chain"),
    BlueChipTarget("tiffany knot", "jewelry", 0.20, 0.32, 8, 1500, "required", 9, "Interlocking design, trending"),
    BlueChipTarget("tiffany lock", "jewelry", 0.18, 0.28, 6, 2800, "required", 8, "New collection, high demand"),
    BlueChipTarget("tiffany bone cuff", "jewelry", 0.22, 0.35, 6, 1200, "required", 8, "Elsa Peretti, sculptural"),
    BlueChipTarget("tiffany bean", "jewelry", 0.18, 0.28, 10, 400, "preferred", 9, "Elsa Peretti, entry point"),
    BlueChipTarget("tiffany open heart", "jewelry", 0.18, 0.28, 10, 350, "preferred", 9, "Elsa Peretti, classic"),
    BlueChipTarget("tiffany infinity", "jewelry", 0.15, 0.25, 10, 600, "preferred", 8, "Figure-8 design"),
    BlueChipTarget("tiffany victoria", "jewelry", 0.18, 0.28, 8, 2500, "required", 8, "Marquise diamonds"),
    BlueChipTarget("tiffany solitaire", "jewelry", 0.12, 0.20, 8, 15000, "required", 8, "Engagement ring, certified"),
    BlueChipTarget("tiffany metro", "jewelry", 0.15, 0.25, 8, 1800, "required", 8, "Diamond band, everyday"),
    BlueChipTarget("tiffany atlas", "jewelry", 0.18, 0.28, 8, 1200, "required", 8, "Roman numerals, medallion"),
    BlueChipTarget("tiffany 1837", "jewelry", 0.20, 0.32, 10, 450, "preferred", 9, "Entry collection, numbers"),
    BlueChipTarget("tiffany paloma", "jewelry", 0.18, 0.28, 8, 800, "preferred", 8, "Paloma Picasso designs"),
    BlueChipTarget("tiffany return to", "jewelry", 0.22, 0.35, 10, 350, "preferred", 9, "Heart tag, most popular"),
    
    # More Van Cleef & Arpels
    BlueChipTarget("van cleef 5 motif", "jewelry", 0.18, 0.28, 6, 4500, "required", 9, "Bracelet, 4-leaf clover"),
    BlueChipTarget("van cleef 10 motif", "jewelry", 0.15, 0.25, 5, 8500, "required", 8, "Long necklace"),
    BlueChipTarget("van cleef 20 motif", "jewelry", 0.15, 0.25, 4, 16000, "required", 7, "Very long necklace"),
    BlueChipTarget("van cleef sweet", "jewelry", 0.20, 0.32, 8, 1800, "required", 9, "Small alhambra, entry point"),
    BlueChipTarget("van cleef vintage", "jewelry", 0.18, 0.28, 6, 3800, "required", 8, "Large alhambra pendant"),
    BlueChipTarget("van cleef magic", "jewelry", 0.18, 0.28, 5, 5500, "required", 8, "Between sweet and vintage"),
    BlueChipTarget("van cleef perlee", "jewelry", 0.18, 0.28, 8, 2200, "required", 8, "Beaded design, rings/bracelets"),
    BlueChipTarget("van cleef frivole", "jewelry", 0.20, 0.32, 6, 3200, "required", 8, "3-petal flower design"),
    BlueChipTarget("van cleef two butterfly", "jewelry", 0.18, 0.28, 6, 6500, "required", 7, "Between the finger ring"),
    BlueChipTarget("van cleef clover", "jewelry", 0.15, 0.25, 8, 2800, "required", 8, "Cosmos collection"),
    
    # More Cartier jewelry
    BlueChipTarget("cartier love ring", "jewelry", 0.20, 0.32, 12, 1800, "required", 9, "Screw motif, classic"),
    BlueChipTarget("cartier love necklace", "jewelry", 0.18, 0.28, 10, 3200, "required", 9, "Pendant on chain"),
    BlueChipTarget("cartier love earrings", "jewelry", 0.18, 0.28, 8, 2800, "required", 8, "Studs, screw design"),
    BlueChipTarget("cartier juste un clou", "jewelry", 0.20, 0.32, 10, 2800, "required", 9, "Nail bracelet, edgy"),
    BlueChipTarget("cartier juste un clou ring", "jewelry", 0.22, 0.35, 8, 2200, "required", 8, "Nail ring"),
    BlueChipTarget("cartier trinity", "jewelry", 0.18, 0.28, 10, 1500, "required", 9, "Three gold bands"),
    BlueChipTarget("cartier trinity ring", "jewelry", 0.20, 0.32, 10, 1200, "required", 9, "Rolling ring"),
    BlueChipTarget("cartier amulette", "jewelry", 0.22, 0.35, 8, 1800, "required", 8, "Gemstone pendant"),
    BlueChipTarget("cartier d amour", "jewelry", 0.18, 0.28, 8, 2200, "required", 8, "Solitaire pendant"),
    BlueChipTarget("cartier c de", "jewelry", 0.18, 0.28, 6, 2800, "required", 7, "Logo collection"),
    BlueChipTarget("cartier clash", "jewelry", 0.20, 0.32, 6, 4500, "required", 8, "New collection, punk edge"),
    BlueChipTarget("cartier ecrou", "jewelry", 0.22, 0.35, 5, 3800, "required", 7, "Nut and bolt design"),
    BlueChipTarget("cartier panthere", "jewelry", 0.15, 0.25, 6, 5500, "required", 7, "Iconic cat motif"),
    
    # More Bulgari
    BlueChipTarget("bvlgari serpenti bracelet", "jewelry", 0.18, 0.28, 6, 4500, "required", 8, "Coil design"),
    BlueChipTarget("bvlgari serpenti ring", "jewelry", 0.20, 0.32, 6, 3200, "required", 8, "Snake wraps finger"),
    BlueChipTarget("bvlgari serpenti watch", "jewelry", 0.15, 0.22, 5, 8500, "required", 7, "Tubogas bracelet"),
    BlueChipTarget("bvlgari b zero bracelet", "jewelry", 0.18, 0.28, 8, 2800, "required", 8, "Spiral design"),
    BlueChipTarget("bvlgari b zero necklace", "jewelry", 0.18, 0.28, 8, 2200, "required", 8, "Pendant"),
    BlueChipTarget("bvlgari divas dream bracelet", "jewelry", 0.18, 0.28, 6, 3800, "required", 8, "Fan with gemstone"),
    BlueChipTarget("bvlgari divas dream necklace", "jewelry", 0.18, 0.28, 6, 3200, "required", 8, "Openwork fan"),
    BlueChipTarget("bvlgari parentesi", "jewelry", 0.18, 0.28, 6, 2800, "required", 7, "Architectural links"),
    BlueChipTarget("bvlgari fiorever", "jewelry", 0.18, 0.28, 6, 3500, "required", 7, "Flower design"),
    BlueChipTarget("bvlgari allegra", "jewelry", 0.15, 0.25, 5, 5500, "required", 7, "Colorful gemstones"),
    
    # Hermès jewelry
    BlueChipTarget("hermes clic h", "jewelry", 0.20, 0.32, 10, 700, "required", 9, "Enamel bracelet, entry point"),
    BlueChipTarget("hermes clic clac", "jewelry", 0.20, 0.32, 10, 650, "required", 9, "Same as clic h"),
    BlueChipTarget("hermes kelly bracelet", "jewelry", 0.18, 0.28, 8, 2800, "required", 8, "Kelly buckle"),
    BlueChipTarget("hermes kelly ring", "jewelry", 0.20, 0.32, 6, 2200, "required", 8, "Same buckle"),
    BlueChipTarget("hermes chaine d ancre", "jewelry", 0.18, 0.28, 8, 1800, "required", 8, "Anchor chain"),
    BlueChipTarget("hermes farandole", "jewelry", 0.18, 0.28, 6, 1500, "required", 8, "Link bracelet"),
    BlueChipTarget("hermes filet d or", "jewelry", 0.18, 0.28, 6, 2200, "required", 7, "Mesh design"),
    BlueChipTarget("hermes galop", "jewelry", 0.20, 0.32, 6, 1800, "required", 7, "Horse head"),
    BlueChipTarget("hermes ex libris", "jewelry", 0.18, 0.28, 6, 1200, "required", 7, "Bookplate design"),
    BlueChipTarget("hermes loop", "jewelry", 0.18, 0.28, 6, 1500, "required", 7, "Contemporary"),
    BlueChipTarget("hermes iberia", "jewelry", 0.15, 0.25, 5, 2800, "required", 7, "High jewelry feel"),
    BlueChipTarget("hermes medor", "jewelry", 0.18, 0.28, 5, 3200, "required", 7, "Stud design"),
    
    # Chanel jewelry
    BlueChipTarget("chanel coco crush", "jewelry", 0.18, 0.28, 8, 3200, "required", 9, "Quilted pattern, trending"),
    BlueChipTarget("chanel coco crush ring", "jewelry", 0.20, 0.32, 8, 2800, "required", 9, "Beige gold popular"),
    BlueChipTarget("chanel camelia", "jewelry", 0.18, 0.28, 6, 4500, "required", 8, "Flower motif"),
    BlueChipTarget("chanel comete", "jewelry", 0.18, 0.28, 6, 3800, "required", 8, "Star design"),
    BlueChipTarget("chanel ruban", "jewelry", 0.18, 0.28, 6, 3200, "required", 8, "Bow motif"),
    BlueChipTarget("chanel ultra", "jewelry", 0.18, 0.28, 6, 2800, "required", 8, "Black ceramic"),
    BlueChipTarget("chanel premiere", "jewelry", 0.15, 0.25, 6, 4500, "required", 7, "Watch/bracelet hybrid"),
    BlueChipTarget("chanel baroque", "jewelry", 0.15, 0.25, 5, 5500, "required", 7, "Pearls, statement"),
    BlueChipTarget("chanel 1932", "jewelry", 0.12, 0.20, 4, 8500, "required", 6, "High jewelry"),
    
    # Dior jewelry
    BlueChipTarget("dior rose des vents", "jewelry", 0.20, 0.32, 8, 2200, "required", 9, "Wind rose, reversible"),
    BlueChipTarget("dior rose des vents bracelet", "jewelry", 0.20, 0.32, 8, 1800, "required", 9, "Chain with medallion"),
    BlueChipTarget("dior tribales", "jewelry", 0.22, 0.35, 10, 450, "required", 9, "Double pearl, iconic"),
    BlueChipTarget("dior 30 montaigne", "jewelry", 0.18, 0.28, 6, 1200, "required", 8, "CD logo"),
    BlueChipTarget("dior oui", "jewelry", 0.18, 0.28, 6, 2200, "required", 8, "Engagement style"),
    BlueChipTarget("dior gem", "jewelry", 0.18, 0.28, 6, 2800, "required", 7, "Colorful stones"),
    BlueChipTarget("dior lucky", "jewelry", 0.20, 0.32, 8, 650, "required", 8, "Symbols, clover/star"),
    BlueChipTarget("dior evolutions", "jewelry", 0.18, 0.28, 6, 1500, "required", 7, "Modern"),
    BlueChipTarget("dior bois de rose", "jewelry", 0.15, 0.25, 5, 3200, "required", 7, "Thorn design"),
    BlueChipTarget("dior galons", "jewelry", 0.15, 0.22, 5, 4500, "required", 6, "High jewelry"),
    
    # Louis Vuitton jewelry
    BlueChipTarget("louis vuitton empreinte", "jewelry", 0.20, 0.32, 8, 650, "preferred", 9, "Monogram imprint"),
    BlueChipTarget("louis vuitton nanogram", "jewelry", 0.22, 0.35, 8, 550, "preferred", 9, "Small monogram"),
    BlueChipTarget("louis vuitton idylle", "jewelry", 0.18, 0.28, 8, 850, "preferred", 8, "Blossom collection"),
    BlueChipTarget("louis vuitton blossom", "jewelry", 0.18, 0.28, 8, 1200, "preferred", 8, "Flower design"),
    BlueChipTarget("louis vuitton vivienne", "jewelry", 0.18, 0.28, 6, 2200, "required", 7, "Mascot figure"),
    BlueChipTarget("louis vuitton l to v", "jewelry", 0.18, 0.28, 6, 1800, "preferred", 7, "Letters"),
    BlueChipTarget("louis vuitton volt", "jewelry", 0.18, 0.28, 6, 2800, "required", 7, "Lightning bolt V"),
    BlueChipTarget("louis vuitton pure v", "jewelry", 0.18, 0.28, 6, 2200, "required", 7, "V design"),
    BlueChipTarget("louis vuitton gamble", "jewelry", 0.15, 0.25, 5, 3200, "required", 7, "Dice motif"),
    BlueChipTarget("louis vuitton spirit", "jewelry", 0.15, 0.25, 5, 4500, "required", 6, "High jewelry"),
    
    # Gucci jewelry
    BlueChipTarget("gucci interlocking g", "jewelry", 0.22, 0.35, 10, 550, "preferred", 9, "Logo, classic"),
    BlueChipTarget("gucci horsebit", "jewelry", 0.20, 0.32, 10, 650, "preferred", 9, "Equestrian hardware"),
    BlueChipTarget("gucci flora", "jewelry", 0.18, 0.28, 8, 850, "preferred", 8, "Flower motif"),
    BlueChipTarget("gucci icon", "jewelry", 0.18, 0.28, 8, 450, "preferred", 8, "Band ring"),
    BlueChipTarget("gucci link to love", "jewelry", 0.20, 0.32, 8, 1200, "preferred", 8, "Modular, trending"),
    BlueChipTarget("gucci blind for love", "jewelry", 0.20, 0.32, 8, 550, "preferred", 8, "Engraved"),
    BlueChipTarget("gucci trademark", "jewelry", 0.18, 0.28, 8, 350, "preferred", 8, "Script logo"),
    BlueChipTarget("gucci running g", "jewelry", 0.18, 0.28, 6, 1500, "preferred", 7, "Continuous logo"),
    BlueChipTarget("gucci le marche", "jewelry", 0.15, 0.25, 5, 2200, "required", 7, "High jewelry"),
    BlueChipTarget("gucci hortus", "jewelry", 0.15, 0.25, 5, 2800, "required", 6, "Delicate floral"),
    
    # Messika - Modern diamond brand, trending
    BlueChipTarget("messika move", "jewelry", 0.20, 0.32, 8, 2200, "required", 9, "Sliding diamond, iconic"),
    BlueChipTarget("messika move uno", "jewelry", 0.22, 0.35, 8, 1800, "required", 9, "Single diamond"),
    BlueChipTarget("messika my twin", "jewelry", 0.18, 0.28, 6, 2800, "required", 8, "Toi et moi style"),
    BlueChipTarget("messika glamazon", "jewelry", 0.18, 0.28, 6, 3200, "required", 7, "Bold, sculptural"),
    BlueChipTarget("messika desert bloom", "jewelry", 0.15, 0.25, 5, 4500, "required", 7, "Cactus flower"),
    
    # Repossi - Architectural, fashion insider
    BlueChipTarget("repossi berbere", "jewelry", 0.18, 0.28, 5, 3200, "required", 7, "Claw setting, minimal"),
    BlueChipTarget("repossi serti sur vide", "jewelry", 0.15, 0.25, 4, 5500, "required", 6, "Floating diamond"),
    BlueChipTarget("repossi antifer", "jewelry", 0.18, 0.28, 5, 2800, "required", 7, "Black gold, edgy"),
    
    # Foundrae - Meaningful jewelry, trending
    BlueChipTarget("foundrae medallion", "jewelry", 0.22, 0.35, 6, 2200, "required", 8, "Symbolism, chunky"),
    BlueChipTarget("foundrae cigar band", "jewelry", 0.20, 0.32, 6, 1800, "required", 8, "Wide ring"),
    BlueChipTarget("foundrae fob", "jewelry", 0.18, 0.28, 5, 1500, "required", 7, "Clip-on pendant"),
    BlueChipTarget("foundrae tenet", "jewelry", 0.18, 0.28, 5, 2800, "required", 7, "Core collection"),
    BlueChipTarget("foundrae wholeness", "jewelry", 0.20, 0.32, 5, 2200, "required", 7, "Snake symbol"),
    
    # Spinelli Kilcollin - Stacked rings
    BlueChipTarget("spinelli kilcollin ring", "jewelry", 0.20, 0.32, 6, 2800, "required", 8, "Linked rings"),
    BlueChipTarget("spinelli kilcollin solarium", "jewelry", 0.18, 0.28, 5, 3200, "required", 7, "Gold variations"),
    BlueChipTarget("spinelli kilcollin nova", "jewelry", 0.18, 0.28, 5, 3800, "required", 7, "Diamond accents"),
    
    # Anita Ko - Delicate, celebrity favorite
    BlueChipTarget("anita ko huggies", "jewelry", 0.18, 0.28, 8, 1200, "required", 8, "Small hoops"),
    BlueChipTarget("anita ko bracelet", "jewelry", 0.18, 0.28, 6, 2200, "required", 7, "Chain designs"),
    BlueChipTarget("anita ko ring", "jewelry", 0.18, 0.28, 6, 1800, "required", 7, "Stacking bands"),
    BlueChipTarget("anita ko ear cuff", "jewelry", 0.20, 0.32, 6, 1500, "required", 8, "No piercing needed"),
    
    # Maria Tash - Fine piercing jewelry
    BlueChipTarget("maria tash stud", "jewelry", 0.20, 0.32, 10, 350, "preferred", 9, "Single stud, entry"),
    BlueChipTarget("maria tash hoop", "jewelry", 0.18, 0.28, 8, 550, "preferred", 8, "Hinged ring"),
    BlueChipTarget("maria tash clicker", "jewelry", 0.18, 0.28, 8, 450, "preferred", 8, "Segment ring"),
    BlueChipTarget("maria tash chain", "jewelry", 0.18, 0.28, 6, 650, "preferred", 7, "Draped chain"),
    BlueChipTarget("maria tash diamond", "jewelry", 0.15, 0.25, 6, 1200, "required", 7, "Larger stones"),
    BlueChipTarget("maria tash crescent", "jewelry", 0.18, 0.28, 6, 850, "preferred", 7, "Moon shape"),
    BlueChipTarget("maria tash flower", "jewelry", 0.18, 0.28, 6, 750, "preferred", 7, "Floral design"),
    BlueChipTarget("maria tash spike", "jewelry", 0.20, 0.32, 6, 550, "preferred", 8, "Edgy"),
    
    # Hanut Singh - Art deco revival
    BlueChipTarget("hanut singh ring", "jewelry", 0.18, 0.28, 5, 2200, "required", 7, "Vintage inspired"),
    BlueChipTarget("hanut singh earrings", "jewelry", 0.18, 0.28, 5, 2800, "required", 7, "Chandelier style"),
    BlueChipTarget("hanut singh bracelet", "jewelry", 0.15, 0.25, 4, 3800, "required", 6, "Statement piece"),
    
    # Sophie Buhai - Minimalist, sculptural
    BlueChipTarget("sophie buhai ring", "jewelry", 0.22, 0.35, 6, 450, "preferred", 8, "Organic shapes"),
    BlueChipTarget("sophie buhai earrings", "jewelry", 0.20, 0.32, 6, 550, "preferred", 8, "Drop designs"),
    BlueChipTarget("sophie buhai pendant", "jewelry", 0.20, 0.32, 5, 650, "preferred", 7, "Sculptural"),
    BlueChipTarget("sophie buhai hair", "jewelry", 0.18, 0.28, 5, 750, "preferred", 7, "Accessories"),
    
    # Charlotte Chesnais - Architectural
    BlueChipTarget("charlotte chesnais ring", "jewelry", 0.20, 0.32, 6, 550, "preferred", 8, "Sculptural"),
    BlueChipTarget("charlotte chesnais bracelet", "jewelry", 0.18, 0.28, 6, 850, "preferred", 7, "Twisted designs"),
    BlueChipTarget("charlotte chesnais earrings", "jewelry", 0.18, 0.28, 6, 750, "preferred", 7, "Statement"),
    BlueChipTarget("charlotte chesnais necklace", "jewelry", 0.18, 0.28, 5, 950, "preferred", 7, "Bold"),
    
    # CompletedWorks - Contemporary pearl
    BlueChipTarget("completedworks ring", "jewelry", 0.20, 0.32, 5, 450, "preferred", 7, "Modern pearl"),
    BlueChipTarget("completedworks earrings", "jewelry", 0.20, 0.32, 5, 550, "preferred", 7, "Sculptural"),
    BlueChipTarget("completedworks bracelet", "jewelry", 0.18, 0.28, 5, 650, "preferred", 7, "Vermeil"),
    
    # Alighieri - Poetic, textured
    BlueChipTarget("alighieri necklace", "jewelry", 0.22, 0.35, 8, 350, "preferred", 8, "Dante inspired"),
    BlueChipTarget("alighieri earrings", "jewelry", 0.20, 0.32, 8, 280, "preferred", 8, "Mismatched"),
    BlueChipTarget("alighieri ring", "jewelry", 0.20, 0.32, 6, 320, "preferred", 7, "Molten texture"),
    BlueChipTarget("alighieri bracelet", "jewelry", 0.18, 0.28, 6, 380, "preferred", 7, "Chain"),
    
    # Missoma - Accessible luxury
    BlueChipTarget("missoma necklace", "jewelry", 0.25, 0.40, 10, 250, "preferred", 9, "Layering chains"),
    BlueChipTarget("missoma bracelet", "jewelry", 0.25, 0.40, 10, 180, "preferred", 9, "Harris Reed collab"),
    BlueChipTarget("missoma earrings", "jewelry", 0.22, 0.35, 8, 220, "preferred", 8, "Huggies"),
    BlueChipTarget("missoma pendant", "jewelry", 0.22, 0.35, 8, 280, "preferred", 8, "Coin designs"),
    BlueChipTarget("missoma ring", "jewelry", 0.22, 0.35, 8, 150, "preferred", 8, "Stackable"),
    
    # Astrid & Miyu - Delicate, stackable
    BlueChipTarget("astrid miyu chain", "jewelry", 0.22, 0.35, 8, 120, "preferred", 8, "Layering"),
    BlueChipTarget("astrid miyu hoop", "jewelry", 0.20, 0.32, 8, 85, "preferred", 8, "Everyday"),
    BlueChipTarget("astrid miyu stud", "jewelry", 0.22, 0.35, 8, 65, "preferred", 8, "Minimal"),
    
    # Catbird - NYC favorite
    BlueChipTarget("catbird ring", "jewelry", 0.20, 0.32, 8, 350, "preferred", 8, "Stacking bands"),
    BlueChipTarget("catbird bracelet", "jewelry", 0.18, 0.28, 6, 280, "preferred", 7, "Chain"),
    BlueChipTarget("catbird necklace", "jewelry", 0.18, 0.28, 6, 320, "preferred", 7, "Delicate"),
    
    # Stone and Strand - Dainty diamonds
    BlueChipTarget("stone and strand ring", "jewelry", 0.18, 0.28, 6, 450, "preferred", 7, "Pavé"),
    BlueChipTarget("stone and strand necklace", "jewelry", 0.18, 0.28, 6, 550, "preferred", 7, "Delicate"),
    BlueChipTarget("stone and strand bracelet", "jewelry", 0.18, 0.28, 6, 480, "preferred", 7, "Chain"),
    BlueChipTarget("stone and strand earrings", "jewelry", 0.18, 0.28, 6, 380, "preferred", 7, "Studs"),
]

# ARCHIVE FASHION (Proven performers)
BLUE_CHIP_FASHION = [
    BlueChipTarget("rick owens geobasket", "fashion", 0.25, 0.40, 8, 800, "preferred", 8, "Iconic sneaker"),
    BlueChipTarget("rick owens dunks", "fashion", 0.30, 0.50, 6, 1200, "preferred", 7, "Rare, high margin"),
    BlueChipTarget("rick owens leather jacket", "fashion", 0.25, 0.40, 6, 1500, "preferred", 7, "Staple piece"),
    BlueChipTarget("margiela tabi boots", "fashion", 0.22, 0.35, 10, 700, "preferred", 9, "Split toe design"),
    BlueChipTarget("margiela tabi heels", "fashion", 0.20, 0.30, 8, 600, "preferred", 8, "Fashion favorite"),
    BlueChipTarget("margiela replica sneakers", "fashion", 0.18, 0.28, 12, 400, "preferred", 9, "German army trainer"),
    BlueChipTarget("saint laurent teddy jacket", "fashion", 0.20, 0.35, 10, 1200, "preferred", 9, "Hedi Slimane classic"),
    BlueChipTarget("saint laurent wyatt boots", "fashion", 0.18, 0.30, 10, 800, "preferred", 9, "Chelsea boot"),
    BlueChipTarget("helmut lang leather jacket", "fashion", 0.25, 0.40, 6, 600, "preferred", 7, "90s archive"),
    BlueChipTarget("raf simons riot bomber", "fashion", 0.30, 0.45, 5, 1000, "preferred", 6, "Archive grail"),
    
    # Kiko Kostadinov - Bulgarian designer, cult following
    BlueChipTarget("kiko kostadinov asics", "fashion", 0.25, 0.40, 10, 350, "preferred", 9, "Sneaker collabs, high demand"),
    BlueChipTarget("kiko kostadinov jacket", "fashion", 0.22, 0.35, 6, 800, "preferred", 8, "Technical outerwear"),
    BlueChipTarget("kiko kostadinov pants", "fashion", 0.20, 0.32, 8, 450, "preferred", 8, "Pleated, utilitarian"),
    BlueChipTarget("kiko kostadinov shirt", "fashion", 0.20, 0.30, 8, 350, "preferred", 8, "Workwear inspired"),
    BlueChipTarget("kiko kostadinov sweater", "fashion", 0.18, 0.28, 6, 550, "preferred", 7, "Knitwear, unique patterns"),
    BlueChipTarget("kiko kostadinov camier", "fashion", 0.22, 0.35, 5, 1200, "preferred", 7, "Biker jacket"),
    BlueChipTarget("kiko kostadinov diru", "fashion", 0.20, 0.32, 5, 650, "preferred", 7, "Denim, distinctive pockets"),
    BlueChipTarget("kiko kostadinov gel korika", "fashion", 0.25, 0.40, 8, 400, "preferred", 9, "Asics gel variant"),
    BlueChipTarget("kiko kostadinov gel burz", "fashion", 0.22, 0.35, 8, 380, "preferred", 8, "Asics trail runner"),
    BlueChipTarget("kiko kostadinov gel delva", "fashion", 0.22, 0.35, 6, 420, "preferred", 8, "Asics hiking shoe"),
    
    # Craig Green - British avant-garde
    BlueChipTarget("craig green jacket", "fashion", 0.22, 0.35, 6, 700, "preferred", 8, "Quilted, architectural"),
    BlueChipTarget("craig green pants", "fashion", 0.20, 0.32, 6, 450, "preferred", 7, "Workwear, straps"),
    BlueChipTarget("craig green shirt", "fashion", 0.20, 0.30, 6, 350, "preferred", 7, "Panel construction"),
    BlueChipTarget("craig green worker", "fashion", 0.22, 0.35, 5, 550, "preferred", 7, "Jacket, multiple pockets"),
    BlueChipTarget("craig green quilted", "fashion", 0.20, 0.32, 6, 650, "preferred", 8, "Signature technique"),
    BlueChipTarget("craig green adidas", "fashion", 0.25, 0.40, 8, 300, "preferred", 9, "Sneaker collabs"),
    
    # Issey Miyake - Japanese innovation
    BlueChipTarget("issey miyake pleats please", "fashion", 0.20, 0.32, 10, 350, "preferred", 9, "Permanent pleats, iconic"),
    BlueChipTarget("issey miyake homme plisse", "fashion", 0.20, 0.32, 10, 400, "preferred", 9, "Mens pleated line"),
    BlueChipTarget("issey miyake baobao", "fashion", 0.18, 0.28, 12, 450, "preferred", 9, "Geometric bag"),
    BlueChipTarget("issey miyake me", "fashion", 0.18, 0.28, 8, 550, "preferred", 8, "A-poc construction"),
    BlueChipTarget("issey miyake 132 5", "fashion", 0.18, 0.28, 6, 650, "preferred", 7, "Origami fashion"),
    BlueChipTarget("issey miyake men", "fashion", 0.20, 0.32, 6, 500, "preferred", 7, "Archive menswear"),
    BlueChipTarget("issey miyake watch", "fashion", 0.15, 0.25, 8, 350, "preferred", 8, "O design, unique face"),
    
    # Yohji Yamamoto - Japanese avant-garde
    BlueChipTarget("yohji yamamoto pour homme", "fashion", 0.20, 0.32, 6, 800, "preferred", 7, "Mainline, black"),
    BlueChipTarget("yohji yamamoto y's", "fashion", 0.18, 0.28, 8, 550, "preferred", 8, "Diffusion, accessible"),
    BlueChipTarget("yohji yamamoto y3", "fashion", 0.22, 0.35, 10, 350, "preferred", 9, "Adidas collab"),
    BlueChipTarget("yohji yamamoto jacket", "fashion", 0.20, 0.30, 6, 900, "preferred", 7, "Deconstructed tailoring"),
    BlueChipTarget("yohji yamamoto pants", "fashion", 0.18, 0.28, 8, 450, "preferred", 8, "Wide leg, drop crotch"),
    BlueChipTarget("yohji yamamoto coat", "fashion", 0.18, 0.28, 5, 1200, "preferred", 7, "Dramatic silhouettes"),
    BlueChipTarget("yohji yamamoto new era", "fashion", 0.25, 0.40, 6, 250, "preferred", 8, "Cap collab"),
    
    # Comme des Garçons - Rei Kawakubo
    BlueChipTarget("comme des garcons play", "fashion", 0.25, 0.40, 15, 150, "preferred", 10, "Heart logo, entry point"),
    BlueChipTarget("comme des garcons shirt", "fashion", 0.20, 0.32, 10, 350, "preferred", 9, "Patchwork, stripes"),
    BlueChipTarget("comme des garcons homme plus", "fashion", 0.18, 0.28, 6, 800, "preferred", 7, "Runway pieces"),
    BlueChipTarget("comme des garcons junya", "fashion", 0.20, 0.32, 6, 700, "preferred", 7, "Watanabe, technical"),
    BlueChipTarget("comme des garcons wallet", "fashion", 0.22, 0.35, 10, 350, "preferred", 9, "SA8100 classic"),
    BlueChipTarget("comme des garcons converse", "fashion", 0.25, 0.40, 12, 180, "preferred", 9, "Play collab"),
    BlueChipTarget("comme des garcons nike", "fashion", 0.25, 0.40, 8, 250, "preferred", 8, "Sneaker collabs"),
    
    # Undercover - Japanese streetwear
    BlueChipTarget("undercover jacket", "fashion", 0.22, 0.35, 6, 700, "preferred", 8, "Graphic, punk influence"),
    BlueChipTarget("undercover hoodie", "fashion", 0.25, 0.40, 8, 450, "preferred", 8, "Prints, collaborations"),
    BlueChipTarget("undercover t shirt", "fashion", 0.30, 0.50, 10, 250, "preferred", 9, "Graphics, limited"),
    BlueChipTarget("undercover nike", "fashion", 0.28, 0.45, 8, 300, "preferred", 9, "Sneaker collabs"),
    BlueChipTarget("undercover valentino", "fashion", 0.20, 0.32, 5, 1200, "preferred", 7, "High fashion collab"),
    BlueChipTarget("undercover gu", "fashion", 0.25, 0.40, 8, 120, "preferred", 8, "Uniqlo collab"),
    
    # Number (N)ine - Archive Japanese
    BlueChipTarget("number nine jacket", "fashion", 0.25, 0.40, 5, 800, "preferred", 7, "Takahiro Miyashita"),
    BlueChipTarget("number nine jeans", "fashion", 0.22, 0.35, 6, 450, "preferred", 7, "Denim, distressing"),
    BlueChipTarget("number nine shirt", "fashion", 0.20, 0.32, 6, 350, "preferred", 7, "Floral, western"),
    BlueChipTarget("number nine boots", "fashion", 0.20, 0.30, 5, 550, "preferred", 6, "Chelsea, archive"),
    
    # Enfants Riches Déprimés — Piece-specific blue chips
    BlueChipTarget("enfants riches deprimes classic logo hoodie", "fashion", 0.30, 0.45, 6, 1600, "preferred", 9, "Most liquid ERD piece"),
    BlueChipTarget("enfants riches deprimes classic logo tee", "fashion", 0.35, 0.50, 8, 900, "preferred", 9, "Highest volume ERD listing"),
    BlueChipTarget("enfants riches deprimes safety pin earring", "fashion", 0.30, 0.45, 6, 400, "preferred", 9, "Most iconic ERD accessory"),
    BlueChipTarget("enfants riches deprimes bennys video hoodie", "fashion", 0.25, 0.40, 5, 2000, "preferred", 8, "Film reference, cult following"),
    BlueChipTarget("enfants riches deprimes menendez hoodie", "fashion", 0.30, 0.45, 5, 1400, "preferred", 8, "Trend-driven, true crime wave"),
    BlueChipTarget("enfants riches deprimes viper room hat", "fashion", 0.35, 0.55, 4, 10000, "preferred", 7, "C&D piece, wide price range"),
    BlueChipTarget("enfants riches deprimes spanish elegy jacket", "fashion", 0.25, 0.40, 4, 6000, "preferred", 7, "Premium moto leather"),
    BlueChipTarget("enfants riches deprimes frozen beauties flannel", "fashion", 0.30, 0.50, 3, 4500, "preferred", 6, "Only 50 made, Kanye co-sign"),

    # The Soloist - Miyashita's current line
    BlueChipTarget("soloist jacket", "fashion", 0.20, 0.32, 5, 900, "preferred", 7, "Deconstructed"),
    BlueChipTarget("soloist shirt", "fashion", 0.18, 0.28, 5, 550, "preferred", 7, "Patchwork"),
    BlueChipTarget("soloist coat", "fashion", 0.18, 0.28, 4, 1200, "preferred", 6, "Long, dramatic"),
    
    # Kapital - Japanese boro/denim
    BlueChipTarget("kapital boro", "fashion", 0.22, 0.35, 6, 800, "preferred", 8, "Patchwork, indigo"),
    BlueChipTarget("kapital ring coat", "fashion", 0.20, 0.32, 6, 700, "preferred", 8, "Blanket coat"),
    BlueChipTarget("kapital century", "fashion", 0.20, 0.32, 8, 350, "preferred", 8, "Denim, repairs"),
    BlueChipTarget("kapital smiley", "fashion", 0.25, 0.40, 10, 250, "preferred", 9, "Embroidery"),
    BlueChipTarget("kapital bandana", "fashion", 0.30, 0.50, 12, 180, "preferred", 9, "Rebuild, patchwork"),
    BlueChipTarget("kapital socks", "fashion", 0.35, 0.55, 15, 65, "preferred", 10, "Entry point, colorful"),
    BlueChipTarget("kapital knit", "fashion", 0.20, 0.32, 6, 450, "preferred", 7, "Sweaters, unique yarn"),
    
    # Engineered Garments - NYC workwear
    BlueChipTarget("engineered garments jacket", "fashion", 0.20, 0.32, 8, 450, "preferred", 8, "Bedford, unstructured"),
    BlueChipTarget("engineered garments pants", "fashion", 0.18, 0.28, 8, 320, "preferred", 8, "Fatigue, multiple pockets"),
    BlueChipTarget("engineered garments shirt", "fashion", 0.20, 0.30, 10, 280, "preferred", 9, "19th century, patchwork"),
    BlueChipTarget("engineered garments nb", "fashion", 0.22, 0.35, 8, 220, "preferred", 8, "New Balance collab"),
    BlueChipTarget("engineered garments hoka", "fashion", 0.22, 0.35, 6, 280, "preferred", 8, "Hoka collab"),
    BlueChipTarget("engineered garments tie", "fashion", 0.25, 0.40, 6, 180, "preferred", 8, "Seasonal prints"),
    
    # Needles - Japanese rebuild
    BlueChipTarget("needles rebuild", "fashion", 0.25, 0.40, 8, 450, "preferred", 9, "7 cuts, flannel"),
    BlueChipTarget("needles track", "fashion", 0.22, 0.35, 10, 350, "preferred", 9, "Papillon, stripes"),
    BlueChipTarget("needles mohair", "fashion", 0.20, 0.32, 8, 380, "preferred", 8, "Cardigan, colorful"),
    BlueChipTarget("needles cowboy", "fashion", 0.20, 0.30, 6, 550, "preferred", 7, "Bootcut, archive"),
    BlueChipTarget("needles butterfly", "fashion", 0.20, 0.32, 8, 320, "preferred", 8, "Embroidery"),
    BlueChipTarget("needles asics", "fashion", 0.25, 0.40, 8, 280, "preferred", 9, "Sneaker collab"),
    
    # Sacai - Japanese hybrid
    BlueChipTarget("sacai nike", "fashion", 0.25, 0.40, 10, 250, "preferred", 9, "LDWaffle, VaporWaffle"),
    BlueChipTarget("sacai blazer", "fashion", 0.22, 0.35, 8, 220, "preferred", 8, "Double swoosh"),
    BlueChipTarget("sacai jacket", "fashion", 0.20, 0.32, 6, 700, "preferred", 7, "Hybrid construction"),
    BlueChipTarget("sacai dress", "fashion", 0.18, 0.28, 6, 650, "preferred", 7, "Layered, pleated"),
    BlueChipTarget("sacai kaws", "fashion", 0.25, 0.40, 6, 350, "preferred", 8, "Artist collab"),
    BlueChipTarget("sacai fragment", "fashion", 0.22, 0.35, 6, 400, "preferred", 8, "Hiroshi Fujiwara"),
    BlueChipTarget("sacai clot", "fashion", 0.25, 0.40, 6, 320, "preferred", 8, "Kiss of Death"),
    
    # Junya Watanabe - Technical/commercial
    BlueChipTarget("junya watanabe cdg", "fashion", 0.20, 0.32, 6, 800, "preferred", 7, "Mainline, patchwork"),
    BlueChipTarget("junya watanabe man", "fashion", 0.18, 0.28, 8, 550, "preferred", 8, "Mens, collaborations"),
    BlueChipTarget("junya watanabe north face", "fashion", 0.22, 0.35, 8, 550, "preferred", 8, "TNF collab"),
    BlueChipTarget("junya watanabe levis", "fashion", 0.22, 0.35, 8, 450, "preferred", 8, "Denim collab"),
    BlueChipTarget("junya watanabe carhartt", "fashion", 0.25, 0.40, 6, 500, "preferred", 8, "Workwear collab"),
    BlueChipTarget("junya watanabe palace", "fashion", 0.25, 0.40, 6, 450, "preferred", 8, "Skate collab"),
    
    # Stone Island - Technical outerwear
    BlueChipTarget("stone island jacket", "fashion", 0.20, 0.32, 10, 550, "preferred", 9, "Ghost, shadow projects"),
    BlueChipTarget("stone island sweater", "fashion", 0.18, 0.28, 10, 400, "preferred", 9, "Knitwear, badge"),
    BlueChipTarget("stone island pants", "fashion", 0.18, 0.28, 8, 380, "preferred", 8, "Cargo, nylon metal"),
    BlueChipTarget("stone island supreme", "fashion", 0.25, 0.40, 8, 450, "preferred", 9, "Hype collab"),
    BlueChipTarget("stone island shadow", "fashion", 0.20, 0.32, 6, 800, "preferred", 8, "Diffusion, experimental"),
    BlueChipTarget("stone island heat reactive", "fashion", 0.22, 0.35, 6, 650, "preferred", 8, "Ice jacket, thermo"),
    BlueChipTarget("stone island badge", "fashion", 0.30, 0.50, 10, 80, "preferred", 9, "Button, rare colors"),
    
    # C.P. Company - Italian sportswear
    BlueChipTarget("cp company jacket", "fashion", 0.20, 0.32, 8, 450, "preferred", 8, "Goggle, explorer"),
    BlueChipTarget("cp company sweater", "fashion", 0.18, 0.28, 8, 350, "preferred", 8, "Lens detail"),
    BlueChipTarget("cp company shirt", "fashion", 0.18, 0.28, 8, 280, "preferred", 8, "Coggles, overshirt"),
    BlueChipTarget("cp company adidas", "fashion", 0.22, 0.35, 6, 400, "preferred", 8, "Spezial collab"),
    
    # Acne Studios - Scandinavian minimal
    BlueChipTarget("acne studios jacket", "fashion", 0.20, 0.32, 8, 650, "preferred", 8, "Leather, shearling"),
    BlueChipTarget("acne studios jeans", "fashion", 0.22, 0.35, 10, 280, "preferred", 9, "Max, 1996, river"),
    BlueChipTarget("acne studios scarf", "fashion", 0.25, 0.40, 10, 220, "preferred", 9, "Canada, oversized"),
    BlueChipTarget("acne studios boots", "fashion", 0.20, 0.32, 8, 550, "preferred", 8, "Jensen, ankle"),
    BlueChipTarget("acne studios sweater", "fashion", 0.18, 0.28, 8, 380, "preferred", 8, "Face patch, crew"),
    BlueChipTarget("acne studios bag", "fashion", 0.18, 0.28, 6, 450, "preferred", 7, "Musubi, knot"),
    
    # Our Legacy - Swedish contemporary
    BlueChipTarget("our legacy jacket", "fashion", 0.20, 0.32, 6, 550, "preferred", 7, "Leather, suede"),
    BlueChipTarget("our legacy shirt", "fashion", 0.22, 0.35, 8, 280, "preferred", 8, "Borrowed, box"),
    BlueChipTarget("our legacy boots", "fashion", 0.20, 0.32, 6, 450, "preferred", 7, "Camion, zip"),
    BlueChipTarget("our legacy sweater", "fashion", 0.18, 0.28, 6, 350, "preferred", 7, "Knit, unique yarn"),
    BlueChipTarget("our legacy stussy", "fashion", 0.25, 0.40, 6, 350, "preferred", 8, "Streetwear collab"),
    
    # Dries Van Noten - Belgian designer
    BlueChipTarget("dries van noten jacket", "fashion", 0.18, 0.28, 6, 900, "preferred", 7, "Prints, embroidery"),
    BlueChipTarget("dries van noten shirt", "fashion", 0.20, 0.32, 6, 450, "preferred", 7, "Silk, floral"),
    BlueChipTarget("dries van noten shoes", "fashion", 0.18, 0.28, 6, 550, "preferred", 7, "Chelsea, derby"),
    BlueChipTarget("dries van noten bag", "fashion", 0.15, 0.25, 5, 800, "preferred", 6, "Pouch, tote"),
    
    # Ann Demeulemeester - Gothic romantic
    BlueChipTarget("ann demeulemeester boots", "fashion", 0.20, 0.32, 6, 700, "preferred", 8, "Lace-up, harness"),
    BlueChipTarget("ann demeulemeester jacket", "fashion", 0.18, 0.28, 5, 900, "preferred", 7, "Tailored, black"),
    BlueChipTarget("ann demeulemeester shirt", "fashion", 0.18, 0.28, 6, 450, "preferred", 7, "Poet, ruffles"),
    BlueChipTarget("ann demeulemeester belt", "fashion", 0.22, 0.35, 6, 350, "preferred", 8, "Harness, iconic"),
    
    # Guidi - Italian leather artisan
    BlueChipTarget("guidi boots", "fashion", 0.20, 0.32, 8, 800, "preferred", 9, "796, 995, horse leather"),
    BlueChipTarget("guidi pl1", "fashion", 0.20, 0.32, 6, 900, "preferred", 8, "Front zip"),
    BlueChipTarget("guidi pl2", "fashion", 0.18, 0.28, 6, 950, "preferred", 8, "Back zip"),
    BlueChipTarget("guidi 788z", "fashion", 0.18, 0.28, 6, 850, "preferred", 8, "Derby, soft horse"),
    BlueChipTarget("guidi bag", "fashion", 0.18, 0.28, 5, 1200, "preferred", 7, "Leather, minimal"),
    BlueChipTarget("guidi sneaker", "fashion", 0.20, 0.32, 6, 650, "preferred", 7, "Runner, distressed"),
    
    # CCP - Carol Christian Poell
    BlueChipTarget("ccp drips", "fashion", 0.25, 0.40, 4, 2500, "required", 6, "Titanium dipped"),
    BlueChipTarget("ccp tornado", "fashion", 0.22, 0.35, 4, 2200, "required", 6, "Leather treatment"),
    BlueChipTarget("ccp prosthetic", "fashion", 0.20, 0.32, 3, 3500, "required", 5, "Artisanal, rare"),
    BlueChipTarget("ccp bison", "fashion", 0.18, 0.28, 4, 1800, "required", 6, "Leather type"),
    BlueChipTarget("ccp horse", "fashion", 0.18, 0.28, 4, 1600, "required", 6, "Leather type"),
    
    # Alyx - Matthew Williams
    BlueChipTarget("alyx roller coaster", "fashion", 0.25, 0.40, 10, 350, "preferred", 9, "Belt, iconic buckle"),
    BlueChipTarget("alyx chest rig", "fashion", 0.22, 0.35, 8, 450, "preferred", 8, "Bag, tactical"),
    BlueChipTarget("alyx nike", "fashion", 0.25, 0.40, 10, 250, "preferred", 9, "Sneaker collabs"),
    BlueChipTarget("alyx necklace", "fashion", 0.22, 0.35, 6, 550, "preferred", 8, "Hardware, industrial"),
    BlueChipTarget("alyx puffer", "fashion", 0.18, 0.28, 6, 800, "preferred", 7, "Jacket, oversized"),
    BlueChipTarget("alyx moncler", "fashion", 0.20, 0.32, 6, 1200, "preferred", 7, "Puffer collab"),
    BlueChipTarget("alyx dior", "fashion", 0.18, 0.28, 5, 1500, "required", 7, "Men's jewelry"),
    
    # Fear of God - Jerry Lorenzo
    BlueChipTarget("fear of god essentials", "fashion", 0.25, 0.40, 15, 120, "preferred", 10, "Entry point, basics"),
    BlueChipTarget("fear of god mainline", "fashion", 0.20, 0.32, 8, 650, "preferred", 8, "Collection, luxury"),
    BlueChipTarget("fear of god sneakers", "fashion", 0.22, 0.35, 10, 350, "preferred", 9, "Nike collab"),
    BlueChipTarget("fear of god jacket", "fashion", 0.18, 0.28, 6, 900, "preferred", 7, "Bomber, shearling"),
    BlueChipTarget("fear of god 5th", "fashion", 0.20, 0.32, 6, 550, "preferred", 7, "Archive collection"),
    BlueChipTarget("fear of god 4th", "fashion", 0.22, 0.35, 5, 650, "preferred", 7, "Archive collection"),
    BlueChipTarget("fear of god zegna", "fashion", 0.18, 0.28, 5, 1200, "preferred", 7, "Tailoring collab"),
    
    # Amiri - LA luxury streetwear
    BlueChipTarget("amiri jeans", "fashion", 0.22, 0.35, 10, 550, "preferred", 9, "MX1, leather patch"),
    BlueChipTarget("amiri jacket", "fashion", 0.20, 0.32, 8, 1200, "preferred", 8, "Bandana, trucker"),
    BlueChipTarget("amiri t shirt", "fashion", 0.25, 0.40, 10, 350, "preferred", 9, "Shotgun, paint"),
    BlueChipTarget("amiri hoodie", "fashion", 0.22, 0.35, 8, 550, "preferred", 8, "Chenille, logo"),
    BlueChipTarget("amiri shoes", "fashion", 0.20, 0.32, 8, 650, "preferred", 8, "Skel top, bone"),
    BlueChipTarget("amiri hat", "fashion", 0.25, 0.40, 8, 280, "preferred", 8, "Trucker, logo"),
    
    # Rhude - Rhuigi Villaseñor
    BlueChipTarget("rhude shirt", "fashion", 0.25, 0.40, 10, 350, "preferred", 9, "Hawaiian, bandana"),
    BlueChipTarget("rhude shorts", "fashion", 0.25, 0.40, 10, 280, "preferred", 9, "Traxedo, side stripe"),
    BlueChipTarget("rhude puma", "fashion", 0.25, 0.40, 8, 220, "preferred", 8, "Sneaker collab"),
    BlueChipTarget("rhude jacket", "fashion", 0.20, 0.32, 6, 800, "preferred", 7, "Racing, motorsport"),
    BlueChipTarget("rhude sweater", "fashion", 0.20, 0.30, 6, 450, "preferred", 7, "Logo, knit"),
    BlueChipTarget("rhude zara", "fashion", 0.30, 0.50, 8, 120, "preferred", 9, "Diffusion, accessible"),
    
    # Gallery Dept. - LA artwear
    BlueChipTarget("gallery dept jeans", "fashion", 0.25, 0.40, 8, 650, "preferred", 8, "Paint splatter, flare"),
    BlueChipTarget("gallery dept t shirt", "fashion", 0.30, 0.50, 10, 280, "preferred", 9, "Vintage, printed"),
    BlueChipTarget("gallery dept hoodie", "fashion", 0.25, 0.40, 8, 550, "preferred", 8, "French logo"),
    BlueChipTarget("gallery dept hat", "fashion", 0.30, 0.50, 8, 220, "preferred", 8, "Trucker, art"),
    BlueChipTarget("gallery dept shorts", "fashion", 0.25, 0.40, 6, 380, "preferred", 7, "Cutoff, paint"),
    BlueChipTarget("gallery dept lanvin", "fashion", 0.20, 0.32, 5, 900, "preferred", 7, "Luxury collab"),
    
    # Denim Tears - Tremaine Emory
    BlueChipTarget("denim tears jeans", "fashion", 0.28, 0.45, 8, 450, "preferred", 8, "Cotton wreath, Levi's"),
    BlueChipTarget("denim tears jacket", "fashion", 0.25, 0.40, 6, 550, "preferred", 7, "Trucker, wreath"),
    BlueChipTarget("denim tears converse", "fashion", 0.30, 0.50, 10, 180, "preferred", 9, "Chuck 70, wreath"),
    BlueChipTarget("denim tears hoodie", "fashion", 0.28, 0.45, 6, 350, "preferred", 8, "French logo, cotton"),
    BlueChipTarget("denim tears shirt", "fashion", 0.25, 0.40, 6, 320, "preferred", 7, "Button up, wreath"),
    BlueChipTarget("denim tears levis", "fashion", 0.28, 0.45, 6, 450, "preferred", 8, "Collaboration"),

    # Vetements — Demna-era pieces (2014-2019) with proven liquidity
    BlueChipTarget("vetements polizei hoodie", "fashion", 0.25, 0.40, 8, 1500, "preferred", 9, "Most iconic Vetements piece, green commands premium"),
    BlueChipTarget("vetements metal logo hoodie", "fashion", 0.25, 0.40, 6, 1200, "preferred", 8, "OG AW15 versions most valuable"),
    BlueChipTarget("vetements dhl tee", "fashion", 0.30, 0.50, 8, 500, "preferred", 8, "SS16 originals are grails, high rep risk"),
    BlueChipTarget("vetements total darkness hoodie", "fashion", 0.25, 0.40, 6, 2500, "preferred", 7, "AW17 reversible, appreciating"),
    BlueChipTarget("vetements champion hoodie", "fashion", 0.25, 0.40, 8, 700, "preferred", 8, "High volume, multiple seasons"),
    BlueChipTarget("vetements snoop dogg", "fashion", 0.25, 0.40, 6, 920, "preferred", 7, "Cross-cultural appeal"),
    BlueChipTarget("vetements alpha industries bomber", "fashion", 0.25, 0.40, 6, 850, "preferred", 7, "Demna-era exclusive, reversible"),
    BlueChipTarget("vetements staff hoodie", "fashion", 0.25, 0.40, 8, 480, "preferred", 8, "Hanes collab, entry Vetements"),
    BlueChipTarget("vetements polizei raincoat", "fashion", 0.25, 0.40, 6, 500, "preferred", 7, "Seasonal demand, fall/winter"),
    BlueChipTarget("vetements securite hoodie", "fashion", 0.25, 0.40, 6, 2000, "preferred", 7, "Institutional parody series"),
]

# Combine all blue-chip targets
ALL_BLUE_CHIP_TARGETS = (
    BLUE_CHIP_JEWELRY +
    BLUE_CHIP_FASHION
)

# Quick lookup by category
TARGETS_BY_CATEGORY = {
    'jewelry': BLUE_CHIP_JEWELRY,
    'fashion': BLUE_CHIP_FASHION,
}


def get_target_config(query: str) -> Optional[BlueChipTarget]:
    """Get configuration for a specific target."""
    query_lower = query.lower()
    for target in ALL_BLUE_CHIP_TARGETS:
        if target.query.lower() == query_lower:
            return target
    return None


def get_targets_by_tier(tier: str) -> List[BlueChipTarget]:
    """Get targets appropriate for customer tier."""
    if tier == 'beginner':
        return [t for t in ALL_BLUE_CHIP_TARGETS if t.max_price <= 3000]
    elif tier == 'intermediate':
        return [t for t in ALL_BLUE_CHIP_TARGETS if t.max_price <= 8000]
    else:  # expert
        return ALL_BLUE_CHIP_TARGETS


def get_targets_by_category(category: str) -> List[BlueChipTarget]:
    """Get targets by category."""
    return TARGETS_BY_CATEGORY.get(category.lower(), [])


def get_high_margin_targets(min_margin: float = 0.30) -> List[BlueChipTarget]:
    """Get targets with high margin potential."""
    return [t for t in ALL_BLUE_CHIP_TARGETS if t.target_margin >= min_margin]


def get_high_liquidity_targets(min_score: int = 9) -> List[BlueChipTarget]:
    """Get targets with high liquidity (fast sellers)."""
    return [t for t in ALL_BLUE_CHIP_TARGETS if t.liquidity_score >= min_score]


# Statistics
def get_target_stats() -> dict:
    """Get statistics about blue-chip targets."""
    return {
        'total_targets': len(ALL_BLUE_CHIP_TARGETS),
        'jewelry': len(BLUE_CHIP_JEWELRY),
        'fashion': len(BLUE_CHIP_FASHION),
        'avg_margin': sum(t.target_margin for t in ALL_BLUE_CHIP_TARGETS) / len(ALL_BLUE_CHIP_TARGETS),
        'high_margin': len(get_high_margin_targets(0.30)),
        'high_liquidity': len(get_high_liquidity_targets(9)),
    }


if __name__ == "__main__":
    # Print stats when run directly
    stats = get_target_stats()
    print("Blue-Chip Target Statistics:")
    print(f"  Total: {stats['total_targets']}")
    print(f"  Watches: {stats['watches']}")
    print(f"  Bags: {stats['bags']}")
    print(f"  Jewelry: {stats['jewelry']}")
    print(f"  Fashion: {stats['fashion']}")
    print(f"  Avg Target Margin: {stats['avg_margin']:.1%}")
    print(f"  High Margin (30%+): {stats['high_margin']}")
    print(f"  High Liquidity (9+): {stats['high_liquidity']}")
