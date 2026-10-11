"""Piece-specific edit topology. No capture, I/O, AI or input injection."""
from dataclasses import dataclass, field
from itertools import permutations
import math


@dataclass(frozen=True)
class EditRoute:
    distance: float
    points: tuple
    order: tuple
    mode: str = "drag"

    def legacy(self):
        return self.distance, self.points, self.order


@dataclass(frozen=True)
class EditDefinition:
    id: str
    piece: str
    tiles: tuple
    name: str
    result_shape: str = ""
    data: dict = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_dict(cls, value):
        return cls(value["id"], get_piece(value["piece"]).kind, tuple(value.get("tiles", ())),
                   value.get("name", value["id"]), value.get("result_shape", ""), dict(value))

    def to_dict(self):
        return dict(self.data, id=self.id, piece=self.piece, tiles=list(self.tiles), name=self.name,
                    result_shape=self.result_shape, cols=get_piece(self.piece).cells, rows=get_piece(self.piece).cells)


class BuildPiece:
    kind, cells, topology = "unknown", 2, "tiles"

    def screen_tiles(self, context, tiles):
        if context is None:return tuple(tiles)
        from .edit_geometry import tiles_to_grid
        return tiles_to_grid(context, tiles)

    def screen_point(self, context, point):
        if context is None:return tuple(point)
        from .edit_geometry import piece_to_grid
        return piece_to_grid(context, *point)

    def regions(self):
        n = self.cells
        return tuple((c/n, r/n, (c+1)/n, (r+1)/n) for r in range(n) for c in range(n))

    def matches(self, edit, tiles, context=None, gesture=()):
        return bool(tiles) and set(self.screen_tiles(context, edit.get("tiles", ()))) == set(tiles)

    def route(self, aim, edit, inset=.15):
        from .edit_advisor import safe_path
        tiles = tuple(edit.get("tiles", ()))
        if not tiles:return None
        route = safe_path(aim, tiles, cols=self.cells, inset=inset)
        if route:return EditRoute(*route)
        if self.cells == 2:
            choices = []
            for order in permutations(tiles):
                points = tuple((t % 2 + .5, t // 2 + .5) for t in order)
                length = math.dist(aim, points[0]) + sum(math.dist(a,b) for a,b in zip(points, points[1:]))
                choices.append(EditRoute(length, points, order, "taps"))
            return min(choices, key=lambda r: (r.distance, r.order))
        return None

    def display(self, edit, context):
        return dict(edit, tiles=list(self.screen_tiles(context, edit.get("tiles", ()))))


class WallPiece(BuildPiece):
    kind, cells = "wall", 3

    def screen_tiles(self, context, tiles):
        return tuple(tiles)


class FloorPiece(BuildPiece):
    kind = "floor"


class ConePiece(BuildPiece):
    kind = "cone"


class RampPiece(BuildPiece):
    kind, topology = "ramp", "gesture"

    def regions(self):return ()

    def matches(self, edit, tiles=(), context=None, gesture=()):
        return bool(gesture) and any(tuple(r) == tuple(gesture) for r in edit.get("gesture", {}).get("routes", ()))

    def display(self, edit, context):
        gesture = dict(edit.get("gesture") or {})
        gesture["nodes"] = {k: self.screen_point(context, (p[0]*2, p[1]*2))
                            for k,p in gesture.get("nodes", {}).items()}
        gesture["coordinate_space"] = "grid"
        return dict(edit, gesture=gesture)

    def route(self, aim, edit, inset=.15):
        g = edit.get("gesture") or {}
        scale = 1 if g.get("coordinate_space") == "grid" else self.cells
        nodes = {k: tuple(float(v)*scale for v in p) for k,p in g.get("nodes", {}).items()}
        edges = {tuple(e) for e in g.get("edges", ())}
        routes = []
        for order in g.get("routes", ()):
            if not order or any(n not in nodes for n in order) or any((a,b) not in edges for a,b in zip(order, order[1:])):continue
            points = tuple(nodes[n] for n in order)
            length = math.dist(aim, points[0]) + sum(math.dist(a,b) for a,b in zip(points, points[1:]))
            routes.append(EditRoute(length, points, tuple(order)))
        return min(routes, key=lambda r: (r.distance, r.order)) if routes else None

    def gesture_node(self, point, edit, tolerance=.18):
        nodes = (edit.get("gesture") or {}).get("nodes", {})
        if not nodes:return None
        scale = 1 if edit.get("gesture", {}).get("coordinate_space") == "grid" else 2
        name, distance = min(((k, math.dist(point, (p[0]*scale, p[1]*scale))) for k,p in nodes.items()), key=lambda x:x[1])
        return name if distance <= tolerance else None


PIECES = {p.kind: p for p in (WallPiece(), FloorPiece(), ConePiece(), RampPiece())}


def get_piece(kind):
    from .pieces import canonical
    name = canonical(kind)
    if name not in PIECES:raise ValueError(f"Unsupported build piece: {kind}")
    return PIECES[name]
