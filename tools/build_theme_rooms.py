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
CARD_W, CARD_H, CARD_GAP = 320.0, 480.0, 30.0   # the seven National Heroes only
CARD_Z = 730.0                 # above the mod bench and server racks on that wall (they top out at 272)
ROW_Y = -65025.0               # centre of the usable span between the back wall and the corner
HEADER_W, HEADER_Z = 2350.0, 1135.0
# West wall, "faith and roots" (player 2026-10-11: Selassie and the Marley tribute are not National Heroes; beside them
# a cross for Jesus, as Calvary): Selassie, Calvary, the reggae tribute and the lion of Judah, under their own header.
# It replaces the KT7_ArmoryArt_Focal panel (import_armory_art.py --apply brings that back).
ROOTS_Y, ROOTS_Z, ROOTS_GAP = -65025.0, 700.0, 50.0
ROOTS_CARD_W, ROOTS_CALVARY_W = 300.0, 920.0
# The historical Lion of Judah flag (Ethiopian Empire 1897-1974, public domain, Wikimedia Commons; SOURCES.md).
ROOTS_FLAG_W = 600.0
ROOTS_HEADER_W, ROOTS_HEADER_Z = 2000.0, 1150.0

# Build wing ("67 room").
BUILD_RECT = (3584.0, 7168.0, -62976.0, -56320.0)
SPACING_67 = 380.0
SEED = 67


def png_aspect(path):
    w, h = struct.unpack(">II", path.read_bytes()[16:24])
    return w / h


def stem_key(png):
    """File stem plus a content hash, so a re-rendered image becomes a new texture instead of the stale import."""
    import hashlib
    return re.sub(r"[^A-Za-z0-9_]", "_", png.stem) + "_" + hashlib.sha1(png.read_bytes()).hexdigest()[:6]


def texture(b, png):
    name = "T_KT_Theme_" + stem_key(png)
    path = f"{TEX_FOLDER}/{name}.{name}"
    if not b.m.tool(AS, "exists", path=path):
        b.m.tool(TT, "import_file", folder_path=TEX_FOLDER, asset_name=name, source_file=str(png))
        # Sharp up close (player 2026-10-11: "the Nanny tile is blurry"). UEFN validation requires streaming textures,
        # so no NeverStream: full-size top mip (LOD bias 0) in the World group, as the armory icons use.
        b.props(path, {"powerOfTwoMode": "StretchToPowerOfTwo", "neverStream": False, "lODBias": 0,
                       "lODGroup": "TEXTUREGROUP_World", "mipGenSettings": "TMGS_FromTextureGroup"})
    return path


def material(b, png, masked):
    tex = texture(b, png)
    name = "M_KT_Theme_" + stem_key(png)
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
    cards = [ART / "heroes" / f"hero_{k}.png" for k in HERO_ORDER if k != "selassie"]
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


def cross(b, actors):
    """The west wall's faith-and-roots group (the old single cross is replaced by Calvary)."""
    for a in actors:
        if a["label"] == "KT7_ArmoryArt_Focal":
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    h = ART / "heroes"
    row = [(h / "hero_selassie.png", ROOTS_CARD_W), (h / "calvary.png", ROOTS_CALVARY_W),
           (h / "tribute_reggae.png", ROOTS_CARD_W), (h / "lion_of_judah_flag.png", ROOTS_FLAG_W)]
    span = sum(w for _, w in row) + ROOTS_GAP * (len(row) - 1)
    x = WEST_FACE_X + 4.0
    # Facing this wall (towards -X) a viewer has -Y on their right, so the row runs towards -Y.
    y = ROOTS_Y + span / 2
    bottom = ROOTS_Z - (ROOTS_CARD_W / png_aspect(row[0][0])) / 2
    for k, (png, w) in enumerate(row):
        hgt = w / png_aspect(png)
        mount(b, f"{PREFIX}Cross_{k:02d}_{png.stem}", material(b, png, False), x, y - w / 2, bottom + hgt / 2, w, hgt, (1, 0))
        y -= w + ROOTS_GAP
    head = h / "header_roots.png"
    mount(b, f"{PREFIX}Cross_Header", material(b, head, False), x, ROOTS_Y, ROOTS_HEADER_Z, ROOTS_HEADER_W,
          ROOTS_HEADER_W / png_aspect(head), (1, 0))
    print("faith and roots group placed")


def blocked(actors, x, y, z, half, normal, half_h=None):
    """Like build_graffiti.blocked, but graffiti and earlier theme pieces count as obstacles too. half is the
    half-width along the wall, half_h the half-height (defaults to half)."""
    half_h = half if half_h is None else half_h
    for a in actors:
        lab = a["label"]
        if lab.startswith(graf.WALLS) or "Floor" in lab or "Ceil" in lab or lab.startswith("KT_Wing_"):
            continue
        mn, mx = a["bounds"]["min"], a["bounds"]["max"]
        if mx["x"] - mn["x"] > 20000 or mx["y"] - mn["y"] > 20000:
            continue
        if mn["z"] > z + half_h or mx["z"] < z - half_h:
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


