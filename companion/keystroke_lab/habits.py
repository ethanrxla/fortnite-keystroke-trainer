"""Learn which keys you habitually press, so a key you really use is never called an accident.

While the game is focused, every press of a key that is not in your bind profile is counted per key and per
minute of play. A key becomes a habit once it has been pressed at least MIN_PRESSES times across at least
MIN_MINUTES different minutes: rare slips never reach that, a real unmapped key does within a short session.
State lives in companion/habits.json (gitignored). Only key names and counts are stored, never order or timing.
"""

import json
import pathlib

HABITS_FILE = pathlib.Path(__file__).resolve().parents[1] / "habits.json"
MIN_PRESSES = 12
MIN_MINUTES = 3


class Habits:
    def __init__(self, path=HABITS_FILE, min_presses=MIN_PRESSES, min_minutes=MIN_MINUTES):
        self.path = pathlib.Path(path) if path else None
        self.min_presses = min_presses
        self.min_minutes = min_minutes
        self.data = {}
        self.dirty = 0
        if self.path and self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def record(self, key, minute):
        entry = self.data.setdefault(key, {"presses": 0, "minutes": []})
        entry["presses"] += 1
        if minute not in entry["minutes"]:
            entry["minutes"] = (entry["minutes"] + [minute])[-60:]
        self.dirty += 1
        # Persist at session shutdown, outside the input/display path.

    def is_habit(self, key):
        entry = self.data.get(key)
        return bool(entry) and entry["presses"] >= self.min_presses and len(entry["minutes"]) >= self.min_minutes

    def habits(self):
        return sorted(k for k in self.data if self.is_habit(k))

    def reset(self):
        self.data = {}
        self.save()

    def save(self):
        self.dirty = 0
        if self.path:
            self.path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
