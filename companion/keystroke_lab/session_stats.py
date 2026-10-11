"""This session's numbers for the stats panel: missed keystrokes, accidental presses (with Jev's verdict) and edit accuracy.

Pure and read-only: it reads what already exists and changes nothing.
  * the newest sessions/keys-*.events.jsonl the keyboard overlay writes (presses, Jev `analysis` records, `ai_tip` lines);
  * the player store (companion/data/player.db) the collector fills: the recorded edit attempts (`edit_attempts`, joined
    with the overlay's confirm / reset presses, with review labels).
Regular gameplay only: nothing a drill grades or emits (KT|step results, drill-mode `missed` / `order` verdicts) is
used; presses made during a drill count like any others.
The session starts at the first wall-clock `ts` in that events file (the overlay starts a new file per launch).
"""

import collections
import json
import pathlib
import statistics

from .keyboard_overlay import DOUBLE_SECONDS

SESSIONS = pathlib.Path(__file__).resolve().parents[1] / "sessions"
MIN_CONFIDENCE = 0.8          # as analysis.MIN_CONFIDENCE: a Jev verdict below this counts as unsure
MIN_ATTEMPTS = 5              # as personalize.MIN_ATTEMPTS: fewer attempts than this is "needs data"
VERDICTS = ("slip", "deliberate", "noise", "unsure")


