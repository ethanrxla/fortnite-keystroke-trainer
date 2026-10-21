"""Render the theme-room art as PNGs (assets/theme/), all drawn here: no photos, no third-party characters.

    python tools/render_theme_art.py          # writes assets/theme/{67,heroes,cross}/...

Player 2026-10-11: Jamaica's National Heroes and Haile Selassie on the armory wall (illustrated, never real images, to
stay inside Epic's Developer Rules), a cross, and a "67 room" (the build wing) with 67 all over it. Bob Marley's name and
likeness are licensed by his estate, so his spot is a red-gold-green Rasta tribute panel with no name or face.
Hero cards: Jamaica's flag colours, a drawn bust, name, years and one line of why they are a hero. Text is facts only.
tools/build_theme_rooms.py imports and mounts these.

    python tools/render_theme_art.py --portraits DIR   # also redraw DIR/<key>.jpg (public-domain sources) as prints

Portraits: public-domain photos from Wikimedia Commons (SOURCES.md) are redrawn as four-ink screenprints
(assets/theme/heroes/print_<key>.png); the source photos are never stored in the repo or the map. Nanny, Sam Sharpe and
Paul Bogle have no public-domain portrait, so their cards keep the drawn bust.
"""
import math
import pathlib
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "theme"
TITLE = str(next((ROOT / "assets" / "fonts" / "bitcount-ink").glob("*.ttf")))
BODY = "C:/Windows/Fonts/bahnschrift.ttf"
HEAVY = "C:/Windows/Fonts/ariblk.ttf"
IMPACT = "C:/Windows/Fonts/impact.ttf"

GREEN, GOLD, BLACK = (0, 155, 58), (254, 209, 0), (0, 0, 0)
RED = (206, 17, 38)

# Jamaica's seven National Heroes (Order of National Hero), in the order they are usually listed, then Selassie.
HEROES = [
    ("nanny", "NANNY OF THE MAROONS", "c. 1686 - c. 1755", "Led the Windward Maroons and held the Blue Mountains against British forces. The only woman among the National Heroes."),
    ("sharpe", "SAMUEL SHARPE", "1801 - 1832", "Baptist deacon who led the 1831 Christmas Rebellion against slavery. Emancipation followed in 1834."),
    ("bogle", "PAUL BOGLE", "c. 1820 - 1865", "Baptist deacon who led the 1865 Morant Bay Rebellion for justice and fair treatment of the poor."),
    ("gordon", "GEORGE WILLIAM GORDON", "1820 - 1865", "Legislator and landowner who spoke for the poor in the Assembly. Executed after Morant Bay."),
    ("garvey", "MARCUS GARVEY", "1887 - 1940", "Founded the UNIA and led a worldwide movement for African pride and self-reliance. First National Hero (1964)."),
    ("bustamante", "SIR ALEXANDER BUSTAMANTE", "1884 - 1977", "Labour leader of the 1938 workers' movement and Jamaica's first Prime Minister (1962)."),
    ("manley", "NORMAN WASHINGTON MANLEY", "1893 - 1969", "Lawyer and Premier who led the drive for self-government and Jamaica's independence."),
    ("selassie", "HAILE SELASSIE I", "1892 - 1975", "Emperor of Ethiopia, 1930 - 1974. His visit to Jamaica on 21 April 1966 is remembered as Grounation Day."),
]


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        test = (line + " " + word).strip()
        if draw.textlength(test, font=fnt) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + [line]


def fit(draw, text, path, start, width):
    size = start
    while size > 12 and draw.textlength(text, font=font(path, size)) > width:
        size -= 2
    return font(path, size)


