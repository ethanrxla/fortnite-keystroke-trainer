"""Wall take (piece takeover): the player's structure from 2026-10-13, in the old pickaxe swap room (KT33_WallTake_*).

    python tools/build_wall_take.py --dry-run
    python tools/build_wall_take.py [--grid-offset 256]

Player 2026-10-13 (two screenshots): "a live bot should be in the enemy box, it should be an enemy builds you have to
take, the floor youre standing on is yours. the goal is to reclaim this enemies wall and kill the dummy inside."
Layout, on the room's start ledge (KT_Ledge_W2, top z 0), forward = +X:
  * your floor: one cell at ground level next to the enemy box;
  * the enemy box: the next cell forward, four metal walls and a metal cone, with a live bot inside (team 2, HIGH
    accuracy, respawns 3 s after it is eliminated). Its walls can be shot down and taken;
  * your high ground beside it: a metal floor one level up on the left (-Y) with metal stairs climbing to it; the
    WALL TAKE plate drops you here (KT33_WallTake_Arrive).
A Prop Manipulator covers the enemy box; the bot's elimination restores the box's health and shows its pieces again
(VERIFY that it brings back a wall that was destroyed). --grid-offset moves every cell by that many cm in x and y, for
when the player build grid turns out to be offset from the world (the hub's KT32_GridTest_A / _B).
A rerun replaces only KT33_WallTake_* actors.
"""
import argparse
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT33_WallTake_"
C, H = bm.CELL, bm.LEVEL_H
METAL = "/Game/Building/ActorBlueprints/Player/Metal/L1/"
CLS = {k: f"{METAL}PBWA_M1_{n}.PBWA_M1_{n}_C" for k, n in (("wall", "Solid"), ("floor", "Floor"), ("ramp", "StairW"),
                                                            ("cone", "RoofC"))}
RAMP_YAW = {"S": 0.0, "E": 90.0, "N": 180.0, "W": 270.0}      # climb direction -> yaw (build_fight_lab.py, measured)
MANIPULATOR = "/CRD_PropManipulationDevice/SetupAssets/PID_Device_PropManipulator.PID_Device_PropManipulator"
BOT = {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
       "enabledAtGameStart": True, "allowInfiniteSpawn": True, "spawnCount": 1, "spawnOnTimer": True, "spawnTimer": 3.0,
       "showHealthBar": True, "accuracy": "VERY HIGH", "enablePatrol": False, "useDeviceSpawnLocation": True,
       "spawnRadius_InMeter": 0,   # max accuracy; spawn inside the box (player 2026-10-20)
       "bGrantDefaultPickaxe": False}   # no pickaxe: it hacked its own walls out (player 2026-10-21)


def plan(ledge, off):
    # Cells on the ledge: the second column from its back edge is your floor, the third the enemy box; the row is the
    # ledge's middle, with the platform one row to the left.
    i0 = math.floor((ledge["min"]["x"] - off) / C) + 1
    jm = math.floor(((ledge["min"]["y"] + ledge["max"]["y"]) / 2 - off) / C)
    centre = lambda i, j: (i * C + C / 2 + off, j * C + C / 2 + off)
    pieces = []

    def wall(label, i, j, z, edge):
        cx, cy = centre(i, j)
        if edge in "WE":
            pieces.append((label, "wall", cx + (C / 2 if edge == "E" else -C / 2), cy, z, 90.0))
        else:
            pieces.append((label, "wall", cx, cy + (C / 2 if edge == "N" else -C / 2), z, 0.0))

    def flat(label, kind, i, j, z, yaw=0.0):
        cx, cy = centre(i, j)
        r = math.radians(yaw)
        dx, dy = -math.sin(r), math.cos(r)
        pieces.append((label, kind, cx - dx * C / 2, cy - dy * C / 2, z, yaw))

    you, enemy = (i0, jm), (i0 + 1, jm)
    flat("You_Floor", "floor", *you, 0.0)
    for e in "NSEW":
        wall(f"Enemy_{e}", *enemy, 0.0, e)
    flat("Enemy_Cone", "cone", *enemy, H)
    flat("High_Floor", "floor", you[0], jm - 1, H)
    flat("High_Stairs", "ramp", you[0] - 1, jm - 1, 0.0, RAMP_YAW["E"])
    return pieces, centre(*you), centre(*enemy)


PROP_WALL = "/Game/Building/ActorBlueprints/Wall/Construction_MetalWall_Solid_01.Construction_MetalWall_Solid_01_C"
SPARE_WALLS = 30
SPARE_Z = -9000.0
ENEMY_TEAM = {"Team": "HumanPvP_Team2", "TeamIndex": 4}


