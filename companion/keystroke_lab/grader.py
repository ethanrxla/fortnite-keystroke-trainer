"""Grade recorded key presses against a drill (design doc 3.1 to 3.4).

Mirrors verse/KeystrokeTrainer/Tempo.verse; change both together.
"""

from dataclasses import dataclass, field
from statistics import pstdev

LADDER = [40, 60, 80, 100, 120, 150, 180, 220]
FREE = 0
PROMOTE_ACC = 0.95
DEMOTE_ACC = 0.80


def click_interval(apm):
    return 60.0 / apm if apm > 0 else 0.0


def companion_window(apm):
    """+/- 25% of the click interval, never tighter than 60 ms."""
    return max(0.25 * click_interval(apm), 0.060)


@dataclass
class StepGrade:
    expected: str
    pressed: str | None
    offset: float | None  # seconds, negative = early
    result: str  # ok | wrong_key | missing | late | early


@dataclass
class RepGrade:
    steps: list
    extra_keys: list = field(default_factory=list)

    @property
    def clean(self):
        return not self.extra_keys and all(s.result == "ok" for s in self.steps)


def grade_rep(expected_keys, presses, start, apm, watched_keys):
    """Grade one rep.

    expected_keys: keys in order, one per click.
    presses: [(timestamp_seconds, key)] the player pressed during the rep, any order.
    start: timestamp of the first click. Click i is at start + i * interval.
    watched_keys: build/edit keys; a press of one of these that matches no step is an extra key.
    """
    interval = click_interval(apm)
    window = companion_window(apm)
    remaining = sorted(p for p in presses if p[1] in watched_keys)
    steps = []
    for i, key in enumerate(expected_keys):
        click = start + i * interval
        # Nearest watched press to this click within half an interval belongs to this step.
        near = [p for p in remaining if abs(p[0] - click) <= max(interval / 2, window)]
        if not near:
            steps.append(StepGrade(key, None, None, "missing"))
            continue
        t, pressed = min(near, key=lambda p: (p[1] != key, abs(p[0] - click)))
        remaining.remove((t, pressed))
        offset = t - click
        if pressed != key:
            result = "wrong_key"
        elif offset < -window:
            result = "early"
        elif offset > window:
            result = "late"
        else:
            result = "ok"
        steps.append(StepGrade(key, pressed, offset, result))
    return RepGrade(steps, extra_keys=remaining)


@dataclass
class SetGrade:
    accuracy: float
    timing_spread_ms: float
    errors: dict


def grade_set(reps):
    clean = sum(r.clean for r in reps)
    offsets = [s.offset for r in reps for s in r.steps if s.offset is not None]
    errors = {}
    for r in reps:
        for s in r.steps:
            if s.result != "ok":
                errors[s.result] = errors.get(s.result, 0) + 1
        if r.extra_keys:
            errors["extra_key"] = errors.get("extra_key", 0) + len(r.extra_keys)
    spread = pstdev(offsets) * 1000 if len(offsets) > 1 else 0.0
    return SetGrade(clean / len(reps) if reps else 0.0, spread, errors)


def decide_tempo(recent_accuracies, recent_spreads_ms=None, apm=None):
    """recent_*: sets at the current tempo, oldest first. Spread gate applies in companion mode."""
    last3 = recent_accuracies[-3:]
    if len(last3) == 3 and all(a >= PROMOTE_ACC for a in last3):
        if recent_spreads_ms is None or apm in (None, FREE):
            return "promote"
        limit = 0.15 * click_interval(apm) * 1000
        if all(s < limit for s in recent_spreads_ms[-3:]):
            return "promote"
        return "hold"
    last2 = recent_accuracies[-2:]
    if len(last2) == 2 and all(a < DEMOTE_ACC for a in last2):
        return "demote"
    return "hold"


def step_tempo(current, decision):
    if current == FREE:
        return LADDER[-1] if decision == "demote" else FREE
    i = LADDER.index(current)
    if decision == "promote":
        return LADDER[i + 1] if i + 1 < len(LADDER) else FREE
    if decision == "demote":
        return LADDER[max(i - 1, 0)]
    return current
