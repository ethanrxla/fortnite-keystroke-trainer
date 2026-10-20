"""Wall take: every rep resets the box to the enemy's metal walls; the bot at its hardest (KT33_WallTake_Reset*).

    python tools/build_wall_take_reset.py [--dry-run]

Player 2026-10-20: "for the wall take, every rep should reset the box to the enemy metal wall. increase the bot
difficulty to max." A rep ends when the bot (KT33_WallTake_Bot) is eliminated. Until now that only fired the prop
manipulator's Restore Health and Show Props, so a wall the player had taken stayed theirs: their own piece sat in the
slot and nothing cleared it.
Now, on the bot's elimination:
  1. KT33_WallTake_ResetTrigger (1 s delay) fires KT33_WallTake_ResetBarrel at the box: structure damage only, radius
     RADIUS_TILES, so the player's pieces in and around the box go (their floor, high ground and stairs cannot be
     damaged and stay);
  2. the barrel's On Exploded fires the manipulator's Restore Health and Show Props, which bring the enemy box back
     (VERIFY in a playtest that Restore Health revives a destroyed enemy wall; if not, the walls need a Verse respawn);
  3. the bot respawns on its own 3 s timer, into a whole box.
The old direct bot -> manipulator links are removed so the restore always follows the clear.
The bot's accuracy goes to VERY HIGH, the top of the guard spawner's scale (LOW / MODERATE / HIGH / VERY HIGH).
A rerun replaces only KT33_WallTake_Reset* actors.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT33_WallTake_Reset"
RADIUS_TILES = 1.5
BARREL = {"blast Radius": RADIUS_TILES, "player Damage": 0, "structure Damage": 10000, "visible During Game": False,
          "collision During Games": "Off", "requires Line of Sight": False, "play Audio": False,
          "time Until Reset Allowed": 0, "knockbackPlayer": 0, "damage Indestructible Buildings": False,
          "display Damage Numbers": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", name="KT33_WallTake_", collision_channels=[]) or [])}
    bot, manip = acts["KT33_WallTake_Bot"]["actorPath"], acts["KT33_WallTake_Restore"]["actorPath"]
    walls = [a for l, a in acts.items() if l.startswith("KT33_WallTake_Enemy_")]
    cx = sum((a["bounds"]["min"]["x"] + a["bounds"]["max"]["x"]) / 2 for a in walls) / len(walls)
    cy = sum((a["bounds"]["min"]["y"] + a["bounds"]["max"]["y"]) / 2 for a in walls) / len(walls)
    print(f"box centre ({cx:.0f}, {cy:.0f}); {len(walls)} enemy pieces")
    if args.dry_run:
        return
    for l, a in acts.items():
        if l.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for link in m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": manip}) or []:
        if link["sourceDevicePath"]["refPath"] == bot:
            m.tool(bm.DEVICE, "RemoveEventBinding", **link)
    trig = b.device(bm.TRIGGER, PREFIX + "Trigger", cx, cy, -400.0)
    b.props(trig, {"visible in Game": False, "triggerDelay": 1.0, "reset Delay": 0.0})
    boom = b.device(bm.EXPLOSIVE, PREFIX + "Barrel", cx, cy, 200.0)
    for key, value in BARREL.items():
        try:
            b.props(boom, {key: value})
        except RuntimeError as exc:
            print(f"  barrel {key} refused ({str(exc)[-60:]})")
    b.bind(bot, "On Eliminated", trig, "Trigger")
    b.bind(trig, "OnTriggered", boom, "Explode")
    b.bind(boom, "On Exploded", manip, "Restore Health")
    b.bind(boom, "On Exploded", manip, "Show Props")
    b.bind(boom, "On Exploded", boom, "Reset")
    b.props(bot, {"accuracy": "VERY HIGH"})
    for p in (trig, boom, bot, manip):
        m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    print("bot accuracy:", m.tool(bm.OBJ, "get_properties", instance={"refPath": bot}, properties=["accuracy"]))
    print("manipulator links:", [(l["sourceEvent"], l["targetFunction"]) for l in
                                 m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": manip}) or []])


if __name__ == "__main__":
    main()
