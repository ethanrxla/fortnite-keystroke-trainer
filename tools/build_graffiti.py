"""Permanent graffiti on the map's walls, from Fortnite's own environment-set graffiti textures (KT19_Graf_*).

    python tools/build_graffiti.py --list          # the textures used
    python tools/build_graffiti.py --test          # six pieces on the Rebox Arena's west wall, to check look/validation
    python tools/build_graffiti.py                 # the whole map

Player 2026-10-10: "we want permanent graffiti all over the walls". Sprays as cosmetics are not placeable, but the
environment sets carry graffiti, tags and murals (PicketFence, SunStroke, AlleyTown, Beach_Palm). Each piece is a plane
with a lit masked material (texture colour as base colour, its alpha as the mask), 3 cm off a wall face, never over a
sign, device or prop near that face. Walls used: hub and wing enclosure (KT_Wall_*), Fight Lab (KT7_Lab_Wall_*), Rebox
Arena (KT14_Rebox_Wall_*). Seeded, so a rerun puts the same pieces in the same places.
"""
import argparse
import json
import random
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT19_Graf_"
MT = "editor_toolset.toolsets.material.MaterialTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
MATERIALS = bm.MODULE + "/KT_Materials"
PLANE = "/Engine/BasicShapes/Plane.Plane"
SETS = ("/Hera/Sets/PicketFence/Textures/Graffiti/", "/Hermes/Sets/AlleyTown/Textures/Murals/",
        "/Hera/Foliage/Trees/Beach_Palm/Textures/Graffiti/")   # SunStroke murals fail UEFN validation (disallowed)
WALLS = ("KT_Wall_", "KT8_Range_Wall_")      # hub, wings, lane rooms (player 2026-10-11) and the gun range
WEB = bm.ROOT / "assets" / "graffiti" / "openclipart"     # CC0 pieces, imported as textures (SOURCES.md)
TEX_FOLDER = bm.MODULE + "/KT_Graffiti"
TT = "editor_toolset.toolsets.texture.TextureTools"
# Never over the armory gun wall: its face on the back wall (y -66560, facing +Y), x span with a margin.
KEEP_CLEAR = [{"normal": (0, 1), "y": -66560.0, "x0": -600.0, "x1": 1100.0}]
SPACING = 900.0           # one piece per this many cm of wall face, on average (player: "repeat them throughout the walls")
SEED = 20261011
# Textures UEFN validation rejects (disallowed references), found on push 2026-10-11.
DISALLOWED = ("T_graffiti_003", "T_Graffiti_Fish_C")
DONE = set()


def textures(m):
    out = set()
    for q in ("Graffiti", "Mural"):
        r = m.tool(AS, "find_assets", name=q)
        for x in (json.loads(r) if isinstance(r, str) else r) or []:
            if any(s in x for s in SETS) and re.search(r"/T_[^/]*$", x.split(".")[0]) and \
                    not re.search(r"_(N|M|R|ORM|MRA|AO|Mask|Normal|Rough|Spec|E)$", x.split(".")[-1]) and                     x.split(".")[-1] not in DISALLOWED:
                out.add(x)
    return sorted(out)


def import_web(b):
    """The Openclipart PNGs as textures (once), with each image's width / height for the plane's aspect."""
    import struct
    out = {}
    for f in sorted(WEB.glob("*.png")):
        name = "T_KT_Graf_" + re.sub(r"[^A-Za-z0-9_]", "_", f.stem)
        path = f"{TEX_FOLDER}/{name}.{name}"
        if not b.m.tool(AS, "exists", path=path):
            b.m.tool(TT, "import_file", folder_path=TEX_FOLDER, asset_name=name, source_file=str(f))
            b.props(path, {"powerOfTwoMode": "StretchToPowerOfTwo", "neverStream": False, "mipGenSettings": "TMGS_FromTextureGroup"})
        w, h = struct.unpack(">II", f.read_bytes()[16:24])
        out[path] = w / h
    return out


