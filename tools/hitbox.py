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
