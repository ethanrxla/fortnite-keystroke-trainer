"""Skills Test: shoot a tile to pick the difficulty or the weapon, or to start, additive (KT15_SkillsTile_* only).

    python tools/build_skills_tiles.py [--dry-run]

History: 2026-10-11 the player asked for shootable difficulty buttons; they floated above lane A2 and were retired on
2026-10-20 ("removed from the aim practice area"). Player 2026-10-20, again: the Skills Test buttons "should also have
shootable buttons". So they come back low, as a row on the floor just past the shoot line (like the gun range's counter
tiles), under the sight line to the bots: EASY, MEDIUM, HARD, HAND CANNON, HEAVY AR, START, each a 95 x 95 cm plate
with its word, a grid of hit dummies over the whole plate (hitbox.place_grid), wired On Hit -> a hidden trigger under
the floor tagged for kt_skills_test_device (SkillsTest.verse). The difficulty tiles have a small light that is on for
the chosen level. The interact buttons behind the shoot line stay.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402
import hitbox  # noqa: E402
from build_skills_test import SHOOT_X, LANE_Y  # noqa: E402
from build_range_modes import FONT, TEX_FOLDER  # noqa: E402

PREFIX = "KT15_SkillsTile_"
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
FACE_X = SHOOT_X + 160.0        # the plates stand just past the shoot line, facing back at the player (-X)
Z = 58.0                         # centre: the plate stands on the floor, top at about 1 m
TILE_W, TILE_H, PITCH = 95.0, 95.0, 165.0
# name, plate rgb (linear), trigger tag, light tag, light rgb
TILES = [("EASY", (0.02, 0.25, 0.04), "kt_skills_easy_tag", "kt_skills_light_easy_tag", (0.2, 1.0, 0.3)),
         ("MEDIUM", (0.30, 0.22, 0.01), "kt_skills_medium_tag", "kt_skills_light_medium_tag", (1.0, 0.8, 0.1)),
         ("HARD", (0.30, 0.02, 0.02), "kt_skills_hard_tag", "kt_skills_light_hard_tag", (1.0, 0.15, 0.1)),
         ("HAND CANNON", (0.18, 0.08, 0.02), "kt_skills_handcannon_shot_tag", None, None),
         ("HEAVY AR", (0.06, 0.08, 0.10), "kt_skills_heavy_ar_shot_tag", None, None),
         ("START", (0.25, 0.25, 0.28), "kt_skills_start_shot_tag", None, None)]


def texture(name, rgb):
    from PIL import Image, ImageDraw, ImageFont
    key = name.replace(" ", "")
    out = bm.ROOT / "assets" / "ui" / "skills_tiles" / f"T_KT_SkillsTile_{key}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    srgb = tuple(int(255 * min(1.0, (c * 1.6) ** (1 / 2.2))) for c in rgb)
    w_px, h_px = 768, round(768 * TILE_H / TILE_W)
    im = Image.new("RGBA", (w_px, h_px), srgb + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle((10, 10, w_px - 11, h_px - 11), outline=(255, 255, 255, 200), width=10)
    font_file = next(FONT.glob("*.ttf"))
    size = 200
    while size > 30:
        f = ImageFont.truetype(str(font_file), size)
        if d.textlength(name, font=f) <= w_px - 100 and size <= h_px - 120:
            break
        size -= 6
    d.text((w_px / 2, h_px / 2), name, font=f, fill=(255, 255, 255, 255), anchor="mm", stroke_width=6,
           stroke_fill=(0, 0, 0, 220))
    im.save(out)
    asset = f"T_KT_SkillsTile_{key}"
    return out, f"{TEX_FOLDER}/{asset}.{asset}"


def plate(g, label, x, y, z, material):
    """A TILE_W x TILE_H plate facing -X: Grid.plane is square, so scale it and check its long side runs along y."""
    m = g.m
    path = g.plane(label, x, y, z, TILE_H, 90.0, material)
    t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": path})
    for sx, sy in ((TILE_W / 100.0, TILE_H / 100.0), (TILE_H / 100.0, TILE_W / 100.0)):
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path},
               xform={"location": t["location"], "rotation": t["rotation"], "scale": {"x": sx, "y": sy, "z": 1.0}})
        b = next(a for a in m.tool(bm.SCENE, "find_actors", name=label, collision_channels=[]) if a["label"] == label)["bounds"]
        if abs((b["max"]["y"] - b["min"]["y"]) - TILE_W) < 5.0:
            return path, b
    raise RuntimeError(f"{label}: could not size the plate to {TILE_W:.0f} x {TILE_H:.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ys = [LANE_Y + (k - (len(TILES) - 1) / 2) * PITCH for k in range(len(TILES))]
    for (name, *_), y in zip(TILES, ys):
        print(f"  {name:12} at ({FACE_X:.0f}, {y:.0f}, {Z:.0f})")
    if args.dry_run:
        return
    g = ag.Grid()
    b, m = g.b, g.m
    for a in m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for (name, rgb, tag, light_tag, light_rgb), y in zip(TILES, ys):
        label = PREFIX + name.replace(" ", "")
        png, tex = texture(name, rgb)
        if not m.tool(ag.AS, "exists", path=tex.split(".")[0]):
            m.tool("editor_toolset.toolsets.texture.TextureTools", "import_file", folder_path=TEX_FOLDER,
                   asset_name=tex.split(".")[-1], source_file=str(png))
            m.tool(ag.AS, "save_assets", asset_paths=[tex])
        path, bounds = plate(g, label + "_Plate", FACE_X, y, Z, g.icon_material(tex))
        trig = b.device(bm.TRIGGER, label + "_Trigger", FACE_X + 200.0, y, -400.0)
        b.props(trig, {"visible in Game": False})
        b.tag(trig, tag)
        saved = [path, trig]
        centre = tuple((bounds["min"][k] + bounds["max"][k]) / 2 for k in "xyz")
        dummies = hitbox.place_grid(b, label + "_Hit", (centre[0], centre[1], 100.0), 150.0, 200.0, 180.0, (FACE_X - 5.0, y), [(trig, "Trigger")])
        for dummy in dummies:
            hitbox.hide(m, dummy)
        if light_tag:
            li = b.device(LIGHT, label + "_Light", FACE_X - 200.0, y, 160.0)
            b.tag(li, light_tag)
            for key, value in {"initialState": False, "maximumRadius": 220.0,
                               "lightColor": {"r": light_rgb[0], "g": light_rgb[1], "b": light_rgb[2], "a": 1}}.items():
                try:
                    b.props(li, {key: value})
                except RuntimeError as exc:
                    print(f"  {label}: light {key} refused ({str(exc)[-50:]})")
            saved.append(li)
        for p in saved:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
        print(f"  {name}: placed")
    print(f"placed {len(TILES)} shootable tiles")


if __name__ == "__main__":
    main()