def wing_faces(actors, rect):
    """Wall faces on the border of rect (x0, x1, y0, y1) that look into it: (fx, fy, normal, along, lo, hi, top), with the
    span [lo, hi] (along X or Y) clipped to the rect."""
    x0, x1, y0, y1 = rect
    out = []
    for (fx, fy, normal, along, length, top) in graf.faces(actors):
        on_x = abs(fx - x0) < 5 or abs(fx - x1) < 5
        on_y = abs(fy - y0) < 5 or abs(fy - y1) < 5
        ix, iy = fx + normal[0] * 50, fy + normal[1] * 50
        if not (on_x or on_y):
            continue
        if along[0]:
            lo, hi = max(fx - length / 2, x0), min(fx + length / 2, x1)
            if not (y0 <= iy <= y1):
                continue
        else:
            lo, hi = max(fy - length / 2, y0), min(fy + length / 2, y1)
            if not (x0 <= ix <= x1):
                continue
        if hi - lo >= 300:
            out.append((fx, fy, normal, along, lo, hi, min(top, 1536.0)))
    return out


def remember(actors, label, ref, x, y, z, w, h, normal):
    hw = w / 2
    if normal is None:
        mn, mx = {"x": x - hw, "y": y - hw, "z": z - 6}, {"x": x + hw, "y": y + hw, "z": z}
    elif normal[0]:
        mn, mx = {"x": x - 5, "y": y - hw, "z": z - h / 2}, {"x": x + 5, "y": y + hw, "z": z + h / 2}
    else:
        mn, mx = {"x": x - hw, "y": y - 5, "z": z - h / 2}, {"x": x + hw, "y": y + 5, "z": z + h / 2}
    actors.append({"label": label, "actorPath": ref, "bounds": {"min": mn, "max": mx}})


def ceiling_free(actors, x, y, size, margin=150.0, depth=None):
    """Nothing flat on the ceiling within the piece's footprint (size along X, depth along Y) plus margin."""
    d = size if depth is None else depth
    return not any(a["bounds"]["max"]["z"] > 1400 and a["bounds"]["min"]["z"] < 1536
                   and a["bounds"]["max"]["z"] - a["bounds"]["min"]["z"] < 400
                   and not a["label"].startswith(graf.WALLS)
                   and a["bounds"]["min"]["x"] < x + size / 2 + margin and a["bounds"]["max"]["x"] > x - size / 2 - margin
                   and a["bounds"]["min"]["y"] < y + d / 2 + margin and a["bounds"]["max"]["y"] > y - d / 2 - margin
                   for a in actors)


def scatter(b, actors, rect, pieces, tag, sizes, rows, ceil_spacing, seed, weights=None):
    """Random pieces over a room's walls (and ceiling when ceil_spacing): pieces = [(material, width / height)]."""
    x0, x1, y0, y1 = rect
    rng = random.Random(seed)
    placed = 0

    def pick():
        return rng.choices(pieces, weights=weights)[0]

    for (fx, fy, normal, along, lo, hi, top) in wing_faces(actors, rect):
        for _ in range(int((hi - lo) / SPACING_67 * rows + rng.random())):
            mat, aspect = pick()
            size = rng.choice(sizes)                      # the longer side
            w, h = (size, size / aspect) if aspect >= 1 else (size * aspect, size)
            if hi - lo < w + 80 or top < h + 100:
                continue
            c = rng.uniform(lo + w / 2 + 30, hi - w / 2 - 30)
            z = rng.uniform(h / 2 + 40, top - h / 2 - 40)
            x = c if along[0] else fx + normal[0] * 3.0
            y = fy + normal[1] * 3.0 if along[0] else c
            if blocked(actors, x, y, z, w / 2, normal, h / 2):
                continue
            label = f"{PREFIX}{tag}{placed:03d}"
            remember(actors, label, mount(b, label, mat, x, y, z, w, h, normal), x, y, z, w, h, normal)
            placed += 1
    if ceil_spacing:
        for _ in range(int((x1 - x0) * (y1 - y0) / (ceil_spacing * ceil_spacing))):
            mat, aspect = pick()
            size = rng.choice(sizes) * 1.5
            w, h = (size, size / aspect) if aspect >= 1 else (size * aspect, size)
            x, y = rng.uniform(x0 + size / 2 + 80, x1 - size / 2 - 80), rng.uniform(y0 + size / 2 + 80, y1 - size / 2 - 80)
            if not ceiling_free(actors, x, y, size):
                continue
            label = f"{PREFIX}{tag}C{placed:03d}"
            remember(actors, label, mount(b, label, mat, x, y, 1533.0, w, h, None), x, y, 1536.0, max(w, h), 0, None)
            placed += 1
    return placed


