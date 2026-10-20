"""Live AI bots and cover structures in the Arena and the bot range.

    python tools/build_bot_arena.py [--dry-run]

Arena (inside KT_ArenaWall_N/E/W): two AI bot spawners (Guard Spawner) on the far side, enemy team,
health bars on, respawning 5 s after elimination, patrolling the arena; and pre-built Fortnite pieces as
cover: two wall pairs, a ramp up to a floor, so fights have structures to use. Bot range: a few walls
and a ramp around the patrol bots. Pieces are real player-style builds (wood, editable, breakable), so
damage leaves them broken until the match restarts.
Labels are KT4_Arena_* and KT4_BotCover_*; only those are replaced.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

GUARD = "/CRD_HenchmanSpawner/SetupAssets/PID_Device_GuardSpawner_V2.PID_Device_GuardSpawner_V2"
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
WALL = PIECES + "PBWA_W1_Solid.PBWA_W1_Solid_C"
FLOOR = PIECES + "PBWA_W1_Floor.PBWA_W1_Floor_C"
RAMP = PIECES + "PBWA_W1_StairW.PBWA_W1_StairW_C"
C, H = bm.CELL, bm.LEVEL_H


def piece(b, label, cls, x, y, z, yaw=0.0):
    ref = b.m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": cls}, name=label, xform=bm.xform(x, y, z, yaw=yaw))
    path = b.labelled(ref["refPath"], label)
    b.props(path, {"bForciblyStructurallySupported": True})
    return path


def bot(b, label, x, y, accuracy=None, health=100, shield=50):
    g = b.device(GUARD, label, x, y, 0.0)
    b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": g}, xform=bm.xform(x, y, 0.0, yaw=180))
    values = {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
              "enabledAtGameStart": True, "allowInfiniteSpawn": True, "spawnOnTimer": True, "spawnTimer": 5,
              "spawnCount": 1, "showHealthBar": True, "startingHealth": health, "max Health": health,
              "startingShield": shield, "enablePatrol": True, "maxPatrolDistance_InMeter": 15}
    if accuracy:
        values["accuracy"] = accuracy
    b.props(g, values)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    n, e, w = (acts[f"KT_ArenaWall_{k}"]["bounds"] for k in "NEW")
    x0, x1 = w["min"]["x"], n["min"]["x"]           # arena interior along X (open side toward the ready room)
    y0, y1 = w["max"]["y"], e["min"]["y"]           # between the west and east walls
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    # Pieces sit on the player build grid (player 2026-10-20): walls +C/2 in x, floor and ramp +C/2 in x and y.
    print(f"arena interior x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f}")
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith(("KT4_Arena_", "KT4_BotCover_")):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})

    # Cover: two wall pairs either side of the middle, a ramp up to a floor on the far side.
    k = 0
    for dy in (-2 * C, 2 * C):
        piece(b, f"KT4_Arena_Wall_{k}", WALL, xm + C / 2, ym + dy, 0.0, yaw=90); k += 1
        piece(b, f"KT4_Arena_Wall_{k}", WALL, xm + C / 2, ym + dy + C, 0.0, yaw=90); k += 1
    piece(b, "KT4_Arena_Ramp", RAMP, x1 - 3.0 * C, ym + C / 2, 0.0)
    piece(b, "KT4_Arena_Floor", FLOOR, x1 - 2.0 * C, ym + C / 2, H)
    # Live bots on the far side, spread across the width.
    for i, dy in enumerate((-3 * C, 3 * C)):
        bot(b, f"KT4_Arena_Bot_{i}", x1 - 1.5 * C, ym + dy)

    sign = acts.get("KT_Sign_Area_Arena")
    if sign:
        b.props(sign["actorPath"], {"text": "BOT ARENA\nlive AI bots with health bars\nthey fight back and respawn after 5 s\nstep on the pad behind you to return"})

    # Bot range: cover around the patrol bots placed by build_bot_range.py.
    for label, a in acts.items():
        if label.startswith("KT4_Bot_Patrol_"):
            bb = a["bounds"]
            px, py = (bb["min"]["x"] + bb["max"]["x"]) / 2, (bb["min"]["y"] + bb["max"]["y"]) / 2
            i = label.rsplit("_", 1)[-1]
            piece(b, f"KT4_BotCover_{i}_a", WALL, px - C, py - C / 2, 0.0, yaw=90)
            piece(b, f"KT4_BotCover_{i}_b", WALL, px - C, py + C / 2, 0.0, yaw=90)
            piece(b, f"KT4_BotCover_{i}_ramp", RAMP, px + C, py + C, 0.0, yaw=180)
    print("arena bots and cover placed")


if __name__ == "__main__":
    main()
