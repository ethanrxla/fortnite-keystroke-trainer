"""One vocabulary for build pieces, shared by every module, the attempt records and the database.

Canonical names are what players say: wall, floor, cone, ramp. shared/edits.json and the Verse catalog still key their
lists by the older names (roof, stairs); `catalog_key` maps a canonical name to that key and `canonical` maps anything
back. Everything new (attempt records, Supabase rows, the ranker's public API) uses canonical names only.
"""

CANONICAL = ("wall", "floor", "cone", "ramp")
_TO_CANONICAL = {"wall": "wall", "floor": "floor", "cone": "cone", "roof": "cone", "ramp": "ramp", "stairs": "ramp"}
_TO_CATALOG = {"wall": "wall", "floor": "floor", "cone": "roof", "ramp": "stairs"}
GRID = {"wall": 3, "floor": 2, "cone": 2, "ramp": 3}   # ramps 3 x 3 on the slope (player 2026-10-22)


def canonical(name):
    """Canonical piece name for any alias, or None for unknown / missing."""
    return _TO_CANONICAL.get((name or "").lower())


def catalog_key(name):
    """The key shared/edits.json `pieces` uses for this piece (roof for cone, stairs for ramp)."""
    c = canonical(name)
    return _TO_CATALOG.get(c) if c else None


def cells(name):
    """Edit grid size: 3 for walls and ramps (3x3), 2 for floors and cones (2x2)."""
    return GRID.get(canonical(name), 3)
