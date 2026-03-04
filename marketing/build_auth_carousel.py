#!/usr/bin/env python3
"""
Instagram Carousel: "HOW WE VERIFY EVERY ITEM"
Deep dive into Archive Arbitrage's 6-signal authentication system.

Dark editorial aesthetic matching the brand's visual language.
"""

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os
import random

OUT_DIR = os.path.join(os.path.dirname(__file__), "posts", "auth_carousel")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 1080, 1350

# ── Palette ──
BLACK = (8, 8, 8)
DARK_GREY = (28, 28, 28)
MID_GREY = (140, 140, 140)
LIGHT_GREY = (200, 200, 200)
BODY_TEXT = (190, 188, 185)
OFF_WHITE = (240, 237, 232)
ACCENT = (215, 190, 140)        # Warm gold
BRIGHT_ACCENT = (230, 205, 155)
GREEN = (80, 200, 120)
RED_ACCENT = (200, 55, 50)
AMBER = (230, 180, 50)
SHIELD_BLUE = (70, 130, 210)


def load_font(size, bold=False, mono=False):
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


def add_grain(img, intensity=18):
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, intensity, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def add_vignette(img, strength=0.4):
    arr = np.array(img).astype(np.float64)
    rows, cols = arr.shape[:2]
    Y, X = np.ogrid[:rows, :cols]
    cy, cx = rows / 2, cols / 2
    dist = np.sqrt((X - cx) ** 2 / (cx ** 2) + (Y - cy) ** 2 / (cy ** 2))
    mask = (1.0 - np.clip(dist * strength, 0, 0.8))[:, :, np.newaxis]
    return Image.fromarray((arr * mask).clip(0, 255).astype(np.uint8))


def scanlines(draw):
    for y in range(0, H, 3):
        o = random.randint(7, 14)
        draw.line([(0, y), (W, y)], fill=(o, o, o), width=1)


def hline(draw, y, x1=80, x2=1000, color=MID_GREY, width=1):
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), t, font=font)[2] <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fin(img):
    return add_vignette(add_grain(img, 18), 0.4)


def new():
    img = Image.new("RGB", (W, H), BLACK)
    return img, ImageDraw.Draw(img)


def draw_shield(d, cx, cy, size, color):
    """Draw a simple shield icon."""
    s = size
    # Shield body
    pts = [
        (cx, cy - s),           # top
        (cx + s * 0.7, cy - s * 0.5),  # top right
        (cx + s * 0.7, cy + s * 0.1),  # mid right
        (cx, cy + s),           # bottom point
        (cx - s * 0.7, cy + s * 0.1),  # mid left
        (cx - s * 0.7, cy - s * 0.5),  # top left
    ]
    d.polygon(pts, outline=color, width=3)


