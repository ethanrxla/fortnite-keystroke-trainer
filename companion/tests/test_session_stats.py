import json
import tempfile
import unittest
from pathlib import Path

from keystroke_lab import session_stats as ss
from keystroke_lab.store import Store


def attempt(n, made, outcome="completed", suggested=None, followed=None, travel=1.2, ideal=1.0, t_open=1000.0):
    return {"attempt_id": f"a{n}", "session_id": "s", "piece": "wall", "outcome": outcome,
            "t_edit_open": t_open + n, "t_close": t_open + n + 0.5, "matched_edit_id": made,
            "suggested_edit_id": suggested or made, "followed_suggestion": followed, "travel": travel,
            "picks": [{"id": made, "cost": 0.4, "travel": ideal}] if made else []}


class SessionStats(unittest.TestCase):
    def test_doubles_count_quick_repeats_but_never_held_keys(self):
        events = [{"t": 1.00, "kind": "ok", "key": "g", "ts": 999.0},
                  {"t": 1.03, "kind": "ok", "key": "g"},          # 30 ms later: a double
                  {"t": 1.05, "kind": "repeat", "key": "g"},      # held key: never a double
                  {"t": 2.00, "kind": "ok", "key": "g"},          # a second later: fine
                  {"t": 3.00, "kind": "unmapped", "key": "caps_lock"},
                  {"t": 3.50, "kind": "unmapped", "key": "caps_lock"}]
        a = ss.accidental(events)
        self.assertEqual((a["strays"], a["doubles"]), (2, 1))
        self.assertEqual(a["top_keys"][0], "caps_lock")

    def test_only_confident_verdicts_count_and_every_stray_is_on_the_bar(self):
        findings = [{"intent": "slip", "confidence": 0.91, "uncertainty": False},
                    {"intent": "deliberate", "confidence": 0.85, "uncertainty": False},
                    {"intent": "slip", "confidence": 0.6, "uncertainty": False},
                    {"intent": "insufficient_evidence", "confidence": 0.95, "uncertainty": True}]
        events = [{"t": i, "kind": "unmapped", "key": "x"} for i in range(6)] + [{"kind": "analysis", "findings": findings}]
        v = ss.accidental(events)["verdicts"]
        self.assertEqual((v["slip"], v["deliberate"], v["noise"], v["unsure"]), (1, 1, 0, 4))
        self.assertEqual(sum(v.values()), 6)

    def test_missed_steps_from_the_island_and_the_overlay(self):
        store = Store(":memory:")
        for n, result in enumerate(("ok", "missing", "ok", "missing", "late")):
            store.add_kt(1000.0 + n, {"event": "step", "drill_id": "edit_peek", "step": 1, "result": result})
        store.add_kt(900.0, {"event": "step", "drill_id": "edit_peek", "step": 1, "result": "missing"})   # older session
        events = [{"ts": 1000.0, "t": 0, "kind": "ok", "key": "w"},
                  {"t": 5, "kind": "missed", "drill": "edit_half_wall", "actions": ["jump"]}]
        m = ss.missed(events, store, ss.session_start(events))
        self.assertEqual((m["missed"], m["graded"]), (4, 6))
        self.assertEqual((m["steps"][0]["drill"], m["steps"][0]["missed"]), ("edit_half_wall", 1))
        self.assertEqual(ss.missed([], None, None), {"steps": [], "graded": 0, "missed": 0})

    def test_edit_accuracy_follows_labels_and_measures_travel_against_ideal(self):
        store = Store(":memory:")
        store.add_attempt(attempt(1, "window_center", followed=True, travel=1.2, ideal=1.0))
        store.add_attempt(attempt(2, "window_center", followed=True, travel=1.6, ideal=1.0))
        store.add_attempt(attempt(3, None, outcome="reset", suggested="half_arch_right", followed=None))
        store.add_attempt(attempt(4, "corner_lower_left", suggested="window_center", followed=False, travel=3.0, ideal=2.0))
        store.add_attempt(attempt(5, "window_center", followed=True))
        store.add_attempt(attempt(0, "window_center", t_open=10.0))          # before this session
        store.add_label("a5", "rejected")
        e = ss.edits(store, 1000.0)
        self.assertEqual(e["attempts"], 4)
        self.assertEqual(e["completed_pct"], 75)
        self.assertEqual(e["followed_pct"], 67)
        self.assertEqual(e["travel_vs_ideal"], 1.5)   # median of 1.2, 1.6 and 3.0 / 2.0
        self.assertEqual(e["per_edit"][0], {"edit": "window_center", "attempts": 2, "enough": False, "completed_pct": 100})

    def test_snapshot_reads_the_newest_file_and_survives_a_torn_line(self):
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder) / "keys-1.events.jsonl"
            new = Path(folder) / "keys-2.events.jsonl"
            old.write_text(json.dumps({"ts": 1.0, "t": 0, "kind": "unmapped", "key": "z"}) + "\n")
            new.write_text(json.dumps({"ts": 2000.0, "t": 0, "kind": "unmapped", "key": "x"}) + "\n"
                           + json.dumps({"t": 1, "kind": "ai_tip", "text": "Slow reps."}) + "\n" + '{"t": 2, "ki')
            import os
            os.utime(old, (1, 1))
            events = ss.read_events(ss.newest_events(folder))
            snap = ss.snapshot(events, Store(":memory:"))
            self.assertEqual((snap["since"], snap["accidental"]["strays"], snap["tip"]), (2000.0, 1, "Slow reps."))
            self.assertEqual(snap["edits"]["attempts"], 0)
            self.assertIsNone(ss.newest_events(Path(folder) / "none"))


