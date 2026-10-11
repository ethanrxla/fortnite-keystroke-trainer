"""Add named team-mode entry/staging devices without rebuilding the arena.

Dry run by default. --apply places missing labels and configures only this
builder's KT24_Team_ devices. Read-back verifies every Verse reference.
"""
import argparse
import json
import datetime
import build_map as bm

PREFIX = "KT24_Team_"
VOLUME = "/CRD_Volume/SetupAssets/PID_CP_Devices_Volume.PID_CP_Devices_Volume"
FLAG = bm.DEV + "PID_Device_CaptureItemSpawner.PID_Device_CaptureItemSpawner"
HUD = bm.DEV + "PID_Device_HUDMessage.PID_Device_HUDMessage"


def plan():
    buttons = [
        ("Enter", (1650, -60500, 100), "TEAM MODES"),
        ("Leave", (72500, -58200, 100), "RETURN TO HUB"),
        ("JoinRed", (72500, -57600, 100), "JOIN RED"),
        ("JoinBlue", (72500, -57000, 100), "JOIN BLUE"),
        ("StartSkirmish", (72200, -57600, 100), "SKIRMISH"),
        ("StartCTF", (72200, -57000, 100), "CAPTURE THE FLAG"),
        ("StartZone", (72200, -56400, 100), "ZONE WARS"),
        ("Cancel", (72500, -56400, 100), "CANCEL MATCH"),
    ]
    devices = [(name, bm.BUTTON, pos, {"interaction Text": text, "delay": 0.0, "resetDelay": 0.5})
               for name, pos, text in buttons]
    devices += [
        ("Arrival", bm.TELEPORTER, (72300, -57900, 50), {}),
        ("Hub", bm.TELEPORTER, (1300, -60300, 50), {}),
        ("Arena", VOLUME, (75776, -55808, 2304), {"volumeWidth":16.0,"volumeDepth":16.0,"volumeHeight":12.0,"visibleInGame":False,"playerEventsEnabled":True}),
        ("Objective", VOLUME, (75776, -55808, 50), {"volumeWidth":2.0,"volumeDepth":2.0,"volumeHeight":3.0,"visibleInGame":False,"playerEventsEnabled":True}),
        ("RedFlag", FLAG, (72192, -55808, 0), {"bEnabledAtGameStart":False,"returnDroppedItems":"10 Seconds","scoreValue":0,"friendlyTeam":{"teamType":"TeamIndex","teamIndex":1}}),
        ("BlueFlag", FLAG, (79360, -55808, 0), {"bEnabledAtGameStart":False,"returnDroppedItems":"10 Seconds","scoreValue":0,"friendlyTeam":{"teamType":"TeamIndex","teamIndex":2}}),
        ("Status", HUD, (75776, -55808, -700), {}),
        ("Match", bm.MODULE + "/_Verse.KeystrokeTrainer-kt_team_match_device", (75776, -55808, -700), {}),
        ("Access", bm.MODULE + "/_Verse.KeystrokeTrainer-kt_team_access_device", (75776, -55808, -700), {}),
        ("Tests", bm.MODULE + "/_Verse.KeystrokeTrainer-kt_team_rules_test_device", (75776, -55808, -700), {}),
    ]
    return devices


def apply():
    b = bm.Builder()
    if b.m.tool(bm.SCENE, "get_current_level") != bm.MODULE + "/KeystrokeTrainer":
        raise RuntimeError("Wrong open island")
    actors = b.m.tool(bm.SCENE, "find_actors", name="", collision_channels=[])
    existing = {a["label"]: a["actorPath"] for a in actors}
    if "KT21_Team_Floor" not in existing:
        raise RuntimeError("Place/inspect the team arena first")
    backup = bm.ROOT / "backups" / ("team-devices-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(json.dumps([a for a in actors if a["label"].startswith(PREFIX)], indent=2))
    paths = {}
    for name, asset, pos, values in plan():
        label = PREFIX + name
        path = existing.get(label)
        if not path:
            path = b.device(asset, label, *pos)
        paths[name] = path
        b.m.tool(bm.ACTOR,"set_actor_transform",actor={"refPath":path},xform=bm.xform(*pos))
        if values:
            b.m.tool(bm.OBJ, "list_properties", instance={"refPath": path})
            b.props(path, values)
            actual=b.m.tool(bm.OBJ,"get_properties",instance={"refPath":path},properties=list(values))
            actual=json.loads(actual) if isinstance(actual,str) else actual
            if actual!=values:
                raise RuntimeError(f"{label} did not retain settings: {actual}")
    # The fixed arrival endpoints never randomly select native teleporter groups.
    for name in ("Arrival", "Hub"):
        b.m.tool(bm.OBJ, "list_properties", instance={"refPath": paths[name]})
        b.props(paths[name], {"knob_TargetTeleporterGroup": "Group_None", "teleporter Rift Visible": False,
                             "enabledDuringPhase": "Always", "conserve Momentum": False})
    for name,path in paths.items():
        if name in ("Access","Tests"):
            continue
        components=b.m.tool(bm.ACTOR,"get_components",actor={"refPath":path})
        if not any(c["refPath"].endswith('.KT_Tags') for c in components):
            b.tag(path,"kt_team_match_tag" if name=="Match" else "kt_team_helper_tag")
    # Controls report their validation state; activation stays explicit until the
    # native volumes, loadouts and respawns pass an in-game acceptance run.
    for name, pos, text in (
        ("HubLabel", (1500, -60700, 200), "TEAM MODES\nSkirmish / CTF / Zone Wars\nInteract with TEAM MODES"),
        ("RulesLabel", (73300, -58000, 220), "TEAM MODES - DEVELOPMENT COURT\nJoin RED or BLUE, then select a mode\nSkirmish: hold centre / CTF: bring flag home\nZone Wars: survival / Return: back to hub"),
    ):
        label = PREFIX + name
        if label not in existing:
            path = b.sign(dict(label=label, pos=pos, yaw=180, text=text, size=20, zone="Hub"))
            b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path},
                     xform=bm.xform(*pos, .9, .9, .9, yaw=270))
            paths[name] = path
    for path in paths.values():
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print("Saved team access and mode controls. Runtime activation requires validation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps([dict(label=PREFIX+n, pos=p) for n, _, p, _ in plan()], indent=2))
    if args.apply:
        apply()
