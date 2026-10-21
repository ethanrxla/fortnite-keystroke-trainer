"""Operation: the Scenario Expansion as one linear three-level game level (design/operation-level-design.md). KT16_Op_*.

Player 2026-10-21: "one long pipeline rather than users being able to enter multiple places at once". Since then:
  * the only way in is the hub portal / OPERATION sign, landing in the crawl room (KT16_Op_Arrive); arriving starts a
    run. The outdoor storm strip (old L1), the walkway door, the START button and the Fight Lab's own start rifts,
    bots and title sign are gone; the Fight Lab spine is closed at its west end (KT16_Op_SpineEnd);
  * the four Fight Lab rooms are stages of the run, entered in order through gated doorways off the spine:
      L1 COMPOUND  crawl, grenade (2 bots), peek (1 bot, left or right at random), high ground, breach
      L2 FIGHT LAB A towers (a bot on each tower top), C retake, D box fight, B peek and reset
      L3 BOMBSITE  entered from room B; clear, plant at the bomb console (hold to plant), hold the retake, extract;
  * the enemy's pieces (high-ground platform, retake platform, their box and cover) are team 2 builds, not editable.
  A second player may follow the runner through the open doors; one run at a time.
The history below describes how the level was first laid out.

    python tools/build_operation.py --dry-run       # print the plan and the stage table
    python tools/build_operation.py --write-verse   # only regenerate verse/KeystrokeTrainer/OperationLayout.verse
    python tools/build_operation.py                 # (re)place it: removes KT16_Op_* actors, the old S1..S4 bays and
                                                    # their signs and the four ANGLE free-practice labs (backed up)
    python tools/build_operation.py --site-only     # (re)place only bombsite A (KT16_Op_Site_*), keep everything else
    then BuildAll; the run is driven by Operation.verse (kt_operation_device)

Player 2026-10-11: the Scenario Expansion becomes the island's one real game level, built only from existing areas:
  L1 ZONE EDGE  north strip of the Scenario plate, outdoors, walled: the storm closes from the east; push west and
                clear two zone-edge positions (4 bots behind cover), then cross into the compound.
  L2 COMPOUND   south strip, enclosed and roofed, in the style of the Counter-Strike intro training course: one skill
                per room in a straight line, the next door opens only when the room is done:
                  1 crawl under the barrier (crouch or slide)  2 grenade the nest over its wall, clean up the gap
                  3 edit a window in your wall, peek, reset    4 retake the high ground (bots on a built platform)
                  5 breach their boxes, then the door into the towers.
  L3 TOWERS     Fight Lab room A: bots on top of the climb and drop towers; eliminate both, then south to the site.
  L4 BOMBSITE A (player 2026-10-20: "go with the bombsite plan", a Counter-Strike style ending) on the empty ground
                south of Fight Lab rooms A and B (x -25600..-15360, y -74752..-69632): two entrances from the towers
                (main and short), crates for cover, the A plant zone. Stages: clear the three defenders, plant (stand on
                the A plate PlantSeconds), hold the site while a retake wave comes until the bomb timer runs out, then
                reach the extraction corner (south-west), where the EXIT plate takes you to the hub
                (tools/build_room_exits.py "OpExtract"). Its pieces sit on the player build grid (cells centred on
                multiples of 512), unlike the older rooms.
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
METAL = "/Game/Building/ActorBlueprints/Player/Metal/L1/"
CLS.update({"mwall": f"{METAL}PBWA_M1_Solid.PBWA_M1_Solid_C", "mfloor": f"{METAL}PBWA_M1_Floor.PBWA_M1_Floor_C",
            "mramp": f"{METAL}PBWA_M1_StairW.PBWA_M1_StairW_C"})
# Bombsite A: the strip south of Fight Lab rooms A and B, open to room A on its north side.
SITE_X0, SITE_X1, SITE_Y0, SITE_Y1 = -50 * C, -30 * C, -146 * C, -136 * C     # x -25600..-15360, y -74752..-69632
SITE_WALL = 2 * H
PLANT = (-19712.0, -17664.0, -73472.0, -71424.0)      # the A plate: 4 x 4 player cells
EXTRACT = (SITE_X0, -24576.0, SITE_Y0, -73728.0)      # south-west corner, 2 x 2 cells, beside the EXIT plate
CONSOLE = (-18176.0, -72960.0)                        # the bomb console, on the plate clear of the Default crate
PLANT_HOLD = 5.0                                      # seconds to hold the plant button
ENEMY_TEAM = {"Team": "HumanPvP_Team2", "TeamIndex": 4}   # site crates: theirs, not editable (Creative team 2)
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
# Storm (Kind 1) is unused since the storm strip went (2026-10-21); Operation.verse still reads the constants.
STORM = {"start_x": LAB_X, "end_x": -66 * C, "seconds": 75.0, "damage": 5.0}
# The Fight Lab (tools/build_fight_lab.py): its rooms use cell(i, j) centred at i*512 + 256; the spine is j -131..-130.
SPINE_Y0, SPINE_Y1 = -131 * C, -129 * C           # y -67072..-66048
LAB_MID = -40 * C                                  # x -20480, between the west rooms (A, C) and the east rooms (B, D)
LAB_X1 = -30 * C                                   # x -15360, the lab's east wall
LAB_DOORS = {"A": (-46, -45), "B": (-36, -35), "C": (-46, -45), "D": (-36, -35)}   # build_fight_lab.DOORS
SITE_DOORS = (-40, -31)                            # one-cell doors from room B into the site (west, east)
# Pieces of the Fight Lab that belong to the enemy: team 2, so the player cannot edit them (player 2026-10-21).
LAB_ENEMY = ("KT7_Lab_C_Plat_", "KT7_Lab_C_PlatWall_", "KT7_Lab_C_EnemyRamp", "KT7_Lab_C_EnemyCone",
             "KT7_Lab_D_BotBox_", "KT7_Lab_B_BotCover_")


def cell(i, j):
    return i * C + C / 2, j * C + C / 2


def door_y():
    return DOOR_J * C, (DOOR_J + 1) * C


class Plan:
    def __init__(self):
        self.slabs, self.pieces, self.devices, self.signs, self.stages = [], [], [], [], []

    def slab(self, label, x0, x1, y0, y1, top, thick, zone="Void"):
        self.slabs.append({"label": PREFIX + label, "bounds": (x0, x1, y0, y1), "top": top, "thick": thick, "mat": zone})

    def piece(self, label, kind, x, y, z, yaw, props=None):
        self.pieces.append({"label": PREFIX + label, "cls": CLS[kind], "xf": (x, y, z, yaw), "props": props or {}})

    def crate(self, label, i, j, levels=1):
        """A metal crate on the player grid: cell (i, j) centred at (i*512, j*512), 4 walls and a lid per level."""
        x, y = i * C, j * C
        for k in range(levels):
            for e, (dx, dy, yaw) in {"N": (0, C / 2, 0.0), "S": (0, -C / 2, 0.0), "E": (C / 2, 0, 90.0),
                                     "W": (-C / 2, 0, 90.0)}.items():
                self.piece(f"{label}_{k}{e}", "mwall", x + dx, y + dy, k * H, yaw, ENEMY_TEAM)
            self.piece(f"{label}_{k}Lid", "mfloor", x, y - C / 2, (k + 1) * H, 0.0, ENEMY_TEAM)

    def wall(self, label, i, j, k, edge, props=None):
        cx, cy = cell(i, j)
        if edge in "WE":
            self.piece(label, "wall", cx + (-C / 2 if edge == "W" else C / 2), cy, k * H, 90.0, props)
        else:
            self.piece(label, "wall", cx, cy + (-C / 2 if edge == "S" else C / 2), k * H, 0.0, props)

    def flat(self, label, kind, i, j, z, yaw=0.0, props=None):
        r = math.radians(yaw)
        dx, dy = -math.sin(r), math.cos(r)
        cx, cy = cell(i, j)
        self.piece(label, kind, cx - dx * C / 2, cy - dy * C / 2, z, yaw, props)

    def device(self, label, asset, x, y, z=0.0, props=None, yaw=None, tag=None, **extra):
        self.devices.append(dict({"label": PREFIX + label, "asset": asset, "pos": (x, y, z), "props": props or {},
                                   "yaw": yaw, "tag": tag}, **extra))

    def bot(self, label, i, j, z, accuracy, health=100, shield=0, yaw=180.0, tag="kt_op_bot_tag", grid=False):
        x, y = (i * C, j * C) if grid else cell(i, j)
        self.device(label, bm.GUARD, x, y, z, bot_props(accuracy, health, shield), yaw=yaw, tag=tag)

    def gate(self, label, x, y, along_x, cells=1.0, height=ROOF):
        """A blue barrier in a doorway cells wide; along_x for a door in a wall that runs along x (yaw 90). It fills the
        doorway to the top of its wall (height), so it cannot be climbed or built over."""
        self.device(label, BARRIER, x, y, 0.0, {"barrierWidth": cells, "barrierDepth": 0.1, "barrierHeight": height / C,
                                                "zoneShape": "Box", "blockWeaponFire": True, "collide with Camera": False,
                                                "baseVisibleDuringGame": False, "barrierMaterial": {"refPath": GATE_MAT}},
                    yaw=90.0 if along_x else 0.0, tag="kt_op_gate_tag")

    def stage(self, name, level, instruction, box, checkpoint, gate=None, kind=0, pick=0):
        """gate: the (x, y) of the barrier that opens when the stage is clear, or a list of them. pick: spawn only
        this many of the stage's bots, chosen at random each time (0 = all)."""
        gates = [] if gate is None else list(gate) if isinstance(gate, list) else [gate]
        self.stages.append({"name": name, "level": level, "instruction": instruction, "box": box,
                            "checkpoint": checkpoint, "gates": gates, "kind": kind, "pick": pick})


