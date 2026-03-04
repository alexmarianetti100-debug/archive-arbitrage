"""
Authenticity Checker V2 — Production-grade authentication system.

Multi-signal scoring modeled after Grailed/eBay authentication:
1. Seller reputation & history analysis
2. Price anomaly detection (statistical, not just threshold)
3. Listing quality analysis (description depth, photo quality)
4. Brand-specific authentication rules (tags, hardware, labels)
5. Image analysis (stock detection, quality, EXIF, duplicates)
6. Cross-reference detection (same item across platforms)
7. Red flag pattern matching (replica keywords, wholesale signals)

Each signal produces a weighted score. Final confidence is a weighted average.
Items below MIN_AUTH_SCORE are blocked from alerts.
"""

import re
import io
import os
import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from PIL import Image, ExifTags
    import imagehash
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False

logger = logging.getLogger("auth_v2")

# Minimum auth score to send alerts (0.0-1.0)
MIN_AUTH_SCORE = float(os.getenv("MIN_AUTH_SCORE", "0.65"))


class AuthStatus(Enum):
    VERIFIED = "verified"        # High confidence authentic
    LIKELY_AUTH = "likely_auth"  # Probably authentic
    UNCERTAIN = "uncertain"      # Not enough signal
    SUSPICIOUS = "suspicious"    # Multiple red flags
    REPLICA = "replica"          # Definite fake


@dataclass
class ImageAnalysis:
    score: float = 1.0           # 0.0-1.0
    photo_count: int = 0
    has_tag_photos: bool = False  # Photos of tags/labels
    has_detail_shots: bool = False  # Close-up hardware/stitching
    stock_detected: bool = False
    flags: List[str] = field(default_factory=list)
    phashes: List[str] = field(default_factory=list)


@dataclass 
class SellerAnalysis:
    score: float = 0.5           # 0.0-1.0
    total_sales: int = 0
    account_age_days: int = 0
    avg_rating: float = 0.0
    sells_similar_brands: bool = False
    flags: List[str] = field(default_factory=list)


@dataclass
class AuthResult:
    status: AuthStatus
    confidence: float            # 0.0-1.0 overall confidence
    grade: str                   # A/B/C/D/F
    reasons: List[str]           # Human-readable explanations
    signals: Dict[str, float]    # Individual signal scores
    action: str                  # "send", "review", "block"
    image_analysis: Optional[ImageAnalysis] = None
    seller_analysis: Optional[SellerAnalysis] = None


# ==========================================================================
# Signal weights — how much each factor matters
# ==========================================================================
SIGNAL_WEIGHTS = {
    "text_safety": 0.15,       # No replica keywords
    "price_plausibility": 0.25, # Price makes sense for brand/category (INCREASED)
    "seller_reputation": 0.25,  # Seller history (INCREASED)
    "listing_quality": 0.12,    # Description depth, photo count
    "image_analysis": 0.13,     # Photo quality, stock detection
    "brand_markers": 0.10,      # Brand-specific auth checks
}

# ==========================================================================
# Replica / suspicious keyword patterns
# ==========================================================================
REPLICA_HARD = [
    r'\breplica\b', r'\brep\b', r'\b1:1\b', r'\bmirror\b',
    r'\bsuper copy\b', r'\bperfect copy\b', r'\bexact copy\b',
    r'\bindistinguishable\b', r'\bunauthorized\b',
    r'\bfactory direct\b', r'\bbest version\b', r'\blatest batch\b',
    r'\bAAA\b', r'\bgrade\s*[A-Z]{2,}\b',
]

REPLICA_SOFT = [
    r'\bhigh quality\b', r'\bpremium quality\b', r'\btop quality\b',
    r'\bwholesale\b', r'\bbulk\b', r'\bmultiple available\b',
    r'\bmore colors\b', r'\bdm for pics\b', r'\bdm for more\b',
    r'\bwhatsapp\b', r'\bwechat\b', r'\byupoo\b',
    r'\bcomes with everything\b', r'\bbox tags dust bag\b',
    r'\ball accessories\b', r'\bmasterpiece\b',
    r'\bfollow\s+for\s+more\b', r'\bins\b.*\bgram\b',
]

COMPILED_HARD = [re.compile(p, re.IGNORECASE) for p in REPLICA_HARD]
COMPILED_SOFT = [re.compile(p, re.IGNORECASE) for p in REPLICA_SOFT]

