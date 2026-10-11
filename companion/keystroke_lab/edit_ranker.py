"""Which edit to suggest: the Python port of the in-game ranking (EditGuide.verse KTRankEdits), for every piece.

    rank(kind, aim, side, far)  ->  [Pick, ...] cheapest first

Inputs are what the player is doing right now:
  kind   wall | floor | stairs | roof   (the piece being edited)
  aim    (u, v) crosshair point on the piece in tiles; walls 0..3 (u left->right, v bottom->top as seen),
         floors / stairs / roofs 0..2 (u left->right, v near->far as seen)
  side   which third of the piece the player stands in, 0 left, 1 centre, 2 right (as seen)
  far    True when the player is more than about half a tile away

Cost = crosshair travel to the first tile + 0.15 x drag length + 0.3 x ln(best prior / this prior). The priors are
Jev's offline table for this situation (shared/edit-policy*.json); a player's personal factors
(shared/edit-policy-personal.json, from `personalize`) scale those priors, so edits this player executes well move up
and edits they fail at move down. Travel always dominates: the prior moves a pick by at most ~0.8 tiles.
Keep in step with EditGuide.verse (KTRankCost, KTSituation, KTShapeSide, KTAimSide, KTPriorWeight).
"""
from dataclasses import dataclass, field
import json
import math
import pathlib

from .pieces import catalog_key
from .build_pieces import get_piece

SHARED = pathlib.Path(__file__).resolve().parents[2] / "shared"
PRIOR_WEIGHT = 0.3
DRAG_WEIGHT = 0.15
POLICY_FILES = {"wall": "edit-policy.json", "floor": "edit-policy-floor.json", "roof": "edit-policy-roof.json",
                "stairs": "edit-policy-stairs.json"}


def cols(kind):
    return 3 if kind == "wall" else 2


@dataclass(frozen=True)
class Pick:
    id: str
    name: str
    tiles: tuple          # in drag order (possibly reversed from the library order)
    cost: float
    travel: float         # tiles of crosshair travel: approach + drag
    prior: float
    factor: float = 1.0   # personal factor applied to the prior
    reasons: dict = field(default_factory=dict)


