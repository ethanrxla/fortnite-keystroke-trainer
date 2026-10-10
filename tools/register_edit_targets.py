"""Register authored edit targets (walls, floors, stairs, roofs) from their actual transforms. No empty grid planes.

    python tools/register_edit_targets.py

Writes shared/edit-targets.json and verse/KeystrokeTrainer/EditTargets.verse. Piece geometry (measured in the editor):
  wall   PBWA_W1_Solid   pivot = bottom centre of the wall; 512 wide, 384 high; plane normal = local +Y.
  floor  PBWA_W1_Floor   pivot = middle of the near edge; the 512 x 512 footprint extends 512 along local +Y, so the
                         centre is the pivot + 256 along the normal.
  roof   PBWA_W1_RoofC   same footprint rule; treated as a horizontal plane ROOF_PLANE_Z above its base.
  stairs PBWA_W1_StairW  same footprint rule; the slab RISES toward its pivot edge and falls toward local +Y (high edge
                         at the pivot, 384 up; low edge 512 away), so Rise = 384 and the surface drops along the normal.
A lab piece's label may carry its edit goal: KT12_Lab_<kind>_<goal id>_<n>, e.g. KT12_Lab_floor_floor_hole_near_left_0.
"""
import json
import math
import re
from pathlib import Path

import build_map as b

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"_Solid": "wall", "_Floor": "floor", "_RoofC": "roof", "_StairW": "stairs"}
ROOF_PLANE_Z = 90.0
FOOTPRINT = 512.0
WALL_GOALS = [("E2", "window_center"), ("E4", "half_wall"), ("E5", "window_center"), ("E7", "side_peek_right")]
LAB_LABEL = re.compile(r"^KT12_Lab_(wall|floor|stairs|roof)_(.+)_(\d+)$")


def kind_of(class_path):
    for suffix, kind in KINDS.items():
        if "PBWA_" in class_path and class_path.rsplit(".", 1)[-1].replace("_C", "").endswith(suffix):
            return kind
    return None


def goal_of(label, kind, known_goals):
    for code, edit in WALL_GOALS:
        if label.startswith("KT_EditWall_" + code + "_"):
            return edit
    m = LAB_LABEL.match(label)
    if m and m.group(1) == kind and m.group(2) in known_goals:
        return m.group(2)
    return ""


def describe(label, path, kind, loc, rot, scale, goal):
    yaw = math.radians(rot["yaw"])
    right = {"x": math.cos(yaw), "y": math.sin(yaw), "z": 0.0}
    normal = {"x": -math.sin(yaw), "y": math.cos(yaw), "z": 0.0}
    centre = dict(loc)
    width, height, depth, rise = FOOTPRINT * scale["x"], 384.0 * scale["z"], FOOTPRINT * scale["y"], 0.0
    if kind != "wall":
        centre = {"x": loc["x"] + normal["x"] * depth / 2.0, "y": loc["y"] + normal["y"] * depth / 2.0, "z": loc["z"]}
        height = depth
    if kind == "roof":
        centre["z"] += ROOF_PLANE_Z
    if kind == "stairs":
        rise = 384.0 * scale["z"]
    return dict(label=label, path=path, kind=kind, centre=centre, right=right, normal=normal,
                width=width, height=height, depth=depth, rise=rise, goal=goal)


def verse_vec(p):
    return "vector3{" + ", ".join(k.upper() + " := " + str(float(v)) for k, v in p.items()) + "}"


def write_verse(defs):
    lines = [
        "# Generated authored edit-target transforms (walls, floors, stairs, roofs), never a claim that arbitrary builds exist.",
        "using { /UnrealEngine.com/Temporary/SpatialMath }",
        "kt_edit_wall_def<public> := struct<computes>:",
        '    Id:string = ""',
        '    Kind:string = "wall"',
        "    Centre:vector3 = vector3{}",
        "    Right:vector3 = vector3{}",
        "    Normal:vector3 = vector3{}",
        "    Width:float = 512.0",
        "    Height:float = 384.0",
        "    Depth:float = 512.0",
        "    Rise:float = 0.0",
        '    Goal:string = ""',
        "KTPracticeWalls<public>:[]kt_edit_wall_def = array:",
    ]
    for d in defs:
        lines.append("    kt_edit_wall_def{Id := " + json.dumps(d["label"]) + ", Kind := " + json.dumps(d["kind"]) +
                     ", Centre := " + verse_vec(d["centre"]) + ", Right := " + verse_vec(d["right"]) +
                     ", Normal := " + verse_vec(d["normal"]) + ", Width := " + str(float(d["width"])) +
                     ", Height := " + str(float(d["height"])) + ", Depth := " + str(float(d["depth"])) +
                     ", Rise := " + str(float(d["rise"])) + ", Goal := " + json.dumps(d["goal"]) + "}")
    (ROOT / "verse/KeystrokeTrainer/EditTargets.verse").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    known = set()
    data = json.loads((ROOT / "shared/edits.json").read_text(encoding="utf-8"))
    for meta in data.get("pieces", {"wall": {"list": "wall_edits"}}).values():
        known |= {e["id"] for e in data.get(meta["list"], [])}
    m = b.Mcp()
    defs = []
    for a in m.tool(b.SCENE, "find_actors", collision_channels=[]):
        kind = kind_of(a["class"]["refPath"])
        if kind is None or (kind != "wall" and not a["label"].startswith("KT12_Lab_")):
            continue     # only lab floors / stairs / roofs are authored targets; stray stairs elsewhere must not trigger the guide
        t = m.tool(b.ACTOR, "get_actor_transform", actor={"refPath": a["actorPath"]})
        if abs(t["rotation"]["pitch"]) > 1 or abs(t["rotation"]["roll"]) > 1:
            continue
        defs.append(describe(a["label"], a["actorPath"], kind, t["location"], t["rotation"], t["scale"],
                             goal_of(a["label"], kind, known)))
    (ROOT / "shared/edit-targets.json").write_text(json.dumps(defs, indent=2), encoding="utf-8")
    write_verse(defs)
    counts = {k: sum(1 for d in defs if d["kind"] == k) for k in KINDS.values()}
    print("Registered", counts, "authored edit targets; dynamic builds remain unverified.")


if __name__ == "__main__":
    main()
