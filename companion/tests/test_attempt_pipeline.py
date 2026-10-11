import json
import tempfile
import unittest
import uuid
from pathlib import Path

from keystroke_lab import collector, ktlog
from keystroke_lab.store import Store


def record(**over):
    r = {"schema": "edit_attempt.v1", "attempt_id": str(uuid.uuid4()), "session_id": "s", "map_id": "keystroke_trainer",
         "catalog_version": 2, "policy_version": None, "piece": "wall", "piece_evidence": "observed", "source": "screen",
         "suggested_edit_id": "window_center", "suggestion_verified": False, "picks": [], "context": None,
         "t_edit_open": 100.0, "t_first_select": 100.2, "t_confirm": None, "t_reset": None, "t_close": 101.0,
         "selection_trace": [{"t": 100.2, "tiles": [4]}], "aim_trace": [], "final_tiles": [4],
         "matched_edit_id": "window_center", "followed_suggestion": True, "travel": 0.0, "observation_gaps": 0,
         "outcome": "completed", "auto_label_confidence": 0.8, "label_status": "auto", "frames": []}
    r.update(over)
    return r


BINDS = {"edit": "c", "edit_confirm": "c", "reset": "wheel_down"}


class AttemptPipelineTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.dir.name)
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def write(self, *records, name="edit-s.attempts.jsonl"):
        with (self.folder / name).open("a") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_ingest_is_idempotent_and_skips_invalid_records(self):
        good = record()
        self.write(good, {"schema": "edit_attempt.v1", "attempt_id": "bad"})
        self.assertEqual(collector.ingest_attempts(self.store, self.folder), 1)
        self.assertEqual(collector.ingest_attempts(self.store, self.folder), 0)     # offset remembered
        self.store.add_attempt(good)                                                # re-insert is harmless
        self.assertEqual(self.store.rows("SELECT COUNT(*) FROM edit_attempts")[0][0], 1)

    def test_legacy_confirm_join_does_not_upgrade_confidence(self):
        r = record()
        self.write(r)
        collector.ingest_attempts(self.store, self.folder)
        self.store.add_key(100.05, "c", "ok")        # the press that opened edit mode: skipped
        self.store.add_key(100.9, "c", "ok")         # confirm
        self.store.add_key(200.0, "w", "ok")         # key data exists after the attempt
        self.assertEqual(collector.enrich_attempts(self.store, BINDS, now=500.0), 1)
        out = self.store.attempt(r["attempt_id"])
        self.assertEqual(out["t_confirm"], 100.9)
        self.assertEqual(out["auto_label_confidence"], 0.8)
        self.assertEqual(collector.enrich_attempts(self.store, BINDS, now=500.0), 0)   # done once

    def test_waits_for_key_data(self):
        self.write(record())
        collector.ingest_attempts(self.store, self.folder)
        self.assertEqual(collector.enrich_attempts(self.store, BINDS, now=500.0), 0)   # no keys at all yet
        self.assertEqual(collector.enrich_attempts(self.store, BINDS, now=102.0), 0)   # too soon after close

    def test_labels_newest_wins(self):
        r = record()
        self.store.add_attempt(r)
        self.store.add_label(r["attempt_id"], "rejected", at=1.0)
        self.store.add_label(r["attempt_id"], "approved", "window_center", at=2.0)
        self.assertEqual(self.store.label(r["attempt_id"])["status"], "approved")


class KtlogTests(unittest.TestCase):
    def test_events_without_a_drill_keep_their_first_value(self):
        rec = ktlog.parse_line("LogVerse: : KT|context|players=1|t=3.5|px=1")
        self.assertEqual(rec["drill_id"], "")
        self.assertEqual(rec["players"], "1")
        self.assertEqual(rec["t"], 3.5)

    def test_drill_events_unchanged(self):
        rec = ktlog.parse_line("KT|step|B1|tempo=60|rep=2|step=1|result=ok|t=1.0")
        self.assertEqual(rec["drill_id"], "B1")
        self.assertEqual(rec["rep"], 2)


if __name__ == "__main__":
    unittest.main()
