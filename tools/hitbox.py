"""Shootable buttons: cover a plate with target dummies, from the dummy's real collision.

The hit test of a target dummy (Device_TargetDummy, mesh SM_Target_Char11) is one convex hull, a kite: 71 cm wide at
the shoulders, 58 at the feet, narrowing to an 8 cm point at the head (BodySetup_1 of the mesh, read 2026-10-12). One
dummy behind a square plate leaves the upper corners dead, and earlier sizing guessed the in-play size from a
screenshot and put the hit box low on the plate (player 2026-10-12: "i see them mainly on the bottom of the plates";
in play the hull sits exactly where the editor shows it).

So a plate gets a grid of dummies. Each one is scaled so the rectangle that lies wholly inside its hull fills one
cell; the hull's extra parts (the head point, and 11 / 5.5 cm of shoulder on either side) are turned towards the
plate's middle: dummies in the upper half are rolled upside down, and each dummy is mirrored (turned round) so its
wider shoulder points inward. The outer cells are inset by the small outward shoulder, so nothing shows past the edge.

    from hitbox import place_grid
    paths = place_grid(builder, label, centre_xyz, face_w, face_h, facing_yaw, depth_point_xy, targets=[(path, fn)])
"""
import json
import math

import build_map as bm

# Actor-local collision of an upright dummy (roll 0): TargetMesh sits 38 cm above the actor, hull from the mesh asset.
HULL = [(-32.8, -40.7), (25.8, -40.7), (32.8, 29.0), (20.5, 84.0), (2.3, 117.7), (-5.5, 117.7), (-38.3, 66.5)]
# The largest axis-aligned rectangle inside it (y across, z up).
RECT_Y = (-32.8, 21.8)
RECT_Z = (-40.7, 78.0)
SPILL_SMALL = RECT_Y[0] - (-38.3)          # 5.5: hull beyond the rectangle on one side
CELL_MAX = 140.0                           # largest cell edge; smaller cells keep the shoulder spill small


def _variants(yaw):
    """(yaw, roll, su, sv): world u = su * local y, world v = sv * local z, u along the base yaw's local +y."""
    return [(yaw, 0.0, 1, 1), ((yaw + 180.0) % 360, 0.0, -1, 1), (yaw, 180.0, -1, -1), ((yaw + 180.0) % 360, 180.0, 1, -1)]


def plan_grid(face_w, face_h, cell_max=CELL_MAX):
    cols = max(1, math.ceil(face_w / cell_max))
    rows = max(1, math.ceil(face_h / cell_max))
    # One row would point every head the same way, out past one edge: a 2.6 m sign hanging in the air showed the
    # inverted dummies' heads below it (player 2026-10-12). Two rows point both halves inward. Only a face under
    # 1.2 m keeps one row (the range tiles, whose point goes down into the low wall in front of them).
    if rows == 1 and face_h >= 120.0:
        rows = 2
    rect_w = RECT_Y[1] - RECT_Y[0]
    # Outer cells give up the small shoulder at the face edge: cell_w * (cols + 2 * spill/rect_w) = face_w.
    cell_w = face_w / (cols + 2 * SPILL_SMALL / rect_w)
    cell_h = face_h / rows
    inset = (face_w - cols * cell_w) / 2
    cells = []
    for i in range(cols):
        for j in range(rows):
            u = -face_w / 2 + inset + (i + 0.5) * cell_w
            v = -face_h / 2 + (j + 0.5) * cell_h
            cells.append((u, v, cell_w, cell_h))
    return cells


def place_grid(b, label, centre, face_w, face_h, yaw, depth_xy, targets, cell_max=CELL_MAX):
    """Dummies covering a face of face_w x face_h centred at `centre` (x, y, z), standing at depth_xy (the old
    dummy's x, y), base facing `yaw`. `targets` are (device path, function) each dummy's On Hit calls.
    Returns the new dummy paths; the first keeps `label`, the rest get `label`_1, _2..."""
    m = b.m
    th = math.radians(yaw)
    ux, uy = -math.sin(th), math.cos(th)            # world direction of local +y at the base yaw
    cx, cy, cz = centre
    # Project the depth point onto the face: keep the old dummy's distance behind the plate.
    dx, dy = depth_xy
    nx, ny = math.cos(th), math.sin(th)             # facing direction
    depth = (dx - cx) * nx + (dy - cy) * ny
    rect_w = RECT_Y[1] - RECT_Y[0]
    rect_h = RECT_Z[1] - RECT_Z[0]
    yc, zc = (RECT_Y[0] + RECT_Y[1]) / 2, (RECT_Z[0] + RECT_Z[1]) / 2
    paths = []
    for k, (u, v, w, h) in enumerate(plan_grid(face_w, face_h, cell_max)):
        sy, sz = w / rect_w * 1.01, h / rect_h * 1.01
        best = None
        for vyaw, roll, su, sv in _variants(yaw):
            # Head point inward: upper cells need the hull's tip pointing down (sv = -1), lower ones up.
            # A single row counts as upper: its point goes down, never above the plate (the range tiles sit under a
            # low wall's top edge).
            if (v > -1e-6 and sv > 0) or (v < -1e-6 and sv < 0):
                continue
            # Wider shoulder (local +y side, 11 cm) inward: towards -u for cells right of centre.
            big_side = su                      # world u sign of the 11 cm shoulder
            score = -big_side * u
            if best is None or score > best[0]:
                best = (score, vyaw, roll, su, sv)
        _, vyaw, roll, su, sv = best
        # Pivot so the rectangle's centre lands on the cell centre.
        pu = u - su * yc * sy
        pv = v - sv * zc * sz
        px = cx + nx * depth + ux * pu
        py = cy + ny * depth + uy * pu
        pz = cz + pv
        name = label if k == 0 else f"{label}_{k}"
        d = b.device(bm.DUMMY, name, px, py, pz)
        xf = bm.xform(px, py, pz, 0.15, sy, sz, yaw=vyaw)
        xf["rotation"]["roll"] = roll
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": d}, xform=xf)
        b.props(d, {"infiniteHealth": True})
        try:
            b.props(d, {"showHealthBar": False})
        except RuntimeError:
            pass
        for path, fn in targets:
            b.bind(d, "On Hit", path, fn)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": d})
        paths.append(d)
    # The links are listed on the target device; save it too, or they can be lost when UEFN closes (2026-10-20: the
    # Operation and 1v1 sign targets and the range tiles came back from a restart unwired).
    for path, _fn in targets:
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    return paths