def sixty_seven(b, actors):
    """67 everywhere, plus LARP, MOG and the drawn 6-7 characters (player 2026-10-11), all in assets/theme/67."""
    pngs = sorted((ART / "67").glob("*.png"))
    pieces = [(material(b, p, True), png_aspect(p)) for p in pngs]
    # Plain 67s are most of the room; words and characters are rarer so they stand out.
    weights = [3.0 if p.stem.startswith("sixty_seven") else 1.5 for p in pngs]
    n = scatter(b, actors, BUILD_RECT, pieces, "67_", (220.0, 280.0, 340.0, 420.0), 3, 900.0, SEED, weights)
    print("67 room pieces:", n)


EDIT_RECT = (-6656.0, -3072.0, -62976.0, -56320.0)
PIECE_RECT = (-3584.0, 4096.0, -56320.0, -52736.0)
FLAG_W = 640.0
FLAG_ROWS = (1080.0, 560.0)     # two bands of panels; slots that would cover graffiti, signs or devices are skipped


def flags(b, actors):
    """The edit wing is the flag room: 3 x 2 flag panels in alphabetical order, in two bands around its walls, then
    across its ceiling. A panel never covers graffiti (it stays, player 2026-10-11), a sign or a device."""
    pngs = sorted((ART / "flags").glob("flags_*.png"))
    todo = list(pngs)
    for z in FLAG_ROWS:
        for (fx, fy, normal, along, lo, hi, top) in wing_faces(actors, EDIT_RECT):
            c = lo + FLAG_W / 2 + 40
            while todo and c + FLAG_W / 2 + 40 <= hi:
                png = todo[0]
                h = FLAG_W / png_aspect(png)
                x = c if along[0] else fx + normal[0] * 3.0
                y = fy + normal[1] * 3.0 if along[0] else c
                if blocked(actors, x, y, z, FLAG_W / 2 + 20, normal, h / 2 + 20):
                    c += 100.0
                    continue
                label = f"{PREFIX}Flags_{png.stem}"
                remember(actors, label, mount(b, label, material(b, png, False), x, y, z, FLAG_W, h, normal),
                         x, y, z, FLAG_W, h, normal)
                todo.pop(0)
                c += FLAG_W + 60.0
    x0, x1, y0, y1 = EDIT_RECT
    gx, gy = x0 + 450.0, y0 + 450.0
    while todo and gy < y1 - 400:
        png = todo[0]
        if ceiling_free(actors, gx, gy, FLAG_W, 30.0, FLAG_W / png_aspect(png)):
            label = f"{PREFIX}Flags_{png.stem}"
            mount(b, label, material(b, png, False), gx, gy, 1533.0, FLAG_W, FLAG_W / png_aspect(png), None)
            remember(actors, label, None, gx, gy, 1536.0, FLAG_W, 0, None)
            todo.pop(0)
            gx += FLAG_W + 150
        else:
            gx += 200.0
        if gx > x1 - 400:
            gx, gy = x0 + 450.0, gy + 300.0
    print("flag panels placed:", len(pngs) - len(todo), "not placed:", [p.stem for p in todo])


def movement(b, actors):
    """Piece-control (movement) wing: Fortnite's own characters as graffiti. Only textures UEFN validation has accepted
    on this map are used (the Fortnite loading-screen art is rejected as a disallowed reference)."""
    base = "/Hera/Sets/PicketFence/Textures/Graffiti/Graffiti/"
    names = ("Peely", "FishStick", "BobHead", "Bear", "Ghost", "Duck", "Burger", "Slurp")
    pieces = [(graf.material(b, f"{base}T_Graffiti_{n}_A.T_Graffiti_{n}_A"), 1.0) for n in names]
    n = scatter(b, actors, PIECE_RECT, pieces, "Move_", (300.0, 380.0, 460.0), 2, 1100.0, 7)
    print("movement room pieces:", n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("heroes", "cross", "67", "flags", "movement"))
    args = ap.parse_args()
    b = bm.Builder()
    actors = b.m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    want = {args.only} if args.only else {"heroes", "cross", "67", "flags", "movement"}
    tags = {"heroes": "Hero_", "cross": "Cross", "67": "67_", "flags": "Flags_", "movement": "Move_"}
    for a in actors:
        if a["label"].startswith(PREFIX) and any(a["label"].startswith(PREFIX + tags[w]) for w in want):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    actors = [a for a in actors if not (a["label"].startswith(PREFIX) and any(a["label"].startswith(PREFIX + tags[w]) for w in want))]
    if "heroes" in want:
        heroes(b, actors)
    if "cross" in want:
        cross(b, actors)
    if "67" in want:
        sixty_seven(b, actors)
    if "flags" in want:
        flags(b, actors)
    if "movement" in want:
        movement(b, actors)
    found = json.loads(b.m.tool(AS, "find_assets", name="_KT_Theme_") or "[]") if isinstance(b.m.tool(AS, "find_assets", name="_KT_Theme_"), str) \
        else (b.m.tool(AS, "find_assets", name="_KT_Theme_") or [])
    b.m.tool(AS, "save_assets", asset_paths=[p for p in found if "_KT_Theme_" in p])


if __name__ == "__main__":
    main()
