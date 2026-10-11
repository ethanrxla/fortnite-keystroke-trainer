"""Hub lobby boards (player 2026-10-11, with screenshots):

    python tools/lobby_boards.py [--dry-run]
    then: python tools/render_signs.py && python tools/build_sign_shots.py

* "where the RXLA TRAINING board is, replace it with the game modes graphic and move the rxla training onto the
  adjacent wall": KT_Sign_Title (RXLA TRAINING GROUND / START HERE / FREE BUILD) moves flat onto the hub's south wall
  (y=-61952, facing +Y, left of a player looking at the pads), and a new billboard KT26_Lobby_Modes takes its old spot
  in front of the join pads: GAME MODES with Rift, Control, Skirmish, Elimination and Free for all.
* "the boards in the lobby should be AGAINST the wall, not slightly in front of it": every hub board standing within
  4 m of a hub wall and parallel to it is pushed back until its billboard touches the wall; its sign art, back panel and
  shoot-to-travel dummy move with it.
Old KT20_SignArt_ / KT25_SignBack_ panels of the moved boards are removed so render_signs.py / build_sign_shots.py
redraw them in place (render_signs also gives KT24_Team_HubLabel the sign font).
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

HUB = (-2048.0, 2560.0, -61952.0, -57344.0)       # inner wall faces: west, east, south, north
TITLE = "KT_Sign_Title"
MODES = "KT26_Lobby_Modes"
MODES_TEXT = "GAME MODES\nRift | Control | Skirmish | Elimination | Rumble\nStep on a glowing pad to queue"
TITLE_SPOT = (1700.0, -61952.0)                   # south wall face, between the pads' row ends and the east corner
BOARDS = ("KT3_Sign", "KT_Sign_Gate_Aim", "KT_Sign_Gate_Arena", "KT_Sign_Gate_Scenario", "KT24_Team_HubLabel")
FOLLOW = ("KT20_SignArt_", "KT25_SignBack_", "KT25_SignShot_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []}

    def xf(label):
        return m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[label]["actorPath"]})

    def shift(label, dx, dy):
        t = xf(label)
        loc = dict(t["location"], x=t["location"]["x"] + dx, y=t["location"]["y"] + dy)
        if not args.dry_run:
            m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": acts[label]["actorPath"]},
                   xform={"location": loc, "rotation": t["rotation"], "scale": t["scale"]})
            m.tool(bm.SCENE, "save_actor", actor={"refPath": acts[label]["actorPath"]})

    # 1. Flush to the wall.
    for label in BOARDS:
        if label not in acts:
            continue
        mn, mx = acts[label]["bounds"]["min"], acts[label]["bounds"]["max"]
        gaps = {"W": mn["x"] - HUB[0], "E": HUB[1] - mx["x"], "S": mn["y"] - HUB[2], "N": HUB[3] - mx["y"]}
        # Only the walls the board is parallel to: a board thin along X faces a west or east wall.
        thin_x = (mx["x"] - mn["x"]) < (mx["y"] - mn["y"])
        gaps = {k: v for k, v in gaps.items() if (k in "WE") == thin_x}
        side = min(gaps, key=gaps.get)
        gap = gaps[side]
        if gap > 400.0 or gap < 1.0:
            print(f"{label}: {side} gap {gap:.0f} cm, left")
            continue
        dx = {"W": -gap, "E": gap}.get(side, 0.0)
        dy = {"S": -gap, "N": gap}.get(side, 0.0)
        print(f"{label}: {side} wall, moved {gap:.0f} cm")
        shift(label, dx, dy)
        for f in FOLLOW:
            if f + label in acts:
                shift(f + label, dx, dy)

    # 2. The title onto the south wall; the modes board in its place.
    t = xf(TITLE)
    old = dict(t["location"])
    depth = acts[TITLE]["bounds"]["max"]["x"] - acts[TITLE]["bounds"]["min"]["x"]
    if not args.dry_run:
        for f in ("KT20_SignArt_", "KT25_SignBack_"):
            if f + TITLE in acts:
                m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": acts[f + TITLE]["actorPath"]})
        # A billboard at yaw 0 faces -Y; yaw 180 faces +Y, into the hub from the south wall.
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": acts[TITLE]["actorPath"]},
               xform={"location": {"x": TITLE_SPOT[0], "y": TITLE_SPOT[1] + depth / 2 + 1.0, "z": old["z"]},
                      "rotation": dict(t["rotation"], yaw=180.0), "scale": t["scale"]})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": acts[TITLE]["actorPath"]})
        modes = acts[MODES]["actorPath"] if MODES in acts else b.device(bm.BILLBOARD, MODES, old["x"], old["y"], old["z"])
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": modes},
               xform={"location": old, "rotation": t["rotation"], "scale": t["scale"]})
        props = {}
        src = m.tool(bm.OBJ, "get_properties", instance={"refPath": acts[TITLE]["actorPath"]},
                     properties=["backgroundColor", "textSize", "showBorder", "textColor"])
        src = __import__("json").loads(src) if isinstance(src, str) else src
        props.update(src or {})
        props["text"] = MODES_TEXT
        b.props(modes, props)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": modes})
    print(f"title -> south wall at x {TITLE_SPOT[0]}; {MODES} at the old title spot {old}")


if __name__ == "__main__":
    main()
