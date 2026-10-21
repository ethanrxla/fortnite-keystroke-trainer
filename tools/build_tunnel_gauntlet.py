"""Tunnel (P7) gauntlet: five boxed bots in line down the tunnel room, with cover walls between them (KT38_Tunnel_*).

    python tools/build_tunnel_gauntlet.py --dry-run
    python tools/build_tunnel_gauntlet.py

Player 2026-10-20: the tunnel "is bugged, as the bots seem to either dissapear or disengage, or stop moving a little
after we get close, it needs to be harder. with more bots and builds in line." Picked: 5 bots, 5 boxes.
* The cause of the vanishing bots was KT_Lane_P7's AbandonDistance (5000 cm from the start; the one guard stood 5538 cm
  away), so reaching it counted as leaving the lane and despawned everything. This sets it to 9000 (the room's far
  corner from the start is under 8000).
* Five 1x1 metal boxes (walls north, south, east and a cone; open west towards the player, like build_enemy_boxes.py)
  on player-grid cell centres, staggered either side of the start row (y -40448) so the player's own tunnel is not
  blocked, the last one straight down the row. One guard spawner per box (team 2, HIGH accuracy, one bot, no patrol,
  spawns on the device), tagged kt_lane_bot_tag so DrillDevice spawns one in each.
* Three cover walls on cell edges between the boxes, across the line of fire.
* KT_Lane_P7: BotsToClear 5, ClearEachRep on. The old single guard (KT_Guard_P7) and its KT31_EnemyBox_P7_* box are
  removed (build_enemy_boxes.py no longer builds P7).
A rerun replaces only KT38_Tunnel_* actors.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT38_Tunnel_"
ENEMY_TEAM = {"Team": "HumanPvP_Team2", "TeamIndex": 4}     # Creative team 2, the bots' team (EFortTeam HumanPvP_Team2)
C, H = bm.CELL, bm.LEVEL_H
METAL = "/Game/Building/ActorBlueprints/Player/Metal/L1/"
CLS = {k: f"{METAL}PBWA_M1_{n}.PBWA_M1_{n}_C" for k, n in (("wall", "Solid"), ("cone", "RoofC"))}
START = (41472.0, -40448.0)
FLOOR_Z = 0.0
# Box cell centres (multiples of 512), alternating two cells either side of the start row, then down the row.
BOXES = [(42496.0, -39424.0), (43520.0, -41472.0), (44544.0, -39424.0), (45568.0, -41472.0), (45568.0, -40448.0)]
# Cover walls across the line of fire (yaw 90 = a wall on an x edge, at 256 mod 512), one cell off the start row.
COVER = [(43008.0 + 256.0, -40960.0), (44032.0 + 256.0, -39936.0), (45056.0 - 256.0, -40960.0)]
BOT = {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
       "enabledAtGameStart": False, "allowInfiniteSpawn": True, "spawnCount": 1, "spawnOnTimer": False,
       "accuracy": "HIGH", "enablePatrol": False, "useDeviceSpawnLocation": True, "useDeviceSpawnRotation": True,
       "spawnRadius_InMeter": 0, "despawnGuardsWhenDisabled": True, "showHealthBar": True}
# The spawner's default spawnRadius_InMeter is 10 (its derived spawnRadius 1000 cannot be set): with it bots appeared anywhere around their box, not inside it
# (player 2026-10-20: "bots dont spawn inside boxes"). main() prints it back after placing.
# Five manned-able boxes; the lane spawns BOTS of them (player 2026-10-20: "there should be just 2 bots", and later a
# player choice of how many).
BOTS = 2
LANE = {"abandonDistance": 9000.0, "botsToClear": BOTS, "clearEachRep": True}


def pieces():
    out = []
    for i, (cx, cy) in enumerate(BOXES):
        assert cx % C == 0 and cy % C == 0, (cx, cy)
        out += [(f"Box{i}_N", "wall", cx, cy + C / 2, FLOOR_Z, 0.0), (f"Box{i}_S", "wall", cx, cy - C / 2, FLOOR_Z, 0.0),
                (f"Box{i}_E", "wall", cx + C / 2, cy, FLOOR_Z, 90.0), (f"Box{i}_Cone", "cone", cx, cy - C / 2, FLOOR_Z + H, 0.0)]
    for i, (x, y) in enumerate(COVER):
        assert x % C == C / 2 and y % C == 0, (x, y)
        out.append((f"Cover{i}", "wall", x, y, FLOOR_Z, 90.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    plan = pieces()
    for p in plan:
        print(f"  {p[0]:10} {p[1]:4} ({p[2]:.0f}, {p[3]:.0f}, {p[4]:.0f}) yaw {p[5]:.0f}  mod512 ({p[2] % C:.0f}, {p[3] % C:.0f})")
    print("bots at", BOXES)
    if args.dry_run:
        return
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    lane = acts.get("KT_Lane_P7")
    if not lane:
        raise SystemExit("KT_Lane_P7 not found")
    gone = [l for l in acts if l.startswith(PREFIX) or l.startswith("KT31_EnemyBox_P7_") or l == "KT_Guard_P7"]
    for l in gone:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": acts[l]})
    print("removed", len(gone), "old actors")
    for name, kind, x, y, z, yaw in plan:
        label = PREFIX + name
        ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": CLS[kind]}, name=label,
                     xform=bm.xform(x, y, z, yaw=yaw))
        path = b.labelled(ref["refPath"], label)
        b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True, "bCanBeDamaged": False})
        if name.startswith("Box"):      # the bots' boxes are enemy builds: team 2, not editable (player 2026-10-20)
            b.props(path, ENEMY_TEAM)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    refused = set()
    for i, (cx, cy) in enumerate(BOXES):
        bot = b.device(bm.GUARD, f"{PREFIX}Bot{i}", cx, cy, FLOOR_Z)
        b.face(bot, 180.0)                                  # faces -X, towards the player
        for key, value in BOT.items():
            try:
                b.props(bot, {key: value})
            except RuntimeError:
                refused.add(key)
        b.tag(bot, "kt_lane_bot_tag")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": bot})
    for key, value in LANE.items():
        m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName=key, value=str(value).lower()
               if isinstance(value, bool) else str(value))
    m.tool(bm.SCENE, "save_actor", actor={"refPath": lane})
    print("lane:", m.tool(bm.DEVICE, "GetDeviceProperties", device={"refPath": lane}, propertyNames=list(LANE)))
    radii = [m.tool(bm.OBJ, "get_properties", instance={"refPath": a["actorPath"]}, properties=["spawnRadius_InMeter"])
             for a in (m.tool(bm.SCENE, "find_actors", name=PREFIX + "Bot", collision_channels=[]) or [])]
    print("bot spawn radius:", radii)
    print(f"placed {len(plan)} pieces and {len(BOXES)} bots; refused bot settings: {sorted(refused)}")


if __name__ == "__main__":
    main()