def bot_props(accuracy, health, shield):
    return {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
            "enabledAtGameStart": False, "allowInfiniteSpawn": True, "spawnOnTimer": False, "spawnCount": 1,
            "showHealthBar": True, "startingHealth": health, "max Health": health, "startingShield": shield,
            "accuracy": accuracy, "enablePatrol": False, "useDeviceSpawnLocation": True,
            "spawnRadius_InMeter": 0}       # hold their spot, not anywhere within 10 m (2026-10-20)


def plan():
    p = Plan()
    dy0, dy1 = door_y()
    gate_y = (dy0 + dy1) / 2
    team2 = ENEMY_TEAM

    # ---- L1 COMPOUND: enclosed, roofed, five rooms in a line, doors on row DOOR_J. Closed on every side but the
    # door into the Fight Lab: you arrive in room 1 (KT16_Op_Arrive), there is no way in on foot. ----
    p.slab("C_Wall_S", X0 - WALL_T, LAB_X, YC0 - WALL_T, YC0, ROOF, ROOF + 100)
    p.slab("C_Wall_W", X0 - WALL_T, X0, YC0, YC1, ROOF, ROOF + 100)
    p.slab("C_Wall_N", X0 - WALL_T, LAB_X, YC1, YC1 + WALL_T, ROOF, ROOF + 100)
    p.slab("C_Roof", X0 - WALL_T, LAB_X, YC0 - WALL_T, YC1 + WALL_T, ROOF + 100, 100)
    for n, x in enumerate(PARTITIONS):
        p.slab(f"C_Part{n}_S", x - WALL_T / 2, x + WALL_T / 2, YC0, dy0, ROOF, ROOF + 100)
        p.slab(f"C_Part{n}_N", x - WALL_T / 2, x + WALL_T / 2, dy1, YC1, ROOF, ROOF + 100)

    # Room 1 CRAWL (i -70..-67): a barrier across the room with a 1.4 m gap under it. The run starts here.
    p.slab("R1_Crawl", -68 * C, -67 * C, YC0, YC1, ROOF, ROOF - CRAWL)
    p.stage("Crawl", "L1 COMPOUND", "Room 1: crouch or slide under the barrier.",
            ((X0, YC0, -100.0), (PARTITIONS[0], YC1, ROOF)), (*cell(-69, -132), 0.0))

    # Room 2 GRENADE (i -66..-62): two bots behind a 2.2 m wall; the north cell is open for the clean-up.
    p.slab("R2_NestWall", -63 * C - WALL_T / 2, -63 * C + WALL_T / 2, YC0, -132 * C, 220.0, 220.0)
    for n, j in enumerate((-135, -133)):
        p.bot(f"R2_Bot_{n}", -62, j, 0.0, "VERY HIGH")
    # Grenades lie on the floor (player 2026-10-21: "switch it so that they are on the floor"): two pickups where the
    # run starts and two at the grenade room's door, each back 5 s after it is taken.
    for n, (x, y) in enumerate(((-35328.0, -68352.0), (-35072.0, -68864.0), (*cell(-66, -135),), (*cell(-66, -133),))):
        p.device(f"Nade_{n}", bm.ITEM_SPAWNER, x, y, 0.0, spawn="EXPLOSIVES")
    p.stage("Grenade", "L1 COMPOUND",
            "Room 2: two behind the wall. Lob a grenade over it, then clear the gap on the left.",
            ((PARTITIONS[0], YC0, -100.0), (PARTITIONS[1], YC1, ROOF)), (*cell(-66, DOOR_J), 0.0),
            gate=(PARTITIONS[1], gate_y), kind=2)
    p.gate("Gate_R2", PARTITIONS[1], gate_y, along_x=False)

    # Room 3 PEEK (i -61..-57): a cover line with one real wood wall in it; one bot, on the left or the right at random.
    p.slab("R3_Cover_S", -60 * C - WALL_T / 2, -60 * C + WALL_T / 2, YC0, dy0, ROOF, ROOF)
    p.slab("R3_Cover_N", -60 * C - WALL_T / 2, -60 * C + WALL_T / 2, dy1, YC1, ROOF, ROOF)
    p.slab("R3_Cover_Top", -60 * C - WALL_T / 2, -60 * C + WALL_T / 2, dy0, dy1, ROOF, ROOF - H)
    p.wall("R3_EditWall", -60, DOOR_J, 0, "W")
    for n, j in enumerate((-135, -133)):
        p.bot(f"R3_Bot_{n}", -58, j, 0.0, "VERY HIGH")
    p.stage("Peek", "L1 COMPOUND", "Room 3: one holds the far side, left or right. Edit a window, hit your shot, reset.",
            ((PARTITIONS[1], YC0, -100.0), (PARTITIONS[2], YC1, ROOF)), (*cell(-61, DOOR_J), 0.0),
            gate=(PARTITIONS[2], gate_y), pick=1)
    p.gate("Gate_R3", PARTITIONS[2], gate_y, along_x=False)

    # Room 4 HIGH GROUND (i -56..-54): their platform two levels up (i -55..-54, j -134..-133), reached by two ramps
    # climbing north along the south wall; cover on its west and north edges. All of it is theirs (team 2).
    p.flat("R4_Ramp0", "ramp", -55, -136, 0.0, RAMP_YAW["N"], team2)
    p.flat("R4_Ramp1", "ramp", -55, -135, H, RAMP_YAW["N"], team2)
    for i in (-55, -54):
        for j in (-134, -133):
            p.flat(f"R4_Floor_{-i}_{-j}", "floor", i, j, 2 * H, props=team2)
        p.wall(f"R4_Wall_N{-i}", i, -133, 2, "N", team2)
    p.wall("R4_Wall_Front", -55, -133, 2, "W", team2)
    for n, j in enumerate((-134, -133)):
        p.bot(f"R4_Bot_{n}", -54, j, 2 * H + 20.0, "VERY HIGH")
    p.stage("High ground", "L1 COMPOUND",
            "Room 4: they hold a built platform. Take height (their ramp or your own builds), then eliminate both.",
            ((PARTITIONS[2], YC0, -100.0), (PARTITIONS[3], YC1, ROOF)), (*cell(-56, DOOR_J), 0.0),
            gate=(PARTITIONS[3], gate_y))
    p.gate("Gate_R4", PARTITIONS[3], gate_y, along_x=False)

    # Room 5 BREACH (i -52..-51): two closed bot boxes beside the door; edit in, eliminate, the lab door opens.
    for n, j in enumerate((-135, -133)):
        for e in "NSEW":
            p.wall(f"R5_Box{n}_{e}", -52, j, 0, e)
        p.flat(f"R5_Box{n}_Cone", "cone", -52, j, H)
        p.bot(f"R5_Bot_{n}", -52, j, 0.0, "VERY HIGH")
    p.stage("Breach", "L1 COMPOUND", "Room 5: their boxes guard the door. Edit in, eliminate both, breach into the lab.",
            ((PARTITIONS[3], YC0, -100.0), (LAB_X, YC1, ROOF)), (*cell(-51, DOOR_J), 0.0), gate=(LAB_X, gate_y))
    # Fight Lab room A's west wall, restored with the door into L2 (no ceiling: the sky stays open).
    p.slab("LabWall_W_S0", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, YC0, dy0, LAB_CEIL, LAB_CEIL + 100, "Scenario")
    p.slab("LabWall_W_S1", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, dy1, YC1, LAB_CEIL, LAB_CEIL + 100, "Scenario")
    p.slab("LabWall_W_Lintel", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, dy0, dy1, LAB_CEIL, LAB_CEIL - ROOF, "Scenario")
    p.gate("Gate_R5", LAB_X, gate_y, along_x=False)
    # The spine's west end (it used to open onto the walkway and the Scenario portal): closed.
    p.slab("SpineEnd", LAB_X - WALL_T / 2, LAB_X + WALL_T / 2, SPINE_Y0, SPINE_Y1, LAB_CEIL, LAB_CEIL + 100, "Scenario")

    # ---- L2 FIGHT LAB: rooms A, C, D, B in that order. Each room's doorway onto the spine is gated by the room
    # before it, so the spine never offers a choice. Lab geometry is tools/build_fight_lab.py's (KT7_Lab_*). ----
    def lab_door(room):
        a, b_ = LAB_DOORS[room]
        return ((a * C + (b_ + 1) * C) / 2, SPINE_Y0 if room in "AB" else SPINE_Y1)

    def lab_box(x0, x1, y0, y1):
        return ((x0, y0, -100.0), (x1, y1, 2600.0))

    labn_y0, labn_y1 = SPINE_Y1, -124 * C                     # north rooms C, D: y -66048..-63488
    # A TOWERS: a bot on top of each tower (player 2026-10-21: "bot here"): edit your way up, take them.
    p.bot("A_Bot_Drop", -42, -135, 3 * H + 20.0, "VERY HIGH", health=150)
    p.bot("A_Bot_Climb", -45, -135, 4 * H + 20.0, "VERY HIGH", health=150)
    door_c = lab_door("C")
    p.stage("Towers", "L2 FIGHT LAB",
            "Room A: one on top of each tower. Edit your way up (or build), eliminate both. Then room C, across the hall.",
            lab_box(LAB_X, LAB_MID, YC0, YC1), (*cell(-50, DOOR_J), 0.0), gate=door_c)
    p.gate("Gate_LabC", *door_c, along_x=True, cells=2.0, height=LAB_CEIL)
    # C RETAKE: their ramp, cone and two-level platform (team 2 since 2026-10-21), a bot on the platform.
    p.bot("C_Bot", -42, -127, 2 * H + 20.0, "VERY HIGH", health=150)
    door_d = lab_door("D")
    p.stage("Retake", "L2 FIGHT LAB",
            "Room C: they own the platform. Wall their ramp, go up a layer, own the height, eliminate them.",
            lab_box(LAB_X, LAB_MID, labn_y0, labn_y1), (door_c[0], labn_y0 + 256.0, 0.0), gate=door_d)
    p.gate("Gate_LabD", *door_d, along_x=True, cells=2.0, height=LAB_CEIL)
    # D BOX FIGHT: your closed box against theirs.
    p.bot("D_Bot", -33, -127, 0.0, "VERY HIGH")
    door_b = lab_door("B")
    p.stage("Box fight", "L2 FIGHT LAB",
            "Room D: box up in yours, edit out, trade, re-box. Take their box.",
            lab_box(LAB_MID, LAB_X1, labn_y0, labn_y1), (door_d[0], labn_y0 + 256.0, 0.0), gate=door_b)
    p.gate("Gate_LabB", *door_b, along_x=True, cells=2.0, height=LAB_CEIL)
    # B PEEK AND RESET: two behind their cover; the doors into the site are behind them.
    for n, j in enumerate((-135, -133)):
        p.bot(f"B_Bot_{n}", -32, j, 0.0, "VERY HIGH")
    site_gates = [(i * C + C / 2, SITE_Y1) for i in SITE_DOORS]
    p.stage("Peek and reset", "L2 FIGHT LAB",
            "Room B: two hold the far wall. Edit, shoot, reset. The doors to bombsite A are behind them.",
            lab_box(LAB_MID, LAB_X1, YC0, YC1), (door_b[0], SPINE_Y0 - 256.0, 0.0), gate=site_gates)
    for n, (x, y) in enumerate(site_gates):
        p.gate(f"Gate_Site{n}", x, y, along_x=True, height=LAB_CEIL)
    site(p)

    # ---- Loadout and run device (out of the play space, under the old walkway). ----
    p.device("Loadout", GRANTER, -34560.0, -66816.0, -400.0, tag="kt_op_loadout_tag", grant=("AR", "SHOTGUN", "HEALS"),
             qty=1)
    p.device("Device", DEVICE, -30720.0, -66560.0, -150.0, tag="kt_op_device_tag")
    # Arrival in the crawl room (player 2026-10-21: "they should spawn in that room to the left where you have to
    # crouch"): the OPERATION sign and the hub portal land here, and arriving starts a run (Operation.verse).
    ax, ay = cell(-69, -132)
    p.device("Arrive", bm.TELEPORTER, ax, ay - 256.0, 15.0, {"knob_TeleporterGroup": "Group_None",
             "knob_TargetTeleporterGroup": "Group_None", "teleporter Rift Visible": False, "maintain Relative Position": False,
             "conserve Momentum": False, "enabledDuringPhase": "Always"}, yaw=270.0, tag="kt_op_arrive_tag")
    room_signs = [("Sign_R1", -69, "1  CRAWL\nCrouch or slide under the barrier"),
                  ("Sign_R2", -65, "2  GRENADE\nLob it over the wall, then clear the gap"),
                  ("Sign_R3", -61, "3  PEEK\nOne bot, left or right. Edit, shoot, reset"),
                  ("Sign_R4", -56, "4  HIGH GROUND\nTake height first"),
                  ("Sign_R5", -52, "5  BREACH\nEdit in, eliminate, door opens")]
    for label, i, text in room_signs:
        x, _ = cell(i, -136)
        p.signs.append({"label": PREFIX + label, "pos": (x, YC0 + 120, 260), "yaw": 90, "zone": "Scenario",
                        "size": 30, "text": text})
    p.signs.append({"label": PREFIX + "Sign_Brief", "pos": (X0 + 120, -68096.0, 330), "yaw": 0, "zone": "Scenario",
                    "size": 24, "text": "OPERATION\nCompound > Fight Lab > Bombsite A, one room at a time.\n"
                                        "Each door opens when its room is clear. Die and you restart that room.\n"
                                        "Shoot EXIT to leave."})
    return p


