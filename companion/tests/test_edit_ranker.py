import unittest

from keystroke_lab.edit_ranker import Ranker, cols
from tests import test_edit_policy as verse_port


class RankerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = Ranker(personal={})

    def test_wall_matches_the_verse_ranking_everywhere(self):
        for ub in range(6):
            for vb in range(6):
                aim = ((ub + 0.5) / 2, (vb + 0.5) / 2)
                for side in range(3):
                    for far in (False, True):
                        # Exact ties keep library order here (as Verse's insertion sort does); the test port breaks
                        # them alphabetically, so compare cost by cost and the set of edits.
                        expected = verse_port.rank(aim, side, far)
                        got = self.r.rank("wall", aim, side, far)
                        self.assertEqual(len(got), len(expected))
                        for p, (c, _) in zip(got, expected):
                            self.assertAlmostEqual(p.cost, c, places=3, msg=(aim, side, far))
                        self.assertEqual({p.id for p in got}, {i for _, i in expected})

    def test_each_piece_has_suggestions_inside_its_grid(self):
        for kind in ("wall", "floor", "roof"):
            c = cols(kind)
            picks = self.r.rank(kind, (0.3, 0.3), 0, False)
            self.assertTrue(picks, kind)
            for p in picks:
                self.assertTrue(all(0 <= t < c * c for t in p.tiles))

    def test_floor_suggests_the_tile_under_the_crosshair(self):
        self.assertEqual(self.r.rank("floor", (0.4, 0.4), 1, False)[0].id, "floor_hole_near_left")
        self.assertEqual(self.r.rank("floor", (1.6, 1.6), 1, False)[0].id, "floor_hole_far_right")

    def test_never_the_other_side_of_the_piece(self):
        for p in self.r.rank("wall", (0.4, 1.5), 0, False):
            self.assertNotEqual(p.reasons and p.tiles and sum(t % 3 for t in p.tiles) / len(p.tiles) > 1.2, True, p.id)

    def test_off_piece_aim_gives_nothing(self):
        self.assertEqual(self.r.rank("wall", (3.2, 1.0)), [])
        self.assertEqual(self.r.rank("floor", (2.5, 1.0)), [])
        self.assertEqual(self.r.rank("unknown", (1.0, 1.0)), [])

    def test_personal_factor_moves_a_close_call_toward_what_the_player_does_well(self):
        aim, side, far = (2.4, 2.4), 2, False
        base = self.r.rank("wall", aim, side, far)
        second = base[1].id
        boosted = Ranker(personal={second: 1.3, base[0].id: 0.7}).rank("wall", aim, side, far)
        self.assertLess([p.id for p in boosted].index(second), 2)
        self.assertLess(boosted[[p.id for p in boosted].index(second)].cost, base[1].cost)


if __name__ == "__main__":
    unittest.main()


class IntentMapTests(unittest.TestCase):
    """The player's aim map (shared/edit-intent.json), 2026-10-10 screenshots: corners at corners, half wall (not quarter)
    on the top-middle tile, window in the centre (including its edges), door bottom-middle."""
    @classmethod
    def setUpClass(cls):
        from keystroke_lab.edit_ranker import IntentMap
        cls.m = IntentMap()

    def test_every_wall_tile(self):
        expect = {(0.5, 2.5): "corner_upper_left", (1.5, 2.5): "half_wall", (2.5, 2.5): "corner_upper_right",
                  (0.5, 1.3): "corner_lower_left", (1.5, 1.7): "window_center", (2.5, 1.3): "corner_lower_right",
                  (0.5, 0.5): "corner_lower_left", (1.5, 0.5): "door", (2.5, 0.5): "corner_lower_right"}
        for aim, edit in expect.items():
            self.assertEqual(self.m.lookup("wall", aim), edit, aim)

    def test_junctions_give_corners_and_centre_edges_give_the_window(self):
        self.assertEqual(self.m.lookup("wall", (1.9, 1.85)), "corner_upper_right")
        self.assertEqual(self.m.lookup("wall", (1.12, 1.15)), "half_arch_left")
        self.assertEqual(self.m.lookup("wall", (1.1, 1.5)), "window_center")      # left edge, mid height
        self.assertEqual(self.m.lookup("wall", (1.5, 1.9)), "window_center")      # top edge, centred

    def test_half_arch_at_the_lower_junctions_of_the_centre(self):
        # Player 2026-10-12: aiming at the centre tile's lower corner shows the half arch on that side.
        self.assertEqual(self.m.lookup("wall", (2.05, 1.1)), "half_arch_right")
        self.assertEqual(self.m.lookup("wall", (1.1, 0.9)), "half_arch_left")
        self.assertEqual(self.m.lookup("wall", (1.5, 1.2)), "window_center")
        self.assertEqual(self.m.lookup("wall", (1.5, 0.3)), "door")
        self.assertEqual(self.m.lookup("wall", (0.3, 1.3)), "corner_lower_left")
        self.assertEqual(self.m.lookup("wall", (2.7, 1.3)), "corner_lower_right")

    def test_side_tiles_give_the_triangle_on_the_crosshairs_half(self):
        # Player 2026-10-10 screenshot: crosshair above the middle of the right-middle tile -> upper right corner.
        self.assertEqual(self.m.lookup("wall", (2.3, 1.7)), "corner_upper_right")
        self.assertEqual(self.m.lookup("wall", (0.5, 1.8)), "corner_upper_left")
        self.assertEqual(self.m.lookup("wall", (2.3, 1.2)), "corner_lower_right")

    def test_never_quarter_wall_on_the_top_row(self):
        for u in (1.2, 1.5, 1.8):
            self.assertNotEqual(self.m.lookup("wall", (u, 2.6)), "quarter_wall")

    def test_floors_cones_and_bounds(self):
        self.assertEqual(self.m.lookup("floor", (0.3, 1.7)), "floor_hole_far_left")
        self.assertEqual(self.m.lookup("cone", (1.7, 0.3)), "roof_one_near_right")
        self.assertIsNone(self.m.lookup("wall", (3.2, 1.0)))
        self.assertIsNone(self.m.lookup("ramp", (0.5, 0.5)))

    def test_every_mapped_edit_exists_in_the_catalogue(self):
        from keystroke_lab.edit_dictionary import EditDictionary
        known = EditDictionary().all
        for n, names, _ in self.m.tables.values():
            for e in names:
                self.assertIn(e, known)
