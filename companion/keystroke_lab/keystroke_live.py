"""The overlay's live keystroke grading: the map's KT|step lines joined with gated presses (keystroke_math), and Jev
asked about the ambiguous ones (jev_keystrokes) under KeystrokeLimits.

Runs on the overlay's worker threads, never on the capture or Tk thread. Steps are graded only while the island
reports a single player (`KT|context|players=1`), because KT lines carry no player id: with several players, a step
line cannot be tied to this keyboard.
"""

import collections
import datetime
import json
import os
import pathlib
import threading
import time

from . import jev_keystrokes
from .keyboard_overlay import neighbours, normal
from .keystroke_math import StepMatcher

# Off until the step join passes the replay against the map's own verdicts (2026-10-14: only 41% of map-confirmed
# steps matched; the press -> log-line gap ranged from -0.8 s to +7 s, and lat_ms=0 steps need no press at all).
STEP_GRADING = False
PRESS_MEMORY_S = 30.0
BATCH_WAIT_S = 1.0              # an ambiguous press waits at most this long for others to share its Jev call
PER_MINUTE = 20                 # runaway guard
PER_DAY = 2000                  # about $0.36/day at the observed ~4.2k tokens per call
RUNTIME = pathlib.Path(__file__).resolve().parents[1] / ".runtime"


