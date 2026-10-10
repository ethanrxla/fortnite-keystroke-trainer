"""Pose from the edit grid: synthetic scenes with a known camera, projected with the same pinhole model."""
import math
import sys
import unittest
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.vision_packages'))
    import cv2
    import numpy as np
    from keystroke_lab import edit_geometry as g
except ImportError:
    cv2 = None

W, H = 1920, 1080


def camera(pos, yaw_deg, pitch_deg):
    """World Z up. Returns (R world->camera with rows right, down, forward; position)."""
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    f = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    d = np.cross(f, r)
    return np.array([r, d, f]), np.array(pos, float)


def project(cam, points):
    R, c = cam
    K = g.camera_matrix(W, H)
    out = []
    for P in points:
        pc = R @ (np.array(P, float) - c)
        uvw = K @ pc
        out.append((uvw[0] / uvw[2], uvw[1] / uvw[2]))
    return out


def observe(cam, corners, cells):
    """What the observer reports: the quad and the crosshair (screen centre) in grid coordinates."""
    quad = project(cam, corners)
    Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [cells, 0], [cells, cells], [0, cells]]), np.float32(quad))
    gx, gy = cv2.perspectiveTransform(np.float32([[[W / 2, H / 2]]]), np.linalg.inv(Hm))[0, 0]
    return {'wall_quad': quad, 'aim_uv': (float(gx), float(cells - gy)), 'cells': cells}


@unittest.skipIf(cv2 is None, 'optional local vision dependencies missing')
class GeometryTests(unittest.TestCase):
    def test_wall_side_aim_and_distance(self):
        cam = camera((0, 150, 200), 0, 0)              # facing +x, standing left of the wall centre (+y is left)
        wall = [(500, 256, 384), (500, -256, 384), (500, -256, 0), (500, 256, 0)]
        ctx = g.piece_context(observe(cam, wall, 3), W, H)
        self.assertEqual(ctx.kind, 'wall')
        self.assertAlmostEqual(ctx.aim[0], (256 - 150) / 512 * 3, places=2)
        self.assertAlmostEqual(ctx.aim[1], 200 / 384 * 3, places=2)
        self.assertEqual(ctx.side, 0)
        self.assertTrue(ctx.far)                       # body ~275 cm from the aim point

    def test_wall_close_on_the_right(self):
        cam = camera((150, -200, 200), 0, 0)
        wall = [(500, 256, 384), (500, -256, 384), (500, -256, 0), (500, 256, 0)]
        ctx = g.piece_context(observe(cam, wall, 3), W, H)
        self.assertEqual(ctx.side, 2)
        self.assertFalse(ctx.far)

    def test_floor_below_is_a_floor_with_near_far_axes(self):
        cam = camera((0, 60, 300), 0, -35)
        floor = [(812, 256, 0), (812, -256, 0), (300, -256, 0), (300, 256, 0)]   # far-left, far-right, near-right, near-left
        ctx = g.piece_context(observe(cam, floor, 2), W, H)
        self.assertEqual(ctx.kind, 'floor')
        hit_x = 300 / math.tan(math.radians(35))       # where the crosshair meets the floor
        self.assertAlmostEqual(ctx.aim[1], (hit_x - 300) / 512 * 2, places=1)   # v measured from the near edge
        self.assertAlmostEqual(ctx.aim[0], (256 - 60) / 512 * 2, places=1)      # u from the left as seen
        self.assertLess(ctx.aim[1], 1.0)               # near half

    def test_floor_seen_from_the_side_keeps_tile_0_near_left(self):
        # Same floor, approached along -y (camera on the +y side looking right-to-left in world terms).
        cam = camera((556, 500, 300), -90, -40)
        floor = [(300, 256, 0), (812, 256, 0), (812, -256, 0), (300, -256, 0)]
        obs = observe(cam, floor, 2)
        ctx = g.piece_context(obs, W, H)
        self.assertEqual(ctx.kind, 'floor')
        self.assertLess(ctx.aim[1], 1.2)
        # back-project the near-left tile centre and check it is below and left of the far-right one on screen
        a = g.piece_to_screen(ctx, obs['wall_quad'], 0.5, 0.5)
        b = g.piece_to_screen(ctx, obs['wall_quad'], 1.5, 1.5)
        self.assertGreater(a[1], b[1])                 # near is lower on screen
        self.assertLess(a[0], b[0])                    # left is left

    def test_roof_overhead(self):
        cam = camera((0, 0, 180), 0, 40)
        roof = [(0, 256, 520), (512, 256, 520), (512, -256, 520), (0, -256, 520)]
        obs = observe(cam, roof, 2)
        ctx = g.piece_context(obs, W, H)
        self.assertEqual(ctx.kind, 'roof')

    def test_route_points_round_trip_on_a_wall(self):
        cam = camera((0, 0, 200), 0, 0)
        wall = [(500, 256, 384), (500, -256, 384), (500, -256, 0), (500, 256, 0)]
        obs = observe(cam, wall, 3)
        ctx = g.piece_context(obs, W, H)
        x, y = g.piece_to_screen(ctx, obs['wall_quad'], *ctx.aim)
        self.assertAlmostEqual(x, W / 2, delta=1)
        self.assertAlmostEqual(y, H / 2, delta=1)


if __name__ == '__main__':
    unittest.main()
