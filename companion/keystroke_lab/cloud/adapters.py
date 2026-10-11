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
        self.sent_revisions = {}

    def pending(self, store, limit, now):
        rows = store.rows("SELECT session_id, record FROM edit_attempts WHERE synced=0 AND (enriched=1 OR t_close<?) "
                          "ORDER BY t_open LIMIT ?", (now - self.SETTLE_SECONDS, limit))
        return [(s, json.loads(r)) for s, r in rows]

    def payload(self, session_id, records, consent, store):
        out = []
        for r in records:
            r = dict(r, map_id=self.map_id)
            self.sent_revisions[r["attempt_id"]] = r.get("record_revision", 1)
            # A compact summary is the upload boundary, not the local replay.
            r["frames"] = []
            r.pop("aim_trace", None)
            r.pop("selection_trace", None)
            r.pop("gesture_trace", None)
            r.pop("profile_id", None)
            if r.get("context"):
                r["context"] = {k:v for k,v in r["context"].items() if k not in ("camera","body")}
            label = store.label(r["attempt_id"])
            if label:
                r["label_status"] = {"approved": "approved", "rejected": "rejected"}.get(label["status"], "relabelled")
                if r.get("schema") == "edit_attempt.v2":
                    r.update(reviewed_edit_id=label.get("edit_id"), review_result_confirmed=bool(label.get("result_confirmed")),
                             reviewed_piece=label.get("piece") or r["piece"], review_revision=label["at"])
            out.append(r)
        body = {"session_id": session_id, "client_version": self.client_version, "attempts": out}
        summary = self.key_summary(store, out)
        if summary:
            body["key_summary"] = summary
        return body

    def key_summary(self, store, records):
        """Anonymous verdict totals within this session and attempt span."""
        if not records:
            return None
        lo = min(r["t_edit_open"] for r in records)
        hi = max(r["t_close"] for r in records)
        verdicts = dict(store.rows("SELECT verdict, COUNT(*) FROM keys WHERE ts BETWEEN ? AND ? AND session_id=? GROUP BY verdict",
                                  (lo, hi, records[0]["session_id"])))
        verdicts={k:v for k,v in verdicts.items() if k in {'ok','order','stray','double','unmapped','repeat','release','habit'}}
        if not verdicts:
            return None
        return {"verdicts": verdicts}

    def mark(self, store, accepted, rejected):
        for attempt_id in accepted:
            store.db.execute("UPDATE edit_attempts SET synced=1 WHERE attempt_id=? AND COALESCE(json_extract(record,'$.record_revision'),1)=?",
                             (attempt_id,self.sent_revisions.get(attempt_id,1)))
        for attempt_id in rejected:
            store.db.execute("UPDATE edit_attempts SET synced=-1 WHERE attempt_id=? AND COALESCE(json_extract(record,'$.record_revision'),1)=?",
                             (attempt_id,self.sent_revisions.get(attempt_id,1)))
        store.commit()


ADAPTERS = {KeystrokeTrainerAdapter.map_id: KeystrokeTrainerAdapter}