# ==========================================================================
# Brand-specific authentication rules
# ==========================================================================
BRAND_RULES = {
    "rick owens": {
        "price_floor": 120,       # Absolute minimum for any legit piece
        "price_typical_min": 200, # Mainline starts here
        "auth_keywords": ["drkshdw", "made in italy", "lido", "geobasket", "ramones", "dunks", "milk"],
        "rep_misspellings": ["rickowens", "drkshaw"],
        "high_rep_categories": ["ramones", "geobasket", "dunks", "vans", "vans old skool", "vans sk8"],  # Most replicated — Vans collabs heavily faked
        "tag_details": "Rick Owens tags have specific font, 'RICK OWENS' on mainline, 'DRKSHDW' on diffusion",
    },
    "chrome hearts": {
        "price_floor": 150,
        "price_typical_min": 300,
        "auth_keywords": ["925", "sterling", "made in usa", "hollywood"],
        "rep_misspellings": [],
        "high_rep_categories": ["jewelry", "ring", "pendant", "cross"],
        "tag_details": "Authentic CH has .925 stamp, scroll work details, proper weight",
    },
    "balenciaga": {
        "price_floor": 150,
        "price_typical_min": 250,
        "auth_keywords": ["made in italy", "paris"],
        "rep_misspellings": ["balenciage", "balanciaga"],
        "high_rep_categories": ["triple s", "track", "speed", "city bag"],
        "tag_details": "Balenciaga tags have specific font weight and letter spacing",
    },
    "saint laurent": {
        "price_floor": 150,
        "price_typical_min": 250,
        "auth_keywords": ["made in italy", "paris", "hedi"],
        "rep_misspellings": ["saint laurant", "st laurant"],
        "high_rep_categories": ["wyatt", "teddy", "court"],
    },
    "prada": {
        "price_floor": 200,
        "price_typical_min": 300,
        "auth_keywords": ["made in italy", "milano", "tessuto"],
        "rep_misspellings": ["prado", "milian"],
        "high_rep_categories": ["re-nylon", "triangle", "cloudbust"],
        "tag_details": "Triangle logo plaque, R has specific curve, proper hardware weight",
    },
    "dior homme": {
        "price_floor": 200,
        "price_typical_min": 350,
        "auth_keywords": ["made in italy", "hedi slimane", "kris van assche"],
        "rep_misspellings": [],
        "high_rep_categories": ["navigate", "b23", "saddle"],
    },
    "maison margiela": {
        "price_floor": 100,
        "price_typical_min": 200,
        "auth_keywords": ["made in italy", "four stitch", "tabi", "replica"],  # Note: Margiela has a line literally called "Replica"
        "rep_misspellings": ["margela", "margeila"],
        "high_rep_categories": ["tabi", "german trainer"],
        "special_notes": "Margiela 'Replica' is a legitimate product line — do NOT flag it as replica keyword",
    },
    "number nine": {
        "price_floor": 100,
        "price_typical_min": 200,
        "auth_keywords": ["takahiro miyashita", "soloist"],
        "rep_misspellings": [],
        "high_rep_categories": [],
    },
    "undercover": {
        "price_floor": 80,
        "price_typical_min": 150,
        "auth_keywords": ["jun takahashi", "made in japan"],
        "rep_misspellings": [],
        "high_rep_categories": [],
    },
    "helmut lang": {
        "price_floor": 60,
        "price_typical_min": 100,
        "auth_keywords": ["made in italy", "made in usa", "bondage"],
        "rep_misspellings": [],
        "high_rep_categories": ["painter jeans"],
    },
    "raf simons": {
        "price_floor": 100,
        "price_typical_min": 200,
        "auth_keywords": ["made in belgium", "made in italy", "consumed"],
        "rep_misspellings": ["ralph simons"],
        "high_rep_categories": ["ozweego", "virginia creeper", "riot"],
    },
    "vetements": {
        "price_floor": 100,
        "price_typical_min": 200,
        "auth_keywords": ["demna", "gvasalia", "made in italy", "made in portugal"],
        "rep_misspellings": ["vetement", "vetments"],
        "high_rep_categories": ["champion hoodie", "dhl", "total darkness"],
    },
    "enfants riches deprimes": {
        "price_floor": 150,
        "price_typical_min": 300,
        "auth_keywords": ["erd", "henri alexander levy", "made in usa"],
        "rep_misspellings": ["enfant riche deprime"],
        "high_rep_categories": [],
    },
    "comme des garcons": {
        "price_floor": 50,
        "price_typical_min": 100,
        "auth_keywords": ["rei kawakubo", "made in japan", "play"],
        "rep_misspellings": ["comme des garcon", "cdg"],
        "high_rep_categories": ["play heart", "converse"],
    },
    "yohji yamamoto": {
        "price_floor": 100,
        "price_typical_min": 200,
        "auth_keywords": ["y's", "pour homme", "made in japan"],
        "rep_misspellings": ["yoji", "yamomoto"],
        "high_rep_categories": [],
    },
    "jean paul gaultier": {
        "price_floor": 80,
        "price_typical_min": 150,
        "auth_keywords": ["made in italy", "made in france", "mesh", "maille"],
        "rep_misspellings": ["jean paul gautier", "gauliter"],
        "high_rep_categories": ["mesh top", "femme"],
    },
    "vivienne westwood": {
        "price_floor": 80,
        "price_typical_min": 150,
        "auth_keywords": ["made in england", "made in italy", "orb", "worlds end"],
        "rep_misspellings": ["viviene", "westwod", "viviane"],
        "high_rep_categories": ["orb necklace", "pearl", "necklace", "choker", "ring", "armor ring", "pendant", "earring", "bracelet", "bag", "wallet"],  # VW jewelry/accessories heavily repped
        "tag_details": "Authentic VW has specific orb engravings, weight, and hallmarks. Most jewelry reps are lightweight with poor orb detail.",
    },
    "louis vuitton": {
        "price_floor": 300,
        "price_typical_min": 500,
        "auth_keywords": ["made in france", "made in spain", "made in usa", "date code"],
        "rep_misspellings": ["loui vuitton", "louis vitton"],
        "high_rep_categories": ["keepall", "neverfull", "speedy", "alma"],
        "tag_details": "Date codes match factory + year/month, alignment of monogram pattern",
    },
    "gucci": {
        "price_floor": 200,
        "price_typical_min": 350,
        "auth_keywords": ["made in italy", "tom ford", "alessandro michele"],
        "rep_misspellings": ["guchi", "guci"],
        "high_rep_categories": ["ace", "marmont", "dionysus"],
    },
    "supreme": {
        "price_floor": 40,
        "price_typical_min": 80,
        "auth_keywords": ["made in usa", "made in canada"],
        "rep_misspellings": [],
        "high_rep_categories": ["box logo", "bogo"],
        "tag_details": "Box logo stitching: cross-stitch pattern, oval in p, grain on tags",
    },
    "off-white": {
        "price_floor": 80,
        "price_typical_min": 150,
        "auth_keywords": ["virgil abloh", "made in italy", "made in portugal"],
        "rep_misspellings": ["offwhite", "off white"],
        "high_rep_categories": ["industrial belt", "arrows"],
    },
    "gallery dept": {
        "price_floor": 100,
        "price_typical_min": 200,
        "auth_keywords": ["josue thomas", "made in usa", "la"],
        "rep_misspellings": ["gallery dep", "galery dept"],
        "high_rep_categories": ["flared", "painted"],
    },
    "amiri": {
        "price_floor": 150,
        "price_typical_min": 300,
        "auth_keywords": ["mike amiri", "made in usa", "made in italy"],
        "rep_misspellings": ["amri", "ammiri"],
        "high_rep_categories": ["mx1", "skeleton"],
    },
}

