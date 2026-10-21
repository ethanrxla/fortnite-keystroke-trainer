"""Check, from the live level, that every drill room clears all of its builds after each rep (read only).

    python tools/audit_room_clears.py

Player 2026-10-20: "ensure verify all builds clear after rep". For each lane room in build_room_resets.ROOMS:
  * the lane device (KT_Lane_<code>) has ClearEachRep on (SameTrack is reported, not required);
  * the barrels its clear trigger fires (event bindings into each barrel) cover the whole room: every point on a
    SAMPLE_CM grid from the room's floor to its ceiling is within the blast radius of one of them;
  * every one of those barrels is silent and invisible (play Audio / VFX off, hidden), does structure damage only,
    never touches indestructible buildings, and re-arms itself on exploding.
Exit status 1 when any room fails. This proves the wiring and the coverage; the blast itself still needs one playtest.
"""
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
from build_room_resets import ROOMS, room_box  # noqa: E402

TILE_CM = 512.0
SAMPLE_CM = 256.0
EXPECT = {"play Audio / VFX": False, "visible During Game": False, "player Damage": 0,
          "damage Indestructible Buildings": False}


def main():
    m = bm.Mcp()
    acts = m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []
    by = {a["label"]: a for a in acts}
    barrels = [a for a in acts if "ExplosiveBarrel" in a["class"]["refPath"]]
    links = {a["actorPath"]: m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": a["actorPath"]}) or []
             for a in barrels}
    failed = []
    for code, (lanes, triggers) in ROOMS.items():
        problems = []
        trig_paths = {by[t]["actorPath"] for t in triggers if t in by}
        if len(trig_paths) != len(triggers):
            problems.append(f"missing trigger(s) {[t for t in triggers if t not in by]}")
        fired = [a for a in barrels if any(l["sourceDevicePath"]["refPath"] in trig_paths for l in links[a["actorPath"]])]
        centres, radius = [], None
        for a in fired:
            path = a["actorPath"]
            props = json.loads(m.tool(bm.OBJ, "get_properties", instance={"refPath": path},
                                      properties=list(EXPECT) + ["blast Radius", "structure Damage"]))
            bad = {k: props.get(k) for k, v in EXPECT.items() if props.get(k) != v}
            if props.get("structure Damage", 0) < 1000:
                bad["structure Damage"] = props.get("structure Damage")
            if not any(l["sourceDevicePath"]["refPath"] == path and l["targetFunction"] == "Reset" for l in links[path]):
                bad["self reset"] = False
            if bad:
                problems.append(f"{a['label']}: {bad}")
            r = props.get("blast Radius", 0) * TILE_CM
            radius = r if radius is None else min(radius, r)
            t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": path})["location"]
            centres.append((t["x"], t["y"], t["z"]))
        box = room_box(acts, code)
        floors = [a["bounds"]["max"]["z"] for l, a in by.items() if l == f"KT_RoomFloor_{code}"]
        if not box or not centres:
            problems.append("no room geometry" if not box else "no barrels fired by the clear trigger")
            uncovered, total = [], 0
        else:
            lo, hi = box
            floor = min(floors + [0.0])
            nx, ny = int((hi["x"] - lo["x"]) // SAMPLE_CM), int((hi["y"] - lo["y"]) // SAMPLE_CM)
            nz = int((hi["z"] - floor) // SAMPLE_CM)
            uncovered, total = [], 0
            for i in range(nx + 1):
                for j in range(ny + 1):
                    for k in range(nz + 1):
                        p = (lo["x"] + i * SAMPLE_CM, lo["y"] + j * SAMPLE_CM, floor + k * SAMPLE_CM)
                        total += 1
                        if min(math.dist(p, c) for c in centres) > radius:
                            uncovered.append(p)
            if uncovered:
                worst = max(uncovered, key=lambda p: min(math.dist(p, c) for c in centres))
                problems.append(f"{len(uncovered)}/{total} sample points out of reach, e.g. "
                                f"({worst[0]:.0f}, {worst[1]:.0f}, {worst[2]:.0f})")
        for lane in lanes:
            dev = by.get(f"KT_Lane_{lane}")
            if not dev:
                problems.append(f"KT_Lane_{lane} missing")
                continue
            p = m.tool(bm.DEVICE, "GetDeviceProperties", device={"refPath": dev["actorPath"]},
                       propertyNames=["ClearEachRep", "SameTrack"])
            p = json.loads(p) if isinstance(p, str) else p
            if not p.get("ClearEachRep"):
                problems.append(f"KT_Lane_{lane} ClearEachRep off")
            print(f"  KT_Lane_{lane}: ClearEachRep {p.get('ClearEachRep')}, SameTrack {p.get('SameTrack')}")
        state = "FAIL" if problems else "ok"
        print(f"{code}: {state}  {len(centres)} barrels, radius {radius or 0:.0f} cm, {total} points checked")
        for line in problems[:8]:
            print("   ", line)
        if problems:
            failed.append(code)
    print("all rooms clear completely" if not failed else f"rooms failing: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
