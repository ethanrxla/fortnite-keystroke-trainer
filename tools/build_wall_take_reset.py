"""Wall take: one rep per visit, the enemy's full metal box on every arrival (KT33_WallTake_Reset*, WallTake.verse).

    python tools/build_wall_take_reset.py [--dry-run]
    then: BuildAll

Player 2026-10-20: "Wall Take becomes one rep per visit. make sure the full box is made." The earlier per-rep reset (bot
elimination -> barrel -> prop manipulator Restore Health / Show Props) failed in the playtest: the barrel blew the
enemy box apart and Restore Health does not bring back a destroyed wall. Now kt_wall_take_device (WallTake.verse) runs
the room:
  * on arrival at KT33_WallTake_Arrive it drops the surviving enemy pieces out of the way, fires
    KT33_WallTake_ResetBarrel to clear the player's own pieces, puts every piece back, fills any slot whose piece was
    destroyed from the spares stashed under the room (KT33_WallTake_ResetSpare*), then spawns the bot;
  * the bot's elimination ends the rep; it no longer respawns on a timer.
Playtest 2026-10-20: Verse cannot read or move placed building pieces (walls=0), so the four enemy walls are now Creative's
metal wall prop (Construction_MetalWall_Solid_01, same size and pivot as a metal build wall), which Verse can move. A
destroyed prop never returns either, so the stash under the room holds SPARE_WALLS more. The metal cone stays a build
piece and is made indestructible (the barrel would break it and nothing could restore it).
This replaces the four walls in place (same labels, kt_wall_take_wall_tag), places the spares and the device, removes
KT33_WallTake_ResetTrigger, KT33_WallTake_Restore, KT42_Probe_* and the old links. A rerun replaces only
KT33_WallTake_Reset* actors except the barrel, which it keeps.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT33_WallTake_Reset"
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_wall_take_device"
PROP_WALL = "/Game/Building/ActorBlueprints/Wall/Construction_MetalWall_Solid_01.Construction_MetalWall_Solid_01_C"
SPARE_WALLS = 40
ENEMY_TEAM = {"Team": "HumanPvP_Team2", "TeamIndex": 4}     # Creative team 2, the bot's team (EFortTeam HumanPvP_Team2)
SPARE_Z = -6000.0               # well under the room floor and the 30 m drop the surviving pieces take
RADIUS_TILES = 1.5
BARREL = {"blast Radius": RADIUS_TILES, "player Damage": 0, "structure Damage": 10000, "visible During Game": False,
          "collision During Games": "Off", "requires Line of Sight": False, "play Audio": False,
          "time Until Reset Allowed": 0, "knockbackPlayer": 0, "damage Indestructible Buildings": False,
          "display Damage Numbers": False, "play Audio / VFX": False}  # no visible explosion (player 2026-10-20)
BOT = {"accuracy": "VERY HIGH", "spawnOnTimer": False, "enabledAtGameStart": True}


def tag_once(b, path, tag):
    """Builder.tag, skipped when the actor already carries a KT_Tags component (a rerun)."""
    comps = b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []
    if not any("KT_Tags" in c["refPath"] for c in comps):
        b.tag(path, tag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", name="KT33_WallTake_", collision_channels=[]) or [])}
    bot, arrive = acts["KT33_WallTake_Bot"]["actorPath"], acts["KT33_WallTake_Arrive"]["actorPath"]
    walls = {l: a for l, a in acts.items() if l.startswith("KT33_WallTake_Enemy_") and l != "KT33_WallTake_Enemy_Cone"}
    cone = acts["KT33_WallTake_Enemy_Cone"]
    cx = sum((a["bounds"]["min"]["x"] + a["bounds"]["max"]["x"]) / 2 for a in walls.values()) / len(walls)
    cy = sum((a["bounds"]["min"]["y"] + a["bounds"]["max"]["y"]) / 2 for a in walls.values()) / len(walls)
    print(f"box centre ({cx:.0f}, {cy:.0f}); walls {sorted(walls)}; {SPARE_WALLS} spare walls at z {SPARE_Z:.0f}")
    if args.dry_run:
        return
    # The old chain: bot -> trigger -> barrel -> manipulator.
    for link in m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": bot}) or []:
        if link["sourceDevicePath"]["refPath"] == bot:
            m.tool(bm.DEVICE, "RemoveEventBinding", **link)
    for label in ("KT33_WallTake_ResetTrigger", "KT33_WallTake_Restore"):
        if label in acts:
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": acts[label]["actorPath"]})
    for a in m.tool(bm.SCENE, "find_actors", name="KT42_Probe_", collision_channels=[]) or []:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for l, a in acts.items():
        if l.startswith(PREFIX) and l not in ("KT33_WallTake_ResetBarrel", "KT33_WallTake_ResetTrigger"):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    boom = acts["KT33_WallTake_ResetBarrel"]["actorPath"] if "KT33_WallTake_ResetBarrel" in acts else \
        b.device(bm.EXPLOSIVE, PREFIX + "Barrel", cx, cy, 200.0)
    for link in m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": boom}) or []:
        try:
            m.tool(bm.DEVICE, "RemoveEventBinding", **link)
        except RuntimeError:        # a link from the trigger removed above
            pass
    for key, value in BARREL.items():
        try:
            b.props(boom, {key: value})
        except RuntimeError as exc:
            print(f"  barrel {key} refused ({str(exc)[-60:]})")
    for key, value in BOT.items():
        b.props(bot, {key: value})
    # The four walls become the movable metal wall prop, in the same spot under the same label.
    for label, a in walls.items():
        t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": a["actorPath"]})
        if "Construction_MetalWall" not in a["class"]["refPath"]:      # still the build piece
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
            ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": PROP_WALL}, name=label,
                         xform=bm.xform(t["location"]["x"], t["location"]["y"], t["location"]["z"], yaw=t["rotation"]["yaw"]))
            path = b.labelled(ref["refPath"], label)
        else:
            path = a["actorPath"]
        tag_once(b, path, "kt_wall_take_wall_tag")
        b.props(path, ENEMY_TEAM)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    b.props(cone["actorPath"], {"bCanBeDamaged": False, **ENEMY_TEAM})
    m.tool(bm.SCENE, "save_actor", actor={"refPath": cone["actorPath"]})
    # Spares in a grid of cells under the room, each in its own cell.
    n = 0
    for k in range(SPARE_WALLS):
        label = f"{PREFIX}Spare_wall_{k}"
        x, y = cx + (k % 8 - 4) * bm.CELL, cy + (k // 8 - 2) * bm.CELL
        ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": PROP_WALL}, name=label,
                     xform=bm.xform(x, y, SPARE_Z))
        path = b.labelled(ref["refPath"], label)
        b.tag(path, "kt_wall_take_spare_wall_tag")
        b.props(path, ENEMY_TEAM)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
        n += 1
    dev = b.device(DEVICE, PREFIX + "Device", cx, cy, -1500.0)
    # The device finds its helpers by tag (linking device references over MCP is refused).
    for path, tag in ((arrive, "kt_wall_take_arrive_tag"), (bot, "kt_wall_take_bot_tag"), (boom, "kt_wall_take_clear_tag")):
        tag_once(b, path, tag)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    for p in (dev, boom, bot):
        m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    print("bot:", m.tool(bm.OBJ, "get_properties", instance={"refPath": bot}, properties=["accuracy", "spawnOnTimer"]))
    print("bot links:", m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": bot}))
    print(f"placed {n} spares")


if __name__ == "__main__":
    main()
