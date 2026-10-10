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
