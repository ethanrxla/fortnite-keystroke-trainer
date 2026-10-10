"""Calibrate keybinds.json by pressing each of your own keys once.

    python -m keystroke_lab binds [--out keybinds.json] [--category move combat build edit ui] [--only sprint wall]

Fortnite keeps your bindings in your Epic account, not in a local file, so the only way to match them exactly is
to ask. For each action (see actions.py: movement, combat, build, edit, ui) it waits for one key or mouse-button
press and stores it. Every tool (keys, record, practice, review) then reads that file by default.
Esc keeps the current value. Several actions may share a key (the prompt tells you when one already does).
Only the key you press while prompted is read.
"""

import json
import pathlib

from . import actions, drills, keyboard_overlay
from .bind_profiles import ProfileStore


def shared_with(binds, action, key):
    return [a for a, k in binds.items() if k == key and a != action and a != "swap_weapon"]


def apply_choice(binds, action, key):
    """Store one calibrated key and return the other actions that already use it (for the warning)."""
    others = shared_with(binds, action, key)
    binds[action] = key
    if action == "slot1":
        binds["swap_weapon"] = key
    return others


def run(out, only=None, categories=None):
    try:
        from pynput import keyboard, mouse
    except ImportError:
        print("binds needs pynput: pip install pynput")
        return 2
    import queue
    q = queue.Queue()
    kl = keyboard.Listener(on_press=lambda k: q.put(keyboard_overlay.normal(getattr(k, "char", None) or getattr(k, "name", k))))
    ml = mouse.Listener(on_click=lambda x, y, b, p: q.put("mouse_" + b.name) if p else None,
                        on_scroll=lambda x, y, dx, dy: q.put("wheel_up" if dy > 0 else "wheel_down"))
    kl.start()
    ml.start()
    store = ProfileStore(out, confirm_sprint=pathlib.Path(out) == drills.BINDS_FILE)
    binds = store.snapshot.primary()
    todo = only or actions.actions_in(categories)
    try:
        for action in todo:
            while not q.empty():
                q.get()
            print(f"[{actions.CATEGORY_OF.get(action, '?')}] press your key for {actions.PROMPTS.get(action, action)} "
                  f"(now: {binds.get(action, '-')}); Esc keeps it ... ", end="", flush=True)
            key = q.get()
            if key == "esc":
                print("kept")
                continue
            others = apply_choice(binds, action, key)
            keys = [key]
            while not q.empty():
                q.get()
            print('Press an alternate for this action, or Esc to continue ... ', end='', flush=True)
            alternate = q.get()
            if alternate != 'esc' and alternate != key:
                keys.append(alternate)
                print(alternate)
            else:
                print('no alternate')
            store.update(action, keys, actions.CATEGORY_OF.get(action, 'any'), verified=True)
            if action == "slot1":
                store.update("swap_weapon", keys, "combat", verified=True)
            print(key + (f"   (also {', '.join(others)})" if others else ""))
    finally:
        kl.stop()
        ml.stop()
    # Each confirmed action is persisted atomically with verification and revision.
    print("saved", out)
    return 0
