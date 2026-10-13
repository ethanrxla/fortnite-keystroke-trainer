"""A shootable plate for every drill, in the wing it belongs to, and a rift out of every drill room (KT30_Drill_*).

    python tools/build_drill_plates.py --dry-run     # print where each plate and rift goes
    python tools/build_drill_plates.py               # (re)place them; removes only KT30_Drill_* actors
    python tools/install_rift_router.py              # then route the room exits (DRILL_RIFTS there)

Player 2026-10-13: "there should be plates and rifts/ teleporters (in the drill room) for all the drills, including piece
control, sky boxing, etc, currently im not sure how to get there, we have rooms so you can put the signs in the rooms
that make the most sense", and hit boxes on the section signs (MOVEMENT, BOXES, ...).

* Lane drills (KT_Lane_<code>): the plate's dummies fire a hidden trigger beside the lane device tagged
  kt_drill_start_tag; DrillDevice.verse (OnStartShot) runs one set and brings the player back to where they shot from.
* Areas with their own start (Sky Box, Rebox Arena, Piece Lab): the dummies teleport the shooter to that start.
* Every lane room gets a visible exit rift at its back wall, routed by the rift router to its wing's arrival.
* The hub section signs (KT3_Section_*_Sign) get a dummy grid over their art; a hit puts the shooter on the section pad.
Plates: a Bitcount Ink face texture on a plane 45 cm off the wall, dummies between plate and wall (tools/hitbox.py).
Each plate takes the first spot along its wall where nothing but wall and graffiti stands within 1.5 m of the face:
RXLA logos, signs, art and other plates are never covered.
"""
import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402
import hitbox  # noqa: E402
from build_sign_shots import facing  # noqa: E402

PREFIX = "KT30_Drill_"
TEX_FOLDER = bm.MODULE + "/KT_UI"
FONT = bm.ROOT / "assets" / "fonts" / "bitcount-ink"
SIZE, GAP, Z = 230.0, 70.0, 300.0         # plate edge, space between plates, plate centre height (cm)
OFF = 45.0                                # plate off the wall face
DUMMY_OFF = 22.0                          # dummies between plate and wall
# Wing walls (inner face): (axis, face coordinate, along-min, along-max, normal into the room)
WALLS = {
    "build_north": ("y", -56320.0, 4096.0, 7168.0, (0.0, -1.0)),
    "piece_west": ("x", -3584.0, -56320.0, -52736.0, (1.0, 0.0)),
    "piece_east": ("x", 4096.0, -55808.0, -52736.0, (-1.0, 0.0)),
    "edit_south": ("y", -62976.0, -6656.0, -3072.0, (0.0, 1.0)),
    "edit_north": ("y", -56320.0, -6656.0, -4096.0, (0.0, -1.0)),
    "edit_west": ("x", -6656.0, -62976.0, -56320.0, (1.0, 0.0)),
    "armory_west": ("x", -3072.0, -66560.0, -63488.0, (1.0, 0.0)),
    "armory_south": ("y", -66560.0, -3072.0, 3584.0, (0.0, 1.0)),
}
WING_ARRIVAL = {"B": "KT3_03_Dest", "P": "KT3_04_Dest", "E": "KT3_05_Dest", "W": "KT3_06_Dest"}
# code or area, plate words, rgb (linear), walls in order of preference, lane code or teleporter to arrive at
PLATES = [
    ("B2", "FLOOR", (0.05, 0.16, 0.30), ["build_north"], "lane"),
    ("B3", "RAMP", (0.05, 0.16, 0.30), ["build_north"], "lane"),
    ("B5", "PIECE SWITCH", (0.05, 0.16, 0.30), ["build_north"], "lane"),
    ("P2", "RAMP RUSH", (0.20, 0.06, 0.30), ["piece_west"], "lane"),
    ("P5", "TUNNEL", (0.20, 0.06, 0.30), ["piece_west"], "lane"),
    ("P6", "90s", (0.20, 0.06, 0.30), ["piece_west"], "lane"),
    ("SKY", "SKY BOX", (0.03, 0.22, 0.30), ["piece_west", "piece_east"], "KT18_Sky_Rift_Start"),
    ("P4", "BOX UP", (0.30, 0.12, 0.02), ["piece_east"], "lane"),
    ("P7", "TUNNEL WINDOW", (0.30, 0.12, 0.02), ["piece_east"], "lane"),
    ("P8", "RE-BOX", (0.30, 0.12, 0.02), ["piece_east"], "lane"),
    ("REBOX", "PIECE CONTROL", (0.30, 0.04, 0.04), ["piece_east", "piece_west"], "KT14_Rebox_Rift_Start"),
    ("E2", "WINDOW PEEK", (0.04, 0.24, 0.10), ["edit_south", "edit_north", "edit_west"], "lane"),
    ("E4", "HALF WALL", (0.04, 0.24, 0.10), ["edit_south", "edit_north", "edit_west"], "lane"),
    ("E5", "EDIT RESET", (0.04, 0.24, 0.10), ["edit_south", "edit_north", "edit_west"], "lane"),
    ("E7", "EDIT PEEK", (0.04, 0.24, 0.10), ["edit_south", "edit_north", "edit_west"], "lane"),
    ("LAB", "PIECE LAB", (0.10, 0.20, 0.04), ["edit_south", "edit_north", "edit_west"], "KT12_Gate_LabIn"),
    ("W1", "GUN SWAP", (0.28, 0.20, 0.02), ["armory_west", "armory_south"], "lane"),
    ("W2", "PICKAXE SWAP", (0.28, 0.20, 0.02), ["armory_west", "armory_south"], "lane"),
    ("W3", "BUILD SWAP", (0.28, 0.20, 0.02), ["armory_west", "armory_south"], "lane"),
]
SECTION_SIGNS = ["build", "movement", "boxes", "editing"]
IGNORE = ("KT_Wall_", "KT_Wing_", "KT_Hub", "KT_Ceil_", "KT19_", "KT23_Theme_Move_", PREFIX)


