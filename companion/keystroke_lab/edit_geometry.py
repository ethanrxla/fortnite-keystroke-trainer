"""Where the player is relative to the piece they are editing, from the edit grid seen on screen.

    piece_context(observation, frame_width, frame_height) -> PieceContext | None

The observed grid quad (four screen corners) plus a pinhole camera model gives the camera pose relative to the piece
(cv2.solvePnP). From that pose:
  kind   wall (3x3 grid) | floor (2x2 grid below the camera) | roof (2x2 grid above the camera). Stairs also show a
         2x2 grid; telling a ramp from a floor needs the camera pitch, which the screen does not give, so a ramp is
         reported as a floor (stairs edits are unconfirmed and never suggested anyway).
  aim    crosshair on the piece in the ranker's frame (edit_ranker): walls u left->right, v bottom->top; floors and
         roofs u left->right, v near->far as the player sees them, so tile 0 is always near-left.
  side   which third of the piece the player's body is in (0 left, 1 centre, 2 right), as EditGuide.verse computes it.
  far    body more than 256 cm from the aim point (EditGuide.verse).

The body is estimated from the third-person camera: CAMERA_BOOM cm ahead of the camera along the horizontal view
direction and SHOULDER cm to its left. Both, and the field of view, are estimates (VERIFY against KT|context telemetry
in a UEFN session, which logs the true player position and view).
"""
from dataclasses import dataclass, asdict
import math

import cv2
import numpy as np

CELL = 512.0             # build grid cell, cm
WALL_HEIGHT = 384.0      # wall height, cm (one build level; VERIFY)
HFOV_DEG = 80.0          # Fortnite horizontal field of view at 16:9 (VERIFY)
CAMERA_BOOM = 230.0      # camera to character, cm along the horizontal view direction (VERIFY)
SHOULDER = 55.0          # camera sits right of the character by this much (VERIFY)
FAR_CM = 256.0


@dataclass(frozen=True)
class PieceContext:
    kind: str
    cells: int
    aim: tuple
    side: int
    far: bool
    distance_cm: float
    camera: tuple          # camera position in the piece frame, cm
    body: tuple            # estimated character position in the piece frame, cm
    across: tuple          # piece-frame unit vector for "u" (2x2 pieces), or (1, 0, 0) for walls
    away: tuple            # piece-frame unit vector for "v"
    source: str = 'screen_pose_estimate'

    def to_dict(self):
        return asdict(self)


def camera_matrix(width, height, hfov=HFOV_DEG):
    f = (width / 2.0) / math.tan(math.radians(hfov) / 2.0)
    return np.array([[f, 0, width / 2.0], [0, f, height / 2.0], [0, 0, 1]], np.float64)


def _object_points(cells):
    """Piece-frame corners for the quad order TL, TR, BR, BL (image). x = image-right edge direction,
    y = image-down edge direction, z = x cross y (into the screen for a face-on piece)."""
    width = CELL
    height = WALL_HEIGHT if cells == 3 else CELL
    return np.array([[0, 0, 0], [width, 0, 0], [width, height, 0], [0, height, 0]], np.float64), width, height


def solve_pose(quad, cells, width, height):
    """(R, t) mapping piece-frame points to camera coordinates, or None."""
    obj, _, _ = _object_points(cells)
    img = np.asarray(quad, np.float64).reshape(4, 2)
    K = camera_matrix(width, height)
    best = None
    # IPPE is exact for most views but returned a mirrored pose for some steep floors; keep whichever solver
    # reprojects the four corners best.
    for flag in (cv2.SOLVEPNP_IPPE, cv2.SOLVEPNP_ITERATIVE):
        ok, rvec, tvec = cv2.solvePnP(obj, img, K, None, flags=flag)
        if not ok:
            continue
        error = float(np.abs(cv2.projectPoints(obj, rvec, tvec, K, None)[0].reshape(4, 2) - img).max())
        if best is None or error < best[0]:
            best = (error, rvec, tvec)
    if best is None or best[0] > 0.05 * max(width, height):
        return None
    R, _ = cv2.Rodrigues(best[1])
    return R, best[2].reshape(3)


def _body(camera, forward, right, up):
    """Character position from the camera: ahead along the horizontal view, and left of the camera."""
    flat = forward - up * float(forward @ up)
    norm = np.linalg.norm(flat)
    flat = flat / norm if norm > 1e-6 else flat
    side = right - up * float(right @ up)
    norm = np.linalg.norm(side)
    side = side / norm if norm > 1e-6 else side
    return camera + flat * CAMERA_BOOM - side * SHOULDER


