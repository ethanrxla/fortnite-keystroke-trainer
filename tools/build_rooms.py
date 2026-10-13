"""Rebuild the lane room shells where the lanes really are, then dress the rooms (additive, KT5_* labels).

    python tools/build_rooms.py --dry-run             # print each room's extent, change nothing
    python tools/build_rooms.py --shells              # replace the walls, floor and ceiling of every lane
    python tools/build_rooms.py --pilot P4            # dress one room (containers, ghost cells, posts, ports, signs)

Why --shells exists: the lane devices, ledges and props sit where the plan had them before drills were retired,
while the enclosure was last built from the compacted plan, so the room labelled P4 stood about 19 tiles away
from lane P4 (and overlapped other lanes). This reads the lane's real actors instead and wraps them with one
tile of slack on every side. The old shells are written to backups/rooms-stale.json first.

Dressing is labelled KT5_<code>_*; a rerun of --pilot removes only those. KT4_* belongs to another session.
"""

import argparse
import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

CELL = bm.CELL
CODES = ["B2", "B3", "B5", "P2", "P4", "P5", "P6", "P7", "P8", "E2", "E4", "E5", "E7", "W1", "W2", "W3"]
SHELL_KINDS = ("KT_Wall_", "KT_RoomFloor_", "KT_Ceil_Lane_")
CONTAINERS = [
    "/CR_Legacy/Creative/Maps/Prefabs/Props/PPIDs/PPID_CR_Legacy_Apollo_Industrial_ShippingContainer_01_6c658245.PPID_CR_Legacy_Apollo_Industrial_ShippingContainer_01_6c658245",
    "/CR_Legacy/Creative/Maps/Prefabs/Props/PPIDs/PPID_CR_Legacy_Apollo_Industrial_ShippingContainer_01_86e3de35.PPID_CR_Legacy_Apollo_Industrial_ShippingContainer_01_86e3de35",
]
CONTAINER_LEN = 608.0       # measured: 608 x 246 x 294 cm at yaw 0
PREFIX = "KT5_"


def has_code(label, code):
    return re.search(rf"(?:^|_){code}(?:_|$)", label) is not None


def lane_extents(acts):
    """code -> (x0, x1, y0, y1) in cm, the union of the lane's own actors, shells and clutter-free, snapped to cells."""
    out = {}
    for code in CODES:
        xs0, xs1, ys0, ys1 = [], [], [], []
        for a in acts:
            l, b = a["label"], a.get("bounds")
            if not isinstance(b, dict) or not has_code(l, code) or l.startswith(SHELL_KINDS) or l.startswith(PREFIX):
                continue
            xs0.append(b["min"]["x"]); xs1.append(b["max"]["x"]); ys0.append(b["min"]["y"]); ys1.append(b["max"]["y"])
        if not xs0:
            continue
        out[code] = [math.floor(min(xs0) / CELL) * CELL - CELL, math.ceil(max(xs1) / CELL) * CELL + CELL,
                     math.floor(min(ys0) / CELL) * CELL - CELL, math.ceil(max(ys1) / CELL) * CELL + CELL]
        out[code].extend([min(ys0), max(ys1)])         # raw content span along y, used to share walls
    # Lanes in the same wing sit side by side along y. When two rooms plus their walls would overlap, they share
    # one wall centred between the two lanes' content.
    t = CELL
    for wing in "BPEW":
        row = sorted((c for c in out if c[0] == wing), key=lambda c: out[c][2])
        for a, c in zip(row, row[1:]):
            A, B = out[a], out[c]
            if A[3] + t > B[2] - t:
                mid = (A[5] + B[4]) / 2
                A[3], B[2] = mid - t / 2, mid + t / 2
    return {c: tuple(v[:4]) for c, v in out.items()}


def lane_top(code, drills):
    d = next((x for x in drills if x.get("code") == code), {})
    return bm.LEVEL_H * (d.get("lane", {}).get("up", 1) + 3)


