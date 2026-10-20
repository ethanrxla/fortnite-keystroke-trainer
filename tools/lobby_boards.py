"""Hub lobby boards (player 2026-10-11, with screenshots):

    python tools/lobby_boards.py [--dry-run]
    then: python tools/render_signs.py && python tools/build_sign_shots.py

* (2026-10-11, done once) KT_Sign_Title moved onto the hub's south wall. The GAME MODES board that took its old spot
  (KT26_Lobby_Modes) left with the team modes on 2026-10-20 (fortnite-arena-modes legacy-v1), so this no longer
  places it.
* "the boards in the lobby should be AGAINST the wall, not slightly in front of it": every hub board standing within
  4 m of a hub wall and parallel to it is pushed back until its billboard touches the wall; its sign art, back panel and
  shoot-to-travel dummy move with it.
Old KT20_SignArt_ / KT25_SignBack_ panels of the moved boards are removed so render_signs.py / build_sign_shots.py
redraw them in place.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

HUB = (-2048.0, 2560.0, -61952.0, -57344.0)       # inner wall faces: west, east, south, north
BOARDS = ("KT3_Sign", "KT_Sign_Gate_Aim", "KT_Sign_Gate_Arena", "KT_Sign_Gate_Scenario")
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


if __name__ == "__main__":
    main()
