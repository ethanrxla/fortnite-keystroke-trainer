"""More moving dummies on the Aim plate's tracking lane (A3), additive (KT23_AimRail_* only).

    python tools/build_aim_rails.py [--dry-run]

Player 2026-10-11: "put more of the moving dummies in the free range aim practice. right now, theres only 1."
KT_AimTarget_A3 (25 m) stays; four more rails run across the lane at 10 / 18 / 35 / 50 m, each at its own speed so
they never move in step. Rails are turned to yaw 90 so they run across the lane, as in tools/build_gun_range.py.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT23_AimRail_"
RAILS = [(10, 0.6, -350.0), (18, 1.2, 300.0), (35, 0.9, -200.0), (50, 1.4, 250.0)]   # metres, speed factor, sideways cm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    line = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts["KT_ShootLine_A3"]})["location"]
    places = [(f"{PREFIX}{m}m", line["x"] + m * 100.0, line["y"] + side, factor) for m, factor, side in RAILS]
    for p in places:
        print(p)
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    for label, x, y, factor in places:
        rail = b.device(bm.DUMMY_TRACK, label, x, y, 0.0)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": rail}, xform=bm.xform(x, y, 0.0, yaw=90))
        b.props(rail, {"infiniteHealth": True})
        speed = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": rail}, properties=["speed"])).get("speed")
        if isinstance(speed, (int, float)):
            b.props(rail, {"speed": speed * factor})
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": rail})
    print(f"placed {len(places)} rails")


if __name__ == "__main__":
    main()
