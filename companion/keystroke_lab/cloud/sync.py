"""Upload local edit attempts to Supabase, only with the player's consent, in batches, safe to retry.

    python -m keystroke_lab cloud sync           # once
    (the collector loop calls sync_once every SYNC_INTERVAL seconds when the cloud is configured and consented)

Nothing is sent unless api.me() says consent_upload is true. Attempt ids make every upload idempotent: a batch that
times out is simply sent again. Records the server rejects are marked locally and never retried.
"""
import time

from .adapters import KeystrokeTrainerAdapter
from .client import CloudError

BATCH = 50
SYNC_INTERVAL = 60.0


def consent(client):
    me = client.rpc("me")
    return me if isinstance(me, dict) and me.get("id") else {}


def sync_once(store, client, adapter=None, now=None, batch=BATCH, max_batches=20):
    adapter = adapter or KeystrokeTrainerAdapter()
    now = time.time() if now is None else now
    report = {"sent": 0, "accepted": 0, "rejected": 0, "skipped": None}
    if not client.configured:
        report["skipped"] = "not configured"
        return report
    me = consent(client)
    if not me.get("consent_upload"):
        report["skipped"] = "no upload consent"
        return report
    for _ in range(max_batches):
        pending = adapter.pending(store, batch, now)
        if not pending:
            break
        by_session = {}
        for session_id, record in pending:
            by_session.setdefault(session_id, []).append(record)
        for session_id, records in by_session.items():
            me = consent(client)
            if not me.get("consent_upload"):
                report["skipped"] = "upload consent withdrawn"
                return report
            body = adapter.payload(session_id, records, me, store)
            report["sent"] += len(records)
            try:
                reply = client.function(adapter.ingest_function, body)
            except CloudError as exc:
                if exc.code in (429, 503) or exc.code >= 500 or exc.code == 0:
                    report["skipped"] = f"server busy ({exc.code}); will retry"
                    return report
                raise
            accepted = list(reply.get("accepted") or [])
            rejected = [r.get("attempt_id") for r in (reply.get("rejected") or []) if r.get("attempt_id")]
            adapter.mark(store, accepted, rejected)
            report["accepted"] += len(accepted)
            report["rejected"] += len(rejected)
    return report
