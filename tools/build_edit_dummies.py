"""Target dummies for the wall-edit drills, and a repair for the weapon-swap targets.

    python tools/build_edit_dummies.py [--dry-run]

Edit drills that end on a shot (shared/drills.json, a target_hit gun check):
  * E2 edit_window    right-hand peek: per track, a dummy behind the wall and one cell to the right.
  * E4 edit_half_wall jump shot: per track, a dummy straight behind the wall on a low pedestal, so the
                      shot is taken over the wall from a jump.
  * E7 edit_peek      right-hand peek, same placement as E2.
Each lane gets one hidden trigger tagged kt_gun_hit_tag (the lane device finds it itself); every
dummy's On Hit is bound to it. Everything here is labelled KT3_* and only those actors are replaced.

Repair: the weapon-swap lanes (W1 to W3) have gun dummies 3 cells ahead, but the lane room's front wall
is on that same cell, so they sit inside the wall. They are moved to 2 cells ahead.

The ring wall of a lane room is at 3 cells ahead for lanes without a shooter, so everything here stays
within 2 cells. Placement of the pedestal height and the peek geometry are VERIFY items for a playtest.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT3_"
LANES = {"E2": "peek", "E4": "jump", "E7": "peek"}
AHEAD = 2 * bm.CELL            # cells in front of the lane origin, inside the room
PEDESTAL = 120.0               # cm, for the jump-shot dummy
FACE_PLAYER_YAW = 180.0        # a dummy at yaw 0 faces +X; the player approaches from -X


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    drills = {d["code"]: d for d in json.loads((bm.ROOT / "shared" / "drills.json").read_text(encoding="utf-8"))["drills"]}
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    plan = []
    for code, kind in LANES.items():
        lane = acts.get(f"KT_Lane_{code}")
        if not lane:
            print(f"{code}: lane not found, skipped")
            continue
        t = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": lane})["location"]
        reps = drills[code]["reps"]
        pitch = abs(drills[code].get("advance", [1, 0, 0])[0]) * bm.CELL
        plan.append((code, kind, t["x"], t["y"], reps, pitch))
        print(f"{code} {drills[code]['id']}: {reps} dummies ({kind})")
    # weapon-swap dummies that sit inside the front wall
    fix = []
    for label, path in acts.items():
        if label.startswith("KT_GunTarget_W"):
            lane = acts.get(f"KT_Lane_{label.split('_')[2]}")
            if not lane:
                continue
            lx = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": lane})["location"]["x"]
            cur = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": path})["location"]
            if abs(cur["x"] - (lx + 3 * bm.CELL)) < 5:
                fix.append((label, path, cur, lx + AHEAD))
    print(f"{len(fix)} weapon-swap dummies are inside the front wall and would be moved")
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX) and label.split("_")[1] in ("Dummy", "GunHit", "Ped"):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    for code, kind, ox, oy, reps, pitch in plan:
        trig = b.device(bm.TRIGGER, f"KT3_GunHit_{code}", ox - bm.CELL, oy, 0.0)
        b.props(trig, {"visible in Game": False})
        b.tag(trig, "kt_gun_hit_tag")
        for k in range(reps):
            y = oy + k * pitch
            if kind == "jump":
                b.slab({"label": f"KT3_Ped_{code}_{k}", "bounds": (ox + AHEAD - 80, ox + AHEAD + 80, y - 80, y + 80),
                        "top": PEDESTAL, "thick": PEDESTAL, "mat": "Edit"})
                dm = b.device(bm.DUMMY, f"KT3_Dummy_{code}_{k}", ox + AHEAD, y, PEDESTAL)
            else:
                dm = b.device(bm.DUMMY, f"KT3_Dummy_{code}_{k}", ox + AHEAD, y + bm.CELL, 0.0)
            # Face the player, who comes from -X (lanes run +X). PlaceDevice ignores rotation and left them at
            # yaw 90, side-on (player 2026-10-10: "dummies placed sideways").
            cur = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": dm})["location"]
            b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dm},
                     xform=bm.xform(cur["x"], cur["y"], cur["z"], yaw=FACE_PLAYER_YAW))
            b.props(dm, {"infiniteHealth": True})
            b.bind(dm, "On Hit", trig, "Trigger")
        print(f"{code}: trigger and {reps} dummies placed")
    for label, path, cur, nx in fix:
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path},
                 xform=bm.xform(nx, cur["y"], cur["z"], yaw=FACE_PLAYER_YAW))
    print(f"moved {len(fix)} weapon-swap dummies out of the wall")


if __name__ == "__main__":
    main()
