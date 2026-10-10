"""Passive local keyboard overlay with calibrated profiles and explicit-drill feedback.

Unmapped inputs and held repeats remain neutral. Only verified expected actions can
be graded inside a selected drill. Per-player profile revisions invalidate prior
analysis. Capture queues inputs; asynchronous workers handle logging and AI.
This app never injects game inputs or reads game process memory.
"""

import json
import pathlib
import sys
import time

from .analysis import Analyzer
from . import bind_server, drills
from .bind_profiles import BindProfile, ProfileStore
from .habits import Habits
from .jev_client import JevClient
from .input_analysis import KeystrokeAnalyzer, InputEvent

NEWLINE = chr(10)
DOUBLE_SECONDS = 0.07   # two presses of one key this close are a bounce or an accident
REP_IDLE_SECONDS = 2.5  # silence this long ends a rep; unmet steps are reported as missed
SLIP_SECONDS = 0.6      # a stray then a neighbouring bound key within this long is a slip

# (label, pynput name, width in key units). Mouse buttons are drawn as keys named mouse_*.
ROWS = [
    [("Esc", "esc", 1.0), ("F1", "f1", 1.0), ("F2", "f2", 1.0), ("F3", "f3", 1.0), ("F4", "f4", 1.0),
     ("F5", "f5", 1.0), ("F6", "f6", 1.0), ("F7", "f7", 1.0), ("F8", "f8", 1.0)],
    [("`", "`", 1.0)] + [(c, c, 1.0) for c in "1234567890"] + [("Bksp", "backspace", 1.6)],
    [("Tab", "tab", 1.5)] + [(c.upper(), c, 1.0) for c in "qwertyuiop"],
    [("Caps", "caps_lock", 1.8)] + [(c.upper(), c, 1.0) for c in "asdfghjkl"] + [("Enter", "enter", 1.7)],
    [("Shift", "shift", 2.3)] + [(c.upper(), c, 1.0) for c in "zxcvbnm"],
    [("Ctrl", "ctrl_l", 1.4), ("Alt", "alt_l", 1.2), ("Space", "space", 5.0)],
    [("LMB", "mouse_left", 1.6), ("MMB", "mouse_middle", 1.6), ("RMB", "mouse_right", 1.6),
     ("M4", "mouse_x1", 1.2), ("M5", "mouse_x2", 1.2),
     ("WU", "wheel_up", 1.2), ("WD", "wheel_down", 1.2)],
]
ALIASES = {"shift_l": "shift", "shift_r": "shift", "ctrl_r": "ctrl_l", "ctrl": "ctrl_l", "alt_r": "alt_l",
           "alt": "alt_l", "alt_gr": "alt_l", "return": "enter"}


# Keys that are never game input: screenshots, Windows key, media and volume, lock keys. Ignored everywhere.
IGNORED_KEYS = {"print_screen", "scroll_lock", "pause", "num_lock", "menu", "cmd", "cmd_l", "cmd_r",
                "media_play_pause", "media_next", "media_previous", "media_volume_up", "media_volume_down",
                "media_volume_mute", "insert"}


def normal(name):
    name = str(name).lower()
    return ALIASES.get(name, name)


# Windows virtual-key codes of the punctuation keys, as their unshifted US-layout names.
OEM_VK = {0xC0: "`", 0xBD: "-", 0xBB: "=", 0xDB: "[", 0xDD: "]", 0xDC: "\\", 0xBA: ";", 0xDE: "'",
          0xBC: ",", 0xBE: ".", 0xBF: "/"}


def key_name(k, platform=sys.platform):
    """The physical key a pynput event came from, in the same naming as keybinds.json.

    pynput's `char` has modifiers applied, so with sprint (Shift) held '1' arrives as '!', and with crouch (Ctrl)
    held 'w' arrives as a control character: bound keys then read as unmapped. Fortnite binds physical keys, so on
    Windows the virtual-key code decides for letters, digits and punctuation; `char` is the fallback elsewhere.
    """
    vk = getattr(k, "vk", None)
    if platform == "win32" and isinstance(vk, int):
        if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if vk in OEM_VK:
            return OEM_VK[vk]
    char = getattr(k, "char", None)
    if char and char.isprintable():
        return char
    return getattr(k, "name", None) or str(k)


