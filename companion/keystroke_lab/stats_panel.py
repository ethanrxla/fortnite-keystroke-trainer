"""A small session-stats strip over the game: missed keystrokes, accidental presses (with Jev's verdict) and edit accuracy.

    python -m keystroke_lab stats-panel        (autostart launches it with the overlay)

It sits at the top of the left column, above the highest point the edit guide panel can reach, so the keyboard overlay
and the edit guide never move or overlap it (their code is not touched; their placement maths is mirrored here). It is
click-through, takes no input, shows only while the Fortnite window is focused, and redraws from a background worker
that reads the session files and the player store every few seconds (never on the Tk thread). Numbers come from
session_stats.py; nothing here writes anywhere.
"""

import json
import pathlib
import sys

from .keyboard_overlay import BOTTOM_MARGIN, LEFT_MARGIN, ROWS, game_rect, make_click_through, exclude_from_capture, single_instance

REFRESH_S = 3.0
PLACE_MS = 250
BASE_W, BASE_H, BASE_U = 380, 150, 30          # size at 1080p (u = 30)
TOP_KEEP = 0.12                                 # never above this fraction of the game window (game-mode banner)
GAP = 8
COLOURS = {"bg": "#121820", "edge": "#2f3b48", "text": "#e8ecf4", "muted": "#9aa7b4", "track": "#233041",
           "meter": "#3987e5", "tip": "#9fd6ff", "clear": "#010203",
           "slip": "#3987e5", "deliberate": "#d95926", "noise": "#199e70", "unsure": "#3a4654"}
SETTINGS = pathlib.Path(__file__).resolve().parents[1] / "overlay-settings.json"


def overlay_scale(path=SETTINGS):
    try:
        return float(json.loads(pathlib.Path(path).read_text()).get("scale", 1.5))
    except (OSError, ValueError, TypeError, AttributeError):
        return 1.5


def geometry(rect, scale=1.5):
    """(x, y, w, h) for the panel in screen px, or None when the game window is too short to fit it above the others.
    Mirrors keyboard_overlay.place (unit from the scale setting) and edit_window (unit with a fixed 1.5, a 240 px panel)."""
    left, top, right, bottom = rect
    gw, gh = right - left, bottom - top
    u_keys = max(22, min(42, int(gh / 54 * max(1.0, min(scale, 2.0)))))
    u_edit = max(22, min(42, int(gh / 54 * 1.5)))
    keys_top = bottom - int(gh * BOTTOM_MARGIN) - 11 * u_keys
    edit_top = bottom - int(gh * BOTTOM_MARGIN) - (len(ROWS) + 4) * u_edit - 240 - GAP
    f = min(u_keys, u_edit) / BASE_U
    w, h = round(BASE_W * f), round(BASE_H * f)
    y = min(keys_top, edit_top) - GAP - h
    if y < top + int(gh * TOP_KEEP):
        return None
    return left + int(gw * LEFT_MARGIN), y, w, h


def lines(snap):
    """The panel's text, row by row, from a session_stats.snapshot: (label, value, meter fraction or None)."""
    m, a, e = snap["missed"], snap["accidental"], snap["edits"]
    if m["steps"]:
        s = m["steps"][0]
        name = "confirm after editing" if (s["drill"], s["step"]) == ("edit", "confirm") else f"{s['drill']} · {s['step']}"
        miss = (f"Missed: {name}", f"{s['missed']} / {s['graded']}", s["missed"] / s["graded"])
    else:
        miss = ("Missed keystrokes", "none yet", None)
    acc = (f"Accidental: {a['strays']} strays · {a['doubles']} doubles",
           ("top " + ", ".join(a["top_keys"])) if a["top_keys"] else "none", None)
    if e["attempts"] >= 1 and e["completed_pct"] is not None:
        bits = [f"{e['completed_pct']}% done"]
        if e["followed_pct"] is not None:
            bits.append(f"followed {e['followed_pct']}%")
        if e["travel_vs_ideal"] is not None:
            bits.append(f"travel {e['travel_vs_ideal']}×")
        edit = (f"Edits ({e['attempts']})", " · ".join(bits), e["completed_pct"] / 100.0)
    else:
        edit = ("Edit accuracy", "no edits yet", None)
    return [miss, acc, edit]


def verdict_parts(snap):
    """[(verdict, count)] for the stray bar, in fixed order, zero counts dropped."""
    v = snap["accidental"]["verdicts"]
    return [(k, v.get(k, 0)) for k in ("slip", "deliberate", "noise", "unsure") if v.get(k, 0) > 0]


