"""Live keyboard overlay: see the keys you press, the ones you miss, and the ones you hit by accident.

    python -m keystroke_lab keys [--drill edit_window] [--binds keybinds.json]

A small always-on-top window (drag it anywhere, Esc or the window's close button to quit) draws a keyboard
and the mouse buttons. While you play:
  green   a key from your bind profile, pressed, and it was the one the drill expected next
  yellow  the key the drill expects next (only with --drill)
  orange  a stray key: not in your bind profile, so probably an accident
  red     a double press (same key twice within DOUBLE_SECONDS) or a bound key out of order
  "missed" appears in the status line when a rep goes quiet before every step was pressed

What it reads: key and mouse-button presses on your own machine, to draw them. Nothing is written to disk
and nothing is sent anywhere. It never touches the game process or sends input; it is the same kind of
thing as a stream input overlay. The tracking logic (KeyTracker) has no GUI dependency and is unit-tested.
"""

import time

DOUBLE_SECONDS = 0.07   # two presses of one key this close are a bounce or an accident
REP_IDLE_SECONDS = 2.5  # silence this long ends a rep; unmet steps are reported as missed

# (label, pynput name, width in key units). Mouse buttons are drawn as keys named mouse_*.
ROWS = [
    [("Esc", "esc", 1.0), ("F1", "f1", 1.0), ("F2", "f2", 1.0), ("F3", "f3", 1.0), ("F4", "f4", 1.0),
     ("F5", "f5", 1.0), ("F6", "f6", 1.0), ("F7", "f7", 1.0), ("F8", "f8", 1.0)],
    [("`", "`", 1.0)] + [(c, c, 1.0) for c in "1234567890"] + [("Bksp", "backspace", 1.6)],
    [("Tab", "tab", 1.5)] + [(c.upper(), c, 1.0) for c in "qwertyuiop"],
    [("Caps", "caps_lock", 1.8)] + [(c.upper(), c, 1.0) for c in "asdfghjkl"] + [("Enter", "enter", 1.7)],
    [("Shift", "shift", 2.3)] + [(c.upper(), c, 1.0) for c in "zxcvbnm"],
    [("Ctrl", "ctrl_l", 1.4), ("Alt", "alt_l", 1.2), ("Space", "space", 5.0)],
    [("LMB", "mouse_left", 1.6), ("MMB", "mouse_middle", 1.6), ("RMB", "mouse_right", 1.6), ("M4", "mouse_x1", 1.2), ("M5", "mouse_x2", 1.2)],
]
ALIASES = {"shift_l": "shift", "shift_r": "shift", "ctrl_r": "ctrl_l", "ctrl": "ctrl_l", "alt_r": "alt_l",
           "alt": "alt_l", "alt_gr": "alt_l", "return": "enter"}


def normal(name):
    name = str(name).lower()
    return ALIASES.get(name, name)


class KeyTracker:
    """Classifies each press. Pure logic: feed it presses with a timestamp, read back a verdict."""

    def __init__(self, binds, expected=None, clock=time.perf_counter):
        self.binds = {a: normal(k) for a, k in binds.items()}
        self.bound = set(self.binds.values())
        self.names = {}
        for action, key in self.binds.items():
            self.names.setdefault(key, action)
        self.expected = [(a, normal(self.binds[a])) for a in (expected or []) if a in self.binds]
        self.clock = clock
        self.index = 0
        self.last = {}
        self.last_press = None

    def next_expected(self):
        if self.index < len(self.expected):
            return self.expected[self.index][1]
        return None

    def press(self, name, now=None):
        """Returns (verdict, key). verdict: ok | stray | double | order."""
        key = normal(name)
        now = self.clock() if now is None else now
        self.last_press = now
        previous = self.last.get(key)
        self.last[key] = now
        if previous is not None and now - previous <= DOUBLE_SECONDS:
            return "double", key
        if key not in self.bound:
            return "stray", key
        if not self.expected:
            return "ok", key
        if key == self.next_expected():
            self.index += 1
            return "ok", key
        return "order", key

    def missed(self, now=None):
        """If the rep has gone quiet with steps unpressed, return their action names and restart the rep."""
        now = self.clock() if now is None else now
        if self.last_press is None or now - self.last_press < REP_IDLE_SECONDS:
            return []
        gone = [a for a, _ in self.expected[self.index:]]
        self.index = 0
        self.last_press = None
        return gone


