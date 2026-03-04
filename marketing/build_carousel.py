#!/usr/bin/env python3
"""
Build Instagram carousel slides for Archive Arbitrage.
Dark editorial aesthetic — black/dark grey backgrounds, white/gold text.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys

# Paths
OUT_DIR = os.path.join(os.path.dirname(__file__), "posts")
os.makedirs(OUT_DIR, exist_ok=True)

# Instagram carousel = 1080x1350 (4:5 ratio)
W, H = 1080, 1350

# Colors
BG_BLACK = (10, 10, 10)
BG_DARK = (18, 18, 18)
TEXT_WHITE = (255, 255, 255)
TEXT_GREY = (200, 200, 200)  # Bumped up for mobile readability
TEXT_GOLD = (212, 175, 55)
TEXT_RED = (220, 50, 50)
TEXT_GREEN = (50, 200, 80)
ACCENT_LINE = (212, 175, 55)

# Fonts (macOS system fonts)
def load_font(size, bold=False):
    """Load a clean sans-serif font."""
    paths = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        try:
            # Index 0 = Regular, higher indices = Bold/Italic variants
            idx = 1 if bold else 0
            return ImageFont.truetype(p, size, index=idx)
        except (OSError, IndexError):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def new_slide(bg_color=BG_BLACK):
    """Create a blank slide."""
    img = Image.new("RGB", (W, H), bg_color)
    return img, ImageDraw.Draw(img)


def draw_centered_text(draw, y, text, font, fill=TEXT_WHITE, max_width=900):
    """Draw centered text, wrapping if needed."""
    lines = wrap_text(draw, text, font, max_width)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += bbox[3] - bbox[1] + 12
    return y


def wrap_text(draw, text, font, max_width):
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_gold_line(draw, y, width=600):
    """Draw a centered gold accent line."""
    x1 = (W - width) // 2
    draw.line([(x1, y), (x1 + width, y)], fill=ACCENT_LINE, width=2)


def draw_header(draw, text, y=80):
    """Draw the @archivearbitrage header."""
    font = load_font(28)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=TEXT_GOLD)
    return y + 50


def draw_slide_number(draw, num, total):
    """Draw slide counter in bottom right."""
    font = load_font(24)
    text = f"{num}/{total}"
    draw.text((W - 80, H - 50), text, font=font, fill=TEXT_GREY)


def draw_footer_cta(draw, text="@archivearbitrage"):
    """Draw footer CTA."""
    font = load_font(28)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - 80), text, font=font, fill=TEXT_GOLD)


# ══════════════════════════════════════════════════════════════
# CAROUSEL 1: "Authenticating Chrome Hearts — 5 Tells"
# ══════════════════════════════════════════════════════════════

def build_chrome_hearts_auth():
    slides = []
    total = 7

    # SLIDE 1: Cover
    img, draw = new_slide()

    title_font = load_font(64, bold=True)
    sub_font = load_font(32)
    detail_font = load_font(26)

    # Top gold accent lines (decorative)
    draw_gold_line(draw, 120, 200)
    draw_gold_line(draw, 130, 300)

    y = 400
    y = draw_centered_text(draw, y, "AUTHENTICATING", title_font, TEXT_WHITE)
    y = draw_centered_text(draw, y + 20, "CHROME HEARTS", title_font, TEXT_GOLD)
    y += 50
    draw_gold_line(draw, y)
    y += 50
    y = draw_centered_text(draw, y, "5 tells that separate", sub_font, TEXT_GREY)
    y = draw_centered_text(draw, y + 8, "real from rep", sub_font, TEXT_GREY)
    y += 60

    # Quick preview of what's inside
    preview_items = [".925 Stamp", "Weight", "Scroll Pattern", "Seller", "Price"]
    for item in preview_items:
        draw_centered_text(draw, y, f"-- {item} --", detail_font, (80, 80, 80))
        y += 35

    draw_centered_text(draw, H - 180, "SWIPE >>", load_font(28), TEXT_GREY)
    draw_footer_cta(draw)
    draw_slide_number(draw, 1, total)
    slides.append(img)

    # SLIDES 2-6: The 5 tells
    tells = [
        {
            "number": "01",
            "title": "THE .925 STAMP",
            "check": "Run your fingernail across it",
            "real": "Deep engraving — your nail catches in the grooves",
            "fake": "Flat, surface-level print — nail slides right over",
            "tip": "This is the single most reliable quick-check. Reps can't replicate the depth of real sterling stamps.",
        },
        {
            "number": "02",
            "title": "WEIGHT & FEEL",
            "check": "Hold it in your palm",
            "real": "Heavy. Solid .925 sterling silver has real heft — a cross pendant should feel substantial",
            "fake": "Light and hollow. Zinc alloy or plated brass feels tinny and cheap",
            "tip": "Chrome Hearts silver is thick-gauge. If it feels like costume jewelry, it is.",
        },
        {
            "number": "03",
            "title": "THE SCROLL PATTERN",
            "check": "Examine the floral scroll engravings",
            "real": "Deep, crisp lines with consistent depth. Hand-finished edges. Slight variations = handmade",
            "fake": "Shallow, uniform machine lines. Too perfect = mass produced. Mushy details",
            "tip": "Real CH is handmade in Hollywood. Perfect uniformity is actually a red flag.",
        },
        {
            "number": "04",
            "title": "SELLER VERIFICATION",
            "check": "Check the source — not just the piece",
            "real": "Purchased from CH boutique, trusted consignment (TRR, Vestiaire), or seller with 50+ sales & reviews",
            "fake": "New accounts, stock photos, 'wholesale' sellers, prices 50%+ below retail",
            "tip": "CH has NO website and NO authorized online retailers. If someone says 'authorized dealer' — run.",
        },
        {
            "number": "05",
            "title": "THE PRICE TEST",
            "check": "If the deal seems too good to be true...",
            "real": "CH cross pendant: $800-1500+. Trucker hat: $400-700. Ring: $300-1200. These are the real ranges.",
            "fake": "Cross pendant under $400. Trucker hat under $250. Any 'Chrome Hearts' under $200 = guaranteed fake",
            "tip": "We built price floors into our bot. Every deal we send has already passed authentication scoring.",
        },
    ]

    num_font = load_font(80, bold=True)
    title_font = load_font(48, bold=True)
    label_font = load_font(30, bold=True)
    body_font = load_font(30)
    tip_font = load_font(26)

    for i, tell in enumerate(tells):
        img, draw = new_slide()
        draw_header(draw, "@archivearbitrage")

        # Number — larger, positioned higher
        draw_centered_text(draw, 140, tell["number"], num_font, TEXT_GOLD)

        # Title
        y = 260
        y = draw_centered_text(draw, y, tell["title"], title_font, TEXT_WHITE)
        y += 15
        draw_gold_line(draw, y, 500)
        y += 35

        # Check instruction
        y = draw_centered_text(draw, y, tell["check"], load_font(30), TEXT_GREY)
        y += 40

        # Real — with green left border
        draw.rectangle([(75, y), (82, y + 120)], fill=TEXT_GREEN)
        draw.text((100, y), "[REAL]", font=label_font, fill=TEXT_GREEN)
        y += 45
        lines = wrap_text(draw, tell["real"], body_font, 840)
        for line in lines:
            draw.text((100, y), line, font=body_font, fill=TEXT_WHITE)
            y += 42
        y += 35

        # Fake — with red left border
        draw.rectangle([(75, y), (82, y + 120)], fill=TEXT_RED)
        draw.text((100, y), "[FAKE]", font=label_font, fill=TEXT_RED)
        y += 45
        lines = wrap_text(draw, tell["fake"], body_font, 840)
        for line in lines:
            draw.text((100, y), line, font=body_font, fill=TEXT_WHITE)
            y += 42
        y += 35

        # Tip box — filled dark grey background for visual weight
        draw_gold_line(draw, y, 860)
        y += 25
        tip_lines = wrap_text(draw, "TIP: " + tell["tip"], tip_font, 840)
        tip_height = len(tip_lines) * 36 + 30
        draw.rectangle([(70, y - 10), (W - 70, y + tip_height)], fill=(30, 30, 30))
        for line in tip_lines:
            draw.text((90, y), line, font=tip_font, fill=TEXT_GOLD)
            y += 36

        draw_slide_number(draw, i + 2, total)
        draw_footer_cta(draw)
        slides.append(img)

    # SLIDE 7: CTA
    img, draw = new_slide()
    draw_header(draw, "@archivearbitrage")
    draw_gold_line(draw, 160)

    y = 300
    title_font = load_font(48, bold=True)
    y = draw_centered_text(draw, y, "EVERY DEAL WE SEND", title_font, TEXT_WHITE)
    y = draw_centered_text(draw, y + 10, "IS AUTHENTICATED", title_font, TEXT_GOLD)
    y += 50

    body_font = load_font(30)
    y = draw_centered_text(draw, y, "Our bot checks price floors,", body_font, TEXT_GREY)
    y = draw_centered_text(draw, y + 5, "seller trust, and listing patterns", body_font, TEXT_GREY)
    y = draw_centered_text(draw, y + 5, "before any alert reaches you.", body_font, TEXT_GREY)
    y += 50
    draw_gold_line(draw, y)
    y += 50

    cta_font = load_font(36, bold=True)
    y = draw_centered_text(draw, y, "Real deals. Verified. 24/7.", cta_font, TEXT_WHITE)
    y += 30
    y = draw_centered_text(draw, y, "$30/month — Link in bio", load_font(32), TEXT_GOLD)

    draw_slide_number(draw, 7, total)
    draw_footer_cta(draw)
    slides.append(img)

    # Save
    for i, slide in enumerate(slides):
        path = os.path.join(OUT_DIR, f"chrome_hearts_auth_{i+1}.jpg")
        slide.save(path, "JPEG", quality=95)
        print(f"  Saved: {path}")

    return slides


# ══════════════════════════════════════════════════════════════
# CAROUSEL 2: "Deal Showcase — This Week's Best Finds"
# ══════════════════════════════════════════════════════════════

def build_deal_showcase():
    slides = []
    total = 6

    deals = [
        {
            "item": "ERD Embroidered Leather Jacket",
            "brand": "Enfants Riches Déprimés",
            "listed": 825,
            "market": 2942,
            "gap": 72,
            "profit": 1575,
            "platform": "Poshmark",
            "score": 70,
            "fire": "🔥🔥🔥",
        },
        {
            "item": "ERD Arcane 17 Leather Jacket",
            "brand": "Enfants Riches Déprimés",
            "listed": 785,
            "market": 2942,
            "gap": 74,
            "profit": 1615,
            "platform": "Poshmark",
            "score": 70,
            "fire": "🔥🔥🔥",
        },
        {
            "item": "Margiela Tabi Boots",
            "brand": "Maison Margiela",
            "listed": 132,
            "market": 503,
            "gap": 63,
            "profit": 296,
            "platform": "Mercari",
            "score": 70,
            "fire": "🔥🔥🔥",
        },
        {
            "item": "Dior Homme 07SS Bee Tank Top",
            "brand": "Dior Homme (Hedi Era)",
            "listed": 174,
            "market": 605,
            "gap": 67,
            "profit": 303,
            "platform": "Vinted",
            "score": 69,
            "fire": "🔥🔥",
        },
    ]

    # SLIDE 1: Cover
    img, draw = new_slide()

    title_font = load_font(56, bold=True)
    sub_font = load_font(32)
    stat_font = load_font(72, bold=True)
    stat_label_font = load_font(22)

    draw_gold_line(draw, 120, 200)
    draw_gold_line(draw, 130, 300)

    y = 300
    y = draw_centered_text(draw, y, "THIS WEEK'S", title_font, TEXT_WHITE)
    y = draw_centered_text(draw, y + 15, "BEST FINDS", title_font, TEXT_GOLD)
    y += 40
    draw_gold_line(draw, y)
    y += 40
    y = draw_centered_text(draw, y, "Real deals caught by our bot", sub_font, TEXT_GREY)
    y = draw_centered_text(draw, y + 5, "Feb 21 - Feb 23, 2026", sub_font, TEXT_GREY)
    y += 60

    # Summary stats to fill space
    stats = [("4", "DEALS FOUND"), ("$3,789", "TOTAL PROFIT"), ("63-74%", "BELOW MARKET")]
    for val, label in stats:
        draw_centered_text(draw, y, val, load_font(44, bold=True), TEXT_GOLD)
        y += 50
        draw_centered_text(draw, y, label, stat_label_font, TEXT_GREY)
        y += 45

    draw_centered_text(draw, H - 180, "SWIPE >>", load_font(28), TEXT_GREY)
    draw_slide_number(draw, 1, total)
    draw_footer_cta(draw)
    slides.append(img)

    # SLIDES 2-5: Individual deals
    num_font = load_font(120, bold=True)
    item_font = load_font(36, bold=True)
    brand_font = load_font(28)
    stat_label = load_font(22)
    stat_value = load_font(44, bold=True)
    detail_font = load_font(26)

    for i, deal in enumerate(deals):
        img, draw = new_slide(BG_DARK)
        draw_header(draw, "@archivearbitrage")

        # Score badge (no emoji — use text)
        y = 160
        fire_count = deal['fire'].count('*') if '*' in deal.get('fire', '') else len(deal.get('fire', '').replace(' ', '')) // 1
        fire_text = f"DEAL SCORE: {deal['score']}/100"
        draw_centered_text(draw, y, fire_text, load_font(32, bold=True), TEXT_GOLD)

        # Item name
        y = 230
        y = draw_centered_text(draw, y, deal["item"].upper(), item_font, TEXT_WHITE)
        y = draw_centered_text(draw, y + 5, deal["brand"], brand_font, TEXT_GREY)
        y += 20
        draw_gold_line(draw, y, 700)
        y += 40

        # Big price comparison
        # Listed price
        draw_centered_text(draw, y, "LISTED", stat_label, TEXT_GREY)
        y += 30
        draw_centered_text(draw, y, f"${deal['listed']:,}", stat_value, TEXT_WHITE)
        y += 60

        # Arrow (use simple text arrow)
        draw_centered_text(draw, y, "|", load_font(36), TEXT_GOLD)
        y += 30
        draw_centered_text(draw, y, "V", load_font(28, bold=True), TEXT_GOLD)
        y += 40

        # Market price
        draw_centered_text(draw, y, "MARKET VALUE", stat_label, TEXT_GREY)
        y += 30
        draw_centered_text(draw, y, f"${deal['market']:,}", stat_value, TEXT_GOLD)
        y += 70

        draw_gold_line(draw, y, 500)
        y += 30

        # Stats row
        stats = [
            (f"{deal['gap']}%", "BELOW MARKET"),
            (f"${deal['profit']:,}", "EST. PROFIT"),
        ]
        x_positions = [W // 4, 3 * W // 4]
        for (val, label), x in zip(stats, x_positions):
            bbox = draw.textbbox((0, 0), val, font=stat_value)
            tw = bbox[2] - bbox[0]
            draw.text((x - tw // 2, y), val, font=stat_value, fill=TEXT_GREEN)
            bbox2 = draw.textbbox((0, 0), label, font=stat_label)
            tw2 = bbox2[2] - bbox2[0]
            draw.text((x - tw2 // 2, y + 55), label, font=stat_label, fill=TEXT_GREY)

        y += 110
        draw_centered_text(draw, y, f"Found on {deal['platform']}", detail_font, TEXT_GREY)

        draw_slide_number(draw, i + 2, total)
        draw_footer_cta(draw)
        slides.append(img)

    # SLIDE 6: CTA
    img, draw = new_slide()
    draw_header(draw, "@archivearbitrage")
    draw_gold_line(draw, 160)

    y = 280
    title_font = load_font(48, bold=True)
    y = draw_centered_text(draw, y, "4 DEALS.", title_font, TEXT_WHITE)
    y = draw_centered_text(draw, y + 10, "$3,789 TOTAL PROFIT.", title_font, TEXT_GOLD)
    y += 50

    body_font = load_font(30)
    y = draw_centered_text(draw, y, "Scanning Grailed, Poshmark,", body_font, TEXT_GREY)
    y = draw_centered_text(draw, y + 5, "Mercari, and Vinted. 24/7.", body_font, TEXT_GREY)
    y += 40

    checkmarks = [
        "[+]  Authenticated before you see it",
        "[+]  Real-time Telegram alerts",
        "[+]  78 archive search targets",
        "[+]  Rep filtering built in",
    ]
    check_font = load_font(28)
    for check in checkmarks:
        draw.text((140, y), check, font=check_font, fill=TEXT_WHITE)
        y += 45

    y += 30
    draw_gold_line(draw, y)
    y += 40
    cta_font = load_font(36, bold=True)
    draw_centered_text(draw, y, "$30/month — Link in bio", cta_font, TEXT_GOLD)

    draw_slide_number(draw, 6, total)
    draw_footer_cta(draw)
    slides.append(img)

    for i, slide in enumerate(slides):
        path = os.path.join(OUT_DIR, f"deal_showcase_{i+1}.jpg")
        slide.save(path, "JPEG", quality=95)
        print(f"  Saved: {path}")

    return slides


if __name__ == "__main__":
    print("Building Chrome Hearts Authentication carousel...")
    build_chrome_hearts_auth()
    print()
    print("Building Deal Showcase carousel...")
    build_deal_showcase()
    print("\nDone! Check marketing/posts/")
