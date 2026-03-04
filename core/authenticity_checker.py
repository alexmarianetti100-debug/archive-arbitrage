"""
Authenticity Checker — Detect replicas and fakes before they enter the pipeline.

This is CRITICAL for maintaining trust and avoiding platform bans.
Includes image-based analysis for stock photo detection, quality checks, and more.
"""

import re
import io
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from PIL import Image
    import imagehash
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False


class AuthStatus(Enum):
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"  # Flag for manual review
    REPLICA = "replica"  # Auto-reject


@dataclass
class ImageCheckResult:
    image_score: float = 1.0  # 0.0-1.0, higher = more authentic-looking
    flags: List[str] = field(default_factory=list)
    stock_photo_detected: bool = False
    photo_count: int = 0


@dataclass
class AuthCheckResult:
    status: AuthStatus
    confidence: float  # 0.0 - 1.0
    reasons: List[str]
    action: str  # "proceed", "review", "reject"
    image_result: Optional[ImageCheckResult] = None


# Keywords that strongly indicate replicas
REPLICA_KEYWORDS = [
    r'\breplica\b', r'\brep\b', r'\b1:1\b', r'\b1 to 1\b', r'\bone to one\b',
    r'\bunauthorized\b', r'\bua\b', r'\bmirror\b', r'\bhigh quality copy\b',
    r'\bsuper copy\b', r'\bAAA\b', r'\bperfect copy\b', r'\bexact copy\b',
    r'\bidentical\b', r'\bindistinguishable\b',
    r'\btop quality\b', r'\bfactory direct\b', r'\boem\b', r'\boriginal equipment\b',
    r'\bgrade\s*[A-Z]\+?\b', r'\bbest version\b', r'\blatest batch\b',
    r'\bcomes with everything\b', r'\bbox tags dust bag\b', r'\ball accessories\b',
    r'\bpremium quality\b', r'\bmasterpiece\b',
]

# Suspicious but not definitive (flag for review)
SUSPICIOUS_KEYWORDS = [
    r'\bhigh quality\b', r'\bpremium\b', r'\bexcellent quality\b', r'\b1:1 quality\b',
    r'\bperfect condition\b.*\bnever worn\b', r'\bwholesale\b', r'\bbulk\b',
    r'\bmultiple available\b', r'\bmore colors\b', r'\bdm for pics\b', r'\bdm for more\b',
    r'\bwhatsapp\b', r'\bwechat\b', r'\bins\b.*\bgram\b', r'\bfollow\s+for\s+more\b',
]

# Brand-specific authentication markers
BRAND_AUTH_MARKERS = {
    "rick owens": {
        "authentic_tags": ["rick owens", "drkshdw", "darkshadow"],
        "common_rep_misspellings": ["rickowens", "drkshaw", "darkshdw"],
        "hardware_details": ["exposed zipper", "milk zipper"],
        "suspicious_low_price": 150,
    },
    "balenciaga": {
        "authentic_tags": ["balenciaga", "paris"],
        "common_rep_misspellings": ["balenciage", "balanciaga"],
        "logo_checks": ["font weight", "letter spacing"],
        "suspicious_low_price": 200,
    },
    "prada": {
        "authentic_tags": ["prada", "milano", "made in italy"],
        "common_rep_misspellings": ["prado", "milian", "milan"],
        "hardware_checks": ["triangle plaque", " Milano spelling"],
        "suspicious_low_price": 250,
    },
    "saint laurent": {
        "authentic_tags": ["saint laurent", "ysl", "paris"],
        "common_rep_misspellings": ["st laurent", "saint laurant"],
        "suspicious_low_price": 200,
    },
    "chrome hearts": {
        "authentic_tags": ["chrome hearts", "925", "sterling"],
        "suspicious_low_price": 300,
    },
    "helmut lang": {
        "authentic_tags": ["helmut lang"],
        "suspicious_low_price": 100,
    },
}