if __name__ == "__main__":
    unittest.main()


class PanelLayout(unittest.TestCase):
    def setUp(self):
        from keystroke_lab import stats_panel
        self.sp = stats_panel

    def test_panel_sits_above_the_edit_guide_and_the_keyboard(self):
        for rect, scale in (((0, 0, 1920, 1080), 1.5), ((0, 0, 2560, 1440), 1.5), ((0, 0, 1920, 1080), 2.0),
                            ((100, 50, 2020, 1130), 1.0)):
            left, top, right, bottom = rect
            gh = bottom - top
            x, y, w, h = self.sp.geometry(rect, scale)
            u_edit = max(22, min(42, int(gh / 54 * 1.5)))
            edit_top = bottom - int(gh * 0.135) - 11 * u_edit - 240 - 8
            u_keys = max(22, min(42, int(gh / 54 * max(1.0, min(scale, 2.0)))))
            keys_top = bottom - int(gh * 0.135) - 11 * u_keys
            self.assertLessEqual(y + h, min(edit_top, keys_top) - 8, rect)
            self.assertGreaterEqual(y, top + int(gh * 0.12), rect)
        self.assertEqual(self.sp.geometry((0, 0, 1920, 1080), 1.5), (23, 199, 380, 150))
        self.assertIsNone(self.sp.geometry((0, 0, 800, 600), 1.5))

    def test_lines_show_empty_states_and_numbers(self):
        empty = ss.snapshot([], None)
        self.assertEqual([l[1] for l in self.sp.lines(empty)], ["no graded drills yet", "none", "no edits yet"])
        snap = {"missed": {"steps": [{"drill": "edit_peek", "step": 2, "missed": 4, "graded": 18}]},
                "accidental": {"strays": 23, "doubles": 6, "top_keys": ["caps_lock", "x"],
                               "verdicts": {"slip": 11, "deliberate": 3, "noise": 0, "unsure": 9}},
                "edits": {"attempts": 12, "completed_pct": 81, "followed_pct": 78, "travel_vs_ideal": 1.3}, "tip": ""}
        rows = self.sp.lines(snap)
        self.assertEqual(rows[0][1], "4 / 18")
        self.assertEqual(rows[2][1], "81% done · followed 78% · travel 1.3×")
        self.assertEqual(self.sp.verdict_parts(snap), [("slip", 11), ("deliberate", 3), ("unsure", 9)])
