#!/usr/bin/env python3
"""
Editorial-style Instagram carousel: "SLEPT ON → SOLD OUT"
Archive pieces that went from forgotten to five figures.
Dark, textured, magazine-editorial feel.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os
import random

OUT_DIR = os.path.join(os.path.dirname(__file__), "posts")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 1080, 1350

# ── Color palette ──
BLACK = (8, 8, 8)
NEAR_BLACK = (14, 14, 14)
DARK_GREY = (28, 28, 28)
MID_GREY = (90, 90, 90)
LIGHT_GREY = (170, 170, 170)
OFF_WHITE = (235, 232, 228)  # Warm white
CREAM = (220, 215, 205)
ACCENT = (195, 170, 130)  # Warm gold/bronze, more muted than before
RED_ACCENT = (180, 45, 40)  # Deep red


def load_font(size, bold=False, mono=False):
    if mono:
        paths = [
            "/System/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/SFMono-Regular.otf",
            "/Library/Fonts/Courier New.ttf",
        ]
    elif bold:
        paths = [
            "/System/Library/Fonts/Supplemental/Futura.ttc",  # index 5 = Condensed ExtraBold
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    else:
        paths = [
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    for p in paths:
        try:
            idx = 0
            if bold and "Futura" in p:
                idx = 5  # Condensed ExtraBold
            elif bold and "HelveticaNeue" in p:
                idx = 8  # Bold
            return ImageFont.truetype(p, size, index=idx)
        except (OSError, IndexError):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def add_grain(img, intensity=25):
    """Add film grain texture."""
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, intensity, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def add_vignette(img, strength=0.6):
    """Add subtle vignette darkening."""
    arr = np.array(img).astype(np.float64)
    rows, cols = arr.shape[:2]
    Y, X = np.ogrid[:rows, :cols]
    cy, cx = rows / 2, cols / 2
    # Normalized distance from center
    dist = np.sqrt((X - cx) ** 2 / (cx ** 2) + (Y - cy) ** 2 / (cy ** 2))
    # Vignette mask: 1 at center, darker at edges
    mask = 1.0 - np.clip(dist * strength, 0, 0.85)
    mask = mask[:, :, np.newaxis]
    arr = (arr * mask).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def draw_line(draw, y, x1=80, x2=1000, color=MID_GREY, width=1):
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


def wrap_text(draw, text, font, max_width):
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


def text_width(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[2]


def new_slide():
    img = Image.new("RGB", (W, H), BLACK)
    return img, ImageDraw.Draw(img)


def finalize(img, grain=20):
    """Apply grain + vignette for editorial feel."""
    img = add_grain(img, grain)
    img = add_vignette(img, 0.5)
    return img


# ══════════════════════════════════════════════════════════════
# SLIDE 1: Cover — "SLEPT ON → SOLD OUT"
# ══════════════════════════════════════════════════════════════
def slide_cover():
    img, draw = new_slide()

    # Subtle textured background — horizontal scan lines
    for y in range(0, H, 3):
        opacity = random.randint(6, 12)
        draw.line([(0, y), (W, y)], fill=(opacity, opacity, opacity), width=1)

    # Top rule
    draw.rectangle([(0, 0), (W, 4)], fill=ACCENT)

    # Small header text — left aligned
    header_font = load_font(18)
    draw.text((80, 60), "ARCHIVE ARBITRAGE", font=header_font, fill=MID_GREY)
    draw.text((80, 85), "VOL. 001  —  FEB 2026", font=header_font, fill=MID_GREY)

    # Right-aligned issue mark
    draw.text((W - 180, 60), "EST. 2026", font=header_font, fill=MID_GREY)

    draw_line(draw, 120, color=DARK_GREY)

    # Main title — huge, dramatic, left-aligned
    title_font = load_font(110, bold=True)
    medium_font = load_font(72, bold=True)

    y = 250
    draw.text((75, y), "SLEPT", font=title_font, fill=OFF_WHITE)
    y += 120
    draw.text((75, y), "ON", font=title_font, fill=OFF_WHITE)

    # Arrow element — a red horizontal line with movement
    y += 160
    draw.rectangle([(75, y), (W - 80, y + 3)], fill=RED_ACCENT)
    # Arrow head
    arrow_font = load_font(48, bold=True)
    draw.text((W - 130, y - 25), "→", font=arrow_font, fill=RED_ACCENT)

    y += 60
    draw.text((75, y), "SOLD", font=title_font, fill=ACCENT)
    y += 120
    draw.text((75, y), "OUT", font=title_font, fill=ACCENT)

    # Subtitle
    y += 170
    sub_font = load_font(26)
    draw.text((80, y), "Five archive pieces that went from clearance", font=sub_font, fill=LIGHT_GREY)
    draw.text((80, y + 38), "rack to five-figure grail. And what's next.", font=sub_font, fill=LIGHT_GREY)

    # Bottom bar
    draw_line(draw, H - 120, color=DARK_GREY)
    bottom_font = load_font(20)
    draw.text((80, H - 90), "SWIPE", font=load_font(24, bold=True), fill=OFF_WHITE)
    draw.text((80, H - 60), "5 PIECES  ·  HISTORY  ·  MARKET DATA", font=bottom_font, fill=MID_GREY)

    # Page indicator
    for i in range(7):
        x = W - 200 + i * 22
        color = OFF_WHITE if i == 0 else DARK_GREY
        draw.ellipse([(x, H - 75), (x + 8, H - 67)], fill=color)

    return finalize(img)


# ══════════════════════════════════════════════════════════════
# PIECE SLIDES — Each tells a story
# ══════════════════════════════════════════════════════════════
def slide_piece(num, total, piece_data):
    img, draw = new_slide()

    # Scan lines bg
    for y in range(0, H, 4):
        opacity = random.randint(6, 10)
        draw.line([(0, y), (W, y)], fill=(opacity, opacity, opacity), width=1)

    # Top accent bar
    draw.rectangle([(0, 0), (W, 3)], fill=ACCENT)

    # Header
    header_font = load_font(16)
    draw.text((80, 45), f"{num:02d} / {total:02d}", font=header_font, fill=MID_GREY)
    draw.text((W - 260, 45), "ARCHIVE ARBITRAGE", font=header_font, fill=MID_GREY)

    draw_line(draw, 80, color=DARK_GREY)

    # Piece number — large, faded
    num_font = load_font(200, bold=True)
    # Draw it very faint in the background
    num_text = f"{num:02d}"
    draw.text((W - 320, 60), num_text, font=num_font, fill=(20, 20, 20))

    # Designer name — small caps style
    y = 120
    designer_font = load_font(22)
    draw.text((80, y), piece_data["designer"].upper(), font=designer_font, fill=ACCENT)

    # Piece name — large
    y += 50
    piece_font = load_font(52, bold=True)
    lines = wrap_text(draw, piece_data["name"].upper(), piece_font, 900)
    for line in lines:
        draw.text((80, y), line, font=piece_font, fill=OFF_WHITE)
        y += 62

    # Season / year
    y += 10
    season_font = load_font(24)
    draw.text((80, y), piece_data["season"], font=season_font, fill=LIGHT_GREY)

    # Divider
    y += 55
    draw_line(draw, y, color=MID_GREY, width=1)
    y += 30

    # The story — 2-3 lines of editorial copy
    story_font = load_font(27)
    story_lines = wrap_text(draw, piece_data["story"], story_font, 880)
    for line in story_lines:
        draw.text((80, y), line, font=story_font, fill=LIGHT_GREY)
        y += 40
    y += 30

    # Price trajectory — the visual centerpiece
    draw_line(draw, y, color=DARK_GREY)
    y += 25

    label_font = load_font(16)
    draw.text((80, y), "PRICE TRAJECTORY", font=label_font, fill=MID_GREY)
    y += 35

    # Price boxes — left = then, right = now
    price_label_font = load_font(18)
    price_font = load_font(56, bold=True)
    small_price_font = load_font(36, bold=True)

    # "THEN" box
    then_x = 80
    draw.text((then_x, y), piece_data["then_label"], font=price_label_font, fill=MID_GREY)
    y_price = y + 28
    draw.text((then_x, y_price), piece_data["then_price"], font=price_font, fill=LIGHT_GREY)

    # Arrow
    arrow_y = y_price + 20
    mid_x = 480
    draw.text((mid_x, arrow_y), "→", font=load_font(40, bold=True), fill=RED_ACCENT)

    # "NOW" box
    now_x = 580
    draw.text((now_x, y), piece_data["now_label"], font=price_label_font, fill=MID_GREY)
    draw.text((now_x, y_price), piece_data["now_price"], font=price_font, fill=ACCENT)

    y = y_price + 80

    # Multiplier callout
    mult_font = load_font(28, bold=True)
    draw.text((80, y), piece_data["multiplier"], font=mult_font, fill=RED_ACCENT)
    y += 50

    # Divider
    draw_line(draw, y, color=DARK_GREY)
    y += 25

    # Market insight — mono font for data feel
    mono_font = load_font(20, mono=True)
    for insight in piece_data["insights"]:
        draw.text((80, y), insight, font=mono_font, fill=MID_GREY)
        y += 30

    # Bottom — why it matters
    y = H - 200
    draw_line(draw, y, color=DARK_GREY)
    y += 25
    why_label = load_font(16)
    draw.text((80, y), "WHY IT MATTERS NOW", font=why_label, fill=ACCENT)
    y += 30
    why_font = load_font(24)
    why_lines = wrap_text(draw, piece_data["why_now"], why_font, 880)
    for line in why_lines:
        draw.text((80, y), line, font=why_font, fill=OFF_WHITE)
        y += 34

    # Page dots
    for i in range(7):
        x = W - 200 + i * 22
        color = OFF_WHITE if i == num else DARK_GREY
        draw.ellipse([(x, H - 45), (x + 8, H - 37)], fill=color)

    return finalize(img, grain=18)


# ══════════════════════════════════════════════════════════════
# SLIDE 7: CTA — The closer
# ══════════════════════════════════════════════════════════════
def slide_cta():
    img, draw = new_slide()

    for y in range(0, H, 3):
        opacity = random.randint(6, 12)
        draw.line([(0, y), (W, y)], fill=(opacity, opacity, opacity), width=1)

    draw.rectangle([(0, 0), (W, 4)], fill=ACCENT)

    header_font = load_font(18)
    draw.text((80, 60), "ARCHIVE ARBITRAGE", font=header_font, fill=MID_GREY)

    draw_line(draw, 110, color=DARK_GREY)

    # Main message
    y = 250
    big_font = load_font(64, bold=True)
    med_font = load_font(42, bold=True)

    draw.text((80, y), "THE NEXT", font=big_font, fill=OFF_WHITE)
    y += 80
    draw.text((80, y), "GRAIL IS", font=big_font, fill=OFF_WHITE)
    y += 80
    draw.text((80, y), "LISTED", font=big_font, fill=ACCENT)
    y += 80
    draw.text((80, y), "RIGHT NOW.", font=big_font, fill=ACCENT)

    y += 120
    draw_line(draw, y, color=MID_GREY)
    y += 30

    body_font = load_font(26)
    lines = [
        "We scan Grailed, Poshmark, Mercari, and Vinted",
        "around the clock. 250+ archive brands. Every",
        "deal is authenticated before it reaches you.",
    ]
    for line in lines:
        draw.text((80, y), line, font=body_font, fill=LIGHT_GREY)
        y += 38

    y += 40

    # Stats in mono — gives it that data-driven feel
    mono = load_font(22, mono=True)
    stats = [
        "PLATFORMS .............. 4",
        "BRANDS ................ 250+",
        "DAILY SCANS ........... 10,000+",
        "AUTH SIGNALS .......... 6",
    ]
    for stat in stats:
        draw.text((80, y), stat, font=mono, fill=MID_GREY)
        y += 32

    y += 40
    draw_line(draw, y, color=DARK_GREY)
    y += 30

    # CTA
    cta_font = load_font(36, bold=True)
    draw.text((80, y), "$30/MONTH", font=cta_font, fill=OFF_WHITE)
    y += 50
    draw.text((80, y), "REAL-TIME TELEGRAM ALERTS", font=load_font(22), fill=ACCENT)
    y += 35
    draw.text((80, y), "LINK IN BIO", font=load_font(22, bold=True), fill=OFF_WHITE)

    # Page dots
    for i in range(7):
        x = W - 200 + i * 22
        color = OFF_WHITE if i == 6 else DARK_GREY
        draw.ellipse([(x, H - 45), (x + 8, H - 37)], fill=color)

    return finalize(img)


# ══════════════════════════════════════════════════════════════
# PIECES DATA
# ══════════════════════════════════════════════════════════════

PIECES = [
    {
        "designer": "RAF SIMONS",
        "name": "Riot Riot Riot Bomber",
        "season": "AW01 — \"Riot Riot Riot\"",
        "story": "Debuted during one of fashion's most politically charged shows. Raf sent models down the runway with anarchy patches and inverted flags post-9/11. The collection was initially considered too controversial to sell. Retailers pulled orders. Pieces hit clearance racks.",
        "then_label": "CLEARANCE (2002)",
        "then_price": "$280",
        "now_label": "CURRENT MARKET",
        "now_price": "$47K+",
        "multiplier": "167× RETURN",
        "insights": [
            "Last recorded sale: $47,000 (2023)",
            "Only ~50 bombers produced",
            "Museum pieces: MoMA, MET Costume Institute",
            "Fakes flooding market since 2019",
        ],
        "why_now": "The bomber that turned Raf from Antwerp outsider to the most collected designer alive. Every archive collection starts with wanting one.",
    },
    {
        "designer": "HELMUT LANG",
        "name": "Astro Biker Jacket",
        "season": "FW98 — Peak Helmut Era",
        "story": "Lang's minimalist masterpiece. Bonded rubber over nylon with asymmetric closure. When Lang left fashion in 2005, prices sat flat for a decade. The archive community rediscovered him around 2016 and everything changed.",
        "then_label": "RESALE (2012)",
        "then_price": "$400",
        "now_label": "CURRENT MARKET",
        "now_price": "$6,500",
        "multiplier": "16× RETURN",
        "insights": [
            "Key piece from Lang's most influential era",
            "Bonded rubber degrades — condition is everything",
            "Sub-$1K examples almost extinct on resale",
            "OG Lang (pre-2005) commands 5-10× over Prada era",
        ],
        "why_now": "OG Helmut Lang pieces under $500 still surface on Poshmark and Mercari — sellers who don't know what they have. Our bot caught 3 this month.",
    },
    {
        "designer": "NUMBER (N)INE",
        "name": "Heart Skull Cashmere Sweater",
        "season": "AW06 — \"NIL\"",
        "story": "Takahiro Miyashita's final Number (N)ine collection before dissolving the brand. The skull-heart motif became the most recognizable symbol in Japanese archive fashion. When the brand ended, prices started climbing and never stopped.",
        "then_label": "RETAIL (2006)",
        "then_price": "$800",
        "now_label": "CURRENT MARKET",
        "now_price": "$12K+",
        "multiplier": "15× RETURN",
        "insights": [
            "Brand dissolved 2009 — finite supply",
            "Cashmere condition varies wildly (moth damage)",
            "Colorway matters: black/red > grey > cream",
            "Soloist pieces (Miyashita's new brand) also rising",
        ],
        "why_now": "Japanese archive is the fastest-appreciating segment. N(N) pieces under $2K are disappearing. If you see one priced wrong, it won't last an hour.",
    },
    {
        "designer": "MAISON MARGIELA",
        "name": "Tabi Boots",
        "season": "1988 — Debut Collection",
        "story": "Margiela's split-toe boot debuted at his first-ever show in 1988. Models walked through red paint, leaving Tabi footprints on the white runway. Critics hated them. The fashion establishment called them unwearable. Now they're the most iconic shoe silhouette of the last 40 years.",
        "then_label": "RESALE (2015)",
        "then_price": "$180",
        "now_label": "CURRENT MARKET",
        "now_price": "$800+",
        "multiplier": "4.4× RETURN",
        "insights": [
            "Vintage pairs (pre-Galliano) command premium",
            "White leather Tabis most sought after",
            "Still in production — but OG pairs are different",
            "Mercari & Poshmark: mispriced Tabis weekly",
        ],
        "why_now": "Tabis are entry-level archive — everyone wants a pair. Because they're still produced, sellers often price vintage pairs at current retail. That's where the arbitrage lives.",
    },
    {
        "designer": "RICK OWENS",
        "name": "Dunks",
        "season": "SS09 — \"Crust\"",
        "story": "Before the Nike collab, before the mainstream moment — Rick's original Dunks were handmade in Italy. Heavy, brutalist, built like armor. They sat on shelves. The fashion world wasn't ready for $1,200 sneakers that weighed 3 pounds. Then everything Rick touched turned to gold.",
        "then_label": "SALE RACK (2010)",
        "then_price": "$600",
        "now_label": "CURRENT MARKET",
        "now_price": "$3,500",
        "multiplier": "5.8× RETURN",
        "insights": [
            "OG Dunks (pre-2012) have different sole + leather",
            "Size 42-43 most liquid, 45+ commands premium",
            "DRKSHDW versions worth ~40% of mainline",
            "Geobaskets follow same trajectory, 2-3 yrs behind",
        ],
        "why_now": "Rick is having a cultural moment. Mainstream adoption means more demand hitting a fixed supply of OG pieces. Mispriced Dunks and Geos appear on Grailed daily — usually gone in minutes.",
    },
]


def build_carousel():
    slides = []

    print("  Building cover...")
    slides.append(slide_cover())

    for i, piece in enumerate(PIECES):
        print(f"  Building slide {i+2}: {piece['designer']} — {piece['name']}...")
        slides.append(slide_piece(i + 1, 5, piece))

    print("  Building CTA...")
    slides.append(slide_cta())

    for i, slide in enumerate(slides):
        path = os.path.join(OUT_DIR, f"editorial_{i+1}.jpg")
        slide.save(path, "JPEG", quality=95)
        print(f"  Saved: {path}")

    return slides


if __name__ == "__main__":
    print("\n🐉 Building editorial carousel: SLEPT ON → SOLD OUT\n")
    build_carousel()
    print(f"\nDone! {len(PIECES) + 2} slides saved to marketing/posts/")