def bust(img, box, colour, rim):
    """A drawn head-and-shoulders silhouette with a rim light: an illustration, not anyone's likeness."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = (x0 + x1) / 2
    head_r = w * 0.2
    head_cy = y0 + h * 0.36
    d.ellipse([cx - head_r * 0.92, head_cy - head_r * 1.1, cx + head_r * 0.92, head_cy + head_r * 1.1], fill=rim)
    d.rectangle([cx - head_r * 0.42, head_cy + head_r * 0.7, cx + head_r * 0.42, head_cy + head_r * 1.5], fill=rim)
    d.chord([x0 + w * 0.08, y0 + h * 0.62, x1 - w * 0.08, y1 + h * 0.55], 180, 360, fill=rim)
    rim_layer = layer.filter(ImageFilter.GaussianBlur(6))
    img.alpha_composite(rim_layer)
    inner = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(inner)
    s = 0.94
    d.ellipse([cx - head_r * 0.92 * s, head_cy - head_r * 1.1 * s, cx + head_r * 0.92 * s, head_cy + head_r * 1.1 * s], fill=colour)
    d.rectangle([cx - head_r * 0.38, head_cy + head_r * 0.7, cx + head_r * 0.38, head_cy + head_r * 1.52], fill=colour)
    d.chord([x0 + w * 0.1, y0 + h * 0.64, x1 - w * 0.1, y1 + h * 0.57], 180, 360, fill=colour)
    img.alpha_composite(inner)


def flag_band(d, x0, y0, x1, y1, ethiopia=False):
    if ethiopia:
        hh = (y1 - y0) / 3
        for k, c in enumerate((GREEN, GOLD, RED)):
            d.rectangle([x0, y0 + k * hh, x1, y0 + (k + 1) * hh], fill=c)
        return
    d.rectangle([x0, y0, x1, y1], fill=GREEN)
    d.polygon([(x0, y0), (x0, y1), ((x0 + x1) / 2, (y0 + y1) / 2)], fill=BLACK)
    d.polygon([(x1, y0), (x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2)], fill=BLACK)
    t = (y1 - y0) * 0.16
    d.line([(x0, y0), (x1, y1)], fill=GOLD, width=int(t))
    d.line([(x0, y1), (x1, y0)], fill=GOLD, width=int(t))


def hero_card(key, name, years, line):
    W, H = 600, 900
    img = Image.new("RGBA", (W, H), (10, 14, 12, 255))
    d = ImageDraw.Draw(img)
    eth = key == "selassie"
    flag_band(d, 0, 0, W, 90, ethiopia=eth)
    # Background glow and the bust.
    portrait = OUT / "heroes" / f"print_{key}.png"
    if portrait.exists():
        img.alpha_composite(Image.open(portrait).convert("RGBA"), (0, 90))
    else:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([60, 140, W - 60, 620], fill=(GOLD if not eth else RED) + (70,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        bust(img, (90, 130, W - 90, 600), (18, 24, 20, 255), GOLD + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 600, W, H], fill=(6, 8, 7, 255))
    d.rectangle([0, 600, W, 608], fill=GOLD)
    nf = fit(d, name, TITLE, 52, W - 48)
    d.text((W / 2, 650), name, font=nf, fill=GOLD, anchor="mm")
    d.text((W / 2, 702), years, font=font(BODY, 30), fill=(220, 230, 220), anchor="mm")
    bf = font(BODY, 25)
    y = 740
    for ln in wrap(d, line, bf, W - 60):
        d.text((W / 2, y), ln, font=bf, fill=(200, 210, 205), anchor="mm")
        y += 32
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=6)
    return img


def tribute():
    """Red-gold-green Rasta tribute: stripes, a drawn crown and a five-pointed star. No name, no face."""
    W, H = 600, 900
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    hh = H / 3
    for k, c in enumerate((RED, GOLD, GREEN)):
        d.rectangle([0, k * hh, W, (k + 1) * hh], fill=c)
    cx, cy = W / 2, H / 2
    d.ellipse([cx - 200, cy - 200, cx + 200, cy + 200], fill=(12, 12, 12))
    # Crown.
    base_y, top_y = cy + 70, cy - 90
    pts = [(cx - 130, base_y), (cx - 130, cy - 30), (cx - 80, cy + 10), (cx - 40, top_y), (cx, cy - 10),
           (cx + 40, top_y), (cx + 80, cy + 10), (cx + 130, cy - 30), (cx + 130, base_y)]
    d.polygon(pts, fill=GOLD)
    d.rectangle([cx - 130, base_y, cx + 130, base_y + 34], fill=GOLD)
    for k, gx in enumerate((cx - 80, cx, cx + 80)):
        d.ellipse([gx - 13, base_y + 4, gx + 13, base_y + 30], fill=(RED, GREEN, RED)[k])
    for px in (cx - 130, cx - 40, cx + 40, cx + 130):
        d.ellipse([px - 12, (top_y if abs(px - cx) == 40 else cy - 30) - 24, px + 12, (top_y if abs(px - cx) == 40 else cy - 30)], fill=GOLD)
    # Star above.
    r1, r2, sy = 34, 14, cy - 150
    star = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        r = r1 if k % 2 == 0 else r2
        star.append((cx + r * math.cos(a), sy + r * math.sin(a)))
    d.polygon(star, fill=GOLD)
    d.text((cx, cy + 300), "RED  GOLD  GREEN", font=font(TITLE, 44), fill=GOLD, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=6)
    return img


def header():
    W, H = 2400, 260
    img = Image.new("RGBA", (W, H), (6, 8, 7, 255))
    d = ImageDraw.Draw(img)
    flag_band(d, 0, 0, 360, H)
    flag_band(d, W - 360, 0, W, H)
    d.text((W / 2, H * 0.42), "NATIONAL HEROES OF JAMAICA", font=fit(d, "NATIONAL HEROES OF JAMAICA", TITLE, 130, W - 820), fill=GOLD, anchor="mm")
    d.text((W / 2, H * 0.8), "Out of many, one people", font=font(BODY, 44), fill=(220, 230, 220), anchor="mm")
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=8)
    return img


def cross():
    W, H = 512, 768
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    cx, bw = W / 2, 70
    d.rectangle([cx - bw / 2 - 18, 20, cx + bw / 2 + 18, H - 20], fill=GOLD + (200,))
    d.rectangle([60, 210 - bw / 2 - 18, W - 60, 210 + bw / 2 + 18], fill=GOLD + (200,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rectangle([cx - bw / 2, 38, cx + bw / 2, H - 38], fill=(250, 246, 232, 255), outline=GOLD, width=6)
    d.rectangle([78, 210 - bw / 2, W - 78, 210 + bw / 2], fill=(250, 246, 232, 255), outline=GOLD, width=6)
    d.rectangle([cx - bw / 2 + 6, 210 - bw / 2 + 6, cx + bw / 2 - 6, 210 + bw / 2 - 6], fill=(250, 246, 232, 255))
    return img


SIXTY_SEVEN = [  # (font, fill, outline, tilt)
    (HEAVY, (255, 214, 0), (0, 0, 0), -8), (IMPACT, (255, 64, 129), (255, 255, 255), 6), (TITLE, (0, 229, 255), (10, 20, 60), -4),
    (HEAVY, (124, 255, 79), (0, 60, 0), 10), (IMPACT, (255, 255, 255), (220, 30, 30), -12), (TITLE, (255, 140, 0), (40, 0, 60), 4),
    (HEAVY, (186, 104, 255), (255, 255, 255), -2), (IMPACT, (0, 200, 120), (0, 0, 0), 14), (HEAVY, (255, 82, 82), (255, 214, 0), 0),
    (TITLE, (255, 255, 255), (0, 120, 255), -10),
]


def sixty_seven(n, spec):
    path, fill, outline, tilt = spec
    W = H = 512
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(path, 300)
    stroke = 16
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((W / 2 + 12, H / 2 + 14), "67", font=f, fill=(0, 0, 0, 150), anchor="mm",
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
    d.text((W / 2, H / 2), "67", font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=outline)
    if n % 3 == 1:   # a few with sparkle marks, graffiti style
        rng = random.Random(n)
        for _ in range(5):
            x, y, r = rng.uniform(40, W - 40), rng.uniform(40, H - 40), rng.uniform(10, 22)
            d.line([(x - r, y), (x + r, y)], fill=(255, 255, 255), width=5)
            d.line([(x, y - r), (x, y + r)], fill=(255, 255, 255), width=5)
    img = img.rotate(tilt, resample=Image.BICUBIC, expand=False)
    return img


PRINT_BOX = (600, 510)          # the portrait window on a hero card (under the 90 px flag band)
# Head-and-shoulders crop of each public-domain source (fractions of width / height), chosen by eye.
CROPS = {"gordon": (0.05, 0.0, 0.95, 0.62), "garvey": (0.17, 0.0, 0.63, 0.42), "manley": (0.0, 0.0, 1.0, 0.66),
         "selassie": (0.1, 0.0, 0.9, 0.58), "bustamante": (0.04, 0.0, 0.96, 0.8)}


def screenprint(src, key):
    """A public-domain portrait redrawn as a four-ink screenprint: no photo survives, only flat tone shapes."""
    im = Image.open(src).convert("L")
    w, h = im.size
    l, t, r, b = CROPS.get(key, (0, 0, 1, 1))
    im = im.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
    # Fill the window (cover), then flatten into four inks at the image's own quartiles.
    bw, bh = PRINT_BOX
    scale = max(bw / im.width, bh / im.height)
    im = im.resize((max(bw, int(im.width * scale)), max(bh, int(im.height * scale))), Image.LANCZOS)
    x0, y0 = (im.width - bw) // 2, 0
    im = im.crop((x0, y0, x0 + bw, y0 + bh))
    # Gordon's source is a hatched engraving: blur the hatching into tone first, and give the light inks more room.
    engraving = key == "gordon"
    im = ImageOps.autocontrast(im, cutoff=2).filter(ImageFilter.GaussianBlur(5.0 if engraving else 2.2))
    hist = sorted(im.get_flattened_data())
    q = [hist[int(len(hist) * f)] for f in ((0.18, 0.38, 0.62) if engraving else (0.3, 0.55, 0.8))]
    inks = [(14, 18, 16), (RED if key == "selassie" else GREEN), GOLD, (250, 240, 210)]
    lut = []
    for v in range(256):
        k = 0 if v < q[0] else 1 if v < q[1] else 2 if v < q[2] else 3
        lut.append(k)
    idx = im.point(lut)
    out = Image.new("RGBA", PRINT_BOX)
    px = out.load()
    src_px = idx.load()
    for yy in range(bh):
        for xx in range(bw):
            px[xx, yy] = inks[src_px[xx, yy]] + (255,)
    # Halftone dots over the mid inks, so it reads as print, not a filtered photo.
    d = ImageDraw.Draw(out)
    for yy in range(4, bh, 9):
        for xx in range(4 + (yy // 9 % 2) * 4, bw, 9):
            if src_px[xx, yy] in (1, 2):
                d.ellipse([xx - 1.4, yy - 1.4, xx + 1.4, yy + 1.4], fill=(14, 18, 16, 110))
    return out


def lion_head(img, cx, cy, r):
    """A drawn lion-of-Judah emblem: a rayed mane, a face, and a small crown on top."""
    d = ImageDraw.Draw(img)
    rays = 22
    pts = []
    for k in range(rays * 2):
        a = math.pi * k / rays
        rr = r if k % 2 == 0 else r * 0.78
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=(196, 110, 18))
    d.ellipse([cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8], fill=(226, 140, 30))
    fr = r * 0.56
    d.ellipse([cx - fr, cy - fr * 0.95, cx + fr, cy + fr * 1.05], fill=GOLD)
    # Ears.
    for s in (-1, 1):
        ex = cx + s * fr * 0.78
        d.ellipse([ex - fr * 0.24, cy - fr * 1.02, ex + fr * 0.24, cy - fr * 0.55], fill=GOLD, outline=(140, 80, 10), width=4)
    # Eyes, brows, muzzle, nose, mouth.
    for s in (-1, 1):
        ex, ey = cx + s * fr * 0.36, cy - fr * 0.18
        d.ellipse([ex - fr * 0.11, ey - fr * 0.08, ex + fr * 0.11, ey + fr * 0.08], fill=(20, 16, 10))
        d.line([(ex - s * fr * 0.18, ey - fr * 0.2), (ex + s * fr * 0.16, ey - fr * 0.14)], fill=(120, 70, 10), width=6)
    d.ellipse([cx - fr * 0.42, cy + fr * 0.12, cx + fr * 0.42, cy + fr * 0.72], fill=(255, 236, 170))
    d.polygon([(cx - fr * 0.18, cy + fr * 0.12), (cx + fr * 0.18, cy + fr * 0.12), (cx, cy + fr * 0.34)], fill=(60, 30, 20))
    d.line([(cx, cy + fr * 0.34), (cx, cy + fr * 0.5)], fill=(60, 30, 20), width=5)
    d.arc([cx - fr * 0.3, cy + fr * 0.36, cx, cy + fr * 0.62], 20, 160, fill=(60, 30, 20), width=5)
    d.arc([cx, cy + fr * 0.36, cx + fr * 0.3, cy + fr * 0.62], 20, 160, fill=(60, 30, 20), width=5)
    # Crown.
    by, ty = cy - r * 0.86, cy - r * 1.32
    cw = r * 0.62
    d.polygon([(cx - cw, by), (cx - cw, ty + 30), (cx - cw / 2, by - 40), (cx, ty), (cx + cw / 2, by - 40),
               (cx + cw, ty + 30), (cx + cw, by)], fill=GOLD, outline=(120, 70, 10))
    d.rectangle([cx - cw, by - 6, cx + cw, by + 18], fill=GOLD, outline=(120, 70, 10))
    d.ellipse([cx - 10, by - 2, cx + 10, by + 16], fill=RED)


def tribute_lion():
    """Red-gold-green Rasta tribute with the lion of Judah. No name, no face of any person."""
    W, H = 600, 900
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    hh = H / 3
    for k, c in enumerate((RED, GOLD, GREEN)):
        d.rectangle([0, k * hh, W, (k + 1) * hh], fill=c)
    d.ellipse([60, 200, W - 60, 680], fill=(12, 12, 12))
    lion_head(img, W / 2, 470, 190)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 800), "LION OF JUDAH", font=font(TITLE, 50), fill=GOLD, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=6)
    return img


WORDS = [("LARP", (255, 82, 82), (255, 255, 255), -6, HEAVY), ("MOG", (124, 255, 79), (0, 0, 0), 5, IMPACT),
         ("LARP", (0, 229, 255), (10, 20, 60), 4, TITLE), ("MOG", (255, 214, 0), (60, 0, 80), -4, HEAVY),
         ("MOGGED", (186, 104, 255), (255, 255, 255), 3, IMPACT)]


def word(text, fill, outline, tilt, path):
    W, H = 768, 384
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = fit(d, text, path, 250, W - 80)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((W / 2 + 10, H / 2 + 12), text, font=f, fill=(0, 0, 0, 150), anchor="mm", stroke_width=14,
                            stroke_fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d.text((W / 2, H / 2), text, font=f, fill=fill, anchor="mm", stroke_width=14, stroke_fill=outline)
    return img.rotate(tilt, resample=Image.BICUBIC)


CHARACTERS = [((255, 120, 60), (255, 214, 0)), ((80, 170, 255), (255, 255, 255)), ((124, 220, 90), (255, 82, 129)),
              ((186, 104, 255), (0, 229, 255))]


def six_seven_character(n, body, accent):
    """An original cartoon character doing the 6-7 hands (one palm up high, one low, like weighing it up)."""
    W, H = 512, 640
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = (20, 20, 28)
    cx = W / 2
    up_left = n % 2 == 0
    # Arms first, behind the body.
    for s in (-1, 1):
        high = (s == -1) == up_left
        sx, sy = cx + s * 120, 380
        hx, hy = cx + s * 210, 170 if high else 300
        d.line([(sx, sy), (hx, hy + 40)], fill=ink, width=34)
        d.line([(sx, sy), (hx, hy + 40)], fill=body, width=22)
        # Open palm facing up, with a label above it.
        d.ellipse([hx - 44, hy + 14, hx + 44, hy + 60], fill=accent, outline=ink, width=6)
        for f in range(4):
            fx = hx - 33 + f * 22
            d.rounded_rectangle([fx - 8, hy - 18, fx + 8, hy + 30], radius=8, fill=accent, outline=ink, width=5)
        d.text((hx, hy - 52), "6" if s == -1 else "7", font=font(HEAVY, 64), fill=accent, anchor="mm",
               stroke_width=6, stroke_fill=ink)
    # Body and head.
    d.ellipse([cx - 140, 300, cx + 140, 600], fill=body, outline=ink, width=8)
    d.ellipse([cx - 120, 120, cx + 120, 340], fill=body, outline=ink, width=8)
    # Face: big eyes, raised brows, a grin.
    for s in (-1, 1):
        ex = cx + s * 46
        d.ellipse([ex - 30, 190, ex + 30, 252], fill=(255, 255, 255), outline=ink, width=5)
        d.ellipse([ex - 12 + s * 6, 212, ex + 12 + s * 6, 238], fill=ink)
        d.line([(ex - 26, 176 - s * 4), (ex + 26, 176 + s * 4)], fill=ink, width=8)
    d.chord([cx - 62, 250, cx + 62, 318], 0, 180, fill=ink)
    d.chord([cx - 46, 262, cx + 46, 300], 0, 180, fill=(255, 255, 255))
    # Motion marks by the hands.
    for s in (-1, 1):
        mx = cx + s * 285
        for k in range(3):
            d.line([(mx, 180 + k * 40), (mx + s * 26, 168 + k * 40)], fill=accent, width=7)
    return img


INK = (14, 18, 16)
CREAM = (250, 240, 210)


def halftone(img, box, colour, step=9, r=1.6, alpha=110):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    for yy in range(y0 + 4, y1, step):
        for xx in range(x0 + 4 + (yy // step % 2) * step // 2, x1, step):
            d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=colour + (alpha,))


def sketch_print(key):
    """Drawn screenprint for a hero with no public-domain portrait: an illustrated figure in the same four inks as
    the other cards (not a likeness of anyone), with a scene from their story behind."""
    W, H = PRINT_BOX
    img = Image.new("RGBA", (W, H), CREAM + (255,))
    d = ImageDraw.Draw(img)
    cx = W / 2
    if key == "nanny":
        # Blue Mountains behind, sun.
        d.ellipse([380, 40, 520, 180], fill=GOLD)
        d.polygon([(0, 330), (120, 190), (220, 280), (340, 150), (470, 270), (600, 200), (600, 510), (0, 510)], fill=GREEN)
    elif key == "sharpe":
        # Chapel window behind.
        d.rectangle([60, 60, 220, 330], fill=GOLD)
        d.pieslice([60, -20, 220, 140], 180, 360, fill=GOLD)
        d.line([(140, 60), (140, 330)], fill=INK, width=8)
        d.line([(60, 190), (220, 190)], fill=INK, width=8)
        d.rectangle([0, 360, W, H], fill=GREEN)
    else:  # bogle: the Morant Bay court house steps
        d.rectangle([0, 300, W, H], fill=GREEN)
        d.polygon([(330, 120), (600, 120), (600, 300), (330, 300)], fill=GOLD)
        d.polygon([(310, 120), (465, 40), (620, 120)], fill=GOLD)
        for k in range(4):
            d.rectangle([350 + k * 65, 140, 370 + k * 65, 300], fill=INK)
    halftone(img, (0, 0, W, H), INK, alpha=60)
    d = ImageDraw.Draw(img)
    # Shoulders and coat.
    coat = GREEN if key == "nanny" else INK
    d.chord([cx - 230, 330, cx + 230, 760], 180, 360, fill=coat, outline=INK, width=6)
    if key == "nanny":
        d.polygon([(cx - 70, 340), (cx + 70, 340), (cx, 440)], fill=GOLD)          # neckline
        for k in range(7):                                                         # bead necklace
            a = math.pi * (0.15 + 0.7 * k / 6)
            d.ellipse([cx - 95 * math.cos(a) - 9, 345 + 60 * math.sin(a) - 9, cx - 95 * math.cos(a) + 9, 345 + 60 * math.sin(a) + 9], fill=RED)
    elif key == "sharpe":
        d.polygon([(cx - 60, 335), (cx + 60, 335), (cx, 420)], fill=CREAM)          # shirt
        d.rectangle([cx - 22, 340, cx - 4, 400], fill=CREAM, outline=INK, width=3)  # preaching bands
        d.rectangle([cx + 4, 340, cx + 22, 400], fill=CREAM, outline=INK, width=3)
        d.rectangle([cx + 90, 400, cx + 190, 470], fill=RED, outline=INK, width=5)  # Bible
        d.line([(cx + 140, 410), (cx + 140, 460)], fill=GOLD, width=5)
        d.line([(cx + 120, 428), (cx + 160, 428)], fill=GOLD, width=5)
    else:
        d.polygon([(cx - 60, 335), (cx + 60, 335), (cx, 420)], fill=CREAM)
        d.polygon([(cx - 20, 345), (cx + 20, 345), (cx, 380)], fill=RED)            # cravat
    # Neck and head (round, simple features: an illustration, not a portrait).
    skin, shade = (120, 72, 40), (82, 46, 24)
    d.rectangle([cx - 38, 270, cx + 38, 345], fill=shade)
    d.ellipse([cx - 92, 110, cx + 92, 310], fill=skin, outline=INK, width=6)
    for s in (-1, 1):                                                              # ears
        d.ellipse([cx + s * 92 - 16, 190, cx + s * 92 + 16, 240], fill=skin, outline=INK, width=5)
    for s in (-1, 1):                                                              # eyes and brows
        ex = cx + s * 36
        d.ellipse([ex - 13, 192, ex + 13, 210], fill=CREAM, outline=INK, width=3)
        d.ellipse([ex - 6, 195, ex + 6, 207], fill=INK)
        d.line([(ex - 20, 180), (ex + 18, 178)], fill=INK, width=7)
    d.line([(cx, 205), (cx - 8, 245), (cx + 10, 247)], fill=shade, width=6)          # nose
    d.arc([cx - 30, 245, cx + 30, 280], 15, 165, fill=INK, width=6)                # mouth
    if key == "nanny":
        # Head wrap: tall folded cloth with a knot, gold hoop earrings.
        d.chord([cx - 100, 70, cx + 100, 230], 180, 360, fill=RED, outline=INK, width=6)
        d.ellipse([cx - 60, 20, cx + 70, 120], fill=RED, outline=INK, width=6)
        d.line([(cx - 90, 150), (cx + 90, 130)], fill=GOLD, width=10)
        d.line([(cx - 80, 120), (cx + 60, 95)], fill=GOLD, width=8)
        for s in (-1, 1):
            d.ellipse([cx + s * 92 - 18, 240, cx + s * 92 + 18, 290], outline=GOLD, width=7)
    elif key == "sharpe":
        d.chord([cx - 94, 100, cx + 94, 230], 180, 360, fill=INK)                  # close-cut hair
    else:
        d.chord([cx - 94, 100, cx + 94, 220], 180, 360, fill=INK)                  # hair
        d.chord([cx - 88, 200, cx + 88, 345], 0, 180, fill=INK)                    # full beard
        d.arc([cx - 30, 238, cx + 30, 272], 15, 165, fill=CREAM, width=5)
    halftone(img, (0, 330, W, H), CREAM, step=10, r=1.4, alpha=50)
    return img


def tribute_reggae():
    """A reggae tribute: a dreadlocked guitarist in silhouette on a red-gold-green sunburst. No name, no face."""
    W, H = 600, 900
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, 400
    for k in range(24):
        a0, a1 = 2 * math.pi * k / 24, 2 * math.pi * (k + 1) / 24
        c = (RED, GOLD, GREEN)[k % 3]
        d.polygon([(cx, cy), (cx + 900 * math.cos(a0), cy + 900 * math.sin(a0)), (cx + 900 * math.cos(a1), cy + 900 * math.sin(a1))], fill=c)
    sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    q = ImageDraw.Draw(sil)
    s = (0, 0, 0, 255)
    hx, hy = cx, 230
    q.ellipse([hx - 58, hy - 70, hx + 58, hy + 62], fill=s)                          # head
    q.rectangle([hx - 26, hy + 40, hx + 26, hy + 100], fill=s)                       # neck
    for k in range(10):                                                              # locks hanging down, gaps between
        a = math.radians(-70 + k * 15.5)
        x0, y0 = hx + 56 * math.sin(a), hy - 40 + 30 * (1 - math.cos(a))
        x1, y1 = x0 + 34 * math.sin(a), hy + 175 + (k % 3) * 22
        q.line([(x0, y0), (x1, y1)], fill=s, width=13)
        q.ellipse([x1 - 7, y1 - 7, x1 + 7, y1 + 7], fill=s)
    q.polygon([(hx - 120, hy + 150), (hx + 120, hy + 150), (hx + 150, hy + 430), (hx - 150, hy + 430)], fill=s)  # torso
    q.ellipse([hx - 150, hy + 120, hx - 60, hy + 200], fill=s)                        # shoulders
    q.ellipse([hx + 60, hy + 120, hx + 150, hy + 200], fill=s)
    q.rectangle([hx - 150, hy + 420, hx + 150, H], fill=s)
    gx, gy = hx - 20, hy + 330
    rim = sil.split()[3].filter(ImageFilter.MaxFilter(9))
    img.paste(GOLD + (255,), (0, 0), rim)
    img.alpha_composite(sil)
    d = ImageDraw.Draw(img)
    wood = (150, 82, 30)
    d.line([(gx + 10, gy - 10), (gx + 230, gy - 250)], fill=wood, width=22)           # guitar neck, in front
    d.polygon([(gx + 220, gy - 265), (gx + 262, gy - 300), (gx + 278, gy - 284), (gx + 238, gy - 245)], fill=wood)
    d.ellipse([gx - 140, gy - 80, gx + 40, gy + 95], fill=wood, outline=GOLD, width=5)   # body
    d.ellipse([gx - 100, gy - 30, gx - 10, gy + 50], fill=wood)
    d.ellipse([gx - 70, gy - 10, gx - 30, gy + 30], fill=(0, 0, 0), outline=GOLD, width=4)  # sound hole
    for t in range(4):                                                               # strings
        d.line([(gx - 60 + t * 6, gy + 10), (gx + 232 + t * 4, gy - 262)], fill=GOLD, width=1)
    d.text((W / 2, 820), "REGGAE", font=font(TITLE, 70), fill=GOLD, anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=6)
    return img


def calvary():
    """Calvary: Jesus on the cross between the two thieves, crown of thorns and the INRI sign, drawn as silhouettes
    against the sky (no wounds, no blood)."""
    W, H = 1500, 900
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(H):                                               # dusk sky
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(60 + 170 * t), int(30 + 70 * t), int(90 - 40 * t)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W / 2 - 330, 60, W / 2 + 330, 640], fill=GOLD + (150,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    d = ImageDraw.Draw(img)
    d.chord([-300, 640, W + 300, 1500], 180, 360, fill=(20, 16, 24))   # the hill
    s = (10, 8, 12)

    def figure(cx, top, scale, centre):
        beam_y = top + 110 * scale
        d.rectangle([cx - 14 * scale, top, cx + 14 * scale, top + 520 * scale], fill=s)        # upright
        d.rectangle([cx - 190 * scale, beam_y - 12 * scale, cx + 190 * scale, beam_y + 14 * scale], fill=s)  # beam
        hy = beam_y + 10 * scale
        d.ellipse([cx - 34 * scale, hy - 52 * scale, cx + 34 * scale, hy + 18 * scale], fill=s)    # head (bowed)
        d.polygon([(cx - 175 * scale, beam_y + 6 * scale), (cx - 40 * scale, hy + 30 * scale), (cx - 45 * scale, hy + 60 * scale),
                   (cx - 175 * scale, beam_y + 20 * scale)], fill=s)                               # arms
        d.polygon([(cx + 175 * scale, beam_y + 6 * scale), (cx + 40 * scale, hy + 30 * scale), (cx + 45 * scale, hy + 60 * scale),
                   (cx + 175 * scale, beam_y + 20 * scale)], fill=s)
        d.polygon([(cx - 48 * scale, hy + 20 * scale), (cx + 48 * scale, hy + 20 * scale), (cx + 36 * scale, hy + 230 * scale),
                   (cx - 36 * scale, hy + 230 * scale)], fill=s)                                   # body and cloth
        d.polygon([(cx - 30 * scale, hy + 230 * scale), (cx + 30 * scale, hy + 230 * scale), (cx + 8 * scale, hy + 400 * scale),
                   (cx - 8 * scale, hy + 400 * scale)], fill=s)                                    # legs
        if centre:
            # Crown of thorns: a gold ring of spikes on the head; the INRI sign above.
            r0 = 40 * scale
            pts = []
            for k in range(28):
                a = 2 * math.pi * k / 28
                rr = r0 if k % 2 == 0 else r0 * 1.32
                pts.append((cx + rr * math.cos(a), hy - 30 * scale + rr * 0.42 * math.sin(a)))
            d.polygon(pts, outline=GOLD, width=5)
            d.rectangle([cx - 80, top - 70, cx + 80, top - 6], fill=CREAM, outline=s, width=4)
            d.text((cx, top - 38), "INRI", font=font(HEAVY, 44), fill=s, anchor="mm")

    figure(W / 2, 190, 1.0, True)
    figure(W / 2 - 470, 330, 0.72, False)
    figure(W / 2 + 470, 330, 0.72, False)
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=8)
    return img


def header_other():
    W, H = 2400, 200
    img = Image.new("RGBA", (W, H), (6, 8, 7, 255))
    d = ImageDraw.Draw(img)
    hh = H / 3
    for k, c in enumerate((RED, GOLD, GREEN)):
        d.rectangle([0, k * hh, 300, (k + 1) * hh], fill=c)
        d.rectangle([W - 300, k * hh, W, (k + 1) * hh], fill=c)
    d.text((W / 2, H / 2), "FAITH  AND  ROOTS", font=fit(d, "FAITH  AND  ROOTS", TITLE, 120, W - 720), fill=GOLD, anchor="mm")
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD, width=8)
    return img


def verse_card(text, ref):
    """A Bible verse panel (shared/bible-verses.json, KJV): verse in white, reference in gold, on a dark card with a
    thin gold frame. The text shrinks until it fits, so long and short verses share one card size."""
    w, h = 1600, 900
    img = Image.new("RGBA", (w, h), (10, 14, 26, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((18, 18, w - 19, h - 19), outline=GOLD, width=6)
    d.rectangle((34, 34, w - 35, h - 35), outline=(120, 100, 30), width=2)
    ref_font = font(TITLE, 64)
    box_w, box_h = w - 220, h - 300
    for size in range(84, 30, -2):
        body = font(BODY, size)
        lines = wrap(d, "“" + text + "”", body, box_w)
        line_h = int(size * 1.28)
        if len(lines) * line_h <= box_h:
            break
    y = 110 + (box_h - len(lines) * line_h) // 2
    for line in lines:
        d.text(((w - d.textlength(line, font=body)) / 2, y), line, font=body, fill=(245, 245, 240))
        y += line_h
    d.text(((w - d.textlength(ref, font=ref_font)) / 2, h - 170), ref, font=ref_font, fill=GOLD)
    return img


def main():
    import sys
    import json
    (OUT / "verses").mkdir(parents=True, exist_ok=True)
    verses = json.loads((ROOT / "shared" / "bible-verses.json").read_text(encoding="utf-8"))["verses"]
    for n, v in enumerate(verses):
        verse_card(v["text"], v["ref"]).save(OUT / "verses" / f"verse_{n:02d}.png")
    if "--verses-only" in sys.argv:
        print("rendered", len(verses), "verse cards to", OUT / "verses")
        return
    (OUT / "heroes").mkdir(parents=True, exist_ok=True)
    (OUT / "67").mkdir(parents=True, exist_ok=True)
    if "--portraits" in sys.argv:
        src = pathlib.Path(sys.argv[sys.argv.index("--portraits") + 1])
        for key in CROPS:
            if (src / f"{key}.jpg").exists():
                screenprint(src / f"{key}.jpg", key).save(OUT / "heroes" / f"print_{key}.png")
    for key in ("nanny", "sharpe", "bogle"):
        sketch_print(key).save(OUT / "heroes" / f"print_{key}.png")
    for key, name, years, line in HEROES:
        hero_card(key, name, years, line).save(OUT / "heroes" / f"hero_{key}.png")
    tribute_lion().save(OUT / "heroes" / "tribute_rasta.png")
    tribute_reggae().save(OUT / "heroes" / "tribute_reggae.png")
    calvary().save(OUT / "heroes" / "calvary.png")
    header_other().save(OUT / "heroes" / "header_roots.png")
    header().save(OUT / "heroes" / "header.png")
    cross().save(OUT / "cross.png")
    for n, spec in enumerate(SIXTY_SEVEN):
        sixty_seven(n, spec).save(OUT / "67" / f"sixty_seven_{n:02d}.png")
    for n, spec in enumerate(WORDS):
        word(*spec).save(OUT / "67" / f"word_{spec[0].lower()}_{n:02d}.png")
    for n, (body, accent) in enumerate(CHARACTERS):
        six_seven_character(n, body, accent).save(OUT / "67" / f"character_{n:02d}.png")
    print("rendered to", OUT)


if __name__ == "__main__":
    main()