def material(b, tex):
    name = "M_KT_Graf_" + re.sub(r"[^A-Za-z0-9_]", "_", tex.split(".")[-1])[:44]
    path = f"{MATERIALS}/{name}.{name}"
    if b.m.tool(AS, "exists", path=path):
        if path not in DONE:
            b.props(path, {"blendMode": "BLEND_Masked", "twoSided": True})
            b.m.tool(MT, "recompile", material_or_function={"refPath": path})
            DONE.add(path)
        return path
    mat = b.m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=name)
    DONE.add(path)
    s = b.m.tool(MT, "add_expression", material_or_function=mat,
                 expression_class={"refPath": "/Script/Engine.MaterialExpressionTextureSample"}, x=-300, y=0)
    b.props(s["refPath"], {"texture": {"refPath": tex}})
    b.m.tool(MT, "connect_to_output", expression=s, output_name="RGB", material_property="MP_BaseColor")
    b.m.tool(MT, "connect_to_output", expression=s, output_name="A", material_property="MP_OpacityMask")
    b.props(path, {"blendMode": "BLEND_Masked", "twoSided": True})     # visible whichever way the plane faces
    b.m.tool(MT, "recompile", material_or_function=mat)
    return path


def faces(actors):
    """Wall slabs -> their two long vertical faces: (x, y, normal, along, length, top)."""
    out = []
    for a in actors:
        if not a["label"].startswith(WALLS):
            continue
        mn, mx = a["bounds"]["min"], a["bounds"]["max"]
        dx, dy, top = mx["x"] - mn["x"], mx["y"] - mn["y"], mx["z"]
        if top < 300 or max(dx, dy) < 600:
            continue
        if dx >= dy:     # runs along X: faces look -Y and +Y
            cx = (mn["x"] + mx["x"]) / 2
            out += [(cx, mn["y"], (0, -1), (1, 0), dx, top), (cx, mx["y"], (0, 1), (1, 0), dx, top)]
        else:
            cy = (mn["y"] + mx["y"]) / 2
            out += [(mn["x"], cy, (-1, 0), (0, 1), dy, top), (mx["x"], cy, (1, 0), (0, 1), dy, top)]
    return out


def blocked(actors, x, y, z, half, normal):
    """Anything that is not a wall, within 2.5 m in front of the face and overlapping the piece's square."""
    for k in KEEP_CLEAR:
        if normal == k["normal"] and abs(y - k["y"]) < 50 and x + half > k["x0"] and x - half < k["x1"]:
            return True
    for a in actors:
        if a["label"].startswith(WALLS + (PREFIX,)) or "Floor" in a["label"] or "Ceil" in a["label"]:
            continue
        mn, mx = a["bounds"]["min"], a["bounds"]["max"]
        if mx["x"] - mn["x"] > 20000 or mx["y"] - mn["y"] > 20000:
            continue
        if mn["z"] > z + half or mx["z"] < z - half:
            continue
        if normal[0]:
            front = (x, x + 250 * normal[0])
            if max(mn["x"], min(front)) > min(mx["x"], max(front)) or mn["y"] > y + half or mx["y"] < y - half:
                continue
        else:
            front = (y, y + 250 * normal[1])
            if max(mn["y"], min(front)) > min(mx["y"], max(front)) or mn["x"] > x + half or mx["x"] < x - half:
                continue
        return True
    return False


def yaw_for(normal):
    # A plane rolled 90 shows its front (unmirrored) towards +Y at yaw 0; rotating by yaw turns that normal. The old
    # table was 180 out: the two-sided material hid it, but every piece read mirrored (player 2026-10-11, RXLA backwards).
    return {(0, 1): 0.0, (-1, 0): 90.0, (0, -1): 180.0, (1, 0): 270.0}[normal]


CEILINGS = ("KT_Ceil_",)
CEIL_SPACING = 1400.0      # one piece per this many cm along each side of a ceiling's area, on average