# What a shot actually collides with (2026-10-25, trace_world across an upright, unscaled dummy at yaw 0): the figure,
# not the hull above. Its one solid part is the chest, local y -20..20 and z 80..150 above the actor, with a 5 cm gap
# at y -15 (z 100..120) that the dummy turned round (yaw + 180, mirrored in y) fills; the head rises 30 cm above it. A
# tile covered by squashed hull cells came out patchy, with its top third bare (player 2026-10-25: "when we shoot, the
# button isnt activated").
CHEST_Y = 40.0
CHEST_Z = (80.0, 150.0)
HEAD_ABOVE = 30.0


def place_tile_pairs(b, label, centre_xy, width, bottom, top, yaw, depth_xy, targets, rows=2):
    """Cover a tile (`width` across, centred at centre_xy, `bottom`..`top` in z) with rows of dummy pairs, each pair
    one dummy and the same dummy turned round, stretched so the chest fills the tile's width and its row, standing at
    depth_xy's distance in front of the tile. The top row's head ends HEAD_ABOVE * z scale above `top`. yaw: the
    facing that puts the tile's width along the dummy's local y (shots travel along its local x)."""
    m = b.m
    sy = width / CHEST_Y
    row_h = (top - bottom) / rows
    sz = row_h / (CHEST_Z[1] - CHEST_Z[0])
    cx, cy = centre_xy
    dx, dy = depth_xy
    th = math.radians(yaw)
    nx, ny = math.cos(th), math.sin(th)
    depth = (dx - cx) * nx + (dy - cy) * ny
    x, y = cx + nx * depth, cy + ny * depth
    paths = []
    k = 0
    for r in range(rows):
        base_z = bottom + r * row_h - CHEST_Z[0] * sz
        for turn in (0.0, 180.0):
            name = label if k == 0 else f"{label}_{k}"
            k += 1
            d = b.device(bm.DUMMY, name, x, y, base_z)
            xf = bm.xform(x, y, base_z, 0.15, sy, sz, yaw=(yaw + turn) % 360)
            m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": d}, xform=xf)
            b.props(d, {"infiniteHealth": True})
            try:
                b.props(d, {"showHealthBar": False})
            except RuntimeError:
                pass
            for path, fn in targets:
                b.bind(d, "On Hit", path, fn)
            m.tool(bm.SCENE, "save_actor", actor={"refPath": d})
            paths.append(d)
    for path, _fn in targets:
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    return paths


def on_hit_targets(m, dummy_path, candidates):
    """(target path, function) for every On Hit binding of an existing dummy. ListEventBindings lists a device's
    incoming links, so the candidate targets are asked which of theirs come from this dummy."""
    out = []
    for target in candidates:
        for link in m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": target}) or []:
            if link["sourceDevicePath"]["refPath"] == dummy_path and link["sourceEvent"] == "On Hit":
                out.append((link["targetDevicePath"]["refPath"], link["targetFunction"]))
    return out


HIDDEN_PARTS = ("TargetMesh", "SM_Target_Base", "SM_Target_StandShort", "HeightExtender")


def hide(m, dummy_path):
    """Stop drawing a target dummy (its figure, base, stand and extender) while it keeps its collision, so a hit area
    can reach past the visible plate without white mannequins showing (player 2026-10-20: "the size of the tile needs
    to be unmodified, only the hitbox should increase"). VERIFY in game that a hidden dummy still takes hits."""
    for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": dummy_path}) or []:
        if c["refPath"].rsplit(".", 1)[-1] in HIDDEN_PARTS:
            m.tool(bm.OBJ, "set_properties", instance={"refPath": c["refPath"]}, values=json.dumps({"bHiddenInGame": True}))
    m.tool(bm.SCENE, "save_actor", actor={"refPath": dummy_path})