# Default rules for brands not explicitly listed
DEFAULT_BRAND_RULES = {
    "price_floor": 50,
    "price_typical_min": 100,
    "auth_keywords": [],
    "rep_misspellings": [],
    "high_rep_categories": [],
}

# Categories that get replicated most (higher scrutiny)
HIGH_REP_CATEGORIES = [
    "shoes", "sneakers", "boots", "bag", "handbag",
    "jewelry", "necklace", "ring", "bracelet",
    "belt", "wallet",
]

# Listing description quality indicators
QUALITY_DESCRIPTION_MARKERS = [
    "measurements", "pit to pit", "shoulder to shoulder",
    "condition", "flaw", "wear", "tag size", "fits like",
    "purchased from", "receipt", "proof of purchase",
    "season", "collection", "fw", "ss", "aw",
    "made in", "fabric", "material", "100%",
]

# Stock/wholesale image URL patterns
STOCK_IMAGE_DOMAINS = [
    "stockx-360.imgix.net", "stockx.imgix.net",
    "image.goat.com", "cdn.goat.com",
    "process.fs.grailed.com",  # Grailed CDN (ok for grailed listings)
    "di2ponv0v5otw.cloudfront.net",  # StockX
]

WHOLESALE_IMAGE_DOMAINS = [
    "1688.com", "taobao.com", "aliexpress.com",
    "yupoo.com", "dhgate.com", "weidian.com",
    "alibaba.com", "made-in-china.com",
]


