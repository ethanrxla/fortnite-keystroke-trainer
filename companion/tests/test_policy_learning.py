import json
import unittest
import uuid
from pathlib import Path

from keystroke_lab import policy_learning as pl
from keystroke_lab.edit_ranker import Ranker, situation_key
from keystroke_lab.store import Store
from tests.test_attempt_pipeline import record

ROOT = Path(__file__).resolve().parents[2]
WALL = json.loads((ROOT / "shared/edit-policy.json").read_text(encoding="utf-8"))


def sample(edit, aim=(2.6, 2.6), side=2, far=False, outcome="result_verified", followed=None):
    return {"piece": "wall", "aim": aim, "side": side, "far": far, "edit": edit, "outcome": outcome,
            "followed": followed, "suggested": None, "reviewed": True}


class BlendTests(unittest.TestCase):
    def test_no_data_keeps_jev_prior(self):
        out = pl.blend(WALL, [], "wall")
        key = next(iter(WALL["priors"]))
        for a, b in zip(out["priors"][key], WALL["priors"][key]):
            self.assertAlmostEqual(a, b, places=2)
        self.assertEqual(out["examples_used"], 0)

    def test_player_choices_move_the_prior_and_its_mirror(self):
        key = situation_key((2.6, 2.6), 2, False, 3)
        ids = WALL["edits"]
        j = ids.index("corner_upper_right")
        out = pl.blend(WALL, [sample("corner_upper_right")] * 60, "wall")
        self.assertGreater(out["priors"][key][j], WALL["priors"][key][j])
        mkey = pl.mirror_key(key, "wall")
        jm = ids.index("corner_upper_left")
        self.assertGreater(out["priors"][mkey][jm], WALL["priors"][mkey][jm])
        for row in out["priors"].values():
            self.assertAlmostEqual(sum(row), 1.0, places=2)
            self.assertGreaterEqual(min(row), WALL["prior_floor"] * 0.9)   # floor then renormalise, as the Jev builder does

    def test_only_completed_attempts_count(self):
        out = pl.blend(WALL, [sample("corner_upper_right", outcome="reset")] * 10, "wall")
        self.assertEqual(out["examples_used"], 0)


class EvaluateTests(unittest.TestCase):
    def test_metrics(self):
        r = Ranker(personal={})
        top = r.rank("wall", (1.5, 1.5), 1, False)[0].id
        samples = [sample(top, aim=(1.5, 1.5), side=1)] * 4 + [sample("corner_upper_right")] + \
                  [sample(top, aim=(1.5, 1.5), side=1, outcome="reset", followed=True),
                   sample(top, aim=(1.5, 1.5), side=1, followed=True)]
        m = pl.evaluate(samples, r, "wall")
        self.assertEqual(m["examples"], 6)
        self.assertGreaterEqual(m["top1"], 0.6)
        self.assertEqual(m["completion_when_followed"], 0.5)
        self.assertIsNotNone(m["ece"])

    def test_blend_wins_when_players_disagree_with_the_prior(self):
        # Players in this situation consistently make the edit the current policy ranks second.
        r = Ranker(personal={})
        aim, side = (2.2, 2.2), 2
        picks = r.rank("wall", aim, side, False)
        second = picks[1].id
        data = [sample(second, aim=aim, side=side)] * 40
        current = pl.evaluate(data, r, "wall")
        blended = pl.blend(WALL, data, "wall", alpha=5)
        scored = pl.evaluate(data, Ranker(personal={}, policies={"wall": blended}), "wall")
        self.assertGreater(scored["top1"], current["top1"])
        self.assertFalse(pl.better(scored, current))  # same-data fit cannot pass a held-out gate

    def test_too_few_examples_never_publish(self):
        self.assertFalse(pl.better({"examples": 3, "top1": 1, "top3": 1, "log_loss": 0}, {"top1": 0, "top3": 0}))


class ExamplesTests(unittest.TestCase):
    def test_labels_decide_what_counts(self):
        s = Store(":memory:")
        ctx = {"aim_uv": [1.5, 1.5], "side": 1, "far": False, "distance_cm": 300.0, "camera": [0, 0, 0],
               "body": [0, 0, 0], "inferred": True}
        a, b, c = (record(attempt_id=str(uuid.uuid4()), context=ctx) for _ in range(3))
        for x in (a, b, c):
            s.add_attempt(x)
        s.add_label(a["attempt_id"], "approved", result_confirmed=True)
        s.add_label(b["attempt_id"], "relabelled", "window_high", result_confirmed=True)
        self.assertEqual(sorted(e["edit"] for e in pl.examples(s)), ["window_center", "window_high"])
        self.assertEqual(len(pl.examples(s, include_auto=True)), 2)  # no verified result for c
        s.add_label(c["attempt_id"], "rejected")
        self.assertEqual(len(pl.examples(s, include_auto=True)), 2)


if __name__ == "__main__":
    unittest.main()
