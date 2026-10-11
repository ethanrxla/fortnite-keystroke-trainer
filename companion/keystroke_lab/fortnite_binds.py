"""Import keybinds from Fortnite's own local config instead of guessing from defaults.

    python -m keystroke_lab import-binds [--file PATH] [--write] [--trust]

Reads Unreal input mappings (`ActionMappings=(ActionName="Jump",...,Key=SpaceBar)` and
`AxisMappings=(AxisName="MoveForward",Scale=1.0,Key=W)`) from Input.ini / GameUserSettings.ini under
%LOCALAPPDATA%\\FortniteGame\\Saved\\Config\\WindowsClient. Current Fortnite builds keep most bindings in the
cloud-synced ClientSettings.Sav, which is a binary save this tool does not parse, so an empty or stale ini is
possible (VERIFY against your Settings > Keyboard Controls). Without --write it only prints what it found.

Imported bindings are unverified unless --trust: they stop bound keys reading as stray, but drill grading still
waits for `binds` calibration. Actions you already calibrated are never overwritten. Reads files only.
"""

import os
import pathlib
import re

from .actions import CATEGORY_OF
from .bind_profiles import Binding

# Unreal key names (FKey) -> keybinds.json naming (pynput, see keyboard_overlay.ROWS).
UE_KEYS = {
    "spacebar": "space", "leftshift": "shift", "rightshift": "shift", "leftcontrol": "ctrl_l",
    "rightcontrol": "ctrl_l", "leftalt": "alt_l", "rightalt": "alt_l", "tab": "tab", "capslock": "caps_lock",
    "enter": "enter", "escape": "esc", "backspace": "backspace", "tilde": "`", "hyphen": "-", "equals": "=",
    "leftbracket": "[", "rightbracket": "]", "backslash": "\\", "semicolon": ";", "apostrophe": "'",
    "comma": ",", "period": ".", "slash": "/",
    "leftmousebutton": "mouse_left", "rightmousebutton": "mouse_right", "middlemousebutton": "mouse_middle",
    "thumbmousebutton": "mouse_x1", "thumbmousebutton2": "mouse_x2",
    "mousescrollup": "wheel_up", "mousescrolldown": "wheel_down",
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9",
}
UE_KEYS.update({f"f{n}": f"f{n}" for n in range(1, 13)})
UE_KEYS.update({c: c for c in "abcdefghijklmnopqrstuvwxyz"})

# Fortnite action names, normalized (lowercase, letters and digits only) -> actions.py ids. Names vary between
# seasons; anything unknown is reported, not guessed.
UE_ACTIONS = {
    "jump": "jump", "sprint": "sprint", "crouch": "crouch", "fire": "fire", "primaryfire": "fire",
    "targeting": "aim", "aimdownsights": "aim", "aim": "aim", "reload": "reload", "reloadrotate": "reload",
    "harvestingtool": "pickaxe", "pickaxe": "pickaxe",
    "weaponslot1": "slot1", "weaponslot2": "slot2", "weaponslot3": "slot3", "weaponslot4": "slot4",
    "weaponslot5": "slot5",
    "wall": "wall", "buildwall": "wall", "floor": "floor", "buildfloor": "floor", "stairs": "ramp",
    "buildstair": "ramp", "buildstairs": "ramp", "ramp": "ramp", "roof": "cone", "buildroof": "cone",
    "cone": "cone", "trap": "trap", "placetrap": "trap", "changebuildingmaterial": "material",
    "switchbuildingmaterial": "material", "rotatebuilding": "rotate", "rotate": "rotate",
    "repair": "repair", "repairbuilding": "repair",
    "edit": "edit", "buildingedit": "edit", "selectbuildingedit": "edit", "confirmedit": "edit_confirm",
    "editselect": "edit_confirm", "resetbuildingedit": "reset", "reset": "reset",
    "use": "use", "interact": "use", "map": "map", "inventory": "inventory", "chat": "chat",
    "pushtotalk": "push_to_talk", "emote": "emote", "emotewheel": "emote", "ping": "ping", "placemarker": "ping",
}
# (axis name, sign of Scale) -> action.
UE_AXES = {
    ("moveforward", 1): "forward", ("moveforward", -1): "back",
    ("moveright", 1): "right", ("moveright", -1): "left",
}

