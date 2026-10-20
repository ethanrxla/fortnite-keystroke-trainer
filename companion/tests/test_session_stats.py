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
        self.assertEqual((a["strays"], a["unmapped"], a["doubles"]), (0, 2, 1))
        self.assertEqual(a["top_keys"][0], "caps_lock")

    def test_only_valid_non_shadow_findings_reach_player_stats(self):
        from keystroke_lab.analysis import INTENT_OPTIONS
        def finding(i, **changes):
            f = dict(intent='deliberate', confidence=.95, uncertainty=False, shadow=False,
                     evidence_ids=[str(i)], probabilities={k: (.97 if k == 'deliberate' else .01) for k in INTENT_OPTIONS})
            f.update(changes)
            return f
        good = finding(1)
        findings = [good, dict(good), finding(2, shadow=True), finding(3, probabilities={}),
                    finding(4, confidence=True), finding(5, uncertainty=True)]
        v = ss.accidental([{'kind':'analysis', 'findings': findings}])['verdicts']
        self.assertEqual(v['deliberate'], 1)
        self.assertEqual(v['slip'], 0)
        self.assertEqual(v['unsure'], 3)

    def test_drill_grading_never_feeds_the_stats(self):
        store = Store(":memory:")
        for n, result in enumerate(("missing", "missing", "late")):
            store.add_kt(1000.0 + n, {"event": "step", "drill_id": "edit_peek", "step": 1, "result": result})
        events = [{"ts": 1000.0, "t": 0, "kind": "ok", "key": "w"},
                  {"t": 5, "kind": "missed", "drill": "edit_half_wall", "actions": ["jump"]},
                  {"t": 6, "kind": "order", "key": "q", "drill": "edit_half_wall"}]
        snap = ss.snapshot(events, store)
        self.assertEqual(snap["missed"], {"steps": [], "graded": 0, "missed": 0})
        self.assertNotIn("order", snap["accidental"])
        self.assertEqual(ss.missed([], None, None), {"steps": [], "graded": 0, "missed": 0})

    def test_missed_confirm_in_ordinary_play_without_any_drill(self):
        store = Store(":memory:")
        def add(n, tiles, confirmed, outcome="completed", reset=False, enriched=True):
            rec = attempt(n, "window_center", outcome=outcome)
            rec.update(final_tiles=tiles, selection_trace=[{"t": 1, "tiles": tiles}] if tiles else [],
                       t_confirm=1001.0 + n if confirmed else None, t_reset=1001.0 + n if reset else None)
            store.add_attempt(rec)
            if enriched:
                store.update_attempt(rec, enriched=True)
        add(1, [4], True)
        add(2, [4], False)                                  # selected, closed without confirming: a missed confirm
        add(3, [1, 4], False, outcome="wrong_shape")        # likewise
        add(4, [4], False, outcome="reset", reset=True)     # a deliberate reset: not a miss
        add(5, [], False, outcome="abandoned")              # nothing selected: not counted
        add(6, [4], False, enriched=False)                  # key presses not joined yet: not judged
        events = [{"ts": 1000.0, "t": 0, "kind": "ok", "key": "w"}]
        m = ss.missed(events, store, 1000.0, {"edit": "g", "edit_confirm": "mouse_left"})
        self.assertEqual(m["steps"][0]["not_observed"], 2)
        self.assertEqual((m["missed"], m["graded"]), (0, 0))
        # Edit and confirm on one key (C / C): the second press is the confirm, counted the same way.
        self.assertEqual(ss.missed(events, store, 1000.0, {"edit": "c", "edit_confirm": "c"})["steps"][0]["not_observed"], 2)

    def test_missing_confirms_never_infer_edit_on_release_or_a_miss(self):
        store = Store(":memory:")
        for n in range(1, 10):                      # nine edits with a selection, none with a confirm press
            rec = attempt(n, "window_center")
            rec.update(final_tiles=[4], selection_trace=[{"t": 1, "tiles": [4]}], t_confirm=None, t_reset=None)
            store.add_attempt(rec)
            store.update_attempt(rec, enriched=True)
        m = ss.edit_misses(store, 1000.0)
        self.assertTrue(m["unknown_mode"])
        self.assertIsNone(ss.edits_on_release(store))
        self.assertEqual((m["missed"], m["graded"]), (0, 0))
        # The player's own setting wins over the guess either way.
        self.assertEqual(ss.edit_misses(store, 1000.0, on_release=False)["missed"], 0)
        self.assertEqual(ss.edit_misses(store, 1000.0, on_release=False)["not_observed"], 9)
        self.assertTrue(ss.edits_on_release(store, True))
        from keystroke_lab import stats_panel
        snap = ss.snapshot([{"ts": 1000.0, "t": 0, "kind": "ok", "key": "w"}], store)
        self.assertEqual(stats_panel.lines(snap)[0][1], "9 / 9 · ungraded")
        snap = ss.snapshot([{"ts": 1000.0}], store, on_release=True)
        self.assertEqual(stats_panel.lines(snap)[0][1], "not observable: edit on release")

    def test_selection_match_follows_labels_and_measures_travel_against_ideal(self):
        store = Store(":memory:")
        selected = [attempt(1, "window_center", followed=True, travel=1.2, ideal=1.0),
                    attempt(2, "window_center", followed=True, travel=1.6, ideal=1.0),
                    attempt(4, "corner_lower_left", suggested="window_center", followed=False, travel=3.0, ideal=2.0),
                    attempt(5, "window_center", followed=True),
                    attempt(0, "window_center", t_open=10.0)]  # before this session
        for rec in selected:
            rec.update(final_tiles=[4], selection_trace=[{"t": rec["t_edit_open"], "tiles": [4]}])
            store.add_attempt(rec)
        store.add_attempt(attempt(3, None, outcome="reset", suggested="half_arch_right", followed=None))
        store.add_label("a5", "rejected")
        e = ss.edits(store, 1000.0)
        self.assertEqual(e["attempts"], 3)
        self.assertEqual(e["completed_pct"], 100)
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
            self.assertEqual((snap["since"], snap["accidental"]["unmapped"], snap["tip"]), (2000.0, 1, "Slow reps."))
            self.assertEqual(snap["edits"]["attempts"], 0)
            self.assertIsNone(ss.newest_events(Path(folder) / "none"))