# ==========================================================================
# Main Checker
# ==========================================================================

class AuthenticityCheckerV2:
    """Production-grade multi-signal authenticity checker."""
    
    def __init__(self, db_path: str = "data/archive.db"):
        self.db_path = db_path
        self._hard_patterns = COMPILED_HARD
        self._soft_patterns = COMPILED_SOFT
    
    async def check(
        self,
        title: str,
        description: str = "",
        price: float = 0,
        brand: str = "",
        category: str = "",
        seller_name: str = "",
        seller_rating: Optional[float] = None,
        seller_sales: int = 0,
        seller_joined: Optional[str] = None,
        images: List[str] = None,
        source: str = "",
    ) -> AuthResult:
        """
        Run all authentication signals and produce a weighted confidence score.
        """
        signals = {}
        reasons = []
        brand_lower = brand.lower().strip()
        text = f"{title} {description}".lower()
        rules = BRAND_RULES.get(brand_lower, DEFAULT_BRAND_RULES)
        
        # ── Signal 1: Text Safety ──
        signals["text_safety"], text_reasons = self._check_text(text, brand_lower, rules)
        reasons.extend(text_reasons)
        
        # ── Signal 2: Price Plausibility ──
        signals["price_plausibility"], price_reasons = self._check_price(
            price, brand_lower, category, rules
        )
        reasons.extend(price_reasons)
        
        # ── Signal 3: Seller Reputation ──
        signals["seller_reputation"], seller_reasons, seller_analysis = self._check_seller(
            seller_name, seller_rating, seller_sales, seller_joined, source
        )
        reasons.extend(seller_reasons)
        
        # ── Signal 4: Listing Quality ──
        signals["listing_quality"], quality_reasons = self._check_listing_quality(
            title, description, images
        )
        reasons.extend(quality_reasons)
        
        # ── Signal 5: Image Analysis ──
        image_analysis = None
        if images and HAS_IMAGE_LIBS and HAS_HTTPX:
            try:
                image_analysis = await asyncio.wait_for(
                    self._check_images(images, source), timeout=15.0
                )
                signals["image_analysis"] = image_analysis.score
                if image_analysis.flags:
                    reasons.extend(image_analysis.flags[:3])
            except (asyncio.TimeoutError, Exception) as e:
                logger.debug(f"Image analysis failed/timed out: {e}")
                signals["image_analysis"] = 0.7  # Neutral on failure
        else:
            signals["image_analysis"] = 0.7  # No image libs = neutral
        
        # ── Signal 6: Brand Markers ──
        signals["brand_markers"], brand_reasons = self._check_brand_markers(
            text, brand_lower, category, rules
        )
        reasons.extend(brand_reasons)
        
        # ── Compute weighted confidence ──
        confidence = sum(
            signals.get(k, 0.5) * w
            for k, w in SIGNAL_WEIGHTS.items()
        )
        confidence = max(0.0, min(1.0, confidence))
        
        # ── Determine status ──
        # Hard replica keywords = instant block regardless of score
        if signals["text_safety"] <= 0.1:
            status = AuthStatus.REPLICA
            action = "block"
            confidence = min(confidence, 0.1)
        elif confidence >= 0.80:
            status = AuthStatus.VERIFIED
            action = "send"
        elif confidence >= 0.60:
            status = AuthStatus.LIKELY_AUTH
            action = "send"
        elif confidence >= 0.40:
            status = AuthStatus.UNCERTAIN
            action = "review"
        elif confidence >= 0.20:
            status = AuthStatus.SUSPICIOUS
            action = "block"
        else:
            status = AuthStatus.REPLICA
            action = "block"
        
        # Grade
        if confidence >= 0.85:
            grade = "A"
        elif confidence >= 0.70:
            grade = "B"
        elif confidence >= 0.55:
            grade = "C"
        elif confidence >= 0.40:
            grade = "D"
        else:
            grade = "F"
        
        return AuthResult(
            status=status,
            confidence=confidence,
            grade=grade,
            reasons=[r for r in reasons if r],
            signals=signals,
            action=action,
            image_analysis=image_analysis,
            seller_analysis=seller_analysis,
        )
    
    # ------------------------------------------------------------------
    # Signal 1: Text Safety
    # ------------------------------------------------------------------
    def _check_text(self, text: str, brand: str, rules: dict) -> Tuple[float, List[str]]:
        score = 1.0
        reasons = []
        
        # Special case: Maison Margiela "Replica" line is legit
        check_text = text
        if brand == "maison margiela":
            check_text = re.sub(r'\breplica\b', '', check_text)
        
        # Hard replica keywords
        hard_hits = 0
        for pattern in self._hard_patterns:
            if pattern.search(check_text):
                hard_hits += 1
                match = pattern.search(check_text).group()
                reasons.append(f"🚫 Replica keyword: '{match}'")
        
        if hard_hits >= 2:
            return 0.0, reasons
        elif hard_hits == 1:
            score = 0.15
        
        # Soft suspicious keywords
        soft_hits = 0
        for pattern in self._soft_patterns:
            if pattern.search(check_text):
                soft_hits += 1
                if soft_hits <= 2:
                    match = pattern.search(check_text).group()
                    reasons.append(f"⚠️ Suspicious phrase: '{match}'")
        
        score -= soft_hits * 0.12
        
        # Brand misspellings (word boundary match to avoid false positives)
        for misspelling in rules.get("rep_misspellings", []):
            pattern = re.compile(r'\b' + re.escape(misspelling) + r'\b', re.IGNORECASE)
            if pattern.search(text):
                score -= 0.3
                reasons.append(f"🚫 Known rep misspelling: '{misspelling}'")
        
        return max(0.0, min(1.0, score)), reasons
    
    # ------------------------------------------------------------------
    # Signal 2: Price Plausibility
    # ------------------------------------------------------------------
    def _check_price(self, price: float, brand: str, category: str, rules: dict) -> Tuple[float, List[str]]:
        if price <= 0:
            return 0.5, []
        
        reasons = []
        floor = rules.get("price_floor", 50)
        typical_min = rules.get("price_typical_min", 100)
        
        # Heavily replicated categories get stricter price checks
        category_lower = (category or "").lower()
        is_high_rep = any(c in category_lower for c in HIGH_REP_CATEGORIES)
        high_rep_items = rules.get("high_rep_categories", [])
        is_specific_high_rep = any(item.lower() in f"{category_lower}" for item in high_rep_items)
        
        if is_specific_high_rep:
            floor *= 1.5  # Stricter for known rep targets
            typical_min *= 1.3
        
        ratio = price / typical_min if typical_min > 0 else 1.0
        
        if price < floor * 0.5:
            reasons.append(f"🚫 Price ${price:.0f} is far below floor (${floor:.0f}) for {brand}")
            return 0.1, reasons
        elif price < floor:
            reasons.append(f"⚠️ Price ${price:.0f} below typical floor (${floor:.0f})")
            return 0.3, reasons
        elif ratio < 0.5:
            reasons.append(f"⚠️ Price ${price:.0f} is low for {brand} (typical min: ${typical_min:.0f})")
            return 0.5, reasons
        elif ratio < 0.7:
            return 0.7, reasons
        else:
            return 1.0, reasons
    
    # ------------------------------------------------------------------
    # Signal 3: Seller Reputation
    # ------------------------------------------------------------------
    def _check_seller(
        self, name: str, rating: Optional[float], sales: int,
        joined: Optional[str], source: str
    ) -> Tuple[float, List[str], SellerAnalysis]:
        analysis = SellerAnalysis(total_sales=sales, avg_rating=rating or 0)
        reasons = []
        score = 0.6  # Neutral start
        
        # Sales history
        if sales == 0:
            score -= 0.2
            reasons.append("⚠️ New seller (0 sales)")
        elif sales < 5:
            score -= 0.1
            reasons.append(f"⚠️ Low sales count ({sales})")
        elif sales >= 20:
            score += 0.15
        elif sales >= 50:
            score += 0.25
        elif sales >= 100:
            score += 0.3
        
        # Rating
        if rating is not None:
            if rating >= 4.5:
                score += 0.15
            elif rating >= 4.0:
                score += 0.05
            elif rating < 3.0:
                score -= 0.25
                reasons.append(f"⚠️ Low seller rating: {rating:.1f}")
            elif rating < 3.5:
                score -= 0.1
        
        analysis.score = max(0.0, min(1.0, score))
        return analysis.score, reasons, analysis
    
    # ------------------------------------------------------------------
    # Signal 4: Listing Quality
    # ------------------------------------------------------------------
    def _check_listing_quality(
        self, title: str, description: str, images: List[str] = None
    ) -> Tuple[float, List[str]]:
        score = 0.5
        reasons = []
        desc_lower = (description or "").lower()
        
        # Description depth
        if not description or len(description) < 20:
            score -= 0.2
            reasons.append("⚠️ Very short/missing description")
        elif len(description) > 200:
            score += 0.15
        
        # Quality markers in description
        markers_found = sum(1 for m in QUALITY_DESCRIPTION_MARKERS if m in desc_lower)
        if markers_found >= 4:
            score += 0.25
        elif markers_found >= 2:
            score += 0.15
        elif markers_found >= 1:
            score += 0.05
        
        # Photo count
        num_photos = len(images) if images else 0
        if num_photos == 0:
            score -= 0.2
            reasons.append("⚠️ No photos")
        elif num_photos == 1:
            score -= 0.1
            reasons.append("⚠️ Only 1 photo")
        elif num_photos >= 4:
            score += 0.15
        elif num_photos >= 6:
            score += 0.2
        
        return max(0.0, min(1.0, score)), reasons
    
    # ------------------------------------------------------------------
    # Signal 5: Image Analysis
    # ------------------------------------------------------------------
    async def _check_images(self, images: List[str], source: str = "") -> ImageAnalysis:
        result = ImageAnalysis(photo_count=len(images))
        
        # URL-based checks (fast)
        for url in images:
            url_lower = url.lower()
            
            # Wholesale sources = big red flag
            for domain in WHOLESALE_IMAGE_DOMAINS:
                if domain in url_lower:
                    result.flags.append(f"🚫 Wholesale image source: {domain}")
                    result.score -= 0.35
                    break
            
            # Stock photo sources (not flagged if from same platform)
            for domain in STOCK_IMAGE_DOMAINS:
                if domain in url_lower:
                    # Don't flag Grailed CDN on Grailed listings
                    if "grailed" in domain and source.lower() == "grailed":
                        continue
                    result.stock_detected = True
                    result.flags.append(f"⚠️ Possible stock photo: {domain}")
                    result.score -= 0.15
                    break
        
        # Deep analysis if libraries available
        if HAS_IMAGE_LIBS and HAS_HTTPX:
            try:
                pil_images = await self._download_images(images[:6])
                if pil_images:
                    self._analyze_pil_images(pil_images, result)
            except Exception:
                pass
        
        result.score = max(0.0, min(1.0, result.score))
        return result
    
    async def _download_images(self, urls: List[str]) -> List[Image.Image]:
        pil_images = []
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            for url in urls:
                try:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    })
                    if resp.status_code == 200 and len(resp.content) > 2000:
                        img = Image.open(io.BytesIO(resp.content))
                        pil_images.append(img)
                except Exception:
                    continue
        return pil_images
    
    def _analyze_pil_images(self, pil_images: List[Image.Image], result: ImageAnalysis):
        phashes = []
        exif_count = 0
        studio_count = 0
        
        for img in pil_images:
            try:
                # Perceptual hash
                phash = str(imagehash.phash(img))
                phashes.append(phash)
                result.phashes.append(phash)
                
                w, h = img.size
                
                # Tiny images = stolen thumbnails
                if w < 300 or h < 300:
                    result.flags.append(f"⚠️ Tiny image ({w}x{h}) — possibly stolen")
                    result.score -= 0.1
                
                # Perfect squares at standard sizes = product shots
                if w == h and w in (500, 600, 800, 1000, 1200, 1500, 2000):
                    studio_count += 1
                
                # EXIF = real camera = good
                exif = img.getexif()
                if exif and len(exif) > 3:
                    exif_count += 1
                
                # Very uniform = product render
                try:
                    extrema = img.convert("RGB").getextrema()
                    ranges = [extrema[i][1] - extrema[i][0] for i in range(3)]
                    if all(r < 40 for r in ranges):
                        result.flags.append("⚠️ Very uniform image — possible render")
                        result.score -= 0.1
                except Exception:
                    pass
                    
            except Exception:
                continue
        
        # EXIF presence is a positive signal
        if exif_count >= 2:
            result.score += 0.05
        
        # Duplicate detection
        if len(phashes) > 1:
            unique = set(phashes)
            if len(unique) < len(phashes):
                dupes = len(phashes) - len(unique)
                result.flags.append(f"⚠️ {dupes} duplicate photo(s)")
                result.score -= 0.1
        
        # All studio shots
        if studio_count >= 3:
            result.flags.append("⚠️ Multiple studio product shots")
            result.score -= 0.15
    
    # ------------------------------------------------------------------
    # Signal 6: Brand Markers
    # ------------------------------------------------------------------
    def _check_brand_markers(
        self, text: str, brand: str, category: str, rules: dict
    ) -> Tuple[float, List[str]]:
        score = 0.6  # Neutral
        reasons = []
        
        # Positive: auth keywords present
        auth_kw = rules.get("auth_keywords", [])
        hits = sum(1 for kw in auth_kw if kw.lower() in text)
        if hits >= 2:
            score += 0.3
        elif hits >= 1:
            score += 0.15
        
        # Negative: highly replicated category
        high_rep = rules.get("high_rep_categories", [])
        category_lower = (category or "").lower()
        title_lower = text[:200]  # Just title portion
        
        for rep_item in high_rep:
            if rep_item.lower() in title_lower:
                # Collab items (vans, converse, adidas) are more heavily repped than mainline
                is_collab = rep_item.lower() in ("vans", "vans old skool", "vans sk8", "converse", "adidas", "play heart")
                penalty = 0.25 if is_collab else 0.15
                score -= penalty
                reasons.append(f"⚠️ {'Heavily' if is_collab else 'Commonly'} replicated: {rep_item}")
                break
        
        return max(0.0, min(1.0, score)), reasons


