"""This session's numbers for the stats panel: observed input flags and edit-pattern results.

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
    # Unmapped means the bind profile cannot explain the key; it is not evidence that
    # the press was accidental. Keep it as a separate observation for the UI.
    strays = collections.Counter(e["key"] for e in events if e.get("kind") == "stray" and e.get("key"))
    unmapped = collections.Counter(e["key"] for e in events if e.get("kind") == "unmapped" and e.get("key"))
    doubles = collections.Counter(e["key"] for e in events if e.get("kind") == "double" and e.get("key"))
    marked_doubles = {(e.get("key"), e.get("t")) for e in events if e.get("kind") == "double" and e.get("key")}
    last = {}
    for e in events:
        if e.get("kind") not in ("ok", "unmapped", "habit") or not e.get("key") or not isinstance(e.get("t"), (int, float)):
            continue
        prev = last.get(e["key"])
        # Some overlay versions emit both the raw press and an explicit `double`
        # record. Do not count that same press a second time.
        if (prev is not None and 0 <= e["t"] - prev < DOUBLE_SECONDS
                and (e["key"], e["t"]) not in marked_doubles):
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
    # Only known stray events are candidates for interpretation. Unmapped presses
    # remain explicitly unresolved and are never called accidental.
    verdicts["unsure"] += max(0, sum(strays.values()) - judged)
    return {"strays": sum(strays.values()), "unmapped": sum(unmapped.values()), "doubles": sum(doubles.values()),
            "top_keys": [k for k, _ in (strays + unmapped + doubles).most_common(3)], "verdicts": dict(verdicts)}


RELEASE_MIN = 8            # edits with a selection needed before deciding the player edits on release
RELEASE_SHARE = 0.15       # below this share of edits with a confirm press, confirms must be happening on release


def _selected_edits(store, since=None):
    """(confirmed?) per joined edit attempt where tiles were selected and that was not deliberately reset."""
    sql = "SELECT record FROM edit_attempts WHERE enriched=1" + (" AND t_open >= ?" if since is not None else "")
    out = []
    for (raw,) in store.rows(sql, (since,) if since is not None else ()):
        r = json.loads(raw)
        if not r.get("final_tiles") and not r.get("selection_trace"):
            continue
        if r.get("t_reset") is not None and r.get("outcome") == "reset":
            continue                    # a reset is a deliberate cancel, not a missed confirm
        out.append(r.get("t_confirm") is not None)
    return out


def edits_on_release(store, setting=None):
    """True when the player's confirms happen on releasing the edit key (no second press to see). The setting wins
    (overlay-settings.json "edit_on_release"); otherwise judged from all their recorded edits: with enough of them and
    almost none showing a confirm press, the confirms must be releases. Too few edits: assume presses."""
    if setting is not None:
        return bool(setting)
    history = _selected_edits(store)
    return len(history) >= RELEASE_MIN and sum(history) / len(history) < RELEASE_SHARE


def edit_misses(store, since, binds=None, on_release=None):
    """Missed keystrokes in ordinary play: edits where tiles were selected but the edit closed without the confirm key.
    The collector joins each recorded edit with the overlay's presses; the press that opened the edit is skipped, so with
    edit and confirm on one key (C / C, common) the second press is the confirm and this works as with separate keys.
    Only edit-on-release can't be seen (the confirm is a key release, never logged): then the result says so instead of
    counting false misses."""
    if store is None or since is None:
        return None
    if edits_on_release(store, on_release):
        return {"drill": "edit", "step": "confirm", "missed": 0, "graded": 0, "release": True}
    session = _selected_edits(store, since)
    if not session:
        return None
    return {"drill": "edit", "step": "confirm", "missed": session.count(False), "graded": len(session)}


def missed(events, store, since, binds=None, on_release=None):
    """Missed keystrokes in ordinary play (edit_misses). Drill grading never feeds in: no KT|step results, no
    drill-mode `missed` reps; presses made while doing a drill count like any others, through the same edit records."""
    natural = edit_misses(store, since, binds, on_release)
    steps = [natural] if natural else []
    return {"steps": steps, "graded": sum(m["graded"] for m in steps), "missed": sum(m["missed"] for m in steps)}


def edits(store, since):
    """This session's observed edit selections: pattern match, elapsed time, suggestion following and route travel.
    A catalog match describes the observed selection only; it is not proof Fortnite accepted or applied the edit.
    Review labels count as in personalize.edit_stats: rejected attempts are skipped, a relabel names the edit made."""
    if store is None or since is None:
        return {"attempts": 0, "per_edit": []}
    per, followed, judged, ratios, done, total, times = {}, 0, 0, [], 0, 0, []
    for attempt_id, raw in store.rows("SELECT attempt_id, record FROM edit_attempts WHERE t_open >= ?", (since,)):
        label = store.label(attempt_id)
        if label and label["status"] == "rejected":
            continue
        r = json.loads(raw)
        if r.get("outcome") == "reset" or (not r.get("final_tiles") and not r.get("selection_trace")):
            continue                    # an intentional reset or no observed selection is not a pattern attempt
        made = label["edit_id"] if label and label["status"] == "relabelled" else r.get("matched_edit_id")
        edit_id = made or r.get("suggested_edit_id")
        if not edit_id:
            continue
        completed = r.get("outcome") == "completed" and made == edit_id
        total += 1
        done += completed
        if isinstance(r.get("t_close"), (int, float)) and isinstance(r.get("t_edit_open"), (int, float)):
            times.append(max(0.0, r["t_close"] - r["t_edit_open"]))
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


def snapshot(events, store, binds=None, on_release=None):
    since = session_start(events)
    return {"since": since, "accidental": accidental(events), "missed": missed(events, store, since, binds, on_release),
            "edits": edits(store, since), "tip": tip(events)}