if __name__ == "__main__":
    unittest.main()


class PanelLayout(unittest.TestCase):
    def setUp(self):
        from keystroke_lab import stats_panel
        self.sp = stats_panel

    def test_panel_sits_below_the_edit_guide_and_above_the_keyboard(self):
        for rect, scale in (((0, 0, 1920, 1080), 1.5), ((0, 0, 2560, 1440), 1.5), ((0, 0, 1920, 1080), 2.0),
                            ((100, 50, 2020, 1130), 1.0)):
            left, top, right, bottom = rect
            gh = bottom - top
            x, y, w, h = self.sp.geometry(rect, scale)
            u_edit = max(22, min(42, int(gh / 54 * 1.5)))
            u_keys = max(22, min(42, int(gh / 54 * max(1.0, min(scale, 2.0)))))
            from keystroke_lab.overlay_layout import edit_guide_lift
            lift = edit_guide_lift(gh, scale, 11)
            edit_top = max(top + 8, bottom - int(gh * 0.135) - 11 * u_edit - 240 - 8 - lift)
            keys_top = bottom - int(gh * 0.135) - 11 * u_keys
            self.assertGreaterEqual(y, edit_top + 240 + 8, rect)
            self.assertLessEqual(y + h, keys_top - 8, rect)
            self.assertGreaterEqual(y, top + int(gh * 0.12), rect)
        self.assertEqual(self.sp.geometry((0, 0, 1920, 1080), 1.5), (23, 447, 380, 150))
        self.assertIsNone(self.sp.geometry((0, 0, 800, 600), 1.5))

    def test_lines_show_empty_states_and_numbers(self):
        empty = ss.snapshot([], None)
        self.assertEqual([l[1] for l in self.sp.lines(empty)], ["needs a fully observed drill", "none", "no observed attempts yet"])
        snap = {"missed": {"steps": [{"drill": "edit_peek", "step": 2, "missed": 4, "graded": 18}]},
                "accidental": {"strays": 23, "doubles": 6, "top_keys": ["caps_lock", "x"],
                               "verdicts": {"slip": 11, "deliberate": 3, "noise": 0, "unsure": 9}},
                "edits": {"attempts": 12, "completed_pct": 81, "followed_pct": 78, "travel_vs_ideal": 1.3}, "tip": ""}
        rows = self.sp.lines(snap)
        self.assertEqual(rows[0][1], "4 / 18")
        self.assertEqual(rows[2][1], "81% selection match · followed 78% · travel 1.3×")
        self.assertEqual(self.sp.verdict_parts(snap), [("slip", 11), ("deliberate", 3), ("unsure", 9)])
