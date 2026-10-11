"""Fight Lab: four enclosed rooms east of the Scenario plate that put edits and piece control in front of
live opponents instead of empty lanes.

    python tools/build_fight_lab.py --dry-run   # print the plan
    python tools/build_fight_lab.py             # (re)place it; removes only KT7_Lab_* actors
    python tools/build_fight_lab.py --open      # in place: open room A and the roof, add the start rifts (no rebuild)

Player 2026-10-10: the towers should not be enclosed, and a player should start at the top of a tower to edit down,
then edit up the tower beside it; the other rooms likewise start you where the exercise begins. So there is no
ceiling, room A has no outer walls (the wall to room B stays, it blocks B's bots), and each room has a start rift
beside its doorway (out of the walking line, so leaving the room never sends you back in). Room A loops: the top of
the climb tower has a rift back to the top of the drop tower. Rifts are routed by the Verse rift router
(tools/install_rift_router.py, LAB_RIFTS).
Room A's west wall now belongs to the Operation (tools/build_operation.py, KT16_Op_LabWall_*): it carries the door from
the Operation's compound into the towers, so this builder must not place a Wall_W_S again.

Layout (cells of 512 cm, i = x / 512, j = y / 512): i -50..-31, j -136..-125, directly east of KT_Area_Scenario,
so players walk in from the Scenario portal. A two-cell spine (j -131..-130) runs west to east; two rooms on
each side, each 10 x 5 cells, with a two-cell doorway onto the spine.

  A  Edit Towers (south-west)   single-tile wall box, floor-edit climb tower (4 levels), drop tower (3 levels).
                                Raider464's routine opens with edit towers: same tiles, rhythm, no crosshair travel.
  B  Peek and Reset (south-east) staggered cover walls vs two live bots behind their own cover.
                                Edit, shoot, reset, under fire; the reset is the part people skip.
  C  Retake (north-west)        enemy ramp up to a two-level platform held by a live bot, enemy cone above
                                the ramp base. Fortnite3 beginner retake: wall, go up a layer, own the piece first.
  D  Box Fight (north-east)     your closed 1x1 box vs a bot box with one open side, two cover walls between.

Pre-built pieces are real wood player pieces (editable), set invulnerable and forcibly supported so bot fire
and the reset do not leave the course broken (VERIFY in game that invulnerable pieces still edit). Each room
has a reset button that detonates hidden zero-player-damage explosives to clear player builds.
Bots are Guard Spawners on team 2, lowest accuracy, respawn 5 s after elimination; room walls block their sight.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT7_Lab_"
C, H = bm.CELL, bm.LEVEL_H
CEIL = 6 * H
WALL_T = 40.0
I0, I1, J0, J1 = -50, -31, -136, -125          # inclusive cell range
SPINE = (-131, -130)
MID_I = -40                                      # first cell of the east rooms
DOORS = {"A": (-46, -45), "B": (-36, -35), "C": (-46, -45), "D": (-36, -35)}
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
CLS = {k: f"{PIECES}PBWA_W1_{n}.PBWA_W1_{n}_C" for k, n in
       (("wall", "Solid"), ("floor", "Floor"), ("ramp", "StairW"), ("cone", "RoofC"))}
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
ROOM_ZONE = {"A": "Edit", "B": "Aim", "C": "Piece", "D": "Arena"}
# Floors, ramps and cones extend from their pivot (middle of one edge) along (-sin yaw, cos yaw); a ramp
# climbs the opposite way. Measured 2026-10-09 with temporary pieces (bounds + a side capture).
RAMP_YAW = {"S": 0.0, "E": 90.0, "N": 180.0, "W": 270.0}

SIGNS = {
    "A": "A  EDIT TOWERS\n"
         "Step on the rift: you start on top of the drop tower. Edit the floor under you, drop, repeat.\n"
         "Then the climb tower beside it: edit the floor above, climb; its top sends you back to the drop.\n"
         "Wall box: wall up behind you, edit the wall in front, reset. Why: edit timing first.",
    "B": "B  PEEK AND RESET\n"
         "Two live bots hold the far wall. Edit a window or door, hit your shot, reset before\n"
         "they answer. Swap walls each rep. Why: the reset is what keeps you alive; slow is fine.",
    "C": "C  RETAKE\n"
         "A bot holds the platform two levels up, with a cone over the ramp base.\n"
         "Wall in front of their ramp, go up a layer, own the piece before you look down.\n"
         "Why: the player who places first owns the height.",
    "D": "D  BOX FIGHT\n"
         "Start in your box. The bot's box is open on your side. Edit out, trade, re-box.\n"
         "Use the two cover walls in the middle. Why: real fights happen in boxes, not open lanes.",
}


def cell(i, j):
    return i * C + C / 2, j * C + C / 2


class Plan:
    def __init__(self):
        self.slabs, self.pieces, self.devices, self.signs = [], [], [], []

    def slab(self, label, x0, x1, y0, y1, top, thick, zone):
        self.slabs.append({"label": PREFIX + label, "bounds": (x0, x1, y0, y1), "top": top, "thick": thick, "mat": zone})

    def wall_x(self, label, x, y0, y1, zone):           # wall slab on the line x, spanning y0..y1
        if y1 > y0:
            self.slab(label, x - WALL_T / 2, x + WALL_T / 2, y0, y1, CEIL, CEIL + 100, zone)

    def wall_y(self, label, y, x0, x1, zone):
        if x1 > x0:
            self.slab(label, x0, x1, y - WALL_T / 2, y + WALL_T / 2, CEIL, CEIL + 100, zone)

    def piece(self, label, kind, x, y, z, yaw):
        self.pieces.append({"label": PREFIX + label, "cls": CLS[kind], "xf": (x, y, z, yaw)})

    # Build pieces in grid terms. Edges: W/E = x-min/x-max edge of the cell, S/N = y-min/y-max.
    def wall(self, label, i, j, k, edge):
        cx, cy = cell(i, j)
        if edge in "WE":
            self.piece(label, "wall", cx + (-C / 2 if edge == "W" else C / 2), cy, k * H, 90.0)
        else:
            self.piece(label, "wall", cx, cy + (-C / 2 if edge == "S" else C / 2), k * H, 0.0)

    def flat(self, label, kind, i, j, z, yaw=0.0):
        import math
        cx, cy = cell(i, j)
        r = math.radians(yaw)
        dx, dy = -math.sin(r), math.cos(r)
        self.piece(label, kind, cx - dx * C / 2, cy - dy * C / 2, z, yaw)

    def ramp(self, label, i, j, k, climb):
        self.flat(label, "ramp", i, j, k * H, RAMP_YAW[climb])

    def device(self, label, asset, x, y, z=0.0, props=None, yaw=None):
        self.devices.append({"label": PREFIX + label, "asset": asset, "pos": (x, y, z), "props": props or {}, "yaw": yaw})


def plan_lab():
    p = Plan()
    x0, x1, y0, y1 = I0 * C, (I1 + 1) * C, J0 * C, (J1 + 1) * C
    xm = MID_I * C
    ys0, ys1 = SPINE[0] * C, (SPINE[1] + 1) * C          # spine y range

    # Floors (zone coloured per room) and one ceiling.
    p.slab("Floor_Spine", x0, x1, ys0, ys1, 0.0, 100.0, "Scenario")
    for room, (a, b_, c, d) in {"A": (x0, xm, y0, ys0), "B": (xm, x1, y0, ys0),
                                "C": (x0, xm, ys1, y1), "D": (xm, x1, ys1, y1)}.items():
        p.slab(f"Floor_{room}", a, b_, c, d, 0.0, 100.0, ROOM_ZONE[room])
    # No ceiling, and room A (the towers) has no outer walls: open sky, not a closed box (player 2026-10-10).
    # Perimeter: west wall open onto the spine (the way in from Scenarios).
    p.wall_x("Wall_W_N", x0, ys1, y1, "Scenario")
    p.wall_x("Wall_E", x1, y0, y1, "Scenario")
    p.wall_y("Wall_S_B", y0, xm, x1, "Scenario")
    p.wall_y("Wall_N", y1, x0, x1, "Scenario")
    p.wall_x("Wall_Mid_S", xm, y0, ys0, "Scenario")
    p.wall_x("Wall_Mid_N", xm, ys1, y1, "Scenario")
    # Spine walls with a two-cell doorway into each room.
    for side, y in (("S", ys0), ("N", ys1)):
        rooms = ("A", "B") if side == "S" else ("C", "D")
        cuts = [(DOORS[r][0] * C, (DOORS[r][1] + 1) * C) for r in rooms]
        xs = [x0] + [v for cut in cuts for v in cut] + [x1]
        for n in range(0, len(xs), 2):
            p.wall_y(f"Wall_Spine_{side}{n // 2}", y, xs[n], xs[n + 1], "Scenario")

    # Lights: two per room, three along the spine.
    lz = CEIL - 150
    for n, f in enumerate((0.17, 0.5, 0.83)):
        p.device(f"Light_Spine_{n}", LIGHT, x0 + (x1 - x0) * f, (ys0 + ys1) / 2, lz, {"maximumRadius": 4200.0})
    for room, (a, b_, c, d) in {"A": (x0, xm, y0, ys0), "B": (xm, x1, y0, ys0),
                                "C": (x0, xm, ys1, y1), "D": (xm, x1, ys1, y1)}.items():
        for n, f in enumerate((0.27, 0.73)):
            p.device(f"Light_{room}_{n}", LIGHT, a + (b_ - a) * f, (c + d) / 2, lz, {"maximumRadius": 4200.0})

    room_a(p)
    room_b(p)
    room_c(p)
    room_d(p)
    start_rifts(p)

    # Signs beside each doorway, facing into the spine; a title at the entrance facing the Scenario plate.
    for room in "ABCD":
        di = DOORS[room]
        sx = (di[0] - 1) * C - 300                      # just west of the doorway
        south = room in "AB"
        sy = ys0 + 60 if south else ys1 - 60
        p.signs.append({"label": f"{PREFIX}Sign_{room}", "pos": (sx, sy, 180), "yaw": 90 if south else 270,
                        "text": SIGNS[room], "size": 26, "zone": ROOM_ZONE[room]})
    p.signs.append({"label": f"{PREFIX}Sign_Title", "pos": (x0 - 60, ys0 - 700, 180), "yaw": 180,
                    "text": "FIGHT LAB  >>\nA edit towers   B peek and reset\nC retake   D box fight\nlive bots: bring a gun from the Armory",
                    "size": 34, "zone": "Scenario"})
    return p


def room_a(p):
    j = -135
    # T1 single-tile wall box: S, E, W walls; the player closes the N side themselves.
    for e in "SEW":
        p.wall(f"A_Box_{e}", -48, j, 0, e)
    # T2 climb tower: walls on every side of levels 0-3 (N open at ground for the entry), switchback ramps,
    # a floor above each ramp to edit through, roof floor at level 4.
    for k in range(4):
        for e in "NSEW":
            if not (k == 0 and e == "N"):
                p.wall(f"A_Climb_{k}{e}", -45, j, k, e)
        p.ramp(f"A_Climb_Ramp{k}", -45, j, k, "S" if k % 2 == 0 else "N")
        p.flat(f"A_Climb_Floor{k + 1}", "floor", -45, j, (k + 1) * H)
    # T3 drop tower: three ramps up its north face to a floor at level 3, then edit floors down to the ground.
    for k, jj in enumerate((-132, -133, -134)):
        p.ramp(f"A_Drop_Ramp{k}", -42, jj, k, "S")
    for k in range(4):
        for e in "NSEW":
            if (k == 0 and e == "N") or (k == 3 and e == "N"):
                continue                                  # exit at the bottom, entry at the top
            p.wall(f"A_Drop_{k}{e}", -42, j, k, e)
    for k in (1, 2, 3):
        p.flat(f"A_Drop_Floor{k}", "floor", -42, j, k * H)
    p.reset_cells = getattr(p, "reset_cells", {})
    p.reset_cells["A"] = [(-47, -133), (-43, -133)]


def room_b(p):
    # Player side (west): staggered walls, one tile apart, so each rep needs a small re-aim.
    for n, (i, jj) in enumerate(((-38, -135), (-37, -134), (-38, -133))):
        p.wall(f"B_Cover_{n}", i, jj, 0, "E")
    # Bot side (east): cover with a gap, two bots behind it.
    for n, jj in enumerate((-135, -133)):
        p.wall(f"B_BotCover_{n}", -33, jj, 0, "W")
        x, y = cell(-32, jj)
        p.device(f"B_Bot_{n}", bm.GUARD, x, y, 0.0, bot_props(patrol=4), yaw=180.0)
    p.reset_cells["B"] = [(-37, -134), (-34, -134)]


def room_c(p):
    # Enemy platform: 2 x 3 floors at level 2 on the east side, walls on its west edge except the middle.
    for i in (-43, -42):
        for jj in (-128, -127, -126):
            p.flat(f"C_Plat_{i}_{jj}", "floor", i, jj, 2 * H)
    for jj in (-128, -126):
        p.wall(f"C_PlatWall_{jj}", -43, jj, 2, "W")
    # Their ramp down toward the player, and a cone over its base.
    p.ramp("C_EnemyRamp0", -45, -127, 0, "E")
    p.ramp("C_EnemyRamp1", -44, -127, 1, "E")
    p.flat("C_EnemyCone", "cone", -46, -127, H)
    x, y = cell(-42, -127)
    p.device("C_Bot", bm.GUARD, x, y, 2 * H + 20, bot_props(patrol=0), yaw=180.0)
    p.reset_cells["C"] = [(-47, -127), (-44, -127)]


def room_d(p):
    # Player box (closed) and bot box (open toward the player), roofs as cones.
    for e in "NSEW":
        p.wall(f"D_Box_{e}", -38, -127, 0, e)
    p.flat("D_Box_Cone", "cone", -38, -127, H)
    for e in "NSE":
        p.wall(f"D_BotBox_{e}", -33, -127, 0, e)
    p.flat("D_BotBox_Cone", "cone", -33, -127, H)
    for jj in (-128, -126):
        p.wall(f"D_Mid_{jj}", -35, jj, 0, "E")
    x, y = cell(-33, -127)
    p.device("D_Bot", bm.GUARD, x, y, 0.0, bot_props(patrol=0), yaw=180.0)
    p.reset_cells["D"] = [(-37, -127), (-34, -127)]


# Where each room's exercise begins: (cell i, cell j, level) of the start, as LAB_RIFTS routes them.
STARTS = {"A": (-42, -135, 3),      # on top of the drop tower: edit down
          "B": (-39, -134, 0),      # behind the staggered cover
          "C": (-48, -127, 0),      # west of the enemy cone, facing their ramp
          "D": (-38, -127, 0)}      # inside your closed box


def start_rifts(p):
    """A walk-in rift beside each doorway (against the spine wall, west of the doorway, so walking through the
    doorway does not touch it) to the room's start, plus room A's loop from the top of the climb tower."""
    ys0, ys1 = SPINE[0] * C, (SPINE[1] + 1) * C
    p.rifts = []
    for room, (i, j, k) in STARTS.items():
        south = room in "AB"
        x = DOORS[room][0] * C - 220
        y = ys0 + 160 if south else ys1 - 160
        p.device(f"Rift_{room}_In", bm.TELEPORTER, x, y, 0.0, rift_props(True))
        sx, sy = cell(i, j)
        p.device(f"Rift_{room}_Start", bm.TELEPORTER, sx, sy, k * H, rift_props(False))
        p.rifts.append((f"{PREFIX}Rift_{room}_In", f"{PREFIX}Rift_{room}_Start"))
    x, y = cell(-45, -135)                                  # climb tower roof (its level-4 floor)
    p.device("Rift_A_Loop", bm.TELEPORTER, x, y, 4 * H, rift_props(True))
    p.rifts.append((f"{PREFIX}Rift_A_Loop", f"{PREFIX}Rift_A_Start"))


def rift_props(walk_in):
    return {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
            "teleporter Rift Visible": walk_in, "enabledDuringPhase": "Always", "maintain Relative Position": False,
            "conserve Momentum": False, "play Sound Effects": walk_in}


def bot_props(patrol):
    v = {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
         "enabledAtGameStart": True, "allowInfiniteSpawn": True, "spawnOnTimer": True, "spawnTimer": 5,
         "spawnCount": 1, "showHealthBar": True, "startingHealth": 100, "max Health": 100, "startingShield": 50,
         "accuracy": "LOW"}
    if patrol:
        v.update({"enablePatrol": True, "maxPatrolDistance_InMeter": patrol})
    else:
        v["enablePatrol"] = False
    return v


def place(b, p):
    old = b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []
    for a in old:
        if a["label"].startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(old)} old {PREFIX}* actors")
    for s in p.slabs:
        b.slab(s)
    print(f"slabs: {len(p.slabs)}")
    for pc in p.pieces:
        x, y, z, yaw = pc["xf"]
        ref = b.m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": pc["cls"]}, name=pc["label"],
                       xform=bm.xform(x, y, z, yaw=yaw))
        path = b.labelled(ref["refPath"], pc["label"])
        b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True})
    print(f"pieces: {len(p.pieces)}")
    for d in p.devices:
        x, y, z = d["pos"]
        path = b.device(d["asset"], d["label"], x, y, z)
        if d["yaw"] is not None:
            b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path}, xform=bm.xform(x, y, z, yaw=d["yaw"]))
        if d["props"]:
            b.props(path, d["props"])
    print(f"devices: {len(p.devices)}")
    # Reset per room: a button inside the doorway and hidden explosives over the play space.
    ys0, ys1 = SPINE[0] * C, (SPINE[1] + 1) * C
    for room, cells in p.reset_cells.items():
        south = room in "AB"
        bx = (DOORS[room][1] + 1) * C + 150
        by = ys0 - 200 if south else ys1 + 200
        btn = b.device(bm.BUTTON, f"{PREFIX}{room}_ResetButton", bx, by, 0.0)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": btn},
                 xform=bm.xform(bx, by, 0.0, yaw=90.0 if not south else 270.0))
        b.props(btn, {"interaction Text": f"Clear your builds in room {room}", "delay": 0.0, "resetDelay": 0.5})
        events = b.m.tool(bm.DEVICE, "GetBindingOptions", devicePath={"refPath": btn}) or {}
        ev = next((e for e in events.get("sourceEvents", []) if "nteract" in e), None)
        for n, (i, j) in enumerate(cells):
            x, y = cell(i, j)
            boom = b.device(bm.EXPLOSIVE, f"{PREFIX}{room}_Clear_{n}", x, y, 1.5 * H)
            b.props(boom, {"blast Radius": 4.5, "player Damage": 0, "structure Damage": 10000, "knockback": "None",
                           "can be Damaged": False, "damage Indestructible Buildings": False,
                           "visible During Game": False, "play Audio / VFX": False, "time Until Reset Allowed": 0.1,
                           "has Timed Detonation From Game Start": False})
            if ev:
                b.bind(btn, ev, boom, "Explode")
            b.bind(boom, "On Exploded", boom, "Reset")
        print(f"room {room} reset: button event {ev}, {len(cells)} charges")
    for s in p.signs:
        b.sign(s)
    print(f"signs: {len(p.signs)}")


def open_in_place(b, p):
    """Bring a lab built before 2026-10-10 to the open layout without rebuilding it: remove the ceiling and room A's
    outer walls, split the south wall, add the start rifts and refresh room A's sign. Idempotent."""
    have = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or [])}
    for label in ("Ceiling", "Wall_W_S", "Wall_S", "Sign_A"):
        if PREFIX + label in have:
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": have[PREFIX + label]})
            print("removed", PREFIX + label)
    for s in p.slabs:
        if s["label"] == PREFIX + "Wall_S_B" and s["label"] not in have:
            b.slab(s)
            print("added", s["label"])
    for d in p.devices:
        if d["label"].startswith(PREFIX + "Rift_") and d["label"] not in have:
            x, y, z = d["pos"]
            path = b.device(d["asset"], d["label"], x, y, z)
            b.props(path, d["props"])
            print("added", d["label"], (x, y, z))
    for s in p.signs:
        if s["label"] == PREFIX + "Sign_A":
            b.sign(s)
    print("routes for tools/install_rift_router.py:", p.rifts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--open", action="store_true", help="update an existing lab in place (see open_in_place)")
    args = ap.parse_args()
    p = plan_lab()
    print(f"plan: {len(p.slabs)} slabs, {len(p.pieces)} pieces, {len(p.devices)} devices, {len(p.signs)} signs")
    if args.open:
        open_in_place(bm.Builder(), p)
        return
    if args.dry_run:
        print(json.dumps({"pieces": p.pieces[:6], "devices": [d["label"] for d in p.devices]}, indent=1))
        return
    place(bm.Builder(), p)


if __name__ == "__main__":
    main()
