"""Text-entry detection from key cadence alone, for the input gate. No imports from the overlay (the gate is imported
by it). Keys arrive already normalised (keyboard_overlay.normal)."""

import collections
import statistics


class TypingDetector:
    """Chat / text-box typing from cadence alone, for the input gate (catches party chat, search boxes and chat opened
    with the mouse, which an Enter latch misses).

    A burst is typing when, within TYPING_WINDOW_S, there are at least TYPING_MIN printable presses of which most are
    unbound or the burst contains a space between letters, at an even cadence (inter-key CV below TYPING_MAX_CV) and
    a typing pace (median gap under TYPING_MAX_GAP_S). Gameplay spam (QWER at 150 ms) uses bound keys, so it never
    trips the unbound rule, and holding movement keys repeats a held key, which is not a new press."""

    WINDOW_S, MIN, MAX_CV, MAX_GAP_S, IDLE_S = 1.5, 4, 0.6, 0.30, 3.0

    def __init__(self, bound_keys):
        self.bound = {str(k).lower() for k in bound_keys}
        self.recent = collections.deque()
        self.typing_until = 0.0

    def press(self, key, t):
        """True when this press (and the burst before it) should be treated as typing."""
        key = str(key).lower()
        printable = len(key) == 1 or key == "space"
        if not printable:
            self.recent.clear()
            return t < self.typing_until
        self.recent.append((t, key))
        while self.recent and t - self.recent[0][0] > self.WINDOW_S:
            self.recent.popleft()
        if t < self.typing_until:
            self.typing_until = t + self.IDLE_S
            return True
        keys = [k for _, k in self.recent]
        if len(keys) < self.MIN:
            return False
        gaps = [b[0] - a[0] for a, b in zip(self.recent, list(self.recent)[1:])]
        mean = statistics.mean(gaps)
        cv = statistics.pstdev(gaps) / mean if mean > 0 else 9.9
        unbound = sum(k not in self.bound for k in keys) / len(keys)
        spaced = "space" in keys[1:-1] and any(len(k) == 1 and k.isalpha() for k in keys)
        if (unbound >= 0.5 or spaced) and cv < self.MAX_CV and statistics.median(gaps) < self.MAX_GAP_S:
            self.typing_until = t + self.IDLE_S
            return True
        return False

    def burst_start(self):
        """Wall time of the first press of the current burst, for dropping it retroactively."""
        return self.recent[0][0] if self.recent else None

    def reset(self):
        self.recent.clear()
        self.typing_until = 0.0