class KeyTracker:
    """Classifies each press. Pure logic: feed it presses with a timestamp, read back a verdict."""

    def __init__(self, binds, expected=None, clock=time.perf_counter, habits=None):
        self.clock, self.habits = clock, habits
        self.expected_actions = list(expected or [])
        self.index, self.last_press = 0, None
        self.last, self.held = {}, set()
        self.set_profile(binds)

    def set_profile(self, binds):
        self.profile_revision = binds.revision if isinstance(binds, BindProfile) else 0
        self.profile_id = binds.profile_id if isinstance(binds, BindProfile) else 'explicit'
        self.binds = binds.primary() if isinstance(binds, BindProfile) else dict(binds)
        self.actions, self.verified_actions = {}, set()
        entries = binds.bindings if isinstance(binds, BindProfile) else []
        if entries:
            for binding in entries:
                for key in binding.keys:
                    self.actions.setdefault(normal(key), []).append(binding.action)
                if binding.verified:
                    self.verified_actions.add(binding.action)
        else:
            for action, key in self.binds.items():
                self.actions.setdefault(normal(key), []).append(action)
                self.verified_actions.add(action)
        self.bound = set(self.actions)
        self.names = {k: '/'.join(dict.fromkeys(a + (' ?' if a not in self.verified_actions else '') for a in v)) for k, v in self.actions.items()}
        # An unverified sequence cannot fairly grade the player's actions.
        self.expected = [(a, normal(self.binds[a])) for a in self.expected_actions if a in self.binds]
        self.grade = bool(self.expected) and all(a in self.verified_actions for a in self.expected_actions)
        self.index, self.last_press = 0, None
        self.last.clear()
        self.held.clear()

    def release(self, name):
        self.held.discard(normal(name))

    def focus_lost(self):
        self.held.clear()
        self.index, self.last_press = 0, None

    def next_expected(self):
        if self.index < len(self.expected):
            return self.expected[self.index][1]
        return None

    def press(self, name, now=None):
        """Returns (verdict, key). verdict: ok | habit (unbound but you use it a lot) | stray | double | order."""
        key = normal(name)
        if key in IGNORED_KEYS:
            return "ignore", key
        now = self.clock() if now is None else now
        if key in self.held:
            return 'repeat', key
        if not key.startswith('wheel_'):
            self.held.add(key)
        if key not in self.bound:
            if self.habits is not None:
                self.habits.record(key, int(now // 60))
                if self.habits.is_habit(key):
                    return 'habit', key
            return 'unmapped', key
        if not self.grade:
            return 'ok', key
        # Ordinary movement/combat/UI keys cannot interrupt a build/edit drill sequence.
        relevant = [a for a in self.actions[key] if a in self.expected_actions]
        if not relevant:
            return 'ok', key
        self.last_press = now
        if self.index < len(self.expected) and self.expected[self.index][0] in relevant:
            self.index += 1
            return 'ok', key
        return 'order', key

    def missed(self, now=None):
        """If the rep has gone quiet with steps unpressed, return their action names and restart the rep."""
        now = self.clock() if now is None else now
        if not self.grade or self.last_press is None or now - self.last_press < REP_IDLE_SECONDS:
            return []
        gone = [a for a, _ in self.expected[self.index:]]
        self.index = 0
        self.last_press = None
        return gone


# --- Which keys sit beside which, and what to say about a mistake ---------------------------------------------

def _key_positions():
    pos = {}
    for r, row in enumerate(ROWS):
        x = 0.0
        for _, key, w in row:
            pos[key] = (x + w / 2.0, r)
            x += w
    return pos


KEY_POS = _key_positions()


def neighbours(key):
    """Keys physically beside this one: same row within 1.7 key units, or the row above or below within 1.2."""
    if key not in KEY_POS or key.startswith("mouse_"):
        return []
    kx, kr = KEY_POS[key]
    out = []
    for other, (ox, orow) in KEY_POS.items():
        if other == key or other.startswith("mouse_"):
            continue
        if (orow == kr and abs(ox - kx) <= 1.7) or (abs(orow - kr) == 1 and abs(ox - kx) <= 1.2):
            out.append(other)
    return out


def explain(verdict, key, tracker, last_stray=None, now=0.0):
    """One short sentence about a press, or an empty string when nothing is wrong. Pure; no I/O."""
    if verdict in ('stray', 'unmapped'):
        return f"Unmapped: '{key}'. Calibrate it if this is a game action."
    if verdict == 'order':
        return f"'{key}' came before the selected drill's expected step."
    return ''



# --- Windows plumbing: find the game window, keep our window click-through and focus-proof --------------------

def foreground_title():
    """Title of the focused window (Windows only; empty elsewhere). Used to log only while you are in the game."""
    if sys.platform != "win32":
        return ""
    import ctypes
    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def in_game(title):
    return "fortnite" in title.lower()


def game_rect():
    """(left, top, right, bottom) of the focused window if it is the Fortnite game client, else None."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    title = foreground_title().lower()
    if "fortnite" not in title or "unreal editor" in title:
        return None
    rect = wintypes.RECT()
    user32.GetWindowRect(handle, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def make_click_through(root):
    if sys.platform != "win32":
        return
    import ctypes
    user32 = ctypes.windll.user32
    handle = user32.GetParent(root.winfo_id()) or root.winfo_id()
    style = user32.GetWindowLongW(handle, -20)
    # layered | transparent (clicks pass through) | no-activate (never takes focus) | tool window (no taskbar)
    user32.SetWindowLongW(handle, -20, style | 0x80000 | 0x20 | 0x8000000 | 0x80)


def exclude_from_capture(root):
    """Hide this window from screen capture (Windows 10 2004+), so an overlay drawn over the game is not read back as game pixels."""
    if sys.platform != "win32":
        return
    import ctypes
    user32 = ctypes.windll.user32
    handle = user32.GetParent(root.winfo_id()) or root.winfo_id()
    user32.SetWindowDisplayAffinity(handle, 0x11)


class SessionLog:
    """Records a play session. Two files: <name>.jsonl keeps bound presses in the recorder format (so analyze,
    review and plan read it), <name>.events.jsonl keeps every verdict with the drill, for insights.

    Only presses made while a Fortnite or UEFN window is focused are written, so typing elsewhere is never stored.
    """

    def __init__(self, base, drill=None, focus=foreground_title, clock=time.perf_counter):
        base = pathlib.Path(base)
        base.parent.mkdir(parents=True, exist_ok=True)
        self.keys = base.with_suffix(".jsonl").open("a", encoding="utf-8")
        self.events = base.with_suffix(".events.jsonl").open("a", encoding="utf-8")
        self.drill = drill.id if drill else None
        self.focus = focus
        self.clock = clock
        self.start = clock()
        import queue, threading
        self.pending = queue.Queue()
        self.writer = threading.Thread(target=self._writer, daemon=True)
        self.writer.start()

    def _emit(self, record):
        # Wall-clock UTC seconds, so collector.py can line these up with the map's KT| log lines.
        self.pending.put(('event', dict(record, ts=round(time.time(), 3))))

    def _writer(self):
        while True:
            kind, record = self.pending.get()
            if kind == 'stop':
                break
            target = self.keys if kind == 'key' else self.events
            target.write(json.dumps(record) + NEWLINE)
            target.flush()


    def write(self, verdict, key, bound):
        if not in_game(self.focus()):
            return False
        t = round(self.clock() - self.start, 4)
        if bound and verdict in ("ok", "order"):
            self.pending.put(("key", {"t": t, "kind": "key", "name": key}))
        self._emit({"t": t, "kind": verdict, "key": key, "drill": self.drill})
        return True

    def tip(self, text):
        self._emit({"t": round(self.clock() - self.start, 4), "kind": "ai_tip", "text": text})

    def missed(self, actions):
        if in_game(self.focus()):
            self._emit({"t": round(self.clock() - self.start, 4), "kind": "missed",
                        "actions": actions, "drill": self.drill})

    def close(self):
        self.pending.put(("stop", None))
        self.writer.join(timeout=5)
        self.keys.close()
        self.events.close()


COLORS = {"idle": "#1d2230", "bound": "#16343f", "ok": "#2ecc71", "habit": "#3b6ea5", "unmapped": "#8196aa", "repeat": "#3b6ea5", "stray": "#8196aa", "double": "#e03030",
          "order": "#e03030", "text": "#e8ecf4", "clear": "#010203"}
FLASH_MS = 350
POLL_MS = 3
KEYS_WIDE = 12.8        # widest row, in key units
BOTTOM_MARGIN = 0.135   # fraction of the game window height kept free for the health bar
LEFT_MARGIN = 0.012


def single_instance(name=r"Local\KeystrokeTrainerOverlay"):
    """False if another overlay already runs on this PC (a named Windows mutex). Several launchers (login watcher,
    a terminal, another tool) may all try to start one; only the first draws, the rest exit quietly."""
    if sys.platform != "win32":
        return True
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, name)
    return ctypes.windll.kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS


def run(binds, drill=None, log_base=None, use_ai=True, serve_port=True, binds_path=None):
    if not single_instance():
        print("an overlay is already running; not starting a second one")
        return 0
    try:
        import queue
        import threading
        import tkinter as tk
        from pynput import keyboard, mouse
    except ImportError:
        print("keys needs pynput (pip install pynput) and tkinter")
        return 2
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    # Separate local observer process: no capture or AI work on the keyboard/display path.
    import subprocess, os, uuid
    os.environ["KT_COACH_SESSION"]=uuid.uuid4().hex
    os.environ["KT_NO_AI"]="0" if use_ai else "1"
    try:
        edit_reference = subprocess.Popen([sys.executable, '-m', 'keystroke_lab.edit_window', str(binds_path or drills.BINDS_FILE)],
            cwd=str(pathlib.Path(__file__).resolve().parents[1]),
            creationflags=0x08000000 if sys.platform == 'win32' else 0)
    except OSError:
        edit_reference = None
    store = ProfileStore(binds_path or drills.BINDS_FILE, confirm_sprint=binds_path is None)
    tracker = KeyTracker(store.snapshot, None, habits=Habits(path=store.path.with_suffix(".habits.json")))
    sequences=([drill.steps]+drill.accepts) if drill else []
    local_analysis=[KeystrokeAnalyzer(store.snapshot,sequences)]
    log = SessionLog(log_base, drill) if log_base else None
    recent_events = []
    habits = tracker.habits
    server = bind_server.start(lambda: store.snapshot.primary(), lambda: habits.habits(), recent_events, binds_file=store.path, store=store) if serve_port else None
    analyzer = Analyzer(tracker, jev=None if use_ai else JevClient(key=""), llm=None if use_ai else (lambda *a: ""))
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=COLORS["clear"])
    root.attributes("-transparentcolor", COLORS["clear"])
    root.withdraw()
    canvas = tk.Canvas(root, bg=COLORS["clear"], highlightthickness=0)
    canvas.pack()
    rects = {}
    ids = {}
    state = {"unit": None, "shown": False, "last_stray": None, "asked": -99.0, "size": (0, 0)}
    incoming = queue.Queue()

    def build(u):
        canvas.delete("all")
        rects.clear()
        width = int(KEYS_WIDE * u) + 8
        top=3*u
        height = len(ROWS) * u + 4 * u
        canvas.config(width=width, height=height)
        for r, row in enumerate(ROWS):
            x = 4
            for label, key, w in row:
                action = tracker.names.get(key)
                fill = COLORS["bound"] if action else COLORS["idle"]
                rect = canvas.create_rectangle(x, 4 + top + r * u, x + w * u - 3, 4 + top + r * u + u - 3, fill=fill, outline="#3a4256")
                canvas.create_text(x + (w * u - 3) / 2, 4 + top + r * u + u * (0.31 if action else 0.48), text=label,
                                   fill=COLORS["text"], font=("Segoe UI", max(9, int(u * 0.38)), "bold"))
                if action:
                    compact = action.split("/")[0].replace("move_", "").replace("edit_confirm", "OK").replace("pickaxe", "axe").replace("sprint", "run")
                    if "/" in action: compact = compact[:4] + "+"
                    canvas.create_text(x + (w * u - 3) / 2, 4 + top + r * u + u * 0.77, text=compact[:6],
                                       fill="#9fd5df", font=("Segoe UI", max(7, int(u * 0.24))))
                rects[key] = (rect, fill)
                x += w * u
        ids["status"] = canvas.create_text(4, 4, anchor="nw", width=width - 8, fill=COLORS["text"],
                                           font=("Segoe UI", max(8, int(u * 0.5)), "bold"), text="")
        ids["tip"] = canvas.create_text(4, 4 + u * 1.5, anchor="nw", width=width - 8, fill="#9fd6ff",
                                        font=("Segoe UI", max(8, int(u * 0.46))), text="")
        state["unit"] = u
        state["size"] = (width, height)

    def flash(key, color):
        if key in rects:
            canvas.itemconfig(rects[key][0], fill=color)
            root.after(FLASH_MS, lambda: canvas.itemconfig(rects[key][0], fill=rects[key][1]))

    def handle(name, now):
        title = foreground_title()
        if not in_game(title) or "unreal editor" in title.lower():
            tracker.focus_lost()
            return
        evidence=local_analysis[0].accept(InputEvent(normal(name),"down",now))
        verdict, key = tracker.press(name, now)
        if verdict == "ignore":
            return
        if log:
            log.write(verdict, key, key in tracker.bound)
        flash(key, COLORS["ok" if verdict == "ok" else verdict])
        text = explain(verdict, key, tracker, state["last_stray"], now)
        if verdict == "unmapped":
            state["last_stray"] = (key, now)
        analyzer.note(key, now)
        recent_events.append({"kind": verdict, "key": key})
        del recent_events[:-50]
        if verdict == "unmapped":
            near = [(k, tracker.names[k]) for k in neighbours(key) if k in tracker.names]
            analyzer.add_stray(key, now, near, evidence)
        if text:
            canvas.itemconfig(ids["status"], text=text)
            root.after(2200, lambda expected=text: canvas.itemconfig(ids["status"], text="") if canvas.itemcget(ids["status"], "text") == expected else None)
        if analyzer.claim(now):

            def work():
                revision = analyzer.profile_revision
                try:
                    findings = analyzer.resolve(now)
                    if log and revision == analyzer.profile_revision:
                        log._emit({"kind": "analysis", "profile_revision": revision, "findings": findings,
                                   "attempts": analyzer.jev.calls, "usage": dict(analyzer.jev.tokens)})
                    incoming.put(("tip", (revision, analyzer.tip(now, tracker.binds))))
                finally:
                    analyzer.release_claim()

            threading.Thread(target=work, daemon=True).start()

    feedback_at=[-float('inf')]
    def refresh_edit_feedback():
        now=time.monotonic()
        if now-feedback_at[0]<.5:return
        feedback_at[0]=now
        try:
            data=json.loads((pathlib.Path(__file__).resolve().parents[1]/'edit-state.json').read_text())
            attempt=data.get('last_attempt') or {}
            if attempt.get('profile_id')!=tracker.profile_id or attempt.get('profile_revision')!=tracker.profile_revision:return
            if time.monotonic()-attempt.get('ended_at',0)>30:return
            text=("Edit observation incomplete" if not attempt.get('complete_observation') else
                  f"Observed target tiles: {round(100*attempt.get('observed_coverage',0))}% | extra: {len(attempt.get('extra_selections',[]))}")
            canvas.itemconfig(ids['tip'],text=text+' | game result unverified')
        except (OSError,ValueError,TypeError):pass

    def poll_once():
        try:
            while True:
                kind, payload = incoming.get_nowait()
                if kind == "key":
                    handle(*payload)
                elif kind == "release":
                    name,at=payload
                    tracker.release(name)
                    local_analysis[0].accept(InputEvent(normal(name),"up",at))
                elif kind == "tip" and payload:
                    revision, text = payload
                    if revision == analyzer.profile_revision and text:
                        canvas.itemconfig(ids["tip"], text=text)
                        if log:
                            log.tip(text)
        except queue.Empty:
            pass
        refresh_edit_feedback()

    calibration_button = tk.Toplevel(root)
    calibration_button.overrideredirect(True)
    calibration_button.attributes('-topmost', True)
    def poll():
        try:poll_once()
        except Exception:
            import traceback
            with (pathlib.Path(__file__).resolve().parents[1]/'keyboard-display-error.log').open('a') as errors:errors.write(traceback.format_exc())
        finally:root.after(POLL_MS,poll)

    calibration_process = [None]
    def calibrate_player():
        if calibration_process[0] is not None and calibration_process[0].poll() is None:
            return
        calibration_process[0] = subprocess.Popen([sys.executable, '-m', 'keystroke_lab.calibration_window', str(store.path)],
            cwd=str(pathlib.Path(__file__).resolve().parents[1]), creationflags=0x08000000 if sys.platform == 'win32' else 0)
    tk.Button(calibration_button, text='Calibrate controls', command=calibrate_player,
              bg='#173945', fg='white', relief='flat', font=('Segoe UI',9)).pack()
    calibration_button.withdraw()

    def place():
        rect = game_rect()
        snapshot = store.refresh()
        if (snapshot.profile_id, snapshot.revision) != (tracker.profile_id, tracker.profile_revision):
            tracker.set_profile(snapshot)
            analyzer.invalidate(snapshot.revision, snapshot.profile_id)
            local_analysis[0]=KeystrokeAnalyzer(snapshot,sequences)
            state["last_stray"] = None
            build(state["unit"] or 20)
        if rect is None:
            tracker.focus_lost()
            if state["shown"]:
                local_analysis[0].accept(InputEvent("","focus_lost",time.perf_counter()))
                root.withdraw()
                calibration_button.withdraw()
                state["shown"] = False
        else:
            left, top, right, bottom = rect
            gw, gh = right - left, bottom - top
            try:
                display_scale = float(json.loads((pathlib.Path(__file__).resolve().parents[1] / "overlay-settings.json").read_text()).get("scale", 1.5))
            except (OSError, ValueError, TypeError):
                display_scale = 1.5
            u = max(22, min(42, int(gh / 54 * max(1.0, min(display_scale, 2.0)))))
            if u != state["unit"]:
                build(u)
            width, height = state["size"]
            root.geometry(f"{width}x{height}+{left + int(gw * LEFT_MARGIN)}+{bottom - height - int(gh * BOTTOM_MARGIN)}")
            calibration_button.geometry(f"140x28+{left + int(gw * LEFT_MARGIN)}+{bottom - height - int(gh * BOTTOM_MARGIN) - 30}")
            if not state["shown"]:
                calibration_button.withdraw()
                root.deiconify()
                make_click_through(root)
                state["shown"] = True
        root.after(250, place)

    def on_key(k):
        if not game_rect():
            return
        incoming.put(("key", (key_name(k), time.perf_counter())))

    def on_release(k):
        incoming.put(('release', (key_name(k), time.perf_counter())))

    def on_click(_x, _y, button, pressed):
        if pressed and not game_rect():
            return
        if pressed:
            incoming.put(('key', (f'mouse_{button.name}', time.perf_counter())))
        else:
            incoming.put(('release', (f'mouse_{button.name}',time.perf_counter())))

    def on_scroll(_x, _y, dx, dy):
        if not game_rect():
            return
        incoming.put(('key', ('wheel_up' if dy > 0 else 'wheel_down', time.perf_counter())))


    build(20)
    listeners = [keyboard.Listener(on_press=on_key, on_release=on_release), mouse.Listener(on_click=on_click, on_scroll=on_scroll)]
    for listener in listeners:
        listener.start()
    root.after(POLL_MS, poll)
    root.after(50, place)
    print("overlay running over the game window (Ctrl+C here to stop)")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if edit_reference is not None and edit_reference.poll() is None:
            edit_reference.terminate()
        for listener in listeners:
            listener.stop()
        habits.save()
        if server:
            server.shutdown()
            server.server_close()
        if log:
            log.close()
    return 0
