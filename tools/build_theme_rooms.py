"""Mount the theme-room art from tools/render_theme_art.py (KT23_Theme_*).

    python tools/build_theme_rooms.py                  # everything
    python tools/build_theme_rooms.py --only heroes    # heroes | cross | 67

Player 2026-10-11:
  * heroes: Jamaica's National Heroes, Haile Selassie and a Rasta tribute panel on the armory's east wall (where the old
    KT7_ArmoryArt_Gallery panel hung; it is removed, `import_armory_art.py --apply` would bring it back), under a header.
  * cross: on the armory's west wall, above the KT7_ArmoryArt_Focal panel.
  * 67: the build wing is the "67 room": 67 all over its walls and ceiling. Graffiti (KT19_Graf_) stays; 67 pieces keep
    clear of it, of signs and of devices.
Every piece is an unlit plane with no collision that does not light the room. Only KT23_Theme_* actors are replaced.
"""
import argparse
import json
import pathlib
import random
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_graffiti as graf  # noqa: E402

PREFIX = "KT23_Theme_"
ART = bm.ROOT / "assets" / "theme"
TEX_FOLDER = bm.MODULE + "/KT_Theme"
MATERIALS = bm.MODULE + "/KT_Materials"
MT = "editor_toolset.toolsets.material.MaterialTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
TT = "editor_toolset.toolsets.texture.TextureTools"
PLANE = "/Engine/BasicShapes/Plane.Plane"

# Armory (KT_Wing_Armory x -3072..3584, y -66560..-62976, ceiling 1536).
EAST_FACE_X = 3584.0           # KT_Wall_Hub_2's inner face; pieces face -X into the room
WEST_FACE_X = -3072.0          # KT_Wall_Hub_1's inner face; pieces face +X
HERO_ORDER = ["nanny", "sharpe", "bogle", "gordon", "garvey", "bustamante", "manley", "selassie"]
CARD_W, CARD_H, CARD_GAP = 250.0, 375.0, 22.0
CARD_Z = 715.0                 # above the mod bench and server racks on that wall (they top out at 272)
ROW_Y = -65025.0               # centre of the usable span between the back wall and the corner
HEADER_W, HEADER_Z = 2200.0, 1110.0
CROSS_Y, CROSS_Z, CROSS_H = -64768.0, 1335.0, 330.0   # above the Focal panel (top 1129), below the ceiling

# Build wing ("67 room").
BUILD_RECT = (3584.0, 7168.0, -62976.0, -56320.0)
SPACING_67 = 380.0
SEED = 67


def png_aspect(path):
    w, h = struct.unpack(">II", path.read_bytes()[16:24])
    return w / h


def texture(b, png):
    name = "T_KT_Theme_" + re.sub(r"[^A-Za-z0-9_]", "_", png.stem)
    path = f"{TEX_FOLDER}/{name}.{name}"
    if not b.m.tool(AS, "exists", path=path):
        b.m.tool(TT, "import_file", folder_path=TEX_FOLDER, asset_name=name, source_file=str(png))
        b.props(path, {"powerOfTwoMode": "StretchToPowerOfTwo", "neverStream": False, "mipGenSettings": "TMGS_FromTextureGroup"})
    return path


def material(b, png, masked):
    tex = texture(b, png)
    name = "M_KT_Theme_" + re.sub(r"[^A-Za-z0-9_]", "_", png.stem)
    path = f"{MATERIALS}/{name}.{name}"
    if b.m.tool(AS, "exists", path=path):
        return path
    mat = b.m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=name)
    s = b.m.tool(MT, "add_expression", material_or_function=mat,
                 expression_class={"refPath": "/Script/Engine.MaterialExpressionTextureSample"}, x=-300, y=0)
    b.props(s["refPath"], {"texture": {"refPath": tex}})
    b.m.tool(MT, "connect_to_output", expression=s, output_name="RGB", material_property="MP_EmissiveColor")
    if masked:
        b.m.tool(MT, "connect_to_output", expression=s, output_name="A", material_property="MP_OpacityMask")
        b.props(path, {"blendMode": "BLEND_Masked"})
    b.props(path, {"shadingModel": "MSM_Unlit", "twoSided": True})
    b.m.tool(MT, "recompile", material_or_function=mat)
    return path


