"""Operation: the Scenario Expansion as a three-level game level (design/operation-level-design.md). KT16_Op_* only.

    python tools/build_operation.py --dry-run       # print the plan and the stage table
    python tools/build_operation.py --write-verse   # only regenerate verse/KeystrokeTrainer/OperationLayout.verse
    python tools/build_operation.py                 # (re)place it: removes KT16_Op_* actors, the old S1..S4 bays and
                                                    # their signs and the four ANGLE free-practice labs (backed up)
    then BuildAll; the run is driven by Operation.verse (kt_operation_device)

Player 2026-10-11: the Scenario Expansion becomes the island's one real game level, built only from existing areas:
  L1 ZONE EDGE  north strip of the Scenario plate, outdoors, walled: the storm closes from the east; push west and
                clear two zone-edge positions (4 bots behind cover), then cross into the compound.
  L2 COMPOUND   south strip, enclosed and roofed, in the style of the Counter-Strike intro training course: one skill
                per room in a straight line, the next door opens only when the room is done:
                  1 crawl under the barrier (crouch or slide)  2 grenade the nest over its wall, clean up the gap
                  3 edit a window in your wall, peek, reset    4 retake the high ground (bots on a built platform)
                  5 breach their boxes, then the door into the towers.
  L3 TOWERS     Fight Lab room A: bots on top of the climb and drop towers; eliminate both to finish.
The Fight Lab's room A west wall (KT7_Lab_Wall_W_S, removed with the ceiling) is restored here as KT16_Op_LabWall_*,
with the L2 -> L3 door in it; the sky stays open. The walkway between the strips (j -131..-130, portal to the Fight Lab
spine) stays open. Grid: cells of 512 cm, i = x / 512, j = y / 512; plate i -70..-51, j -136..-125.
"""
import argparse
import datetime
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT16_Op_"
C, H = bm.CELL, bm.LEVEL_H
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_operation_device"
GRANTER = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
BARRIER = "/CRD_VolumetricRegion/SetupAssets/PID_Device_Barrier.PID_Device_Barrier"
GATE_MAT = "/Game/Items/Traps/Materials/M_Barrier_BoundsTranslucent_Blue_Inst.M_Barrier_BoundsTranslucent_Blue_Inst"
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
CLS = {k: f"{PIECES}PBWA_W1_{n}.PBWA_W1_{n}_C" for k, n in
       (("wall", "Solid"), ("floor", "Floor"), ("ramp", "StairW"), ("cone", "RoofC"))}
RAMP_YAW = {"S": 0.0, "E": 90.0, "N": 180.0, "W": 270.0}     # as build_fight_lab.py (measured 2026-10-09)
WALL_T = 40.0
LAB_CEIL = 6 * H                  # Fight Lab wall height (build_fight_lab.py CEIL)
ROOF = 4 * H                      # compound roof: tall enough to build for the high ground
L1_WALL = 2 * H
CRAWL = 140.0                     # gap under the crawl barrier, cm (VERIFY: crouch and slide fit, standing does not)
X0, X1 = -70 * C, -50 * C         # plate x -35840..-25600
YC0, YC1 = -136 * C, -131 * C     # compound (south strip) y -69632..-67072
YW1 = -129 * C                    # walkway y -67072..-66048; L1 strip starts here
YL1 = -124 * C                    # L1 north edge y -63488
DOOR_J = -134                     # every compound door is on this row (y -68608..-68096)
PARTITIONS = [-66 * C, -61 * C, -56 * C, -53 * C]   # R1|R2, R2|R3, R3|R4, R4|R5: x -33792, -31232, -28672, -27136
LAB_X = -50 * C                   # x -25600, the Fight Lab's west line
# Storm for L1: the edge starts at the east wall and stops short of the exit position.
STORM = {"start_x": LAB_X, "end_x": -66 * C, "seconds": 75.0, "damage": 5.0}
SIGN_TEXT = ("OPERATION\nL1 Zone edge  >  L2 Compound breach  >  L3 Towers\n"
             "Press START OPERATION. Each door opens when its room is clear.\n"
             "Die and you restart the room you were in. Best time on the board.")


def cell(i, j):
    return i * C + C / 2, j * C + C / 2


def door_y():
    return DOOR_J * C, (DOOR_J + 1) * C


