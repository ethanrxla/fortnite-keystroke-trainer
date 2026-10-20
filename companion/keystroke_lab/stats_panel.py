"""A small session-stats strip over the game: unobserved confirms, input flags and edit-pattern results.

    python -m keystroke_lab stats-panel        (autostart launches it with the overlay)

It sits in the left column between the edit guide and keyboard. The guide reserves its scaled slot through
overlay_layout.py; the stats panel hides when the game window is too short to fit all three without overlap. It is
click-through, takes no input, shows only while the Fortnite window is focused, and redraws from a background worker
that reads the session files and the player store every few seconds (never on the Tk thread). Numbers come from
session_stats.py; nothing here writes anywhere.
"""

import json
import pathlib
import sys

from .keyboard_overlay import BOTTOM_MARGIN, LEFT_MARGIN, ROWS, game_rect, make_click_through, exclude_from_capture, single_instance
from .overlay_layout import STATS_SLOT_GAP, units, edit_guide_lift, BASE_STATS_HEIGHT, BASE_UNIT

REFRESH_S = 3.0
PLACE_MS = 250
BASE_W = 380
TOP_KEEP = 0.12                                 # never above this fraction of the game window (game-mode banner)
GAP = 8
COLOURS = {"bg": "#121820", "edge": "#2f3b48", "text": "#e8ecf4", "muted": "#9aa7b4", "track": "#233041",
           "meter": "#3987e5", "tip": "#9fd6ff", "clear": "#010203",
           "slip": "#3987e5", "deliberate": "#d95926", "noise": "#199e70", "unsure": "#3a4654"}
SETTINGS = pathlib.Path(__file__).resolve().parents[1] / "overlay-settings.json"


def edit_on_release_setting(path=SETTINGS):
    """Explicit confirmation setting, or None (unknown; never inferred from absence)."""
    try:
        v = json.loads(pathlib.Path(path).read_text()).get("edit_on_release")
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return v if isinstance(v, bool) else None


def overlay_scale(path=SETTINGS):
    try:
        return float(json.loads(pathlib.Path(path).read_text()).get("scale", 1.5))
    except (OSError, ValueError, TypeError, AttributeError):
        return 1.5


def geometry(rect, scale=1.5):
    """(x, y, w, h) for the panel in screen px, or None when the game window is too short for this slot.
    Mirrors keyboard_overlay.place (unit from the scale setting) and edit_window (unit with a fixed 1.5, a 240 px panel)."""
    left, top, right, bottom = rect
    gw, gh = right - left, bottom - top
    u_keys, u_edit = units(gh, scale)
    keys_top = bottom - int(gh * BOTTOM_MARGIN) - 11 * u_keys
    f = min(u_keys, u_edit) / BASE_UNIT
    w, h = round(BASE_W * f), round(BASE_STATS_HEIGHT * f)
    # edit_window reserves this slot by lifting its guide above the stats panel.
    y = keys_top - STATS_SLOT_GAP - h
    guide_top = max(top + 8, bottom - int(gh * BOTTOM_MARGIN) - 11 * u_edit - 240 - GAP
                    - edit_guide_lift(gh, scale, len(ROWS) + 4))
    if y < top + int(gh * TOP_KEEP) or y < guide_top + 240 + GAP:
        return None
    return left + int(gw * LEFT_MARGIN), y, w, h