def mount(b, label, mat, x, y, z, w, h, normal):
    """A plane w x h (cm) centred at (x, y, z), its picture facing `normal`; normal None = on a ceiling, facing down."""
    if normal is None:
        # Roll 180 shows the front from below; yaw 90 reads upright for someone walking in facing +X (checked in a capture).
        pose = bm.xform(x, y, z, w / 100.0, h / 100.0, 1.0, yaw=90.0)
        pose["rotation"]["roll"] = 180.0
    else:
        pose = bm.xform(x, y, z, w / 100.0, h / 100.0, 1.0, yaw=graf.yaw_for(normal))
        pose["rotation"]["roll"] = 90.0
    ref = b.labelled(b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=label, xform=pose)["refPath"], label)
    for c in b.m.tool(bm.ACTOR, "get_components", actor={"refPath": ref}) or []:
        if "StaticMeshComponent0" in c["refPath"]:
            b.props(c["refPath"], {"overrideMaterials": [{"refPath": mat}], "castShadow": False,
                                   "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
            for key in ("bAffectDynamicIndirectLighting", "bAffectDistanceFieldLighting"):
                try:
                    b.props(c["refPath"], {key: False})
                except RuntimeError:
                    pass
    b.m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
    return ref


def heroes(b, actors):
    for a in actors:
        if a["label"] == "KT7_ArmoryArt_Gallery":
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    cards = [ART / "heroes" / f"hero_{k}.png" for k in HERO_ORDER] + [ART / "heroes" / "tribute_rasta.png"]
    n = len(cards)
    span = n * CARD_W + (n - 1) * CARD_GAP
    x = EAST_FACE_X - 4.0
    # UE is left-handed: a viewer facing +X (towards this wall) has +Y on their right, so the row runs towards +Y.
    for k, png in enumerate(cards):
        y = ROW_Y - span / 2 + CARD_W / 2 + k * (CARD_W + CARD_GAP)
        mount(b, f"{PREFIX}Hero_{k:02d}_{png.stem}", material(b, png, False), x, y, CARD_Z, CARD_W, CARD_H, (-1, 0))
    head = ART / "heroes" / "header.png"
    mount(b, f"{PREFIX}Hero_Header", material(b, head, False), x, ROW_Y, HEADER_Z, HEADER_W, HEADER_W / png_aspect(head), (-1, 0))
    print("heroes:", n, "cards + header")


def cross(b):
    png = ART / "cross.png"
    a = png_aspect(png)
    mount(b, f"{PREFIX}Cross", material(b, png, True), WEST_FACE_X + 4.0, CROSS_Y, CROSS_Z, CROSS_H * a, CROSS_H, (1, 0))
    print("cross placed")


def blocked(actors, x, y, z, half, normal):
    """Like build_graffiti.blocked, but graffiti and earlier 67s count as obstacles too."""
    for a in actors:
        lab = a["label"]
        if lab.startswith(graf.WALLS) or "Floor" in lab or "Ceil" in lab or lab.startswith("KT_Wing_"):
            continue
        mn, mx = a["bounds"]["min"], a["bounds"]["max"]
        if mx["x"] - mn["x"] > 20000 or mx["y"] - mn["y"] > 20000:
            continue
        if mn["z"] > z + half or mx["z"] < z - half:
            continue
        if normal[0]:
            front = (x - 20 * normal[0], x + 250 * normal[0])
            if max(mn["x"], min(front)) > min(mx["x"], max(front)) or mn["y"] > y + half or mx["y"] < y - half:
                continue
        else:
            front = (y - 20 * normal[1], y + 250 * normal[1])
            if max(mn["y"], min(front)) > min(mx["y"], max(front)) or mn["x"] > x + half or mx["x"] < x - half:
                continue
        return True
    return False


def sixty_seven(b, actors):
    x0, x1, y0, y1 = BUILD_RECT
    pngs = sorted((ART / "67").glob("*.png"))
    mats = [material(b, p, True) for p in pngs]
    rng = random.Random(SEED)
    placed = 0
    for (fx, fy, normal, along, length, top) in graf.faces(actors):
        # Only faces on the wing's border that look into it.
        on_x = abs(fx - x0) < 5 or abs(fx - x1) < 5
        on_y = abs(fy - y0) < 5 or abs(fy - y1) < 5
        ix, iy = fx + normal[0] * 50, fy + normal[1] * 50
        if not (on_x or on_y):
            continue
        # The slab may run past the wing: clip its span to the wing.
        if along[0]:
            lo, hi = max(fx - length / 2, x0), min(fx + length / 2, x1)
            if not (y0 <= iy <= y1):
                continue
        else:
            lo, hi = max(fy - length / 2, y0), min(fy + length / 2, y1)
            if not (x0 <= ix <= x1):
                continue
        if hi - lo < 300:
            continue
        count = int((hi - lo) / SPACING_67 * 3 + rng.random())      # three rows' worth along the face
        for _ in range(count):
            size = rng.choice((220.0, 280.0, 340.0, 420.0))
            c = rng.uniform(lo + size / 2 + 30, hi - size / 2 - 30)
            z = rng.uniform(size / 2 + 40, min(top, 1536.0) - size / 2 - 40)
            x = c if along[0] else fx + normal[0] * 3.0
            y = fy + normal[1] * 3.0 if along[0] else c
            if blocked(actors, x, y, z, size / 2, normal):
                continue
            k = rng.randrange(len(pngs))
            label = f"{PREFIX}67_{placed:03d}"
            ref = mount(b, label, mats[k], x, y, z, size, size, normal)
            mn = {"x": x - size / 2, "y": y - size / 2, "z": z - size / 2}
            mx = {"x": x + size / 2, "y": y + size / 2, "z": z + size / 2}
            actors.append({"label": label, "actorPath": ref, "bounds": {"min": mn, "max": mx}})
            placed += 1
    # Ceiling: big ones looking down.
    for _ in range(int((x1 - x0) * (y1 - y0) / (900.0 * 900.0))):
        size = rng.choice((400.0, 520.0, 650.0))
        x, y = rng.uniform(x0 + size / 2 + 80, x1 - size / 2 - 80), rng.uniform(y0 + size / 2 + 80, y1 - size / 2 - 80)
        # Keep clear of other ceiling pieces (graffiti included, or the two z-fight) and of anything hanging down.
        if any(a["bounds"]["max"]["z"] > 1400 and a["bounds"]["min"]["z"] < 1536 and a["bounds"]["max"]["z"] - a["bounds"]["min"]["z"] < 400
               and not a["label"].startswith(graf.WALLS)
               and a["bounds"]["min"]["x"] < x + size / 2 + 150 and a["bounds"]["max"]["x"] > x - size / 2 - 150
               and a["bounds"]["min"]["y"] < y + size / 2 + 150 and a["bounds"]["max"]["y"] > y - size / 2 - 150 for a in actors):
            continue
        label = f"{PREFIX}67_C{placed:03d}"
        ref = mount(b, label, mats[rng.randrange(len(mats))], x, y, 1536.0 - 3.0, size, size, None)
        actors.append({"label": label, "actorPath": ref, "bounds": {"min": {"x": x - size / 2, "y": y - size / 2, "z": 1530},
                                                                   "max": {"x": x + size / 2, "y": y + size / 2, "z": 1536}}})
        placed += 1
    print("67s placed:", placed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("heroes", "cross", "67"))
    args = ap.parse_args()
    b = bm.Builder()
    actors = b.m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    want = {args.only} if args.only else {"heroes", "cross", "67"}
    tags = {"heroes": "Hero_", "cross": "Cross", "67": "67_"}
    for a in actors:
        if a["label"].startswith(PREFIX) and any(a["label"].startswith(PREFIX + tags[w]) for w in want):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    actors = [a for a in actors if not (a["label"].startswith(PREFIX) and any(a["label"].startswith(PREFIX + tags[w]) for w in want))]
    if "heroes" in want:
        heroes(b, actors)
    if "cross" in want:
        cross(b)
    if "67" in want:
        sixty_seven(b, actors)
    found = json.loads(b.m.tool(AS, "find_assets", name="_KT_Theme_") or "[]") if isinstance(b.m.tool(AS, "find_assets", name="_KT_Theme_"), str) \
        else (b.m.tool(AS, "find_assets", name="_KT_Theme_") or [])
    b.m.tool(AS, "save_assets", asset_paths=[p for p in found if "_KT_Theme_" in p])


if __name__ == "__main__":
    main()
