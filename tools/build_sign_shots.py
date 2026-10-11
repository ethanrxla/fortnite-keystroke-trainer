"""Shoot an area sign to go there, additive (KT25_SignShot_* only).

    python tools/build_sign_shots.py [--dry-run]

Player 2026-10-11: "the same way we shoot at guns we should be able to shoot at the signs that say the different
areas for us to go into like the 1v1, the training area, etc." Behind each hub area sign's panel (the KT20_SignArt_*
plane) stands one thin target dummy, scaled to 90% of the panel so the opaque panel hides it; its On Hit teleports
the shooter with the same receiving teleporter the walk-in rift or level-select button uses.
A target dummy's mesh can't be hidden (its TargetMesh refuses material overrides), hence behind the panel.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT25_SignShot_"
# sign billboard label -> receiving teleporter
SIGNS = {
    "KT_Sign_Gate_Scenario": "KT_Portal_Scenario_Return",
    "KT_Sign_Gate_Aim": "KT_Portal_Aim_Return",
    "KT_Sign_Gate_Arena": "KT_Portal_Arena_Return",
    "KT_Sign_Gate_Armory": "KT3_06_Dest",
    "KT_Sign_Gate_Build": "KT3_03_Dest",
    "KT_Sign_Gate_Edit": "KT3_05_Dest",
    "KT_Sign_Gate_Piece": "KT3_04_Dest",
    "KT2_QuickLabel": "KT2_CourtArrival",
    "KT2_FreeLabel": "KT2_FreeArrival",
}
UNIT = 268.0        # a target dummy's width and height at scale 1 (0.82 covers a 220 cm armory tile)
PIVOT = 140.0       # centre height above the pivot at scale 1 (armory: 115 at 0.82)
FILL = 0.75        # arms reach past the 268 cm estimate; 0.9 showed a hand at the panel edge


def centre(bounds):
    return {k: (bounds["min"][k] + bounds["max"][k]) / 2 for k in "xyz"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a for a in (b.m.tool(bm.SCENE, "find_actors", collision_channels=[]) or [])}
    plan = []
    for sign, dest in SIGNS.items():
        art, bb = acts.get("KT20_SignArt_" + sign), acts.get(sign)
        if not (art and bb and dest in acts):
            print(f"  skip {sign}: art {bool(art)} billboard {bool(bb)} destination {dest in acts}")
            continue
        a, s = centre(art["bounds"]), centre(bb["bounds"])
        size = {k: art["bounds"]["max"][k] - art["bounds"]["min"][k] for k in "xyz"}
        # The art plane stands in front of its billboard, towards the viewer.
        if size["x"] < size["y"]:
            n, width = (1.0 if a["x"] > s["x"] else -1.0, 0.0), size["y"]
            yaw = 0.0 if n[0] > 0 else 180.0
        else:
            n, width = (0.0, 1.0 if a["y"] > s["y"] else -1.0), size["x"]
            yaw = 90.0 if n[1] > 0 else 270.0
        sy, sz = width * FILL / UNIT, size["z"] * FILL / UNIT
        x, y = a["x"] - n[0] * 30.0, a["y"] - n[1] * 30.0
        plan.append((sign, dest, x, y, a["z"] - PIVOT * sz, yaw, sy, sz))
    for p in plan:
        print(p)
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for sign, dest, x, y, z, yaw, sy, sz in plan:
        d = b.device(bm.DUMMY, PREFIX + sign, x, y, z)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": d}, xform=bm.xform(x, y, z, 0.15, sy, sz, yaw=yaw))
        b.props(d, {"infiniteHealth": True})
        for key, value in {"showHealthBar": False}.items():
            try:
                b.props(d, {key: value})
            except RuntimeError:
                pass
        b.bind(d, "On Hit", acts[dest]["actorPath"], "Teleport")
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": d})
    print(f"placed {len(plan)} sign targets")


if __name__ == "__main__":
    main()