def lines(snap):
    """The panel's text, row by row, from a session_stats.snapshot: (label, value, meter fraction or None)."""
    m, a, e = snap["missed"], snap["accidental"], snap["edits"]
    if m["steps"] and m["steps"][0].get("release"):
        miss = ("Confirm presses", "not observable: edit on release", None)
    elif m["steps"] and m["steps"][0].get("incomplete_evidence"):
        s = m['steps'][0]
        miss = ('Confirm press not observed', f"{s['not_observed']} / {s['observed_attempts']} · ungraded", None)
    elif m["steps"]:
        s = m["steps"][0]
        name = "confirm after editing" if (s["drill"], s["step"]) == ("edit", "confirm") else f"{s['drill']} · {s['step']}"
        miss = (f"Not observed: {name}", f"{s['missed']} / {s['graded']}", s["missed"] / s["graded"] if s["graded"] else None)
    else:
        miss = ("Keystroke accuracy", "needs a fully observed drill", None)
    acc = (f"Input flags: {a['strays']} stray · {a.get('unmapped', 0)} unmapped · {a['doubles']} rapid",
           ("top " + ", ".join(a["top_keys"])) if a["top_keys"] else "none", None)
    if e["attempts"] >= 1 and e["completed_pct"] is not None:
        bits = [f"{e['completed_pct']}% selection match"]
        if e["followed_pct"] is not None:
            bits.append(f"followed {e['followed_pct']}%")
        if e["travel_vs_ideal"] is not None:
            bits.append(f"travel {e['travel_vs_ideal']}×")
        edit = (f"Shape match ({e['attempts']})", " · ".join(bits), e["completed_pct"] / 100.0)
    else:
        edit = ("Shape match", "no observed attempts yet", None)
    return [miss, acc, edit]


def keystroke_snapshot(events, binds=None, tip=""):
    """The four keystroke rows (stats_rows.py) from this session's events: accuracy, timing, misses by cause, fix next.
    The coach's tip stands in for "Fix next" only when the math has nothing to say yet."""
    import time
    from .keystroke_math import summary
    from .stats_rows import rows
    action_of = {str(k).lower(): a for a, k in (binds or {}).items() if isinstance(k, str)}
    # Drill rows only while a drill is live (a graded step in the last DRILL_LINGER_S); otherwise back to free play.
    steps = [e.get("ts") for e in events if e.get("kind") == "kstep" and isinstance(e.get("ts"), (int, float))]
    if not steps or time.time() - max(steps) > DRILL_LINGER_S:
        events = [e for e in events if e.get("kind") not in ("kstep", "jev")]
    out = rows(summary(events), action_of)
    if tip and out[-1][1] == "keep going":
        out[-1] = ("Fix next", tip[:70], None)
    return {"rows": out}


DRILL_LINGER_S = 30.0

CAUSE_COLOURS = {"wrong_key": "#e03030", "slip": "#e0a030", "early": "#e8d040", "late": "#e8d040",
                 "missing": "#b03050", "modifier": "#9a6ad6", "unmapped": "#5a6a7a"}


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
                latest.put(keystroke_snapshot(events, binds, session_stats.tip(events)))
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
        x0, x1 = 10 * f, w - 10 * f
        for label, value, bar in snap["rows"]:
            canvas.create_text(x0, y, anchor="nw", text=label, fill=COLOURS["muted"], font=("Segoe UI", fs(9)))
            canvas.create_text(x1, y, anchor="ne", text=value, fill=COLOURS["text"], font=("Segoe UI", fs(10), "bold"))
            bar_y = y + 17 * f
            if bar and bar[0] != "none":
                canvas.create_rectangle(x0, bar_y, x1, bar_y + 5 * f, fill=COLOURS["track"], width=0)
            if bar and bar[0] == "meter":
                canvas.create_rectangle(x0, bar_y, x0 + (x1 - x0) * max(0.0, min(bar[1], 1.0)), bar_y + 5 * f,
                                        fill=COLOURS["meter"], width=0)
            elif bar and bar[0] == "centre":          # early (left) / late (right) of your own median
                mid = (x0 + x1) / 2
                end = mid + (x1 - x0) / 2 * bar[1]
                canvas.create_rectangle(min(mid, end), bar_y, max(mid, end) + 2 * f, bar_y + 5 * f,
                                        fill=COLOURS["meter"], width=0)
                canvas.create_rectangle(mid - f, bar_y - 2 * f, mid + f, bar_y + 7 * f, fill=COLOURS["text"], width=0)
            elif bar and bar[0] == "stack":
                total = sum(c for _, c in bar[1]) or 1
                x = x0
                for cause, count in bar[1]:
                    seg = (x1 - x0) * count / total
                    canvas.create_rectangle(x, bar_y, x + max(seg - 2 * f, 1), bar_y + 5 * f,
                                            fill=CAUSE_COLOURS.get(cause, COLOURS["meter"]), width=0)
                    x += seg
            y += 30 * f

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