class Plan:
    def __init__(self):
        self.slabs, self.pieces, self.devices, self.signs, self.stages = [], [], [], [], []

    def slab(self, label, x0, x1, y0, y1, top, thick, zone="Void"):
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

    def device(self, label, asset, x, y, z=0.0, props=None, yaw=None, tag=None, **extra):
        self.devices.append(dict({"label": PREFIX + label, "asset": asset, "pos": (x, y, z), "props": props or {},
                                   "yaw": yaw, "tag": tag}, **extra))

    def bot(self, label, i, j, z, accuracy, health=100, shield=0, yaw=180.0):
        x, y = cell(i, j)
        self.device(label, bm.GUARD, x, y, z, bot_props(accuracy, health, shield), yaw=yaw, tag="kt_op_bot_tag")

    def gate(self, label, x, y, along_x):
        """A blue barrier in a 1-cell doorway; along_x for a door in a wall that runs along x (yaw 90)."""
        self.device(label, BARRIER, x, y, 0.0, {"barrierWidth": 1.0, "barrierDepth": 0.1, "barrierHeight": ROOF / C,
                                                "zoneShape": "Box", "blockWeaponFire": True, "collide with Camera": False,
                                                "baseVisibleDuringGame": False, "barrierMaterial": {"refPath": GATE_MAT}},
                    yaw=90.0 if along_x else 0.0, tag="kt_op_gate_tag")

    def stage(self, name, level, instruction, box, checkpoint, gate=None, kind=0):
        self.stages.append({"name": name, "level": level, "instruction": instruction, "box": box,
                            "checkpoint": checkpoint, "gate": gate, "kind": kind})


def bot_props(accuracy, health, shield):
    return {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
            "enabledAtGameStart": False, "allowInfiniteSpawn": True, "spawnOnTimer": False, "spawnCount": 1,
            "showHealthBar": True, "startingHealth": health, "max Health": health, "startingShield": shield,
            "accuracy": accuracy, "enablePatrol": False, "useDeviceSpawnLocation": True}


