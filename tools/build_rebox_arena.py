"""Rebox Arena: the "02 Rebox and awareness" bay's live scenario, in its own walled space east of the practice court.

    python tools/build_rebox_arena.py --dry-run   # print the plan
    python tools/build_rebox_arena.py             # (re)place it; removes only KT14_Rebox_* actors
    then: python tools/install_rift_router.py     # registers the two rifts (REBOX_RIFTS there)

Player 2026-10-10: bay 02 looked unfinished. It should put you in a fight: your box against bots that have their own
boxes and pieces; take piece control and eliminate them, and add several bots because they die easily; the training
areas want live opponents that shoot back. The court bays are open to each other, so the fight is here instead:

  * a rift in bay 02 drops you inside your own closed 1x1 box, with a shotgun and an AR granted on arrival;
  * three bot boxes in an arc 5..6 cells east, each open on your side with a live bot inside (Guard Spawner, team 2,
    low accuracy, respawns 5 s after elimination) and a ramp up its front: the high ground over their box is the
    piece to take first;
  * two cover walls between; perimeter walls four levels high stop shots leaving the arena; open sky;
  * a reset button by your box clears your builds (hidden zero-player-damage explosives); the pre-built pieces are
    invulnerable and forcibly supported, so the course survives bots and resets (VERIFY they still edit);
  * a rift by the west wall back to bay 02.
Cells are 512 cm; arena cells i 48..59 (x 24576..30720), j -68..-57 (y -34816..-28672), empty space checked 2026-10-10.
"""

import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT14_Rebox_"
C, H = bm.CELL, bm.LEVEL_H
I0, I1, J0, J1 = 48, 59, -68, -57
WALL_H = 4 * H
WALL_T = 40.0
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
CLS = {k: f"{PIECES}PBWA_W1_{n}.PBWA_W1_{n}_C" for k, n in
       (("wall", "Solid"), ("floor", "Floor"), ("ramp", "StairW"), ("cone", "RoofC"))}
RAMP_YAW = {"S": 0.0, "E": 90.0, "N": 180.0, "W": 270.0}     # as build_fight_lab.py (measured 2026-10-09)
PLAYER_BOX = (50, -63)
BOT_BOXES = [(56, -66), (57, -63), (56, -60)]
COVER = [(53, -65), (53, -61)]
# Court side: the entry pad at bay 02's east corner (clear of the crosswalk), and where the way back lands.
COURT_IN = (5888.0, -29900.0, 0.0)
COURT_HOME = (5888.0, -29350.0, 0.0)
LOADOUT = ("SHOTGUN", "AR")
SIGN = ("02  REBOX ARENA\n"
        "Three live bots, each in its own box with a ramp up the front.\n"
        "Edit out, take their ramp's height first, eliminate, then re-box before you heal.\n"
        "Reset clears your builds. The rift by the west wall goes back to the court.")


def cell(i, j):
    return i * C + C / 2, j * C + C / 2


class Plan:
    def __init__(self):
        self.slabs, self.pieces, self.devices, self.signs, self.rifts = [], [], [], [], []

    def slab(self, label, x0, x1, y0, y1, top, thick, zone):
        self.slabs.append({"label": PREFIX + label, "bounds": (x0, x1, y0, y1), "top": top, "thick": thick, "mat": zone})

    def piece(self, label, kind, x, y, z, yaw):
        self.pieces.append({"label": PREFIX + label, "cls": CLS[kind], "xf": (x, y, z, yaw)})

    def wall(self, label, i, j, k, edge):
        cx, cy = cell(i, j)
        if edge in "WE":
            self.piece(label, "wall", cx + (-C / 2 if edge == "W" else C / 2), cy, k * H, 90.0)
        else:
            self.piece(label, "wall", cx, cy + (-C / 2 if edge == "S" else C / 2), k * H, 0.0)

    def flat(self, label, kind, i, j, z, yaw=0.0):
        r = math.radians(yaw)
        dx, dy = -math.sin(r), math.cos(r)
        cx, cy = cell(i, j)
        self.piece(label, kind, cx - dx * C / 2, cy - dy * C / 2, z, yaw)

    def device(self, label, asset, x, y, z=0.0, props=None, yaw=None):
        self.devices.append({"label": PREFIX + label, "asset": asset, "pos": (x, y, z), "props": props or {}, "yaw": yaw})