def site(p):
    """L3 BOMBSITE A, Counter-Strike style: two doors in from Fight Lab room B (SITE_DOORS, gated by room B), crates,
    the A plate with its bomb console, defenders, a retake wave, extraction in the south-west corner. Player build
    grid: cell (i, j) is centred at (i*512, j*512)."""
    x0, x1, y0, y1 = SITE_X0, SITE_X1, SITE_Y0, SITE_Y1
    p.slab("Site_Floor", x0, x1, y0, y1, 0.0, 100.0, "Scenario")
    # Outer walls. North: closed to room A (2026-10-21, no second way in), two one-cell doors from room B.
    p.slab("Site_Wall_S", x0 - WALL_T, x1 + WALL_T, y0 - WALL_T, y0, SITE_WALL, SITE_WALL + 100)
    p.slab("Site_Wall_W", x0 - WALL_T, x0, y0, y1, SITE_WALL, SITE_WALL + 100)
    p.slab("Site_Wall_E", x1, x1 + WALL_T, y0, y1, SITE_WALL, SITE_WALL + 100)
    # As tall as the Fight Lab's walls, so nobody builds over from room B instead of using the gated doors.
    p.slab("Site_Wall_N_A", x0, LAB_MID, y1 - WALL_T, y1, LAB_CEIL, LAB_CEIL + 100)
    edges = [LAB_MID] + [v for i in SITE_DOORS for v in (i * C, (i + 1) * C)] + [x1]
    for n in range(0, len(edges), 2):
        if edges[n + 1] > edges[n]:
            p.slab(f"Site_Wall_N_B{n // 2}", edges[n], edges[n + 1], y1 - WALL_T, y1, LAB_CEIL, LAB_CEIL + 100)
    # The A plate (orange) and the extraction pad (green), painted on the floor.
    p.slab("Site_Plate_A", *PLANT, 6.0, 6.0, "Edit")
    # The plant zone, marked so it reads from the doors (player 2026-10-21: "clearly defined with props / controls"):
    # an orange post at each corner of the plate, and the bomb console on it: a pedestal with a hold-to-plant button
    # (Operation.verse kt_op_plant_tag; it only works during the plant stage).
    for n, (px, py) in enumerate(((PLANT[0], PLANT[2]), (PLANT[0], PLANT[3]), (PLANT[1], PLANT[2]), (PLANT[1], PLANT[3]))):
        p.slab(f"Site_Post_{n}", px - 30, px + 30, py - 30, py + 30, 360.0, 360.0, "Edit")
    cx, cy = CONSOLE
    p.slab("Site_Console", cx - 70, cx + 70, cy - 70, cy + 70, 110.0, 110.0, "Arena")
    p.device("Site_PlantButton", bm.BUTTON, cx, cy + 90.0, 0.0,
             {"interaction Text": "PLANT THE BOMB", "interactTime": PLANT_HOLD, "delay": 0.0, "resetDelay": 0.5},
             yaw=90.0, tag="kt_op_plant_tag")
    p.slab("Site_Extract", *EXTRACT, 6.0, 6.0, "Scenario")
    # Cover. Mid divider between the main and short routes, then crates on and around the site.
    for j in (-138, -139, -140):
        p.piece(f"Site_Mid_{-j}", "mwall", -44 * C - C / 2, j * C, 0.0, 90.0, ENEMY_TEAM)
    for label, i, j, levels in (("Site_Crate_Main", -47, -140, 1), ("Site_Crate_Mid", -44, -142, 1),
                                ("Site_Crate_Front", -40, -139, 1), ("Site_Crate_Default", -37, -141, 1),
                                ("Site_Crate_Back", -35, -144, 1), ("Site_Crate_Stack", -34, -139, 2)):
        p.crate(label, i, j, levels)
    # Defenders hold the site (face north, at the entrances); the retake comes from the far sides.
    p.bot("Site_Def_0", -37, -143, 0.0, "VERY HIGH", yaw=90.0, grid=True)
    p.bot("Site_Def_1", -34, -139, 2 * H + 20.0, "VERY HIGH", yaw=135.0, grid=True)
    p.bot("Site_Def_2", -40, -142, 0.0, "VERY HIGH", yaw=90.0, grid=True)
    for n, (i, j, yaw) in enumerate(((-32, -145, 135.0), (-32, -138, 225.0), (-44, -145, 45.0))):
        p.bot(f"Site_Retake_{n}", i, j, 0.0, "VERY HIGH", yaw=yaw, tag="kt_op_retake_tag", grid=True)
    site_box = ((x0, y0, -100.0), (x1, y1 - 1.0, 2600.0))
    plant_box = ((PLANT[0], PLANT[2], -100.0), (PLANT[1], PLANT[3], 800.0))
    extract_box = ((EXTRACT[0], EXTRACT[2], -100.0), (EXTRACT[1], EXTRACT[3], 800.0))
    plant_mid = ((PLANT[0] + PLANT[1]) / 2, (PLANT[2] + PLANT[3]) / 2, 0.0)
    door_in = (SITE_DOORS[0] * C + C / 2, y1 - 256.0, 0.0)
    p.stage("Site", "L3 BOMBSITE A",
            "Three hold bombsite A. Pick a door (left or right) and clear the site.",
            site_box, door_in)
    p.stage("Plant", "L3 BOMBSITE A", f"Plant the bomb: hold the button on the bomb console (orange plate, A) for "
            f"{PLANT_HOLD:.0f} s.", plant_box, plant_mid, kind=3)
    p.stage("Hold", "L3 BOMBSITE A", "Bomb planted. The retake is coming: hold the site until it blows.",
            plant_box, plant_mid, kind=4)
    p.stage("Extract", "L3 BOMBSITE A", "Get out: reach the green extraction pad in the south-west corner.",
            extract_box, ((EXTRACT[0] + EXTRACT[1]) / 2, (EXTRACT[2] + EXTRACT[3]) / 2, 0.0), kind=5)
    p.signs.append({"label": PREFIX + "Site_Sign_A", "pos": (-18688.0, y0 + 120.0, 300.0), "yaw": 90,
                    "zone": "Arena", "size": 60, "text": "A"})
    p.signs.append({"label": PREFIX + "Site_Sign_Plant", "pos": (-16640.0, y0 + 120.0, 300.0), "yaw": 90,
                    "zone": "Edit", "size": 28, "text": "PLANT ZONE A\nBomb console on the orange plate:\n"
                                                         f"hold the button {PLANT_HOLD:.0f} s to plant"})
    p.signs.append({"label": PREFIX + "Site_Sign_Extract", "pos": (x0 + 120.0, -74240.0, 520.0), "yaw": 0,
                    "zone": "Scenario", "size": 30, "text": "EXTRACTION\nShoot EXIT to leave"})


