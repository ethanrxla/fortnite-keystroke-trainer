import unittest

from keystroke_lab.keystroke_math import (PressLabeler, StepMatcher, TypingDetector, fix_next, key_distance,
                                          step_window, summary)

BINDS = {"wall": {"q"}, "floor": {"f"}, "ramp": {"e"}, "edit": {"g"}}


def step(ts, action, lat_ms=200, result="Ok", tempo=0, n=0):
    return {"ts": ts, "action": action, "lat_ms": lat_ms, "result": result, "tempo": tempo, "drill_id": "P2",
            "rep": 1, "step": n}


class PressLabelerTest(unittest.TestCase):
    def setUp(self):
        self.p = PressLabeler({"q": {"wall"}, "f": {"floor"}, "alt_l": set()}, known={"q", "f", "alt_l"})

    def test_bound_unbound_and_double(self):
        self.assertEqual(self.p.press("q", 1.0), "ok")
        self.p.release("q", 1.01)
        self.assertEqual(self.p.press("q", 1.05), "double")
        self.assertEqual(self.p.press("h", 2.0), "unmapped")

    def test_held_key_repeats_are_not_presses(self):
        self.p.press("f", 1.0)
        self.assertEqual(self.p.press("f", 1.03), "repeat")

    def test_caps_lock_unbound_is_a_modifier_slip(self):
        self.assertEqual(self.p.press("caps_lock", 1.0), "modifier")

    def test_lone_fast_alt_tap_is_a_modifier_slip_but_alt_with_another_key_is_not(self):
        self.p.press("alt_l", 1.0)
        self.assertEqual(self.p.release("alt_l", 1.1), "modifier")
        self.p.press("alt_l", 2.0)
        self.p.press("q", 2.05)
        self.assertIsNone(self.p.release("alt_l", 2.1))


class StepMatcherTest(unittest.TestCase):
    def test_window_from_latency(self):
        self.assertEqual(step_window(step(10.0, "wall", lat_ms=400)), (9.6, 10.0))

    def test_clean_step(self):
        m = StepMatcher(BINDS)
        out = m.match(step(10.0, "wall"), [(9.85, "q")])
        self.assertEqual(out["outcome"], "clean")
        self.assertEqual(out["pressed"], "q")

    def test_wrong_adjacent_key_then_correction_is_a_slip(self):
        m = StepMatcher(BINDS)
        out = m.match(step(10.0, "floor", lat_ms=500), [(9.55, "g"), (9.70, "f")])
        self.assertEqual(out["outcome"], "slip")
        self.assertEqual((out["wrong"], out["intended"]), ("g", "f"))

    def test_wrong_adjacent_key_without_correction_is_ambiguous_for_jev(self):
        m = StepMatcher(BINDS)
        out = m.match(step(10.0, "floor", lat_ms=500, result="Missing"), [(9.6, "d")])
        self.assertEqual(out["outcome"], "wrong_key")
        self.assertTrue(out["ambiguous"])

    def test_far_drill_key_is_a_wrong_key_but_not_ambiguous(self):
        out = StepMatcher(BINDS).match(step(10.0, "floor", lat_ms=500, result="missing"), [(9.6, "q")])
        self.assertEqual(out["outcome"], "wrong_key")
        self.assertFalse(out["ambiguous"])

    def test_far_unbound_key_and_keys_outside_the_drill_are_ignored(self):
        m = StepMatcher(dict(BINDS, forward={"w"}), {"P2": {"floor", "wall"}})
        out = m.match(step(10.0, "floor", lat_ms=500, result="missing"), [(9.6, "p"), (9.62, "w")])
        self.assertEqual(out["outcome"], "missing")

    def test_one_press_completes_one_step(self):
        m = StepMatcher(BINDS)
        self.assertEqual(m.match(step(10.0, "wall", tempo=0), [(9.85, "q")])["outcome"], "clean")
        self.assertEqual(m.match(step(10.3, "wall", tempo=0), [(9.85, "q")])["outcome"], "missing")

    def test_unchecked_step_at_tempo_uses_one_click_interval(self):
        self.assertEqual(step_window({"ts": 10.0, "tempo": 60}, prev_end=5.0), (9.0, 10.0))

    def test_missing(self):
        out = StepMatcher(BINDS).match(step(10.0, "wall", result="Missing"), [])
        self.assertEqual(out["outcome"], "missing")

    def test_unverified_action_is_never_graded(self):
        out = StepMatcher(BINDS).match(step(10.0, "jump"), [(9.9, "space")])
        self.assertEqual(out["outcome"], "ungraded")

    def test_log_delay_is_learned_and_drift_flagged(self):
        m = StepMatcher(BINDS)
        t = 100.0
        for i in range(12):                 # log lines arrive 300 ms after the press, steadily
            m.match(step(t + 0.3 + 0.2, "wall", lat_ms=200, tempo=60), [(t + 0.0 + (0.01 if i % 2 else 0), "q")])
            t += 2.0
        self.assertAlmostEqual(m.delay, 0.3, delta=0.02)
        out = m.match(step(t + 0.5, "wall", lat_ms=200, tempo=60), [(t + 0.2, "q")])
        self.assertTrue(out.get("drift"))

    def test_tempo_timing(self):
        m = StepMatcher(BINDS)
        self.assertEqual(m._timing(-0.3, 60), "early")
        self.assertEqual(m._timing(0.05, 60), "clean")
        self.assertEqual(m._timing(0.9, 60), "late")
        self.assertEqual(m._timing(2.0, 0), "clean")


