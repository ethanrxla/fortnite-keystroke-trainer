"""Bot range next to the Aim area: moving dummies on rails and patrolling bots to shoot at.

    python tools/build_bot_range.py [--dry-run]

Additive: only KT4_Bot_* actors are placed or replaced. The range is a floor strip along the south side of
KT_Area_Aim (same portal, walk across), with a shoot line at the near end and:
  * four rail dummies (Target Dummy Track) at about 25, 40, 60 and 80 m, strafing sideways at
    increasing speed; infinite health, they never shoot;
  * three patrol bots (Guard Spawner) further back on an enemy team: they walk a 12 m patrol, respawn
    after elimination, and DO shoot back with the lowest accuracy setting;
  * a sign over the shoot line.
Positions come from KT_Area_Aim in the level, so this follows wherever that area is.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT4_Bot_"
GUARD = "/CRD_HenchmanSpawner/SetupAssets/PID_Device_GuardSpawner_V2.PID_Device_GuardSpawner_V2"
WIDTH_CELLS = 12      # depth of the strip toward -Y
RAILS = [(5, 0.6), (8, 0.8), (12, 1.0), (16, 1.3)]      # (cells from the shoot line, speed factor)
BOTS = [10, 14, 18]                                      # cells from the shoot line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    area = acts["KT_Area_Aim"]["bounds"]
    x0, x1 = area["min"]["x"], area["max"]["x"]
    y1 = area["min"]["y"]                     # the range sits just south of the Aim area
    y0 = y1 - WIDTH_CELLS * bm.CELL
    line_x = x0 + 3 * bm.CELL
    yc = (y0 + y1) / 2
    print(f"bot range: x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f}, shoot line at x {line_x:.0f}")
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})

    b.slab({"label": f"{PREFIX}Floor", "bounds": (x0, x1, y0, y1), "top": 0.0, "thick": 100.0, "mat": "Aim"})
    b.slab({"label": f"{PREFIX}ShootLine", "bounds": (line_x - 40, line_x + 40, y0 + 256, y1 - 256), "top": 2.0,
            "thick": 2.0, "mat": "Hub"})
    b.sign({"label": f"{PREFIX}Sign", "pos": (line_x - 2 * bm.CELL, yc, 380), "yaw": 180, "zone": "Aim", "size": 48,
            "text": "BOT RANGE\nnear: moving dummies on rails (safe)\nfar: patrol bots - they shoot back"})

    for n, (cells, factor) in enumerate(RAILS):
        x = line_x + cells * bm.CELL
        y = yc + (bm.CELL if n % 2 else -bm.CELL)
        rail = b.device(bm.DUMMY_TRACK, f"{PREFIX}Rail_{n}", x, y, 0.0)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": rail}, xform=bm.xform(x, y, 0.0, yaw=90))
        speed = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": rail}, properties=["speed"])).get("speed")
        values = {"infiniteHealth": True, "showHealthBar": True}
        if isinstance(speed, (int, float)):
            values["speed"] = speed * factor
        b.props(rail, values)
        b.m.tool(bm.DEVICE, "AddEventBinding", sourceDevicePath={"refPath": rail}, sourceEvent="On Knockdown",
                 targetDevicePath={"refPath": rail}, targetFunction="Reset")

    schema = json.loads(b.m.tool(bm.OBJ, "list_properties", instance={"refPath": b.device(GUARD, f"{PREFIX}Probe", x0, y0, -5000)}))
    accuracy = (schema.get("accuracy", {}).get("enum") or ["LOW"])[0]
    probe = next(a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name=f"{PREFIX}Probe", collision_channels=[]) or []))
    b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": probe})
    for n, cells in enumerate(BOTS):
        x = line_x + cells * bm.CELL
        y = yc + (n - 1) * 3 * bm.CELL
        g = b.device(GUARD, f"{PREFIX}Patrol_{n}", x, y, 0.0)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": g}, xform=bm.xform(x, y, 0.0, yaw=180))
        b.props(g, {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
                    "enablePatrol": True, "maxPatrolDistance_InMeter": 12, "showHealthBar": True,
                    "accuracy": accuracy, "enabledAtGameStart": True, "allowInfiniteSpawn": True})
    print(f"bot range placed: {len(RAILS)} rail dummies, {len(BOTS)} patrol bots (accuracy {accuracy})")


if __name__ == "__main__":
    main()
