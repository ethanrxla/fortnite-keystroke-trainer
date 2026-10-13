"""Move drill rooms onto the player build grid: every actor inside a room moves by the grid offset (KT rooms only).

    python tools/shift_to_player_grid.py --dry-run
    python tools/shift_to_player_grid.py [--rooms B5,P2,P6,P7,W3,W2] [--offset 256]
    then: python tools/build_drill_plates.py and python tools/install_rift_router.py (positions changed)

Player 2026-10-13 (wall take screenshot, "cant place wall, not in line"): the player's build grid is offset half a cell
(256 cm in x and y) from the world grid the builders used (cell centres at 256 mod 512): player cells are centred on
multiples of 512. Every pre-built piece, lane start and ledge in a room therefore sat half a cell off the player's own
pieces. This moves each room, walls included, by the offset, so relative layout is unchanged.

Rooms whose pieces are registered in the locked shared/edit-targets.json (edit lanes E*, Sky Box, Fight Lab,
Operation, Piece Lab, arena) are NOT moved here: their registry would need regenerating (needs the player's approval).
Moved labels and their old positions go to backups/grid-shift-<rooms>.json.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

DEFAULT_ROOMS = "B5,P2,P6,P7,W3,W2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rooms", default=DEFAULT_ROOMS)
    ap.add_argument("--offset", type=float, default=256.0)
    args = ap.parse_args()
    m = bm.Mcp()
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    by = {a["label"]: a for a in acts}
    rects = {}
    for code in args.rooms.split(","):
        ceil = by.get(f"KT_Ceil_Lane_{code}")
        if not ceil:
            print(f"  {code}: no room")
            continue
        b = ceil["bounds"]
        rects[code] = (b["min"]["x"] - 5, b["max"]["x"] + 5, b["min"]["y"] - 5, b["max"]["y"] + 5)
    moving = []
    for a in acts:
        b = a.get("bounds")
        if not b or not a["label"].startswith("KT"):
            continue
        size = max(b["max"]["x"] - b["min"]["x"], b["max"]["y"] - b["min"]["y"])
        cx, cy = (b["min"]["x"] + b["max"]["x"]) / 2, (b["min"]["y"] + b["max"]["y"]) / 2
        if size < 20000 and any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, x1, y0, y1 in rects.values()):
            moving.append(a)
    print(f"{len(moving)} actors in {list(rects)} move by ({args.offset}, {args.offset})")
    if args.dry_run:
        return
    log = []
    for a in moving:
        p = {"refPath": a["actorPath"]}
        t = m.tool(bm.ACTOR, "get_actor_transform", actor=p)
        log.append({"label": a["label"], "from": dict(t["location"])})
        t["location"]["x"] += args.offset
        t["location"]["y"] += args.offset
        m.tool(bm.ACTOR, "set_actor_transform", actor=p, xform=t)
        m.tool(bm.SCENE, "save_actor", actor=p)
    name = "grid-shift-" + "-".join(rects) + ".json"
    (bm.ROOT / "backups" / name).write_text(json.dumps(log, indent=1))
    print(f"moved {len(log)}; old positions in backups/{name}")


if __name__ == "__main__":
    main()
