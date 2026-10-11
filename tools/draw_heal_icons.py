"""Draw the armory wall's Bandages and Small Shield icons (assets/ui/T_KT_Icon_*.png).

    python tools/draw_heal_icons.py

Fortnite's own icons for these two can't be used: the Figment copies are disallowed by island validation and the
editor refuses to export Epic's textures. These are drawn to read like the in-game icons at tile size: a cream
bandage roll with its strip unrolling, and the round blue mini shield flask. Drawn at 4x and downsampled for clean
edges; 1024 px with alpha.
"""
import pathlib

from PIL import Image, ImageDraw, ImageFilter

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "ui"
S = 4                     # supersampling
N = 1024


def canvas():
    return Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))


def finish(im, name):
    im = im.resize((N, N), Image.LANCZOS)
    im.save(OUT / name)
    print("wrote", OUT / name)


def p(*xy):
    return [v * S for v in xy]


def bandage():
    im = canvas()
    d = ImageDraw.Draw(im)
    ink = (34, 30, 38, 255)
    # Loose strip unrolling down and to the left, drawn first so the roll sits on it.
    strip = [(250, 600), (520, 610), (430, 860), (90, 900), (150, 760)]
    d.polygon([tuple(v * S for v in pt) for pt in strip], fill=(238, 230, 210, 255), outline=ink, width=14 * S)
    for k in range(4):                                # weave lines on the strip
        a = 0.2 + 0.18 * k
        x0, y0 = 250 + (90 - 250) * a, 600 + (900 - 600) * a
        x1, y1 = 520 + (430 - 520) * a, 610 + (860 - 610) * a
        d.line(p(x0 + 30, y0 - 5, x1 - 10, y1 - 5), fill=(205, 196, 172, 255), width=8 * S)
    # Roll body: a cylinder lying on its side, seen a little from the right.
    body = p(230, 300, 760, 650)
    d.rounded_rectangle(body, radius=60 * S, fill=(246, 240, 224, 255), outline=ink, width=16 * S)
    for k in range(7):                                # wrap lines
        x = 300 + k * 64
        d.line(p(x, 312, x - 12, 638), fill=(214, 205, 182, 255), width=10 * S)
    shade = Image.new("RGBA", im.size, (0, 0, 0, 0))   # soft shadow under the roll's lower half
    ImageDraw.Draw(shade).rounded_rectangle(p(240, 520, 750, 640), radius=50 * S, fill=(150, 130, 100, 70))
    im.alpha_composite(shade.filter(ImageFilter.GaussianBlur(14 * S)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(body, radius=60 * S, outline=ink, width=16 * S)
    # End face with the core.
    d.ellipse(p(650, 290, 860, 660), fill=(232, 222, 198, 255), outline=ink, width=16 * S)
    for r in (80, 60):
        d.ellipse(p(755 - r * 0.55, 475 - r, 755 + r * 0.55, 475 + r), outline=(205, 194, 168, 255), width=8 * S)
    d.ellipse(p(728, 430, 782, 520), fill=(160, 146, 120, 255), outline=ink, width=8 * S)
    # Red cross on the roll.
    cx, cy, a, b = 445, 470, 95, 34
    d.rectangle(p(cx - a, cy - b, cx + a, cy + b), fill=(214, 38, 46, 255))
    d.rectangle(p(cx - b, cy - a, cx + b, cy + a), fill=(214, 38, 46, 255))
    d.line(p(270, 340, 640, 335), fill=(255, 255, 255, 170), width=18 * S)   # highlight
    finish(im, "T_KT_Icon_Bandage.png")


def small_shield():
    im = canvas()
    ink = (24, 30, 52, 255)
    # Glow behind the flask.
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(p(170, 250, 860, 940), fill=(70, 170, 255, 120))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60 * S)))
    d = ImageDraw.Draw(im)
    # Neck and silver cap.
    d.rounded_rectangle(p(430, 240, 600, 420), radius=24 * S, fill=(180, 214, 240, 255), outline=ink, width=16 * S)
    d.rounded_rectangle(p(400, 130, 630, 270), radius=36 * S, fill=(196, 204, 216, 255), outline=ink, width=16 * S)
    d.rectangle(p(420, 150, 470, 250), fill=(236, 240, 246, 255))
    # Round glass body.
    body = p(220, 340, 810, 930)
    d.ellipse(body, fill=(150, 205, 245, 255), outline=ink, width=18 * S)
    # Blue liquid filling the lower two thirds, lighter at the top surface.
    liquid = Image.new("L", im.size, 0)
    ld = ImageDraw.Draw(liquid)
    ld.ellipse(p(240, 360, 790, 910), fill=255)
    ld.rectangle(p(0, 0, N, 520), fill=0)
    fill = Image.new("RGBA", im.size, (36, 132, 238, 255))
    grad = Image.linear_gradient("L").resize(im.size)
    deep = Image.new("RGBA", im.size, (14, 72, 186, 255))
    fill = Image.composite(deep, fill, grad)
    im.paste(fill, (0, 0), liquid)
    d = ImageDraw.Draw(im)
    d.ellipse(p(250, 495, 780, 560), fill=(110, 196, 255, 255))           # liquid surface
    # Bubbles and glass highlights.
    for x, y, r in ((620, 700, 26), (560, 790, 16), (680, 610, 14)):
        d.ellipse(p(x - r, y - r, x + r, y + r), outline=(200, 236, 255, 255), width=7 * S)
    d.arc(p(270, 390, 760, 880), 200, 260, fill=(255, 255, 255, 230), width=30 * S)
    d.ellipse(p(330, 430, 400, 500), fill=(255, 255, 255, 220))
    d.ellipse(body, outline=ink, width=18 * S)
    finish(im, "T_KT_Icon_SmallShield.png")


if __name__ == "__main__":
    bandage()
    small_shield()
