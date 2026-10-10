"""Turn recorded play into a personal training plan.

Pure logic, no devices and no network, so it can be tested with made-up events.

Flow:  recorded events -> actions -> builds (bursts) -> best-matching drill -> per-player stats
       -> weakness score per drill -> a short plan that follows the 5 / 5 / 5 warm-up shape
       (edits, building combos, fight practice) at a tempo the player can actually keep clean.

Events are dicts {"t": seconds, "kind": "key" | "flick", "name": ...}. Only keys in the player's
bind profile are ever recorded (recorder.py drops everything else), so no typing is captured.
Nothing here reads game memory or injects input.
"""

import statistics
from collections import defaultdict

from . import drills

# A pause longer than this ends a build. Fast players chain pieces well under half a second apart.
BUILD_GAP = 0.6
# Mouse flicks (a fast sideways camera move) count as a turn: that is what a 90 is made of.
FLICK_ACTION = "turn_right"
MIN_BUILD_ACTIONS = 2
# Cap on how different a build may be from a drill (edit distance, in actions) and still count as it.
MAX_DISTANCE = 2

BLOCKS = [("edits", "E"), ("building combos", "P"), ("fight practice", "W")]


DRILL_ACTIONS = {"wall", "floor", "ramp", "cone", "edit", "edit_confirm", "reset", "jump", "crouch", "fire",
                 "swap_weapon", "pickaxe"}


def to_actions(events, binds):
    """[(t, action)] from raw events. A mouse click is edit_confirm right after an edit, otherwise fire."""
    inverse = {}
    entries = ((b.action, key) for b in binds.profile.bindings if b.verified for key in b.keys) if hasattr(binds, "profile") else binds.items()
    for action, key in entries:
        # Only the actions drills are made of; movement, hotbar and ui keys must not shadow them.
        if action in DRILL_ACTIONS:
            inverse.setdefault(key, []).append(action)
    out = []
    for e in sorted(events, key=lambda e: e["t"]):
        if e["kind"] == "flick":
            out.append((e["t"], FLICK_ACTION))
            continue
        options = inverse.get(e["name"], [])
        if not options:
            continue
        if hasattr(binds, "profile") and len(set(options)) > 1:
            # A passive recording has no reliable game context; do not choose an action arbitrarily.
            continue
        if e["name"] == "mouse_left":
            recent_edit = out and out[-1][1] == "edit" and e["t"] - out[-1][0] < 1.5
            out.append((e["t"], "edit_confirm" if recent_edit else "fire"))
        else:
            out.append((e["t"], options[0]))
    return out


def segment(actions, gap=BUILD_GAP):
    builds, cur = [], []
    for t, a in actions:
        if cur and t - cur[-1][0] > gap:
            builds.append(cur)
            cur = []
        cur.append((t, a))
    if cur:
        builds.append(cur)
    return [b for b in builds if len(b) >= MIN_BUILD_ACTIONS]


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def drill_distance(seq, drill):
    """Distance to the closest accepted order: the reference steps or any listed alternative."""
    return min(edit_distance(seq, order) for order in [drill.steps] + list(drill.accepts))


def classify(build, catalog):
    """(drill_id, distance) of the closest drill, or (None, None) when nothing is close enough.
    A build that matches an accepted alternative exactly counts as clean (distance 0)."""
    seq = [a for _, a in build]
    best = (None, None)
    for d in catalog.values():
        dist = drill_distance(seq, d)
        if dist <= MAX_DISTANCE and (best[1] is None or dist < best[1] or (dist == best[1] and len(d.steps) > len(catalog[best[0]].steps))):
            best = (d.id, dist)
    return best


