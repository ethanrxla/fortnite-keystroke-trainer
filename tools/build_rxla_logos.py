"""Scatter the RXLA logo across the map's walls, additive (KT24_RXLA_* only).

    python tools/build_rxla_logos.py [--list]

Player 2026-10-11: "we also want to scatter our RXLA logos throughout the map". The logos are the player's own
(assets/logos/rxla, trimmed copies in assets/logos/rxla/trimmed), imported once as textures into KT_Brand and shown
on masked, two-sided planes like the graffiti (tools/build_graffiti.py, whose wall faces and clearance checks this
reuses). Logos sit higher than the graffiti (5-9 m) and further apart, and never overlap a graffiti piece.
"""
import argparse
import pathlib
import random
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_graffiti as bg  # noqa: E402

PREFIX = "KT24_RXLA_"
SRC = bm.ROOT / "assets" / "logos" / "rxla" / "trimmed"
TEX_FOLDER = bm.MODULE + "/KT_Brand"
WEIGHTS = {"rxla_tall": 3, "rxla_slant": 3, "rxla_laptop": 1}
SPACING = 5200.0           # one logo per this many cm of wall face, on average
SEED = 2026101124


def import_logos(b):
    out = {}
    for f in sorted(SRC.glob("*.png")):
        name = "T_KT_" + re.sub(r"[^A-Za-z0-9_]", "_", f.stem)
        path = f"{TEX_FOLDER}/{name}.{name}"
        if not b.m.tool(bg.AS, "exists", path=path):
            b.m.tool(bg.TT, "import_file", folder_path=TEX_FOLDER, asset_name=name, source_file=str(f))
            b.props(path, {"powerOfTwoMode": "StretchToPowerOfTwo", "neverStream": False, "mipGenSettings": "TMGS_FromTextureGroup"})
        w, h = struct.unpack(">II", f.read_bytes()[16:24])
        out[path] = (f.stem, w / h)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    logos = import_logos(b)
    if args.list:
        print(logos)
        return
    actors = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    for a in actors:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    actors = [a for a in actors if not a["label"].startswith(PREFIX)]
    graf = [a["bounds"] for a in actors if a["label"].startswith(bg.PREFIX)]
    pool = [t for t, (stem, _) in logos.items() for _ in range(WEIGHTS.get(stem, 1))]
    rng = random.Random(SEED)
    plan = []
    for (fx, fy, normal, along, length, top) in bg.faces(actors):
        count = int(length / SPACING + rng.random() * 0.8)
        for _ in range(count):
            tex = rng.choice(pool)
            aspect = logos[tex][1]
            w = rng.choice((420.0, 520.0, 640.0))
            h = w / aspect
            if top < 500 + h / 2 + 40 or length < w + 200:
                continue
            off = rng.uniform(-length / 2 + w / 2 + 80, length / 2 - w / 2 - 80)
            z = rng.uniform(500.0, max(500.0, min(top - h / 2 - 40, 900.0)))
            x = fx + along[0] * off + normal[0] * 4.0
            y = fy + along[1] * off + normal[1] * 4.0
            if bg.blocked(actors, x, y, z, w / 2, normal):
                continue
            hit = False
            for g in graf:       # never over a graffiti piece on the same face
                if abs((g["min"]["x"] + g["max"]["x"]) / 2 - x) < 60 + w / 2 + (g["max"]["x"] - g["min"]["x"]) / 2 \
                        and abs((g["min"]["y"] + g["max"]["y"]) / 2 - y) < 60 + w / 2 + (g["max"]["y"] - g["min"]["y"]) / 2 \
                        and g["min"]["z"] < z + h / 2 + 30 and g["max"]["z"] > z - h / 2 - 30:
                    hit = True
                    break
            if hit or any(abs(x - p[1]) + abs(y - p[2]) < 3000 for p in plan):
                continue
            plan.append((tex, x, y, z, w, h, normal))
    print(f"{len(logos)} logos, {len(plan)} placements")
    for n, (tex, x, y, z, w, h, normal) in enumerate(plan):
        pose = bm.xform(x, y, z, w / 100.0, h / 100.0, 1.0, yaw=bg.yaw_for(normal))
        pose["rotation"]["roll"] = 90.0
        label = f"{PREFIX}{n:03d}"
        ref = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=bg.PLANE, name=label, xform=pose)["refPath"], label)
        for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": ref}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                b.props(c["refPath"], {"overrideMaterials": [{"refPath": bg.material(b, tex)}], "castShadow": False,
                                       "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
                for key, value in {"bAffectDynamicIndirectLighting": False, "bAffectDistanceFieldLighting": False}.items():
                    try:
                        b.props(c["refPath"], {key: value})
                    except RuntimeError:
                        pass
        m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
    found = m.tool(bg.AS, "find_assets", name="M_KT_Graf_T_KT_rxla")
    found = bg.json.loads(found) if isinstance(found, str) else found
    m.tool(bg.AS, "save_assets", asset_paths=list(found or []) + list(logos))
    print("placed", len(plan))


if __name__ == "__main__":
    main()
