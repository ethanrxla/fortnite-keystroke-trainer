"""Ways back: a rift on the tunnel goal to the hub, and a return zone under the 90s ceiling.

    python tools/build_returns.py [--dry-run]
    python tools/install_rift_router.py        # routes the new endpoints

Additive: only KT22_Return_* actors are replaced. Endpoints are plain teleporters routed by the rift router
(RiftRouter.verse); a source with a box in shared/return-zones.json is invisible and fires when a player is
anywhere inside that box, instead of walking into a portal.

Player 2026-10-11: "at the tunnel section nothing brings me back to the main area" and "the 90s area shouldnt
have a roof, or should have rifts at the top of the room to teleport you back to the starting position".
The roof stays (without it the walls can be climbed out of); the top level of the room sends you back instead.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT22_Return_"
ZONES = bm.ROOT / "shared" / "return-zones.json"


def lane_room(acts, b, code):
    """The lane origin cell and its room (matches build_map.enclose)."""
    d = next(x for x in json.loads(bm.DRILLS.read_text(encoding="utf-8"))["drills"] if x.get("code") == code)
    lane = d.get("lane", {"kind": "flat", "forward": 2, "up": 1})
    tracks = (d["reps"] - 1) * abs(d.get("advance", [1, 0, 0])[0]) + 1
    o = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[f"KT_Lane_{code}"]})["location"]
    oi, oj = round((o["x"] - bm.CELL / 2) / bm.CELL), round((o["y"] - bm.CELL / 2) / bm.CELL)
    front = oi + lane.get("forward", 2) + (5 if bm.has_exposure(d) else 1)
    x0, x1, y0, y1 = bm.rect(oi - 2, front - 1, oj, oj + tracks - 1)       # inside the ring of walls
    return dict(oi=oi, oj=oj, tracks=tracks, lane=lane, x0=x0, x1=x1, y0=y0, y1=y1,
                top=bm.LEVEL_H * (lane.get("up", 1) + 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}

    tun = lane_room(acts, b, "P5")
    gx, gy = bm.cc(tun["oi"] + tun["lane"]["forward"], tun["oj"] + (tun["tracks"] - 1) // 2)   # goal ledge, middle track
    nin = lane_room(acts, b, "P6")
    cx, cy = (nin["x0"] + nin["x1"]) / 2, (nin["y0"] + nin["y1"]) / 2
    sx, sy = bm.cc(nin["oi"], nin["oj"])
    band = bm.LEVEL_H                                                       # the top level, up to the ceiling
    places = [("TunnelHub", gx + 120, gy, 0.0), ("NinetiesTop", cx, cy, nin["top"] - band),
              ("NinetiesStart", sx - 150, sy, 0.0)]
    zones = {PREFIX + "NinetiesTop": [(nin["x1"] - nin["x0"]) / 2, (nin["y1"] - nin["y0"]) / 2, band + 200.0]}
    for p in places:
        print(p)
    print("zones", zones)
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    for name, x, y, z in places:
        t = b.device(bm.TELEPORTER, PREFIX + name, x, y, z)
        b.props(t, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
                    "teleporter Rift Visible": False})
    ZONES.write_text(json.dumps(zones, indent=2) + "\n", encoding="utf-8")
    print(f"placed {len(places)} endpoints; now run tools/install_rift_router.py")


if __name__ == "__main__":
    main()