def bot_props():
    return {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
            "enabledAtGameStart": True, "allowInfiniteSpawn": True, "spawnOnTimer": True, "spawnTimer": 5,
            "spawnCount": 1, "showHealthBar": True, "startingHealth": 100, "max Health": 100, "startingShield": 50,
            "accuracy": "LOW", "enablePatrol": False}


def rift_props(walk_in):
    return {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
            "teleporter Rift Visible": walk_in, "enabledDuringPhase": "Always", "maintain Relative Position": False,
            "conserve Momentum": False, "play Sound Effects": walk_in}


def plan():
    p = Plan()
    x0, x1, y0, y1 = I0 * C, (I1 + 1) * C, J0 * C, (J1 + 1) * C
    p.slab("Floor", x0, x1, y0, y1, 0.0, 100.0, "Arena")
    p.slab("Wall_W", x0 - WALL_T, x0, y0, y1, WALL_H, WALL_H + 100, "Arena")
    p.slab("Wall_E", x1, x1 + WALL_T, y0, y1, WALL_H, WALL_H + 100, "Arena")
    p.slab("Wall_S", x0 - WALL_T, x1 + WALL_T, y0 - WALL_T, y0, WALL_H, WALL_H + 100, "Arena")
    p.slab("Wall_N", x0 - WALL_T, x1 + WALL_T, y1, y1 + WALL_T, WALL_H, WALL_H + 100, "Arena")
    # Your box: closed, cone on top.
    pi, pj = PLAYER_BOX
    for e in "NSEW":
        p.wall(f"You_{e}", pi, pj, 0, e)
    p.flat("You_Cone", "cone", pi, pj, H)
    # Bot boxes: open on the west (your) side, cone on top, a ramp up the front climbing toward them.
    for n, (i, j) in enumerate(BOT_BOXES):
        for e in "NSE":
            p.wall(f"Bot{n}_{e}", i, j, 0, e)
        p.flat(f"Bot{n}_Cone", "cone", i, j, H)
        p.flat(f"Bot{n}_Ramp", "ramp", i - 1, j, 0.0, RAMP_YAW["E"])
        x, y = cell(i, j)
        p.device(f"Bot{n}", bm.GUARD, x, y, 0.0, bot_props(), yaw=180.0)
    for n, (i, j) in enumerate(COVER):
        p.wall(f"Cover{n}", i, j, 0, "E")
    # Rifts: court -> inside your box; west wall -> court. The router (install_rift_router.py) routes them.
    sx, sy = cell(pi, pj)
    p.device("Rift_In", bm.TELEPORTER, *COURT_IN, rift_props(True))
    p.device("Rift_Start", bm.TELEPORTER, sx, sy, 0.0, rift_props(False))
    bx, by = cell(I0, pj + 4)
    p.device("Rift_Back", bm.TELEPORTER, bx, by, 0.0, rift_props(True))
    p.device("Rift_Home", bm.TELEPORTER, *COURT_HOME, rift_props(False))
    p.rifts = [(PREFIX + "Rift_In", PREFIX + "Rift_Start"), (PREFIX + "Rift_Back", PREFIX + "Rift_Home")]
    # Arrival loadout: granted when the start rift fires (On Teleported -> GrantItem), below the floor.
    p.device("Granter", "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter", sx, sy, -400.0)
    # Reset: a button just outside your box's north side; charges over the play space.
    p.reset_button = cell(pi, pj + 1)
    p.reset_cells = [(52, -65), (52, -61), (55, -66), (55, -63), (55, -60), (51, -63)]
    # Signs: one in the arena by the way back, one in bay 02 by the entry pad.
    p.signs.append({"label": PREFIX + "Sign", "pos": (bx + 300, by + 200, 180), "yaw": 0,
                    "text": SIGN, "size": 24, "zone": "Arena"})
    p.signs.append({"label": PREFIX + "Sign_Court", "pos": (COURT_IN[0] - 250, COURT_IN[1], 180), "yaw": 0,
                    "text": "LIVE REBOX  >>\nstep on the rift\nthree bots shoot back", "size": 24, "zone": "Arena"})
    return p


