#!/usr/bin/env python3
"""
Editorial carousel v2: "SLEPT ON → SOLD OUT"
Fixes: brighter text, tighter layouts, larger fonts, removed custom dots,
less text per slide, stronger visual contrast.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os
import random

OUT_DIR = os.path.join(os.path.dirname(__file__), "posts")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 1080, 1350

# ── Adjusted palette — brighter midtones ──
BLACK = (8, 8, 8)
DARK_GREY = (28, 28, 28)
MID_GREY = (140, 140, 140)
LIGHT_GREY = (200, 200, 200)
BODY_TEXT = (190, 188, 185)  # Warm off-white for readability
OFF_WHITE = (240, 237, 232)
ACCENT = (215, 190, 140)  # Brighter warm gold
BRIGHT_ACCENT = (230, 205, 155)  # Even brighter for key moments
RED_ACCENT = (200, 55, 50)
DEEP_RED = (140, 35, 30)


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


def add_grain(img, intensity=20):
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, intensity, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def add_vignette(img, strength=0.45):
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
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def fin(img):
    return add_vignette(add_grain(img, 18), 0.4)


def new():
    img = Image.new("RGB", (W, H), BLACK)
    return img, ImageDraw.Draw(img)


# ══════════════════════════════════════════════════════════════
# SLIDE 1: COVER
# ══════════════════════════════════════════════════════════════
def cover():
    img, d = new()
    scanlines(d)

    # Top bar
    d.rectangle([(0, 0), (W, 5)], fill=ACCENT)

    # Header
    f16 = load_font(20)
    d.text((80, 55), "ARCHIVE ARBITRAGE", font=f16, fill=MID_GREY)
    d.text((80, 82), "VOL. 001", font=f16, fill=MID_GREY)

    hline(d, 120, color=DARK_GREY)

    # Main title
    huge = load_font(120, bold=True)
    big = load_font(120, bold=True)

    y = 220
    d.text((72, y), "SLEPT", font=huge, fill=OFF_WHITE)
    y += 130
    d.text((72, y), "ON", font=huge, fill=OFF_WHITE)

    # Red divider with arrow
    y += 170
    d.rectangle([(72, y), (W - 72, y + 4)], fill=RED_ACCENT)
    # Draw arrow with lines instead of glyph
    arr_y = y - 8
    arr_x = W - 160
    d.line([(arr_x, arr_y), (arr_x + 70, arr_y)], fill=RED_ACCENT, width=4)
    d.line([(arr_x + 50, arr_y - 15), (arr_x + 70, arr_y)], fill=RED_ACCENT, width=4)
    d.line([(arr_x + 50, arr_y + 15), (arr_x + 70, arr_y)], fill=RED_ACCENT, width=4)

    y += 55
    d.text((72, y), "SOLD", font=huge, fill=BRIGHT_ACCENT)
    y += 130
    d.text((72, y), "OUT", font=huge, fill=BRIGHT_ACCENT)

    # Subtitle — bigger, brighter
    y += 160
    sub = load_font(30)
    d.text((80, y), "Five archive pieces that went from", font=sub, fill=BODY_TEXT)
    d.text((80, y + 42), "clearance rack to five-figure grail.", font=sub, fill=BODY_TEXT)

    # Bottom
    hline(d, H - 130, color=DARK_GREY)
    d.text((80, H - 100), "SWIPE →", font=load_font(28, bold=True), fill=OFF_WHITE)
    d.text((80, H - 65), "5 PIECES  ·  HISTORY  ·  MARKET DATA", font=load_font(22), fill=MID_GREY)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# PIECE SLIDE — Tighter, brighter, less text
# ══════════════════════════════════════════════════════════════
def piece_slide(num, data):
    img, d = new()
    scanlines(d)

    d.rectangle([(0, 0), (W, 4)], fill=ACCENT)

    # Header
    f18 = load_font(18)
    d.text((80, 40), f"{num:02d} / 05", font=f18, fill=MID_GREY)
    d.text((W - 260, 40), "ARCHIVE ARBITRAGE", font=f18, fill=MID_GREY)
    hline(d, 75, color=DARK_GREY)

    # Big faded number
    d.text((W - 340, 50), f"{num:02d}", font=load_font(220, bold=True), fill=(18, 18, 18))

    # Designer
    y = 110
    d.text((80, y), data["designer"], font=load_font(24), fill=ACCENT)

    # Piece name — larger
    y += 48
    pf = load_font(58, bold=True)
    for line in wrap(d, data["name"].upper(), pf, 880):
        d.text((80, y), line, font=pf, fill=OFF_WHITE)
        y += 68

    # Season
    y += 5
    d.text((80, y), data["season"], font=load_font(26), fill=LIGHT_GREY)

    # Divider
    y += 50
    hline(d, y, color=MID_GREY)
    y += 25

    # Story — condensed, 2 lines max, bigger font
    sf = load_font(30)
    for line in wrap(d, data["story_short"], sf, 880):
        d.text((80, y), line, font=sf, fill=BODY_TEXT)
        y += 42
    y += 25

    # ── PRICE BLOCK — the centerpiece ──
    hline(d, y, color=ACCENT, width=2)
    y += 20

    d.text((80, y), "PRICE TRAJECTORY", font=load_font(18), fill=ACCENT)
    y += 35

    # Then price
    lbl = load_font(20)
    price_big = load_font(64, bold=True)
    
    d.text((80, y), data["then_label"], font=lbl, fill=MID_GREY)
    y += 28
    d.text((80, y), data["then_price"], font=price_big, fill=LIGHT_GREY)
    then_bottom = y + 72

    # Arrow — drawn with lines for consistent rendering
    arrow_y = y + 30
    d.line([(440, arrow_y), (540, arrow_y)], fill=RED_ACCENT, width=4)
    d.line([(520, arrow_y - 15), (540, arrow_y)], fill=RED_ACCENT, width=4)
    d.line([(520, arrow_y + 15), (540, arrow_y)], fill=RED_ACCENT, width=4)

    # Now price
    d.text((560, y - 28), data["now_label"], font=lbl, fill=MID_GREY)
    d.text((560, y), data["now_price"], font=price_big, fill=BRIGHT_ACCENT)

    y = then_bottom + 20

    # Multiplier
    d.text((80, y), data["multiplier"], font=load_font(32, bold=True), fill=RED_ACCENT)
    y += 55

    hline(d, y, color=DARK_GREY)
    y += 20

    # Key insights — bigger mono, brighter
    mono = load_font(22, mono=True)
    for insight in data["insights"][:3]:  # Max 3 for readability
        d.text((80, y), insight, font=mono, fill=LIGHT_GREY)
        y += 34
    y += 20

    # Why it matters — bottom section
    hline(d, y, color=ACCENT, width=1)
    y += 18
    d.text((80, y), "WHY IT MATTERS NOW", font=load_font(18, bold=True), fill=ACCENT)
    y += 32
    why_f = load_font(28)
    for line in wrap(d, data["why_now"], why_f, 880):
        d.text((80, y), line, font=why_f, fill=OFF_WHITE)
        y += 38

    # Bottom brand bar
    hline(d, H - 60, color=DARK_GREY)
    d.text((80, H - 42), "@archivearbitrage", font=load_font(18), fill=MID_GREY)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# CTA SLIDE
# ══════════════════════════════════════════════════════════════
def cta_slide():
    img, d = new()
    scanlines(d)

    d.rectangle([(0, 0), (W, 5)], fill=ACCENT)
    d.text((80, 55), "ARCHIVE ARBITRAGE", font=load_font(20), fill=MID_GREY)
    hline(d, 100, color=DARK_GREY)

    # Headline — big and clear
    y = 220
    huge = load_font(72, bold=True)
    d.text((80, y), "THE NEXT", font=huge, fill=OFF_WHITE)
    y += 90
    d.text((80, y), "GRAIL IS", font=huge, fill=OFF_WHITE)
    y += 90
    d.text((80, y), "LISTED", font=huge, fill=BRIGHT_ACCENT)
    y += 90
    d.text((80, y), "RIGHT", font=huge, fill=BRIGHT_ACCENT)
    y += 90
    d.text((80, y), "NOW.", font=huge, fill=BRIGHT_ACCENT)

    y += 120
    hline(d, y, color=ACCENT, width=2)
    y += 30

    body = load_font(28)
    for line in [
        "We scan Grailed, Poshmark, Mercari,",
        "and Vinted 24/7. 250+ archive brands.",
        "Every deal authenticated before it",
        "reaches you.",
    ]:
        d.text((80, y), line, font=body, fill=BODY_TEXT)
        y += 40

    y += 35

    # Stats — monospace, bigger
    mono = load_font(24, mono=True)
    stats = [
        "PLATFORMS ........... 4",
        "BRANDS ............. 250+",
        "DAILY SCANS ........ 10,000+",
    ]
    for s in stats:
        d.text((80, y), s, font=mono, fill=LIGHT_GREY)
        y += 36

    y += 40
    hline(d, y, color=DARK_GREY)
    y += 25

    # CTA — prominent
    d.text((80, y), "$30/MONTH", font=load_font(44, bold=True), fill=OFF_WHITE)
    y += 60

    # Button-like element
    btn_y = y
    btn_text = "LINK IN BIO →"
    btn_font = load_font(26, bold=True)
    btn_w = d.textbbox((0, 0), btn_text, font=btn_font)[2] + 60
    d.rectangle([(78, btn_y - 5), (78 + btn_w, btn_y + 42)], outline=ACCENT, width=2)
    d.text((108, btn_y + 3), btn_text, font=btn_font, fill=ACCENT)

    y += 55
    d.text((80, y), "REAL-TIME TELEGRAM ALERTS", font=load_font(22), fill=MID_GREY)

    return fin(img)


# ══════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════
PIECES = [
    {
        "designer": "RAF SIMONS",
        "name": "Riot Riot Riot Bomber",
        "season": "AW01 — \"Riot Riot Riot\"",
        "story_short": "Debuted at one of fashion's most politically charged shows. Retailers pulled orders post-9/11. Pieces hit clearance racks. Now it's the most valuable garment in archive fashion.",
        "then_label": "CLEARANCE (2002)",
        "then_price": "$280",
        "now_label": "CURRENT MARKET",
        "now_price": "$47K+",
        "multiplier": "167× RETURN",
        "insights": [
            "Only ~50 bombers produced",
            "Museum pieces: MoMA, MET Costume Inst.",
            "Last sale: $47,000 (2023)",
        ],
        "why_now": "The bomber that made Raf the most collected designer alive. Every serious archive collection starts with wanting one.",
    },
    {
        "designer": "HELMUT LANG",
        "name": "Astro Biker Jacket",
        "season": "FW98 — Peak Helmut Era",
        "story_short": "Bonded rubber over nylon, asymmetric closure. When Lang left fashion in 2005, prices sat flat for a decade. The archive wave changed everything around 2016.",
        "then_label": "RESALE (2012)",
        "then_price": "$400",
        "now_label": "CURRENT MARKET",
        "now_price": "$6,500",
        "multiplier": "16× RETURN",
        "insights": [
            "Bonded rubber degrades — condition is king",
            "Sub-$1K examples almost extinct",
            "OG Lang (pre-2005) = 5-10× over Prada era",
        ],
        "why_now": "OG Lang pieces under $500 still surface on Poshmark and Mercari from sellers who don't know what they have. We caught 3 this month.",
    },
    {
        "designer": "NUMBER (N)INE",
        "name": "Heart Skull Cashmere",
        "season": "AW06 — \"NIL\" (Final Collection)",
        "story_short": "Miyashita's final collection before dissolving the brand. The skull-heart motif became the most recognizable symbol in Japanese archive fashion. Finite supply, infinite demand.",
        "then_label": "RETAIL (2006)",
        "then_price": "$800",
        "now_label": "CURRENT MARKET",
        "now_price": "$12K+",
        "multiplier": "15× RETURN",
        "insights": [
            "Brand dissolved 2009 — fixed supply",
            "Black/red colorway = most valuable",
            "Japanese archive = fastest appreciating",
        ],
        "why_now": "N(N) pieces under $2K are disappearing fast. If you see one priced wrong, it won't last an hour.",
    },
    {
        "designer": "MAISON MARGIELA",
        "name": "Tabi Boots",
        "season": "1988 — Debut Collection",
        "story_short": "Models walked through red paint, leaving split-toe footprints on white runway. Critics called them unwearable. Now the most iconic shoe silhouette of the last 40 years.",
        "then_label": "RESALE (2015)",
        "then_price": "$180",
        "now_label": "CURRENT MARKET",
        "now_price": "$800+",
        "multiplier": "4.4× RETURN",
        "insights": [
            "Vintage pairs (pre-Galliano) = premium",
            "Still in production — but OGs are different",
            "Mispriced Tabis on Mercari weekly",
        ],
        "why_now": "Entry-level archive grail. Sellers often price vintage at current retail — that's where the arbitrage lives.",
    },
    {
        "designer": "RICK OWENS",
        "name": "Dunks",
        "season": "SS09 — \"Crust\"",
        "story_short": "Before the Nike collab, before mainstream Rick. Handmade in Italy, brutalist, 3 pounds per shoe. They sat on sale racks. Then everything Rick touched turned to gold.",
        "then_label": "SALE RACK (2010)",
        "then_price": "$600",
        "now_label": "CURRENT MARKET",
        "now_price": "$3,500",
        "multiplier": "5.8× RETURN",
        "insights": [
            "OG Dunks (pre-2012) = different sole + leather",
            "Size 42-43 most liquid on resale",
            "Geobaskets on same trajectory, 2-3yr lag",
        ],
        "why_now": "Rick's mainstream moment means more demand hitting fixed supply. Mispriced Dunks and Geos appear daily — gone in minutes.",
    },
]


def build():
    slides = []
    print("  Cover...")
    slides.append(cover())

    for i, p in enumerate(PIECES):
        print(f"  {p['designer']} — {p['name']}...")
        slides.append(piece_slide(i + 1, p))

    print("  CTA...")
    slides.append(cta_slide())

    for i, s in enumerate(slides):
        path = os.path.join(OUT_DIR, f"editorial_v2_{i+1}.jpg")
        s.save(path, "JPEG", quality=95)
        print(f"  → {path}")

    return slides


if __name__ == "__main__":
    print("\n🐉 Building editorial v2: SLEPT ON → SOLD OUT\n")
    build()
    print(f"\nDone! 7 slides → marketing/posts/")
