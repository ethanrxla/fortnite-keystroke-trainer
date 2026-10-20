"""Import keybinds from Fortnite's own settings instead of guessing from defaults or calibrating.

    python -m keystroke_lab import-binds [--file PATH] [--write] [--trust]

Primary source (2026-10-20): the local copy of the cloud settings save,
%LOCALAPPDATA%\\FortniteGame\\Saved\\Cloud\\<account>\\ClientSettings.Sav: an "ECFD" header, then a zlib stream of
Unreal tagged properties. Its UserBindingsPerSubGame map holds, under ESubGame::Athena (Battle Royale and Creative),
one FortActionKeyMapping per action: ActionName, KeyBind1, KeyBind2 and InputScale (its sign tells forward from back
and right from left). Those are the binds Fortnite actually uses, so they are imported as verified and replace
earlier calibration where they differ. The file is only read; Fortnite rewrites it when settings change.

Fallback: the older ini format below.

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
import struct
import zlib

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

# ClientSettings.Sav action names (normalised) -> actions.py ids. Context copies (CrouchWhileBuilding, ...) and
# vehicle / creative-tool actions are skipped.
SAV_ACTIONS = {
    "jump": "jump", "sprint": "sprint", "crouch": "crouch", "fire": "fire", "target": "aim", "reload": "reload",
    "use": "use", "hotbarkey1": "pickaxe", "hotbarkey2": "slot1", "hotbarkey3": "slot2", "hotbarkey4": "slot3",
    "hotbarkey5": "slot4", "hotbarkey6": "slot5", "hotbarkeyf1": "wall", "hotbarkeyf2": "floor",
    "hotbarkeyf3": "ramp", "hotbarkeyf4": "cone", "hotbarkeyf5": "trap", "changematerial": "material",
    "rotateprimitiveclockwise": "rotate", "performbuildingimprovementinteraction": "repair",
    "performbuildingeditinteraction": "edit", "completebuildingeditinteraction": "edit_confirm",
    "buildingeditreset": "reset", "togglefullscreenmap": "map", "toggleinventory": "inventory", "chat": "chat",
    "pushtotalk": "push_to_talk", "emotepicker": "emote", "placemapmarkerinworld": "ping",
}
SAV_AXES = {("moveforward", 1): "forward", ("moveforward", -1): "back",
            ("moveright", 1): "right", ("moveright", -1): "left"}
PLUMBING = {"NameProperty", "EnumProperty", "StructProperty", "ByteProperty", "Key", "KeyName", "/Script/InputCore",
            "/Script/FortniteGame", "EFortInputActionGroup", "ESubGame", "FloatProperty", "BoolProperty"}


def decode_sav(data):
    """The uncompressed property stream of a ClientSettings.Sav (cloud copies are 'ECFD' + 12 bytes + zlib)."""
    if data[:4] == b"ECFD":
        return zlib.decompress(data[16:])
    return data


def _fstrings(raw):
    """[(offset, text)] for every Unreal FString (int32 length incl. NUL, ASCII, NUL) in the stream."""
    out, i, n = [], 0, len(raw)
    while i < n - 5:
        size = struct.unpack_from("<i", raw, i)[0]
        if 1 <= size <= 128 and i + 4 + size <= n and raw[i + 3 + size] == 0:
            s = raw[i + 4:i + 3 + size]
            if all(32 <= c < 127 for c in s):
                out.append((i, s.decode()))
                i += 4 + size
                continue
        i += 1
    return out


def parse_sav(raw):
    """({action: [keys]}, [skipped]) from the ESubGame::Athena user bindings of a decoded ClientSettings.Sav."""
    toks = _fstrings(raw)
    words = [w for _, w in toks]
    start = next((j for j in range(len(words) - 1)
                  if words[j] == "ESubGame::Athena" and words[j + 1] == "UserActionBindings"), None)
    if start is None:
        return {}, ["no ESubGame::Athena user bindings in this save"]
    end = next((j for j in range(start + 2, len(words))
                if words[j] in ("CustomGamepadActionBindings", "UpgradedLegacyMappings")
                or (words[j].startswith("ESubGame::") and words[j + 1:j + 2] == ["UserActionBindings"])), len(words))

    def value(j, name):
        for k in range(j, min(j + 40, end)):
            if words[k] == name:
                for m in range(k + 1, min(k + 12, end)):
                    if words[m] not in PLUMBING:
                        return words[m], m
        return None, None

    found, skipped = {}, []
    for j in range(start, end):
        if words[j] != "ActionName":
            continue
        name, _ = value(j, "ActionName")
        keys = [ue_key(k) for k in (value(j, "KeyBind1")[0], value(j, "KeyBind2")[0]) if k and k != "None"]
        keys = [k for k in keys if k]
        if not name or not keys:
            continue
        action = SAV_ACTIONS.get(norm(name))
        if norm(name) in ("moveforward", "moveright"):
            sign = 1
            for k in range(j, min(j + 40, end)):
                if words[k] == "InputScale" and words[k + 1] == "FloatProperty":
                    off = toks[k + 1][0] + 4 + len("FloatProperty") + 1 + 9   # tag, size, array index, guid flag
                    if off + 4 <= len(raw):
                        sign = 1 if struct.unpack_from("<f", raw, off)[0] >= 0 else -1
                    break
            action = SAV_AXES.get((norm(name), sign))
        if not action:
            skipped.append(f"action {name}")
            continue
        have = found.setdefault(action, [])
        for k in keys:
            if k not in have:
                have.append(k)
    return found, skipped


def sav_files(env=os.environ):
    """Cloud settings copies, newest first."""
    base = env.get("LOCALAPPDATA")
    if not base:
        return []
    files = pathlib.Path(base, "FortniteGame", "Saved", "Cloud").glob("*/ClientSettings.Sav")
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def read_sav(path):
    return parse_sav(decode_sav(pathlib.Path(path).read_bytes()))


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
    if not files or str(files[0]).lower().endswith(".sav"):
        for path in ([pathlib.Path(f) for f in files] if files else sav_files()):
            found, skipped = read_sav(path)
            if found:
                return report(store, found, skipped, [path], write, trust=True, overwrite=True)
    files = files or candidate_files()
    if not files:
        print("LOCALAPPDATA is not set; pass --file with the path to Fortnite's Input.ini")
        return 2
    found, skipped, used = read_binds(files)
    if not used:
        print("no keyboard bindings found in:", *[str(f) for f in files], sep="\n  ")
        print("Fortnite may keep them only in its cloud save; run `python -m keystroke_lab binds` to calibrate.")
        return 1
    return report(store, found, skipped, used, write, trust)


def report(store, found, skipped, used, write, trust=False, overwrite=False):
    """Print what was found against the current profile; with write, merge it in one revision."""
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
    changed = store.merge(to_bindings(found, trust), overwrite_verified=overwrite)
    print(f"updated {len(changed)} actions in {store.path}" + ("" if trust else " (unverified; calibrate to grade drills)"))
    return 0


class SavSync:
    """Keep a ProfileStore in step with Fortnite's own binds: re-import whenever the newest ClientSettings.Sav
    changes (Fortnite rewrites it when settings change). Cheap to call often; the file is parsed only on change."""

    def __init__(self, store, files=sav_files):
        self.store, self.files, self.seen = store, files, None

    def poll(self):
        """Actions that changed in the profile, or [] (no save, unchanged, or nothing new)."""
        try:
            paths = self.files()
            if not paths:
                return []
            stamp = (str(paths[0]), paths[0].stat().st_mtime_ns)
        except OSError:
            return []
        if stamp == self.seen:
            return []
        self.seen = stamp
        try:
            found, _ = read_sav(paths[0])
        except (OSError, ValueError, zlib.error, struct.error):
            return []
        return self.store.merge(to_bindings(found, trust=True), overwrite_verified=True) if found else []
