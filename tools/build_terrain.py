"""Static structures between a lane's tracks, so practice happens beside real cover and ramps.

    python tools/build_terrain.py --dry-run
    python tools/build_terrain.py

Each rep gets its own track and advance-2 lanes leave an empty column between neighbouring tracks.
This fills those columns, alternating a one-level block and a ramp (a 36.87 degree slope over one
512 cm cell, rising 384 cm). They are plain static meshes: players cannot edit or damage them, unlike
the editable pre-built walls in the edit course. Placed outside the build cells, they never sit on a
track, so scoring checks are unaffected.

Only lanes without a pressure source get terrain (P3, P4, P5, P6): between-track blocks would shield
the guard on P7 and P8 from the far tracks. All actors are labelled KT3_Terrain_* and only those are
ever removed. Lane origins are read from the level (KT_Lane_<code>), so it follows wherever the lanes are.
"""

import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT3_Terrain_"
# P4 (box up) runs every rep on track 1 since 2026-10-13 (SameTrack); terrain beside it got in the way of the box.
CODES = ()   # 2026-10-13: none; static blocks in the build columns made 90s and boxes build badly


def lane_plan(drill, origin):
    """[(kind, cx, cy, base_z)] for the free columns of one lane. origin is the lane device position."""
    adv = drill.get("advance", [1, 0, 0])
    if abs(adv[0]) < 2:
        return []
    lane = drill.get("lane", {})
    fwd = lane.get("forward", 2)
    base = -bm.LEVEL_H if lane.get("kind") == "gap" else 0.0
    ox, oy, oz = origin
    out = []
    for k in range(drill["reps"] - 1):
        cy = oy + (abs(adv[0]) * k + 1) * bm.CELL
        # alternate: block on the first forward cell, ramp on the last, swapping every other column
        kinds = ("block", "ramp") if k % 2 == 0 else ("ramp", "block")
        cells = (1, max(fwd, 2))
        for kind, f in zip(kinds, cells):
            out.append((kind, ox + f * bm.CELL, cy, base))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    drills = {d["code"]: d for d in json.loads((bm.ROOT / "shared" / "drills.json").read_text(encoding="utf-8"))["drills"] if d.get("code") in CODES}
    b = bm.Builder()
    lanes = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT_Lane_", collision_channels=[]) or [])}
    total = 0
    plans = {}
    for code in CODES:
        path = lanes.get(f"KT_Lane_{code}")
        if not path:
            print(f"{code}: lane not found in the level, skipped")
            continue
        t = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": path})["location"]
        plans[code] = lane_plan(drills[code], (t["x"], t["y"], t["z"]))
        total += len(plans[code])
        print(f"{code}: {len(plans[code])} structures between tracks")
    if args.dry_run:
        print(total, "structures in all")
        return
    for label, path in {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or [])}.items():
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    rise = bm.LEVEL_H
    run = bm.CELL
    slope = math.degrees(math.atan2(rise, run))          # 36.87 degrees
    length = math.hypot(run, rise)                       # 640 cm along the slope
    for code, items in plans.items():
        zone = bm.ZONE[code[0]]
        for n, (kind, cx, cy, base) in enumerate(items):
            label = f"{PREFIX}{code}_{n:02d}"
            if kind == "block":
                b.slab({"label": label, "bounds": (cx - bm.CELL / 2, cx + bm.CELL / 2, cy - bm.CELL / 2, cy + bm.CELL / 2),
                        "top": base + rise, "thick": rise, "mat": zone})
            else:
                # A thin plate tilted up toward +X. The 100 cm box pivots at its bottom centre, so lift it
                # by half the rise (less half the plate thickness) to put the slope across the cell.
                xf = bm.xform(cx, cy, base + rise / 2.0 - 12.0, length / 100.0, bm.CELL / 100.0, 0.24)
                xf["rotation"]["pitch"] = slope
                ref = b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=bm.BOX, name=label, xform=xf)
                path = b.labelled(ref["refPath"], label)
                comps = b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []
                mesh = next((c["refPath"] for c in comps if "StaticMeshComponent" in c["refPath"]), None)
                if mesh:
                    b.props(mesh, {"OverrideMaterials": [{"refPath": bm.MAT[zone]}]})
    print("terrain placed:", total)


if __name__ == "__main__":
    main()
