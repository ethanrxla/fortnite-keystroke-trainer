import unittest

from keystroke_lab.keyboard_overlay import KeyTracker, REP_IDLE_SECONDS

BINDS = {"edit": "g", "edit_confirm": "mouse_left", "reset": "mouse_right", "wall": "q"}


class KeyTrackerTests(unittest.TestCase):
    def test_in_order_presses_are_ok(self):
        t = KeyTracker(BINDS, ["edit", "edit_confirm"])
        self.assertEqual(t.press("g", 0.0)[0], "ok")
        self.assertEqual(t.press("mouse_left", 0.5)[0], "ok")

    def test_unbound_key_is_stray(self):
        t = KeyTracker(BINDS, ["edit"])
        self.assertEqual(t.press("x", 0.0)[0], "stray")

    def test_double_press_flagged(self):
        t = KeyTracker(BINDS)
        t.press("q", 0.0)
        self.assertEqual(t.press("q", 0.04)[0], "double")
        self.assertEqual(t.press("q", 0.5)[0], "ok")

    def test_bound_key_out_of_order(self):
        t = KeyTracker(BINDS, ["edit", "edit_confirm"])
        self.assertEqual(t.press("q", 0.0)[0], "order")

    def test_missed_steps_reported_after_idle(self):
        t = KeyTracker(BINDS, ["edit", "edit_confirm", "reset"])
        t.press("g", 0.0)
        self.assertEqual(t.missed(1.0), [])
        self.assertEqual(t.missed(REP_IDLE_SECONDS + 0.1), ["edit_confirm", "reset"])
        self.assertEqual(t.next_expected(), "g")

    def test_shift_variants_collapse(self):
        t = KeyTracker({"sprint": "shift"})
        self.assertEqual(t.press("shift_r", 0.0)[0], "ok")


if __name__ == "__main__":
    unittest.main()
