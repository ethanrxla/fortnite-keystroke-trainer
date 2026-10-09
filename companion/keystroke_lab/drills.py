"""Drill definitions (shared/drills.json) and the player's keybind profile."""

import json
import pathlib
from dataclasses import dataclass, field

SHARED = pathlib.Path(__file__).resolve().parents[2] / "shared" / "drills.json"

# Fortnite's default PC binds. Players override these in keybinds.json.
DEFAULT_BINDS = {
    "wall": "q", "floor": "f2", "ramp": "f3", "cone": "f4",
    "edit": "g", "edit_confirm": "mouse_left", "reset": "mouse_right",
    "jump": "space", "crouch": "ctrl_l", "fire": "mouse_left", "swap_weapon": "1",
    # VERIFY your own pickaxe bind; players override both in keybinds.json.
    "pickaxe": "f1",
}


@dataclass
class Drill:
    id: str
    tier: int
    name: str
    steps: list
    reps: int = 10
    checks: list = field(default_factory=list)
    # Map-only fields (rep spacing and lane geometry); the companion ignores them.
    advance: list = field(default_factory=lambda: [1, 0, 0])
    lane: dict = field(default_factory=dict)
    code: str = ""
    # Coaching sentence shown when a set is not clean (map and companion share it).
    tip: str = ""
    principle: str = ""
    # any | melee. Map-only: melee lanes strip weapons on the pad. The companion ignores it.
    loadout: str = "any"
    # Other action orders that reach the same state and count as this drill (steps is the reference).
    accepts: list = field(default_factory=list)
    # Kept in the catalog (logs, saved progress, review) but no lane or section is built for it.
    retired: bool = False
    basis: str = ""
    why: str = ""
    reflect: str = ""
    # Map-only: target tiles, start/end tile and guided reps for the crosshair coach on edit walls.
    edit_guide: dict = field(default_factory=dict)


def load_catalog(path=SHARED):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    drills = {d["id"]: Drill(**d) for d in data["drills"]}
    return data["tempo_ladder"], drills


def load_principles(path=SHARED):
    """Principle id -> {name, rule, why, creative}, from the same JSON as the drills."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return {p["id"]: p for p in data.get("principles", [])}


BINDS_FILE = pathlib.Path(__file__).resolve().parents[1] / "keybinds.json"


def load_binds(path=None):
    """Defaults, overridden by your calibrated keybinds.json (python -m keystroke_lab binds)."""
    binds = dict(DEFAULT_BINDS)
    if path is None and BINDS_FILE.exists():
        path = BINDS_FILE
    if path and pathlib.Path(path).exists():
        binds.update(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))
    return binds


def expected_keys(drill, binds):
    """Turn a drill's actions into the keys this player should press (turns are mouse moves, skipped)."""
    return [binds[a] for a in drill.steps if a in binds]
