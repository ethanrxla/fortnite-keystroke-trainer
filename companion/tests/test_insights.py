import json
import tempfile
import unittest
from pathlib import Path

from keystroke_lab import insights
from keystroke_lab.keyboard_overlay import SessionLog, in_game

EV = [
    {"t": 1, "kind": "stray", "key": "x", "drill": "edit_window"},
    {"t": 2, "kind": "stray", "key": "x", "drill": "edit_window"},
    {"t": 3, "kind": "double", "key": "g", "drill": "edit_window"},
    {"t": 4, "kind": "order", "key": "q", "drill": "edit_window"},
    {"t": 5, "kind": "ok", "key": "g", "drill": "edit_window"},
    {"t": 9, "kind": "missed", "actions": ["edit_confirm"], "drill": "edit_window"},
]


class InsightsTests(unittest.TestCase):
    def test_summary_counts(self):
        s = insights.summarize(EV)
        self.assertEqual(s["presses"], 5)
        self.assertEqual(s["strays"]["x"], 2)
        self.assertEqual(s["missed"][("edit_window", "edit_confirm")], 1)

    def test_advice_ranks_biggest_first(self):
        text = insights.advice(insights.summarize(EV))
        self.assertIn("'x'", text[0])
        self.assertTrue(any("edit_confirm" in t for t in text))

    def test_current_overlay_kinds_are_not_counted_as_presses(self):
        ev = [{"kind": "ok", "key": "g"}, {"kind": "repeat", "key": "g"}, {"kind": "repeat", "key": "g"},
              {"kind": "unmapped", "key": "esc"}, {"kind": "habit", "key": "h"},
              {"kind": "ai_tip", "text": "x"}, {"kind": "analysis", "findings": []}]
        s = insights.summarize(ev)
        self.assertEqual(s["presses"], 3)
        self.assertEqual(s["held"], 2)
        self.assertEqual(s["strays"]["esc"], 1)

    def test_step_failures_are_ranked_with_their_rate(self):
        recs = [{"event": "step", "drill_id": "B1", "step": 2, "result": r}
                for r in ["ok", "missing", "missing", "late", "ok"]]
        recs += [{"event": "step", "drill_id": "B1", "step": 1, "result": "unchecked"},
                 {"event": "set_end", "drill_id": "B1"}]
        f = insights.step_failures(recs)
        self.assertEqual(list(f), [("B1", 2)])
        self.assertEqual(f[("B1", 2)]["graded"], 5)
        text = insights.step_advice(f)
        self.assertIn("B1 step 2", text[0][1])
        self.assertIn("2 of 5", text[0][1])
        self.assertIn("never happened", text[0][1])

    def test_report_mentions_step_failures(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "a.events.jsonl"
            path.write_text(json.dumps({"kind": "ok", "key": "g"}) + "\n")
            out = insights.report([path], [{"event": "step", "drill_id": "E2", "step": 1, "result": "early"}])
            self.assertIn("E2 step 1", out)

    def test_logging_only_while_game_focused(self):
        with tempfile.TemporaryDirectory() as d:
            focus = {"title": "Notepad"}
            log = SessionLog(Path(d) / "s", focus=lambda: focus["title"])
            self.assertFalse(log.write("stray", "h", False))
            focus["title"] = "Fortnite"
            self.assertTrue(log.write("ok", "g", True))
            log.close()
            keys = (Path(d) / "s.jsonl").read_text().splitlines()
            events = (Path(d) / "s.events.jsonl").read_text().splitlines()
            self.assertEqual([json.loads(k)["name"] for k in keys], ["g"])
            self.assertEqual(len(events), 1)

    def test_in_game_matches_uefn_and_fortnite(self):
        self.assertTrue(in_game("Unreal Editor for Fortnite"))
        self.assertFalse(in_game("Notepad"))


if __name__ == "__main__":
    unittest.main()
