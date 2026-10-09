"""Crosshair guides on the edit lanes: red marks painted on the wall plus a crosshair coach device.

    python tools/build_crosshair_guides.py [--dry-run]

For every drill with an `edit_guide` in shared/drills.json that has a lane in the level (KT_Lane_<code>):
  * places a kt_crosshair_coach_device (CrosshairCoach.verse) on the lane device, so the player gets a
    live 3x3 aim radar and an on-target score at every wall;
  * on the first `guided_reps` tracks only, paints the guide on the player's side of the pre-built wall in
    the Flowstide style (reference screenshots in project files reference/flowstide): a red ring where
    the crosshair starts and, for drag edits, two parallel red lines as the corridor to drag along.
    Later tracks are left bare so the player has to place the crosshair from memory;
  * one finished-shape panel per lane above the far end: red tiles where the wall stays, dark where the
    edit removes them.
Marks are thin boxes with collision switched off, 5 cm in front of the wall face. Labels are
KT4_Guide_<code>_* and KT4_Coach_<code>; only those are removed on a re-run.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT4_Guide_"
COACH_PREFIX = "KT4_Coach_"
COACH_DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_crosshair_coach_device"
GUIDE_MAT = bm.MODULE + "/KT_Materials/MI_KT_Guide.MI_KT_Guide"
TILE_W = bm.CELL / 3.0          # edit grid tile width on a wall
TILE_H = bm.LEVEL_H / 3.0       # edit grid tile height
FACE_GAP = 45.0                 # cm in front of the wall's centre plane (player side)
DEPTH = 4.0                     # thickness of a mark


def tile_centre(track_y, tile):
    row, col = divmod(tile, 3)
    return track_y - bm.CELL / 2 + (col + 0.5) * TILE_W, (row + 0.5) * TILE_H


def mark(b, label, x, y0, y1, z0, z1, mat="Guide"):
    """A flat box in the plane x, spanning y0..y1 and z0..z1, with no collision (red guide by default)."""
    path = b.slab({"label": label, "bounds": (x - DEPTH / 2, x + DEPTH / 2, y0, y1), "top": z1,
                   "thick": z1 - z0, "mat": mat})
    comps = b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []
    mesh = next((c["refPath"] for c in comps if "StaticMeshComponent" in c["refPath"]), None)
    if mesh:
        b.props(mesh, {"bUseDefaultCollision": False, "bodyInstance": {"collisionEnabled": "NoCollision"}})
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixed-wall-marks", action="store_true", help="Use the old drill-specific paint instead of adaptive routes")
    args = ap.parse_args()
    bm.MAT["Guide"] = GUIDE_MAT
    drills = [d for d in json.loads(bm.DRILLS.read_text(encoding="utf-8"))["drills"] if d.get("edit_guide")]
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    todo = [d for d in drills if f"KT_Lane_{d['code']}" in acts]
    for d in drills:
        print(f"{d['code']} {d['id']}: {'lane found' if d in todo else 'no lane in the level, skipped'}")
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith((PREFIX, COACH_PREFIX)):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})

    for d in todo:
        g, code = d["edit_guide"], d["code"]
        o = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[f"KT_Lane_{code}"]})["location"]
        coach = b.device(COACH_DEVICE, f"{COACH_PREFIX}{code}", o["x"], o["y"], o["z"])
        b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": coach}, propertyName="drillId", value=json.dumps(d["id"]))
        b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": coach}, propertyName="adaptiveRoutes", value=json.dumps(not args.fixed_wall_marks))
        b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": acts[f"KT_Lane_{code}"]}, propertyName="showEditPanel", value="false")
        if not args.fixed_wall_marks:
            print(f"{code}: permanent adaptive HUD; no conflicting fixed wall paint")
            continue
        spacing = abs(d.get("advance", [1, 0, 0])[0] or 1) * bm.CELL
        x = o["x"] + bm.CELL / 2 - FACE_GAP
        n = 0
        for k in range(min(g.get("guided_reps", 5), d["reps"])):
            ty = o["y"] + k * spacing
            sy, sz = tile_centre(ty, g["start"])
            ey, ez = tile_centre(ty, g["end"])
            sz, ez = o["z"] + sz, o["z"] + ez
            # Start ring (Flowstide reference 04): a hollow square ring around the start point.
            r, w = 26.0, 6.0
            mark(b, f"{PREFIX}{code}_{k}_ring_t", x, sy - r, sy + r, sz + r - w, sz + r)
            mark(b, f"{PREFIX}{code}_{k}_ring_b", x, sy - r, sy + r, sz - r, sz - r + w)
            mark(b, f"{PREFIX}{code}_{k}_ring_l", x, sy - r, sy - r + w, sz - r, sz + r)
            mark(b, f"{PREFIX}{code}_{k}_ring_r", x, sy + r - w, sy + r, sz - r, sz + r)
            if g["end"] != g["start"]:
                # Drag corridor (references 07 and 08): two parallel lines to keep the crosshair between,
                # from just before the start to just past the end.
                gap, lw, over = 22.0, 6.0, 40.0
                if abs(ez - sz) < 1:
                    y0, y1 = min(sy, ey) - over, max(sy, ey) + over
                    mark(b, f"{PREFIX}{code}_{k}_lane_a", x, y0, y1, sz + gap, sz + gap + lw)
                    mark(b, f"{PREFIX}{code}_{k}_lane_b", x, y0, y1, sz - gap - lw, sz - gap)
                else:
                    z0, z1 = min(sz, ez) - over, max(sz, ez) + over
                    mark(b, f"{PREFIX}{code}_{k}_lane_a", x, sy + gap, sy + gap + lw, z0, z1)
                    mark(b, f"{PREFIX}{code}_{k}_lane_b", x, sy - gap - lw, sy - gap, z0, z1)
            n += 1
        # Finished-shape panel (reference 09): above the far end of the lane, red where the wall stays and
        # dark where the edit removes tiles, facing the player.
        px = o["x"] + 2.5 * bm.CELL - 20      # just in front of the lane room's end wall
        py = o["y"] + (min(d["reps"], 3) - 1) * spacing / 2
        pz0, cell = 560.0, 70.0
        mark(b, f"{PREFIX}{code}_panel_back", px + 6, py - 1.8 * cell, py + 1.8 * cell, pz0 - 0.3 * cell, pz0 + 3.3 * cell, "Void")
        for t in range(9):
            row, col = divmod(t, 3)
            if t in g["tiles"]:
                continue
            cy = py - 1.5 * cell + (col + 0.5) * cell
            cz = pz0 + (row + 0.5) * cell
            mark(b, f"{PREFIX}{code}_panel_{t}", px, cy - cell / 2 + 3, cy + cell / 2 - 3, cz - cell / 2 + 3, cz + cell / 2 - 3)
        print(f"{code}: coach placed, guides on {n} of {d['reps']} walls")


if __name__ == "__main__":
    main()
