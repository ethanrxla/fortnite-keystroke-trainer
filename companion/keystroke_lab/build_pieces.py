"""Build pieces as data: four piece classes, edit state as a tile bitmask, and one table of every valid edit shape.

    piece = piece_for("wall")                   # WallPiece / FloorPiece / StairPiece / ConePiece
    piece.select(4)                             # edit mode: toggle tiles (or set the whole selection)
    outcome = piece.confirm(PatternTable())     # match against the library; unsupported or floating shapes are rejected
    visual = piece.visual()                     # which tiles to show / collide, and the Fortnite class to swap in

Everything comes from shared/edits.json (`pieces` for the grid, class and edit semantics; the *_edits lists for the
shapes), so a new edit is a data change, never a new class. The same model is in Verse (BuildPieces.verse, patterns
generated into EditPatterns.verse by tools/gen_edits.py).

Tile order (as everywhere else in this repo): walls 0..8 row-major from the bottom-left as the player sees the wall;
2 x 2 pieces 0 near-left, 1 near-right, 2 far-left, 3 far-right (for a ramp, far = the high end).

Edit semantics:
  remove_selected (wall, floor, cone)  the selected tiles are cut out; what is left must be one connected part unless
                                       the library knows the shape as a real Fortnite piece (a door joins two halves).
  keep_path (ramp)                     the tiles dragged through, bottom first, become the stairs; order matters, so a
                                       ramp's state is a path and its patterns are matched by path, not by mask.
"""
from dataclasses import dataclass, field
import json
import pathlib

from .pieces import canonical, catalog_key

SHARED = pathlib.Path(__file__).resolve().parents[2] / "shared"
CELL_CM = 512.0          # build grid cell
LEVEL_CM = 384.0         # one build level (VERIFY, AGENTS.md)
MATERIALS = {"wood": "W1", "stone": "S1", "metal": "M1"}            # PBWA_<code>_<class>; S1 / M1 VERIFY
MAX_HEALTH = {"wood": 150, "stone": 300, "metal": 500}             # fully built wall, BR values (VERIFY per piece)
CLASS_ROOT = "/Game/Building/ActorBlueprints/Player/{folder}/L1/PBWA_{code}_{name}.PBWA_{code}_{name}_C"
FOLDER = {"W1": "Wood", "S1": "Stone", "M1": "Metal"}


def class_path(name, material="wood"):
    """Asset class path of a Fortnite build result class (e.g. "DoorC"). Only the wood path is confirmed."""
    if not name:
        return None
    code = MATERIALS.get(material, "W1")
    return CLASS_ROOT.format(folder=FOLDER[code], code=code, name=name)


@dataclass(frozen=True)
class EditPattern:
    """One valid edit shape: the selection (mask, plus the path for ramps) and what the piece becomes."""
    id: str
    piece: str                # canonical piece name
    mask: int                 # selected tiles as a bitmask (bit t = tile t)
    path: tuple = ()          # ramps: tiles in climb order; others: the library's drag order
    name: str = ""
    result_class: str = None  # PBWA_W1_<result_class>, None when not identified
    suggest: bool = False     # the guide may recommend it
    status: str = "unverified"

    def rows(self, cols, rows):
        """The mask as bool rows, bottom (or near) row first: the "2D bool array" view of the shape."""
        return [[bool(self.mask >> (r * cols + c) & 1) for c in range(cols)] for r in range(rows)]


@dataclass(frozen=True)
class EditOutcome:
    valid: bool
    pattern: EditPattern = None
    reason: str = ""          # "", "no_edit", "nothing_left", "floating", "broken_path", "unsupported_shape"
    kept: int = 0             # tiles that stay solid, as a bitmask


@dataclass(frozen=True)
class PieceVisual:
    """What the one update function produces: per tile, shown and colliding, plus the class to swap in."""
    visible: tuple            # tile indexes drawn
    collision: tuple          # tile indexes that block
    result_class: str = None
    class_path: str = None
    selected: tuple = ()      # tiles highlighted while still in edit mode


