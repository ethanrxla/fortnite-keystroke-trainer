import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.vision_packages'))
try:
    import numpy as np
    from keystroke_lab import attempt_schema
    from keystroke_lab.frame_dataset import FrameDataset, load_manifest, record_from_result
except ImportError:
    np = None

RESULT = {"mode": "editing", "detection_reason": "native_edit_grid_observed", "reference_ids": ["corner_upper_right"],
          "processing_ms": 42.0,
          "observation": {"piece": "wall", "wall_quad": [[100, 100], [700, 100], [700, 500], [100, 500]],
                          "aim_uv": [1.9, 1.9], "selected_tiles": [5]}}


@unittest.skipIf(np is None, "vision dependencies missing")
class FrameDatasetTests(unittest.TestCase):
    def test_record_matches_schema(self):
        rec = record_from_result("1", "1.jpg", "s", 10.0, 1280, 720, RESULT, "a1")
        self.assertEqual(attempt_schema.errors(rec, attempt_schema.load("edit_frame.v1")), [])
        self.assertEqual(rec["auto"]["suggested_edit_id"], "corner_upper_right")

    def test_live_saving_is_rate_limited_scaled_and_edit_mode_only(self):
        with tempfile.TemporaryDirectory() as d:
            now = [0.0]
            ds = FrameDataset("s1", root=d, rate=2.0, clock=lambda: now[0])
            frame = np.zeros((1080, 1920, 3), np.uint8)
            self.assertIsNone(ds.maybe_save(frame, dict(RESULT, mode="unknown"), 1.0))
            self.assertIsNotNone(ds.maybe_save(frame, RESULT, 1.0))
            now[0] = 0.2
            self.assertIsNone(ds.maybe_save(frame, RESULT, 1.2))          # within 0.5 s
            now[0] = 0.6
            rec = ds.maybe_save(frame, RESULT, 1.6, "att")
            self.assertEqual(rec["attempt_id"], "att")
            self.assertEqual(rec["width"], 1280)
            self.assertAlmostEqual(rec["auto"]["quad"][1][0], 700 * 1280 / 1920, places=3)   # quad scaled with the image
            rows = load_manifest(d)
            self.assertEqual(len(rows), 2)
            self.assertTrue((Path(d) / "s1" / rows[0][1]["image"]).exists())

    def test_never_raises(self):
        ds = FrameDataset("s", root=tempfile.mkdtemp())
        self.assertIsNone(ds.maybe_save(None, RESULT, 1.0))


if __name__ == "__main__":
    unittest.main()
