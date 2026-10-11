"""Sky Box: forward boxing on a strip high above the map (KT18_Sky_*; run by SkyBox.verse, kt_sky_box_device).

    python tools/build_sky_box.py --dry-run
    python tools/build_sky_box.py              # (re)place it; removes only KT18_Sky_* actors
    then: python tools/install_rift_router.py  # routes bay 02's rift here and the exit rift back (REBOX_RIFTS there)

Player 2026-10-10: the rebox arena on the ground "doesn't make sense" for boxing; boxing should be high up so you box
forward or fall off, restricted to one level so building ramps is pointless, with a portal out. Design canvas board
"Sky Box". Layout (cells of 512 cm): a strip 14 tiles long (east) and 3 wide at level 20 (z 7680), x 20480..27648,
y -44800..-43264 (high above empty ground):
  tile 0  exit rift back to the court        tile 1   your closed box (start rift inside it, loadout granted)
  tile 6  wave 1: one bot box                tile 10  wave 2: two bot boxes (north and south rows)
  tile 13 wave 3: one bot box
Bot boxes are open on your side (west) with a cone roof; pre-built pieces are invulnerable and forcibly supported.
A translucent ceiling 300 cm above the first level stops anyone gaining height. Bots: Guard Spawners, team 2,
low accuracy, tagged kt_sky_bot_tag, spawned per wave by the Verse device (not at game start).
"""
import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT18_Sky_"
C, H = bm.CELL, bm.LEVEL_H
X0, YC, TOP = 40 * C, -87 * C + C / 2, 20 * H
LENGTH = 14
CEIL_Z = TOP + H + 300.0
DEVICE_DEPTH = 700.0
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_sky_box_device"
GRANTER = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
CEIL_MAT = "/Game/Items/Traps/Materials/M_Barrier_BoundsTranslucent_Blue_Inst.M_Barrier_BoundsTranslucent_Blue_Inst"
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
CLS = {k: f"{PIECES}PBWA_W1_{n}.PBWA_W1_{n}_C" for k, n in (("wall", "Solid"), ("cone", "RoofC"))}
BOT_BOXES = [(6, 0), (10, -1), (10, 1), (13, 0)]       # (tile east of X0, row: -1 south, 0 middle, 1 north)
LOADOUT = ("SHOTGUN", "AR")
COURT_HOME = "KT14_Rebox_Rift_Home"
COURT_SIGN = "KT14_Rebox_Sign_Court"
SIGN = ("SKY BOX\nBox forward to each bot. One level only: ramps get you nothing.\n"
        "Off the edge and you start again in your box. Exit rift behind you.")


def cell(t, row):
    return X0 + t * C + C / 2, YC + row * C


class Plan:
    def __init__(self):
        self.slabs, self.pieces, self.devices = [], [], []

    def wall(self, label, t, row, edge):
        cx, cy = cell(t, row)
        if edge in "WE":
            self.pieces.append((PREFIX + label, "wall", cx + (-C / 2 if edge == "W" else C / 2), cy, TOP, 90.0))
        else:
            self.pieces.append((PREFIX + label, "wall", cx, cy + (-C / 2 if edge == "S" else C / 2), TOP, 0.0))

    def cone(self, label, t, row):
        cx, cy = cell(t, row)                       # a cone's pivot is the middle of its near edge (yaw 0: -Y edge)
        self.pieces.append((PREFIX + label, "cone", cx, cy - C / 2, TOP + H, 0.0))

    def box(self, label, t, row, open_west):
        for e in ("NSE" if open_west else "NSEW"):
            self.wall(f"{label}_{e}", t, row, e)
        self.cone(f"{label}_Cone", t, row)


def bot_props():
    return {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
            "enabledAtGameStart": False, "spawnOnTimer": False, "allowInfiniteSpawn": True, "spawnCount": 1,
            "showHealthBar": True, "startingHealth": 100, "max Health": 100, "startingShield": 0,
            "accuracy": "LOW", "enablePatrol": False, "useDeviceSpawnLocation": True}


def rift_props(walk_in):
    return {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
            "teleporter Rift Visible": walk_in, "enabledDuringPhase": "Always", "maintain Relative Position": False,
            "conserve Momentum": False, "play Sound Effects": walk_in}