class BuildPiece:
    """Health, material, grid cell and the edit state shared by every piece. Subclasses only set grid and rules."""
    kind = "wall"             # canonical name
    cols = rows = 3
    semantics = "remove_selected"
    base_class = "Solid"

    def __init__(self, material="wood", cell=(0, 0, 0), yaw=0):
        self.material = material
        self.health = self.max_health = MAX_HEALTH.get(material, 150)
        self.cell = tuple(cell)
        self.yaw = yaw % 360
        self.selection = ()   # tiles in the order they were selected
        self.applied = None   # EditOutcome of the last confirmed edit, None = unedited

    # -- grid -----------------------------------------------------------------------------------------------------------
    @property
    def tiles(self):
        return self.cols * self.rows

    @property
    def full(self):
        return (1 << self.tiles) - 1

    @staticmethod
    def mask_of(tiles):
        return sum(1 << t for t in set(tiles))

    def tiles_of(self, mask):
        return tuple(t for t in range(self.tiles) if mask >> t & 1)

    def neighbours(self, t):
        c, r = t % self.cols, t // self.cols
        return [r * self.cols + c + dc for dc in (-1, 1) if 0 <= c + dc < self.cols] + \
               [(r + dr) * self.cols + c for dr in (-1, 1) if 0 <= r + dr < self.rows]

    def mirror(self, tiles):
        """Left/right mirror (column c -> cols - 1 - c), order kept."""
        return tuple(t - 2 * (t % self.cols) + self.cols - 1 for t in tiles)

    def parts(self, mask):
        """Number of 4-connected groups of tiles in `mask`."""
        left, count = set(self.tiles_of(mask)), 0
        while left:
            count += 1
            stack = [left.pop()]
            while stack:
                for n in self.neighbours(stack.pop()):
                    if n in left:
                        left.remove(n)
                        stack.append(n)
        return count

    @classmethod
    def snap(cls, location_cm):
        """World location (cm) -> build grid cell (x, y, level)."""
        x, y, z = location_cm
        return (int(x // CELL_CM), int(y // CELL_CM), int(z // LEVEL_CM))

    # -- edit state -----------------------------------------------------------------------------------------------------
    def select(self, tile):
        """Toggle a tile in edit mode (re-selecting a tile deselects it, as in game)."""
        if not 0 <= tile < self.tiles:
            raise ValueError(f"tile {tile} outside a {self.cols} x {self.rows} {self.kind}")
        self.selection = tuple(t for t in self.selection if t != tile) if tile in self.selection else self.selection + (tile,)
        return self.selection

    def set_selection(self, tiles):
        for t in tiles:
            if not 0 <= t < self.tiles:
                raise ValueError(f"tile {t} outside a {self.cols} x {self.rows} {self.kind}")
        self.selection = tuple(dict.fromkeys(tiles))
        return self.selection

    def reset(self):
        """Edit reset: back to the full piece."""
        self.selection, self.applied = (), None

    def kept(self, selection):
        """Tiles that stay solid for this selection, as a mask."""
        return self.full & ~self.mask_of(selection)

    def check(self, selection):
        """Rule-only check (no table): reason string, or "" when the shape could exist."""
        if not selection:
            return "no_edit"
        kept = self.kept(selection)
        if not kept:
            return "nothing_left"
        return "" if self.parts(kept) == 1 else "floating"

    def confirm(self, table):
        """Apply the current selection: it must match a library shape. Unsupported shapes leave the piece unchanged."""
        outcome = table.match(self, self.selection)
        if outcome.valid:
            self.applied = outcome
        self.selection = ()
        return outcome

    # -- the one update function -----------------------------------------------------------------------------------------
    def visual(self):
        """Visible and colliding tiles plus the result class, from the edit state. Used by every renderer."""
        if self.applied is None or self.applied.pattern is None:
            kept, cls = self.full, self.base_class
        else:
            kept, cls = self.applied.kept, self.applied.pattern.result_class
        shown = self.tiles_of(kept)
        return PieceVisual(shown, shown, cls, class_path(cls, self.material), tuple(self.selection))


class WallPiece(BuildPiece):
    kind, cols, rows, base_class = "wall", 3, 3, "Solid"


class TwoByTwoPiece(BuildPiece):
    cols = rows = 2

    def rotate(self, tiles, quarter_turns=1):
        """Turn a 2 x 2 selection clockwise as seen from above (near-left -> far-left -> far-right -> near-right)."""
        ring = [0, 2, 3, 1]
        return tuple(ring[(ring.index(t) + quarter_turns) % 4] for t in tiles)


class FloorPiece(TwoByTwoPiece):
    kind, base_class = "floor", "Floor"


class ConePiece(TwoByTwoPiece):
    kind, base_class = "cone", "RoofC"


class StairPiece(TwoByTwoPiece):
    """A ramp keeps the drawn path. Its state is the ordered path, bottom tile first."""
    kind, base_class, semantics = "ramp", "StairW", "keep_path"

    def kept(self, selection):
        return self.mask_of(selection) if selection else self.full

    def select(self, tile):
        # Drawing a ramp is a drag: going back onto the previous tile undoes the last step, any other tile extends.
        if len(self.selection) >= 2 and tile == self.selection[-2]:
            self.selection = self.selection[:-1]
            return self.selection
        if tile in self.selection:
            return self.selection
        return super().select(tile)

    def check(self, selection):
        if not selection:
            return "no_edit"
        if len(selection) < 2 or len(set(selection)) != len(selection):
            return "broken_path"
        if any(b not in self.neighbours(a) for a, b in zip(selection, selection[1:])):
            return "broken_path"
        return ""


PIECES = {"wall": WallPiece, "floor": FloorPiece, "cone": ConePiece, "ramp": StairPiece}


def piece_for(name, **kwargs):
    """A new piece of the canonical kind for any alias (roof = cone, stairs = ramp)."""
    kind = canonical(name)
    if kind not in PIECES:
        raise ValueError(f"unknown build piece {name!r}")
    return PIECES[kind](**kwargs)


class PatternTable:
    """Every edit shape in shared/edits.json, keyed by piece and mask (ramps by path). The arbiter of valid edits."""

    def __init__(self, path=None):
        data = json.loads(pathlib.Path(path or SHARED / "edits.json").read_text(encoding="utf-8"))
        self.by_mask, self.by_path, self.all = {}, {}, {}
        for key, meta in data["pieces"].items():
            kind = canonical(key)
            for e in data.get(meta["list"], []):
                tiles = tuple(e.get("path") or e.get("tiles") or ())
                if not tiles:
                    continue
                p = EditPattern(e["id"], kind, BuildPiece.mask_of(tiles), tiles, e.get("name", ""),
                                e.get("result_class"), bool(e.get("suggest")),
                                (e.get("validation") or {}).get("status", "unverified"))
                self.all[p.id] = p
                if meta.get("edit_semantics") == "keep_path" or kind == "ramp":
                    if e.get("path"):
                        self.by_path.setdefault((kind, tiles), p)
                else:
                    self.by_mask.setdefault((kind, p.mask), []).append(p)

    def patterns(self, piece):
        kind = canonical(piece) or piece
        return [p for p in self.all.values() if p.piece == kind]

    def match(self, piece, selection):
        """EditOutcome for applying `selection` to `piece`.

        Valid when the library has the shape and it holds together: the kept tiles form one part, or the shape has a
        known Fortnite result class (a door or a diagonal floor joins its parts in game). Everything else is rejected:
        "floating" when it would leave disconnected parts, "unsupported_shape" when the game has no such edit.
        """
        selection = tuple(selection)
        reason = piece.check(selection)
        kept = piece.kept(selection)
        if reason in ("no_edit", "nothing_left", "broken_path"):
            return EditOutcome(False, None, reason, kept)
        if piece.semantics == "keep_path":
            p = self.by_path.get((piece.kind, selection))
            return EditOutcome(True, p, "", kept) if p else EditOutcome(False, None, "unsupported_shape", kept)
        found = self.by_mask.get((piece.kind, piece.mask_of(selection)), [])
        if not found:
            return EditOutcome(False, None, reason or "unsupported_shape", kept)
        # Several library ids can share a mask (drag-order variants); prefer one with a known result class.
        p = sorted(found, key=lambda x: (x.result_class is None, not x.suggest, x.id))[0]
        if reason == "floating" and p.result_class is None:
            return EditOutcome(False, p, "floating", kept)
        return EditOutcome(True, p, "", kept)

    def coverage(self, piece):
        """{mask: [pattern ids]} for every mask of a remove-selected piece: which of the 2^n selections are edits."""
        p = piece_for(piece)
        return {m: [x.id for x in self.by_mask.get((p.kind, m), [])] for m in range(1, p.full + 1)}


def catalog_list(piece):
    """The edits.json list name for a piece (kept for callers that still read the catalogue directly)."""
    return {"wall": "wall_edits", "floor": "floor_edits", "roof": "roof_edits", "stairs": "stairs_edits"}[catalog_key(piece)]
