"""Local player-data store (SQLite), kept on this PC only: companion/data/player.db (gitignored).

Everything is keyed on wall-clock UTC seconds, so data from different programs lines up without sharing a clock:
  keys      every key / mouse press the overlay judged while the game was focused (key name + verdict, no typed text)
  kt        every KT| line the map printed (read from the UEFN editor log): lock, gate, crosshair, step, set_start ...
  attempts  one row per edit the guide recommended, joined to what the player did next (see collector.correlate)
  edit_attempts  one row per edit attempt the overlay recorded (shared/schemas/edit_attempt.v1.json), with the full
                 record as JSON; `enriched` once confirm / reset key presses were joined, `synced` once uploaded
  labels    the user's review of an attempt: approved / rejected / relabelled (newest row wins)
  ingest    byte offsets of the files being tailed, so a restart never double-counts
Rows are deduplicated by unique keys, so re-reading a file is harmless.
"""

import json
import pathlib
import sqlite3

DB_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "player.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS keys(ts REAL, key TEXT, verdict TEXT, drill TEXT, src TEXT, UNIQUE(ts, key, src));
CREATE TABLE IF NOT EXISTS kt(ts REAL, event TEXT, drill TEXT, data TEXT, UNIQUE(ts, event, data));
CREATE TABLE IF NOT EXISTS attempts(
    lock_ts REAL PRIMARY KEY, face TEXT, edit_id TEXT, u_h INTEGER, v_h INTEGER, side INTEGER, far INTEGER,
    px INTEGER, py INTEGER, pz INTEGER, ax INTEGER, ay INTEGER, az INTEGER,
    edit_ts REAL, confirm_ts REAL, reset_ts REAL, travel_h INTEGER, ideal_h INTEGER);
CREATE TABLE IF NOT EXISTS ingest(path TEXT PRIMARY KEY, offset INTEGER);
CREATE TABLE IF NOT EXISTS edit_attempts(
    attempt_id TEXT PRIMARY KEY, session_id TEXT, t_open REAL, t_close REAL, piece TEXT, outcome TEXT,
    suggested TEXT, matched TEXT, record TEXT, enriched INTEGER DEFAULT 0, synced INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS labels(
    attempt_id TEXT, at REAL, status TEXT, edit_id TEXT, reviewer TEXT, note TEXT, synced INTEGER DEFAULT 0,
    PRIMARY KEY(attempt_id, at));
CREATE INDEX IF NOT EXISTS edit_attempts_open ON edit_attempts(t_open);
CREATE INDEX IF NOT EXISTS keys_ts ON keys(ts);
CREATE INDEX IF NOT EXISTS kt_ts ON kt(ts);
"""


class Store:
    def __init__(self, path=DB_FILE):
        if str(path) != ":memory:":
            pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        for table, columns in {
            "keys": {"session_id": "TEXT", "profile_id": "TEXT", "profile_revision": "INTEGER",
                     "edge": "TEXT DEFAULT 'down'"},
            "labels": {"result_confirmed": "INTEGER DEFAULT 0", "piece": "TEXT"},
        }.items():
            present = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            for name, declaration in columns.items():
                if name not in present:self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def add_key(self, ts, key, verdict, drill=None, src="overlay", session_id=None, profile_id=None, profile_revision=None, edge="down"):
        self.db.execute("INSERT OR IGNORE INTO keys(ts,key,verdict,drill,src,session_id,profile_id,profile_revision,edge) VALUES(?,?,?,?,?,?,?,?,?)",
                        (ts, key, verdict, drill, src, session_id, profile_id, profile_revision, edge))

    def add_kt(self, ts, rec):
        self.db.execute("INSERT OR IGNORE INTO kt VALUES(?,?,?,?)",
                        (ts, rec.get("event", ""), rec.get("drill_id", ""), json.dumps(rec, sort_keys=True)))

    def add_attempt(self, record):
        """Insert or replace one edit attempt (keyed by attempt_id, so a re-read file is harmless)."""
        self.db.execute("INSERT OR REPLACE INTO edit_attempts(attempt_id, session_id, t_open, t_close, piece, outcome, "
                        "suggested, matched, record, enriched, synced) VALUES(?,?,?,?,?,?,?,?,?,"
                        "COALESCE((SELECT enriched FROM edit_attempts WHERE attempt_id=?),0),"
                        "COALESCE((SELECT synced FROM edit_attempts WHERE attempt_id=?),0))",
                        (record["attempt_id"], record["session_id"], record["t_edit_open"], record["t_close"],
                         record["piece"], record["outcome"], record.get("suggested_edit_id"),
                         record.get("matched_edit_id"), json.dumps(record, sort_keys=True),
                         record["attempt_id"], record["attempt_id"]))

    def attempt(self, attempt_id):
        row = self.db.execute("SELECT record FROM edit_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def update_attempt(self, record, enriched=None):
        if record.get("schema") == "edit_attempt.v2":
            record = dict(record, record_revision=record.get("record_revision", 1) + 1)
        self.db.execute("UPDATE edit_attempts SET record=?, outcome=?, matched=?, synced=0" +
                        (", enriched=?" if enriched is not None else "") + " WHERE attempt_id=?",
                        (json.dumps(record, sort_keys=True), record["outcome"], record.get("matched_edit_id")) +
                        ((int(enriched),) if enriched is not None else ()) + (record["attempt_id"],))

    def add_label(self, attempt_id, status, edit_id=None, reviewer="local", note="", at=None, result_confirmed=False, piece=None):
        import time
        from .edit_dictionary import EditDictionary
        r = self.attempt(attempt_id)
        if not r or status not in ("approved", "rejected", "relabelled"):raise ValueError("Invalid attempt or review status")
        piece = piece or r["piece"]
        edit_id = edit_id or (r.get("matched_edit_id") if status == "approved" else None)
        edit = EditDictionary().all.get(edit_id) if edit_id else None
        if status == "relabelled" and not edit:raise ValueError("Relabel needs a known edit")
        if edit_id and (not edit or edit["piece"] != piece):raise ValueError("Edit does not belong to reviewed piece")
        if result_confirmed and (status == "rejected" or not edit):raise ValueError("Confirmed result needs a reviewed edit")
        self.db.execute("INSERT OR REPLACE INTO labels(attempt_id,at,status,edit_id,reviewer,note,synced,result_confirmed,piece) VALUES(?,?,?,?,?,?,0,?,?)",
                        (attempt_id, at if at is not None else time.time(), status, edit_id, reviewer, note, int(result_confirmed), piece))
        from .attempt_evidence import upgrade_record
        updated = upgrade_record(r)
        self.update_attempt(updated)  # a post-upload correction becomes pending again

    def label(self, attempt_id):
        row = self.db.execute("SELECT status, edit_id, reviewer, at, result_confirmed, piece FROM labels WHERE attempt_id=? ORDER BY at DESC LIMIT 1",
                              (attempt_id,)).fetchone()
        return dict(zip(("status", "edit_id", "reviewer", "at", "result_confirmed", "piece"), row)) if row else None

    def offset(self, path):
        row = self.db.execute("SELECT offset FROM ingest WHERE path=?", (str(path),)).fetchone()
        return row[0] if row else 0

    def set_offset(self, path, offset):
        self.db.execute("INSERT OR REPLACE INTO ingest VALUES(?,?)", (str(path), offset))

    def rows(self, sql, args=()):
        return self.db.execute(sql, args).fetchall()

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()
