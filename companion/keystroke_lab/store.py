"""Local player-data store (SQLite), kept on this PC only: companion/data/player.db (gitignored).

Everything is keyed on wall-clock UTC seconds, so data from different programs lines up without sharing a clock:
  keys      every key / mouse press the overlay judged while the game was focused (key name + verdict, no typed text)
  kt        every KT| line the map printed (read from the UEFN editor log): lock, gate, crosshair, step, set_start ...
  attempts  one row per edit the guide recommended, joined to what the player did next (see collector.correlate)
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