def newest_events(folder=SESSIONS):
    files = sorted(pathlib.Path(folder).glob("*.events.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def read_events(path):
    """Events of one file; a half-written last line (the overlay is appending) is skipped, not fatal."""
    out = []
    if path is None or not pathlib.Path(path).is_file():
        return out
    for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def session_start(events):
    stamps = [e["ts"] for e in events if isinstance(e.get("ts"), (int, float))]
    return min(stamps) if stamps else None


def accidental(events):
    """Strays (keys outside the bind profile), doubles (one key twice within DOUBLE_SECONDS; a held key's auto-repeat
    is reported as `repeat` and never counts) and Jev's verdicts on the strays."""
    strays = collections.Counter(e["key"] for e in events if e.get("kind") in ("stray", "unmapped") and e.get("key"))
    doubles = collections.Counter(e["key"] for e in events if e.get("kind") == "double" and e.get("key"))
    last = {}
    for e in events:
        if e.get("kind") not in ("ok", "unmapped", "habit") or not e.get("key") or not isinstance(e.get("t"), (int, float)):
            continue
        prev = last.get(e["key"])
        if prev is not None and 0 <= e["t"] - prev < DOUBLE_SECONDS:
            doubles[e["key"]] += 1
        last[e["key"]] = e["t"]
    verdicts = collections.Counter({v: 0 for v in VERDICTS})
    for e in events:
        if e.get("kind") != "analysis":
            continue
        for f in e.get("findings") or []:
            intent = f.get("intent")
            sure = (isinstance(f.get("confidence"), (int, float)) and f["confidence"] >= MIN_CONFIDENCE
                    and not f.get("uncertainty", True) and intent in VERDICTS[:3])
            verdicts[intent if sure else "unsure"] += 1
    judged = sum(verdicts.values())
    # Strays Jev has not looked at yet are unsure too, so the bar always covers every stray.
    verdicts["unsure"] += max(0, sum(strays.values()) - judged)
    return {"strays": sum(strays.values()), "doubles": sum(doubles.values()),
            "top_keys": [k for k, _ in (strays + doubles).most_common(3)], "verdicts": dict(verdicts)}


def edit_misses(store, since, binds=None):
    """Missed keystrokes in ordinary play, no drill needed: edits where tiles were selected but the edit closed without
    the confirm key (the collector joins each recorded edit with the overlay's confirm / reset presses; only joined
    attempts count). With edit and confirm on one key (edit-on-release setups) a confirm cannot be told apart from the
    press that opened the edit, so the measure is skipped rather than guessed."""
    if store is None or since is None:
        return None
    if binds:
        from .keyboard_overlay import normal
        if binds.get("edit") and normal(binds.get("edit")) == normal(binds.get("edit_confirm", "")):
            return None
    selected, unconfirmed = 0, 0
    for (raw,) in store.rows("SELECT record FROM edit_attempts WHERE enriched=1 AND t_open >= ?", (since,)):
        r = json.loads(raw)
        if not r.get("final_tiles") and not r.get("selection_trace"):
            continue
        if r.get("t_reset") is not None and r.get("outcome") == "reset":
            continue                    # a reset is a deliberate cancel, not a missed confirm
        selected += 1
        unconfirmed += r.get("t_confirm") is None
    return {"drill": "edit", "step": "confirm", "missed": unconfirmed, "graded": selected} if selected else None


def missed(events, store, since, binds=None):
    """Missed keystrokes in ordinary play (edit_misses). Drill grading never feeds in: no KT|step results, no
    drill-mode `missed` reps; presses made while doing a drill count like any others, through the same edit records."""
    natural = edit_misses(store, since, binds)
    steps = [natural] if natural else []
    return {"steps": steps, "graded": sum(m["graded"] for m in steps), "missed": sum(m["missed"] for m in steps)}


def edits(store, since):
    """This session's edit attempts: completion, median open-to-close time, how often the guide's suggestion was
    followed, and crosshair travel against the ranker's ideal for the edit made. Review labels count as in
    personalize.edit_stats: rejected attempts are skipped, a relabel names the edit made."""
    if store is None or since is None:
        return {"attempts": 0, "per_edit": []}
    per, followed, judged, ratios, done, total, times = {}, 0, 0, [], 0, 0, []
    for attempt_id, raw in store.rows("SELECT attempt_id, record FROM edit_attempts WHERE t_open >= ?", (since,)):
        label = store.label(attempt_id)
        if label and label["status"] == "rejected":
            continue
        r = json.loads(raw)
        made = label["edit_id"] if label and label["status"] == "relabelled" else r.get("matched_edit_id")
        edit_id = made or r.get("suggested_edit_id")
        if not edit_id:
            continue
        completed = r.get("outcome") == "completed" and made == edit_id
        total += 1
        done += completed
        times.append(r["t_close"] - r["t_edit_open"])
        if r.get("followed_suggestion") is not None:
            judged += 1
            followed += bool(r["followed_suggestion"])
        ideal = next((p.get("travel") for p in r.get("picks") or [] if p.get("id") == made), None)
        if completed and isinstance(r.get("travel"), (int, float)) and isinstance(ideal, (int, float)) and ideal > 0:
            ratios.append(r["travel"] / ideal)
        e = per.setdefault(edit_id, {"edit": edit_id, "attempts": 0, "done": 0})
        e["attempts"] += 1
        e["done"] += completed
    rows = []
    for e in sorted(per.values(), key=lambda e: -e["attempts"])[:3]:
        rows.append({"edit": e["edit"], "attempts": e["attempts"], "enough": e["attempts"] >= MIN_ATTEMPTS,
                     "completed_pct": round(100.0 * e["done"] / e["attempts"])})
    return {"attempts": total,
            "completed_pct": round(100.0 * done / total) if total else None,
            "median_s": round(statistics.median(times), 2) if times else None,
            "followed_pct": round(100.0 * followed / judged) if judged else None,
            "travel_vs_ideal": round(statistics.median(ratios), 2) if ratios else None,
            "per_edit": rows}


def tip(events):
    """The newest coach tip the overlay wrote (Jev finding worded by the LLM, or its template); empty when AI is off."""
    for e in reversed(events):
        if e.get("kind") == "ai_tip" and e.get("text"):
            return e["text"]
    return ""


def snapshot(events, store, binds=None):
    since = session_start(events)
    return {"since": since, "accidental": accidental(events), "missed": missed(events, store, since, binds),
            "edits": edits(store, since), "tip": tip(events)}
