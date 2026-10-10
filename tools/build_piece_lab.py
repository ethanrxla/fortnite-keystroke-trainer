"""Piece Lab: authored floors, stairs, roofs and extra wall edits to practise on (additive; KT12_Lab_* and KT12_Room_*).

    python tools/build_piece_lab.py --dry-run
    python tools/build_piece_lab.py
    python tools/register_edit_targets.py       # then register the new pieces as authored edit targets

An enclosed room east of the tracking arena. Every practice piece is a real player-build class (PBWA_W1_*) labelled
KT12_Lab_<kind>_<edit id>_<n>, so register_edit_targets.py gives the guide its exact pose and its edit goal:
  * floors at floor level, one hole variant each;      * roofs one level up (overhead), one square / two adjacent / diagonal;
  * stairs (no confirmed edits yet, so they show the grid and say so);
  * walls for the edits the first lab does not cover: corners, half arches, high window, quarter wall, peek left.
Players enter from the west wall; the tracking arena holds a teleporter into the lab (group V) and one back (group W).
A rerun replaces only KT12_* actors. The pieces face the entrance so the guide's near/far axes match what the player sees.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT12_"
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
CLASS = {k: f"{PIECES}PBWA_W1_{n}.PBWA_W1_{n}_C" for k, n in (("wall", "Solid"), ("floor", "Floor"), ("stairs", "StairW"), ("roof", "RoofC"))}
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
HEIGHT = 1000.0
ROOM_CELLS = 12
YAW_FACING_WEST = 90.0       # wall normal = (-1, 0): faces a player who walks in from the west and looks east

ROWS = [
    ("floor", 0.0, ["floor_hole_near_left", "floor_hole_near_right", "floor_hole_far_left", "floor_hole_far_right"]),
    ("roof", 384.0, ["roof_one_near_left", "roof_one_far_right", "roof_two_near", "roof_two_left", "roof_diagonal_a", "roof_diagonal_b"]),
    ("stairs", 0.0, ["", ""]),
    ("wall", 0.0, ["corner_lower_left", "corner_lower_right", "corner_upper_left", "half_arch_left", "half_arch_right",
                   "window_high", "quarter_wall", "side_peek_left"]),
]


def plan(x0, y0):
    """(label, kind, x, y, z, goal) for every practice piece: one row per kind, 1024 cm apart, rows 1024 cm apart in x."""
    out = []
    for r, (kind, z, goals) in enumerate(ROWS):
        x = x0 + (4 + 2 * r) * bm.CELL
        span = len(goals)
        for n, goal in enumerate(goals):
            y = y0 + (ROOM_CELLS * bm.CELL) / 2.0 + (n - (span - 1) / 2.0) * 1.5 * bm.CELL
            label = f"KT12_Lab_{kind}_{goal}_{n}" if goal else f"KT12_Lab_{kind}_open_{n}"
            out.append((label, kind, x, y, z, goal))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    arena = m.tool(bm.ACTOR, "get_actor_bounds", actor={"refPath": acts["KT11_Track_Floor"]})
    x0 = arena["max"]["x"] + 2 * bm.CELL                       # a two-cell gap east of the tracking arena
    y0 = arena["min"]["y"]
    x1, y1 = x0 + ROOM_CELLS * bm.CELL, y0 + ROOM_CELLS * bm.CELL
    yc = (y0 + y1) / 2.0
    pieces = plan(x0, y0)
    print(f"piece lab: x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f}; {len(pieces)} practice pieces")
    for label, kind, x, y, z, goal in pieces:
        print(f"  {label:44} x={x:8.0f} y={y:9.0f} z={z:4.0f}")
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})

    # Room: floor, three walls (the west side is the entrance, open to the teleporter pad), ceiling, lights
    b.slab({"label": PREFIX + "Room_Floor", "bounds": (x0, x1, y0, y1), "top": 0.0, "thick": 100.0, "mat": "Edit"})
    b.slab({"label": PREFIX + "Room_Wall_E", "bounds": (x1, x1 + 20, y0, y1), "top": HEIGHT, "thick": HEIGHT, "mat": "Edit"})
    b.slab({"label": PREFIX + "Room_Wall_N", "bounds": (x0, x1, y1, y1 + 20), "top": HEIGHT, "thick": HEIGHT, "mat": "Edit"})
    b.slab({"label": PREFIX + "Room_Wall_S", "bounds": (x0, x1, y0 - 20, y0), "top": HEIGHT, "thick": HEIGHT, "mat": "Edit"})
    b.slab({"label": PREFIX + "Room_Wall_W", "bounds": (x0 - 20, x0, y0, y1), "top": HEIGHT, "thick": HEIGHT, "mat": "Edit"})
    b.slab({"label": PREFIX + "Room_Ceiling", "bounds": (x0, x1, y0, y1), "top": HEIGHT + 100, "thick": 100, "mat": "Edit"})
    for i, fx in enumerate((0.15, 0.4, 0.65, 0.9)):
        for j, fy in enumerate((0.2, 0.5, 0.8)):
            b.device(LIGHT, f"{PREFIX}Room_Light_{i}{j}", x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy, HEIGHT - 150)
    b.sign({"label": PREFIX + "Room_Sign", "pos": (x0 + bm.CELL, y0 + 0.4 * bm.CELL, 380), "yaw": 0, "zone": "Edit", "size": 44,
            "text": "PIECE LAB\nfloors, stairs, roofs and wall edits\nbuild tool out + aim at a piece: the guide shows its grid"})

    # Practice pieces
    for label, kind, x, y, z, goal in pieces:
        ref = m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=CLASS[kind], name=label,
                     xform=bm.xform(x, y, z, yaw=YAW_FACING_WEST))["refPath"]
        b.labelled(ref, label)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})

    # Teleporters: arena -> lab (group V), lab -> arena (group W)
    near_x = acts["KT11_Track_Floor"]
    arena_b = m.tool(bm.ACTOR, "get_actor_bounds", actor={"refPath": near_x})
    ax = arena_b["min"]["x"] + 1.5 * bm.CELL
    ay = (arena_b["min"]["y"] + arena_b["max"]["y"]) / 2.0
    gate = {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_V"}
    to_lab = b.device(bm.TELEPORTER, PREFIX + "Gate_ToLab", ax, ay + 3 * bm.CELL, 0.0)
    b.props(to_lab, gate)
    lab_in = b.device(bm.TELEPORTER, PREFIX + "Gate_LabIn", x0 + 1.5 * bm.CELL, yc, 0.0)
    b.props(lab_in, {"knob_TeleporterGroup": "Group_V", "knob_TargetTeleporterGroup": "Group_None", "teleporter Rift Visible": False})
    back = b.device(bm.TELEPORTER, PREFIX + "Gate_ToArena", x0 + 1.5 * bm.CELL, y0 + 1.2 * bm.CELL, 0.0)
    b.props(back, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_W"})
    arena_in = b.device(bm.TELEPORTER, PREFIX + "Gate_ArenaIn", ax, ay - 3 * bm.CELL, 0.0)
    b.props(arena_in, {"knob_TeleporterGroup": "Group_W", "knob_TargetTeleporterGroup": "Group_None", "teleporter Rift Visible": False})
    b.sign({"label": PREFIX + "Gate_Sign", "pos": (ax, ay + 3 * bm.CELL - 300, 300), "yaw": 180, "zone": "Edit", "size": 40,
            "text": "PIECE LAB >\nfloors, stairs, roofs, more wall edits"})
    print("placed room, pieces and teleporters (groups V and W)")


if __name__ == "__main__":
    main()
