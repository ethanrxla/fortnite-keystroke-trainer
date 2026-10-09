"""Calibrate keybinds.json by pressing each of your own keys once.

    python -m keystroke_lab binds [--out keybinds.json] [--only wall floor edit]

Fortnite keeps your bindings in your Epic account, not in a local file, so the only way to match them
exactly is to ask. For each action it waits for one key or mouse-button press and stores it. Every tool
(keys, record, practice, review) then reads that file by default. Press Esc to skip an action and keep
its current value. Only the key you press while prompted is read.
"""

import json
import pathlib

from . import drills, keyboard_overlay

PROMPTS = {
    "wall": "WALL (build)", "floor": "FLOOR (build)", "ramp": "RAMP / stairs (build)", "cone": "ROOF / cone (build)",
    "edit": "EDIT", "edit_confirm": "EDIT CONFIRM", "reset": "EDIT RESET", "jump": "JUMP", "crouch": "CROUCH",
    "fire": "FIRE", "swap_weapon": "your FIRST GUN slot", "pickaxe": "PICKAXE slot",
}
ORDER = ["wall", "floor", "ramp", "cone", "edit", "edit_confirm", "reset", "jump", "crouch", "fire",
         "swap_weapon", "pickaxe"]


def run(out, only=None):
    try:
        from pynput import keyboard, mouse
    except ImportError:
        print("binds needs pynput: pip install pynput")
        return 2
    import queue
    q = queue.Queue()
    kl = keyboard.Listener(on_press=lambda k: q.put(keyboard_overlay.normal(getattr(k, "char", None) or getattr(k, "name", k))))
    ml = mouse.Listener(on_click=lambda x, y, b, p: q.put("mouse_" + b.name) if p else None)
    kl.start(); ml.start()
    binds = drills.load_binds(out)
    try:
        for action in (only or ORDER):
            while not q.empty():
                q.get()
            print(f"Press your key for {PROMPTS.get(action, action)} (now: {binds.get(action, '-')}); Esc keeps it ... ", end="", flush=True)
            key = q.get()
            if key == "esc":
                print("kept")
                continue
            binds[action] = key
            print(key)
    finally:
        kl.stop(); ml.stop()
    pathlib.Path(out).write_text(json.dumps(binds, indent=2), encoding="utf-8")
    print("saved", out)
    return 0