def restorable(b, acts, dry_run):
    """The box as it stands, made to come back on every visit (player 2026-10-25: "the dummy either shoots through the
    back wall or there is none"). The wall facing your floor (Enemy_W) becomes the metal wall prop that WallTake.verse
    puts back from SPARE_WALLS spares under the room (EnemySlots.verse); the other walls and the cone become
    indestructible enemy pieces, so the bot's pickaxe (bGrantDefaultPickaxe cannot be turned off over MCP) cannot open
    the back. A hidden barrel in the box (tagged kt_wall_take_clear_tag) clears your own pieces on each visit."""
    from build_room_resets import BARREL
    m = b.m
    w = acts[PREFIX + "Enemy_W"]
    t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": w["actorPath"]})
    loc, yaw = t["location"], t["rotation"]["yaw"]
    cx = (acts[PREFIX + "Enemy_W"]["bounds"]["min"]["x"] + acts[PREFIX + "Enemy_E"]["bounds"]["max"]["x"]) / 2
    cy = (acts[PREFIX + "Enemy_S"]["bounds"]["min"]["y"] + acts[PREFIX + "Enemy_N"]["bounds"]["max"]["y"]) / 2
    print(f"Enemy_W -> prop at ({loc['x']:.0f}, {loc['y']:.0f}, {loc['z']:.0f}) yaw {yaw:.0f}; box centre ({cx:.0f}, "
          f"{cy:.0f}); {SPARE_WALLS} spares at z {SPARE_Z:.0f}")
    if dry_run:
        return
    for label, a in acts.items():
        if label.startswith((PREFIX + "Spare_Wall_", PREFIX + "Clear")):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    if "Construction_MetalWall" not in w["class"]["refPath"]:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": w["actorPath"]})
        ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": PROP_WALL}, name=PREFIX + "Enemy_W",
                     xform=bm.xform(loc["x"], loc["y"], loc["z"], yaw=yaw))
        path = b.labelled(ref["refPath"], PREFIX + "Enemy_W")
        b.tag(path, "kt_wall_take_wall_tag")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    for name in ("Enemy_N", "Enemy_E", "Enemy_S", "Enemy_Cone", "You_Floor", "High_Floor", "High_Stairs"):
        path = acts[PREFIX + name]["actorPath"]
        b.props(path, {"bCanBeDamaged": False, "bIsInvulnerable": True, "bForciblyStructurallySupported": True,
                       **(ENEMY_TEAM if name.startswith("Enemy_") else {})})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    for k in range(SPARE_WALLS):
        label = f"{PREFIX}Spare_Wall_{k}"
        ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": PROP_WALL}, name=label,
                     xform=bm.xform(cx + (k % 6 - 3) * C, cy + (k // 6 - 2) * C, SPARE_Z))
        path = b.labelled(ref["refPath"], label)
        b.tag(path, "kt_wall_take_spare_wall_tag")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    boom = b.device(bm.EXPLOSIVE, PREFIX + "Clear", cx, cy, 200.0)
    for key, value in {**BARREL, "blast Radius": 1.5}.items():
        try:
            b.props(boom, {key: value})
        except RuntimeError as exc:
            print(f"  barrel {key} refused ({str(exc)[-60:]})")
    b.tag(boom, "kt_wall_take_clear_tag")
    m.tool(bm.SCENE, "save_actor", actor={"refPath": boom})
    print(f"Enemy_W is a restorable prop; {SPARE_WALLS} spares; N/E/S, cone and your pieces indestructible; clear barrel")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--grid-offset", type=float, default=256.0)   # the player grid (2026-10-13)
    ap.add_argument("--restorable", action="store_true",
                    help="only make the standing box restorable (prop front wall, spares, clear barrel); no rebuild")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    if args.restorable:
        restorable(b, acts, args.dry_run)
        return
    pieces, you, enemy = plan(acts["KT_Ledge_W2"]["bounds"], args.grid_offset)
    for p in pieces:
        print(f"  {p[0]:12} {p[1]:5} ({p[2]:.0f}, {p[3]:.0f}, {p[4]:.0f}) yaw {p[5]:.0f}")
    print("you", you, "enemy", enemy)
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for name, kind, x, y, z, yaw in pieces:
        label = PREFIX + name
        ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": CLS[kind]}, name=label,
                     xform=bm.xform(x, y, z, yaw=yaw))
        path = b.labelled(ref["refPath"], label)
        # Your pieces stay put; the enemy's can be shot down and taken.
        b.props(path, {"bForciblyStructurallySupported": True, "bCanBeDamaged": name.startswith("Enemy_")})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    # Arrive on the high ground beside the box (player 2026-10-13: "should spawn here", the raised floor).
    hx, hy = next((x, y) for n, k, x, y, z, yaw in pieces if n == "High_Floor")
    pad = b.device(bm.TELEPORTER, PREFIX + "Arrive", hx, hy + C / 2, H + 45.0)
    b.props(pad, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
                  "teleporter Rift Visible": False, "maintain Relative Position": False, "conserve Momentum": False,
                  "enabledDuringPhase": "Always"})
    b.face(pad, 0.0)
    bot = b.device(bm.GUARD, PREFIX + "Bot", enemy[0], enemy[1], 0.0)
    b.face(bot, 180.0)
    refused = []
    for key, value in BOT.items():
        try:
            b.props(bot, {key: value})
        except RuntimeError:
            refused.append(key)
    manip = b.device(MANIPULATOR, PREFIX + "Restore", enemy[0], enemy[1], 0.0)
    links = []
    for fn in ("Restore Health", "Show Props", "RestoreHealth", "ShowProps"):
        try:
            b.bind(bot, "On Eliminated", manip, fn)
            links.append(fn)
        except RuntimeError:
            pass
    for p in (pad, bot, manip):
        m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    print(f"placed {len(pieces)} pieces, arrival, bot (refused: {refused}), manipulator links: {links}")


if __name__ == "__main__":
    main()