# Removed so the plate is free (all backed up first): the empty "opening next" bays and the four ANGLE labs.
# 2026-10-21 (one pipeline): the Fight Lab's start rifts, its always-on bots (the Operation places its own) and its
# title sign, which stood in the breach room.
OLD = [f"KT_Bay_S{k}" for k in range(1, 5)] + [f"KT_Sign_Bay_S{k}" for k in range(1, 5)] + \
      [f"KT3_Upgrade_Scenario_{n}_{s}" for n in range(4) for s in ("Corner", "Angle", "Target", "Brief")] + \
      [f"KT7_Lab_Rift_{r}_{e}" for r in "ABCD" for e in ("In", "Start")] + ["KT7_Lab_Rift_A_Loop"] + \
      ["KT7_Lab_B_Bot_0", "KT7_Lab_B_Bot_1", "KT7_Lab_C_Bot", "KT7_Lab_D_Bot", "KT7_Lab_Sign_Title"]
RETEXT = {"KT_Sign_Area_Scenario": "OPERATION\nThe way in is the OPERATION sign or portal in the hub:\n"
                                   "you start in the crawl room",
          "KT_Sign_Gate_Scenario": "OPERATION\nCompound > Fight Lab > Bombsite A, one long run",
          "KT7_Lab_Sign_A": "6  TOWERS\nOne on top of each tower. Edit your way up, take them.\n"
                            "Then room C, across the hall.",
          "KT7_Lab_Sign_C": "7  RETAKE\nThey own the platform. Wall their ramp, go up a layer,\nown the height first.",
          "KT7_Lab_Sign_D": "8  BOX FIGHT\nStart in your box. Edit out, trade, re-box. Take theirs.",
          "KT7_Lab_Sign_B": "9  PEEK AND RESET\nTwo hold the far wall. Edit, shoot, reset.\n"
                            "Bombsite A is through the doors behind them."}