def plan():
    p = Plan()
    dy0, dy1 = door_y()
    gate_y = (dy0 + dy1) / 2

    # ---- L1 ZONE EDGE: walled outdoor strip, open sky, exit at the west end onto the walkway. ----
    p.slab("L1_Wall_N", X0 - WALL_T, X1, YL1, YL1 + WALL_T, L1_WALL, L1_WALL + 100)
    p.slab("L1_Wall_W", X0 - WALL_T, X0, YW1, YL1, L1_WALL, L1_WALL + 100)
    p.slab("L1_Wall_S", -68 * C, X1, YW1 - WALL_T, YW1, L1_WALL, L1_WALL + 100)   # gap x -35840..-34816 = the exit
    for n, (i, j, e) in enumerate(((-55, -127, "W"), (-62, -126, "W"), (-63, -128, "W"), (-55, -125, "W"))):
        p.wall(f"L1_Cover_{n}", i, j, 0, e)                                      # your cover on the way west
    for n, (i, j) in enumerate(((-59, -128), (-59, -126), (-67, -127), (-67, -125))):
        p.wall(f"L1_BotCover_{n}", i, j, 0, "E")                                 # their cover faces east, at you
        p.bot(f"L1_Bot_{n}", i, j, 0.0, "LOW", yaw=0.0)
    p.stage("Zone edge", "L1 ZONE EDGE",
            "The storm closes from the east. Push west, clear both zone-edge positions, then get into the compound.",
            ((X0, YW1, -100.0), (X1, YL1, 1500.0)), (*cell(-52, -127), 0.0), gate=(-69 * C + C / 2, YC1), kind=1)

    # ---- L2 COMPOUND: enclosed, roofed, five rooms in a line, doors on row DOOR_J. ----
    p.slab("C_Wall_S", X0 - WALL_T, LAB_X, YC0 - WALL_T, YC0, ROOF, ROOF + 100)
    p.slab("C_Wall_W", X0 - WALL_T, X0, YC0, YC1, ROOF, ROOF + 100)
    p.slab("C_Wall_N0", X0, -69 * C, YC1, YC1 + WALL_T, ROOF, ROOF + 100)                 # door at i -69: way in
    p.slab("C_Wall_N1", -68 * C, LAB_X, YC1, YC1 + WALL_T, ROOF, ROOF + 100)
    p.slab("C_Roof", X0 - WALL_T, LAB_X, YC0 - WALL_T, YC1 + WALL_T, ROOF + 100, 100)
    for n, x in enumerate(PARTITIONS):
        p.slab(f"C_Part{n}_S", x - WALL_T / 2, x + WALL_T / 2, YC0, dy0, ROOF, ROOF + 100)
        p.slab(f"C_Part{n}_N", x - WALL_T / 2, x + WALL_T / 2, dy1, YC1, ROOF, ROOF + 100)
    p.gate("Gate_L1", -69 * C + C / 2, YC1, along_x=True)

    # Room 1 CRAWL (i -70..-67): a barrier across the room with a 1.4 m gap under it.
    p.slab("R1_Crawl", -68 * C, -67 * C, YC0, YC1, ROOF, ROOF - CRAWL)
    p.stage("Crawl", "L2 COMPOUND", "Room 1: crouch or slide under the barrier.",
            ((X0, YC0, -100.0), (PARTITIONS[0], YC1, ROOF)), (*cell(-69, -132), 0.0))

    # Room 2 GRENADE (i -66..-62): the nest behind a 2.2 m wall; the north cell is open for the clean-up.
    p.slab("R2_NestWall", -63 * C - WALL_T / 2, -63 * C + WALL_T / 2, YC0, -132 * C, 220.0, 220.0)
    for n, j in enumerate((-135, -134, -133)):
        p.bot(f"R2_Bot_{n}", -62, j, 0.0, "LOW")
    gx, _ = cell(-66, -136)
    p.device("R2_Grenades", GRANTER, gx, cell(-66, -136)[1], -400.0, tag="kt_op_grenade_tag", grant="EXPLOSIVES", qty=2)
    p.stage("Grenade", "L2 COMPOUND",
            "Room 2: lob a grenade over the wall into the nest, then clear the gap on the left.",
            ((PARTITIONS[0], YC0, -100.0), (PARTITIONS[1], YC1, ROOF)), (*cell(-66, DOOR_J), 0.0),
            gate=(PARTITIONS[1], gate_y), kind=2)
    p.gate("Gate_R2", PARTITIONS[1], gate_y, along_x=False)

    # Room 3 PEEK (i -61..-57): a cover line with one real wood wall in it; edit, shoot, reset.
    p.slab("R3_Cover_S", -60 * C - WALL_T / 2, -60 * C + WALL_T / 2, YC0, dy0, ROOF, ROOF)
    p.slab("R3_Cover_N", -60 * C - WALL_T / 2, -60 * C + WALL_T / 2, dy1, YC1, ROOF, ROOF)
    p.slab("R3_Cover_Top", -60 * C - WALL_T / 2, -60 * C + WALL_T / 2, dy0, dy1, ROOF, ROOF - H)
    p.wall("R3_EditWall", -60, DOOR_J, 0, "W")
    for n, j in enumerate((-135, -133)):
        p.bot(f"R3_Bot_{n}", -58, j, 0.0, "LOW")
    p.stage("Peek", "L2 COMPOUND", "Room 3: edit a window in your wall, hit your shot, reset. Two hold the far side.",
            ((PARTITIONS[1], YC0, -100.0), (PARTITIONS[2], YC1, ROOF)), (*cell(-61, DOOR_J), 0.0),
            gate=(PARTITIONS[2], gate_y))
    p.gate("Gate_R3", PARTITIONS[2], gate_y, along_x=False)

    # Room 4 HIGH GROUND (i -56..-54): their platform two levels up (i -55..-54, j -134..-133), reached by two ramps
    # climbing north along the south wall; cover on its west and north edges faces the door you come in by.
    p.flat("R4_Ramp0", "ramp", -55, -136, 0.0, RAMP_YAW["N"])
    p.flat("R4_Ramp1", "ramp", -55, -135, H, RAMP_YAW["N"])
    for i in (-55, -54):
        for j in (-134, -133):
            p.flat(f"R4_Floor_{-i}_{-j}", "floor", i, j, 2 * H)
        p.wall(f"R4_Wall_N{-i}", i, -133, 2, "N")
    p.wall("R4_Wall_Front", -55, -133, 2, "W")
    for n, j in enumerate((-134, -133)):
        p.bot(f"R4_Bot_{n}", -54, j, 2 * H + 20.0, "MEDIUM")
    p.stage("High ground", "L2 COMPOUND",
            "Room 4: they hold a built platform. Take height (their ramp or your own builds), then eliminate both.",
            ((PARTITIONS[2], YC0, -100.0), (PARTITIONS[3], YC1, ROOF)), (*cell(-56, DOOR_J), 0.0),
            gate=(PARTITIONS[3], gate_y))
    p.gate("Gate_R4", PARTITIONS[3], gate_y, along_x=False)

    # Room 5 BREACH (i -52..-51): two closed bot boxes beside the door; edit in, eliminate, the lab door opens.
    for n, j in enumerate((-135, -133)):
        for e in "NSEW":
            p.wall(f"R5_Box{n}_{e}", -52, j, 0, e)
        p.flat(f"R5_Box{n}_Cone", "cone", -52, j, H)
        p.bot(f"R5_Bot_{n}", -52, j, 0.0, "MEDIUM")
    p.stage("Breach", "L2 COMPOUND", "Room 5: their boxes guard the door. Edit in, eliminate both, breach into the towers.",
            ((PARTITIONS[3], YC0, -100.0), (LAB_X, YC1, ROOF)), (*cell(-51, DOOR_J), 0.0), gate=(LAB_X, gate_y))
    # Fight Lab room A's west wall, restored with the door into L3 (no ceiling: the sky stays open).
    p.slab("LabWall_W_S0", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, YC0, dy0, LAB_CEIL, LAB_CEIL + 100, "Scenario")
    p.slab("LabWall_W_S1", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, dy1, YC1, LAB_CEIL, LAB_CEIL + 100, "Scenario")
    p.slab("LabWall_W_Lintel", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, dy0, dy1, LAB_CEIL, LAB_CEIL - ROOF, "Scenario")
    p.gate("Gate_R5", LAB_X, gate_y, along_x=False)

    # ---- L3 TOWERS (Fight Lab room A, x -25600..-20480). The climb and drop tower tops carry the lab's rifts, so the
    # bots get two new two-level perches on the free north row, each with cover on its west (your) side at the top:
    # you have to take height on them (build, or climb a tower and edit out), not shoot up from the floor. ----
    for n, i in enumerate((-49, -44)):
        for k in (0, 1):
            for e in "NSEW":
                p.wall(f"L3_Perch{n}_{k}{e}", i, -132, k, e)
        p.flat(f"L3_Perch{n}_Top", "floor", i, -132, 2 * H)
        p.wall(f"L3_Perch{n}_Cover", i, -132, 2, "W")
        p.bot(f"L3_Bot_{n}", i, -132, 2 * H + 20.0, "HIGH", health=150)
    p.stage("Towers", "L3 TOWERS",
            "Last: two bots hold walled perches behind cover. Take height on them (build or climb and edit out), eliminate both.",
            ((LAB_X, YC0, -100.0), (-40 * C, YC1, 2600.0)), (*cell(-50, DOOR_J), 0.0))

    # ---- Start, loadout, run device, signs (on the walkway by the portal). ----
    sx, sy = -34560.0, -66816.0
    p.device("Start", bm.BUTTON, sx, sy, 0.0, {"interaction Text": "START OPERATION", "delay": 0.0, "resetDelay": 0.5},
             yaw=0.0, tag="kt_op_start_tag")
    p.device("Loadout", GRANTER, sx, sy, -400.0, tag="kt_op_loadout_tag", grant=("AR", "SHOTGUN", "HEALS"), qty=1)
    p.device("Device", DEVICE, -30720.0, -66560.0, -150.0, tag="kt_op_device_tag")
    p.signs.append({"label": PREFIX + "Sign_Start", "pos": (sx + 600, sy, 300), "yaw": 180, "zone": "Scenario",
                    "size": 26, "text": SIGN_TEXT})
    room_signs = [("Sign_R1", -69, "1  CRAWL\nCrouch or slide under the barrier"),
                  ("Sign_R2", -65, "2  GRENADE\nLob it over the wall, then clear the gap"),
                  ("Sign_R3", -61, "3  PEEK\nEdit, shoot, reset"),
                  ("Sign_R4", -56, "4  HIGH GROUND\nTake height first"),
                  ("Sign_R5", -52, "5  BREACH\nEdit in, eliminate, door opens")]
    for label, i, text in room_signs:
        x, _ = cell(i, -136)
        p.signs.append({"label": PREFIX + label, "pos": (x, YC0 + 120, 260), "yaw": 90, "zone": "Scenario",
                        "size": 30, "text": text})
    return p