def run(sessions=None):
    if not single_instance(r"Local\KeystrokeTrainerStats"):
        print("a stats panel is already running")
        return 0
    try:
        import queue
        import threading
        import tkinter as tk
    except ImportError:
        print("stats-panel needs tkinter")
        return 2
    from . import drills, session_stats
    from .store import Store
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa: BLE001  older Windows
            ctypes.windll.user32.SetProcessDPIAware()
    folder = pathlib.Path(sessions) if sessions else session_stats.SESSIONS
    latest = queue.Queue()
    stop = threading.Event()

    def worker():
        store = Store()           # SQLite connections stay on the thread that opened them
        while not stop.is_set():
            try:
                binds = dict(drills.load_binds())
                events = session_stats.read_events(session_stats.newest_events(folder))
                latest.put(session_stats.snapshot(events, store, binds))
            except Exception as exc:  # noqa: BLE001  a bad read must never take the panel down; try again next tick
                print("stats panel: read failed:", type(exc).__name__, exc)
            stop.wait(REFRESH_S)
        store.close()

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=COLOURS["clear"])
    root.attributes("-transparentcolor", COLOURS["clear"])
    canvas = tk.Canvas(root, bg=COLOURS["clear"], highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    root.withdraw()
    state = {"shown": False, "size": None, "snap": None}

    def draw():
        snap, size = state["snap"], state["size"]
        canvas.delete("all")
        if not snap or not size:
            return
        w, h = size
        f = w / BASE_W
        fs = lambda px: max(7, round(px * f))
        canvas.create_rectangle(0, 0, w - 1, h - 1, fill=COLOURS["bg"], outline=COLOURS["edge"])
        canvas.create_text(10 * f, 8 * f, anchor="nw", text="SESSION STATS", fill=COLOURS["text"],
                           font=("Segoe UI", fs(11), "bold"))
        y = 30 * f
        for n, (label, value, frac) in enumerate(lines(snap)):
            canvas.create_text(10 * f, y, anchor="nw", text=label, fill=COLOURS["text"], font=("Segoe UI", fs(10)))
            canvas.create_text(w - 10 * f, y, anchor="ne", text=value, fill=COLOURS["muted"], font=("Segoe UI", fs(9)))
            bar_y = y + 17 * f
            if n == 1:
                parts, total = verdict_parts(snap), sum(c for _, c in verdict_parts(snap))
                x = 10 * f
                for verdict, count in parts:
                    seg = (w - 20 * f) * count / total - 2 * f
                    canvas.create_rectangle(x, bar_y, x + max(seg, 1), bar_y + 5 * f, fill=COLOURS[verdict], width=0)
                    x += seg + 2 * f
                if not parts:
                    canvas.create_rectangle(10 * f, bar_y, w - 10 * f, bar_y + 5 * f, fill=COLOURS["track"], width=0)
            else:
                canvas.create_rectangle(10 * f, bar_y, w - 10 * f, bar_y + 5 * f, fill=COLOURS["track"], width=0)
                if frac:
                    canvas.create_rectangle(10 * f, bar_y, 10 * f + (w - 20 * f) * min(frac, 1.0), bar_y + 5 * f,
                                            fill=COLOURS["meter"], width=0)
            y += 30 * f
        if snap["tip"]:
            canvas.create_text(10 * f, y, anchor="nw", width=w - 20 * f, text=snap["tip"][:140], fill=COLOURS["tip"],
                               font=("Segoe UI", fs(9)))

    def tick():
        try:
            while True:
                state["snap"] = latest.get_nowait()
                draw()
        except queue.Empty:
            pass
        rect = game_rect()
        place = geometry(rect, overlay_scale()) if rect else None
        if place is None:
            if state["shown"]:
                root.withdraw()
                state["shown"] = False
        else:
            x, y, w, h = place
            root.geometry(f"{w}x{h}+{x}+{y}")
            if state["size"] != (w, h):
                state["size"] = (w, h)
                draw()
            if not state["shown"]:
                root.deiconify()
                make_click_through(root)
                exclude_from_capture(root)
                state["shown"] = True
        root.after(PLACE_MS, tick)

    threading.Thread(target=worker, daemon=True, name="stats-panel-reader").start()
    root.after(50, tick)
    print("stats panel running (Ctrl+C here to stop)")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    return 0
