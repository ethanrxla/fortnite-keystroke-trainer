"""Collect player data independently of UEFN and join it into one local database.

    python -m keystroke_lab collect            # run the loop (stop with Ctrl+C); the autostart watcher runs it for you
    python -m keystroke_lab collect --once     # ingest what is there now, correlate, print a summary, exit
    python -m keystroke_lab data               # summary of what has been collected

Two sources, joined on wall-clock UTC time:
  * the overlay's recordings (companion/sessions/*.events.jsonl): every key and mouse press while the game was
    focused. This works with UEFN closed.
  * the KT| lines the map prints, read from the UEFN editor log: edit locks (face, recommended edit, aim point, your
    position vector and crosshair vector), the build-tool gate, crosshair travel, drill steps. Verse prints only on the
    island server, which runs inside UEFN, so these arrive only while a UEFN session is running; the Fortnite client
    log carries no KT| lines. Everything else here still works without it.

correlate() turns the two streams into `attempts`: for each edit the guide recommended, when you pressed edit, when you
confirmed, when you reset, and how far the crosshair travelled against the ideal. personalize.py hands those to Jev.
"""

import datetime
import json
import os
import pathlib
import re
import time

from . import drills, ktlog
from .keyboard_overlay import normal
from .store import Store

SESSIONS = pathlib.Path(__file__).resolve().parents[1] / "sessions"
LOG_TS = re.compile(r"^\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]")
EDIT_WINDOW = 8.0      # seconds after a lock in which an edit press counts as acting on it
CONFIRM_WINDOW = 4.0
RESET_WINDOW = 6.0
FINISH_WINDOW = 15.0


def log_ts(line):
    """Wall-clock UTC seconds from a UEFN log line prefix, or None."""
    m = LOG_TS.match(line)
    if not m:
        return None
    y, mo, d, h, mi, s, ms = (int(x) for x in m.groups())
    return datetime.datetime(y, mo, d, h, mi, s, tzinfo=datetime.timezone.utc).timestamp() + ms / 1000.0


