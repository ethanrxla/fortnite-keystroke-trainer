import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.vision_packages'))   # numpy / cv2 for the matcher

from keystroke_lab import attempt_schema
from keystroke_lab.attempt_recorder import AttemptLog, AttemptRecorder, default_matcher
from keystroke_lab.edit_dictionary import EditDictionary
from keystroke_lab.pieces import canonical, catalog_key, cells


def frame(mode="editing", tiles=(), aim=(1.5, 1.5), piece="wall", suggestion="window_center", projected=True):
    return {"mode": mode, "projected": projected and mode == "editing",
            "observation": {"piece": piece, "aim_uv": list(aim), "selected_tiles": list(tiles)} if mode == "editing" else None,
            "reference_ids": [suggestion] if suggestion else [], "verified": False,
            "picks": [{"id": suggestion, "name": "x", "cost": 0.2, "travel": 0.3}] if suggestion else [],
            "piece_context": {"kind": "wall", "cells": 3, "aim": list(aim), "side": 1, "far": False, "distance_cm": 300.0,
                              "camera": [1.0, 2.0, 3.0], "body": [1.0, 2.0, 3.0], "across": [1.0, 0, 0], "away": [0, -1.0, 0],
                              "source": "screen_pose_estimate"}}


class PiecesTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(canonical("roof"), "cone")
        self.assertEqual(canonical("stairs"), "ramp")
        self.assertEqual(catalog_key("cone"), "roof")
        self.assertEqual(cells("floor"), 2)
        self.assertIsNone(canonical("banana"))


class AttemptRecorderTests(unittest.TestCase):
    def setUp(self):
        self.out = []
        self.rec = AttemptRecorder("s1", sink=self.out.append, matcher=default_matcher(EditDictionary()))

    def play(self, frames, t0=1000.0, dt=0.1):
        t = t0
        for f in frames:
            self.rec.feed(f, t)
            t += dt
        return t

    def test_completed_window_that_followed_the_suggestion(self):
        self.play([frame(), frame(tiles=(4,)), frame(tiles=(4,)), frame("unknown"), frame("unknown"), frame("unknown"),
                   frame("unknown")])
        self.assertEqual(len(self.out), 1)
        a = self.out[0]
        self.assertEqual(a["outcome"], "selection_matched")
        self.assertFalse(a["result_confirmed"])
        self.assertEqual(a["matched_edit_id"], "window_center")
        self.assertTrue(a["followed_suggestion"])
        self.assertEqual(a["piece"], "wall")
        self.assertEqual(a["piece_evidence"], "observed")
        self.assertAlmostEqual(a["t_first_select"], 1000.1)
        self.assertEqual(attempt_schema.errors(a), [])

    def test_one_flickering_frame_does_not_split_the_attempt(self):
        self.play([frame(), frame(tiles=(4,)), frame("unknown"), frame(tiles=(4,)), frame("unknown"), frame("unknown"),
                   frame("unknown"), frame("unknown")])
        self.assertEqual(len(self.out), 1)

    def test_reset_then_leave_is_a_reset(self):
        self.play([frame(), frame(tiles=(4,)), frame(tiles=()), frame("unknown")] + [frame("unknown")] * 4)
        a = self.out[0]
        self.assertEqual(a["outcome"], "reset")
        self.assertIsNotNone(a["t_reset"])
        self.assertEqual(a["final_tiles"], [])

    def test_unknown_shape_is_wrong_shape_and_not_followed(self):
        self.play([frame(), frame(tiles=(0, 4, 8))] + [frame("unknown")] * 5)
        a = self.out[0]
        self.assertEqual(a["outcome"], "unknown")
        self.assertIsNone(a["matched_edit_id"])

    def test_different_edit_than_suggested(self):
        self.play([frame(suggestion="window_center"), frame(tiles=(6, 7, 8), suggestion="window_center")] + [frame("unknown")] * 5)
        a = self.out[0]
        self.assertEqual(a["matched_edit_id"], "half_wall")
        self.assertFalse(a["followed_suggestion"])

    def test_nothing_selected_is_abandoned_and_gaps_lower_confidence(self):
        self.play([frame(), frame(projected=False), frame(projected=False)] + [frame("unknown")] * 5)
        a = self.out[0]
        self.assertEqual(a["outcome"], "unknown")
        self.assertEqual(a["observation_gaps"], 2)
        self.assertLess(a["auto_label_confidence"], 0.5)

    def test_floor_is_recorded_as_inferred(self):
        f = frame(piece="floor", suggestion=None)
        self.play([f] + [frame("unknown")] * 5)
        self.assertEqual(self.out[0]["piece"], "floor")
        self.assertEqual(self.out[0]["piece_evidence"], "inferred")

    def test_close_flushes_an_open_attempt(self):
        self.play([frame(), frame(tiles=(4,))])
        self.rec.close(2000.0)
        self.assertEqual(len(self.out), 1)

    def test_log_writes_one_json_line_per_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            log = AttemptLog(Path(d) / "s.attempts.jsonl")
            rec = AttemptRecorder("s2", sink=log.write)
            for i, f in enumerate([frame(), frame(tiles=(4,))] + [frame("unknown")] * 5):
                rec.feed(f, 10 + i * 0.1)
            lines = (Path(d) / "s.attempts.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["session_id"], "s2")


class SchemaTests(unittest.TestCase):
    def test_rejects_bad_records(self):
        self.assertTrue(attempt_schema.errors({}))
        bad = {"schema": "edit_attempt.v1", "attempt_id": "not-a-uuid", "session_id": "s", "map_id": "m", "piece": "tree",
               "piece_evidence": "observed", "source": "screen", "t_edit_open": 1, "t_close": 2, "outcome": "completed",
               "label_status": "auto", "secret": 1}
        problems = " ".join(attempt_schema.errors(bad))
        self.assertIn("uuid", problems)
        self.assertIn("tree", problems)
        self.assertIn("unexpected field secret", problems)

    def test_non_finite_numbers_rejected(self):
        self.assertTrue(attempt_schema.errors(float("nan"), {"type": "number"}))


if __name__ == "__main__":
    unittest.main()
