import unittest

from keystroke_lab import drills, grader, ktlog


class TempoRules(unittest.TestCase):
    def test_promote_hold_demote(self):
        self.assertEqual(grader.decide_tempo([0.96, 0.95, 1.0]), "promote")
        self.assertEqual(grader.decide_tempo([0.96, 0.9, 0.97]), "hold")
        self.assertEqual(grader.decide_tempo([0.9, 0.7, 0.79]), "demote")

    def test_spread_gate_blocks_promotion(self):
        # 60 APM: interval 1000 ms, gate 150 ms
        self.assertEqual(grader.decide_tempo([1, 1, 1], [100, 120, 200], 60), "hold")
        self.assertEqual(grader.decide_tempo([1, 1, 1], [100, 120, 140], 60), "promote")

    def test_step_tempo(self):
        self.assertEqual(grader.step_tempo(40, "promote"), 60)
        self.assertEqual(grader.step_tempo(220, "promote"), grader.FREE)
        self.assertEqual(grader.step_tempo(40, "demote"), 40)
        self.assertEqual(grader.step_tempo(grader.FREE, "demote"), 220)

    def test_windows(self):
        self.assertAlmostEqual(grader.companion_window(60), 0.25)
        self.assertAlmostEqual(grader.companion_window(300), 0.060)


class RepGrading(unittest.TestCase):
    keys = ["q", "f3", "f2"]
    watched = {"q", "f2", "f3", "f4"}

    def test_clean_rep(self):
        r = grader.grade_rep(self.keys, [(0.02, "q"), (1.05, "f3"), (1.9, "f2")], 0.0, 60, self.watched)
        self.assertTrue(r.clean, r)

    def test_wrong_late_missing_extra(self):
        presses = [(0.0, "q"), (1.0, "f2"), (1.1, "f4"), (2.4, "f2")]
        r = grader.grade_rep(self.keys, presses, 0.0, 60, self.watched)
        self.assertEqual([s.result for s in r.steps], ["ok", "wrong_key", "late"])
        self.assertEqual(r.extra_keys, [(1.1, "f4")])
        self.assertFalse(r.clean)
        r = grader.grade_rep(self.keys, [(0.0, "q")], 0.0, 60, self.watched)
        self.assertEqual([s.result for s in r.steps], ["ok", "missing", "missing"])

    def test_set(self):
        good = grader.grade_rep(self.keys, [(0.0, "q"), (1.0, "f3"), (2.0, "f2")], 0.0, 60, self.watched)
        bad = grader.grade_rep(self.keys, [(0.0, "q")], 0.0, 60, self.watched)
        s = grader.grade_set([good, good, good, bad])
        self.assertEqual(s.accuracy, 0.75)
        self.assertEqual(s.errors, {"missing": 2})


class Catalog(unittest.TestCase):
    def test_catalog_loads_and_keys_resolve(self):
        ladder, catalog = drills.load_catalog()
        self.assertEqual(ladder, grader.LADDER)
        keys = drills.expected_keys(catalog["wall_ramp_floor"], drills.DEFAULT_BINDS)
        self.assertEqual(keys, ["q", "f3", "f2"])


class KTLog(unittest.TestCase):
    def test_parse(self):
        line = "[2026.10.06-03.10.00:000][  0]LogVerse: : KT|set_end|wall_ramp_floor|tempo=80|rep=10|step=0|result=ok|t=123.5|clean=9|accuracy=0.9|decision=hold"
        r = ktlog.parse_line(line)
        self.assertEqual(r["event"], "set_end")
        self.assertEqual(r["tempo"], 80)
        self.assertEqual(r["accuracy"], 0.9)
        self.assertEqual(r["decision"], "hold")
        self.assertIsNone(ktlog.parse_line("LogVerse: : hello"))


if __name__ == "__main__":
    unittest.main()