def drill_actions(path=pathlib.Path(__file__).resolve().parents[2] / "shared" / "drills.json"):
    """drill id -> the actions its steps and accepted orders use (shared/drills.json)."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for d in data.get("drills", []):
        acts = set(d.get("steps", []))
        for alt in d.get("accepts", []) or []:
            acts |= set(alt)
        out[d["id"]] = acts
    return out


class KeystrokeLimits:
    """Per-minute and per-day call limits for the keystroke Jev domain; the day count survives restarts."""

    def __init__(self, path=RUNTIME / "jev-keystroke-day.json", per_minute=PER_MINUTE, per_day=PER_DAY,
                 clock=time.time):
        self.path, self.per_minute, self.per_day, self.clock = pathlib.Path(path), per_minute, per_day, clock
        self.recent = collections.deque()
        self.lock = threading.Lock()

    def _day(self):
        return datetime.datetime.fromtimestamp(self.clock(), datetime.timezone.utc).strftime("%Y-%m-%d")

    def _read(self):
        try:
            data = json.loads(self.path.read_text())
            return data["calls"] if data.get("day") == self._day() else 0
        except (OSError, ValueError, KeyError, TypeError):
            return 0

    def take(self):
        """True and counted when a call may go out now."""
        with self.lock:
            now = self.clock()
            while self.recent and now - self.recent[0] > 60.0:
                self.recent.popleft()
            calls = self._read()
            if len(self.recent) >= self.per_minute or calls >= self.per_day:
                return False
            self.recent.append(now)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps({"day": self._day(), "calls": calls + 1}))
            except OSError:
                pass
            return True


def keystroke_client(key=None):
    """A JevClient on its own broker session: no shared 30 s cooldown with the edit guide, one call in flight."""
    from .jev_broker import JevBroker
    from .jev_client import JevClient
    session = os.environ.get("KT_COACH_SESSION", "standalone") + ":keystroke"
    return JevClient(key=key, domain="keystroke_intent", broker=JevBroker(session=session, cooldown=0.0, cap=10 ** 9),
                     max_calls=PER_DAY, shadow=False)


class KeystrokeLive:
    def __init__(self, verified_by_key, profile_rev, emit, jev=None, limits=None, clock=time.time):
        """verified_by_key: key -> set of verified actions. emit(record) writes to the session log."""
        self.emit, self.jev, self.clock = emit, jev, clock
        self.limits = limits or KeystrokeLimits()
        self.lock = threading.RLock()
        self.presses = collections.deque()
        self.pending = []
        self.cache = {}
        self.single_player = True
        self.set_profile(verified_by_key, profile_rev)

    def set_profile(self, verified_by_key, profile_rev):
        with self.lock:
            self.bound = {normal(k): set(v) for k, v in verified_by_key.items() if v}
            by_action = collections.defaultdict(set)
            for k, acts in self.bound.items():
                for a in acts:
                    by_action[a].add(k)
            self.matcher = StepMatcher(by_action, drill_actions())
            self.profile_rev = profile_rev
            self.pending.clear()
            self.cache.clear()

    def press(self, key, ts):
        with self.lock:
            self.presses.append((ts, normal(key)))
            while self.presses and ts - self.presses[0][0] > PRESS_MEMORY_S:
                self.presses.popleft()

    def revoke_since(self, ts):
        """Forget presses from ts on (the gate decided they were typing)."""
        with self.lock:
            while self.presses and self.presses[-1][0] >= ts:
                self.presses.pop()

    def on_kt(self, rec, ts):
        """Feed one KT record with its log wall time. Returns the step outcome, or None."""
        event = rec.get("event")
        if event == "context" and "players" in rec:
            try:
                self.single_player = int(rec["players"]) <= 1
            except (TypeError, ValueError):
                self.single_player = False
            return None
        if event == "set_start":
            with self.lock:
                self.matcher.prev_end = None
            return None
        if event != "step" or not self.single_player or not STEP_GRADING:
            return None
        with self.lock:
            out = self.matcher.match(dict(rec, ts=ts), list(self.presses))
            out["profile_rev"] = self.profile_rev
            if out.get("ambiguous"):
                out["event_id"] = f"e{int(ts * 1000) % 10 ** 9}"
        self.emit(out)
        if out.get("ambiguous"):
            with self.lock:
                self._queue(out)
        return out

    def _queue(self, out):
        key = out["pressed"]
        just_before = [{"key": k, "ms_ago": round((out["ts"] - t) * 1000)}
                       for t, k in list(self.presses)[-4:] if 0 < out["ts"] - t < 1.0 and k != key]
        event = {"id": out["event_id"], "key": key, "expected_action": out["action"],
                 "offset_ms": out.get("offset_ms"), "baseline": self.matcher.baseline(), "just_before": just_before,
                 "queued": self.clock()}
        cache_key = (key, out["action"], tuple(sorted(n for n in neighbours(key) if n in self.bound)))
        if cache_key in self.cache:
            self.emit(dict(self.cache[cache_key], event_id=event["id"], cached=True))
            return
        event["cache_key"] = cache_key
        self.pending.append(event)

    def jev_due(self):
        with self.lock:
            if not self.pending:
                return False
            return (len(self.pending) >= jev_keystrokes.EVENTS_PER_CALL
                    or self.clock() - self.pending[0]["queued"] >= BATCH_WAIT_S)

    def ask_jev(self):
        """One batched call when due and allowed. Returns the accepted/likely/unclassified results (also emitted)."""
        with self.lock:
            if not self.pending or self.jev is None or not self.jev.available:
                self.pending.clear()
                return []
            batch = self.pending[:jev_keystrokes.EVENTS_PER_CALL]
            del self.pending[:jev_keystrokes.EVENTS_PER_CALL]
            bound, rev = dict(self.bound), self.profile_rev
        if not self.limits.take():
            return []
        started = time.perf_counter()
        results = jev_keystrokes.ask(self.jev, batch, bound, rev, current_rev=self.profile_rev)
        ms = round((time.perf_counter() - started) * 1000)
        with self.lock:
            if rev != self.profile_rev:
                return []
            for r, e in zip(results, batch):
                r["latency_ms"] = ms
                if r.get("accepted") in ("live", "likely", "unclassified"):
                    self.cache[e["cache_key"]] = {k: v for k, v in r.items() if k != "event_id"}
        for r in results:
            self.emit(r)
        return results


def follow_kt(path, stop, poll=0.1):
    """Yield (wall_ts, record) for KT lines appended to the editor log from now on."""
    from . import collector, ktlog
    path = pathlib.Path(path)
    offset = path.stat().st_size if path.exists() else 0
    pending = ""
    while not stop.is_set():
        size = path.stat().st_size if path.exists() else 0
        if size < offset:
            offset = 0
        if size > offset:
            with path.open("rb") as f:
                f.seek(offset)
                pending += f.read(size - offset).decode("utf-8", errors="replace")
            offset = size
            *lines, pending = pending.split("\n")
            for line in lines:
                rec, ts = ktlog.parse_line(line), collector.log_ts(line)
                if rec and ts:
                    yield ts, rec
        stop.wait(poll)