# Price thresholds by brand (under this = suspicious)
PRICE_THRESHOLDS = {
    "rick owens": 150,
    "balenciaga": 200,
    "prada": 250,
    "saint laurent": 200,
    "chrome hearts": 300,
    "maison margiela": 200,
    "vetements": 150,
    "helmut lang": 100,
    "number nine": 150,
    "undercover": 100,
    "comme des garcons": 80,
    "yohji yamamoto": 150,
    "issey miyake": 100,
}


class AuthenticityChecker:
    """Check items for authenticity markers including image analysis."""

    # Known stock/catalog photo perceptual hashes (grows over time)
    KNOWN_STOCK_HASHES: List[str] = []

    def __init__(self):
        self.replica_patterns = [re.compile(kw, re.IGNORECASE) for kw in REPLICA_KEYWORDS]
        self.suspicious_patterns = [re.compile(kw, re.IGNORECASE) for kw in SUSPICIOUS_KEYWORDS]

    # ------------------------------------------------------------------
    # Image-Based Authentication
    # ------------------------------------------------------------------

    async def check_images(self, images: List[str]) -> ImageCheckResult:
        """
        Analyze listing images for authenticity signals.
        Downloads images and checks for stock photos, quality, watermarks, etc.
        Non-blocking — returns a neutral result on any failure.
        """
        result = ImageCheckResult(photo_count=len(images) if images else 0)

        if not images:
            result.image_score = 0.5
            result.flags.append("No images provided")
            return result

        # Photo count scoring
        if len(images) == 1:
            result.image_score -= 0.15
            result.flags.append("Only 1 photo")
        elif len(images) == 2:
            result.image_score -= 0.05
            result.flags.append("Only 2 photos")

        # URL-based checks (fast, no download needed)
        stock_domains = ["stockx.com", "goat.com", "cdn.shopify.com/s/files"]
        wholesale_domains = ["1688.com", "taobao.com", "aliexpress.com", "yupoo", "dhgate"]

        for img_url in images:
            url_lower = img_url.lower()
            for domain in stock_domains:
                if domain in url_lower:
                    result.flags.append(f"Stock photo source: {domain}")
                    result.stock_photo_detected = True
                    result.image_score -= 0.2
                    break
            for domain in wholesale_domains:
                if domain in url_lower:
                    result.flags.append(f"Wholesale source: {domain}")
                    result.image_score -= 0.3
                    break

        # Deep image analysis (requires PIL + imagehash + httpx)
        if HAS_IMAGE_LIBS and HAS_HTTPX:
            try:
                downloaded = await self._download_images(images[:5])
                if downloaded:
                    await self._analyze_downloaded_images(downloaded, result)
            except Exception:
                pass  # Never let image checks kill the pipeline

        result.image_score = max(0.0, min(1.0, result.image_score))
        return result

    async def _download_images(self, urls: List[str], timeout: float = 8.0) -> List[Image.Image]:
        """Download images, return PIL Images. Skips failures silently."""
        pil_images = []
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for url in urls:
                try:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                    })
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        img = Image.open(io.BytesIO(resp.content))
                        pil_images.append(img)
                except Exception:
                    continue
        return pil_images

    async def _analyze_downloaded_images(self, pil_images: List[Image.Image], result: ImageCheckResult):
        """Run deep checks on downloaded images."""
        phashes = []
        studio_count = 0

        for img in pil_images:
            try:
                # Perceptual hash for duplicate/stock detection
                phash = str(imagehash.phash(img))
                phashes.append(phash)

                # Check against known stock hashes
                for stock_hash in self.KNOWN_STOCK_HASHES:
                    try:
                        dist = imagehash.hex_to_hash(phash) - imagehash.hex_to_hash(stock_hash)
                        if dist < 10:
                            result.stock_photo_detected = True
                            result.flags.append("Matches known stock photo")
                            result.image_score -= 0.25
                            break
                    except Exception:
                        continue

                width, height = img.size

                # Perfect square crops = common in stock/wholesale
                if width == height and width in (800, 1000, 1200, 1500, 2000):
                    studio_count += 1

                # Very small images = likely thumbnails/stolen
                if width < 300 or height < 300:
                    result.flags.append(f"Very small image: {width}x{height}")
                    result.image_score -= 0.1

                # EXIF data — real photos usually have it
                exif = img.getexif()
                if exif:
                    result.image_score += 0.02  # Slight boost for real camera photos

                # Check for very uniform images (product renders, solid backgrounds)
                try:
                    extrema = img.convert("RGB").getextrema()
                    r_range = extrema[0][1] - extrema[0][0]
                    g_range = extrema[1][1] - extrema[1][0]
                    b_range = extrema[2][1] - extrema[2][0]
                    avg_range = (r_range + g_range + b_range) / 3
                    if avg_range < 50:
                        result.flags.append("Very uniform image — possible product render")
                        result.image_score -= 0.1
                except Exception:
                    pass

            except Exception:
                continue

        # Duplicate detection within listing
        if len(phashes) > 1:
            unique_hashes = set(phashes)
            if len(unique_hashes) < len(phashes):
                dupes = len(phashes) - len(unique_hashes)
                result.flags.append(f"{dupes} duplicate image(s) in listing")
                result.image_score -= 0.15

        # All studio shots = suspicious
        if studio_count >= 3:
            result.flags.append("Multiple studio-quality shots — possible stock photos")
            result.image_score -= 0.15

    # ------------------------------------------------------------------
    # Main check — async with image analysis
    # ------------------------------------------------------------------

    async def check_item_async(
        self,
        title: str,
        description: str = "",
        price: float = 0,
        brand: str = "",
        seller_name: str = "",
        seller_rating: Optional[float] = None,
        seller_sales: int = 0,
        images: List[str] = None,
    ) -> AuthCheckResult:
        """Full async check including image analysis."""
        # Run text-based checks first
        result = self.check_item(
            title=title, description=description, price=price,
            brand=brand, seller_name=seller_name,
            seller_rating=seller_rating, seller_sales=seller_sales,
            images=images,
        )

        # Run image checks
        if images:
            try:
                img_result = await self.check_images(images)
                result.image_result = img_result

                if img_result.stock_photo_detected:
                    result.reasons.append("⚠️ Stock/catalog photo detected")
                    result.confidence = max(0.1, result.confidence - 0.2)
                    if result.status == AuthStatus.AUTHENTIC:
                        result.status = AuthStatus.SUSPICIOUS
                        result.action = "review"

                if img_result.image_score < 0.5:
                    result.confidence = max(0.1, result.confidence - 0.15)
                    result.reasons.extend(img_result.flags[:2])
                elif img_result.image_score > 0.8:
                    result.confidence = min(1.0, result.confidence + 0.05)
            except Exception:
                pass  # Image checks are best-effort

        return result

    # ------------------------------------------------------------------
    # Sync text/price/seller check (original)
    # ------------------------------------------------------------------

    def check_item(
        self,
        title: str,
        description: str = "",
        price: float = 0,
        brand: str = "",
        seller_name: str = "",
        seller_rating: Optional[float] = None,
        seller_sales: int = 0,
        images: List[str] = None,
    ) -> AuthCheckResult:
        """
        Check an item for authenticity (text + price + seller checks).
        For full checks including images, use check_item_async().
        """
        reasons = []
        replica_score = 0.0
        suspicious_score = 0.0

        text_to_check = f"{title} {description}".lower()
        brand_lower = brand.lower()

        # 1. Replica keywords
        for pattern in self.replica_patterns:
            if pattern.search(text_to_check):
                replica_score += 0.3
                match = pattern.search(text_to_check).group()
                reasons.append(f"Replica keyword: '{match}'")

        # 2. Suspicious keywords
        for pattern in self.suspicious_patterns:
            if pattern.search(text_to_check):
                suspicious_score += 0.1
                match = pattern.search(text_to_check).group()
                reasons.append(f"Suspicious phrase: '{match}'")

        # 3. Price analysis
        if brand_lower in PRICE_THRESHOLDS:
            threshold = PRICE_THRESHOLDS[brand_lower]
            if price > 0 and price < threshold:
                price_ratio = price / threshold
                if price_ratio < 0.3:
                    replica_score += 0.4
                    reasons.append(f"Price ${price} is {price_ratio:.0%} of typical minimum (${threshold})")
                elif price_ratio < 0.5:
                    suspicious_score += 0.2
                    reasons.append(f"Price ${price} suspiciously low for {brand} (typical min: ${threshold})")

        # 4. Brand-specific checks
        if brand_lower in BRAND_AUTH_MARKERS:
            markers = BRAND_AUTH_MARKERS[brand_lower]
            for misspelling in markers.get("common_rep_misspellings", []):
                if misspelling in text_to_check:
                    replica_score += 0.25
                    reasons.append(f"Common rep misspelling: '{misspelling}'")

        # 5. Seller reputation
        if seller_sales == 0 and price > 100:
            suspicious_score += 0.15
            reasons.append("New seller with high-value item")

        if seller_rating is not None and seller_rating < 3.0:
            suspicious_score += 0.1
            reasons.append(f"Low seller rating: {seller_rating}")

        # 6. Basic image URL checks (fast, no download)
        if images:
            stock_indicators = ["stockx", "goat"]
            for img in images:
                img_lower = img.lower()
                for indicator in stock_indicators:
                    if indicator in img_lower and "user" not in img_lower:
                        suspicious_score += 0.15
                        reasons.append(f"Possible stock photo source: {indicator}")
                        break

        # Determine final status
        if replica_score >= 0.5:
            return AuthCheckResult(
                status=AuthStatus.REPLICA,
                confidence=min(replica_score, 1.0),
                reasons=reasons,
                action="reject"
            )
        elif replica_score >= 0.3 or suspicious_score >= 0.4:
            return AuthCheckResult(
                status=AuthStatus.SUSPICIOUS,
                confidence=min(replica_score + suspicious_score, 1.0),
                reasons=reasons,
                action="review"
            )
        else:
            return AuthCheckResult(
                status=AuthStatus.AUTHENTIC,
                confidence=1.0 - (replica_score + suspicious_score),
                reasons=reasons or ["No red flags detected"],
                action="proceed"
            )

    def batch_check(self, items: List[dict]) -> List[AuthCheckResult]:
        """Check multiple items."""
        return [
            self.check_item(
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=item.get("price", 0),
                brand=item.get("brand", ""),
                seller_name=item.get("seller_name", ""),
                seller_rating=item.get("seller_rating"),
                seller_sales=item.get("seller_sales", 0),
                images=item.get("images", []),
            )
            for item in items
        ]