def verse_vec(v):
    return "vector3{X := %.1f, Y := %.1f, Z := %.1f}" % v


def verse_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_verse(p):
    lines = ["# GENERATED by tools/build_operation.py (the same plan that places the level). Do not edit by hand.",
             "# One entry per room of the Operation, in play order. Operation.verse assigns each tagged bot to the stage",
             "# whose box holds it and each gate to the stage with the nearest Gates point; Pick > 0 spawns only that",
             "# many of the stage's bots, chosen at random each time. Kind 1 = storm, 2 = grenades,",
             "# 3 = plant (stand in the box), 4 = hold (retake bots, bomb timer), 5 = extract (reach the box). Kinds 3-5 follow",
             "# the room before them; their boxes are zones, not rooms.",
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
             "    Gates<public>:[]vector3 = array{}",
             "    Kind<public>:int = 0",
             "    Pick<public>:int = 0",
             "",
             f"KTOpStormStartX<public>:float = {STORM['start_x']:.1f}",
             f"KTOpStormEndX<public>:float = {STORM['end_x']:.1f}",
             f"KTOpStormSeconds<public>:float = {STORM['seconds']:.1f}",
             f"KTOpStormDamage<public>:float = {STORM['damage']:.1f}",
             "",
             "KTOpStages<public>:[]kt_op_stage = array:"]
    for s in p.stages:
        mn, mx = s["box"]
        g = (", Gates := array{" + ", ".join(verse_vec((x, y, 0.0)) for x, y in s["gates"]) + "}") if s["gates"] else ""
        g += f", Pick := {s['pick']}" if s["pick"] else ""
        lines.append(f"    kt_op_stage{{Name := {verse_str(s['name'])}, Level := {verse_str(s['level'])}, "
                     f"Instruction := {verse_str(s['instruction'])}, Lo := {verse_vec(mn)}, Hi := {verse_vec(mx)}, "
                     f"Checkpoint := {verse_vec(s['checkpoint'])}{g}, Kind := {s['kind']}}}")
    return "\n".join(lines) + "\n"


