"""Map adapters: the one place that knows how a map's local data becomes upload payloads.

Each map subclasses MapAdapter. The rest of the companion (sync, CLI) only calls the base-class methods, so a new map
plugs in by adding a subclass and its private database schema, without touching shared code. Raw rows never leave an
adapter; only payloads that match the shared schemas do.
"""
import json


class MapAdapter:
    map_id = None
    ingest_function = "ingest"

    def pending(self, store, limit, now):
        """Local records ready to upload: [(session_id, record), ...]."""
        raise NotImplementedError

    def payload(self, session_id, records, consent, store):
        """The JSON body for the ingest function."""
        raise NotImplementedError

    def mark(self, store, accepted, rejected):
        """Record upload results locally (accepted: synced; rejected: never retried)."""
        raise NotImplementedError


class KeystrokeTrainerAdapter(MapAdapter):
    map_id = "keystroke_trainer"
    SETTLE_SECONDS = 120.0      # upload an unenriched attempt anyway once its key data had time to arrive

    def __init__(self, client_version="companion"):
        self.client_version = client_version

    def pending(self, store, limit, now):
        rows = store.rows("SELECT session_id, record FROM edit_attempts WHERE synced=0 AND (enriched=1 OR t_close<?) "
                          "ORDER BY t_open LIMIT ?", (now - self.SETTLE_SECONDS, limit))
        return [(s, json.loads(r)) for s, r in rows]

    def payload(self, session_id, records, consent, store):
        out = []
        for r in records:
            r = dict(r, map_id=self.map_id)
            if not consent.get("consent_frames"):
                r["frames"] = []
            label = store.label(r["attempt_id"])
            if label:
                r["label_status"] = {"approved": "approved", "rejected": "rejected"}.get(label["status"], "relabelled")
            out.append(r)
        body = {"session_id": session_id, "client_version": self.client_version, "attempts": out}
        summary = self.key_summary(store, out)
        if summary:
            body["key_summary"] = summary
        return body

    def key_summary(self, store, records):
        """Counts only (verdict totals and per-key totals) over the attempts' time span: no order, no timing."""
        if not records:
            return None
        lo = min(r["t_edit_open"] for r in records) - 60
        hi = max(r["t_close"] for r in records) + 60
        verdicts = dict(store.rows("SELECT verdict, COUNT(*) FROM keys WHERE ts BETWEEN ? AND ? GROUP BY verdict", (lo, hi)))
        if not verdicts:
            return None
        keys = dict(store.rows("SELECT key, COUNT(*) FROM keys WHERE ts BETWEEN ? AND ? GROUP BY key", (lo, hi)))
        return {"verdicts": verdicts, "keys": keys}

    def mark(self, store, accepted, rejected):
        for attempt_id in accepted:
            store.db.execute("UPDATE edit_attempts SET synced=1 WHERE attempt_id=?", (attempt_id,))
        for attempt_id in rejected:
            store.db.execute("UPDATE edit_attempts SET synced=-1 WHERE attempt_id=?", (attempt_id,))
        store.commit()


ADAPTERS = {KeystrokeTrainerAdapter.map_id: KeystrokeTrainerAdapter}