def place(b, p):
    old = b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []
    for a in old:
        if a["label"].startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(old)} old {PREFIX}* actors")
    saved = []
    for s in p.slabs:
        saved.append(b.slab(s))
    for pc in p.pieces:
        x, y, z, yaw = pc["xf"]
        ref = b.m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": pc["cls"]}, name=pc["label"],
                       xform=bm.xform(x, y, z, yaw=yaw))
        path = b.labelled(ref["refPath"], pc["label"])
        b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True})
        saved.append(path)
    print(f"slabs {len(p.slabs)}, pieces {len(p.pieces)}")
    paths = {}
    for d in p.devices:
        x, y, z = d["pos"]
        path = b.device(d["asset"], d["label"], x, y, z)
        if d["yaw"] is not None:
            b.face(path, d["yaw"])
        if d["props"]:
            b.props(path, d["props"])
        paths[d["label"]] = path
        saved.append(path)
    # Loadout on arrival.
    granter = paths[PREFIX + "Granter"]
    loadout = json.loads((bm.ROOT / "shared" / "practice-loadout.json").read_text(encoding="utf-8"))["items"]
    for name, value in {"onGrantAction": "Keep All", "grant": "All Items", "grantCondition": "Always",
                        "bEquipGrantedItem": True}.items():
        try:
            b.props(granter, {name: value})
        except RuntimeError as exc:
            print(f"  granter: could not set {name} ({str(exc)[-50:]})")
    raw = b.m.tool(bm.OBJ, "get_properties", instance={"refPath": granter}, properties=["pickupItemList"])
    items = (json.loads(raw) if isinstance(raw, str) else raw)["pickupItemList"]
    b.m.tool(bm.OBJ, "reset_properties", instance=items, properties=["itemListData"])
    b.props(items["refPath"], {"itemListData": [{"itemDefinition": {"refPath": loadout[k]}, "itemQuantity": 1} for k in LOADOUT]})
    b.bind(paths[PREFIX + "Rift_Start"], "On Teleported", granter, "GrantItem")
    # Reset button and charges.
    bx, by = p.reset_button
    btn = b.device(bm.BUTTON, PREFIX + "ResetButton", bx, by, 0.0)
    b.face(btn, 270.0)
    b.props(btn, {"interaction Text": "Clear your builds in the rebox arena", "delay": 0.0, "resetDelay": 0.5})
    events = b.m.tool(bm.DEVICE, "GetBindingOptions", devicePath={"refPath": btn}) or {}
    ev = next((e for e in events.get("sourceEvents", []) if "nteract" in e), None)
    saved.append(btn)
    for n, (i, j) in enumerate(p.reset_cells):
        x, y = cell(i, j)
        boom = b.device(bm.EXPLOSIVE, f"{PREFIX}Clear_{n}", x, y, 1.5 * H)
        b.props(boom, {"blast Radius": 4.5, "player Damage": 0, "structure Damage": 10000, "knockback": "None",
                       "can be Damaged": False, "damage Indestructible Buildings": False,
                       "visible During Game": False, "play Audio / VFX": False, "time Until Reset Allowed": 0.1,
                       "has Timed Detonation From Game Start": False})
        if ev:
            b.bind(btn, ev, boom, "Explode")
        b.bind(boom, "On Exploded", boom, "Reset")
        saved.append(boom)
    print(f"reset: button event {ev}, {len(p.reset_cells)} charges")
    for s in p.signs:
        b.sign(s)
    for path in saved:
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print("routes for tools/install_rift_router.py:", p.rifts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    p = plan()
    print(f"plan: {len(p.slabs)} slabs, {len(p.pieces)} pieces, {len(p.devices)} devices, {len(p.signs)} signs")
    if args.dry_run:
        print(json.dumps({"devices": [(d["label"], d["pos"]) for d in p.devices], "rifts": p.rifts}, indent=1))
        return
    place(bm.Builder(), p)


if __name__ == "__main__":
    main()
