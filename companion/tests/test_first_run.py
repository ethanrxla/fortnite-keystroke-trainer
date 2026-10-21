import json
import tempfile
import unittest
from pathlib import Path

from keystroke_lab import first_run


class FirstRunTests(unittest.TestCase):
    def test_missing_binds_file_needs_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(first_run.needs_calibration(Path(d) / "keybinds.json"))
            self.assertIn("sprint", first_run.unverified(Path(d) / "keybinds.json"))

    def test_confirmed_core_binds_stop_the_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "keybinds.json"
            path.write_text(json.dumps({
                "version": 1, "profile_id": "p", "revision": 1,
                "bindings": [{"action": a, "keys": ["x"], "context": "any", "verified": True} for a in first_run.CORE_ACTIONS]}),
                encoding="utf-8")
            self.assertEqual(first_run.unverified(path), [])
            self.assertFalse(first_run.needs_calibration(path))

    def test_prompt_limits(self):
        self.assertTrue(first_run.should_prompt({"prompts": 0, "last": 0}, now=1000.0, missing=True))
        self.assertFalse(first_run.should_prompt({"prompts": 0, "last": 0}, now=1000.0, missing=False))
        self.assertFalse(first_run.should_prompt({"prompts": first_run.MAX_PROMPTS, "last": 0}, now=1e9, missing=True))
        self.assertFalse(first_run.should_prompt({"prompts": 1, "last": 990.0}, now=1000.0, missing=True))   # too soon

    def test_launch_opens_calibration_once_per_gap_and_records_it(self):
        with tempfile.TemporaryDirectory() as d:
            launched = []
            kwargs = dict(popen=lambda cmd, **kw: launched.append(cmd) or "proc", binds_path=Path(d) / "keybinds.json",
                          state_path=Path(d) / "state.json")
            self.assertEqual(first_run.maybe_launch(saves=lambda: [], now=5000.0, **kwargs), "proc")
            self.assertTrue(any("calibration_window" in part for part in launched[0]))
            self.assertIsNone(first_run.maybe_launch(saves=lambda: [], now=5001.0, **kwargs))          # inside the gap: not again
            self.assertEqual(first_run.maybe_launch(saves=lambda: [], now=9000.0, **kwargs), "proc")   # a later game start offers it again
            self.assertEqual(first_run.load_state(Path(d) / "state.json")["prompts"], 2)

    def test_no_launch_when_fortnite_settings_save_exists(self):
        with tempfile.TemporaryDirectory() as d:
            launched = []
            proc = first_run.maybe_launch(saves=lambda: [Path(d) / "ClientSettings.Sav"], popen=lambda *a, **k: launched.append(a),
                                          binds_path=Path(d) / "keybinds.json", state_path=Path(d) / "s.json", now=5000.0)
            self.assertIsNone(proc)
            self.assertEqual(launched, [])

    def test_no_launch_when_calibrated(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "keybinds.json"
            path.write_text(json.dumps({
                "version": 1, "profile_id": "p", "revision": 1,
                "bindings": [{"action": a, "keys": ["x"], "context": "any", "verified": True} for a in first_run.CORE_ACTIONS]}),
                encoding="utf-8")
            self.assertIsNone(first_run.maybe_launch(saves=lambda: [], popen=lambda *a, **k: "proc", binds_path=path, state_path=Path(d) / "s.json", now=1.0))


if __name__ == "__main__":
    unittest.main()
