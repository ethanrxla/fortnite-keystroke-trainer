import copy
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from keystroke_lab import attempt_review
from keystroke_lab.store import Store
from tests.test_attempt_pipeline import record

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import promote_edits  # noqa: E402


class ReviewServerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "p.db"
        s = Store(self.db)
        self.rec = record(attempt_id=str(uuid.uuid4()))
        s.add_attempt(self.rec)
        s.close()
        self.server, self.url = attempt_review.serve(port=0, open_browser=False, store_factory=lambda: Store(self.db),
                                                     secret="t0k")
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.dir.cleanup()

    def get(self, path):
        req=urllib.request.Request(self.base+path,headers={"X-KT-Token":"t0k"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()

    def post(self, body, token="t0k"):
        req = urllib.request.Request(self.base + "/api/label", json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-KT-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_page_and_queue(self):
        status, page = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("Edit attempts", page)
        data = json.loads(self.get("/api/attempts")[1])
        self.assertEqual([a["attempt_id"] for a in data["attempts"]], [self.rec["attempt_id"]])
        self.assertIn("wall", data["catalogue"])

    def test_label_needs_token_and_leaves_the_queue(self):
        self.assertEqual(self.post({"attempt_id": self.rec["attempt_id"], "status": "approved"}, token="nope"), 403)
        self.assertEqual(self.post({"attempt_id": self.rec["attempt_id"], "status": "maybe"}), 400)
        self.assertEqual(self.post({"attempt_id": "missing", "status": "approved"}), 404)
        self.assertEqual(self.post({"attempt_id": self.rec["attempt_id"], "status": "approved"}), 200)
        self.assertEqual(json.loads(self.get("/api/attempts")[1])["attempts"], [])
        self.assertEqual(len(json.loads(self.get("/api/attempts?status=approved")[1])["attempts"]), 1)


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.data = json.loads((ROOT / "shared/edits.json").read_text(encoding="utf-8"))

    def add(self, session, status="approved", matched="window_center", edit_id=None):
        r = record(attempt_id=str(uuid.uuid4()), session_id=session, matched_edit_id=matched)
        self.store.add_attempt(r)
        self.store.add_label(r["attempt_id"], status, edit_id, reviewer="ethan", result_confirmed=status!="rejected")

    def window(self, data):
        return next(e for e in data["wall_edits"] if e["id"] == "window_center")

    def test_needs_three_approvals_in_two_sessions(self):
        for _ in range(3):
            self.add("s1")
        data = copy.deepcopy(self.data)
        self.assertEqual(promote_edits.promote(data, None, promote_edits.tally(self.store), "42.10"), [])
        self.add("s2")
        promoted = promote_edits.promote(data, None, promote_edits.tally(self.store), "42.10")
        self.assertEqual(promoted, ["window_center"])
        v = self.window(data)["validation"]
        self.assertEqual(v["status"], "game_verified")
        self.assertEqual(len(v["evidence"]), 4)
        self.assertTrue(v["result_confirmed"])

    def test_relabels_count_for_the_corrected_edit_and_rejections_do_not(self):
        self.add("s1", status="relabelled", matched="window_center", edit_id="window_high")
        self.add("s2", status="relabelled", matched=None, edit_id="window_high")
        self.add("s2", status="relabelled", matched=None, edit_id="window_high")
        self.add("s3", status="rejected")
        counts = promote_edits.tally(self.store)
        self.assertEqual(len(counts["window_high"]["approved"]), 3)
        self.assertEqual(counts["window_center"]["rejected"], 1)
        self.assertIn("window_high", promote_edits.promote(copy.deepcopy(self.data), None, counts, "42.10"))

    def test_promoted_edit_becomes_a_verified_dictionary_entry(self):
        from keystroke_lab.edit_dictionary import game_verified
        for s in ("s1", "s1", "s2"):
            self.add(s)
        data = copy.deepcopy(self.data)
        promote_edits.promote(data, None, promote_edits.tally(self.store), "42.10")
        self.assertTrue(game_verified(self.window(data)))


if __name__ == "__main__":
    unittest.main()
