"""Skills Test: Valorant-style flick mode on aim lane A2 ("FLICK pop-ups"), additive (KT15_Skills_* only).

    python tools/build_skills_test.py --dry-run   # print the plan
    python tools/build_skills_test.py             # (re)place it; removes only KT15_Skills_* actors
    then BuildAll; the device is SkillsTest.verse (kt_skills_test_device)

Player 2026-10-11: like the Valorant range, bots appear for a split second and disappear based on the difficulty; you
flick and eliminate them (the elimination must show, so they are real bots: 100 health, no shield, so a Hand Cannon
headshot drops them); they should not shoot back. The player has a Hand Cannon or a Heavy AR and swaps with a button.
The gun range's pop-up target lanes stay as they are; this is the other mode, on the Aim plate's flick lane, which was
free practice only (its five static dummies at 41..61 m stay).

Placed (lane A2: shoot line x -34560, lane centre y -87808, lane y -88576..-87040, shooting +X):
  * nine guard spawners at 5 / 8 / 12 / 15 / 20 / 25 / 30 / 40 / 50 m with sideways offsets, tagged kt_skills_bot_tag;
    disabled at game start, no timer respawn, 100 health / 0 shield, lowest accuracy and (VERIFY) no weapon;
  * START, DIFFICULTY and WEAPON buttons behind the shoot line; Hand Cannon and Heavy AR granters (clear inventory
    first, equip) under the floor;
  * the kt_skills_test_device on the shoot line's lane midpoint, below the floor;
  * distance markers at 5 / 10 / 20 / 30 / 50 m beside the lane and a lane sign;
  * the kt_aim_bot_control_tag on the existing KT12_Aim_Bots_Controller, so a run pauses the roaming practice bots
    (they shoot back) and resumes them after.
Bot settings are read back after they are set; any key UEFN did not accept is printed so it can be set by hand.
"""
import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT15_Skills_"
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_skills_test_device"
GRANTER = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
WEAPONS = {"HandCannon": ("/Game/Athena/Items/Weapons/WID_Pistol_HandCannon_Athena_SR_Ore_T03."
                          "WID_Pistol_HandCannon_Athena_SR_Ore_T03", "kt_skills_handcannon_tag"),
           "HeavyAR": ("/Game/Athena/Items/Weapons/WID_Assault_Heavy_Athena_SR_Ore_T03."
                       "WID_Assault_Heavy_Athena_SR_Ore_T03", "kt_skills_heavy_ar_tag")}
SHOOT_X = -34560.0
LANE_Y = -87808.0
# (metres down range, sideways offset cm): spread so consecutive reps pull the crosshair left, right, near and far.
BOTS = [(5, 0), (8, -480), (12, 420), (15, -260), (20, 360), (25, -500), (30, 500), (40, -200), (50, 260)]
SIGN = ("A2  SKILLS TEST\n"
        "START: bots appear one at a time and vanish. DIFFICULTY sets how fast (Easy 1.2 s, Medium 0.8, Hard 0.5).\n"
        "WEAPON swaps Hand Cannon / Heavy AR. Eliminate each bot before it goes. Why: first-shot flicks under a clock.")


def bot_props():
    # "accuracy" and the team keys are the ones build_rebox_arena.py uses; the weapon key is a best guess (VERIFY).
    return {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
            "enabledAtGameStart": False, "allowInfiniteSpawn": True, "spawnOnTimer": False, "spawnCount": 1,
            "showHealthBar": True, "startingHealth": 100, "max Health": 100, "startingShield": 0,
            "accuracy": "MODERATE", "enablePatrol": False, "useDeviceSpawnLocation": True}


NO_WEAPON = {"guard Weapon": "None"}


def plan():
    devices, signs = [], []
    for n, (m, off) in enumerate(BOTS):
        devices.append({"label": f"{PREFIX}Bot_{n}_{m}m", "asset": bm.GUARD, "pos": (SHOOT_X + m * 100.0, LANE_Y + off, 0.0),
                        "yaw": 180.0, "props": bot_props(), "tag": "kt_skills_bot_tag", "bot": True})
    bx = SHOOT_X - 340.0
    for k, (name, text, tag) in enumerate((("Start", "START Skills Test", "kt_skills_start_tag"),
                                            ("Difficulty", "Difficulty - change", "kt_skills_difficulty_tag"),
                                            ("Weapon", "Weapon - swap", "kt_skills_weapon_tag"))):
        devices.append({"label": f"{PREFIX}{name}", "asset": bm.BUTTON, "pos": (bx, LANE_Y - 300 + k * 300, 0.0),
                        "yaw": 0.0, "props": {"interaction Text": text, "delay": 0.0, "resetDelay": 0.3}, "tag": tag})
    for name, (_, tag) in WEAPONS.items():
        devices.append({"label": f"{PREFIX}Granter_{name}", "asset": GRANTER, "pos": (bx, LANE_Y, -400.0), "props": {},
                        "tag": tag, "weapon": name})
    devices.append({"label": f"{PREFIX}Device", "asset": DEVICE, "pos": (SHOOT_X + 2750.0, LANE_Y, -150.0), "props": {},
                    "tag": "kt_skills_test_tag"})
    # The 5 / 10 / 20 / 30 / 50 m markers are floating text from tools/build_range_markers.py (no board behind them).
    signs.append({"label": f"{PREFIX}Sign", "pos": (bx - 200.0, LANE_Y + 650.0, 300), "yaw": 180, "zone": "Aim",
                  "size": 26, "text": SIGN})
    return devices, signs


