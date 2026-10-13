"""Build the Keystroke Trainer area in the open UEFN level through the UEFN MCP (map plan v2).

Layout, from the map plan page (hub + four colour-coded wings + an off-site lane district):
    hub      9 x 9 cells, spawn in the middle facing north (+X)
    north    BUILD (L1)          stations B1..B5
    east     PIECE CONTROL (L2)  stations P1..P6
    south    EDIT (L3)           stations E1..E5 (signs only until the edit course exists)
    west     ARMORY              weapon pedestals, clear inventory, reset all builds
Each station is a pad with a sign. Standing on it clears that drill's lane (explosives wired to a
hidden trigger on the pad) and the lane device teleports the player to the lane.

Everything placed is labelled KT_* in the Outliner folder "KeystrokeTrainer". A re-run removes
those first, except the autotest device. All positions snap to the 512 cm build grid so lane
checks line up with player builds.

    python tools/build_map.py            # build everything
    python tools/build_map.py --dry-run  # print the plan only
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mcp_call import post  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DRILLS = ROOT / "shared" / "drills.json"
MODULE = "/1f1b8d9c-3e3a-4bb9-b226-03d38d86582e"
BOX = MODULE + "/Content/ShapeTools/Meshes/Box_337D1CB0.Box_337D1CB0"  # 100 cm cube, pivot bottom centre
DRILL_DEVICE = MODULE + "/_Verse.KeystrokeTrainer-keystroke_drill_device"
DEV = "/CreativeCoreDevices/SetupAssets/"
BILLBOARD = DEV + "PID_Device_Billboard.PID_Device_Billboard"
EXPLOSIVE = DEV + "PID_Device_ExplosiveBarrel.PID_Device_ExplosiveBarrel"
TRIGGER = DEV + "PID_Device_Trigger.PID_Device_Trigger"
BUTTON = DEV + "PID_Device_Button.PID_Device_Button"
ITEM_SPAWNER = DEV + "PID_Device_ItemSpawner.PID_Device_ItemSpawner"
GUARD = "/CRD_HenchmanSpawner/SetupAssets/PID_Device_GuardSpawner_V2.PID_Device_GuardSpawner_V2"
ITEM_REMOVER = "/CRD_ItemRemover/SetupAssets/PID_Device_ItemRemover.PID_Device_ItemRemover"
TELEPORTER = DEV + "PID_Device_Teleporter.PID_Device_Teleporter"
DUMMY = DEV + "PID_Device_TargetDummy.PID_Device_TargetDummy"
DUMMY_TRACK = DEV + "PID_Device_TargetDummy_Track.PID_Device_TargetDummy_Track"
EDIT_WALL = "/Game/Building/ActorBlueprints/Player/Wood/L1/PBWA_W1_Solid.PBWA_W1_Solid_C"
TAG_CLASS = MODULE + "/_Verse.KeystrokeTrainer-{}"
FOLDER = "KeystrokeTrainer"
KEEP = {"KT_AutoTest"}

CELL = 512.0
LEVEL_H = 384.0
HUB_CELL = (0, -117)          # hub centre cell (i = +X north, j = +Y east)
LANE_ROW_I = {"B": 60, "P": 80, "E": 100, "W": 120}   # lane district rows, far north of the hub
COMBAT_I = -70                # combat district (aim, arena, scenarios), far south of the hub
LANE_J0 = -200

MAT = {z: f"{MODULE}/KT_Materials/MI_KT_{z}.MI_KT_{z}"
       for z in ("Hub", "Build", "Piece", "Edit", "Armory", "Void", "Aim", "Arena", "Scenario")}
ZONE = {"B": "Build", "P": "Piece", "E": "Edit", "W": "Armory"}
# Linear colours for sign backgrounds, matching the plan page.
SIGN_BG = {"Hub": (0.06, 0.07, 0.09), "Build": (0.05, 0.20, 0.75), "Piece": (0.26, 0.10, 0.66),
           "Edit": (0.80, 0.25, 0.02), "Armory": (0.055, 0.075, 0.105),
           "Aim": (0.02, 0.45, 0.40), "Arena": (0.70, 0.50, 0.02), "Scenario": (0.08, 0.45, 0.12)}
ARMORY = ["AR", "SMG", "SHOTGUN", "PISTOL", "HEALS"]


def cc(i, j):
    """World X, Y of the centre of grid cell (i, j)."""
    return i * CELL + CELL / 2, j * CELL + CELL / 2


def hub_cc(di, dj):
    return cc(HUB_CELL[0] + di, HUB_CELL[1] + dj)


class Mcp:
    def __init__(self):
        _, self.sid = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "kt-build-map", "version": "2"}}})
        post({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.sid)
        self.n = 1

    def tool(self, toolset, tool_name, **args):
        self.n += 1
        res, _ = post({"jsonrpc": "2.0", "id": self.n, "method": "tools/call", "params": {
            "name": "call_tool",
            "arguments": {"toolset_name": toolset, "tool_name": tool_name, "arguments": args}}}, self.sid)
        text = "\n".join(c.get("text", "") for c in res["result"].get("content", []))
        try:
            return json.loads(text).get("returnValue")
        except (json.JSONDecodeError, AttributeError):
            if res["result"].get("isError") or "could not" in text or "not valid" in text:
                raise RuntimeError(f"{toolset}.{tool_name}: {text[:400]}")
            return text


SCENE = "editor_toolset.toolsets.scene.SceneTools"
ACTOR = "editor_toolset.toolsets.actor.ActorTools"
OBJ = "editor_toolset.toolsets.object.ObjectTools"
DEVICE = "ValkyrieToolset.DeviceToolset"


def xform(x, y, z, sx=1.0, sy=1.0, sz=1.0, yaw=0.0):
    return {"location": {"x": x, "y": y, "z": z},
            "rotation": {"pitch": 0, "yaw": yaw, "roll": 0},
            "scale": {"x": sx, "y": sy, "z": sz}}


def rect(i0, i1, j0, j1):
    """Cell range (inclusive) to world bounds."""
    return i0 * CELL, (i1 + 1) * CELL, j0 * CELL, (j1 + 1) * CELL


def plan(drills):
    """Everything to place, as plain data: slabs, signs, stations, lanes, armory."""
    hi, hj = HUB_CELL
    slabs, signs = [], []

    def slab(label, bounds, top, mat, thick=100.0):
        slabs.append({"label": label, "bounds": bounds, "top": top, "thick": thick, "mat": mat})

    def sign(label, x, y, z, yaw, text, size, zone):
        signs.append({"label": label, "pos": (x, y, z), "yaw": yaw, "text": text, "size": size, "zone": zone})

    # Hub, bridges and wings. Wing w: (name, zone, cell rect, gate cell, sign yaw facing the hub).
    slab("KT_Hub", rect(hi - 4, hi + 4, hj - 4, hj + 4), 0.0, "Hub")
    wings = {
        "N": ("BUILD", "Build", rect(hi + 7, hi + 13, hj - 6, hj + 6), rect(hi + 5, hi + 6, hj - 1, hj + 1)),
        "E": ("PIECE CONTROL", "Piece", rect(hi - 7, hi + 7, hj + 7, hj + 13), rect(hi - 1, hi + 1, hj + 5, hj + 6)),
        "S": ("EDIT", "Edit", rect(hi - 13, hi - 7, hj - 6, hj + 6), rect(hi - 6, hi - 5, hj - 1, hj + 1)),
        "W": ("ARMORY", "Armory", rect(hi - 6, hi + 6, hj - 13, hj - 7), rect(hi - 1, hi + 1, hj - 6, hj - 5)),
    }
    for key, (name, zone, wing_r, bridge_r) in wings.items():
        slab(f"KT_Wing_{zone}", wing_r, 0.0, zone)
        slab(f"KT_Bridge_{zone}", bridge_r, 0.0, zone)
    # Floor stripes from the spawn point to each bridge (1 cell wide, 2 cm proud of the hub).
    slab("KT_Stripe_Build", rect(hi + 1, hi + 4, hj, hj), 2.0, "Build", 10.0)
    slab("KT_Stripe_Piece", rect(hi, hi, hj + 1, hj + 4), 2.0, "Piece", 10.0)
    slab("KT_Stripe_Edit", rect(hi - 4, hi - 1, hj, hj), 2.0, "Edit", 10.0)
    slab("KT_Stripe_Armory", rect(hi, hi, hj - 4, hj - 1), 2.0, "Armory", 10.0)

    # Gate signs at each wing entrance, facing the hub, and the title board behind spawn's view line.
    x, y = hub_cc(7, 0); sign("KT_Sign_Gate_Build", x - 256, y, 520, 180, "BUILD\nL1  single pieces  B1-B5", 64, "Build")
    x, y = hub_cc(0, 7); sign("KT_Sign_Gate_Piece", x, y - 256, 520, 270, "PIECE CONTROL\nL2  movement and boxing  P1-P8", 64, "Piece")
    x, y = hub_cc(-7, 0); sign("KT_Sign_Gate_Edit", x + 256, y, 520, 0, "EDIT\nL3  edit course  E1-E7", 64, "Edit")
    x, y = hub_cc(0, -7); sign("KT_Sign_Gate_Armory", x, y + 256, 520, 90, "ARMORY\nweapons  heals  resets\nswitching drills  W1-W3", 64, "Armory")
    x, y = hub_cc(2, -2)
    sign("KT_Sign_Title", x, y, 330, 180,
         "KEYSTROKE TRAINER\nSlow is smooth. Smooth is fast.\nStand on a station pad to start a set.\nClean sets raise your tempo.", 40, "Hub")

    # Stations: pads + signs in each wing, lanes in the district.
    by_wing = {"B": [], "P": [], "E": [], "W": []}
    for d in sorted(drills, key=lambda d: d.get("code", "Z9")):
        if d.get("code") and d["code"][0] in by_wing:
            by_wing[d["code"][0]].append(d)
        elif d.get("code"):
            print(f"note: {d['code']} {d['id']} has no wing in this layout (combat district); skipped")
    stations, lanes = [], []
    lane_j = {w: LANE_J0 for w in by_wing}
    for w, ds in by_wing.items():
        zone = ZONE[w]
        n = len(ds)
        for k, d in enumerate(ds):
            off = (k - (n - 1) / 2) * 2          # pads every 2 cells, centred
            if w == "B":
                pi, pj, si, sj, yaw = hi + 10, hj + off, hi + 12, hj + off, 180
            elif w == "P":
                pi, pj, si, sj, yaw = hi + off, hj + 10, hi + off, hj + 12, 270
            elif w == "E":
                pi, pj, si, sj, yaw = hi - 10, hj + off, hi - 12, hj + off, 0
            else:
                pi, pj, si, sj, yaw = hi + off, hj - 12, hi + off, hj - 13, 90
            px, py = cc(int(pi), int(pj)) if off == int(off) else (pi * CELL + CELL, pj * CELL + CELL)
            sx, sy = cc(int(si), int(sj)) if off == int(off) else (si * CELL + CELL, sj * CELL + CELL)
            chain = "  >  ".join(d["steps"])
            live = True
            text = f"{d['code']}  {d['name'].upper()}\n{chain}\n" + (f"stand on the pad  |  {d['reps']} reps" if live else "opening next")
            if d.get("loadout") == "melee":
                text += "\n" + MELEE_NOTE
            sign(f"KT_Sign_{d['code']}", sx, sy, 330, yaw, text, 40, zone)
            st = {"drill": d, "pad": (px, py), "live": live, "zone": zone}
            stations.append(st)
            if not live:
                continue
            adv = d.get("advance", [1, 0, 0])
            lane = d.get("lane", {"kind": "flat", "forward": 2, "up": 1})
            tracks = (d["reps"] - 1) * abs(adv[0]) + 1
            oi, oj = LANE_ROW_I[w], lane_j[w]
            fwd, up = lane.get("forward", 2), lane.get("up", 1)
            ox, oy = cc(oi, oj)
            if lane.get("kind") == "gap":
                slab(f"KT_Ledge_{d['code']}", rect(oi - 2, oi, oj, oj + tracks - 1), 0.0, zone)
                slab(f"KT_Catch_{d['code']}", rect(oi + 1, oi + fwd, oj, oj + tracks - 1), -LEVEL_H, "Void")
            else:
                slab(f"KT_Ledge_{d['code']}", rect(oi - 2, oi + fwd, oj, oj + tracks - 1), 0.0, zone)
            lx, ly = cc(oi + fwd + 1, oj + (tracks - 1) // 2)
            sign(f"KT_Sign_Lane_{d['code']}", lx, ly, LEVEL_H * up + 260, 180,
                 f"{d['code']}  {d['name'].upper()}\n{chain}", 72, zone)
            # Explosives along the lane: one every 6 cells, mid-height, radius 4 cells.
            booms = []
            for t in range(0, tracks, 6):
                bx, by = cc(oi + max(fwd // 2, 0), oj + min(t + 3, tracks - 1))
                booms.append((bx, by, LEVEL_H * up / 2))
            if prebuilt_edit(d):
                booms = []    # explosives would destroy the pre-built walls the drill edits
            lanes.append({"drill": d, "origin": (ox, oy, 0.0), "booms": booms, "station": st, "tracks": tracks})
            lane_j[w] += tracks + 4

    # Armory pedestals and buttons.
    armory = []
    for k, name in enumerate(ARMORY):
        x, y = hub_cc(-4 + 2 * k, -10)
        armory.append({"name": name, "pos": (x, y)})
        sign(f"KT_Sign_Armory_{name}", x, y - CELL, 330, 90, name, 64, "Armory")
    return {"slabs": slabs, "signs": signs, "stations": stations, "lanes": lanes, "armory": armory,
            "spawn": hub_cc(0, 0), "buttons": {"clear": hub_cc(-1, -8), "reset": hub_cc(1, -8)}}


def prebuilt_edit(drill):
    """Edit drills that start from a pre-built wall (every E drill except the ones that build first)."""
    return drill["code"].startswith("E") and drill["steps"][0] == "edit"


def track_y(ln, k):
    adv = ln["drill"].get("advance", [1, 0, 0])
    return ln["origin"][1] + k * abs(adv[0]) * CELL


def place_edit_walls(b, p):
    """One wood wall per rep track on the edge between the start cell and cell 1, facing the player.

    Players edit these (door, window, arch, half wall) and walk through; the lane grades the
    pass-through. Edited walls stay edited until the match restarts (open question 4)."""
    for ln in p["lanes"]:
        d = ln["drill"]
        if not prebuilt_edit(d):
            continue
        ox = ln["origin"][0]
        for k in range(d["reps"]):
            label = f"KT_EditWall_{d['code']}_{k}"
            ref = b.m.tool(SCENE, "add_to_scene_from_class", actor_type={"refPath": EDIT_WALL},
                           name=label, xform=xform(ox + CELL / 2, track_y(ln, k), 0.0, yaw=90))
            path = b.labelled(ref["refPath"], label)
            b.props(path, {"bForciblyStructurallySupported": True})
        print(f"edit walls {d['code']}: {d['reps']}")


def place_switch_targets(b, p):
    """W lanes: per track a gun dummy 3 cells ahead and one cell right (clear of a wall built in
    front), and for pickaxe drills a dummy just in front. Hits go to tagged triggers the lane finds."""
    for ln in p["lanes"]:
        d = ln["drill"]
        targets = {c.get("target") for c in d["checks"] if c["kind"] == "target_hit"}
        if not targets:
            continue
        ox, oy, _ = ln["origin"]
        hits = {}
        for t in sorted(targets):
            trig = b.device(TRIGGER, f"KT_{t.capitalize()}Hit_{d['code']}", ox - CELL, oy + (CELL if t == "pickaxe" else 0), 0.0)
            b.props(trig, {"visible in Game": False})
            b.tag(trig, f"kt_{t}_hit_tag")
            hits[t] = trig
        for k in range(d["reps"]):
            y = track_y(ln, k)
            if "gun" in hits:
                dm = b.device(DUMMY, f"KT_GunTarget_{d['code']}_{k}", ox + 3 * CELL, y + CELL, 0.0)
                b.face(dm, 180.0)
                b.props(dm, {"infiniteHealth": True})
                b.bind(dm, "On Hit", hits["gun"], "Trigger")
            if "pickaxe" in hits:
                dm = b.device(DUMMY, f"KT_PickTarget_{d['code']}_{k}", ox + CELL / 2 + 40, y, 0.0)
                b.face(dm, 180.0)
                b.props(dm, {"infiniteHealth": True})
                b.bind(dm, "On Hit", hits["pickaxe"], "Trigger")
        print(f"switch targets {d['code']}: {sorted(targets)}")


# Combat district: corner pads in the hub teleport to three areas far south of the hub.
# Each area: (zone, title, hub corner (di, dj), teleporter groups (hub side, area side), size in cells (i, j)).
COMBAT = [
    # Groups S, T, U must stay clear of the Greybox template's demo teleporters, which use A, B, C, D and Z:
    # teleporters that share a group are chosen between, so a clash sends players into the template.
    ("Aim", "AIM RANGE\nL4  static  flick  tracking  recoil", (3, 3), ("Group_S", "Group_T"), (24, 13)),
    ("Arena", "BOT ARENA\nL5  1v1 box fights\nbots next", (-3, 3), ("Group_U", "Group_E"), (20, 12)),
    ("Scenario", "SCENARIOS\nL6  retake  zone  2v1  breach\nopening next", (-3, -3), ("Group_F", "Group_G"), (20, 12)),
]


def place_combat(b):
    hi, hj = HUB_CELL
    j0 = hj - 60
    for zone, title, (di, dj), (g_hub, g_area), (ni, nj) in COMBAT:
        hx, hy = hub_cc(di, dj)
        b.slab({"label": f"KT_Pad_{zone}", "bounds": (hx - 200, hx + 200, hy - 200, hy + 200), "top": 15.0, "thick": 15.0, "mat": zone})
        tp = b.device(TELEPORTER, f"KT_Portal_{zone}", hx, hy, 15.0)
        b.props(tp, {"knob_TeleporterGroup": g_hub, "knob_TargetTeleporterGroup": g_area, "change Teleporter Target": "On Entry", "maintain Relative Position": False, "conserve Momentum": False})
        b.sign({"label": f"KT_Sign_Gate_{zone}", "pos": (hx + (CELL if di > 0 else -CELL), hy, 380),
                "yaw": 180 if di > 0 else 0, "text": title, "size": 56, "zone": zone})
        ai, aj = COMBAT_I, j0
        b.slab({"label": f"KT_Area_{zone}", "bounds": rect(ai, ai + ni - 1, aj, aj + nj - 1), "top": 0.0, "thick": 100.0, "mat": zone})
        ax, ay = cc(ai + 1, aj + nj // 2)
        back = b.device(TELEPORTER, f"KT_Portal_{zone}_Return", ax, ay, 0.0)
        b.props(back, {"knob_TeleporterGroup": g_area, "knob_TargetTeleporterGroup": g_hub, "change Teleporter Target": "On Entry", "maintain Relative Position": False, "conserve Momentum": False})
        sx, sy = cc(ai + 3, aj + nj // 2)
        b.sign({"label": f"KT_Sign_Area_{zone}", "pos": (sx, sy, 380), "yaw": 180,
                "text": title + "\nstep on the pad behind you to return", "size": 56, "zone": zone})
        if zone == "Aim":
            place_aim_range(b, ai, aj)
        elif zone == "Arena":
            ri, rj = ai + 4, aj
            for label, bounds in (("N", rect(ri + 12, ri + 12, rj, rj + 11)),
                                  ("E", rect(ri, ri + 11, rj + 12, rj + 12)),
                                  ("W", rect(ri, ri + 11, rj - 1, rj - 1))):
                b.slab({"label": f"KT_ArenaWall_{label}", "bounds": bounds, "top": LEVEL_H * 3, "thick": LEVEL_H * 3, "mat": "Void"})
        else:
            for k, name in enumerate(("S1 HIGH-GROUND RETAKE", "S2 ZONE EDGE", "S3 TWO VS ONE", "S4 BREACH")):
                bi = ai + 4 + (k // 2) * 7
                bj = aj + (k % 2) * 6 + 1
                b.slab({"label": f"KT_Bay_S{k + 1}", "bounds": rect(bi, bi + 4, bj, bj + 4), "top": 20.0, "thick": 20.0, "mat": "Hub"})
                x, y = cc(bi + 5, bj + 2)
                b.sign({"label": f"KT_Sign_Bay_S{k + 1}", "pos": (x, y, 300), "yaw": 180,
                        "text": name + "\nopening next", "size": 40, "zone": zone})
        print(f"combat {zone}: area at cells ({ai}, {aj}), hub pad ({di}, {dj})")
        j0 += nj + 8


def place_aim_range(b, ai, aj):
    """Four lanes, 22 cells long, 3 wide: static plates at 5/10/20 cells (25/50/100 m), flick
    pop-ups, a tracking dummy on a rail, and a recoil wall. Scoring (kt_aim_lane_device) is next."""
    names = ["A1 STATIC PLATES  25 / 50 / 100 m", "A2 FLICK  pop-ups", "A3 TRACKING  stay on the mover", "A4 RECOIL  spray into the ring"]
    for k, name in enumerate(names):
        lj = aj + 1 + k * 3
        lx, ly = cc(ai + 2, lj + 1)
        b.slab({"label": f"KT_ShootLine_A{k + 1}", "bounds": (lx - 40, lx + 40, ly - 700, ly + 700), "top": 2.0, "thick": 2.0, "mat": "Hub"})
        b.sign({"label": f"KT_Sign_Lane_A{k + 1}", "pos": (lx, ly, 300), "yaw": 180,
                "text": name + "\nfree practice  |  scores next", "size": 40, "zone": "Aim"})
        if k == 0:
            for dist in (5, 10, 20):
                x, y = cc(ai + 2 + dist, lj + 1)
                dm = b.device(DUMMY, f"KT_AimTarget_A1_{dist}", x, y, 0.0)
                b.face(dm, 180.0)              # face the shooter (west, -X)
                b.props(dm, {"infiniteHealth": True})
        elif k == 1:
            for n, (di, dj) in enumerate(((8, 0), (10, 2), (12, 1), (9, 2), (11, 0))):
                x, y = cc(ai + 2 + di, lj + dj)
                dm = b.device(DUMMY, f"KT_AimTarget_A2_{n}", x, y, 0.0)
                b.face(dm, 180.0)              # face the shooter (west, -X)
                b.props(dm, {"infiniteHealth": True})
        elif k == 2:
            x, y = cc(ai + 2 + 5, lj + 1)
            dm = b.device(DUMMY_TRACK, "KT_AimTarget_A3", x, y, 0.0)
            b.props(dm, {"infiniteHealth": True})
        else:
            x, y = cc(ai + 2 + 5, lj + 1)
            dm = b.device(DUMMY, "KT_AimTarget_A4", x, y, 0.0)
            b.face(dm, 180.0)              # face the shooter (west, -X)
            b.props(dm, {"infiniteHealth": True})
            b.slab({"label": "KT_RecoilWall", "bounds": rect(ai + 2 + 7, ai + 2 + 7, lj, lj + 2),
                    "top": LEVEL_H * 2, "thick": LEVEL_H * 2, "mat": "Void"})


PRESSURE_LABELS = ("KT_Pressure_", "KT_Guard_", "KT_GuardPad_")


def has_exposure(drill):
    return any(c["kind"] == "exposure" for c in drill["checks"])


def clear_pressure(b):
    """Remove only the pressure rig (trigger, guard, platform) so it can be re-placed on its own."""
    for a in b.m.tool(SCENE, "find_actors", name="KT_", collision_channels=[]) or []:
        if a["label"].startswith(PRESSURE_LABELS):
            b.m.tool(SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})


def place_pressure(b, p):
    """One hidden trigger and one guard per lane whose drill has exposure checks.

    The lane device fires its pressure trigger at the start of every rep; the trigger spawns the
    guard, which stands on a small platform just beyond the lane's front edge, in the middle of the
    tracks, facing back toward the player. Which damage source player walls block is still an open
    question in the design doc, so this is the first thing to swap if exposure grades look wrong.
    """
    lanes_by_label = {a["label"]: a["actorPath"] for a in (b.m.tool(SCENE, "find_actors", name="KT_Lane_", collision_channels=[]) or [])}
    for ln in p["lanes"]:
        d = ln["drill"]
        if not has_exposure(d):
            continue
        code = d["code"]
        adv = d.get("advance", [1, 0, 0])
        lane_cfg = d.get("lane", {"kind": "flat", "forward": 2, "up": 1})
        tracks = (d["reps"] - 1) * abs(adv[0]) + 1
        fwd = lane_cfg.get("forward", 2)
        ox, oy, _ = ln["origin"]
        oi, oj = round((ox - CELL / 2) / CELL), round((oy - CELL / 2) / CELL)
        jc = oj + (tracks - 1) // 2
        b.slab({"label": f"KT_GuardPad_{code}", "bounds": rect(oi + fwd + 3, oi + fwd + 4, jc - 1, jc),
                "top": 0.0, "thick": 100.0, "mat": ZONE[code[0]]})
        gx, gy = cc(oi + fwd + 3, jc)
        guard = b.device(GUARD, f"KT_Guard_{code}", gx + CELL / 2, gy + CELL / 2, 0.0)
        b.m.tool(ACTOR, "set_actor_transform", actor={"refPath": guard}, xform=xform(gx + CELL / 2, gy + CELL / 2, 0.0, yaw=180))
        # Team 2 and HIGH accuracy: the default team 1 is the players' team, so the guard never hurt anyone
        # (player 2026-10-13: "the bot is also not doing damage to me").
        b.props(guard, {"enabledAtGameStart": True, "allowInfiniteSpawn": True, "guardTeamOption": "Team Index",
                        "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2}, "accuracy": "HIGH"})
        trig = b.device(TRIGGER, f"KT_Pressure_{code}", ox - CELL, oy, 0.0)
        b.props(trig, {"visible in Game": False})
        b.bind(trig, "OnTriggered", guard, "Spawn")
        b.tag(trig, "kt_pressure_tag")    # the lane device picks the nearest tagged trigger itself
        lane = lanes_by_label.get(f"KT_Lane_{code}")
        linked = True
        if False and lane:
            try:
                b.m.tool(DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName="pressureTrigger",
                         value=json.dumps({"refPath": trig}))
                linked = True
            except RuntimeError as exc:
                print(f"  could not link {code}'s pressure trigger ({str(exc)[-90:]})")
        if not linked:
            # Fallback so the lane still has pressure: the guard keeps itself stocked on a timer.
            b.props(guard, {"spawnOnTimer": True, "spawnTimer": 4})
        print(f"pressure {code}: guard at ({gx + CELL / 2:.0f}, {gy + CELL / 2:.0f}), linked to lane trigger: {linked}")


MELEE_NOTE = "MELEE ONLY: pickaxe and building, no guns"


def clear_melee(b):
    for a in b.m.tool(SCENE, "find_actors", name="KT_Melee_", collision_channels=[]) or []:
        b.m.tool(SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})


def loadout_items():
    """Item definition paths of the validated practice loadout (shared/practice-loadout.json)."""
    path = ROOT / "shared" / "practice-loadout.json"
    return list(json.loads(path.read_text(encoding="utf-8"))["items"].values()) if path.exists() else []


def fill_item_list(b, device_path, items):
    """Fill a device's Item List one entry at a time: the editor's array setter only accepts an append."""
    comp = json.loads(b.m.tool(OBJ, "get_properties", instance={"refPath": device_path}, properties=["itemList"]))["itemList"]["refPath"]
    for item in items:
        cur = json.loads(b.m.tool(OBJ, "get_properties", instance={"refPath": comp}, properties=["itemListData"]))["itemListData"]
        if any(x["itemDefinition"]["refPath"] == item for x in cur):
            continue
        try:
            b.m.tool(OBJ, "set_properties", instance={"refPath": comp},
                     values=json.dumps({"itemListData": cur + [{"itemDefinition": {"refPath": item}, "itemQuantity": 1}]}))
        except RuntimeError as exc:
            print(f"  item list: could not add {item.split('/')[-1]} ({str(exc)[-60:]})")


def place_melee(b, p):
    """Melee-only lanes (drills with loadout melee): stepping on the pad strips weapons and consumables.

    An item remover set to Weapons And Consumables is bound to the pad's clear trigger, which already
    fires when the player steps on the pad. Pickaxe and building materials are untouched. Signs get a
    MELEE ONLY line. The armory is where players re-equip afterwards.
    """
    found = {a["label"]: a["actorPath"] for a in (b.m.tool(SCENE, "find_actors", name="KT_", collision_channels=[]) or [])}
    for ln in p["lanes"]:
        d = ln["drill"]
        if d.get("loadout", "any") != "melee":
            for label in (f"KT_Sign_{d['code']}", f"KT_Sign_Lane_{d['code']}"):
                sign = found.get(label)
                if sign:
                    text = json.loads(b.m.tool(OBJ, "get_properties", instance={"refPath": sign}, properties=["text"]))["text"]
                    if "MELEE ONLY" in text:
                        b.props(sign, {"text": text.replace("\n" + MELEE_NOTE, "").replace(MELEE_NOTE, "").rstrip()})
            continue
        code = d["code"]
        trig = found.get(f"KT_Clear_{code}")
        if not trig:
            print(f"melee {code}: no KT_Clear_{code} trigger in the level, skipped")
            continue
        px, py = ln["station"]["pad"]
        rem = b.device(ITEM_REMOVER, f"KT_Melee_{code}", px, py, 0.0)
        # "Weapons And Consumables" also strips the pickaxe (a weapon-slot item), leaving nothing to fight
        # or harvest with. Remove only the guns and consumables the armory can hand out.
        b.props(rem, {"affectedItems": "Objects In Device", "removalMethod": "Remove Items"})
        fill_item_list(b, rem, loadout_items())
        b.bind(trig, "OnTriggered", rem, "Remove")
        for label in (f"KT_Sign_{code}", f"KT_Sign_Lane_{code}"):
            sign = found.get(label)
            if not sign:
                continue
            text = json.loads(b.m.tool(OBJ, "get_properties", instance={"refPath": sign}, properties=["text"]))["text"]
            if "MELEE ONLY" not in text:
                b.props(sign, {"text": text + "\n" + MELEE_NOTE})
        print(f"melee {code}: remover bound to the pad trigger")


ENCLOSURE_LABELS = ("KT_Wall_", "KT_Ceil_", "KT_RoomFloor_")
HUB_HEIGHT = LEVEL_H * 4      # hub and wings: four levels of headroom


def clear_enclosure(b):
    for a in b.m.tool(SCENE, "find_actors", name="KT_", collision_channels=[]) or []:
        if a["label"].startswith(ENCLOSURE_LABELS):
            b.m.tool(SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})


def _runs(cells):
    """Merge a {(i, j): zone} map of wall cells into the fewest boxes: rows first, then equal rows stacked."""
    rows = {}
    for (i, j), z in sorted(cells.items()):
        rows.setdefault((i, z), []).append(j)
    boxes = []
    for (i, z), js in rows.items():
        js.sort()
        start = prev = js[0]
        for j in js[1:] + [None]:
            if j is not None and j == prev + 1:
                prev = j
                continue
            boxes.append([i, i, start, prev, z])
            if j is not None:
                start = prev = j
    boxes.sort(key=lambda t: (t[2], t[3], t[4], t[0]))
    merged = []
    for bx in boxes:
        if merged and merged[-1][2:5] == bx[2:5] and merged[-1][1] + 1 == bx[0]:
            merged[-1][1] = bx[1]
        else:
            merged.append(bx)
    return merged


def place_enclosure(b, p):
    """Close the map: walls and a ceiling around the hub, wings and bridges, and a sealed room per lane.

    Hub complex: every cell just outside the union of hub, wing and bridge slabs gets a wall as tall as
    the ceiling, so the bridges stay open doorways between rooms. Lanes: a ring of wall cells around the
    ledge, tracks and (for pressure lanes) the guard platform, a floor under the whole room, and a
    ceiling three levels above the highest cell the drill needs. Walls take the colour of the zone they
    enclose. Re-run with --enclose-only; it removes its own earlier walls first.
    """
    floors = {}
    for sl in p["slabs"]:
        if sl["label"].startswith(("KT_Hub", "KT_Wing_", "KT_Bridge_")):
            x0, x1, y0, y1 = sl["bounds"]
            for i in range(int(x0 // CELL), int(x1 // CELL)):
                for j in range(int(y0 // CELL), int(y1 // CELL)):
                    floors[(i, j)] = sl["mat"]
            b.slab({"label": f"KT_Ceil_{sl['label'][3:]}", "bounds": sl["bounds"], "top": HUB_HEIGHT + 100.0,
                    "thick": 100.0, "mat": sl["mat"]})
    walls = {}
    for (i, j), z in floors.items():
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + di, j + dj)
            if n not in floors:
                walls.setdefault(n, z)
    boxes = _runs(walls)
    for k, (i0, i1, j0, j1, z) in enumerate(boxes):
        b.slab({"label": f"KT_Wall_Hub_{k}", "bounds": rect(i0, i1, j0, j1), "top": HUB_HEIGHT,
                "thick": HUB_HEIGHT + 100.0, "mat": z})
    print(f"enclosure: hub complex {len(floors)} floor cells, {len(boxes)} wall boxes")

    for ln in p["lanes"]:
        d = ln["drill"]
        code = d["code"]
        zone = ZONE[code[0]]
        lane = d.get("lane", {"kind": "flat", "forward": 2, "up": 1})
        adv = d.get("advance", [1, 0, 0])
        tracks = (d["reps"] - 1) * abs(adv[0]) + 1
        fwd, up = lane.get("forward", 2), lane.get("up", 1)
        ox, oy, _ = ln["origin"]
        oi, oj = round((ox - CELL / 2) / CELL), round((oy - CELL / 2) / CELL)
        front = oi + fwd + (5 if has_exposure(d) else 1)      # pressure lanes also hold the guard platform
        a, c = oi - 3, front
        j0, j1 = oj - 1, oj + tracks
        top = LEVEL_H * (up + 3)
        bottom = -LEVEL_H - 100.0
        ring = {}
        for i in range(a, c + 1):
            ring[(i, j0)] = zone
            ring[(i, j1)] = zone
        for j in range(j0 + 1, j1):
            ring[(a, j)] = zone
            ring[(c, j)] = zone
        for k, (i0, i1, jj0, jj1, z) in enumerate(_runs(ring)):
            b.slab({"label": f"KT_Wall_{code}_{k}", "bounds": rect(i0, i1, jj0, jj1), "top": top,
                    "thick": top - bottom, "mat": z})
        # 1 cm under the level (not 20): just clear of the catch floor's top, while pieces built down here sit on it
        # instead of hovering (player 2026-10-13: "make all structures fit/align with player builds").
        b.slab({"label": f"KT_RoomFloor_{code}", "bounds": rect(a + 1, c - 1, j0 + 1, j1 - 1), "top": -LEVEL_H - 1.0,
                "thick": 100.0, "mat": zone})
        b.slab({"label": f"KT_Ceil_Lane_{code}", "bounds": rect(a, c, j0, j1), "top": top + 100.0,
                "thick": 100.0, "mat": zone})
        print(f"enclosure {code}: room {c - a - 1} x {j1 - j0 - 1} cells, ceiling {top / 100:.1f} m")


class Builder:
    def __init__(self):
        self.m = Mcp()

    def labelled(self, path, label):
        self.m.tool(ACTOR, "set_label", actor={"refPath": path}, label=label)
        self.m.tool(SCENE, "set_actor_folder", actor={"refPath": path}, folder_path=FOLDER)
        return path

    def device(self, asset, label, x, y, z=0.0, yaw=0.0):
        ref = self.m.tool(DEVICE, "PlaceDevice", assetPath={"refPath": asset}, transform=xform(x, y, z, yaw=yaw))
        return self.labelled(ref["refPath"], label)

    def face(self, path, yaw):
        """Turn a placed actor to yaw (PlaceDevice ignores the rotation it is given). A target dummy at yaw 0 faces
        +X; lanes run +X, so a dummy facing the player is yaw 180 (player 2026-10-10: dummies were side-on)."""
        cur = self.m.tool(ACTOR, "get_actor_transform", actor={"refPath": path})
        loc, sc = cur["location"], cur["scale"]
        self.m.tool(ACTOR, "set_actor_transform", actor={"refPath": path},
                    xform=xform(loc["x"], loc["y"], loc["z"], sc["x"], sc["y"], sc["z"], yaw=yaw))

    def tag(self, path, tag_name):
        """Add a Verse Tag Markup component carrying one of the tags declared in Tags.verse."""
        comp = self.m.tool(ACTOR, "add_component", owner={"refPath": path},
                           component_type={"refPath": "/Script/VerseTags.VerseTagMarkupComponent"}, name="KT_Tags")
        self.props(comp["refPath"], {"internalTags": {"internalTags": [{"internalTag": {"refPath": TAG_CLASS.format(tag_name)}}]}})

    def props(self, path, values):
        return self.m.tool(OBJ, "set_properties", instance={"refPath": path}, values=json.dumps(values))

    def bind(self, src, event, dst, fn):
        self.m.tool(DEVICE, "AddEventBinding", sourceDevicePath={"refPath": src}, sourceEvent=event,
                    targetDevicePath={"refPath": dst}, targetFunction=fn)

    def slab(self, s):
        x0, x1, y0, y1 = s["bounds"]
        xf = xform((x0 + x1) / 2, (y0 + y1) / 2, s["top"] - s["thick"],
                   (x1 - x0) / 100.0, (y1 - y0) / 100.0, s["thick"] / 100.0)
        ref = self.m.tool(SCENE, "add_to_scene_from_asset", asset_path=BOX, name=s["label"], xform=xf)
        path = self.labelled(ref["refPath"], s["label"])
        comps = self.m.tool(ACTOR, "get_components", actor={"refPath": path}) or []
        mesh = next((c["refPath"] for c in comps if "StaticMeshComponent" in c["refPath"]), None)
        if mesh:
            self.props(mesh, {"OverrideMaterials": [{"refPath": MAT[s["mat"]]}]})
        return path

    def sign(self, s):
        x, y, z = s["pos"]
        path = self.device(BILLBOARD, s["label"], x, y, z)
        # PlaceDevice ignores rotation. A billboard's panel faces -Y at yaw 0, so turn it by +90
        # from the direction it should face, and scale it up (the stock panel is 3.6 x 1.6 m).
        label = s["label"]
        if "Gate" in label:
            sc, z = 3.0, 380
        elif "Title" in label:
            sc, z = 2.5, 120
        elif "Lane" in label:
            sc = 4.0
        elif "Armory" in label:
            sc, z = 1.5, 250
        else:
            sc, z = 2.0, 180
        self.m.tool(ACTOR, "set_actor_transform", actor={"refPath": path},
                    xform=xform(x, y, z, sc, sc, sc, yaw=(s["yaw"] + 90) % 360))
        r, g, b = SIGN_BG[s["zone"]]
        self.props(path, {"text": s["text"], "textSize": s["size"],
                          "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                          "backgroundColor": {"r": r, "g": g, "b": b, "a": 1}})
        return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--enclose-only", action="store_true", help="only (re)build the walls, floors and ceilings that enclose the hub and every lane")
    ap.add_argument("--melee-only", action="store_true", help="only (re)place the melee-only item removers and sign notes")
    ap.add_argument("--pressure-only", action="store_true", help="only (re)place guards and pressure triggers; leave the rest of the level alone")
    args = ap.parse_args()
    drills = [d for d in json.loads(DRILLS.read_text(encoding="utf-8"))["drills"] if not d.get("retired")]
    p = plan(drills)
    for ln in p["lanes"]:
        d = ln["drill"]
        print(f"{d['code']} {d['id']:16} lane {tuple(round(v) for v in ln['origin'])}  pad {tuple(round(v) for v in ln['station']['pad'])}  booms {len(ln['booms'])}")
    print(f"{len(p['slabs'])} slabs, {len(p['signs'])} signs, {len(p['stations'])} stations")
    if args.dry_run:
        return

    if args.enclose_only:
        b = Builder()
        clear_enclosure(b)
        place_enclosure(b, p)
        return

    if args.melee_only:
        b = Builder()
        clear_melee(b)
        place_melee(b, p)
        return

    if args.pressure_only:
        b = Builder()
        clear_pressure(b)
        place_pressure(b, p)
        return

    b = Builder()
    old = {a["label"]: a["actorPath"] for a in (b.m.tool(SCENE, "find_actors", name="KT_", collision_channels=[]) or [])}
    for label, path in old.items():
        if label not in KEEP:
            b.m.tool(SCENE, "remove_from_scene", actor={"refPath": path})
    print(f"removed {len(old) - len(KEEP & set(old))} old KT_ actors")

    for s in p["slabs"]:
        b.slab(s)
    print("slabs placed")
    for s in p["signs"]:
        b.sign(s)
    print("signs placed")

    all_booms = []
    for st in p["stations"]:
        d, (px, py) = st["drill"], st["pad"]
        b.slab({"label": f"KT_Pad_{d['code']}", "bounds": (px - 160, px + 160, py - 160, py + 160),
                "top": 15.0, "thick": 15.0, "mat": st["zone"]})
    for ln in p["lanes"]:
        d, (ox, oy, oz), (px, py) = ln["drill"], ln["origin"], ln["station"]["pad"]
        lane = b.device(DRILL_DEVICE, f"KT_Lane_{d['code']}", ox, oy, oz)
        b.m.tool(DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName="drillId", value=json.dumps(d["id"]))
        b.m.tool(DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName="padOffset",
                 value=json.dumps({"X": px - ox, "Y": py - oy, "Z": 15.0 - oz}))
        trig = b.device(TRIGGER, f"KT_Clear_{d['code']}", px, py, 0.0)
        b.props(trig, {"visible in Game": False})
        for k, (x, y, z) in enumerate(ln["booms"]):
            boom = b.device(EXPLOSIVE, f"KT_Boom_{d['code']}_{k}", x, y, z)
            b.props(boom, {"blast Radius": 4, "player Damage": 0, "structure Damage": 100000,
                           "visible During Game": False, "knockbackPlayer": 0})
            b.bind(trig, "OnTriggered", boom, "Explode")
            b.bind(boom, "On Exploded", boom, "Reset")
            all_booms.append(boom)
        print(f"lane {d['code']} ready")

    place_pressure(b, p)
    place_melee(b, p)
    place_enclosure(b, p)
    place_edit_walls(b, p)
    place_switch_targets(b, p)
    place_combat(b)

    for a in p["armory"]:
        x, y = a["pos"]
        b.device(ITEM_SPAWNER, f"KT_Armory_{a['name']}", x, y, 0.0)
    cx, cy = p["buttons"]["clear"]
    b.device(ITEM_REMOVER, "KT_Armory_ClearInventory", cx, cy, 0.0)
    rx, ry = p["buttons"]["reset"]
    reset = b.device(BUTTON, "KT_Armory_ResetAllBuilds", rx, ry, 0.0, 90.0)
    events = b.m.tool(DEVICE, "GetBindingOptions", devicePath={"refPath": reset}) or {}
    ev = next((e for e in events.get("sourceEvents", []) if "nteract" in e), None)
    if ev:
        for boom in all_booms:
            b.bind(reset, ev, boom, "Explode")
    print(f"armory placed (reset button event: {ev})")

    sx, sy = p["spawn"]
    for s in b.m.tool(SCENE, "find_actors", name="Player Spawner", collision_channels=[]) or []:
        b.m.tool(ACTOR, "set_actor_transform", actor={"refPath": s["actorPath"]}, xform=xform(sx - 512, sy, 0.0))
    auto = {a["label"]: a["actorPath"] for a in b.m.tool(SCENE, "find_actors", name="KT_AutoTest", collision_channels=[]) or []}
    if "KT_AutoTest" in auto:
        x, y = hub_cc(4, -4)
        b.m.tool(ACTOR, "set_actor_transform", actor={"refPath": auto["KT_AutoTest"]}, xform=xform(x, y, -700.0))   # below the floor, out of the way
    print("done")


if __name__ == "__main__":
    main()
