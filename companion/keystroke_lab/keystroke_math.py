"""Keystroke accuracy by arithmetic: per-press labels, drill-step matching against the map's KT|step lines, timing
baselines and the "fix next" line. Pure: no I/O, no network, no Tk. Jev is asked only about what this module marks
`ambiguous` (see jev_keystrokes.py); the LLM only rewords `summary()` output.

Times are wall-clock UTC seconds (the overlay's event `ts`, the editor log's line prefix via collector.log_ts).

Why some labels from generic "keystroke accuracy" designs are absent:
  * dropped input / rollover loss: a Windows keyboard hook only sees keys the keyboard sent; a ghosted key never
    reaches the OS, so it cannot be observed. A step the map expected with no key pressed is `missing`.
  * early / late release: Fortnite acts on press (edit confirm-on-release aside), so timing is press time.
  * wrong target: aim, graded by the map from outcomes, not by keys.
"""

import collections
import statistics

from .keyboard_overlay import KEY_POS, neighbours, normal
from .typing_detector import TypingDetector  # noqa: F401  (re-exported)

DOUBLE_S = 0.07                 # same key twice this close, not auto-repeat: a bounce or an accident
SELF_CORRECT_S = 0.40           # a wrong key followed by the expected key this soon after is a finger slip
LONE_MODIFIER_S = 0.40          # Alt / Ctrl pressed and released alone this fast is an accidental tap
STEP_LOOKBACK_S = 0.35          # a step's key can land this long before the map's beat
CLOCK_SAMPLES = 20              # log-delay estimate: median over this many matched steps
BASELINE_SAMPLES = 20           # timing baseline (median / MAD) over this many clean steps
DRIFT_MADS = 2.0                # an offset this many MADs from the baseline is drift
MODIFIERS = {"caps_lock": "Caps Lock", "alt_l": "Alt", "ctrl_l": "Ctrl", "cmd": "Windows", "cmd_l": "Windows",
             "cmd_r": "Windows", "windows": "Windows"}
OUTCOMES = ("clean", "early", "late", "wrong_key", "slip", "missing", "extra")
# Two fast presses of a bound key are logged (`double`) but are not a miss: a deliberate double tap is legitimate.
CAUSES = ("wrong_key", "slip", "early", "late", "missing", "modifier", "unmapped")


