import unittest

try:
    from keystroke_lab.edit_window import LEFT_CORNER, RIGHT_CORNER, choose_corner
except ImportError:          # the window needs opencv / mss; skip where they are not installed
    choose_corner = None


@unittest.skipIf(choose_corner is None, "edit window dependencies not installed")
class CornerSideTests(unittest.TestCase):
    def test_follows_where_the_crosshair_is(self):
        self.assertEqual(choose_corner(0.4), LEFT_CORNER)
        self.assertEqual(choose_corner(2.7), RIGHT_CORNER)

    def test_switches_when_you_aim_across_the_wall(self):
        side = choose_corner(0.5)
        side = choose_corner(2.5, side)
        self.assertEqual(side, RIGHT_CORNER)
        self.assertEqual(choose_corner(0.9, side), LEFT_CORNER)

    def test_dead_band_keeps_the_current_side_near_the_middle(self):
        self.assertEqual(choose_corner(1.5, LEFT_CORNER), LEFT_CORNER)
        self.assertEqual(choose_corner(1.4, RIGHT_CORNER), RIGHT_CORNER)
        self.assertEqual(choose_corner(1.6, LEFT_CORNER), LEFT_CORNER)

    def test_never_both_sides(self):
        for u in (0.0, 0.7, 1.35, 1.5, 1.65, 2.3, 2.99):
            self.assertIn(choose_corner(u), (LEFT_CORNER, RIGHT_CORNER))


if __name__ == "__main__":
    unittest.main()