def shells(b, acts, ext, drills):
    stale = [a for a in acts if a["label"].startswith(SHELL_KINDS) and any(has_code(a["label"], c) for c in CODES)]
    (bm.ROOT / "backups").mkdir(exist_ok=True)
    (bm.ROOT / "backups" / "rooms-stale.json").write_text(json.dumps(
        [{"label": a["label"], "bounds": a.get("bounds")} for a in stale], indent=1), encoding="utf-8")
    for a in stale:
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print("removed", len(stale), "stale shell actors")
    for code, (x0, x1, y0, y1) in ext.items():
        zone = bm.ZONE[code[0]]
        top = lane_top(code, drills)
        bottom = -bm.LEVEL_H - 100.0
        t = CELL
        walls = [(x0 - t, x0, y0 - t, y1 + t), (x1, x1 + t, y0 - t, y1 + t), (x0, x1, y0 - t, y0), (x0, x1, y1, y1 + t)]
        for k, w in enumerate(walls):
            b.slab({"label": f"KT_Wall_{code}_{k}", "bounds": w, "top": top, "thick": top - bottom, "mat": zone})
        b.slab({"label": f"KT_RoomFloor_{code}", "bounds": (x0, x1, y0, y1), "top": -bm.LEVEL_H - 20.0, "thick": 100.0, "mat": zone})
        b.slab({"label": f"KT_Ceil_Lane_{code}", "bounds": (x0 - t, x1 + t, y0 - t, y1 + t), "top": top + 100.0, "thick": 100.0, "mat": zone})
        print(f"{code}: room x {x0:.0f}..{x1:.0f} y {y0:.0f}..{y1:.0f} ({(x1 - x0) / CELL:.0f} x {(y1 - y0) / CELL:.0f} tiles), ceiling {top / 100:.1f} m")


def place_prop(b, asset, label, x, y, z=0.0, yaw=0.0):
    ref = b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=asset, name=label, xform=bm.xform(x, y, z, yaw=yaw))
    return b.labelled(ref["refPath"], label)