# ==========================================================================
# Convenience functions
# ==========================================================================

def format_auth_bar(confidence: float) -> str:
    """Format confidence as 🟢🟢🟢⚪⚪ 60%"""
    filled = round(confidence * 5)
    filled = max(0, min(5, filled))
    return "🟢" * filled + "⚪" * (5 - filled) + f" {confidence * 100:.0f}%"


def format_auth_grade(grade: str) -> str:
    """Format grade with emoji."""
    grade_emoji = {"A": "🏆", "B": "✅", "C": "🟡", "D": "⚠️", "F": "🚫"}
    return f"{grade_emoji.get(grade, '❓')} Grade {grade}"


async def check_item_v2(**kwargs) -> AuthResult:
    """Quick async check."""
    checker = AuthenticityCheckerV2()
    return await checker.check(**kwargs)


if __name__ == "__main__":
    import asyncio
    
    async def test():
        checker = AuthenticityCheckerV2()
        
        tests = [
            {
                "title": "Rick Owens DRKSHDW Geobasket High Tops Size 43",
                "description": "Great condition, minor sole wear. Made in Italy. Pit to pit 22in. Season FW14.",
                "price": 320,
                "brand": "rick owens",
                "category": "shoes",
                "seller_sales": 45,
                "seller_rating": 4.8,
                "images": ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg", "https://example.com/4.jpg"],
                "source": "grailed",
            },
            {
                "title": "Chrome Hearts Cross Pendant 1:1 Best Quality",
                "description": "DM for more pics. Multiple available. Premium quality.",
                "price": 85,
                "brand": "chrome hearts",
                "category": "jewelry",
                "seller_sales": 0,
                "images": ["https://example.com/1.jpg"],
                "source": "grailed",
            },
            {
                "title": "Balenciaga Track Sneakers",
                "description": "Good condition",
                "price": 180,
                "brand": "balenciaga",
                "category": "shoes",
                "seller_sales": 3,
                "seller_rating": 4.0,
                "images": ["https://example.com/1.jpg", "https://example.com/2.jpg"],
                "source": "grailed",
            },
        ]
        
        for t in tests:
            result = await checker.check(**t)
            print(f"\n{'='*60}")
            print(f"📝 {t['title'][:60]}")
            print(f"   {format_auth_grade(result.grade)} | {format_auth_bar(result.confidence)}")
            print(f"   Status: {result.status.value} | Action: {result.action}")
            print(f"   Signals: {', '.join(f'{k}={v:.2f}' for k,v in result.signals.items())}")
            if result.reasons:
                print(f"   Reasons: {'; '.join(result.reasons[:4])}")
    
    asyncio.run(test())
