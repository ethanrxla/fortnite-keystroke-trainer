import unittest

from keystroke_lab import jev_keystrokes as jk

BOUND = {"f": {"floor"}, "t": {"wall"}, "q": {"ramp"}}
EVENT = {"id": "e1", "key": "g", "expected_action": "floor", "offset_ms": -20}


def answer(choice, probs, confidence):
    return {"type": "choice", "choice": choice, "probabilities": probs, "confidence": confidence}


class FakeClient:
    available = True

    def __init__(self, answers):
        self.answers, self.asked = answers, None

    def decide(self, state, questions):
        self.asked = (state, questions)
        return self.answers


class BuildTest(unittest.TestCase):
    def test_candidates_are_adjacent_bound_actions_plus_fallbacks(self):
        opts = jk.candidates(EVENT, BOUND)
        self.assertIn("floor", opts)            # F is next to G
        self.assertIn("wall", opts)             # T is next to G
        self.assertNotIn("ramp", opts)          # Q is not
        self.assertIn("none_deliberate", opts)
        self.assertIn("insufficient_evidence", opts)

    def test_two_atomic_questions_per_event_and_at_most_four_events(self):
        events = [dict(EVENT, id=f"e{i}") for i in range(6)]
        state, questions, _ = jk.build(events, BOUND, 3)
        self.assertEqual(len(questions), 8)
        self.assertEqual(state["schema"], "ktkey/1")
        self.assertEqual(questions["e0.slip"]["type"], "noul")


class InterpretTest(unittest.TestCase):
    def setUp(self):
        _, _, self.options = jk.build([EVENT], BOUND, 3)
        n = len(self.options["e1"])
        self.probs = {k: 0.0 for k in self.options["e1"]}

    def run_with(self, probs, confidence, slip=0.9, rev=3, current=3):
        answers = {"e1.intended": answer(max(probs, key=probs.get), probs, confidence),
                   "e1.slip": {"type": "noul", "noul": slip}}
        return jk.interpret(answers, [EVENT], self.options, rev, current)

    def test_confident_answer_is_live_with_intended_key(self):
        probs = dict(self.probs, floor=0.92, wall=0.05, none_deliberate=0.03)
        [r] = self.run_with(probs, 0.89)
        self.assertEqual((r["accepted"], r["intended"], r["intended_key"], r["slip"]), ("live", "floor", "f", True))

    def test_middling_answer_is_likely_only(self):
        probs = dict(self.probs, floor=0.6, wall=0.4)
        [r] = self.run_with(probs, 0.55)
        self.assertEqual(r["accepted"], "likely")

    def test_low_confidence_or_fallback_is_unclassified(self):
        probs = dict(self.probs, insufficient_evidence=0.95, floor=0.05)
        [r] = self.run_with(probs, 0.93)
        self.assertEqual(r["accepted"], "unclassified")

    def test_unknown_label_or_bad_sum_is_rejected(self):
        answers = {"e1.intended": answer("jump", {"jump": 1.0}, 1.0)}
        self.assertEqual(jk.interpret(answers, [EVENT], self.options, 3, 3)[0]["accepted"], "rejected")
        probs = dict(self.probs, floor=0.7, wall=0.7)
        self.assertEqual(self.run_with(probs, 0.9)[0]["accepted"], "rejected")

    def test_stale_profile_revision_drops_everything(self):
        probs = dict(self.probs, floor=1.0)
        self.assertEqual(self.run_with(probs, 1.0, rev=3, current=4), [])

    def test_ask_goes_through_the_client(self):
        probs = dict(self.probs, floor=1.0)
        client = FakeClient({"e1.intended": answer("floor", probs, 1.0), "e1.slip": {"noul": 0.2}})
        [r] = jk.ask(client, [EVENT], BOUND, 3)
        self.assertEqual(r["accepted"], "live")
        self.assertFalse(r["slip"])
        self.assertIn("e1", client.asked[0]["events"])

    def test_unavailable_client_makes_no_call(self):
        client = FakeClient({})
        client.available = False
        self.assertEqual(jk.ask(client, [EVENT], BOUND, 3), [])
        self.assertIsNone(client.asked)


if __name__ == "__main__":
    unittest.main()