# Removed so the plate is free (all backed up first): the empty "opening next" bays and the four ANGLE labs.
OLD = [f"KT_Bay_S{k}" for k in range(1, 5)] + [f"KT_Sign_Bay_S{k}" for k in range(1, 5)] + \
      [f"KT3_Upgrade_Scenario_{n}_{s}" for n in range(4) for s in ("Corner", "Angle", "Target", "Brief")]
RETEXT = {"KT_Sign_Area_Scenario": "OPERATION\nL1 zone edge  L2 compound  L3 towers\nstart button beside you; "
                                   "the pad behind you returns to the hub",
          "KT_Sign_Gate_Scenario": "OPERATION\nScenario expansion: a three-level run"}


def verse_vec(v):
    return "vector3{X := %.1f, Y := %.1f, Z := %.1f}" % v


def verse_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_verse(p):
    lines = ["# GENERATED by tools/build_operation.py (the same plan that places the level). Do not edit by hand.",
             "# One entry per room of the Operation, in play order. Operation.verse assigns each tagged bot to the stage",
             "# whose box holds it and each gate to the stage whose Gate point is nearest; Kind 1 = storm, 2 = grenades.",
             "",
             "using { /UnrealEngine.com/Temporary/SpatialMath }",
             "",
             "kt_op_stage<public> := struct<computes>:",
             "    Name<public>:string = \"\"",
             "    Level<public>:string = \"\"",
             "    Instruction<public>:string = \"\"",
             "    Lo<public>:vector3 = vector3{}",   # room box corners; Min/Max clash with the built-in functions
             "    Hi<public>:vector3 = vector3{}",
             "    Checkpoint<public>:vector3 = vector3{}",
             "    HasGate<public>:logic = false",
             "    Gate<public>:vector3 = vector3{}",
             "    Kind<public>:int = 0",
             "",
             f"KTOpStormStartX<public>:float = {STORM['start_x']:.1f}",
             f"KTOpStormEndX<public>:float = {STORM['end_x']:.1f}",
             f"KTOpStormSeconds<public>:float = {STORM['seconds']:.1f}",
             f"KTOpStormDamage<public>:float = {STORM['damage']:.1f}",
             "",
             "KTOpStages<public>:[]kt_op_stage = array:"]
    for s in p.stages:
        (mn, mx), gate = s["box"], s["gate"]
        g = f", HasGate := true, Gate := {verse_vec((gate[0], gate[1], 0.0))}" if gate else ""
        lines.append(f"    kt_op_stage{{Name := {verse_str(s['name'])}, Level := {verse_str(s['level'])}, "
                     f"Instruction := {verse_str(s['instruction'])}, Lo := {verse_vec(mn)}, Hi := {verse_vec(mx)}, "
                     f"Checkpoint := {verse_vec(s['checkpoint'])}{g}, Kind := {s['kind']}}}")
    return "\n".join(lines) + "\n"


