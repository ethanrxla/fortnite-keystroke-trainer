"""Turn keyboard-overlay recordings into plain advice: what you hit by accident, bounce, skip or do out of order.

    python -m keystroke_lab insights sessions/keys-*.events.jsonl [--binds keybinds.json]

Input is the <name>.events.jsonl file that `keys` writes (only presses made while a Fortnite window was focused).
Everything is counted, not guessed: a stray is a key outside your bind profile, a double is the same key twice
within 70 ms, an order error is a bound key that was not the drill's next step, and a miss is a rep that went quiet
before every step was pressed. Advice is a ranked list of the habits that cost you the most presses.
"""

import collections
import json
import pathlib

# What the overlay writes per key press. "repeat" is a held key auto-repeating (not a new press); "ai_tip" and "analysis"
# are overlay notes, not input. Counting those used to inflate presses by 2-3x in current recordings.
PRESS_KINDS = ("ok", "habit", "stray", "unmapped", "double", "order")
# Drill step results the island logs (Scoring.verse rep_result) that mean the step went wrong.
STEP_ERRORS = ("wrong_outcome", "misplaced", "missing", "late", "early", "exposed")
STEP_WORDS = {"wrong_outcome": "built or edited the wrong thing", "misplaced": "landed in the wrong place",
              "missing": "never happened", "late": "came too late", "early": "came too early",
              "exposed": "took damage while exposed"}


def load(paths):
    events = []
    for p in paths:
        for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


def summarize(events):
    kinds = collections.Counter(e["kind"] for e in events)
    presses = sum(v for k, v in kinds.items() if k in PRESS_KINDS)
    # An unmapped key is a stray: a key outside the bind profile (the overlay's current name for it).
    strays = collections.Counter(e["key"] for e in events if e["kind"] in ("stray", "unmapped"))
    doubles = collections.Counter(e["key"] for e in events if e["kind"] == "double")
    order = collections.Counter(e["key"] for e in events if e["kind"] == "order")
    missed = collections.Counter()
    missed_reps = collections.Counter()
    for e in events:
        if e["kind"] == "missed":
            missed_reps[e.get("drill") or "-"] += 1
            for a in e.get("actions", []):
                missed[(e.get("drill") or "-", a)] += 1
    return {"presses": presses, "held": kinds.get("repeat", 0), "kinds": dict(kinds), "strays": strays, "doubles": doubles, "order": order,
            "missed": missed, "missed_reps": missed_reps}


def step_failures(records):
    """Drill step failures from the island's KT| records (ktlog.parse_line dicts).

    Returns {(drill, step): {"graded": n, "errors": Counter(result)}} for every graded step (result other than
    unchecked), so a failure can be quoted against how often that step was attempted.
    """
    out = {}
    for r in records:
        if r.get("event") != "step" or r.get("result") in (None, "unchecked"):
            continue
        entry = out.setdefault((r.get("drill_id") or "-", r.get("step")), {"graded": 0, "errors": collections.Counter()})
        entry["graded"] += 1
        if r["result"] in STEP_ERRORS:
            entry["errors"][r["result"]] += 1
    return out


def step_advice(failures, top=4):
    """Ranked sentences for the steps that fail most often, with the failure rate."""
    rows = []
    for (drill, step), e in failures.items():
        for result, n in e["errors"].items():
            rows.append((n, n / e["graded"], drill, step, result, e["graded"]))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    return [(n, f"{drill} step {step} {STEP_WORDS.get(result, result)} {n} of {graded} times ({pct(n, graded)}).")
            for n, _, drill, step, result, graded in rows[:top]]


def pct(n, total):
    return f"{100.0 * n / total:.1f}%" if total else "0%"


def advice(summary, failures=None):
    """Ranked, specific sentences. Each cites the count it is based on."""
    out = step_advice(failures) if failures else []
    total = summary["presses"]
    for key, n in summary["strays"].most_common(3):
        out.append((n, f"'{key}' was pressed {n} times and is not one of your binds ({pct(n, total)} of presses): "
                       "unmapped in that recording; calibrate it before drawing conclusions."))
    for key, n in summary["doubles"].most_common(3):
        out.append((n, f"'{key}' had {n} recorded rapid-repeat flags. Timing alone does not establish an accident or hardware bounce."))
    for key, n in summary["order"].most_common(3):
        out.append((n, f"'{key}' came out of order {n} times: you pressed it when the drill expected another step."))
    for (drill, action), n in summary["missed"].most_common(3):
        out.append((n, f"In {drill}, '{action}' was not observed {n} times before the recording's idle boundary. "
                       "This does not prove a forgotten or dropped input."))
    return [text for _, text in sorted(out, key=lambda t: -t[0])]


def report(paths, kt_records=None):
    s = summarize(load(paths))
    held = f", {s['held']} held-key repeats not counted" if s["held"] else ""
    lines = [f"{s['presses']} presses recorded  ({s['kinds']}){held}"]
    failures = step_failures(kt_records or [])
    if failures:
        graded = sum(e["graded"] for e in failures.values())
        bad = sum(sum(e["errors"].values()) for e in failures.values())
        lines.append(f"{graded} graded drill steps from the island log, {bad} failed ({pct(bad, graded)})")
    advice_lines = advice(s, failures)
    lines += ["", "What to work on:"] + [f"  {i}. {t}" for i, t in enumerate(advice_lines, 1)] if advice_lines else \
             ["", "Nothing stands out yet: no strays, bounces, order errors or misses."]
    return "\n".join(lines)