def ceilings(actors):
    """Ceiling slabs -> (x0, x1, y0, y1, underside z)."""
    out = []
    for a in actors:
        if a["label"].startswith(CEILINGS):
            mn, mx = a["bounds"]["min"], a["bounds"]["max"]
            if mx["x"] - mn["x"] > 1000 and mx["y"] - mn["y"] > 1000:
                out.append((mn["x"], mx["x"], mn["y"], mx["y"], mn["z"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    aspect = {t: 1.0 for t in textures(m)}
    aspect.update(import_web(b))
    texs = sorted(aspect)
    if args.list:
        print("\n".join(texs))
        return
    actors = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    for a in actors:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    actors = [a for a in actors if not a["label"].startswith(PREFIX)]
    rng = random.Random(SEED)
    plan = []
    if args.test:
        for n, t in enumerate(texs[::5][:6]):
            plan.append((t, 24576.0 + 3.0, -34000.0 + n * 900.0, 300.0, 380.0, (1, 0)))
    else:
        for (fx, fy, normal, along, length, top) in faces(actors):
            count = max(0, int(length / SPACING + rng.random()))
            for _ in range(count):
                size = rng.choice((260.0, 320.0, 400.0, 520.0))
                if top < size + 120:
                    continue
                off = rng.uniform(-length / 2 + size / 2 + 50, length / 2 - size / 2 - 50)
                z = rng.uniform(size / 2 + 60, min(top - size / 2 - 40, 700.0))
                x = fx + along[0] * off + normal[0] * 3.0
                y = fy + along[1] * off + normal[1] * 3.0
                if blocked(actors, x, y, z, size / 2, normal):
                    continue
                if any(abs(x - p[1]) + abs(y - p[2]) < (size + p[4]) / 2 + 100 and abs(z - p[3]) < (size + p[4]) / 2 for p in plan):
                    continue
                tex = rng.choice(texs)
                half_w = size * max(1.0, aspect[tex]) / 2
                if blocked(actors, x, y, z, half_w, normal):
                    continue
                plan.append((tex, x, y, z, size, normal))
        # Ceilings (player 2026-10-11: "place it on the ceilings and walls"): big pieces facing down.
        for (x0, x1, y0, y1, zc) in ceilings(actors):
            count = int((x1 - x0) * (y1 - y0) / (CEIL_SPACING * CEIL_SPACING) + rng.random())
            for _ in range(count):
                size = rng.choice((500.0, 650.0, 800.0))
                if x1 - x0 < size + 200 or y1 - y0 < size + 200:
                    continue
                x, y = rng.uniform(x0 + size / 2 + 100, x1 - size / 2 - 100), rng.uniform(y0 + size / 2 + 100, y1 - size / 2 - 100)
                if any(p[5] is None and abs(x - p[1]) < (size + p[4]) / 2 + 150 and abs(y - p[2]) < (size + p[4]) / 2 + 150 for p in plan):
                    continue
                plan.append((rng.choice(texs), x, y, zc - 3.0, size, None))
    print(f"{len(texs)} textures, {len(plan)} pieces")
    for n, (tex, x, y, z, size, normal) in enumerate(plan):
        a = aspect.get(tex, 1.0)
        w, h = (size, size / a) if a >= 1 else (size * a, size)
        if normal is None:       # ceiling: the plane's front faces up at roll 0, so roll 180 shows it from below
            pose = bm.xform(x, y, z, w / 100.0, h / 100.0, 1.0, yaw=0.0)
            pose["rotation"]["roll"] = 180.0
        else:
            pose = bm.xform(x, y, z, w / 100.0, h / 100.0, 1.0, yaw=yaw_for(normal))
            pose["rotation"]["roll"] = 90.0
        label = f"{PREFIX}{n:03d}"
        ref = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=label, xform=pose)["refPath"], label)
        for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": ref}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                b.props(c["refPath"], {"overrideMaterials": [{"refPath": material(b, tex)}], "castShadow": False,
                                       "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
    found = json.loads(m.tool(AS, "find_assets", name="M_KT_Graf_")) if isinstance(m.tool(AS, "find_assets", name="M_KT_Graf_"), str) else m.tool(AS, "find_assets", name="M_KT_Graf_")
    m.tool(AS, "save_assets", asset_paths=[p for p in (found or []) if "M_KT_Graf_" in p])
    print("placed", len(plan))


if __name__ == "__main__":
    main()