def check(p):
    """Every bot sits in exactly one stage box, every gate point has a barrier, every checkpoint is inside its box."""
    errors = []
    inside = lambda pos, box: all(box[0][k] <= pos[k] <= box[1][k] for k in range(3))
    for d in p.devices:
        if d["tag"] == "kt_op_bot_tag":
            n = sum(inside(d["pos"], s["box"]) for s in p.stages)
            if n != 1:
                errors.append(f"{d['label']} is in {n} stage boxes")
    gates = [d["pos"] for d in p.devices if d["tag"] == "kt_op_gate_tag"]
    for s in p.stages:
        if not inside(s["checkpoint"], s["box"]):
            errors.append(f"checkpoint of {s['name']} is outside its box")
        if s["gate"] and not any(math.dist(s["gate"], g[:2]) < 1.0 for g in gates):
            errors.append(f"no barrier at the gate of {s['name']}")
    return errors


def place(b, p):
    found = b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []
    by_label = {a["label"]: a["actorPath"] for a in found}
    gone = [a for a in found if a["label"].startswith(PREFIX) or a["label"] in OLD]
    backup = bm.ROOT / "backups" / f"operation-{datetime.date.today()}"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / f"removed-{datetime.datetime.now():%H%M%S}.json").write_text(
        json.dumps([{"label": a["label"], "path": a["actorPath"], "bounds": a.get("bounds")} for a in gone], indent=1))
    for a in gone:
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(gone)} actors (backup in {backup})")
    saved, refused = [], []
    for s in p.slabs:
        saved.append(b.slab(s))
    for pc in p.pieces:
        x, y, z, yaw = pc["xf"]
        ref = b.m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": pc["cls"]}, name=pc["label"],
                       xform=bm.xform(x, y, z, yaw=yaw))
        path = b.labelled(ref["refPath"], pc["label"])
        b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True})
        saved.append(path)
    loadout = json.loads((bm.ROOT / "shared" / "practice-loadout.json").read_text(encoding="utf-8"))["items"]
    for d in p.devices:
        x, y, z = d["pos"]
        path = b.device(d["asset"], d["label"], x, y, z)
        if d["yaw"] is not None:
            b.face(path, d["yaw"])
        for key, value in d["props"].items():
            try:
                b.props(path, {key: value})
            except RuntimeError as exc:
                refused.append(f"{d['label']}: {key} ({str(exc)[-60:]})")
        if d.get("grant"):
            names = d["grant"] if isinstance(d["grant"], tuple) else (d["grant"],)
            clear = "Clear All" if d["tag"] == "kt_op_loadout_tag" else "Keep All"
            for key, value in {"onGrantAction": clear, "grant": "All Items", "grantCondition": "Always",
                               "bEquipGrantedItem": d["tag"] == "kt_op_loadout_tag"}.items():
                try:
                    b.props(path, {key: value})
                except RuntimeError as exc:
                    refused.append(f"{d['label']}: {key} ({str(exc)[-50:]})")
            raw = b.m.tool(bm.OBJ, "get_properties", instance={"refPath": path}, properties=["pickupItemList"])
            items = (json.loads(raw) if isinstance(raw, str) else raw)["pickupItemList"]
            b.m.tool(bm.OBJ, "reset_properties", instance=items, properties=["itemListData"])
            b.props(items["refPath"], {"itemListData": [{"itemDefinition": {"refPath": loadout[k]}, "itemQuantity": d["qty"]}
                                                        for k in names]})
        if d["tag"]:
            b.tag(path, d["tag"])
        saved.append(path)
    for s in p.signs:
        saved.append(b.sign(s))
    for label, text in RETEXT.items():
        if label in by_label:
            b.props(by_label[label], {"text": text})
            saved.append(by_label[label])
    for path in saved:
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print(f"operation placed: {len(p.slabs)} slabs, {len(p.pieces)} pieces, {len(p.devices)} devices, {len(p.signs)} signs")
    if refused:
        print("not accepted (set these in UEFN by hand):\n  " + "\n  ".join(refused))


OUT_VERSE = bm.ROOT / "verse" / "KeystrokeTrainer" / "OperationLayout.verse"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-verse", action="store_true", help="only regenerate OperationLayout.verse")
    args = ap.parse_args()
    p = plan()
    errors = check(p)
    print(f"plan: {len(p.slabs)} slabs, {len(p.pieces)} pieces, {len(p.devices)} devices, {len(p.signs)} signs, "
          f"{len(p.stages)} stages")
    for n, s in enumerate(p.stages):
        bots = sum(1 for d in p.devices if d["tag"] == "kt_op_bot_tag" and
                   all(s["box"][0][k] <= d["pos"][k] <= s["box"][1][k] for k in range(3)))
        print(f"  {n} {s['level']:<12} {s['name']:<12} bots {bots}  gate {'yes' if s['gate'] else 'no '}  kind {s['kind']}")
    if errors:
        print("\n".join(errors))
        return 1
    OUT_VERSE.write_text(render_verse(p), encoding="utf-8", newline="\n")
    print("wrote", OUT_VERSE.name)
    if args.dry_run or args.write_verse:
        return 0
    place(bm.Builder(), p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
