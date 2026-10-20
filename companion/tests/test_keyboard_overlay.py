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
        self.assertEqual(t.press("x", 0.0)[0], "unmapped")

    def test_double_press_flagged(self):
        t = KeyTracker(BINDS)
        t.press("q", 0.0)
        self.assertEqual(t.press("q", 0.04)[0], "repeat")
        t.release("q")
        self.assertEqual(t.press("q", 0.5)[0], "ok")

    def test_bound_key_out_of_order(self):
        t = KeyTracker(BINDS, ["edit", "edit_confirm"])
        self.assertEqual(t.press("mouse_left", 0.0)[0], "order")

    def test_missed_steps_reported_after_idle(self):
        t = KeyTracker(BINDS, ["edit", "edit_confirm", "reset"])
        t.press("g", 0.0)
        self.assertEqual(t.missed(1.0), [])
        self.assertEqual(t.missed(REP_IDLE_SECONDS + 0.1), ["edit_confirm", "reset"])
        self.assertEqual(t.next_expected(), "g")

    def test_shift_variants_collapse(self):
        t = KeyTracker({"sprint": "shift"})
        self.assertEqual(t.press("shift_r", 0.0)[0], "ok")

    def test_mouse_and_repress(self):
        t = KeyTracker({"reload": "mouse_middle", "crouch": "mouse_x2", "wall": "f"})
        for key in ("mouse_middle", "mouse_x2", "f"):
            self.assertEqual(t.press(key, 0)[0], "ok")
        self.assertEqual(t.press("f", .02)[0], "repeat")
        t.release("f")
        self.assertEqual(t.press("f", .04)[0], "ok")

    def test_unverified_alternate_cannot_complete_drill(self):
        from keystroke_lab.bind_profiles import Binding, BindProfile, BindMap
        profile = BindProfile("player", 35, (
            Binding("wall", ("f",), verified=True),
            Binding("wall", ("q",), verified=False),
        ))
        t = KeyTracker(BindMap(profile), ["wall"])
        self.assertEqual(t.profile_revision, 35)
        self.assertIn("?", t.names["q"])
        t.press("q", 0)
        self.assertEqual(t.index, 0)
        t.press("f", .1)
        self.assertEqual(t.index, 1)


if __name__ == "__main__":
    unittest.main()


class ExplainTests(unittest.TestCase):
    def setUp(self):
        from keystroke_lab import keyboard_overlay as ko
        self.ko = ko
        self.t = ko.KeyTracker({"edit": "tab", "wall": "q", "floor": "f"})

    def test_caps_lock_beside_tab_is_called_out(self):
        self.assertNotIn("'tab'", self.ko.explain("unmapped", "caps_lock", self.t))
        self.assertIn("Unmapped", self.ko.explain("unmapped", "caps_lock", self.t))

    def test_far_stray_has_no_guess(self):
        text = self.ko.explain("stray", "m", self.t)
        self.assertIn("Unmapped", text)

    def test_slip_detected_when_neighbour_follows(self):
        text = self.ko.explain("ok", "tab", self.t, ("caps_lock", 10.0), 10.3)
        self.assertEqual(text, "")
        self.assertEqual(self.ko.explain("ok", "tab", self.t, ("caps_lock", 10.0), 12.0), "")


class WindowIdentityTests(unittest.TestCase):
    def test_browser_and_editor_cannot_be_game_window(self):
        from keystroke_lab.keyboard_overlay import is_fortnite_executable
        self.assertTrue(is_fortnite_executable(r"C:\Games\FortniteClient-Win64-Shipping.exe"))
        for path in (r"C:\Chrome\chrome.exe", "msedge.exe", "UnrealEditorFortnite-Win64-Shipping.exe", "Fortnite.exe"):
            self.assertFalse(is_fortnite_executable(path))