class TypingDetectorTest(unittest.TestCase):
    def test_chat_message_is_typing(self):
        d = TypingDetector({"q", "e", "f", "g", "w", "a", "s", "d"})
        hits = [d.press(k, 1.0 + i * 0.12) for i, k in enumerate("hi there")]
        self.assertTrue(any(hits))

    def test_bound_build_spam_is_not_typing(self):
        d = TypingDetector({"q", "e", "f", "g", "w", "a", "s", "d"})
        self.assertFalse(any(d.press(k, 1.0 + i * 0.15) for i, k in enumerate("qefqefqefqef")))

    def test_typing_lasts_until_idle(self):
        d = TypingDetector(set())
        for i, k in enumerate("hello"):
            d.press(k, 1.0 + i * 0.1)
        self.assertTrue(d.press("q", 2.0))
        self.assertFalse(d.press("q", 10.0))


class SummaryTest(unittest.TestCase):
    def test_summary_and_fix_line(self):
        events = [{"kind": "ok", "key": "q"}] * 8 + [{"kind": "unmapped", "key": "h"}] + [
            {"kind": "kstep", "outcome": "clean", "offset_ms": 10, "lat_ms": 300},
            {"kind": "kstep", "outcome": "clean", "offset_ms": 30, "lat_ms": 340},
            {"kind": "kstep", "outcome": "slip", "wrong": "g", "intended": "f"},
            {"kind": "kstep", "outcome": "slip", "wrong": "g", "intended": "f"},
            {"kind": "kstep", "outcome": "ungraded"}]
        s = summary(events)
        self.assertEqual((s["steps"], s["clean"], s["step_pct"]), (4, 2, 50))
        self.assertEqual(s["bound_pct"], 89)
        self.assertEqual(s["top_pair"], (("g", "f"), 2))
        self.assertEqual(fix_next(s, {"f": "floor"}), "G pressed for F (floor) x2")

    def test_nothing_yet(self):
        self.assertEqual(fix_next(summary([])), "")

    def test_distance(self):
        self.assertEqual(key_distance("g", "f"), 1.0)
        self.assertIsNone(key_distance("mouse_left", "f"))


if __name__ == "__main__":
    unittest.main()


class StatsRowsTest(unittest.TestCase):
    def test_drill_rows(self):
        from keystroke_lab.stats_rows import rows
        events = [{"kind": "kstep", "outcome": "clean", "offset_ms": o, "lat_ms": 300, "drill": "P2", "tempo": 90}
                  for o in (0, 20, -10, 15)] + [{"kind": "kstep", "outcome": "slip", "wrong": "g", "intended": "f"}] * 2
        r = rows(summary(events), {"f": "floor"})
        self.assertEqual([x[0] for x in r], ["Accuracy", "Timing", "Misses by cause", "Fix next"])
        self.assertIn("67% clean · 4/6 steps (P2 · 90 apm)", r[0][1])
        self.assertIn("beat→build 300 ms", r[1][1])
        self.assertEqual(r[2][1], "slip x2 (G→F x2)")
        self.assertEqual(r[3][1], "G pressed for F (floor) x2")

    def test_free_play_and_empty(self):
        from keystroke_lab.stats_rows import rows
        r = rows(summary([{"kind": "ok", "key": "q"}] * 3 + [{"kind": "unmapped", "key": "h"}]))
        self.assertEqual(r[0], ("Accuracy (free play)", "75% bound presses · 1 unbound", ("meter", 0.75)))
        self.assertEqual(rows(summary([]))[0][1], "no presses yet")
