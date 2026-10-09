"""Give every lane its own clearing trigger, tagged so the lane device finds it.

    python tools/build_lane_clear.py [--dry-run]

Why: each lane already has explosives that destroy player structures, but they were wired only to a
trigger on the hub pad, which fires when a player steps onto the pad. With auto-repeat a player never
leaves the pad, and the pad is far from the lane, so earlier builds stayed and could satisfy later
checks. The lane device now fires a trigger tagged kt_clear_tag at the start of every set and rep
(Tags.verse, DrillDevice.verse). This tool places that trigger next to each lane's start and binds it to
the lane's existing explosives (KT_Boom_<code>_*). Labels are KT3_Clear_<code>; only those are replaced.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT3_Clear_"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    lanes = sorted(k[len("KT_Lane_"):] for k in acts if k.startswith("KT_Lane_"))
    plan = {}
    for code in lanes:
        booms = sorted(v for k, v in acts.items() if k.startswith(f"KT_Boom_{code}_"))
        plan[code] = booms
        print(f"{code}: {len(booms)} explosives")
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    placed = 0
    for code, booms in plan.items():
        t = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[f"KT_Lane_{code}"]})["location"]
        trig = b.device(bm.TRIGGER, f"{PREFIX}{code}", t["x"] - bm.CELL, t["y"], t["z"])
        b.props(trig, {"visible in Game": False})
        for boom in booms:
            b.bind(trig, "OnTriggered", boom, "Explode")
        b.tag(trig, "kt_clear_tag")
        placed += 1
    print("lane clear triggers placed:", placed)


if __name__ == "__main__":
    main()
