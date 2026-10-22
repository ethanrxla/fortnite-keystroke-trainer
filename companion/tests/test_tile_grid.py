import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.vision_packages'))
import numpy as np  # noqa: E402

from keystroke_lab.pieces import cells, flat_name  # noqa: E402
from keystroke_lab.tile_grid import find_tile_grid  # noqa: E402


def tiles_image(n, tile=60, gap=12, origin=(200, 60)):
    """A drawn edit grid: n x n saturated-blue tiles with dark gaps, on a dull background (640 x 360)."""
    image = np.full((360, 640, 3), (60, 50, 40), np.uint8)
    x0, y0 = origin
    for r in range(n):
        for c in range(n):
            x, y = x0 + c * (tile + gap), y0 + r * (tile + gap)
            image[y:y + tile, x:x + tile] = (220, 120, 10)          # BGR: the edit tile blue
    return image


class TileGridTests(unittest.TestCase):
    def test_finds_a_3x3_and_its_corners(self):
        image = tiles_image(3)
        found = find_tile_grid(image, (200 + 72 + 30, 60 + 72 + 30))
        self.assertIsNotNone(found)
        n, quad, count, gap = found
        self.assertEqual((n, count), (3, 9))
        # The outline is the cell boundary: half a gap outside the outer tiles. Corners bottom-left .. top-left.
        self.assertTrue(np.allclose(quad[0], (200 - 6, 60 + 3 * 72 - 6), atol=4))
        self.assertTrue(np.allclose(quad[2], (200 + 3 * 72 - 6, 60 - 6), atol=4))
        self.assertGreater(gap, 0.12)

    def test_finds_a_2x2(self):
        found = find_tile_grid(tiles_image(2), (200 + 30, 60 + 30))
        self.assertEqual(found[0], 2)

    def test_nothing_without_tiles(self):
        self.assertIsNone(find_tile_grid(np.full((360, 640, 3), (60, 50, 40), np.uint8), (320, 180)))

    def test_crosshair_far_from_the_grid_finds_nothing(self):
        self.assertIsNone(find_tile_grid(tiles_image(3), (620, 340)))


class FloorOrConeNameTests(unittest.TestCase):
    # A 2x2 is shown as "floor / cone" (player 2026-10-22): edits are named by their tiles, the same on either piece.
    def test_names(self):
        self.assertEqual(flat_name([0]), "1 tile (near left)")
        self.assertEqual(flat_name([2, 3]), "2 tiles (far side)")
        self.assertEqual(flat_name([3, 0]), "2 tiles (diagonal)")
        self.assertEqual(flat_name([0, 1, 2]), "3 tiles (far right kept)")

    def test_grid_sizes(self):
        self.assertEqual([cells(p) for p in ("wall", "ramp", "floor", "cone")], [3, 3, 2, 2])


if __name__ == "__main__":
    unittest.main()
