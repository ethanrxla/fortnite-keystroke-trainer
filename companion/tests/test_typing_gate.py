import types
import unittest

from keystroke_lab.input_gate import GameplayInputGate


def profile(*keys):
    return types.SimpleNamespace(bindings=[types.SimpleNamespace(action=f"a{i}", keys=[k]) for i, k in enumerate(keys)])


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


class TypingGateTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.gate = GameplayInputGate(profile("q", "e", "f", "w", "a", "s", "d"), clock=self.clock)

    def type(self, text, start, gap=0.12):
        out = []
        for i, k in enumerate(text):
            self.clock.t = start + i * gap
            out.append(self.gate.press("space" if k == " " else k, True, self.clock.t))
        return out

    def test_mouse_opened_chat_typing_closes_the_gate_and_revokes_the_burst(self):
        tokens = self.type("hi there", 100.0)
        self.assertIn(None, tokens)
        self.assertFalse(self.gate.active)
        self.assertEqual(self.gate.revoked_from, 100.0)

    def test_enter_after_unlatched_typing_is_a_send_not_chat_open(self):
        self.type("hi there", 100.0)
        self.gate.press("enter", True, self.clock.t + 0.1)
        self.gate.release("enter")
        self.assertFalse(self.gate.chat)
        self.clock.t += 0.2
        self.assertTrue(self.gate.active)

    def test_build_spam_on_bound_keys_keeps_recording(self):
        tokens = self.type("qefqefqefqef", 100.0, gap=0.15)
        self.assertNotIn(None, tokens)

    def test_typing_state_expires_after_idle(self):
        self.type("hello", 100.0)
        self.clock.t += 3.5
        self.assertTrue(self.gate.active)


if __name__ == "__main__":
    unittest.main()
