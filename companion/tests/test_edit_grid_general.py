"""Any-angle grid detection: 2x2 floors / roofs seen in perspective and 3x3 walls, from synthetic renders.
Real floor frames are still needed to tune thresholds (VERIFY in game); these pin the geometry."""
import sys
import unittest
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.vision_packages'))
    import cv2
    import numpy as np
    from keystroke_lab import edit_observation as eo
except ImportError:
    cv2 = None


def render(n, quad, size=(720, 1280)):
    """A flat n x n edit grid (blue tiles, light gaps) warped onto `quad` (TL, TR, BR, BL screen corners)."""
    tile, gap = 200, 14
    side = n * tile
    flat = np.full((side, side, 3), (215, 215, 215), np.uint8)
    for r in range(n):
        for c in range(n):
            flat[r * tile + gap // 2:(r + 1) * tile - gap // 2, c * tile + gap // 2:(c + 1) * tile - gap // 2] = (205, 120, 40)
    H = cv2.getPerspectiveTransform(np.float32([[0, 0], [side, 0], [side, side], [0, side]]), np.float32(quad))
    out = np.full((size[0], size[1], 3), (45, 35, 30), np.uint8)
    warped = cv2.warpPerspective(flat, H, (size[1], size[0]))
    mask = cv2.warpPerspective(np.full((side, side), 255, np.uint8), H, (size[1], size[0])) > 0
    out[mask] = warped[mask]
    return out


@unittest.skipIf(cv2 is None, 'optional local vision dependencies missing')
class GeneralGridTests(unittest.TestCase):
    def test_floor_in_perspective_is_a_2x2_grid(self):
        # A floor below the camera: far edge narrow near the horizon, near edge wide at the bottom.
        img = render(2, [(470, 250), (810, 250), (1110, 600), (170, 600)])
        found = eo._general_grid(img, (640, 360))
        self.assertIsNotNone(found)
        count, H, quad, n = found
        self.assertEqual(n, 2)
        self.assertGreaterEqual(count, 4)

    def test_rotated_floor_seen_at_an_angle(self):
        img = render(2, [(560, 200), (1000, 290), (830, 610), (230, 480)])
        found = eo._general_grid(img, (640, 420))
        self.assertIsNotNone(found)
        self.assertEqual(found[3], 2)

    def test_wall_is_still_3x3(self):
        img = render(3, [(330, 70), (950, 100), (940, 590), (340, 610)])
        found = eo._general_grid(img, (640, 360))
        self.assertIsNotNone(found)
        self.assertEqual(found[3], 3)

    def test_crosshair_off_the_grid_finds_nothing(self):
        img = render(2, [(470, 250), (810, 250), (1110, 600), (170, 600)])
        self.assertIsNone(eo._general_grid(img, (60, 60)))

    def test_observer_reports_cells_and_aim_on_a_floor(self):
        img = render(2, [(470, 250), (810, 250), (1110, 600), (170, 600)])
        obs = eo.EditGridObserver()
        obs._aim_screen = (640.0, 360.0)
        count, H, quad, n = eo._general_grid(img, (640, 360))
        o = obs._from_projection(img, H, quad, 0., 1., count, .9, n)
        self.assertEqual(o.cells, 2)
        self.assertEqual(o.reason, 'native_edit_grid_observed')
        self.assertTrue(all(0 <= v < 2 for v in o.aim_uv))

    def test_lattice_one_tile_off_is_shifted_back_onto_the_wall(self):
        # Live 2026-10-10: a wooden pillar and a floor plank posed as the wall's left and bottom borders, so the
        # detected grid had the right spacing but sat one column left and one row low.
        img = render(3, [(400, 60), (1000, 60), (1000, 660), (400, 660)])
        img[:, 200:400] = (60, 100, 150)        # wood (BGR) left of the wall
        img[660:] = (60, 100, 150)              # wood floor below it
        unit = np.float32([[0, 0], [3, 0], [3, 3], [0, 3]])
        off = cv2.getPerspectiveTransform(unit, np.float32([[200, 260], [800, 260], [800, 860], [200, 860]]))
        H, quad, count = eo._lattice_shift(img, off, (650, 400))
        self.assertEqual(count, 9)
        np.testing.assert_allclose(quad, [[400, 60], [1000, 60], [1000, 660], [400, 660]], atol=1)

    def test_lattice_already_on_the_wall_stays(self):
        img = render(3, [(400, 60), (1000, 60), (1000, 660), (400, 660)])
        unit = np.float32([[0, 0], [3, 0], [3, 3], [0, 3]])
        on = cv2.getPerspectiveTransform(unit, np.float32([[400, 60], [1000, 60], [1000, 660], [400, 660]]))
        H, quad, count = eo._lattice_shift(img, on, (650, 400))
        np.testing.assert_allclose(quad, [[400, 60], [1000, 60], [1000, 660], [400, 660]], atol=1)


if __name__ == '__main__':
    unittest.main()