def draw_bar(d, x, y, w, h, fill_pct, bar_color, bg_color=(40, 40, 40)):
    """Draw a progress bar."""
    d.rounded_rectangle([(x, y), (x + w, y + h)], radius=h // 2, fill=bg_color)
    fill_w = int(w * fill_pct)
    if fill_w > 0:
        d.rounded_rectangle([(x, y), (x + fill_w, y + h)], radius=h // 2, fill=bar_color)


# ══════════════════════════════════════════════════════════════
# SLIDE 1: COVER
# ══════════════════════════════════════════════════════════════
def slide_cover():
    img, d = new()
    scanlines(d)
    d.rectangle([(0, 0), (W, 5)], fill=SHIELD_BLUE)

    f18 = load_font(20)
    d.text((80, 55), "ARCHIVE ARBITRAGE", font=f18, fill=MID_GREY)
    d.text((80, 82), "AUTHENTICATION SYSTEM", font=f18, fill=MID_GREY)
    hline(d, 120, color=DARK_GREY)

    # Shield icon area
    draw_shield(d, W // 2, 310, 100, SHIELD_BLUE)
    # Checkmark inside shield
    check_f = load_font(60, bold=True)
    tw = d.textbbox((0, 0), "✓", font=check_f)[2]
    d.text((W // 2 - tw // 2, 275), "✓", font=check_f, fill=SHIELD_BLUE)

    # Title
    huge = load_font(90, bold=True)
    y = 450
    d.text((80, y), "HOW WE", font=huge, fill=OFF_WHITE)
    y += 105
    d.text((80, y), "VERIFY", font=huge, fill=SHIELD_BLUE)
    y += 105
    d.text((80, y), "EVERY", font=huge, fill=OFF_WHITE)
    y += 105
    d.text((80, y), "ITEM", font=huge, fill=OFF_WHITE)

    # Subtitle
    y += 140
    sub = load_font(28)
    d.text((80, y), "6 signals. 30+ brands. Zero guesswork.", font=sub, fill=BODY_TEXT)
    y += 40
    d.text((80, y), "Items scoring below 65% are blocked.", font=sub, fill=MID_GREY)

    # Stats bar at bottom
    hline(d, H - 180, color=DARK_GREY)
    stat_f = load_font(42, bold=True)
    label_f = load_font(18)

    # Three stat columns
    cols = [(160, "30+", "BRANDS"), (540, "6", "SIGNALS"), (920, "65%", "MIN SCORE")]
    for cx, val, label in cols:
        tw = d.textbbox((0, 0), val, font=stat_f)[2]
        d.text((cx - tw // 2, H - 155), val, font=stat_f, fill=BRIGHT_ACCENT)
        tw2 = d.textbbox((0, 0), label, font=label_f)[2]
        d.text((cx - tw2 // 2, H - 105), label, font=label_f, fill=MID_GREY)

    # Bottom CTA
    d.text((80, H - 65), "SWIPE →", font=load_font(26, bold=True), fill=OFF_WHITE)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# SIGNAL SLIDE TEMPLATE
# ══════════════════════════════════════════════════════════════
def signal_slide(num, emoji, title, weight_pct, description, examples, color=SHIELD_BLUE):
    img, d = new()
    scanlines(d)
    d.rectangle([(0, 0), (W, 4)], fill=color)

    # Header
    f18 = load_font(18)
    d.text((80, 40), f"SIGNAL {num} / 6", font=f18, fill=MID_GREY)
    d.text((W - 260, 40), "ARCHIVE ARBITRAGE", font=f18, fill=MID_GREY)
    hline(d, 75, color=DARK_GREY)

    # Big faded number
    d.text((W - 300, 60), f"{num:02d}", font=load_font(200, bold=True), fill=(18, 18, 18))

    # Signal number badge
    y = 130
    badge_w = 60
    d.rounded_rectangle([(80, y), (80 + badge_w, y + badge_w)], radius=8, fill=color)
    num_f = load_font(36, bold=True)
    tw = d.textbbox((0, 0), str(num), font=num_f)[2]
    d.text((80 + badge_w // 2 - tw // 2, y + 10), str(num), font=num_f, fill=BLACK)

    y += 75
    title_f = load_font(52, bold=True)
    for line in wrap(d, title.upper(), title_f, 880):
        d.text((80, y), line, font=title_f, fill=OFF_WHITE)
        y += 62

    # Weight bar
    y += 20
    d.text((80, y), f"WEIGHT: {weight_pct}%", font=load_font(22), fill=MID_GREY)
    y += 32
    draw_bar(d, 80, y, 400, 14, weight_pct / 100, color)

    # Description
    y += 50
    hline(d, y, color=DARK_GREY)
    y += 25
    desc_f = load_font(30)
    for line in wrap(d, description, desc_f, 880):
        d.text((80, y), line, font=desc_f, fill=BODY_TEXT)
        y += 40

    # Examples box
    y += 30
    d.rounded_rectangle([(60, y), (W - 60, y + len(examples) * 48 + 40)], radius=12, fill=(20, 20, 20))
    y += 20
    mono = load_font(22, mono=True)
    label_f = load_font(20)
    d.text((90, y - 2), "WHAT WE CHECK:", font=label_f, fill=ACCENT)
    y += 35
    for ex in examples:
        d.text((90, y), f"→  {ex}", font=mono, fill=LIGHT_GREY)
        y += 48

    # Bottom
    hline(d, H - 80, color=DARK_GREY)
    d.text((80, H - 55), f"SIGNAL {num}/6", font=load_font(20), fill=MID_GREY)
    d.text((W - 200, H - 55), "SWIPE →", font=load_font(22, bold=True), fill=OFF_WHITE)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# SLIDE 8: GRADING SYSTEM
# ══════════════════════════════════════════════════════════════
def slide_grading():
    img, d = new()
    scanlines(d)
    d.rectangle([(0, 0), (W, 4)], fill=ACCENT)

    f18 = load_font(18)
    d.text((80, 40), "THE RESULT", font=f18, fill=MID_GREY)
    d.text((W - 260, 40), "ARCHIVE ARBITRAGE", font=f18, fill=MID_GREY)
    hline(d, 75, color=DARK_GREY)

    # Title
    y = 120
    d.text((80, y), "CONFIDENCE", font=load_font(68, bold=True), fill=OFF_WHITE)
    y += 80
    d.text((80, y), "SCORING", font=load_font(68, bold=True), fill=BRIGHT_ACCENT)

    y += 110
    desc_f = load_font(26)
    d.text((80, y), "All 6 signals combine into one score.", font=desc_f, fill=BODY_TEXT)
    y += 36
    d.text((80, y), "Below 65%? Blocked. You never see it.", font=desc_f, fill=BODY_TEXT)

    # Grade cards
    y += 60
    grades = [
        ("A", "90-100%", "VERIFIED AUTHENTIC", GREEN, ">>>"),
        ("B", "75-89%", "LIKELY AUTHENTIC", (100, 180, 100), ">>"),
        ("C", "65-74%", "PROCEED WITH CAUTION", AMBER, ">"),
        ("D", "<65%", "BLOCKED FROM ALERTS", RED_ACCENT, "X"),
    ]

    card_h = 100
    for grade, pct, label, color, emoji in grades:
        # Card background
        d.rounded_rectangle([(60, y), (W - 60, y + card_h)], radius=10, fill=(20, 20, 20))

        # Grade letter
        grade_f = load_font(56, bold=True)
        d.text((100, y + 18), grade, font=grade_f, fill=color)

        # Percentage
        pct_f = load_font(28, bold=True)
        d.text((180, y + 22), pct, font=pct_f, fill=OFF_WHITE)

        # Label
        label_f = load_font(22)
        d.text((180, y + 58), label, font=label_f, fill=MID_GREY)

        # Status indicator
        d.text((W - 140, y + 30), emoji, font=load_font(28, bold=True), fill=color)

        y += card_h + 15

    # Bottom stats
    y += 10
    hline(d, y, color=DARK_GREY)
    y += 20
    stat_f = load_font(24)
    d.text((80, y), "Items blocked last 30 days:", font=stat_f, fill=MID_GREY)
    d.text((510, y), "1,200+", font=load_font(24, bold=True), fill=RED_ACCENT)
    y += 35
    d.text((80, y), "Avg confidence of sent alerts:", font=stat_f, fill=MID_GREY)
    d.text((510, y), "82%", font=load_font(24, bold=True), fill=GREEN)

    # CTA
    hline(d, H - 80, color=DARK_GREY)
    d.text((80, H - 55), "SWIPE →", font=load_font(22, bold=True), fill=OFF_WHITE)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# SLIDE 9: REAL EXAMPLE
# ══════════════════════════════════════════════════════════════
def slide_example():
    img, d = new()
    scanlines(d)
    d.rectangle([(0, 0), (W, 4)], fill=GREEN)

    f18 = load_font(18)
    d.text((80, 40), "REAL EXAMPLE", font=f18, fill=MID_GREY)
    d.text((W - 260, 40), "ARCHIVE ARBITRAGE", font=f18, fill=MID_GREY)
    hline(d, 75, color=DARK_GREY)

    y = 120
    d.text((80, y), "WHAT AN ALERT LOOKS LIKE", font=load_font(38, bold=True), fill=OFF_WHITE)

    # Fake alert card
    y += 70
    card_top = y
    card_bot = y + 620
    d.rounded_rectangle([(50, card_top), (W - 50, card_bot)], radius=16, fill=(18, 18, 18), outline=(40, 40, 40), width=1)

    # Fire header
    y += 20
    d.text((90, y), "/// FIRE DEAL", font=load_font(32, bold=True), fill=BRIGHT_ACCENT)
    d.text((90, y + 42), "Score: 74/100", font=load_font(22), fill=MID_GREY)

    y += 85
    hline(d, y, x1=90, x2=W - 90, color=(40, 40, 40))

    # Item details
    y += 15
    d.text((90, y), "Rick Owens Geobasket Black/Milk", font=load_font(28, bold=True), fill=OFF_WHITE)
    y += 38
    d.text((90, y), "Mainline  ·  Size 43  ·  Grailed", font=load_font(22), fill=MID_GREY)

    # Price section
    y += 55
    d.text((90, y), "LISTED", font=load_font(20), fill=MID_GREY)
    d.text((90, y + 26), "$280", font=load_font(44, bold=True), fill=OFF_WHITE)

    d.text((350, y), "MARKET VALUE", font=load_font(20), fill=MID_GREY)
    d.text((350, y + 26), "$480", font=load_font(44, bold=True), fill=GREEN)

    d.text((650, y), "PROFIT", font=load_font(20), fill=MID_GREY)
    d.text((650, y + 26), "+$200", font=load_font(44, bold=True), fill=BRIGHT_ACCENT)

    # Auth bar
    y += 100
    hline(d, y, x1=90, x2=W - 90, color=(40, 40, 40))
    y += 15
    d.text((90, y), "AUTH:", font=load_font(24, bold=True), fill=MID_GREY)
    # Green dots
    dot_x = 230
    for i in range(5):
        color_dot = GREEN if i < 4 else (50, 50, 50)
        d.ellipse([(dot_x + i * 36, y + 4), (dot_x + i * 36 + 24, y + 28)], fill=color_dot)
    d.text((dot_x + 200, y), "82%  — Grade B", font=load_font(24, bold=True), fill=GREEN)

    # Signal breakdown
    y += 45
    signals = [
        ("Text Safety", 0.92, GREEN),
        ("Price Check", 0.85, GREEN),
        ("Seller Rep", 0.78, (100, 180, 100)),
        ("Listing Quality", 0.70, AMBER),
        ("Image Analysis", 0.80, GREEN),
        ("Brand Markers", 0.75, (100, 180, 100)),
    ]
    bar_f = load_font(18)
    for name, score, color in signals:
        d.text((90, y), name, font=bar_f, fill=MID_GREY)
        draw_bar(d, 310, y + 4, 300, 12, score, color)
        d.text((625, y), f"{score*100:.0f}%", font=bar_f, fill=LIGHT_GREY)
        y += 30

    # Buy link
    y += 10
    d.rounded_rectangle([(90, y), (350, y + 44)], radius=8, fill=SHIELD_BLUE)
    d.text((130, y + 8), "BUY NOW  →", font=load_font(24, bold=True), fill=OFF_WHITE)

    # Bottom
    y = H - 120
    hline(d, y, color=DARK_GREY)
    y += 20
    d.text((80, y), "Real alert. Real deal. Sent in real-time.", font=load_font(26), fill=BODY_TEXT)
    d.text((80, H - 55), "SWIPE →", font=load_font(22, bold=True), fill=OFF_WHITE)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# SLIDE 10: CTA
# ══════════════════════════════════════════════════════════════
def slide_cta():
    img, d = new()
    scanlines(d)
    d.rectangle([(0, 0), (W, 5)], fill=ACCENT)

    f18 = load_font(18)
    d.text((80, 55), "ARCHIVE ARBITRAGE", font=f18, fill=MID_GREY)
    hline(d, 100, color=DARK_GREY)

    # Main message
    y = 280
    big = load_font(72, bold=True)
    d.text((80, y), "STOP", font=big, fill=OFF_WHITE)
    y += 85
    d.text((80, y), "BUYING", font=big, fill=OFF_WHITE)
    y += 85
    d.text((80, y), "FAKES.", font=big, fill=RED_ACCENT)

    y += 130
    sub = load_font(32)
    d.text((80, y), "Every alert is verified.", font=sub, fill=BODY_TEXT)
    y += 44
    d.text((80, y), "Every item is scored.", font=sub, fill=BODY_TEXT)
    y += 44
    d.text((80, y), "Every signal is checked.", font=sub, fill=BODY_TEXT)

    y += 80
    hline(d, y, color=MID_GREY)
    y += 30

    # Price
    d.text((80, y), "$30/mo", font=load_font(56, bold=True), fill=BRIGHT_ACCENT)
    y += 70
    d.text((80, y), "Real-time alerts  ·  Telegram + Discord", font=load_font(26), fill=MID_GREY)
    y += 36
    d.text((80, y), "6-signal authentication on every deal", font=load_font(26), fill=MID_GREY)

    # CTA button
    y += 60
    d.rounded_rectangle([(80, y), (500, y + 60)], radius=10, fill=ACCENT)
    d.text((150, y + 12), "LINK IN BIO →", font=load_font(32, bold=True), fill=BLACK)

    # Bottom
    hline(d, H - 80, color=DARK_GREY)
    d.text((80, H - 55), "@archivearbitrage", font=load_font(22), fill=MID_GREY)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# BUILD ALL SLIDES
# ══════════════════════════════════════════════════════════════
def build():
    slides = []

    # 1. Cover
    slides.append(("01_cover.png", slide_cover()))

    # 2-7. Six signal slides
    signal_data = [
        {
            "num": 1, "emoji": "🔍", "title": "Text Safety Analysis",
            "weight": 15, "color": SHIELD_BLUE,
            "desc": "We scan every title and description for replica language, wholesale signals, and suspicious patterns. Hard flags like '1:1' or 'mirror quality' = instant block.",
            "examples": [
                '"replica" / "1:1" / "best version"',
                '"wholesale" / "bulk" / "multiple available"',
                '"WhatsApp" / "WeChat" / "Yupoo"',
                'Misspellings: "Balenciage" / "Viviene"',
                '"DM for pics" / "follow for more"',
            ],
        },
        {
            "num": 2, "emoji": "💰", "title": "Price Plausibility",
            "weight": 25, "color": BRIGHT_ACCENT,
            "desc": "Every brand has minimum authentic price floors. Rick Owens Geobaskets under $300? Chrome Hearts rings under $200? Flagged instantly. We calibrate per brand AND per category.",
            "examples": [
                "Brand-specific price floors",
                "Category-specific minimums",
                "High-rep items get 1.5x stricter floors",
                "Statistical price anomaly detection",
                "Collab items (RO x Vans) extra scrutiny",
            ],
        },
        {
            "num": 3, "emoji": "👤", "title": "Seller Reputation",
            "weight": 15, "color": GREEN,
            "desc": "Most platforms offer buyer protection, so seller rep is a supporting signal — not a dealbreaker. But zero-feedback accounts selling grails still raise flags.",
            "examples": [
                "Sales history & account age",
                "Seller rating percentage",
                "Auto-blocklist repeat offenders",
                "Platform protection as safety net",
                "Low-trust = extra scrutiny, not auto-block",
            ],
        },
        {
            "num": 4, "emoji": "📋", "title": "Listing Quality",
            "weight": 12, "color": (150, 120, 200),
            "desc": "Authentic sellers write detailed descriptions and post multiple high-quality photos. One blurry photo with 'DM for more info'? Suspicious. We score description depth, photo count, and detail level.",
            "examples": [
                "Description length & detail",
                "Number of photos (more = better)",
                "Mentions of flaws / honest wear",
                "Measurements & sizing info",
                "Tag / label photos present",
            ],
        },
        {
            "num": 5, "emoji": "📸", "title": "Image Analysis",
            "weight": 23, "color": (200, 100, 100),
            "desc": "Our heaviest visual signal. We detect stock photos, duplicate images across sellers (rep factories reuse the same pics), EXIF anomalies, and low-quality photos that hide flaws.",
            "examples": [
                "Stock photo detection",
                "Cross-seller image duplicates",
                "Image hash fingerprinting",
                "EXIF metadata analysis",
                "Photo quality & resolution scoring",
            ],
        },
        {
            "num": 6, "emoji": "🏷️", "title": "Brand-Specific Markers",
            "weight": 10, "color": ACCENT,
            "desc": "Every brand has tells. Rick Owens tags have specific fonts. Chrome Hearts has .925 stamps. Vivienne Westwood orbs have exact engravings. We check brand-specific authentication keywords.",
            "examples": [
                '"Made in Italy" for Rick Owens',
                '".925 sterling" for Chrome Hearts',
                '"Made in England" for Vivienne Westwood',
                "Known high-rep category flagging",
                "30+ brand rule databases",
            ],
        },
    ]

    for s in signal_data:
        slides.append((
            f"0{s['num']+1}_signal{s['num']}.png",
            signal_slide(
                s["num"], s["emoji"], s["title"], s["weight"],
                s["desc"], s["examples"], s.get("color", SHIELD_BLUE),
            ),
        ))

    # 8. Grading system
    slides.append(("08_grading.png", slide_grading()))

    # 9. Real example
    slides.append(("09_example.png", slide_example()))

    # 10. CTA
    slides.append(("10_cta.png", slide_cta()))

    for fname, img in slides:
        path = os.path.join(OUT_DIR, fname)
        img.save(path, quality=95)
        print(f"  ✅ {fname} ({img.size[0]}x{img.size[1]})")

    print(f"\n🎨 {len(slides)} slides saved to {OUT_DIR}")


if __name__ == "__main__":
    build()
