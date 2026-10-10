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

    def add_key(self, ts, key, verdict, drill=None, src="overlay"):
        self.db.execute("INSERT OR IGNORE INTO keys VALUES(?,?,?,?,?)", (ts, key, verdict, drill, src))

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
        self.db.execute("UPDATE edit_attempts SET record=?, outcome=?, matched=?, synced=0" +
                        (", enriched=?" if enriched is not None else "") + " WHERE attempt_id=?",
                        (json.dumps(record, sort_keys=True), record["outcome"], record.get("matched_edit_id")) +
                        ((int(enriched),) if enriched is not None else ()) + (record["attempt_id"],))

    def add_label(self, attempt_id, status, edit_id=None, reviewer="local", note="", at=None):
        import time
        self.db.execute("INSERT OR REPLACE INTO labels VALUES(?,?,?,?,?,?,0)",
                        (attempt_id, at if at is not None else time.time(), status, edit_id, reviewer, note))

    def label(self, attempt_id):
        row = self.db.execute("SELECT status, edit_id, reviewer, at FROM labels WHERE attempt_id=? ORDER BY at DESC LIMIT 1",
                              (attempt_id,)).fetchone()
        return dict(zip(("status", "edit_id", "reviewer", "at"), row)) if row else None

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