def piece_context(observation, width, height):
    obs = observation if isinstance(observation, dict) else observation.to_dict()
    quad, aim, cells = obs.get('wall_quad'), obs.get('aim_uv'), obs.get('cells', 3)
    if not quad or len(quad) != 4 or not aim or len(aim) != 2:
        return None
    pose = solve_pose(quad, cells, width, height)
    if pose is None:
        return None
    R, t = pose
    camera = -R.T @ t                                  # camera position in the piece frame
    forward, right, down = R.T[:, 2], R.T[:, 0], R.T[:, 1]
    _, w_cm, h_cm = _object_points(cells)
    # Grid coordinates of the crosshair back in the piece frame: aim is (u, v) with v measured up from the image bottom.
    gx, gy = aim[0], cells - aim[1]
    hit = np.array([gx / cells * w_cm, gy / cells * h_cm, 0.0])
    if cells == 3:
        # Wall: the piece frame is already the wall's; world up is -y (image up along the wall).
        up = np.array([0.0, -1.0, 0.0])
        body = _body(camera, forward, right, up)
        pu = body[0] / w_cm * 3.0
        side = 0 if pu < 1.0 else (1 if pu < 2.0 else 2)
        distance = float(np.linalg.norm((hit - body)[[0, 2]]))
        return PieceContext('wall', 3, (float(aim[0]), float(aim[1])), side, distance > FAR_CM, round(distance, 1),
                            tuple(float(v) for v in camera), tuple(float(v) for v in body), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0))
    # 2x2 piece: horizontal plane, normal = piece z. World up is whichever normal points to the top of the screen
    # (camera roll is zero, so world up always has a component toward image-up while |pitch| < 90).
    normal = np.array([0.0, 0.0, 1.0])
    up = normal if (R @ normal)[1] < 0 else -normal
    centre = np.array([w_cm / 2.0, h_cm / 2.0, 0.0])
    height_above = float((camera - centre) @ up)
    kind = 'floor' if height_above > 0 else 'roof'
    body = _body(camera, forward, right, up)
    look = forward - up * float(forward @ up)
    axes = [np.array(a, float) for a in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]
    away = max(axes, key=lambda a: float(a @ look))
    # "Across" is the in-plane axis perpendicular to away that points to the player's right.
    across = max((a for a in axes if abs(float(a @ away)) < .5), key=lambda a: float(a @ right))
    rel = hit - centre
    u = (float(rel @ across) / w_cm + 0.5) * 2.0
    v = (float(rel @ away) / h_cm + 0.5) * 2.0
    pu = (float((body - centre) @ across) / w_cm + 0.5) * 2.0
    side = 0 if pu < 0.8 else (1 if pu < 1.2 else 2)
    flat = (hit - body) - up * float((hit - body) @ up)
    distance = float(np.linalg.norm(flat))
    u, v = min(max(u, 0.0), 1.999), min(max(v, 0.0), 1.999)
    return PieceContext(kind, 2, (u, v), side, distance > FAR_CM, round(distance, 1), tuple(float(x) for x in camera),
                        tuple(float(x) for x in body), tuple(float(x) for x in across), tuple(float(x) for x in away))


def piece_to_screen(context, quad, u, v):
    """Screen point for a ranker coordinate (u, v) on the piece (inverse of the aim mapping), for drawing edit lines."""
    cells = context.cells
    if cells == 3:
        gx, gy = u, 3 - v
    else:
        _, w_cm, h_cm = _object_points(2)
        centre = np.array([w_cm / 2.0, h_cm / 2.0, 0.0])
        p = centre + np.array(context.across) * ((u / 2.0 - 0.5) * w_cm) + np.array(context.away) * ((v / 2.0 - 0.5) * h_cm)
        gx, gy = p[0] / w_cm * 2.0, p[1] / h_cm * 2.0
    unit = np.array([[0, 0], [cells, 0], [cells, cells], [0, cells]], np.float32)
    H = cv2.getPerspectiveTransform(unit, np.asarray(quad, np.float32).reshape(4, 2))
    x, y = cv2.perspectiveTransform(np.array([[[gx, gy]]], np.float32), H)[0, 0]
    return float(x), float(y)