def _read_new(store, path):
    """Complete new lines of a growing file since the stored offset (resets if the file was rotated)."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    size = path.stat().st_size
    offset = store.offset(path)
    if size < offset:
        offset = 0
    if size == offset:
        return []
    with path.open("rb") as f:
        f.seek(offset)
        chunk = f.read(size - offset)
    cut = chunk.rfind(b"\n")
    if cut < 0:
        return []                       # no complete line yet
    store.set_offset(path, offset + cut + 1)
    return chunk[:cut].decode("utf-8", "replace").splitlines()


def ingest_uefn_log(store, path=ktlog.DEFAULT_LOG):
    n = 0
    for line in _read_new(store, path):
        rec = ktlog.parse_line(line)
        ts = log_ts(line)
        if rec and ts:
            store.add_kt(ts, rec)
            n += 1
    return n


def ingest_overlay(store, folder=SESSIONS):
    n = 0
    for path in sorted(pathlib.Path(folder).glob("*.events.jsonl")) if pathlib.Path(folder).exists() else []:
        for line in _read_new(store, path):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if "ts" in e and "key" in e:
                store.add_key(e["ts"], e["key"], e["kind"], e.get("drill"), src=path.name,
                              session_id=e.get("session_id"), profile_id=e.get("profile_id"),
                              profile_revision=e.get("profile_revision"), edge=e.get("edge", "down"))
                n += 1
    return n


def _first(rows, keys, lo, hi):
    for ts, key in rows:
        if lo < ts <= hi and key in keys:
            return ts
    return None


def correlate(store, binds):
    """Join each edit the guide recommended (a `lock`) with the presses and the crosshair travel that followed it."""
    norm = {a: normal(k) for a, k in binds.items()}
    edit, confirm, reset = {norm.get("edit")}, {norm.get("edit_confirm")}, {norm.get("reset")}
    locks = store.rows("SELECT ts, data FROM kt WHERE event='lock' AND drill='edit_guide' ORDER BY ts")
    finishes = store.rows("SELECT ts, data FROM kt WHERE event='crosshair' AND drill='edit_guide' ORDER BY ts")
    done = 0
    for ts, raw in locks:
        d = json.loads(raw)
        keys = store.rows("SELECT ts, key FROM keys WHERE ts>? AND ts<=? ORDER BY ts", (ts, ts + EDIT_WINDOW + CONFIRM_WINDOW + RESET_WINDOW))
        edit_ts = _first(keys, edit, ts, ts + EDIT_WINDOW)
        confirm_ts = _first(keys, confirm, edit_ts, edit_ts + CONFIRM_WINDOW) if edit_ts else None
        reset_ts = _first(keys, reset, confirm_ts, confirm_ts + RESET_WINDOW) if confirm_ts else None
        travel = ideal = None
        for fts, fraw in finishes:
            f = json.loads(fraw)
            if ts < fts <= ts + FINISH_WINDOW and f.get("face") == d.get("face"):
                travel, ideal = int(f.get("travel_h", 0)), int(f.get("ideal_h", 0))
                break
        store.db.execute("INSERT OR REPLACE INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            ts, d.get("face"), d.get("edit"), int(d.get("u_h", 0)), int(d.get("v_h", 0)), int(d.get("side", 1)),
            int(d.get("far", 0)), int(d.get("px", 0)), int(d.get("py", 0)), int(d.get("pz", 0)),
            int(d.get("ax_h", 0)), int(d.get("ay_h", 0)), int(d.get("az_h", 0)), edit_ts, confirm_ts, reset_ts, travel, ideal))
        done += 1
    return done


def ingest_attempts(store, folder=SESSIONS):
    """Edit attempts from sessions/*.attempts.jsonl (written by the edit overlay's AttemptRecorder)."""
    from .attempt_schema import errors
    n = 0
    for path in sorted(pathlib.Path(folder).glob("*.attempts.jsonl")) if pathlib.Path(folder).exists() else []:
        for line in _read_new(store, path):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if errors(rec):
                continue            # never store a record the database would reject
            store.add_attempt(rec)
            n += 1
    return n


ENRICH_DELAY = 5.0      # seconds after an attempt closes before its key presses are joined (the key log lags)


def enrich_attempts(store, binds, now=None):
    """Join each closed attempt with the keyboard overlay's presses: the confirm and reset keys inside the attempt.

    The edit key often doubles as confirm (edit-on-release setups bind both to one key), so the press that opened the
    edit (within 0.15 s of the open) is skipped. A confirm press on a completed shape raises the auto-label confidence;
    a reset press after the last selection turns a 'completed' into 'reset' only if nothing was selected afterwards."""
    now = time.time() if now is None else now
    norm = {a: normal(k) for a, k in binds.items()}
    confirm, reset = {norm.get("edit_confirm")} - {None}, {norm.get("reset")} - {None}
    done = 0
    for (attempt_id,) in store.rows("SELECT attempt_id FROM edit_attempts WHERE enriched=0 AND t_close<?", (now - ENRICH_DELAY,)):
        rec = store.attempt(attempt_id)
        if rec.get("schema") == "edit_attempt.v2":
            if not rec.get("profile_id") or rec.get("profile_revision") is None:continue
            keys = store.rows("SELECT ts,key,edge FROM keys WHERE ts>? AND ts<=? AND session_id=? AND profile_id=? AND profile_revision=? AND verdict NOT IN ('repeat','unmapped') ORDER BY ts",
                              (rec["t_edit_open"], rec["t_close"]+.15, rec["session_id"], rec["profile_id"], rec["profile_revision"]))
            # Match the player's configured confirmation edge; a release is not assumed to confirm.
            edge = getattr(binds, "confirm_edge", "down")
            hits = [(t, e) for t,k,e in keys if k in confirm and e == edge and t > rec["t_edit_open"]+.15]
            if hits:
                rec["t_confirm"] = hits[-1][0]
                rec["confirmation_evidence"] = "release" if hits[-1][1] == "up" else "press"
                if rec["outcome"] == "selection_matched":rec["outcome"] = "confirm_observed"
            resets = [t for t,k,e in keys if k in reset and e == "down"]
            if resets:rec["t_reset"] = resets[-1]
            if keys or now - rec["t_close"] > 120:
                store.update_attempt(rec, enriched=True)
                done += 1
            continue
        keys = store.rows("SELECT ts, key FROM keys WHERE ts>? AND ts<=? ORDER BY ts",
                          (rec["t_edit_open"] + 0.15, rec["t_close"] + 0.5))
        if not keys and not store.rows("SELECT 1 FROM keys WHERE ts>? LIMIT 1", (rec["t_close"],)):
            continue            # no key data covering this attempt yet (overlay off, or not ingested): try later
        confirms = [t for t, k in keys if k in confirm]
        resets = [t for t, k in keys if k in reset]
        if confirms and rec.get("t_confirm") is None:
            rec["t_confirm"] = confirms[-1]
            if rec["outcome"] == "completed":
                rec["auto_label_confidence"] = round(min(0.97, rec["auto_label_confidence"] * 1.15), 3)
        if resets and rec.get("t_reset") is None:
            rec["t_reset"] = resets[-1]
        store.update_attempt(rec, enriched=True)
        done += 1
    return done


def summary(store):
    q = lambda sql: store.rows(sql)[0][0]
    return {
        "key_events": q("SELECT COUNT(*) FROM keys"),
        "stray_or_double": q("SELECT COUNT(*) FROM keys WHERE verdict IN ('stray','double','order')"),
        "kt_lines": q("SELECT COUNT(*) FROM kt"),
        "edit_locks": q("SELECT COUNT(*) FROM attempts"),
        "edits_pressed": q("SELECT COUNT(*) FROM attempts WHERE edit_ts IS NOT NULL"),
        "edits_confirmed": q("SELECT COUNT(*) FROM attempts WHERE confirm_ts IS NOT NULL"),
        "edit_attempts": q("SELECT COUNT(*) FROM edit_attempts"),
        "edit_attempts_completed": q("SELECT COUNT(*) FROM edit_attempts WHERE outcome='completed'"),
        "edit_attempts_reviewed": q("SELECT COUNT(DISTINCT attempt_id) FROM labels"),
    }


def cycle(store, binds, log_path=ktlog.DEFAULT_LOG, folder=SESSIONS):
    a, b = ingest_overlay(store, folder), ingest_uefn_log(store, log_path)
    c = correlate(store, binds) if (a or b) else 0
    ingest_attempts(store, folder)
    enrich_attempts(store, binds)
    store.commit()
    return a, b, c


def run(store=None, interval=2.0, log_path=ktlog.DEFAULT_LOG, folder=SESSIONS, stop=lambda: False, sleep=time.sleep):
    store = store or Store()
    binds = drills.load_binds()
    while not stop():
        cycle(store, binds, log_path, folder)
        sleep(interval)
    store.close()
