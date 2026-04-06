"""
Shared design system for auto-generated marketing content.

Extracted from build_editorial_v2.py — dark editorial aesthetic with
grain, vignette, and gold accents. All content generators import from here.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os
import random
from typing import List, Tuple, Optional

# ── Canvas sizes ──
INSTAGRAM_SQUARE = (1080, 1080)
INSTAGRAM_PORTRAIT = (1080, 1350)  # 4:5 ratio — carousel standard
INSTAGRAM_STORY = (1080, 1920)     # 9:16 ratio

# ── Color palette ──
BLACK = (8, 8, 8)
DARK_BG = (14, 14, 14)
CARD_BG = (22, 22, 22)
MID_GREY = (140, 140, 140)
LIGHT_GREY = (200, 200, 200)
BODY_TEXT = (190, 188, 185)        # Warm off-white for readability
OFF_WHITE = (240, 237, 232)
GOLD = (215, 190, 140)            # Primary accent
BRIGHT_GOLD = (230, 205, 155)     # Emphasis
RED = (200, 55, 50)
GREEN = (50, 200, 80)
PROFIT_GREEN = (80, 220, 120)
LOSS_RED = (220, 50, 50)
FIRE_ORANGE = (255, 140, 0)
WHALE_PURPLE = (140, 100, 220)

# Fire level colors
FIRE_COLORS = {
    3: FIRE_ORANGE,
    2: GOLD,
    1: LIGHT_GREY,
    0: MID_GREY,
}

# ── Brand accent colors (for brand-specific styling) ──
BRAND_COLORS = {
    "rick owens": (180, 180, 180),
    "chrome hearts": (212, 175, 55),
    "maison margiela": (200, 200, 200),
    "enfants riches deprimes": (200, 50, 50),
    "erd": (200, 50, 50),
    "saint laurent": (220, 220, 220),
    "jean paul gaultier": (180, 140, 200),
    "helmut lang": (160, 160, 160),
    "raf simons": (200, 80, 80),
    "bottega veneta": (100, 160, 100),
    "dior homme": (180, 180, 200),
    "undercover": (140, 140, 160),
}


def load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Load system font with fallback chain."""
    if mono:
        for p in ["/System/Library/Fonts/Menlo.ttc", "/Library/Fonts/Courier New.ttf"]:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue

    if bold:
        for p, idx in [
            ("/System/Library/Fonts/Supplemental/Futura.ttc", 5),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 8),
        ]:
            try:
                return ImageFont.truetype(p, size, index=idx)
            except (OSError, IndexError):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue

    for p in ["/System/Library/Fonts/HelveticaNeue.ttc", "/Library/Fonts/Arial.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def new_canvas(
    size: Tuple[int, int] = INSTAGRAM_PORTRAIT,
    bg: Tuple[int, int, int] = BLACK,
) -> Tuple[Image.Image, ImageDraw.Draw]:
    """Create a blank canvas."""
    img = Image.new("RGB", size, bg)
    return img, ImageDraw.Draw(img)


def add_grain(img: Image.Image, intensity: int = 18) -> Image.Image:
    """Add film grain texture."""
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, intensity, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def add_vignette(img: Image.Image, strength: float = 0.4) -> Image.Image:
    """Add dark vignette around edges."""
    arr = np.array(img).astype(np.float64)
    rows, cols = arr.shape[:2]
    Y, X = np.ogrid[:rows, :cols]
    cy, cx = rows / 2, cols / 2
    dist = np.sqrt((X - cx) ** 2 / (cx ** 2) + (Y - cy) ** 2 / (cy ** 2))
    mask = (1.0 - np.clip(dist * strength, 0, 0.8))[:, :, np.newaxis]
    return Image.fromarray((arr * mask).clip(0, 255).astype(np.uint8))


def add_scanlines(draw: ImageDraw.Draw, height: int) -> None:
    """Draw subtle CRT-style scanlines."""
    width = draw.im.size[0] if hasattr(draw, 'im') else 1080
    for y in range(0, height, 3):
        o = random.randint(7, 14)
        draw.line([(0, y), (width, y)], fill=(o, o, o), width=1)


def finalize(img: Image.Image, grain: int = 18, vignette: float = 0.4) -> Image.Image:
    """Apply grain + vignette post-processing for editorial look."""
    return add_vignette(add_grain(img, grain), vignette)


def wrap_text(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> List[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_text_centered(
    draw: ImageDraw.Draw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int] = OFF_WHITE,
    canvas_width: int = 1080,
    max_width: int = 900,
) -> int:
    """Draw centered text with word wrapping. Returns new Y position."""
    lines = wrap_text(draw, text, font, max_width)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (canvas_width - tw) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += bbox[3] - bbox[1] + 12
    return y


def draw_hline(
    draw: ImageDraw.Draw,
    y: int,
    x1: int = 80,
    x2: int = 1000,
    color: Tuple[int, int, int] = MID_GREY,
    width: int = 1,
) -> None:
    """Draw a horizontal divider line."""
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


def draw_hline_centered(
    draw: ImageDraw.Draw,
    y: int,
    line_width: int = 600,
    canvas_width: int = 1080,
    color: Tuple[int, int, int] = GOLD,
    thickness: int = 2,
) -> None:
    """Draw a centered horizontal accent line."""
    x1 = (canvas_width - line_width) // 2
    draw.line([(x1, y), (x1 + line_width, y)], fill=color, width=thickness)


def draw_pill_badge(
    draw: ImageDraw.Draw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    text_color: Tuple[int, int, int] = BLACK,
    bg_color: Tuple[int, int, int] = GOLD,
    padding_x: int = 20,
    padding_y: int = 8,
) -> Tuple[int, int]:
    """Draw a rounded pill badge. Returns (width, height) of the badge."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w = tw + padding_x * 2
    h = th + padding_y * 2
    radius = h // 2

    # Draw rounded rectangle
    draw.rounded_rectangle(
        [(x, y), (x + w, y + h)],
        radius=radius,
        fill=bg_color,
    )
    draw.text((x + padding_x, y + padding_y), text, font=font, fill=text_color)
    return w, h


def get_brand_accent(brand: str) -> Tuple[int, int, int]:
    """Get accent color for a brand, defaulting to gold."""
    return BRAND_COLORS.get(brand.lower(), GOLD)


def composite_listing_image(
    canvas: Image.Image,
    listing_img: Image.Image,
    region: Tuple[int, int, int, int],
    darken: float = 0.6,
) -> Image.Image:
    """Composite a listing photo into a region of the canvas with darkening overlay.

    Args:
        canvas: The background image to draw on.
        listing_img: The listing photo to composite.
        region: (x1, y1, x2, y2) bounding box on the canvas.
        darken: Darkness level for the overlay (0=invisible, 1=black).
    """
    x1, y1, x2, y2 = region
    target_w, target_h = x2 - x1, y2 - y1

    # Resize listing image to cover the region (crop to fill)
    img_ratio = listing_img.width / listing_img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        # Image is wider — scale by height, crop width
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        # Image is taller — scale by width, crop height
        new_w = target_w
        new_h = int(new_w / img_ratio)

    resized = listing_img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop
    cx = (new_w - target_w) // 2
    cy = (new_h - target_h) // 2
    cropped = resized.crop((cx, cy, cx + target_w, cy + target_h))

    # Apply darkening overlay
    overlay = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    blended = Image.blend(cropped, overlay, darken)

    canvas.paste(blended, (x1, y1))
    return canvas