MAPPING = re.compile(r"^\s*\+?(ActionMappings|AxisMappings)\s*=\s*\((.*)\)\s*$", re.IGNORECASE)
FIELD = re.compile(r'(\w+)\s*=\s*("([^"]*)"|[^,()]+)')


def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def ue_key(name):
    """keybinds.json name for an Unreal key name, or None for gamepad and keys the overlay does not draw."""
    return UE_KEYS.get(norm(name))


def parse_line(line):
    """(action id, key) for one mapping line, or (None, reason) when it cannot be used."""
    m = MAPPING.match(line)
    if not m:
        return None, None
    fields = {k.lower(): (q if q is not None and v.startswith('"') else v.strip()) for k, v, q in FIELD.findall(m.group(2))}
    key = ue_key(fields.get("key", ""))
    if key is None:
        return None, f"key {fields.get('key', '?')} (not keyboard or mouse)"
    if any(fields.get(f, "false").lower() == "true" for f in ("bshift", "bctrl", "balt", "bcmd")):
        return None, f"modifier combo for {fields.get('actionname', '?')}"
    if m.group(1).lower() == "axismappings":
        try:
            sign = 1 if float(fields.get("scale", "1")) >= 0 else -1
        except ValueError:
            return None, "bad axis scale"
        action = UE_AXES.get((norm(fields.get("axisname", "")), sign))
        return (action, key) if action else (None, f"axis {fields.get('axisname', '?')}")
    action = UE_ACTIONS.get(norm(fields.get("actionname", "")))
    return (action, key) if action else (None, f"action {fields.get('actionname', '?')}")


def parse_text(text):
    """({action: [keys in file order]}, [skipped reasons]). Later duplicates become alternates."""
    found, skipped = {}, []
    for line in text.splitlines():
        action, detail = parse_line(line)
        if action:
            keys = found.setdefault(action, [])
            if detail not in keys:
                keys.append(detail)
        elif detail:
            skipped.append(detail)
    return found, skipped


def config_dir(env=os.environ):
    base = env.get("LOCALAPPDATA")
    return pathlib.Path(base) / "FortniteGame" / "Saved" / "Config" / "WindowsClient" if base else None


def candidate_files(env=os.environ):
    folder = config_dir(env)
    return [folder / n for n in ("Input.ini", "GameUserSettings.ini")] if folder else []


def read_binds(files):
    """Merge mappings from the given files (earlier files win per action). Returns (found, skipped, used files)."""
    found, skipped, used = {}, [], []
    for path in files:
        path = pathlib.Path(path)
        if not path.is_file():
            continue
        part, miss = parse_text(path.read_text(encoding="utf-8", errors="replace"))
        if part:
            used.append(path)
        for action, keys in part.items():
            found.setdefault(action, keys)
        skipped += miss
    return found, skipped, used


def to_bindings(found, trust=False):
    """Bindings for ProfileStore.merge. slot1 also feeds the legacy swap_weapon name."""
    out = [Binding(a, tuple(keys), CATEGORY_OF.get(a, "any"), trust) for a, keys in found.items()]
    if "slot1" in found:
        out.append(Binding("swap_weapon", tuple(found["slot1"]), "combat", trust))
    return out


def run(store, files=None, write=False, trust=False):
    files = files or candidate_files()
    if not files:
        print("LOCALAPPDATA is not set; pass --file with the path to Fortnite's Input.ini")
        return 2
    found, skipped, used = read_binds(files)
    if not used:
        print("no keyboard bindings found in:", *[str(f) for f in files], sep="\n  ")
        print("Fortnite may keep them only in its cloud save; run `python -m keystroke_lab binds` to calibrate.")
        return 1
    print("read:", ", ".join(str(u) for u in used))
    current = store.snapshot.primary()
    for action in sorted(found):
        keys = "/".join(found[action])
        mark = "" if current.get(action) == found[action][0] else f"   (profile now: {current.get(action, '-')})"
        print(f"  {action:<14}{keys}{mark}")
    if skipped:
        print(f"skipped {len(skipped)} mappings, e.g. " + "; ".join(sorted(set(skipped))[:6]))
    if not write:
        print("dry run; add --write to save to", store.path)
        return 0
    changed = store.merge(to_bindings(found, trust))
    print(f"updated {len(changed)} actions in {store.path}" + ("" if trust else " (unverified; calibrate to grade drills)"))
    return 0
