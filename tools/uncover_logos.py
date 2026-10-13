"""Make every RXLA logo visible: move any logo something stands in front of along its wall to a clear spot.

    python tools/uncover_logos.py [--dry-run]

Player 2026-10-12: "make sure the RXLA logos show if they are being covered by any tiles". A logo (KT24_RXLA_*, a
plane 4 cm off a wall face) counts as covered when another actor's box overlaps its outline and stands within 3 m in
front of it: tiles, plates, signs, props. Walls, floors, ceilings, graffiti, other logos and devices' 1000 cm editor
boxes are ignored. A covered logo only moves straight up, in 50 cm steps, to the first clear height below the wall top;
one that cannot clear is left where it is and reported.
"""
import argparse
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

LOGO = "KT24_RXLA_"
IGNORE = ("KT_Wall_", "KT8_Range_Wall_", "KT19_", LOGO, "KT_Ceil_", "KT_RoomFloor_", "KT_Wing_", "KT_Area_", "KT_Hub")
DEPTH = 300.0


def solid(a):
    b = a.get("bounds")
    if not b or a["label"].startswith(IGNORE) or "Floor" in a["label"] or "Ceil" in a["label"]:
        return False
    size = [b["max"][k] - b["min"][k] for k in "xyz"]
    if all(abs(v - 1000.0) < 2 for v in size) or size[0] > 20000 or size[1] > 20000:
        return False
    return b["max"]["z"] > -50


def covered(logo, t, others, at=None):
    """Whether anything stands in front of the logo (at its position, or at `at` = (x, y))."""
    b = logo["bounds"]
    yaw = math.radians(t["rotation"]["yaw"])
    # A rolled plane's front faces -Y at yaw 0 before the 2026-10-11 fix and +Y after; use the wall side instead:
    # the logo sits 4 cm off a face, so the open side is the one away from the nearest wall slab.
    nx, ny = t["normal"]
    cx = (b["min"]["x"] + b["max"]["x"]) / 2 if at is None else at[0]
    cy = (b["min"]["y"] + b["max"]["y"]) / 2 if at is None else at[1]
    hw = max(b["max"]["x"] - b["min"]["x"], b["max"]["y"] - b["min"]["y"]) / 2
    z0, z1 = b["min"]["z"], b["max"]["z"]
    for o in others:
        ob = o["bounds"]
        if ob["max"]["z"] < z0 or ob["min"]["z"] > z1:
            continue
        if nx:      # face normal along X: the logo spans Y
            if ob["max"]["y"] < cy - hw or ob["min"]["y"] > cy + hw:
                continue
            near, far = (cx, cx + DEPTH * nx)
            lo, hi = min(near, far), max(near, far)
            if ob["max"]["x"] < lo or ob["min"]["x"] > hi:
                continue
        else:
            if ob["max"]["x"] < cx - hw or ob["min"]["x"] > cx + hw:
                continue
            near, far = (cy, cy + DEPTH * ny)
            lo, hi = min(near, far), max(near, far)
            if ob["max"]["y"] < lo or ob["min"]["y"] > hi:
                continue
        return o["label"]
    return None


def face_normal(logo, walls):
    """The open side of the face the logo is on: away from the wall slab it touches."""
    b = logo["bounds"]
    cx, cy = (b["min"]["x"] + b["max"]["x"]) / 2, (b["min"]["y"] + b["max"]["y"]) / 2
    thin_x = (b["max"]["x"] - b["min"]["x"]) < (b["max"]["y"] - b["min"]["y"])
    for w in walls:
        wb = w["bounds"]
        if thin_x and wb["min"]["y"] - 50 < cy < wb["max"]["y"] + 50:
            if abs(wb["min"]["x"] - cx) < 12:
                return (-1, 0), w
            if abs(wb["max"]["x"] - cx) < 12:
                return (1, 0), w
        if not thin_x and wb["min"]["x"] - 50 < cx < wb["max"]["x"] + 50:
            if abs(wb["min"]["y"] - cy) < 12:
                return (0, -1), w
            if abs(wb["max"]["y"] - cy) < 12:
                return (0, 1), w
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    m = bm.Mcp()
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    walls = [a for a in acts if a["label"].startswith(("KT_Wall_", "KT8_Range_Wall_")) and a.get("bounds")]
    others = [a for a in acts if solid(a)]
    logos = [a for a in acts if a["label"].startswith(LOGO) and a.get("bounds")]
    placed = [((a["bounds"]["min"]["x"] + a["bounds"]["max"]["x"]) / 2, (a["bounds"]["min"]["y"] + a["bounds"]["max"]["y"]) / 2) for a in logos]
    moved = stuck = 0
    for logo in logos:
        normal, wall = face_normal(logo, walls)
        if normal is None:
            continue
        t = {"rotation": {"yaw": 0}, "normal": normal}
        blocker = covered(logo, t, others)
        if not blocker:
            continue
        b = logo["bounds"]
        half = (b["max"]["z"] - b["min"]["z"]) / 2
        top = wall["bounds"]["max"]["z"] - 20
        # Only straight up (player 2026-10-12: "you can move it higher up, but dont put it anywhere else").
        lift = None
        for step in range(1, 40):
            dz = step * 50.0
            if b["max"]["z"] + dz > top:
                break
            raised = dict(logo, bounds={"min": dict(b["min"], z=b["min"]["z"] + dz), "max": dict(b["max"], z=b["max"]["z"] + dz)})
            if not covered(raised, t, others):
                lift = dz
                break
        print(f"{logo['label']}: covered by {blocker} -> {f'raise {lift:.0f} cm' if lift else 'no clear height: left as is'}")
        if args.dry_run or not lift:
            if not lift:
                stuck += 1
            continue
        path = {"refPath": logo["actorPath"]}
        cur = m.tool(bm.ACTOR, "get_actor_transform", actor=path)
        cur["location"]["z"] += lift
        m.tool(bm.ACTOR, "set_actor_transform", actor=path, xform=cur)
        m.tool(bm.SCENE, "save_actor", actor=path)
        moved += 1
    print(f"{len(logos)} logos checked: {moved} raised, {stuck} covered with no clear height (left as is)")


if __name__ == "__main__":
    main()
