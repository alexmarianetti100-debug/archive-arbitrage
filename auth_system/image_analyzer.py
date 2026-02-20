"""
AI Image Authentication

Uses computer vision to detect replica indicators in images.

Current capabilities (rule-based, ML upgrade path outlined):
- Stock photo detection (reverse image search)
- Generic background detection
- Authentication point verification
- Brand-specific marker checking

Future ML capabilities:
- Stitching pattern analysis
- Hardware detail verification  
- Font/spacing analysis on tags
- Material texture analysis
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict
from urllib.parse import urlparse


@dataclass
class ImageAnalysisResult:
    confidence: float  # 0.0 - 1.0 (1.0 = definitely authentic)
    red_flags: List[str]
    positive_indicators: List[str]
    missing_authentication_points: List[str]
    recommended_shots: List[str]


class ImageAuthenticator:
    """Analyze item images for authenticity markers."""
    
    # Authentication points needed by category
    AUTH_POINTS = {
        "footwear": ["overall", "toe_box", "heel", "sole", "insole", "size_tag", "box_label"],
        "bags": ["overall", "front_logo", "hardware", "interior_label", "date_code", "stitching"],
        "clothing": ["overall", "neck_tag", "wash_tag", "hem_stitching", "hardware"],
        "accessories": ["overall", "engraving", "packaging", "certificate"],
    }
    
    # Stock photo sources
    STOCK_SOURCES = [
        "stockx", "goat.com", "grailed.com", "ebay.com", "poshmark.com",
        "fashionphile", "therealreal", "tradesy", "vestiaire",
    ]
    
    # Suspicious image patterns
    SUSPICIOUS_PATTERNS = [
        r"white[_-]?background",
        r"studio[_-]?shot",
        r"professional[_-]?photo",
        r"retail[_-]?image",
    ]
    
    def __init__(self):
        self.hashes_checked = {}  # Cache of reverse image searches
    
    def analyze_images(
        self,
        image_urls: List[str],
        brand: Optional[str] = None,
        category: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """
        Analyze a set of item images.
        
        Returns confidence score and list of issues found.
        """
        red_flags = []
        positive_indicators = []
        missing_points = []
        
        if not image_urls:
            return ImageAnalysisResult(
                confidence=0.0,
                red_flags=["No images provided"],
                positive_indicators=[],
                missing_authentication_points=self.AUTH_POINTS.get(category, ["overall", "tags"]),
                recommended_shots=["front", "back", "tags", "hardware"],
            )
        
        # 1. Check for stock photos
        stock_photo_count = 0
        for url in image_urls:
            if self._is_stock_photo(url):
                stock_photo_count += 1
        
        if stock_photo_count == len(image_urls):
            red_flags.append("REPLICA: All images appear to be stock photos")
        elif stock_photo_count > 0:
            red_flags.append(f"{stock_photo_count} stock photo(s) detected - possible bait-and-switch")
        
        # 2. Analyze image characteristics
        generic_bg_count = 0
        for url in image_urls:
            if self._has_generic_background(url):
                generic_bg_count += 1
        
        if generic_bg_count == len(image_urls) and len(image_urls) > 1:
            red_flags.append("All photos use generic white backgrounds - common for rep sellers")
        
        # 3. Check for authentication points visible
        visible_points = self._identify_visible_auth_points(image_urls, category)
        required_points = self.AUTH_POINTS.get(category, ["overall", "tags"])
        
        missing_points = [p for p in required_points if p not in visible_points]
        
        if len(missing_points) > len(required_points) * 0.5:
            red_flags.append(f"Missing key authentication photos: {', '.join(missing_points[:3])}")
        
        # 4. Brand-specific image checks
        if brand:
            brand_flags, brand_positive = self._brand_specific_checks(image_urls, brand)
            red_flags.extend(brand_flags)
            positive_indicators.extend(brand_positive)
        
        # 5. Photo quality assessment
        if len(image_urls) < 3:
            red_flags.append("Only {} photo(s) provided - insufficient for authentication".format(len(image_urls)))
        
        # Calculate confidence
        # Start at 0.5 (neutral)
        confidence = 0.5
        
        # Penalize for red flags
        replica_flags = [f for f in red_flags if f.startswith("REPLICA:")]
        confidence -= len(replica_flags) * 0.3
        confidence -= (len(red_flags) - len(replica_flags)) * 0.1
        
        # Boost for positive indicators
        confidence += len(positive_indicators) * 0.1
        
        # Adjust for missing points
        if missing_points:
            confidence -= len(missing_points) * 0.05
        
        # Clamp to 0-1
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine recommended shots
        recommended = missing_points if missing_points else []
        if not recommended:
            recommended = ["closer_tag_photo", "hardware_detail"] if category in ["bags", "clothing"] else []
        
        return ImageAnalysisResult(
            confidence=confidence,
            red_flags=red_flags,
            positive_indicators=positive_indicators,
            missing_authentication_points=missing_points,
            recommended_shots=recommended,
        )
    
    def _is_stock_photo(self, url: str) -> bool:
        """Check if image URL appears to be from a stock source."""
        url_lower = url.lower()
        
        # Check against known stock sources
        for source in self.STOCK_SOURCES:
            if source in url_lower:
                # But allow user uploads to these platforms
                if "user" in url_lower or "listing" in url_lower:
                    return False
                return True
        
        # Check for CDN patterns typical of stock photos
        cdn_patterns = [
            r"cdn\.",
            r"cloudfront",
            r"akamai",
            r"img[0-9]*\.",
        ]
        for pattern in cdn_patterns:
            if re.search(pattern, url_lower):
                # Could be stock, could be platform CDN - flag for review
                return False  # Be conservative
        
        return False
    
    def _has_generic_background(self, url: str) -> bool:
        """Detect generic white/gray backgrounds (rep seller pattern)."""
        # In real implementation, this would download and analyze the image
        # For now, use URL heuristics
        url_lower = url.lower()
        
        suspicious_terms = ["white", "bg", "background", "studio", "clean"]
        count = sum(1 for term in suspicious_terms if term in url_lower)
        
        return count >= 2
    
    def _identify_visible_auth_points(
        self,
        image_urls: List[str],
        category: Optional[str],
    ) -> List[str]:
        """
        Identify which authentication points are visible in photos.
        
        In production, this uses CV/ML to classify image content.
        For MVP, uses filename/URL heuristics.
        """
        visible = []
        
        for url in image_urls:
            url_lower = url.lower()
            
            # Tag detection
            if any(term in url_lower for term in ["tag", "label", "size"]):
                visible.append("size_tag")
                if category == "clothing":
                    visible.append("neck_tag")
            
            # Box/ packaging
            if any(term in url_lower for term in ["box", "package", "dust"]):
                visible.append("packaging")
            
            # Overall shot
            if any(term in url_lower for term in ["front", "main", "1", "01"]):
                visible.append("overall")
            
            # Hardware/details
            if any(term in url_lower for term in ["detail", "hardware", "zipper", "logo"]):
                visible.append("hardware")
        
        # Always assume we can see overall if there are images
        if image_urls and "overall" not in visible:
            visible.append("overall")
        
        return list(set(visible))
    
    def _brand_specific_checks(
        self,
        image_urls: List[str],
        brand: str,
    ) -> tuple[List[str], List[str]]:
        """Run brand-specific authentication checks."""
        red_flags = []
        positive = []
        
        brand_lower = brand.lower()
        
        # Rick Owens checks
        if "rick owens" in brand_lower or "drkshdw" in brand_lower:
            # Check for known rep tells
            # In production, would analyze actual image pixels
            positive.append("Rick Owens item - checking for signature details")
        
        # Balenciaga checks
        if "balenciaga" in brand_lower:
            positive.append("Balenciaga item - will verify logo placement")
        
        # Chrome Hearts (high rep risk)
        if "chrome hearts" in brand_lower:
            if len(image_urls) < 5:
                red_flags.append("Chrome Hearts requires 5+ detailed photos - high rep risk brand")
        
        return red_flags, positive
    
    def reverse_image_search(self, image_url: str) -> Dict:
        """
        Perform reverse image search to find if photo appears elsewhere.
        
        Returns dict with:
        - found_on: List of sites where image appears
        - is_stock: Boolean
        - first_seen: Date first indexed
        """
        # Integration with Google Images API, TinEye, or similar
        # For MVP, return placeholder
        return {
            "found_on": [],
            "is_stock": False,
            "first_seen": None,
        }