COLORS = {"idle": "#1d2230", "bound": "#16343f", "ok": "#2ecc71", "next": "#f1c40f",
          "stray": "#ff8c1a", "double": "#e03030", "order": "#e03030", "text": "#e8ecf4"}
FLASH_MS = 450
UNIT = 38


def run(binds, drill=None):
    try:
        import tkinter as tk
        from pynput import keyboard, mouse
    except ImportError:
        print("keys needs pynput (pip install pynput) and tkinter")
        return 2
    tracker = KeyTracker(binds, drill.steps if drill else None)
    root = tk.Tk()
    root.title("Keystroke overlay")
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.88)
    root.configure(bg="#0b0e14")
    width = int(UNIT * 15.2)
    height = UNIT * len(ROWS) + 70
    canvas = tk.Canvas(root, width=width, height=height, bg="#0b0e14", highlightthickness=0)
    canvas.pack()
    rects = {}
    for r, row in enumerate(ROWS):
        x = 6
        for label, key, w in row:
            action = tracker.names.get(key)
            shown = f"{label}\n{action}" if action else label
            rect = canvas.create_rectangle(x, 6 + r * UNIT, x + w * UNIT - 4, 6 + r * UNIT + UNIT - 4,
                                           fill=COLORS["bound"] if action else COLORS["idle"],
                                           outline="#3a4256", width=1)
            canvas.create_text(x + (w * UNIT - 4) / 2, 6 + r * UNIT + (UNIT - 4) / 2, text=shown,
                               fill=COLORS["text"], font=("Segoe UI", 7 if action else 9), justify="center")
            rects[key] = (rect, COLORS["bound"] if action else COLORS["idle"])
            x += w * UNIT
    status = canvas.create_text(8, height - 40, anchor="w", text="Press keys. Drag to move.", fill=COLORS["text"],
                                font=("Segoe UI", 10, "bold"))
    detail = canvas.create_text(8, height - 18, anchor="w", text="", fill="#9aa3b5", font=("Segoe UI", 9))
    events = []

    def paint(key, color, hold_until=None):
        if key in rects:
            canvas.itemconfig(rects[key][0], fill=color)

    def restore(key):
        if key in rects:
            canvas.itemconfig(rects[key][0], fill=COLORS["next"] if key == tracker.next_expected() else rects[key][1])

    def handle(name):
        verdict, key = tracker.press(name)
        events.append((verdict, key))
        color = COLORS["ok" if verdict == "ok" else verdict]
        paint(key, color)
        root.after(FLASH_MS, lambda: restore(key))
        text = {"ok": "ok", "stray": "stray key (not in your binds)", "double": "double press",
                "order": "bound key, but not the next step"}[verdict]
        canvas.itemconfig(status, text=f"{key}: {text}")
        nxt = tracker.next_expected()
        if nxt:
            paint(nxt, COLORS["next"])
            canvas.itemconfig(detail, text=f"next: {nxt}")

    def tick():
        gone = tracker.missed()
        if gone:
            canvas.itemconfig(status, text="missed: " + ", ".join(gone))
        root.after(250, tick)

    def on_key(k):
        name = getattr(k, "char", None) or getattr(k, "name", str(k))
        root.after(0, handle, name)

    def on_click(_x, _y, button, pressed):
        if pressed:
            root.after(0, handle, f"mouse_{button.name}")

    drag = {}
    root.bind("<ButtonPress-1>", lambda e: drag.update(x=e.x, y=e.y))
    root.bind("<B1-Motion>", lambda e: root.geometry(f"+{root.winfo_x() + e.x - drag['x']}+{root.winfo_y() + e.y - drag['y']}"))
    root.bind("<Escape>", lambda e: root.destroy())
    listeners = [keyboard.Listener(on_press=on_key), mouse.Listener(on_click=on_click)]
    for listener in listeners:
        listener.start()
    nxt = tracker.next_expected()
    if nxt:
        paint(nxt, COLORS["next"])
    root.after(250, tick)
    try:
        root.mainloop()
    finally:
        for listener in listeners:
            listener.stop()
    return 0
