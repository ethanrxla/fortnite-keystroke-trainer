"""Find a native edit grid from its tiles rather than its lines (floors, cones and ramps; player 2026-10-21).

The line-lattice finders in edit_observation.py suit walls seen square on, but miss flat and sloped grids seen at a
steep angle (321 of 398 labelled floor, ramp and cone frames had no grid at all). Fortnite draws every edit tile as a
strongly saturated blue panel, separated from its neighbours by a rim and a gap, so here each tile is one region of
that blue, and the grid is the lattice the tiles around the crosshair form:

    found = find_tile_grid(image, aim)      # image: BGR at detector width; aim: crosshair (x, y) in that image
    if found: n, quad, tiles, gap = found   # n 2 (floor, cone) or 3 (ramp, wall); gap: the narrowest space between
                                            # two neighbouring tiles, as a fraction of a tile

quad corners follow the other finders: [bottom-left, bottom-right, top-right, top-left] of the grid as seen, so
cv2.getPerspectiveTransform([[0,0],[n,0],[n,n],[0,n]] -> quad) maps tile coordinates to the image. Tiles the player
has already selected turn grey and are not found; the lattice still fixes the grid from the blue ones. Score changes
with tools/eval_frames.py.

Status 2026-10-22: not wired into the guide yet. On the player-labelled frames it finds the right grid size often
(ramps 3 x 3, cones 2 x 2), but a 2 x 2 floor whose tiles carry faint markings splits into half-tiles that form a
3-wide lattice and would read as a ramp (3 of 86 floors). The space between real neighbouring tiles is at least 0.107
of a tile on every ramp found, split halves 0.03-0.09, but one floor sits at 0.118; more floor frames are needed
before a rule can be trusted.
"""
import math

import cv2
import numpy as np

HUE = (95, 118)          # OpenCV hue of the edit tile blue
SAT_MIN = 200
VAL_MIN = 90
MIN_AREA = 250.          # px at 640 wide
MAX_AREA_FRAC = 0.09     # of the image: anything bigger is sky or a wall face, not one tile
EDGES = True             # selected (grey) tiles cut out along their bright rims (2026-10-22: +4 ramps, +1 floor/cone, no new wrong)
RIM_TOPHAT, RIM_SAT, RIM_GROW = 25, 120, 3
STEP_TOL = 0.38          # a neighbour's centre is one tile step away, within this fraction of the step


