"""One vocabulary for build pieces, shared by every module, the attempt records and the database.

Canonical names are what players say: wall, floor, cone, ramp. shared/edits.json and the Verse catalog still key their
lists by the older names (roof, stairs); `catalog_key` maps a canonical name to that key and `canonical` maps anything
back. Everything new (attempt records, Supabase rows, the ranker's public API) uses canonical names only.
"""

CANONICAL = ("wall", "floor", "cone", "ramp")
_TO_CANONICAL = {"wall": "wall", "floor": "floor", "cone": "cone", "roof": "cone", "ramp": "ramp", "stairs": "ramp"}
_TO_CATALOG = {"wall": "wall", "floor": "floor", "cone": "roof", "ramp": "stairs"}
GRID = {"wall": 3, "floor": 2, "cone": 2, "ramp": 3}   # ramps 3 x 3 on the slope (player 2026-10-22)
# The screen cannot tell a floor's 2x2 grid from a cone's reliably, and both have the same 14 tile selections, so a 2x2
# is observed as piece "floor" with this orientation and shown as "floor / cone" (player 2026-10-22).
FLOOR_OR_CONE = "floor_or_cone"
_SIDE = {(0,): "near left", (1,): "near right", (2,): "far left", (3,): "far right", (0, 1): "near side",
         (2, 3): "far side", (0, 2): "left side", (1, 3): "right side", (0, 3): "diagonal", (1, 2): "diagonal"}
_KEPT = {(1, 2, 3): "near left", (0, 2, 3): "near right", (0, 1, 3): "far left", (0, 1, 2): "far right"}


def canonical(name):
    """Canonical piece name for any alias, or None for unknown / missing."""
    return _TO_CANONICAL.get((name or "").lower())


def catalog_key(name):
    """The key shared/edits.json `pieces` uses for this piece (roof for cone, stairs for ramp)."""
    c = canonical(name)
    return _TO_CATALOG.get(c) if c else None


def flat_name(tiles):
    """A 2x2 edit named by its tiles, the same on a floor and a cone: "1 tile (near left)", "2 tiles (diagonal)".
    Tiles 0 near-left, 1 near-right, 2 far-left, 3 far-right."""
    key = tuple(sorted(set(tiles)))
    if key in _SIDE:
        return f"{len(key)} tile{'s' if len(key) > 1 else ''} ({_SIDE[key]})"
    if key in _KEPT:
        return f"3 tiles ({_KEPT[key]} kept)"
    return f"{len(key)} tiles"


def cells(name):
    """Edit grid size: 3 for walls and ramps (3x3), 2 for floors and cones (2x2)."""
    return GRID.get(canonical(name), 3)