def key_distance(a, b):
    """Physical distance in key units on the drawn layout, or None for keys off the layout (mouse, wheel)."""
    pa, pb = KEY_POS.get(normal(a)), KEY_POS.get(normal(b))
    if not pa or not pb or a.startswith("mouse_") or b.startswith("mouse_"):
        return None
    return round(((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5, 2)


class PressLabeler:
    """Per-press labels that need no plan: ok | unmapped | unverified | double | modifier | repeat.

    `bound` maps key -> set of verified actions; `known` is every key in the profile (verified or not)."""

    def __init__(self, bound, known=None):
        self.bound = {normal(k): set(v) for k, v in bound.items()}
        self.known = {normal(k) for k in (known or bound)}
        self.last = {}
        self.held = {}
        self.others_during = {}

    def press(self, key, t):
        key = normal(key)
        if key in self.held:
            return "repeat"
        for k in self.held:
            self.others_during[k] = True
        self.held[key] = t
        self.others_during[key] = False
        prev, self.last[key] = self.last.get(key), t
        if prev is not None and 0 <= t - prev < DOUBLE_S:
            return "double"
        if key in MODIFIERS and key not in self.known:
            return "modifier"
        if key not in self.known:
            return "unmapped"
        if not self.bound.get(key):
            return "unverified"
        return "ok"

    def release(self, key, t):
        """'modifier' when a bound Alt/Ctrl was tapped alone and fast (alt-tab reflex, a brushed Ctrl), else None."""
        key = normal(key)
        start = self.held.pop(key, None)
        alone = not self.others_during.pop(key, True)
        if start is not None and key in ("alt_l", "ctrl_l") and alone and t - start < LONE_MODIFIER_S \
                and key in self.known and not self.bound.get(key):
            return "modifier"
        return None


def step_window(step, prev_end=None):
    """(start, end) wall seconds of a map step from its log time and lat_ms (beat -> outcome). An unchecked step at a
    set tempo waited out one click interval; in flow mode it ran from the previous step's line to its own."""
    end = step["ts"]
    if isinstance(step.get("lat_ms"), (int, float)) and step["lat_ms"] >= 0:
        return end - step["lat_ms"] / 1000.0, end
    if step.get("tempo"):
        start = end - 60.0 / step["tempo"]
        return (max(start, prev_end) if prev_end is not None else start), end
    return (prev_end if prev_end is not None else end - 1.0), end


class StepMatcher:
    """Join the map's KT|step lines with the player's presses.

    binds: action -> set of verified keys. `delay` is the median gap between a press and the editor log line of the
    step it completed (client -> island server -> editor log); it is learned from steps the map graded ok and applied
    to every window. The log delay and your usual offset from the beat cannot be told apart, so offsets are relative
    to your own median: they measure consistency and drift. Absolute beat -> result time is the map's lat_ms."""

    def __init__(self, binds, drill_actions=None):
        """drill_actions: drill id -> every action its steps or accepted orders use. A press of another of those
        actions' keys inside a step's window is a wrong key; movement, camera and combat keys outside the drill are
        not (holding W while building is normal)."""
        self.drill_actions = {d: set(a) for d, a in (drill_actions or {}).items()}
        self.consumed = collections.deque(maxlen=64)
        self.binds = {a: {normal(k) for k in ks} for a, ks in binds.items()}
        self.key_actions = collections.defaultdict(set)
        for a, ks in self.binds.items():
            for k in ks:
                self.key_actions[k].add(a)
        self.delays = collections.deque(maxlen=CLOCK_SAMPLES)
        self.offsets = collections.deque(maxlen=BASELINE_SAMPLES)
        self.prev_end = None

    @property
    def delay(self):
        return statistics.median(self.delays) if self.delays else 0.0

    def baseline(self):
        if len(self.offsets) < 5:
            return None
        med = statistics.median(self.offsets)
        mad = statistics.median(abs(o - med) for o in self.offsets) or 0.01
        return {"median_ms": round(med * 1000), "mad_ms": round(mad * 1000)}

    def match(self, step, presses):
        """Grade one step. presses: [(ts, key)] sorted, covering at least the step window.
        Returns a dict: outcome, action, expected keys, pressed key, offset_ms, features for Jev when ambiguous."""
        action = step.get("action") or ""
        expected = self.binds.get(action)
        start, end = step_window(step, self.prev_end)
        self.prev_end = end
        out = {"kind": "kstep", "drill": step.get("drill_id"), "rep": step.get("rep"), "step": step.get("step"),
               "action": action, "map_result": step.get("result"), "ts": step["ts"], "tempo": step.get("tempo"),
               "lat_ms": step.get("lat_ms")}
        if not expected:
            out.update(outcome="ungraded", reason="action not verified in your binds")
            return out
        d = self.delay
        lookback = STEP_LOOKBACK_S if len(self.delays) >= 5 else 1.0     # wide until the log delay is learned
        lo, hi = start - d - lookback, end - d
        used = set(self.consumed)
        window = [(t, normal(k)) for t, k in presses if lo <= t <= hi and (t, normal(k)) not in used]
        hits = [(t, k) for t, k in window if k in expected]
        if hits:
            t, k = hits[0]
            self.consumed.append((t, k))              # one press completes one step
            if str(step.get("result")).lower() == "ok" and step.get("lat_ms") is not None:
                self.delays.append(max(0.0, start - t))       # log delay minus your usual offset from the beat
            offset = t - (start - d)
            out.update(pressed=k, offset_ms=round(offset * 1000))
            wrong_before = [(tw, kw) for tw, kw in window if tw < t and kw not in expected]
            if wrong_before and t - wrong_before[-1][0] <= SELF_CORRECT_S:
                kw = wrong_before[-1][1]
                out.update(outcome="slip", wrong=kw, intended=k, corrected_ms=round((t - wrong_before[-1][0]) * 1000),
                           distance=key_distance(kw, k))
                return out
            out["outcome"] = self._timing(offset, step.get("tempo"))
            if out["outcome"] == "clean":
                self.offsets.append(offset)
            base = self.baseline()
            if base and abs(out["offset_ms"] - base["median_ms"]) > DRIFT_MADS * base["mad_ms"]:
                out["drift"] = True
            return out
        drill_keys = set()
        for a in self.drill_actions.get(step.get("drill_id"), set(self.binds)):
            drill_keys |= self.binds.get(a, set())
        bound_keys = set(self.key_actions)
        near_expected = {n for e in expected for n in neighbours(e)}
        wrong = [(t, k) for t, k in window
                 if k not in expected and (k in drill_keys or (k not in bound_keys and k in near_expected))]
        if wrong:
            t, k = wrong[0]
            near = sorted(e for e in expected if k in neighbours(e))
            out.update(outcome="wrong_key", pressed=k, expected=sorted(expected),
                       bound_to=sorted(self.key_actions.get(k, ())), distance=min(
                           (x for x in (key_distance(k, e) for e in expected) if x is not None), default=None))
            # Adjacent with no correction, or an unbound key next to the expected one: intent is a judgement call.
            out["ambiguous"] = bool(near)
            return out
        out.update(outcome="missing", expected=sorted(expected))
        return out

    @staticmethod
    def _timing(offset, tempo):
        if not tempo:                    # flow / free tempo: only the key is graded
            return "clean"
        interval = 60.0 / tempo
        window = max(0.25 * interval, 0.060)
        if offset < -window:
            return "early"
        if offset > interval / 2 + window:
            return "late"
        return "clean"


def summary(events):
    """The stats box's numbers from one session's events (press labels, kstep outcomes, accepted Jev verdicts)."""
    presses = collections.Counter(e["kind"] for e in events
                                  if e.get("kind") in ("ok", "unmapped", "unverified", "double", "modifier", "habit"))
    steps = [e for e in events if e.get("kind") == "kstep" and e.get("outcome") not in (None, "ungraded")]
    causes = collections.Counter()
    pairs = collections.Counter()
    for s in steps:
        if s["outcome"] in CAUSES:
            causes[s["outcome"]] += 1
        if s["outcome"] in ("slip", "wrong_key"):
            pairs[(s.get("wrong") or s.get("pressed"), s.get("intended") or (s.get("expected") or ["?"])[0])] += 1
    causes["modifier"] += presses["modifier"]
    causes["unmapped"] += presses["unmapped"]
    jev = [e for e in events if e.get("kind") == "jev" and e.get("accepted") == "live"]
    for j in jev:
        if j.get("intended_key") and j.get("key"):
            pairs[(j["key"], j["intended_key"])] += 1
    offsets = [s["offset_ms"] for s in steps if s.get("outcome") == "clean" and isinstance(s.get("offset_ms"), int)]
    lat = [s["lat_ms"] for s in events if s.get("kind") == "kstep" and isinstance(s.get("lat_ms"), int)]
    clean = sum(s["outcome"] == "clean" for s in steps)
    total_presses = sum(presses.values())
    return {
        "steps": len(steps), "clean": clean,
        "step_pct": round(100 * clean / len(steps)) if steps else None,
        "drill": next((s.get("drill") for s in reversed(steps) if s.get("drill")), None),
        "tempo": next((s.get("tempo") for s in reversed(steps) if s.get("tempo") is not None), None),
        "presses": total_presses,
        "bound_pct": round(100 * presses["ok"] / total_presses) if total_presses else None,
        "spread_ms": round(statistics.pstdev(offsets)) if len(offsets) > 1 else None,
        "median_offset_ms": round(statistics.median(offsets)) if offsets else None,
        "beat_to_result_ms": round(statistics.median(lat)) if lat else None,
        "drift": sum(bool(s.get("drift")) for s in steps),
        "causes": {c: causes[c] for c in CAUSES if causes[c]},
        "top_pair": pairs.most_common(1)[0] if pairs else None,
        "unmapped_keys": [k for k, _ in collections.Counter(
            e["key"] for e in events if e.get("kind") == "unmapped" and e.get("key")).most_common(3)],
    }


def fix_next(s, action_of=None):
    """One plain line about the biggest thing to fix, from summary(); empty when there is nothing to say yet."""
    action_of = action_of or {}
    if s.get("top_pair") and s["top_pair"][1] >= 2:
        (wrong, meant), n = s["top_pair"]
        what = action_of.get(meant)
        return f"{wrong.upper()} pressed for {meant.upper()}{f' ({what})' if what else ''} x{n}"
    causes = s.get("causes") or {}
    if not causes:
        return ""
    top = max(causes, key=causes.get)
    n = causes[top]
    if top == "late":
        return f"Late on the beat x{n}: press as the click lands, not after"
    if top == "early":
        return f"Early x{n}: wait for the click"
    if top == "missing":
        return f"Missed steps x{n}: slow the tempo until every step lands"
    if top == "double":
        return f"Double presses x{n}: one clean tap per action"
    if top == "modifier":
        return f"Stray modifier (Caps / Alt / Ctrl) x{n}"
    if top == "unmapped":
        keys = ", ".join(k.upper() for k in s.get("unmapped_keys") or [])
        return f"Unbound keys pressed x{n}{f' ({keys})' if keys else ''}"
    return f"{top.replace('_', ' ')} x{n}"
