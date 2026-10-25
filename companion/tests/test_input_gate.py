import unittest
from keystroke_lab.input_gate import GameplayInputGate


class GameplayInputGateTests(unittest.TestCase):
    def test_escape_pauses_until_closed_and_drops_queued_inputs(self):
        g = GameplayInputGate()
        token = g.press('f', True)
        self.assertTrue(g.accepts(token))
        self.assertIsNone(g.press('esc', True))
        self.assertFalse(g.accepts(token))
        self.assertIsNone(g.press('a', True))
        g.press('esc', True)  # held repeat must not reopen recording
        self.assertFalse(g.active)
        g.release('esc')
        g.press('esc', True)
        self.assertIsNotNone(g.press('f', True))

    def test_chat_text_and_send_are_not_recorded(self):
        g = GameplayInputGate()
        self.assertIsNone(g.press('enter', True))
        for key in ('f', 'mouse_middle', 'mouse_x2', 'wheel_down'):
            self.assertIsNone(g.press(key, True))
        g.release('enter')
        self.assertIsNone(g.press('enter', True))
        self.assertIsNotNone(g.press('f', True))

    def test_escape_cancels_chat_without_opening_menu(self):
        g = GameplayInputGate()
        g.press('enter', True)
        g.press('esc', True)
        self.assertTrue(g.active)
        self.assertFalse(g.menu)

    def test_focus_loss_invalidates_queue_and_windows_is_excluded(self):
        g = GameplayInputGate()
        token = g.press('f', True)
        self.assertIsNone(g.press('cmd', True))
        self.assertFalse(g.accepts(token))
        self.assertIsNone(g.press('a', False))
        self.assertIsNotNone(g.press('f', True))
        self.assertFalse(g.accepts(token))

    def test_stuck_menu_latch_releases_after_gameplay_presses(self):
        clock = [0.0]
        g = GameplayInputGate(clock=lambda: clock[0])
        g.press('esc', True, now=0.0)          # menu "opened", then closed with the mouse: the latch sticks
        g.release('esc')
        self.assertIsNone(g.press('f', True, now=1.0))
        t = GameplayInputGate.STALE_S + 1.0
        for n in range(GameplayInputGate.STALE_PRESSES):
            self.assertIsNone(g.press(('f', 'q', 'mouse_x2', 'space')[n % 4], True, now=t + n * 0.7))
        clock[0] = t + 10.0
        self.assertIsNotNone(g.press('f', True, now=t + 10.0))

    def test_alt_tab_does_not_clear_open_menu(self):
        g = GameplayInputGate()
        g.press('esc', True)
        g.focus(False)
        self.assertIsNone(g.press('f', True))

    def test_chat_survives_focus_loss(self):
        g = GameplayInputGate()
        g.press('enter', True)
        g.release('enter')
        g.focus(False)
        for key in ('f', 'g', 'mouse_middle'):
            self.assertIsNone(g.press(key, True))
        g.press('enter', True)
        self.assertIsNotNone(g.press('f', True))

    def test_alternate_chat_bind_and_profile_switch_invalidate_events(self):
        from keystroke_lab.bind_profiles import Binding, BindProfile
        p = BindProfile('p', 1, (Binding('chat', ('y',), 'ui', True),))
        g = GameplayInputGate(p)
        token = g.press('f', True)
        self.assertIsNone(g.press('y', True))
        self.assertFalse(g.accepts(token))
        self.assertIsNone(g.press('t', True))
        g.release('y')
        g.press('y', True)
        token = g.token(True)
        g.configure(p)
        self.assertFalse(g.accepts(token))