def _tiles(image):
    """Candidate tiles: (corners, is_blue). By colour (unselected blue panels), or with EDGES by the bright rims that
    frame every tile, blue or selected grey."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    blue = (h >= HUE[0]) & (h <= HUE[1]) & (s > SAT_MIN) & (v > VAL_MIN)
    if not EDGES:
        return [(q, True) for q in _panels(image, blue)]
    # Rims: thin lines brighter than their surroundings and not strongly coloured. Cutting the edit grid's area along
    # them separates every tile, selected grey ones included (they merge by colour alone).
    top = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    rim = ((top > RIM_TOPHAT) & (s < RIM_SAT)).astype(np.uint8)
    rim = cv2.dilate(rim, np.ones((RIM_GROW, RIM_GROW), np.uint8)) > 0
    grey = (((h >= HUE[0]) & (h <= HUE[1]) & (s >= 55) & (s <= 170)) | (s < 55)) & (v >= 70) & (v <= 235)
    # Blue tiles as by colour (they already separate); the rims only add the selected grey ones.
    return [(q, True) for q in _panels(image, blue)] + [(q, False) for q in _panels(image, grey & ~blue & ~rim)]


def _panels(image, mask):
    mask = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    limit = MAX_AREA_FRAC * image.shape[0] * image.shape[1]
    out = []
    for i in range(1, n):
        if not MIN_AREA <= stats[i][4] <= limit:
            continue
        x, y, w, h = stats[i][:4]
        sub = (lab[y:y + h, x:x + w] == i).astype(np.uint8)
        cs, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull = cv2.convexHull(max(cs, key=cv2.contourArea)) + np.array([x, y])
        if stats[i][4] < 0.75 * cv2.contourArea(hull):
            continue                                   # ragged: not a panel
        quad = cv2.approxPolyDP(hull, 0.04 * cv2.arcLength(hull, True), True).reshape(-1, 2).astype(np.float32)
        if len(quad) != 4:
            continue
        out.append(_order(quad))
    return out


def _order(q):
    """Corners as [bottom-left, bottom-right, top-right, top-left] on screen (y grows downward): walk the convex quad
    clockwise on screen and start at the lower end of its lowest edge, so slanted tiles keep a consistent order."""
    c = q.mean(0)
    q = q[np.argsort(np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0]))]   # increasing angle with y down: clockwise on screen
    # The bottom edge: of the four edges, the one whose midpoint is lowest on screen.
    k = int(np.argmax([(q[i][1] + q[(i + 1) % 4][1]) for i in range(4)]))
    a, b = q[k], q[(k + 1) % 4]
    start = k if a[0] < b[0] else (k + 1) % 4                         # bottom-left = the left end of that edge
    q = np.roll(q, -start, axis=0)
    # Clockwise on screen from bottom-left runs up the left side; we want bottom-left, bottom-right, top-right, top-left.
    return np.array([q[0], q[3], q[2], q[1]], np.float32)


def find_tile_grid(image, aim, max_n=3):
    found = _tiles(image)
    tiles = [t for t, _ in found]
    blue = [b for _, b in found]
    if len(tiles) < 2 or not any(blue):
        return None
    centres = np.array([t.mean(0) for t in tiles])
    aim = np.asarray(aim, np.float32)
    inside = [i for i, t in enumerate(tiles) if cv2.pointPolygonTest(t, tuple(map(float, aim)), False) >= 0]
    if inside:
        seed = inside[0]
    else:                                              # nearest blue tile: a grey region alone proves nothing
        seed = min((i for i in range(len(tiles)) if blue[i]), key=lambda i: np.linalg.norm(centres[i] - aim))
    t0 = tiles[seed]
    size = math.sqrt(cv2.contourArea(t0))
    if not inside and np.linalg.norm(centres[seed] - aim) > 1.5 * size:
        return None
    # Lattice by breadth-first growth: each tile's own sides give the step to its neighbours, so perspective is fine.
    # Perspective draws nearer tiles bigger, so two neighbours' centres are the mean of their two sides apart.
    sides = [((t[1] - t[0] + t[2] - t[3]) / 2, (t[3] - t[0] + t[2] - t[1]) / 2) for t in tiles]   # (u, v) per tile
    pos = {seed: (0, 0)}
    queue = [seed]
    gaps = []
    while queue:
        k = queue.pop()
        i, j = pos[k]
        for di, dj, axis, sign in ((1, 0, 0, 1), (-1, 0, 0, -1), (0, 1, 1, 1), (0, -1, 1, -1)):
            for m in range(len(tiles)):
                if m in pos or not 0.25 < cv2.contourArea(tiles[m]) / cv2.contourArea(tiles[k]) < 4.0:
                    continue
                step = sign * (sides[k][axis] + sides[m][axis]) / 2
                if np.linalg.norm(centres[m] - centres[k] - step) <= STEP_TOL * np.linalg.norm(step):
                    pos[m] = (i + di, j + dj)
                    queue.append(m)
                    # Space between their facing edges: real neighbours have a gap and rims between them; the two halves
                    # of a tile split by its markings only a thin line.
                    side = (np.linalg.norm(sides[k][axis]) + np.linalg.norm(sides[m][axis])) / 2
                    gaps.append((np.linalg.norm(centres[m] - centres[k]) - side) / side)
    cells = set(pos.values())
    if len(cells) != len(pos) or len(pos) < 3 or not any(blue[k] for k in pos):
        return None                                    # two tiles on one cell, too few to fix a grid, or no blue tile
    i0, i1 = min(c[0] for c in cells), max(c[0] for c in cells)
    j0, j1 = min(c[1] for c in cells), max(c[1] for c in cells)
    n = max(i1 - i0, j1 - j0) + 1
    if n > max_n or n < 2:
        return None
    # Pin the grid's corners from the tiles that sit at them (or the nearest found tile, extrapolated by its sides).
    at = {c: tiles[k] for k, c in pos.items()}
    if n == 2 and (i1 - i0, j1 - j0) != (1, 1):
        return None                                    # a 2-wide strip: cannot tell 2 x 2 from part of a 3 x 3
    # A tile is its cell less the gap around it: pin each tile's corners inside its cell by half the typical gap, so
    # the grid's outline lands on the cell boundaries (a tile pinned to a whole cell stretches the fit ~5%).
    g = float(np.median(gaps))
    e = g / (2 * (1 + g))
    src, dst = [], []
    for (i, j), t in at.items():
        for corner, (di, dj) in enumerate(((e, e), (1 - e, e), (1 - e, 1 - e), (e, 1 - e))):
            src.append((i - i0 + di, j - j0 + dj))
            dst.append(t[corner])
    H, _ = cv2.findHomography(np.float32(src), np.float32(dst), cv2.RANSAC, 0.12 * size)
    if H is None:
        return None
    quad = cv2.perspectiveTransform(np.float32([[[0, 0], [n, 0], [n, n], [0, n]]]), H)[0]
    return n, quad, len(pos), min(gaps)