def check_authenticity(**kwargs) -> AuthCheckResult:
    """Quick check an item."""
    checker = AuthenticityChecker()
    return checker.check_item(**kwargs)


def format_auth_confidence_bar(confidence: float) -> str:
    """Format confidence as a visual bar for Telegram alerts.
    Returns e.g. '🟢🟢🟢🟢⚪ 80%'
    """
    filled = round(confidence * 5)
    filled = max(0, min(5, filled))
    bar = "🟢" * filled + "⚪" * (5 - filled)
    return f"{bar} {confidence * 100:.0f}%"


if __name__ == "__main__":
    test_cases = [
        {
            "title": "Rick Owens DRKSHDW Geobasket High Tops",
            "price": 120,
            "brand": "rick owens",
            "description": "Great condition, comes with box and tags",
        },
        {
            "title": "Balenciaga Track Sneakers 1:1 Replica",
            "price": 80,
            "brand": "balenciaga",
            "description": "High quality mirror copy, indistinguishable from authentic",
        },
        {
            "title": "Prada Nylon Bag - Wholesale Price",
            "price": 45,
            "brand": "prada",
            "description": "Multiple available, DM for more pics. Premium quality AAA grade",
        },
    ]

    checker = AuthenticityChecker()
    for test in test_cases:
        result = checker.check_item(**test)
        print(f"\n📝 {test['title'][:50]}...")
        print(f"   Status: {result.status.value.upper()}")
        print(f"   Confidence: {result.confidence:.1%}")
        print(f"   Action: {result.action}")
        print(f"   Reasons: {', '.join(result.reasons[:3])}")
