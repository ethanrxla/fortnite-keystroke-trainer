"""Render the theme-room art as PNGs (assets/theme/), all drawn here: no photos, no third-party characters.

    python tools/render_theme_art.py          # writes assets/theme/{67,heroes,cross}/...

Player 2026-10-11: Jamaica's National Heroes and Haile Selassie on the armory wall (illustrated, never real images, to
stay inside Epic's Developer Rules), a cross, and a "67 room" (the build wing) with 67 all over it. Bob Marley's name and
likeness are licensed by his estate, so his spot is a red-gold-green Rasta tribute panel with no name or face.
Hero cards: Jamaica's flag colours, a drawn bust, name, years and one line of why they are a hero. Text is facts only.
tools/build_theme_rooms.py imports and mounts these.
"""
import math
import pathlib
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


def main():
    (OUT / "heroes").mkdir(parents=True, exist_ok=True)
    (OUT / "67").mkdir(parents=True, exist_ok=True)
    for key, name, years, line in HEROES:
        hero_card(key, name, years, line).save(OUT / "heroes" / f"hero_{key}.png")
    tribute().save(OUT / "heroes" / "tribute_rasta.png")
    header().save(OUT / "heroes" / "header.png")
    cross().save(OUT / "cross.png")
    for n, spec in enumerate(SIXTY_SEVEN):
        sixty_seven(n, spec).save(OUT / "67" / f"sixty_seven_{n:02d}.png")
    print("rendered to", OUT)


if __name__ == "__main__":
    main()