def centre(t, c):
    return (t % c + 0.5, t // c + 0.5)


def approach(aim, tiles, c):
    return math.dist(aim, centre(tiles[0], c)) if tiles else 99.0


def drag(tiles, c):
    return sum(math.dist(centre(a, c), centre(b, c)) for a, b in zip(tiles, tiles[1:]))


def shape_side(tiles, c):
    mean = sum(t % c for t in tiles) / len(tiles)
    mid = (c - 1) * 0.5
    return -1 if mean < mid - 0.2 else (1 if mean > mid + 0.2 else 0)


def aim_side(aim, c):
    mid, band = c * 0.5, c * 0.05
    return -1 if aim[0] < mid - band else (1 if aim[0] > mid + band else 0)


def situation_key(aim, side, far, c):
    buckets = c * 2
    clamp = lambda v: max(0, min(buckets - 1, math.floor(v * 2)))
    return f"{clamp(aim[0])},{clamp(aim[1])},{max(0, min(2, side))},{int(bool(far))}"


# Corner snap (the player's preference, 2026-10-10): pointing the crosshair at one of the wall's four inner tile corners
# means "that corner edit". The guide then shows the three-tile corner (green tiles + numbered yellow route) instead of
# whichever single-tile edit has slightly less travel. Within SNAP_RADIUS tiles of the junction.
WALL_JUNCTIONS = {(1.0, 1.0): "corner_lower_left", (2.0, 1.0): "corner_lower_right",
                  (1.0, 2.0): "corner_upper_left", (2.0, 2.0): "corner_upper_right"}
SNAP_RADIUS = 0.5


def junction_corner(aim, radius=SNAP_RADIUS):
    """The corner edit for the inner wall junction nearest the crosshair, or None when no junction is that close."""
    if len(aim) != 2:
        return None
    point, edit = min(WALL_JUNCTIONS.items(), key=lambda kv: math.dist(kv[0], aim))
    return edit if math.dist(point, aim) <= radius else None


class Ranker:
    def __init__(self, shared=SHARED, personal=None, policies=None):
        """policies: optional {piece: policy dict or path} replacing the shared tables (to compare policy versions)."""
        shared = pathlib.Path(shared)
        data = json.loads((shared / "edits.json").read_text(encoding="utf-8"))
        self.library, self.policy = {}, {}
        for kind, meta in data["pieces"].items():
            self.library[kind] = [e for e in data.get(meta["list"], []) if e.get("suggest")]
            path = shared / POLICY_FILES.get(kind, "")
            if path.is_file():
                p = json.loads(path.read_text(encoding="utf-8"))
                self.policy[kind] = (p["edits"], p["priors"])
        for kind, p in (policies or {}).items():
            if not isinstance(p, dict):
                p = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
            self.policy[catalog_key(kind) or kind] = (p["edits"], p["priors"])
        if personal is None:
            path = pathlib.Path(__file__).resolve().parents[1] / "data" / "edit-policy-personal.json"
            personal = json.loads(path.read_text(encoding="utf-8")).get("factors", {}) if path.is_file() else {}
        self.personal = dict(personal)

    def edit(self, edit_id):
        return next((e for lib in self.library.values() for e in lib if e["id"] == edit_id), None)

    def prior(self, kind, key, edit_id):
        ids, table = self.policy.get(kind, ([], {}))
        row = table.get(key)
        if row is None or edit_id not in ids:
            return 0.1
        return row[ids.index(edit_id)]

    def rank(self, kind, aim, side=1, far=False):
        kind = catalog_key(kind) or kind          # accepts canonical names (cone, ramp) and catalogue keys
        c = cols(kind)
        if kind not in self.library or len(aim) != 2 or not all(0 <= v < c for v in aim):
            return []
        key = situation_key(aim, side, far, c)
        weighted = {e["id"]: self.prior(kind, key, e["id"]) * self.personal.get(e["id"], 1.0) for e in self.library[kind]}
        pmax = max(list(weighted.values()) + [0.001])
        my_side = aim_side(aim, c)
        picks = []
        for e in self.library[kind]:
            if kind != 'wall':
                piece=get_piece(kind)
                route=piece.route(aim,dict(e,piece=piece.kind,cols=piece.cells))
                if route is None:continue
                penalty=PRIOR_WEIGHT*math.log(pmax/max(weighted[e['id']],.001))
                picks.append(Pick(e['id'],e['name'],tuple(e.get('tiles',())),round(route.distance+penalty,4),
                                  round(route.distance,4),round(weighted[e['id']],4),self.personal.get(e['id'],1.),
                                  {'route_mode':route.mode,'prior_penalty':round(penalty,3),'situation':key}))
                continue
            tiles = tuple(e["tiles"])
            s = shape_side(tiles, c)
            if s != 0 and my_side != 0 and s != my_side:
                continue        # never offer an edit on the other side of the piece from the crosshair
            penalty = PRIOR_WEIGHT * math.log(pmax / max(weighted[e["id"]], 0.001))
            options = [tiles, tuple(reversed(tiles))]
            costs = [approach(aim, t, c) + DRAG_WEIGHT * drag(t, c) + penalty for t in options]
            best = options[int(costs[1] < costs[0])]
            picks.append(Pick(e["id"], e["name"], best, round(min(costs), 4),
                              round(approach(aim, best, c) + drag(best, c), 4), round(weighted[e["id"]], 4),
                              self.personal.get(e["id"], 1.0),
                              {"approach": round(approach(aim, best, c), 3), "drag": round(drag(best, c), 3),
                               "prior_penalty": round(penalty, 3), "situation": key}))
        return sorted(picks, key=lambda p: p.cost)
