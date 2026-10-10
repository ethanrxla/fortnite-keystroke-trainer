"""Complete shared/edits.json with every build piece and edit shape Fortnite ships (idempotent).

    python tools/add_build_shapes.py && python tools/gen_edits.py

What it adds (never suggested, never marked verified; the review pipeline confirms shapes in game):
  * per piece: the piece class (Wall / Floor / Stair / Cone), its unedited result class and how edit tiles behave
    (`edit_semantics`: walls, floors and cones remove the selected tiles; a ramp keeps the drawn path as stairs),
  * per edit: `result_class`, the Fortnite build actor the edit turns the piece into (PBWA_W1_<class>),
  * the wall edits the library was missing (pillar, door + window, half-wall doors, half-wall slim),
  * every ramp path: half ramps (2 tiles), L ramps (3 tiles) and spiral ramps (4 tiles), each in drag order.

Where the classes come from: on 2026-10-10 every PBWA_W1_* class in /Game/Building/ActorBlueprints/Player/Wood/L1
(34 of them) was placed in UEFN and photographed face-on and top-down. The class -> tiles mapping below is read from
those pictures; `result_class_status` says how sure it is ("probe_matched" = the shape in the picture is exactly this
tile set; "probe_inferred" = right family, exact tiles or mirror side unconfirmed). VERIFY in game before anything
depends on a class (for example spawning a result mesh).
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = "UEFN build-class probe 2026-10-10 (PBWA_W1_* placed and photographed); unconfirmed tile set"

# Piece metadata merged into edits.json `pieces`. Keys already there (cols, rows, list, build_slot, tile_order) are kept.
PIECES = {
    "wall": {"class": "Wall", "canonical": "wall", "base_class": "Solid", "edit_semantics": "remove_selected"},
    "floor": {"class": "Floor", "canonical": "floor", "base_class": "Floor", "edit_semantics": "remove_selected"},
    "stairs": {"class": "Stair", "canonical": "ramp", "base_class": "StairW", "edit_semantics": "keep_path"},
    "roof": {"class": "Cone", "canonical": "cone", "base_class": "RoofC", "edit_semantics": "remove_selected"},
}

# Result class per existing edit id: (class, status). Missing ids have no class identified yet.
RESULT = {
    "window_center": ("WindowC", "probe_matched"),
    "door": ("DoorC", "probe_matched"),
    "half_wall": ("HalfWallS", "probe_matched"),
    "quarter_wall": ("QuarterWallS", "probe_matched"),
    "corner_lower_left": ("Brace", "probe_inferred"),
    "corner_lower_right": ("Brace", "probe_matched"),
    "corner_upper_left": ("RoofWall", "probe_matched"),
    "corner_upper_right": ("RoofWall", "probe_inferred"),
    "half_arch_left": ("ArchwayLarge", "probe_inferred"),
    "half_arch_right": ("ArchwayLarge", "probe_matched"),
    "side_peek_right": ("WindowSide", "probe_matched"),
    "side_peek_left": ("WindowSide", "probe_inferred"),
    "slim_wall_right": ("ArchwayLargeSupport", "probe_inferred"),
    "slim_wall_left": ("ArchwayLargeSupport", "probe_inferred"),
    "tiny_wall_left": ("QuarterWallHalf", "probe_inferred"),
    "tiny_wall_right": ("QuarterWallHalf", "probe_inferred"),
    "arch": ("Archway", "probe_matched"),
    "side_door_left": ("DoorSide", "probe_inferred"),
    "side_door_right": ("DoorSide", "probe_matched"),
    "stairs_open_left": ("StairF", "probe_inferred"),
    "stairs_open_right": ("StairF", "probe_inferred"),
    "stairs_l_left": ("StairR", "probe_inferred"),
    "stairs_l_right": ("StairR", "probe_inferred"),
}
# 2x2 remove-selected pieces: the class follows from what is left (I = three tiles kept, S = two side by side,
# D = two diagonal, O = one). Floors: Balcony*, cones: Roof*.
FAMILY = {"floor": "Balcony", "roof": "Roof"}

# Shapes seen in the probe that the library did not have. (id, name, tiles, mirror_of, purpose, exposure, when, class)
WALLS = [
    ("window_double", "Double window (both side windows)", [3, 5], None, ["peek", "shoot"], "medium",
     "Left and right middle tiles: two windows with the centre post kept. (The whole middle row would leave the top "
     "row floating; the probe shows this centre-post piece instead.)", ("Windows", "probe_matched")),
    ("pillar", "Pillar (centre column stays)", [0, 3, 6, 2, 5, 8], None, ["enter", "pass_through"], "very_high",
     "Remove both side columns: a single post stays, almost all of the wall is open.", ("Pillar", "probe_inferred")),
    ("door_window_left", "Door left + window right", [0, 3, 5], "door_window_right", ["enter", "peek"], "high",
     "A side door with a side window across from it.", ("DoorS", "probe_inferred")),
    ("door_window_right", "Door right + window left", [2, 5, 3], "door_window_left", ["enter", "peek"], "high",
     "A side door with a side window across from it.", ("DoorS", "probe_matched")),
    ("half_wall_door", "Half wall with door", [6, 7, 8, 4, 1], None, ["enter", "pass_through"], "very_high",
     "Top row plus the centre door: a low wall with a gate in the middle.", ("HalfWallDoor", "probe_matched")),
    ("half_wall_side_door_left", "Half wall with side door (left)", [6, 7, 8, 3, 0], "half_wall_side_door_right",
     ["enter", "pass_through"], "very_high", "Top row plus the left door: a low wall with a gate at the side.",
     ("HalfWallDoorS", "probe_inferred")),
    ("half_wall_side_door_right", "Half wall with side door (right)", [6, 7, 8, 5, 2], "half_wall_side_door_left",
     ["enter", "pass_through"], "very_high", "Top row plus the right door: a low wall with a gate at the side.",
     ("HalfWallDoorS", "probe_matched")),
    ("half_wall_slim_left", "Half wall, slim (left column stays)", [8, 7, 6, 5, 4, 1, 2], "half_wall_slim_right",
     ["cover"], "very_high", "Only the bottom two tiles of one column stay: a narrow low post.",
     ("HalfWallHalf", "probe_inferred")),
    ("half_wall_slim_right", "Half wall, slim (right column stays)", [6, 7, 8, 3, 4, 1, 0], "half_wall_slim_left",
     ["cover"], "very_high", "Only the bottom two tiles of one column stay: a narrow low post.",
     ("HalfWallHalf", "probe_inferred")),
]

# Ramp paths. A ramp's 2 x 2 tiles form a ring 0 -> 1 -> 3 -> 2 -> 0 (near-left, near-right, far-right, far-left).
# The player draws the stairs from the bottom tile up; the order is the climb.
RING = [0, 1, 3, 2]
LABEL = {0: "nl", 1: "nr", 2: "fl", 3: "fr"}
WORDS = {0: "near left", 1: "near right", 2: "far left", 3: "far right"}
RAMP_KIND = {2: ("half", "Half ramp", "StairF", ["climb", "pass_through"], "high",
                 "A one-tile-wide ramp: half the material face, the other half open to walk or shoot past."),
             3: ("l", "L ramp", "StairR", ["climb", "protect"], "medium",
                 "Stairs that turn a corner: climb while turning, keeping cover on the turn."),
             4: ("spiral", "Spiral ramp", "StairSpiral", ["climb", "protect"], "low",
                 "Stairs that wind round all four tiles: climb a full storey inside one cell.")}


def mirror_tile(t):
    return t ^ 1          # 2 x 2 column flip: 0 <-> 1, 2 <-> 3


def ramp_paths():
    """Every simple path of 2-4 tiles around the ring, in climb order."""
    seen, out = set(), []
    for length in (2, 3, 4):
        for start in range(4):
            for step in (1, -1):
                path = [RING[(start + step * k) % 4] for k in range(length)]
                if tuple(path) not in seen:
                    seen.add(tuple(path))
                    out.append(path)
    return out


def ramp_id(path):
    kind = RAMP_KIND[len(path)][0]
    return f"ramp_{kind}_" + "_".join(LABEL[t] for t in path)


def ramp_entry(path):
    kind, title, cls, purpose, exposure, when = RAMP_KIND[len(path)]
    mirror = [mirror_tile(t) for t in path]
    return {
        "id": ramp_id(path), "name": f"{title} ({WORDS[path[0]]} up to {WORDS[path[-1]]})", "tiles": list(path),
        "path": list(path), "kind": "grid", "mirror_of": ramp_id(mirror) if mirror != path else None,
        "suggest": False, "confirmed": False, "purpose": purpose, "exposure": exposure,
        "cover_left": len(path), "difficulty": len(path) - 1, "when_to_use": when, "source": SOURCE,
        "result_class": cls, "result_class_status": "probe_inferred",
        "validation": {"status": "unverified", "game_version": None, "evidence": [], "result_confirmed": False,
                       "reason": "Ramp path from the build-class probe; confirm through recorded and reviewed attempts."},
    }


def wall_entry(eid, name, tiles, mirror, purpose, exposure, when, result):
    return {
        "id": eid, "name": name, "tiles": tiles, "kind": "wall", "mirror_of": mirror, "suggest": False,
        "confirmed": False, "purpose": purpose, "exposure": exposure, "cover_left": 9 - len(tiles), "difficulty": 2,
        "when_to_use": when, "source": SOURCE, "result_class": result[0], "result_class_status": result[1],
        "validation": {"status": "unverified", "game_version": None, "evidence": [], "result_confirmed": False,
                       "reason": "Shape from the build-class probe; confirm through recorded and reviewed attempts."},
    }


def family_class(piece, tiles):
    kept = sorted(set(range(4)) - set(tiles))
    if len(kept) == 3:
        suffix = "I"
    elif len(kept) == 1:
        suffix = "O"
    elif len(kept) == 2:
        suffix = "D" if kept in ([0, 3], [1, 2]) else "S"
    else:
        return None
    return FAMILY[piece] + suffix


def main():
    path = ROOT / "shared/edits.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for piece, meta in PIECES.items():
        for k, v in meta.items():
            data["pieces"][piece].setdefault(k, v)
    data["_pieces_classes_note"] = (
        "class / base_class / edit_semantics / result_class: tools/add_build_shapes.py, from the 2026-10-10 UEFN probe "
        "of every PBWA_W1_* build class. remove_selected = the tiles you select are cut out; keep_path = the tiles you "
        "drag through, in order from the bottom, become the stairs. Classes are PBWA_W1_<class>; VERIFY in game.")
    added = []
    walls = data["wall_edits"]
    have = {e["id"] for lst in (data[m["list"]] for m in data["pieces"].values()) for e in lst}
    masks = {frozenset(e["tiles"]) for e in walls}
    for row in WALLS:
        if row[0] not in have and frozenset(row[2]) not in masks:
            walls.append(wall_entry(*row))
            added.append(row[0])
    stairs = data["stairs_edits"]
    for p in ramp_paths():
        if ramp_id(p) not in have:
            stairs.append(ramp_entry(p))
            added.append(ramp_id(p))
    for piece, meta in data["pieces"].items():
        for e in data[meta["list"]]:
            if "result_class" in e:
                continue
            if e["id"] in RESULT:
                e["result_class"], e["result_class_status"] = RESULT[e["id"]]
            elif piece in FAMILY and family_class(piece, e["tiles"]):
                e["result_class"], e["result_class_status"] = family_class(piece, e["tiles"]), "probe_inferred"
            else:
                e["result_class"], e["result_class_status"] = None, "unidentified"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    ledger_path = ROOT / "shared/edit-coverage.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for piece, meta in data["pieces"].items():
        if piece not in ledger["pieces"]:
            continue
        for e in data[meta["list"]]:
            slot = ledger["pieces"][piece][sum(1 << t for t in e["tiles"])]
            if e["id"] not in slot["edit_ids"]:
                slot["edit_ids"].append(e["id"])
    ledger["ramp"] = ("Ramps are ordered paths, not masks: every 2-4 tile path round the ring is a stairs_edits entry "
                      "with `path` (tools/add_build_shapes.py). Gesture graphs still require separate validation.")
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print("added:", ", ".join(added) if added else "nothing (already present)")


if __name__ == "__main__":
    main()