def KTOpStageAt_py(p, pos):
    """Operation.verse KTOpStageAt: the first room box (Kind < 3) holding pos, or -1."""
    for n, s in enumerate(p.stages):
        if s["kind"] < 3 and all(s["box"][0][k] <= pos[k] <= s["box"][1][k] for k in range(3)):
            return n
    return -1


def check(p):
    """Every bot sits in exactly one stage box, every gate point has a barrier, every checkpoint is inside its box."""
    errors = []
    inside = lambda pos, box: all(box[0][k] <= pos[k] <= box[1][k] for k in range(3))
    rooms = [s for s in p.stages if s["kind"] < 3]
    for d in p.devices:
        if d["tag"] in ("kt_op_bot_tag", "kt_op_retake_tag"):
            n = sum(inside(d["pos"], s["box"]) for s in rooms)
            if n != 1:
                errors.append(f"{d['label']} is in {n} room boxes")
    if sum(s["kind"] == 4 for s in p.stages) > 1:
        errors.append("more than one hold stage")
    gates = [d["pos"] for d in p.devices if d["tag"] == "kt_op_gate_tag"]
    for s in p.stages:
        if not inside(s["checkpoint"], s["box"]):
            errors.append(f"checkpoint of {s['name']} is outside its box")
        for gp in s["gates"]:
            if not any(math.dist(gp, g[:2]) < 1.0 for g in gates):
                errors.append(f"no barrier at a gate of {s['name']}")
    return errors


