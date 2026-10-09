"""Turn the P5 lane into a tunnel run: one rep = tunnel across four open cells onto a goal ledge.

    python tools/build_tunnel_run.py [--dry-run]

Additive: it only adds or replaces KT4_Tunnel_* actors and leaves the existing P5 ledge, catch floor and
lane device alone. Run `build_map.py --enclose-only` afterwards so the room reaches the goal, and keep
KT3_Terrain off P5 (its spacer blocks would let a player walk to the goal without building). It adds the catch floor under cells 3-5, a solid goal ledge on cell 5 of every track,
two more explosives over the far cells wired to the lane's existing clear trigger (KT3_Clear_P5), moves
the lane sign above the goal, and sets the P5 lane device's flow timeout so a full run fits in one rep.
Every lane device also gets ClearEachRep off, so nothing explodes around the player between reps.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT4_Tunnel_"
CODE = "P5"
OPEN_CELLS = 4          # cells 1..4 are open; cell 5 is the goal
RUN_TIMEOUT = 60.0      # seconds the last step waits for the player to reach the goal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    drills = json.loads(bm.DRILLS.read_text(encoding="utf-8"))["drills"]
    d = next(x for x in drills if x.get("code") == CODE)
    reps, adv = d["reps"], d.get("advance", [2, 0, 0])
    tracks = (reps - 1) * abs(adv[0]) + 1

    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    lane = acts[f"KT_Lane_{CODE}"]
    o = b.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": lane})["location"]
    oi, oj = round((o["x"] - bm.CELL / 2) / bm.CELL), round((o["y"] - bm.CELL / 2) / bm.CELL)
    print(f"{CODE} lane origin cell ({oi}, {oj}), {tracks} cells wide")
    if args.dry_run:
        return

    for label, path in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})

    # Catch floor under the open cells the old lane did not cover, then the goal ledge.
    b.slab({"label": f"{PREFIX}Catch", "bounds": bm.rect(oi + 3, oi + OPEN_CELLS, oj, oj + tracks - 1),
            "top": -bm.LEVEL_H, "thick": 100.0, "mat": "Void"})
    b.slab({"label": f"{PREFIX}Goal", "bounds": bm.rect(oi + OPEN_CELLS + 1, oi + OPEN_CELLS + 1, oj, oj + tracks - 1),
            "top": 0.0, "thick": 100.0, "mat": "Aim"})

    # Explosives over the far cells, fired with the lane's existing ones at the start of each set.
    clear = acts.get(f"KT3_Clear_{CODE}")
    for k, t in enumerate(range(0, tracks, 6)):
        x, y = bm.cc(oi + 4, oj + min(t + 3, tracks - 1))
        boom = b.device(bm.EXPLOSIVE, f"{PREFIX}Boom_{k}", x, y, bm.LEVEL_H / 2)
        b.props(boom, {"blast Radius": 4, "player Damage": 0, "structure Damage": 100000,
                       "visible During Game": False, "knockbackPlayer": 0})
        b.bind(boom, "On Exploded", boom, "Reset")
        if clear:
            b.bind(clear, "OnTriggered", boom, "Explode")

    # Lane sign above the far edge of the goal, facing back down the lane.
    sign = acts.get(f"KT_Sign_Lane_{CODE}")
    if sign:
        x, y = bm.cc(oi + OPEN_CELLS + 1, oj + (tracks - 1) // 2)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": sign},     # above the goal, inside the room
                 xform=bm.xform(x + bm.CELL / 2 - 40, y, 860, 4, 4, 4, yaw=270))
        b.props(sign, {"text": f"{CODE}  TUNNEL RUN\nfloor  >  wall  >  wall  >  cone   every cell\nreach the goal ledge = one rep"})

    # A button on the goal of every track: clears the lane's builds and sends the player back to that
    # track's start (a receive-only teleporter on the ledge; nothing targets Group_None).
    booms = [v for k, v in acts.items() if k.startswith(f"KT_Boom_{CODE}_")]
    booms += [a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name=f"{PREFIX}Boom_", collision_channels=[]) or [])]
    for k in range(reps):
        jt = oj + k * abs(adv[0])
        gx, gy = bm.cc(oi + OPEN_CELLS + 1, jt)
        sx, sy = bm.cc(oi, jt)
        start = b.device(bm.TELEPORTER, f"{PREFIX}Start_{k}", sx - 150, sy, 0.0)
        b.props(start, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None", "teleporter Rift Visible": False})
        btn = b.device(bm.BUTTON, f"{PREFIX}Button_{k}", gx + 120, gy, 0.0)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": btn}, xform=bm.xform(gx + 120, gy, 0.0, yaw=180))
        b.props(btn, {"interaction Text": "Reset builds and restart"})
        b.bind(btn, "On Interact", start, "Teleport")
        for boom in booms:
            b.bind(btn, "On Interact", boom, "Explode")
    print(f"reset buttons: {reps}, each wired to {len(booms)} explosives")

    # Rep pacing: the last step waits for the goal, long enough for a full run.
    b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName="flowTimeoutSeconds",
             value=json.dumps(RUN_TIMEOUT))
    # No clearing between reps on any lane.
    n = 0
    for label, path in acts.items():
        if label.startswith("KT_Lane_"):
            try:
                b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": path}, propertyName="clearEachRep",
                         value=json.dumps(False))
                n += 1
            except RuntimeError as exc:
                print(f"  {label}: {str(exc)[-80:]}")
    print(f"tunnel run placed; clearEachRep off on {n} lanes; clear trigger wired: {bool(clear)}")


if __name__ == "__main__":
    main()