def plan():
    p = Plan()
    y0, y1 = YC - 1.5 * C, YC + 1.5 * C
    p.slabs.append({"label": PREFIX + "Strip", "bounds": (X0, X0 + LENGTH * C, y0, y1), "top": TOP, "thick": 100.0, "mat": "Arena"})
    p.box("You", 1, 0, open_west=False)
    for n, (t, row) in enumerate(BOT_BOXES):
        p.box(f"Bot{n}", t, row, open_west=True)
        x, y = cell(t, row)
        p.devices.append(dict(label=f"Bot{n}", asset=bm.GUARD, pos=(x, y, TOP), props=bot_props(), yaw=180.0, tag="kt_sky_bot_tag"))
    sx, sy = cell(1, 0)
    ex, ey = cell(0, 0)
    p.devices.append(dict(label="Rift_Start", asset=bm.TELEPORTER, pos=(sx, sy, TOP), props=rift_props(False)))
    p.devices.append(dict(label="Rift_Exit", asset=bm.TELEPORTER, pos=(ex, ey, TOP), props=rift_props(True)))
    p.devices.append(dict(label="Loadout", asset=GRANTER, pos=(sx, sy, TOP - 400.0), props={}, tag="kt_sky_loadout_tag", grant=True))
    p.devices.append(dict(label="Device", asset=DEVICE, pos=(X0, YC, TOP - DEVICE_DEPTH), props={}, tag="kt_sky_device_tag"))
    p.devices.append(dict(label="Sign", asset=bm.BILLBOARD, pos=(ex - 150, ey, TOP + 200), props={}, sign=True))
    return p


def ceiling(b):
    """One translucent slab over the strip and a tile beyond each side: no height above the first level."""
    xf = bm.xform(X0 + LENGTH * C / 2, YC, CEIL_Z, (LENGTH * C + 2 * C) / 100.0, 5 * C / 100.0, 0.2)
    ref = b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=bm.BOX, name=PREFIX + "Ceiling", xform=xf)
    path = b.labelled(ref["refPath"], PREFIX + "Ceiling")
    for c in b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []:
        if "StaticMeshComponent" in c["refPath"]:
            b.props(c["refPath"], {"overrideMaterials": [{"refPath": CEIL_MAT}], "castShadow": False})
    return path


def place(b, p):
    old = b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []
    for a in old:
        if a["label"].startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(old)} old {PREFIX}* actors")
    saved = [b.slab(s) for s in p.slabs]
    saved.append(ceiling(b))
    for label, kind, x, y, z, yaw in p.pieces:
        ref = b.m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": CLS[kind]}, name=label, xform=bm.xform(x, y, z, yaw=yaw))
        path = b.labelled(ref["refPath"], label)
        b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True})
        saved.append(path)
    refused, paths = [], {}
    for d in p.devices:
        x, y, z = d["pos"]
        path = b.device(d["asset"], PREFIX + d["label"], x, y, z)
        paths[d["label"]] = path
        if d.get("yaw") is not None:
            b.face(path, d["yaw"])
        for key, value in d["props"].items():
            try:
                b.props(path, {key: value})
            except RuntimeError as exc:
                refused.append(f"{d['label']}: {key}")
        if d.get("tag"):
            b.tag(path, d["tag"])
        if d.get("sign"):
            b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path}, xform=bm.xform(x, y, z, 1.6, 1.6, 1.6, yaw=270.0))
            b.props(path, {"text": SIGN, "textSize": 20, "showBorder": False, "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                           "backgroundColor": {"r": 0.03, "g": 0.04, "b": 0.07, "a": 1}})
        saved.append(path)
    # Loadout: shotgun and AR, kept alongside the spawn loadout.
    g = paths["Loadout"]
    loadout = json.loads((bm.ROOT / "shared" / "practice-loadout.json").read_text(encoding="utf-8"))["items"]
    for key, value in {"onGrantAction": "Keep All", "grant": "All Items", "grantCondition": "Always", "bEquipGrantedItem": True}.items():
        try:
            b.props(g, {key: value})
        except RuntimeError:
            refused.append(f"Loadout: {key}")
    raw = b.m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["pickupItemList"])
    items = (json.loads(raw) if isinstance(raw, str) else raw)["pickupItemList"]
    b.m.tool(bm.OBJ, "list_properties", instance=items)
    b.m.tool(bm.OBJ, "reset_properties", instance=items, properties=["itemListData"])
    b.props(items["refPath"], {"itemListData": [{"itemDefinition": {"refPath": loadout[k]}, "itemQuantity": 1} for k in LOADOUT]})
    # The court's bay 02 sign now points here.
    for a in b.m.tool(bm.SCENE, "find_actors", name=COURT_SIGN, collision_channels=[]) or []:
        if a["label"] == COURT_SIGN:
            b.props(a["actorPath"], {"text": "SKY BOX  >>\nstep on the rift\nbox forward, don't fall"})
            saved.append(a["actorPath"])
    for path in saved:
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print(f"placed {len(p.slabs) + 1} slabs, {len(p.pieces)} pieces, {len(p.devices)} devices")
    if refused:
        print("not accepted (set by hand):", refused)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    p = plan()
    print(f"plan: strip x {X0:.0f}..{X0 + LENGTH * C:.0f}, y {YC - 1.5 * C:.0f}..{YC + 1.5 * C:.0f}, top z {TOP:.0f}; "
          f"{len(p.pieces)} pieces, {len(p.devices)} devices")
    if args.dry_run:
        for d in p.devices:
            print(f"  {d['label']:12} {d['pos']}")
        return
    place(bm.Builder(), p)


if __name__ == "__main__":
    main()
