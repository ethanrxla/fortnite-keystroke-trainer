import filecmp
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from keystroke_lab.cloud.adapters import KeystrokeTrainerAdapter
from keystroke_lab.cloud.client import CloudClient, CloudError
from keystroke_lab.cloud.sync import sync_once
from keystroke_lab.store import Store
from tests.test_attempt_pipeline import record

ROOT = Path(__file__).resolve().parents[2]


class FakeSupabase:
    """Just enough of auth / PostgREST / functions to exercise the client."""
    def __init__(self, consent=True, reject=()):
        self.consent, self.reject = consent, set(reject)
        self.calls, self.ingested, self.signups = [], [], 0
        self.fail_next = None

    def __call__(self, method, url, headers, body):
        self.calls.append((url, headers, body))
        if self.fail_next:
            code, self.fail_next = self.fail_next, None
            return code, {}, {"error": "busy"}
        if url.endswith("/auth/v1/signup"):
            self.signups += 1
            return 200, {}, {"access_token": f"tok{self.signups}", "refresh_token": "r", "expires_in": 3600, "user": {"id": "p1"}}
        if "grant_type=refresh_token" in url:
            return 200, {}, {"access_token": "tok-refreshed", "refresh_token": "r2", "expires_in": 3600, "user": {"id": "p1"}}
        assert headers["Authorization"].startswith("Bearer tok"), headers
        if url.endswith("/rest/v1/rpc/me"):
            assert headers["Content-Profile"] == "api"
            return 200, {}, {"id": "p1", "consent_upload": self.consent, "consent_frames": False}
        if url.endswith("/functions/v1/ingest"):
            ids = [a["attempt_id"] for a in body["attempts"]]
            self.ingested += [i for i in ids if i not in self.reject]
            return 200, {}, {"accepted": [i for i in ids if i not in self.reject],
                             "rejected": [{"attempt_id": i, "errors": ["x"]} for i in ids if i in self.reject]}
        return 404, {}, {"error": "unknown"}


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.session_file = Path(self.dir.name) / "s.json"
        self.store = Store(":memory:")
        self.now = [1000.0]

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def client(self, fake):
        return CloudClient("https://x.supabase.co", "anon", session_file=self.session_file, http=fake, clock=lambda: self.now[0])

    def add(self, n, **over):
        recs = [record(attempt_id=str(uuid.uuid4()), t_close=100.0 + i, **over) for i in range(n)]
        for r in recs:
            self.store.add_attempt(r)
        return recs

    def test_anonymous_sign_in_is_reused_and_refreshed(self):
        fake = FakeSupabase()
        c = self.client(fake)
        self.assertEqual(c.sign_in(), "p1")
        c2 = self.client(fake)                     # new process: identity read back from the session file
        c2.sign_in()
        self.assertEqual(fake.signups, 1)
        self.now[0] += 4000                        # expired: refresh, not a new identity
        c2.sign_in()
        self.assertEqual(fake.signups, 1)
        self.assertEqual(c2.session["access_token"], "tok-refreshed")

    def test_nothing_uploads_without_consent(self):
        fake = FakeSupabase(consent=False)
        self.add(3)
        rep = sync_once(self.store, self.client(fake), now=10_000)
        self.assertEqual(rep["skipped"], "no upload consent")
        self.assertFalse(any("/functions/" in u for u, _, _ in fake.calls))

    def test_uploads_in_batches_and_marks_synced(self):
        fake = FakeSupabase()
        self.add(5)
        rep = sync_once(self.store, self.client(fake), now=10_000, batch=2)
        self.assertEqual(rep["accepted"], 5)
        self.assertEqual(self.store.rows("SELECT COUNT(*) FROM edit_attempts WHERE synced=1")[0][0], 5)
        self.assertEqual(sync_once(self.store, self.client(fake), now=10_000)["sent"], 0)   # nothing left

    def test_rejected_records_are_not_retried(self):
        recs = self.add(2)
        fake = FakeSupabase(reject={recs[0]["attempt_id"]})
        rep = sync_once(self.store, self.client(fake), now=10_000)
        self.assertEqual((rep["accepted"], rep["rejected"]), (1, 1))
        self.assertEqual(sync_once(self.store, self.client(fake), now=10_000)["sent"], 0)

    def test_server_busy_keeps_records_for_later(self):
        fake = FakeSupabase()
        self.add(2)
        c = self.client(fake)
        c.sign_in()
        fake.fail_next = None
        rpc_ok = c.rpc("me")
        self.assertTrue(rpc_ok["consent_upload"])
        orig = fake.__call__

        def busy(method, url, headers, body):
            if url.endswith("/functions/v1/ingest"):
                return 503, {}, {"error": "busy"}
            return orig(method, url, headers, body)
        c.http = busy
        rep = sync_once(self.store, c, now=10_000)
        self.assertIn("retry", rep["skipped"])
        self.assertEqual(self.store.rows("SELECT COUNT(*) FROM edit_attempts WHERE synced=0")[0][0], 2)

    def test_recent_unenriched_attempts_wait(self):
        self.add(1)
        fake = FakeSupabase()
        rep = sync_once(self.store, self.client(fake), now=150.0)   # closed ~50 s ago, no key data joined yet
        self.assertEqual(rep["sent"], 0)

    def test_frames_stripped_without_frame_consent(self):
        r = record(frames=["a.jpg"])
        body = KeystrokeTrainerAdapter().payload("s", [r], {"consent_frames": False}, self.store)
        self.assertEqual(body["attempts"][0]["frames"], [])

    def test_errors_carry_status_for_jev_retry(self):
        c = self.client(lambda *a: (429, {"retry-after": "3"}, {"error": "slow down"}) if "/functions/" in a[1]
                        else FakeSupabase()(*a))
        with self.assertRaises(CloudError) as ctx:
            c.jev_post({"state": {}, "model": "jev-1.13.0", "questions": {"q": {}}})
        self.assertEqual(ctx.exception.code, 429)


class ContractTests(unittest.TestCase):
    def test_edge_function_uses_the_same_schema_file(self):
        self.assertTrue(filecmp.cmp(ROOT / "shared/schemas/edit_attempt.v1.json",
                                    ROOT / "supabase/functions/_shared/edit_attempt.v1.json", shallow=False))

    def test_migrations_expose_only_the_api_schema(self):
        config = (ROOT / "supabase/config.toml").read_text()
        self.assertIn('schemas = ["api"]', config)
        self.assertIn("enable_anonymous_sign_ins = true", config)
        sql = "\n".join(p.read_text() for p in sorted((ROOT / "supabase/migrations").glob("*.sql")))
        for table in ("core.players", "keystroke_trainer.attempts", "keystroke_trainer.labels"):
            self.assertIn(f"alter table {table} enable row level security", sql)
        self.assertNotIn("service_role_key", sql.lower())


if __name__ == "__main__":
    unittest.main()