def pilot_p4(b, acts, ext, drills, code="P4"):
    x0, x1, y0, y1 = ext[code]
    lane = next(a for a in acts if a["label"] == f"KT_Lane_{code}")["bounds"]
    d = next(x for x in drills if x["code"] == code)
    for a in acts:
        if a["label"].startswith((f"{PREFIX}{code}_", "KT4_Test_Container")):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    ox = (lane["min"]["x"] + lane["max"]["x"]) / 2
    oy = (lane["min"]["y"] + lane["max"]["y"]) / 2
    oi, oj = math.floor(ox / CELL), math.floor(oy / CELL)
    fwd = d["lane"].get("forward", 1)
    step = abs(d["advance"][0])
    tracks = [oj + step * k for k in range(d["reps"])]
    box_i = oi + fwd

    # 1. container wall along the back of the room, one row high (608 cm long, so it runs along y)
    n = int((y1 - y0) // CONTAINER_LEN)
    gap = ((y1 - y0) - n * CONTAINER_LEN) / 2
    for k in range(n):
        place_prop(b, CONTAINERS[k % 2], f"{PREFIX}{code}_Container_{k:02d}", x0 + 123.0 + 4.0, y0 + gap + (k + 0.5) * CONTAINER_LEN, 0.0, 90.0)

    # 2. ghost footprint and four corner posts in every box cell
    for k, j in enumerate(tracks):
        cx0, cx1, cy0, cy1 = box_i * CELL, (box_i + 1) * CELL, j * CELL, (j + 1) * CELL
        b.slab({"label": f"{PREFIX}{code}_Ghost_{k:02d}", "bounds": (cx0, cx1, cy0, cy1), "top": 3.0, "thick": 3.0, "mat": "Arena"})
        for n2, (px, py) in enumerate(((cx0, cy0), (cx0, cy1), (cx1, cy0), (cx1, cy1))):
            s = 15.0
            b.slab({"label": f"{PREFIX}{code}_Post_{k:02d}{n2}", "bounds": (px - s, px + s, py - s, py + s), "top": 110.0, "thick": 110.0, "mat": "Hub"})

    # 3. danger end: a red port slit on the front wall for each track (P4 only; P8's guards need no cue)
    for k, j in enumerate(tracks if code == "P4" else []):
        cy = j * CELL + CELL / 2
        b.slab({"label": f"{PREFIX}{code}_Port_{k:02d}", "bounds": (x1 - 20.0, x1, cy - 160.0, cy + 160.0), "top": 250.0, "thick": 80.0, "mat": "Armory"})

    # 4. order signs above the containers, facing the player
    text = d["name"].upper() + "\n" + "  ".join(f"{n3 + 1} {a}" for n3, a in enumerate(d["steps"])) + "\nYellow cell = where the box goes"
    for k in (1, 5, 9):
        if k < len(tracks):
            b.sign({"label": f"{PREFIX}{code}_Sign_{k:02d}", "pos": (x0 + 300.0, tracks[k] * CELL + CELL / 2, 420.0), "yaw": 0, "text": text, "size": 24, "zone": "Piece"})
    print(f"box room {code}: {n} containers, {len(tracks)} ghost cells, {len(tracks) * 4} posts, {len(tracks)} ports, signs")


def main():
    # MILESTONE 2026-10-13 guard: --shells/--pilot rebuild rooms on the old world grid; the lane rooms were moved onto the player build grid. Pass --i-know to run anyway.
    if "--i-know" not in sys.argv:
        raise SystemExit("build_rooms.py: --shells/--pilot rebuild rooms on the old world grid; the lane rooms were moved onto the player build grid. (milestone 2026-10-13). Pass --i-know to run anyway.")
    sys.argv.remove("--i-know")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shells", action="store_true")
    ap.add_argument("--pilot", metavar="CODE")
    ap.add_argument("--dress", metavar="CODES", help="comma list or 'all': box rooms get ghost cells and posts, the rest a container wall and signs")
    args = ap.parse_args()
    drills = [d for d in json.loads((bm.ROOT / "shared" / "drills.json").read_text(encoding="utf-8"))["drills"] if not d.get("retired")]
    b = bm.Builder()
    acts = b.m.tool(bm.SCENE, "find_actors", name="", collision_channels=[]) or []
    ext = lane_extents(acts)
    for code, (x0, x1, y0, y1) in ext.items():
        print(f"{code}: x {x0:.0f}..{x1:.0f} y {y0:.0f}..{y1:.0f} = {(x1 - x0) / CELL:.0f} x {(y1 - y0) / CELL:.0f} tiles")
    if args.dry_run:
        return
    if args.shells:
        shells(b, acts, ext, drills)
    if args.pilot:
        pilot_p4(b, acts, ext, drills, args.pilot)
    if args.dress:
        for code in (CODES if args.dress == "all" else args.dress.split(",")):
            if code in BOX_ROOMS:
                pilot_p4(b, acts, ext, drills, code)
            else:
                dress_plain(b, acts, ext, drills, code)


def dress_plain(b, acts, ext, drills, code):
    """Rooms that are not box rooms: a container wall at the back and one sign naming the drill and its steps."""
    x0, x1, y0, y1 = ext[code]
    d = next(x for x in drills if x["code"] == code)
    for a in acts:
        if a["label"].startswith(f"{PREFIX}{code}_"):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    n = int((y1 - y0) // CONTAINER_LEN)
    gap = ((y1 - y0) - n * CONTAINER_LEN) / 2
    for k in range(n):
        place_prop(b, CONTAINERS[k % 2], f"{PREFIX}{code}_Container_{k:02d}", x0 + 127.0, y0 + gap + (k + 0.5) * CONTAINER_LEN, 0.0, 90.0)
    text = d["name"].upper() + "\n" + "  ".join(f"{i + 1} {a}" for i, a in enumerate(d["steps"]))
    zone = bm.ZONE[code[0]]
    for k, frac in enumerate((0.25, 0.75)):
        b.sign({"label": f"{PREFIX}{code}_Sign_{k:02d}", "pos": (x0 + 300.0, y0 + (y1 - y0) * frac, 420.0), "yaw": 0, "text": text, "size": 24, "zone": zone})
    print(f"room {code}: {n} containers, 2 signs")


BOX_ROOMS = ("P4", "P8")


if __name__ == "__main__":
    main()
