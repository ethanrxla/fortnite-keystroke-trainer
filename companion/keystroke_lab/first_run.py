"""First-run calibration: open the key calibration window by itself when the player first enters the game.

Fortnite keeps keybinds in the player's Epic account, so the companion cannot read them; it has to be told. Rather than
make the player remember to run `python -m keystroke_lab binds`, the autostart watcher (autostart.py) calls
`maybe_launch()` when the game starts. It opens calibration_window over the game only while the core binds are not yet
confirmed, at most MAX_PROMPTS times (so closing the window unfinished does not nag forever), and never again once every
core action is verified.

State lives in companion/.calibration-state.json (gitignored): {"prompts": n, "last": unix seconds}.
"""

import json
import os
import pathlib
import subprocess
import sys
import time

from . import drills
from .bind_profiles import ProfileStore

STATE_FILE = pathlib.Path(__file__).resolve().parents[1] / ".calibration-state.json"
MAX_PROMPTS = 3
MIN_GAP_SECONDS = 600   # a window closed a moment ago is not re-opened by a game restart
# Actions the overlay, the edit guide and the drills depend on being exactly right for this player.
CORE_ACTIONS = ("forward", "left", "back", "right", "sprint", "jump", "crouch", "fire", "wall", "floor", "ramp",
                "cone", "edit", "edit_confirm", "reset", "pickaxe")


def unverified(path=None):
    """Core actions whose key has not been confirmed by the player (default guesses and old files are unverified)."""
    snapshot = ProfileStore(path or drills.BINDS_FILE, confirm_sprint=False).snapshot
    confirmed = {b.action for b in snapshot.bindings if b.verified}
    return [a for a in CORE_ACTIONS if a not in confirmed]


def needs_calibration(path=None):
    return bool(unverified(path))


def load_state(path=STATE_FILE):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"prompts": 0, "last": 0}


def should_prompt(state, now=None, missing=True):
    now = time.time() if now is None else now
    return bool(missing) and state.get("prompts", 0) < MAX_PROMPTS and now - state.get("last", 0) >= MIN_GAP_SECONDS


def record_prompt(path=STATE_FILE, now=None):
    state = load_state(path)
    state = {"prompts": state.get("prompts", 0) + 1, "last": time.time() if now is None else now}
    pathlib.Path(path).write_text(json.dumps(state), encoding="utf-8")
    return state


def reset(path=STATE_FILE):
    try:
        pathlib.Path(path).unlink()
    except FileNotFoundError:
        pass


def maybe_launch(popen=subprocess.Popen, binds_path=None, state_path=STATE_FILE, now=None, saves=None):
    """Open the calibration window if this player still needs it. Returns the process, or None when not needed.
    Never while Fortnite's own settings save is on this PC: the overlay imports the binds from it (fortnite_binds.SavSync,
    confirmed 2026-10-20 against the player's binds), so calibration is not needed (player 2026-10-20: hide it)."""
    if saves is None:
        from .fortnite_binds import sav_files as saves
    if saves():
        return None
    if not should_prompt(load_state(state_path), now, needs_calibration(binds_path)):
        return None
    record_prompt(state_path, now)
    exe = pathlib.Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    flags = 0x08000000 if os.name == "nt" else 0
    return popen([str(pythonw if pythonw.exists() else exe), "-m", "keystroke_lab.calibration_window"],
                 cwd=str(pathlib.Path(__file__).resolve().parents[1]), creationflags=flags)