def analyze(events, binds, catalog):
    """Per-drill stats from one or more sessions' events (pass them concatenated, each already time-ordered)."""
    stats = defaultdict(lambda: {"builds": 0, "clean": 0, "durations": [], "gaps": defaultdict(list)})
    for build in segment(to_actions(events, binds)):
        did, dist = classify(build, catalog)
        if did is None:
            continue
        s = stats[did]
        s["builds"] += 1
        s["clean"] += dist == 0
        s["durations"].append(build[-1][0] - build[0][0])
        for (t0, a0), (t1, a1) in zip(build, build[1:]):
            s["gaps"][f"{a0}>{a1}"].append(t1 - t0)
    out = {}
    for did, s in stats.items():
        gaps = [g for v in s["gaps"].values() for g in v]
        out[did] = {
            "builds": s["builds"],
            "clean_rate": s["clean"] / s["builds"],
            "mean_gap": statistics.mean(gaps) if gaps else 0.0,
            "gap_spread": statistics.pstdev(gaps) if len(gaps) > 1 else 0.0,
            "mean_duration": statistics.mean(s["durations"]),
            "slowest_transition": max(((k, statistics.mean(v)) for k, v in s["gaps"].items() if v), key=lambda kv: kv[1], default=(None, 0.0)),
        }
    return out


def measured_apm(stat):
    """Actions per minute the player really produced (one action per mean gap)."""
    return 60.0 / stat["mean_gap"] if stat["mean_gap"] > 0 else 0.0


def weakness(stats):
    """drill_id -> 0..1, higher means needs more work. Mixes mistakes, slowness and uneven rhythm."""
    if not stats:
        return {}
    gaps = [s["mean_gap"] for s in stats.values() if s["mean_gap"] > 0]
    median_gap = statistics.median(gaps) if gaps else 1.0
    out = {}
    for did, s in stats.items():
        slow = min(max(s["mean_gap"] / median_gap - 1.0, 0.0), 1.0) if median_gap else 0.0
        uneven = min(s["gap_spread"] / s["mean_gap"], 1.0) if s["mean_gap"] else 0.0
        confidence = min(s["builds"] / 10.0, 1.0)  # a handful of builds should not swing the plan
        out[did] = round(confidence * (0.55 * (1 - s["clean_rate"]) + 0.25 * slow + 0.20 * uneven), 4)
    return out


def next_tempo(stat, ladder):
    """Slow first: start at the highest ladder rung at or below 70% of the speed the player showed, move up
    one rung only when their builds were almost always clean, and drop one or two rungs when they were not
    (so a player who is slipping is never sent faster)."""
    base = measured_apm(stat) * 0.7
    rungs = [r for r in ladder if r <= base]
    idx = len(rungs) - 1 if rungs else 0
    if stat["clean_rate"] >= 0.95 and idx + 1 < len(ladder):
        idx += 1
    elif stat["clean_rate"] < 0.5:
        idx -= 2      # slipping on most builds: speed is not the problem, so go clearly slower
    elif stat["clean_rate"] < 0.8:
        idx -= 1
    return ladder[max(idx, 0)]


def plan(stats, catalog, minutes=15, recent=()):
    """A short session: minutes split evenly over edits, building combos and fight practice.

    Drills with no recorded builds are treated as moderately weak (0.5) so a new player gets a broad
    first plan. Drills practised in `recent` (ids, most recent last) are down-weighted so the plan rotates.
    """
    ladder = drills.load_catalog()[0]
    scores = weakness(stats)
    per_block = max(1, minutes // len(BLOCKS))
    blocks = []
    for name, prefix in BLOCKS:
        pool = [d for d in catalog.values() if d.code.startswith(prefix)]
        ranked = sorted(pool, key=lambda d: scores.get(d.id, 0.5) * (0.6 if d.id in recent else 1.0), reverse=True)
        picks = ranked[:2]
        items = []
        for d in picks:
            st = stats.get(d.id)
            items.append({
                "drill": d.id, "code": d.code, "name": d.name,
                "tempo": next_tempo(st, ladder) if st else ladder[0],
                "why": ("no recorded builds yet, start slow" if not st else
                        f"{st['clean_rate']:.0%} clean, slowest step {st['slowest_transition'][0]}"),
                "principle": d.principle,
            })
        blocks.append({"block": name, "minutes": per_block, "drills": items})
    return {"minutes": per_block * len(BLOCKS), "blocks": blocks}