def plate_texture(code, words, rgb):
    from PIL import Image, ImageDraw, ImageFont
    out = bm.ROOT / "assets" / "ui" / "drill_plates" / f"T_KT_DrillPlate3_{code}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Dark: the plate is unlit emissive and the dim wings are auto-exposed, so mid colours washed out to pastel.
    srgb = tuple(int(255 * min(1.0, (c * 0.25) ** (1 / 2.2))) for c in rgb)
    im = Image.new("RGBA", (512, 512), srgb + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle((10, 10, 501, 501), outline=(255, 255, 255, 200), width=10)
    font_file = str(next(FONT.glob("*.ttf")))
    lines = words.split() if len(words) > 9 else [words]
    size = 140
    while size > 36:
        f = ImageFont.truetype(font_file, size)
        if max(d.textlength(l, font=f) for l in lines) <= 440 and size * 1.1 * len(lines) <= 330:
            break
        size -= 6
    top = 230 - size * 1.1 * (len(lines) - 1) / 2
    for k, l in enumerate(lines):
        d.text((256, top + k * size * 1.1), l, font=f, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=5, stroke_fill=(0, 0, 0, 220))
    small = ImageFont.truetype(font_file, 44)
    d.text((256, 440), "SHOOT TO GO", font=small, fill=(235, 240, 245, 255), anchor="mm")
    im.save(out)
    asset = f"T_KT_DrillPlate3_{code}"
    return out, f"{TEX_FOLDER}/{asset}.{asset}"


def obstacles(acts):
    out = []
    for a in acts:
        b = a.get("bounds")
        if not b or a["label"].startswith(IGNORE) or "Floor" in a["label"]:
            continue
        size = [b["max"][k] - b["min"][k] for k in "xyz"]
        if all(abs(v - 1000.0) < 2 for v in size) or size[0] > 8000 or size[1] > 8000:
            continue
        out.append(b)
    return out


def clear(obs, wall, c, half):
    axis, face, _, _, n = WALLS[wall]
    for b in obs:
        if b["max"]["z"] < Z - half - 30 or b["min"]["z"] > Z + half + 30:
            continue
        a_lo, a_hi = (b["min"]["x"], b["max"]["x"]) if axis == "y" else (b["min"]["y"], b["max"]["y"])
        if a_hi < c - half - 30 or a_lo > c + half + 30:
            continue
        d_lo, d_hi = (b["min"]["y"], b["max"]["y"]) if axis == "y" else (b["min"]["x"], b["max"]["x"])
        k = 1 if axis == "y" else 0
        near, far = face, face + 150.0 * n[k]
        if d_hi < min(near, far) or d_lo > max(near, far):
            continue
        return False
    return True


def plan(acts):
    obs = obstacles(acts)
    taken = []
    out = []
    half = SIZE / 2
    for code, words, rgb, walls, dest in PLATES:
        spot = None
        for wall in walls:
            axis, face, lo, hi, n = WALLS[wall]
            c = lo + 300.0
            while c + half < hi - 300.0:
                if clear(obs, wall, c, half) and all(not (w == wall and abs(c - t) < SIZE + GAP) for w, t in taken):
                    spot = (wall, c)
                    break
                c += 25.0
            if spot:
                break
        if not spot:
            print(f"  {code}: no clear spot on {walls}")
            continue
        taken.append(spot)
        wall, c = spot
        axis, face, _, _, n = WALLS[wall]
        px, py = (c, face + n[1] * OFF) if axis == "y" else (face + n[0] * OFF, c)
        dx, dy = (c, face + n[1] * DUMMY_OFF) if axis == "y" else (face + n[0] * DUMMY_OFF, c)
        out.append(dict(code=code, words=words, rgb=rgb, dest=dest, x=px, y=py, z=Z, n=n, dx=dx, dy=dy,
                        plane_yaw=math.degrees(math.atan2(-n[0], n[1])) % 360,
                        dummy_yaw=math.degrees(math.atan2(n[1], n[0])) % 360))
    return out


def floor_top(acts, x, y, below):
    """Top of the highest floor-like actor under (x, y) that is not above `below`."""
    best = None
    for a in acts:
        b = a.get("bounds")
        if not b or not (b["min"]["x"] < x < b["max"]["x"] and b["min"]["y"] < y < b["max"]["y"]):
            continue
        top = b["max"]["z"]
        if top <= below and b["max"]["z"] - b["min"]["z"] < 600 and (best is None or top > best):
            best = top
    return best if best is not None else 0.0


def exits(acts, by):
    """One exit rift per lane room: on the start ledge 2 m from its back edge, in line with the first track (the strip
    behind the ledge is a level lower and holds the lane's containers and sign)."""
    out = []
    for code, *_rest, dest in PLATES:
        if dest != "lane":
            continue
        lane = next(a for a in acts if a["label"] == f"KT_Lane_{code}")
        lb = lane["bounds"]
        lx, ly, lz = [(lb["min"][k] + lb["max"][k]) / 2 for k in "xyz"]
        ledge = by.get(f"KT_Ledge_{code}")
        if ledge:
            x, z = ledge["bounds"]["min"]["x"] + 200.0, ledge["bounds"]["max"]["z"]
        else:
            x = lx - 1000.0
            z = floor_top(acts, x, ly, lz + 10.0)
        out.append(dict(code=code, x=x, y=ly, z=z, lane=(lx, ly, lz), arrival=WING_ARRIVAL[code[0]]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    g = ag.Grid()
    b, m = g.b, g.m
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    by = {a["label"]: a for a in acts}
    plates = plan(acts)
    rifts = exits(acts, by)
    for p in plates:
        print(f"{p['code']:6} {p['words']:14} at ({p['x']:.0f}, {p['y']:.0f}) yaw {p['plane_yaw']:.0f} -> {p['dest']}")
    for r in rifts:
        print(f"exit {r['code']} at ({r['x']:.0f}, {r['y']:.0f}, {r['z']:.0f}) -> {r['arrival']}")
    if args.dry_run:
        return
    for a in acts:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    starts = {}
    for r in rifts:
        lx, ly, lz = r["lane"]
        trig = b.device(bm.TRIGGER, f"{PREFIX}{r['code']}_Start", lx, ly, lz - 450.0)
        b.props(trig, {"visible in Game": False})
        b.tag(trig, "kt_drill_start_tag")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": trig})
        starts[r["code"]] = trig
        t = b.device(bm.TELEPORTER, f"{PREFIX}{r['code']}_Exit", r["x"], r["y"], r["z"])
        b.props(t, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
                    "teleporter Rift Visible": True, "enabledDuringPhase": "Always"})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": t})
    for p in plates:
        label = f"{PREFIX}{p['code']}"
        png, tex = plate_texture(p["code"], p["words"], p["rgb"])
        if not m.tool(ag.AS, "exists", path=tex.split(".")[0]):
            m.tool("editor_toolset.toolsets.texture.TextureTools", "import_file", folder_path=TEX_FOLDER,
                   asset_name=tex.split(".")[-1], source_file=str(png))
            m.tool(ag.AS, "save_assets", asset_paths=[tex])
        plate = g.plane(label + "_Plate", p["x"], p["y"], p["z"], SIZE, p["plane_yaw"], g.icon_material(tex))
        m.tool(bm.SCENE, "save_actor", actor={"refPath": plate})
        target = (starts[p["code"]], "Trigger") if p["dest"] == "lane" else (by[p["dest"]]["actorPath"], "Teleport")
        hitbox.place_grid(b, label + "_Hit", (p["x"], p["y"], p["z"]), SIZE, SIZE, p["dummy_yaw"], (p["dx"], p["dy"]),
                          [target])
    # Section signs: a dummy grid over the art, a hit puts the shooter on the section pad.
    for s in SECTION_SIGNS:
        sign, art, pad = (by.get(f"KT3_Section_{s}_Sign"), by.get(f"KT20_SignArt_KT3_Section_{s}_Sign"),
                          by.get(f"KT3_Section_{s}_Pad"))
        if not (sign and art and pad):
            print(f"  section {s}: sign, art or pad missing")
            continue
        n, w, h, yaw = facing(art, sign)
        ab, sb = art["bounds"], sign["bounds"]
        cx, cy, cz = [(ab["min"][k] + ab["max"][k]) / 2 for k in "xyz"]
        sx, sy = [(sb["min"][k] + sb["max"][k]) / 2 for k in "xy"]
        pb = pad["bounds"]
        px, py = [(pb["min"][k] + pb["max"][k]) / 2 for k in "xy"]
        arrive = b.device(bm.TELEPORTER, f"{PREFIX}Section_{s}_Arrive", px, py, 15.0)
        b.props(arrive, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
                         "teleporter Rift Visible": False, "maintain Relative Position": False,
                         "conserve Momentum": False, "enabledDuringPhase": "Always"})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": arrive})
        # Dummies just behind the art, between it and the billboard.
        hitbox.place_grid(b, f"{PREFIX}Section_{s}_Hit", (cx, cy, cz), w, h, yaw, ((cx + sx) / 2, (cy + sy) / 2),
                          [(arrive, "Teleport")], cell_max=270.0)
    print(f"placed {len(plates)} plates, {len(rifts)} exit rifts; now run tools/install_rift_router.py")


if __name__ == "__main__":
    main()