def place(b, p, only=None):
    """Remove and (re)place the plan. With only (a label part after PREFIX, e.g. "Site_"), just those actors."""
    found = b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []
    by_label = {a["label"]: a["actorPath"] for a in found}
    if only:
        keep = lambda label: label.startswith(PREFIX + only)
        p.slabs = [x for x in p.slabs if keep(x["label"])]
        p.pieces = [x for x in p.pieces if keep(x["label"])]
        p.devices = [x for x in p.devices if keep(x["label"])]
        p.signs = [x for x in p.signs if keep(x["label"])]
        gone = [a for a in found if keep(a["label"])]
    else:
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
        b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True, "bCanBeDamaged": False,
                       **pc.get("props", {})})
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
            clear = "Clear Inventory" if d["tag"] == "kt_op_loadout_tag" else "Keep All"
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
        if d.get("spawn"):
            for key, value in {"items Respawn": True, "respawn Item On Timer": True, "time Between Spawns": 5.0,
                               "spawn Item On Timer": True, "time Before First Spawn": 0.5,
                               "initial Movement of Item": "None", "run Over Pickup": False}.items():
                try:
                    b.props(path, {key: value})
                except RuntimeError as exc:
                    refused.append(f"{d['label']}: {key} ({str(exc)[-50:]})")
            # Item Spawner V3 keeps its items in Creative_ItemPreview_Component "items to Load", which the MCP refuses
            # to set (2026-10-21; pickupItemList is null on a new spawner). Add the item in UEFN by hand.
            refused.append(f"{d['label']}: Item List -> add {loadout[d['spawn']].rsplit('.', 1)[-1]} in UEFN")
        if d["tag"]:
            b.tag(path, d["tag"])
        saved.append(path)
    for s in p.signs:
        saved.append(b.sign(s))
    for label, text in ({} if only else RETEXT).items():
        if label in by_label:
            b.props(by_label[label], {"text": text})
            saved.append(by_label[label])
    if not only:
        # The Fight Lab's enemy pieces become theirs (team 2): the player cannot edit them.
        for a in found:
            if a["label"].startswith(LAB_ENEMY) and "PBWA" in a["class"]["refPath"]:
                b.props(a["actorPath"], ENEMY_TEAM)
                saved.append(a["actorPath"])
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
    ap.add_argument("--site-only", action="store_true", help="(re)place only bombsite A (KT16_Op_Site_*)")
    ap.add_argument("--arrive-only", action="store_true", help="(re)place only the crawl-room arrival pad (KT16_Op_Arrive)")
    ap.add_argument("--grenades-only", action="store_true", help="(re)place only the floor grenades (KT16_Op_Nade_*)")
    args = ap.parse_args()
    p = plan()
    errors = check(p)
    print(f"plan: {len(p.slabs)} slabs, {len(p.pieces)} pieces, {len(p.devices)} devices, {len(p.signs)} signs, "
          f"{len(p.stages)} stages")
    for n, s in enumerate(p.stages):
        tag = "kt_op_retake_tag" if s["kind"] == 4 else "kt_op_bot_tag"
        bots = sum(1 for d in p.devices if d["tag"] == tag) if s["kind"] == 4 else 0 if s["kind"] in (3, 5) else             sum(1 for d in p.devices if d["tag"] == tag and all(s["box"][0][k] <= d["pos"][k] <= s["box"][1][k] for k in range(3)))
        pick = f" (pick {s['pick']})" if s["pick"] else ""
        print(f"  {n} {s['level']:<14} {s['name']:<15} bots {bots}{pick}  gates {len(s['gates'])}  kind {s['kind']}")
    if errors:
        print("\n".join(errors))
        return 1
    OUT_VERSE.write_text(render_verse(p), encoding="utf-8", newline="\n")
    print("wrote", OUT_VERSE.name)
    if args.dry_run or args.write_verse:
        return 0
    place(bm.Builder(), p, only="Site_" if args.site_only else "Arrive" if args.arrive_only else
          "Nade_" if args.grenades_only else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
