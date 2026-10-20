"""Record your own build inputs to a file, so profile.py can learn how you actually play.

What it reads: verified bound inputs while Fortnite is focused, subject to the shared
menu/chat transition gate. The gate cannot establish an already-open UI at startup.
What it never does: read game memory, touch the Fortnite process, or send any input. It is the same
kind of thing as a stream input overlay.

    python -m keystroke_lab record --out sessions/today.jsonl [--binds keybinds.json] [--flicks]

Stop with Ctrl+C. Each line is {"t": seconds_since_start, "kind": "key" | "flick", "name": ...}.

--flicks also logs fast sideways camera moves as turns (needed to see 90s). It compares successive
mouse positions, which is unreliable while a game recentres the cursor, so treat it as VERIFY and
check a recording of a known 90 before trusting it.
"""

import json
import pathlib
import time
from .input_gate import GameplayInputGate

FLICK_PIXELS = 400      # sideways travel inside the window that counts as a flick
FLICK_WINDOW = 0.15     # seconds
FLICK_COOLDOWN = 0.4


def key_name(k):
    from .keyboard_overlay import key_name as physical
    return str(physical(k)).lower()


def run(out, binds, flicks=False):
    try:
        from pynput import keyboard, mouse
    except ImportError:
        print("record needs pynput: pip install pynput")
        return 2
    from .keyboard_overlay import normal, game_rect
    profile = getattr(binds, 'profile', None)
    watched = {normal(k) for b in profile.bindings if b.verified for k in b.keys} if profile else {normal(k) for k in binds.values()}
    gate = GameplayInputGate(profile)
    held = set()
    path = pathlib.Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    f = path.open("w", encoding="utf-8")
    state = {"x": None, "moves": [], "last_flick": -9.0}

    def emit(kind, name, token):
        if not game_rect() or not gate.accepts(token):
            return
        f.write(json.dumps({"t": round(time.perf_counter() - start, 4), "kind": kind, "name": name}) + "\n")
        f.flush()

    def press(name):
        name = normal(name)
        token = gate.press(name, bool(game_rect()))
        if token is None:
            held.clear()
            return
        if name in watched and name not in held:
            if not name.startswith('wheel_'):
                held.add(name)
            emit('key', name, token)

    def release(name):
        name = normal(name)
        gate.release(name)
        held.discard(name)

    def on_key(k):
        press(key_name(k))

    def on_click(_x, _y, button, pressed):
        name = f"mouse_{button.name}"
        if pressed:
            press(name)
        else:
            release(name)

    def on_scroll(_x, _y, dx, dy):
        if dy:
            press("wheel_up" if dy > 0 else "wheel_down")

    def on_move(x, _y):
        token = gate.token(bool(game_rect()))
        if token is None:
            state['x'], state['moves'] = None, []
            return
        now = time.perf_counter()
        if state["x"] is not None:
            state["moves"].append((now, abs(x - state["x"])))
            state["moves"] = [(t, d) for t, d in state["moves"] if now - t <= FLICK_WINDOW]
            if sum(d for _, d in state["moves"]) >= FLICK_PIXELS and now - state["last_flick"] > FLICK_COOLDOWN:
                state["last_flick"] = now
                emit("flick", "turn", token)
        state["x"] = x

    print(f"recording to {path}  (Ctrl+C to stop)  watching: {', '.join(sorted(watched))}")
    listeners = [keyboard.Listener(on_press=on_key, on_release=lambda k: release(key_name(k))), mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move if flicks else None)]
    for l in listeners:
        l.start()
    try:
        while True:
            gate.focus(bool(game_rect()))
            if not gate.active:
                held.clear()
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        for l in listeners:
            l.stop()
        f.close()
    print("saved", path)
    return 0


def load(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