def check(errors, devices):
    """Every tagged device must sit inside the Verse device's box (SkillsTest.verse HalfExtent 6500 x 3400 x 1500)."""
    centre = next(d["pos"] for d in devices if d["asset"] == DEVICE)
    for d in devices:
        dx, dy, dz = (abs(a - b) for a, b in zip(d["pos"], centre))
        if d.get("tag") and (dx > 6500 or dy > 3400 or dz > 1500):
            errors.append(f"{d['label']} is outside the skills device's box")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    devices, signs = plan()
    errors = check([], devices)
    print(f"plan: {len(devices)} devices, {len(signs)} signs")
    for d in devices:
        print(f"  {d['label']:<34} {tuple(round(v) for v in d['pos'])}")
    if errors:
        print("\n".join(errors))
        return 1
    if args.dry_run:
        return 0
    b = bm.Builder()
    old = [a for a in (b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or [])
           if a["label"].startswith(PREFIX)]
    backup = bm.ROOT / "backups" / f"skills-test-{datetime.date.today()}"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / f"removed-{datetime.datetime.now():%H%M%S}.json").write_text(
        json.dumps([{"label": a["label"], "path": a["actorPath"]} for a in old], indent=1))
    for a in old:
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(old)} old {PREFIX}* actors")
    saved, refused = [], []
    for d in devices:
        x, y, z = d["pos"]
        path = b.device(d["asset"], d["label"], x, y, z)
        if d.get("yaw") is not None:
            b.face(path, d["yaw"])
        for key, value in d["props"].items():
            try:
                b.props(path, {key: value})
            except RuntimeError as exc:
                refused.append(f"{d['label']}: {key} ({str(exc)[-60:]})")
        if d.get("bot"):
            for key, value in NO_WEAPON.items():
                try:
                    b.props(path, {key: value})
                except RuntimeError:
                    refused.append(f"{d['label']}: {key} -> set the guard's weapon to none by hand (VERIFY)")
        if d.get("weapon"):
            grant_weapon(b, path, WEAPONS[d["weapon"]][0], refused, d["label"])
        if d.get("tag"):
            b.tag(path, d["tag"])
        saved.append(path)
    for s in signs:
        saved.append(b.sign(s))
    tag_aim_controller(b, refused)
    for path in saved:
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print("skills test placed")
    if refused:
        print("not accepted (set these in UEFN by hand):\n  " + "\n  ".join(refused))
    return 0


def grant_weapon(b, granter, item, refused, label):
    """Clear the inventory, grant one weapon and equip it (the WEAPON button swaps by granting the other one)."""
    for name, value in {"onGrantAction": "Clear Inventory", "grant": "All Items", "grantCondition": "Always",
                        "bEquipGrantedItem": True}.items():
        try:
            b.props(granter, {name: value})
        except RuntimeError as exc:
            refused.append(f"{label}: {name} ({str(exc)[-50:]})")
    raw = b.m.tool(bm.OBJ, "get_properties", instance={"refPath": granter}, properties=["pickupItemList"])
    items = (json.loads(raw) if isinstance(raw, str) else raw)["pickupItemList"]
    b.m.tool(bm.OBJ, "reset_properties", instance=items, properties=["itemListData"])
    b.props(items["refPath"], {"itemListData": [{"itemDefinition": {"refPath": item}, "itemQuantity": 1}]})


def tag_aim_controller(b, refused):
    found = [a for a in (b.m.tool(bm.SCENE, "find_actors", name="KT12_Aim_Bots_Controller", collision_channels=[]) or [])
             if a["label"] == "KT12_Aim_Bots_Controller"]
    if not found:
        refused.append("KT12_Aim_Bots_Controller not found: practice bots will keep roaming during a run")
        return
    path = found[0]["actorPath"]
    comps = b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []
    if not any(c["refPath"].endswith(".KT_AimBotControl") for c in comps):
        comp = b.m.tool(bm.ACTOR, "add_component", owner={"refPath": path},
                        component_type={"refPath": "/Script/VerseTags.VerseTagMarkupComponent"}, name="KT_AimBotControl")
        b.props(comp["refPath"], {"internalTags": {"internalTags": [
            {"internalTag": {"refPath": bm.TAG_CLASS.format("kt_aim_bot_control_tag")}}]}})
    b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})


if __name__ == "__main__":
    sys.exit(main())
