import tempfile
import pathlib
import unittest

from keystroke_lab import keystroke_live
from keystroke_lab.keystroke_live import KeystrokeLimits, KeystrokeLive

BOUND = {"f": {"floor"}, "q": {"wall"}, "t": {"trap"}}


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakeJev:
    available = True

    def __init__(self):
        self.calls = 0

    def decide(self, state, questions):
        self.calls += 1
        out = {}
        for q, spec in questions.items():
            if spec["type"] == "noul":
                out[q] = {"type": "noul", "noul": 0.9}
            else:
                opts = list(spec["criteria"])
                probs = {o: 0.0 for o in opts}
                probs["floor"] = 0.95
                probs["insufficient_evidence"] = 0.05
                out[q] = {"type": "choice", "choice": "floor", "probabilities": probs, "confidence": 0.93}
        return out


def step(action="floor", lat_ms=300, result="Missing"):
    return {"event": "step", "drill_id": "P2", "rep": 1, "step": 0, "action": action, "lat_ms": lat_ms,
            "result": result, "tempo": 0}


class LiveTest(unittest.TestCase):
    def setUp(self):
        self._grading = keystroke_live.STEP_GRADING
        keystroke_live.STEP_GRADING = True          # the logic under test; live grading stays off until validated
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.limits = KeystrokeLimits(pathlib.Path(self.tmp.name) / "day.json", clock=self.clock)
        self.out = []
        self.jev = FakeJev()
        self.live = KeystrokeLive(BOUND, 7, self.out.append, jev=self.jev, limits=self.limits, clock=self.clock)

    def tearDown(self):
        keystroke_live.STEP_GRADING = self._grading
        self.tmp.cleanup()

    def test_step_grading_is_off_by_default(self):
        self.assertFalse(self._grading)

    def test_clean_step_is_emitted_without_jev(self):
        self.live.press("f", 99.8)
        out = self.live.on_kt(step(result="Ok"), 100.0)
        self.assertEqual(out["outcome"], "clean")
        self.assertFalse(self.live.jev_due())

    def test_adjacent_wrong_key_goes_to_jev_once_and_is_cached(self):
        self.live.press("g", 99.8)
        self.assertEqual(self.live.on_kt(step(), 100.0)["outcome"], "wrong_key")
        self.assertFalse(self.live.jev_due())           # waits up to a second for company
        self.clock.t += 1.1
        self.assertTrue(self.live.jev_due())
        [r] = self.live.ask_jev()
        self.assertEqual((r["accepted"], r["intended_key"]), ("live", "f"))
        self.live.press("g", 109.8)
        self.live.on_kt(step(), 110.0)                  # same situation again: answered from the cache
        self.assertFalse(self.live.jev_due())
        self.assertEqual(self.jev.calls, 1)
        self.assertTrue(self.out[-1].get("cached"))

    def test_several_players_means_no_step_grading(self):
        self.live.on_kt({"event": "context", "players": "2"}, 99.0)
        self.live.press("f", 99.8)
        self.assertIsNone(self.live.on_kt(step(result="Ok"), 100.0))

    def test_revoked_typing_presses_are_not_graded(self):
        self.live.press("f", 99.8)
        self.live.revoke_since(99.5)
        self.assertEqual(self.live.on_kt(step(result="Missing"), 100.0)["outcome"], "missing")

    def test_profile_change_drops_pending_questions(self):
        self.live.press("g", 99.8)
        self.live.on_kt(step(), 100.0)
        self.live.set_profile(BOUND, 8)
        self.clock.t += 2
        self.assertEqual(self.live.ask_jev(), [])
        self.assertEqual(self.jev.calls, 0)


class LimitsTest(unittest.TestCase):
    def test_per_minute_and_per_day(self):
        with tempfile.TemporaryDirectory() as d:
            clock = Clock()
            lim = KeystrokeLimits(pathlib.Path(d) / "day.json", per_minute=2, per_day=3, clock=clock)
            self.assertTrue(lim.take())
            self.assertTrue(lim.take())
            self.assertFalse(lim.take())                # runaway guard
            clock.t += 61
            self.assertTrue(lim.take())
            clock.t += 61
            self.assertFalse(lim.take())                # daily cap, persisted
            again = KeystrokeLimits(pathlib.Path(d) / "day.json", per_minute=2, per_day=3, clock=clock)
            self.assertFalse(again.take())


if __name__ == "__main__":
    unittest.main()
