"""Personal edit factors: how well YOU execute each edit, judged by Jev from your collected attempts.

    python -m keystroke_lab personalize          # writes shared/edit-policy-personal.json
    python tools/build_edit_policy.py --regen-verse --personal      # bake the factors into the in-game table

collector.py joins your key presses with the map's edit locks into `attempts`. This module summarises each edit
(how often you pressed edit and confirmed, how long confirming took, how close the crosshair travel was to the ideal),
asks Jev to rate each as strong / average / weak with calibrated probabilities, and turns that into a bounded
multiplier per edit (0.7 .. 1.3). Edits with fewer than MIN_ATTEMPTS attempts stay at 1.0: no data, no opinion.

The general table stays mirror-symmetric and unbiased; the personal factors are a separate, clearly labelled layer that
reflects this player (for example, someone who executes left-side peeks far better than right-side ones).
"""

import json
import pathlib
import statistics
import time

from .jev_client import JevClient, choice_question
from .store import Store

PERSONAL_JSON = pathlib.Path(__file__).resolve().parents[2] / "shared" / "edit-policy-personal.json"
MIN_ATTEMPTS = 5
SPREAD = 0.3          # factor = 1 + SPREAD * (P(strong) - P(weak)), clipped to 1 +- SPREAD
RATINGS = {
    "strong": "executes this edit quickly, cleanly and with little crosshair travel",
    "average": "executes this edit acceptably but not notably well or badly",
    "weak": "often fails to complete this edit, is slow, or moves the crosshair far more than needed",
}


def edit_stats(store):
    """Per edit: attempts acted on, completion rate, median seconds from edit to confirm, mean travel efficiency."""
    out = {}
    for edit_id in [r[0] for r in store.rows("SELECT DISTINCT edit_id FROM attempts WHERE edit_id IS NOT NULL")]:
        rows = store.rows("SELECT edit_ts, confirm_ts, travel_h, ideal_h FROM attempts WHERE edit_id=? AND edit_ts IS NOT NULL", (edit_id,))
        if not rows:
            continue
        done = [r for r in rows if r[1] is not None]
        times = [r[1] - r[0] for r in done]
        eff = [min(1.0, r[3] / r[2]) for r in rows if r[2] and r[2] > 0 and r[3] is not None]
        out[edit_id] = {
            "attempts": len(rows),
            "completed_pct": round(100.0 * len(done) / len(rows)),
            "median_confirm_s": round(statistics.median(times), 2) if times else None,
            "travel_efficiency_pct": round(100.0 * statistics.mean(eff)) if eff else None,
        }
    return out


def describe(edit_id, s):
    return (f"Edit '{edit_id}': {s['attempts']} attempts, {s['completed_pct']}% completed, median "
            f"{s['median_confirm_s']} s from edit to confirm, crosshair travel efficiency {s['travel_efficiency_pct']}% "
            f"(100% = perfectly efficient).")


def factors(stats, jev=None):
    """{edit_id: factor}. Uses one batched Jev call; falls back to 1.0 for everything if Jev is unavailable."""
    jev = jev if jev is not None else JevClient()
    result = {e: 1.0 for e in stats}
    todo = [e for e, s in stats.items() if s["attempts"] >= MIN_ATTEMPTS]
    if not todo or not jev.available:
        return result
    questions = {f"e{i}": choice_question(
        "Rate how well this Fortnite player executes the edit described. " + describe(e, stats[e]), RATINGS)
        for i, e in enumerate(todo)}
    answers = jev.decide({"task": "rate edit execution"}, questions) or {}
    for i, e in enumerate(todo):
        probs = (answers.get(f"e{i}") or {}).get("probabilities")
        if probs:
            result[e] = round(max(1 - SPREAD, min(1 + SPREAD, 1 + SPREAD * (probs.get("strong", 0.0) - probs.get("weak", 0.0)))), 3)
    return result


def run(store=None, jev=None, out=PERSONAL_JSON):
    store = store or Store()
    stats = edit_stats(store)
    f = factors(stats, jev)
    out = pathlib.Path(out)
    out.write_text(json.dumps({"generated": int(time.time()), "min_attempts": MIN_ATTEMPTS, "factors": f,
                               "stats": stats}, indent=1), encoding="utf-8")
    return stats, f


def apply_to_policy(policy, ids, personal):
    """Multiply each edit's prior by its personal factor and renormalise (floor kept). policy: {situation: [p...]}."""
    fac = [personal.get(i, 1.0) for i in ids]
    out = {}
    for s, vec in policy.items():
        scaled = [p * f for p, f in zip(vec, fac)]
        total = sum(scaled) or 1.0
        out[s] = [max(v / total, 0.02) for v in scaled]
        t2 = sum(out[s])
        out[s] = [v / t2 for v in out[s]]
    return out
