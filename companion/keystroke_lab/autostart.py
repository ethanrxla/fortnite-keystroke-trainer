"""Start the keystroke overlay by itself whenever Fortnite starts, and stop it when Fortnite closes.

    python -m keystroke_lab autostart --install     # run the watcher at every Windows login (current user only)
    python -m keystroke_lab autostart --uninstall   # remove it
    python -m keystroke_lab autostart --status
    python -m keystroke_lab autostart               # run the watcher in this window (what the login entry runs)

The watcher is tiny: every few seconds it asks Windows whether the Fortnite client process is running. Only
while it is does the overlay (and its keyboard hook) exist, so nothing listens to your keys when you are not in
the game. Installing writes one value under HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run;
no admin rights, nothing system-wide, and --uninstall removes it.

Limit: this is a program on your PC. A published Fortnite island cannot start software on other players'
computers, so the overlay appears only on machines that have this companion installed.
"""

import ctypes
import os
import pathlib
import subprocess
import sys
import time
import uuid

GAME_PROCESS = "FortniteClient-Win64-Shipping.exe"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "KeystrokeTrainerOverlay"
POLL_SECONDS = 3.0
COMPANION = pathlib.Path(__file__).resolve().parents[1]
CREATE_NO_WINDOW = 0x08000000
GUIDE_MUTEX = r"Local\KeystrokeLabEditReference"


def mutex_running(name):
    if os.name != "nt":
        return False
    handle = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, name)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def spawn_component(module, args=(), env=None):
    """Windowless children retain startup errors locally instead of failing silently."""
    folder = COMPANION / ".runtime"
    folder.mkdir(exist_ok=True)
    path = folder / (module.rsplit(".", 1)[-1] + "-startup.log")
    if path.exists() and path.stat().st_size > 2_000_000:
        path.replace(path.with_suffix(".previous.log"))
    with path.open("ab") as log:
        return subprocess.Popen([pythonw(), "-m", module, *args], cwd=str(COMPANION),
                                env=env, stdout=log, stderr=log,
                                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)


def game_running(lister=None):
    """True when the Fortnite client process exists. `lister` returns the tasklist text (injectable for tests)."""
    if lister is None:
        def lister():
            out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS}", "/NH"], capture_output=True,
                                 text=True, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
            return out.stdout
    try:
        # tasklist cuts image names to 25 characters ("FortniteClient-Win64-Ship"), so match that prefix. The listing is
        # already filtered to the exact image name, so the anti-cheat helper process (same prefix) is not in it.
        return GAME_PROCESS[:25].lower() in lister().lower()
    except Exception:
        return False


def pythonw():
    """The windowless interpreter next to the current one, so the overlay and watcher never open a console."""
    exe = pathlib.Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


class _Group:
    """The overlay, the data collector and (first run only) the calibration window, treated as one child: alive while the
    overlay is, ended together when the game closes."""

    def __init__(self, overlay, collector, calibration=None, stats=None, guide=None, guide_launch=None):
        self.overlay, self.collector, self.calibration, self.stats = overlay, collector, calibration, stats
        self.guide, self.guide_launch = guide, guide_launch
        self.guide_retry_at = 0.0

    def poll(self):
        return self.overlay.poll()

    def maintain(self, now):
        if self.guide_launch and (self.guide is None or self.guide.poll() is not None):
            if now >= self.guide_retry_at and not mutex_running(GUIDE_MUTEX):
                self.guide_retry_at = now + 3.0
                try:
                    self.guide = self.guide_launch()
                except OSError:
                    pass

    def terminate(self):
        for proc in (self.overlay, self.collector, self.calibration, self.stats, self.guide):
            if proc is not None and proc.poll() is None:
                proc.terminate()


def launch_overlay():
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    env = dict(os.environ, KT_COACH_SESSION=uuid.uuid4().hex, KT_GUIDE_SUPERVISED="1")
    env.setdefault("KT_NO_AI", "0")
    overlay = spawn_component("keystroke_lab", ("keys",), env)
    # The collector (collector.py) refuses to start twice, so this is harmless when one is already running.
    collector = subprocess.Popen([pythonw(), "-m", "keystroke_lab", "collect"], cwd=str(COMPANION), creationflags=flags)
    # The session-stats strip (stats_panel.py) is its own window; it refuses to start twice.
    try:
        stats = subprocess.Popen([pythonw(), "-m", "keystroke_lab", "stats-panel"], cwd=str(COMPANION), creationflags=flags)
    except OSError:
        stats = None
    # First entry into the game: if the player's binds are not confirmed yet, open the calibration window over the game.
    try:
        from . import first_run
        calibration = first_run.maybe_launch()
    except Exception:  # noqa: BLE001  calibration must never stop the overlay from starting
        calibration = None
    guide_launch = lambda: spawn_component("keystroke_lab.edit_window", env=env)
    group = _Group(overlay, collector, calibration, stats, guide_launch=guide_launch)
    group.maintain(time.monotonic())
    return group


OVERLAY_MUTEX = r"Local\KeystrokeTrainerOverlay"


def overlay_running():
    """True if an overlay (started by anything) holds the overlay mutex right now."""
    return mutex_running(OVERLAY_MUTEX)


class _Adopted:
    """An overlay that something else started: alive while its mutex exists. The watcher watches it but does not own it."""

    def poll(self):
        return None if overlay_running() else 0

    def __init__(self):
        self.guide = None
        self.retry_at = 0.0

    def maintain(self, now):
        # An externally started keyboard is not proof its guide is alive.
        if now >= self.retry_at and not mutex_running(GUIDE_MUTEX):
            self.retry_at = now + 3.0
            if self.guide is None or self.guide.poll() is not None:
                try:
                    self.guide = spawn_component("keystroke_lab.edit_window")
                except OSError:
                    pass

    def terminate(self):
        if self.guide is not None and self.guide.poll() is None:
            self.guide.terminate()


def single_instance():
    """False if another watcher already runs (a named Windows mutex), so two logins never start two watchers."""
    if os.name != "nt":
        return True
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\KeystrokeTrainerWatcher")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def watch(poll=POLL_SECONDS, lister=None, launch=launch_overlay, sleep=time.sleep, stop=lambda: False, adopt=overlay_running):
    """Run until `stop()`. Starts the overlay when the game appears, ends it when the game goes away or it dies."""
    child = None
    declined_until = 0.0      # an overlay that exits cleanly (code 0) found another one running: do not respawn at once
    while not stop():
        running = game_running(lister)
        now = time.monotonic()
        if running and child is not None and child.poll() is None:
            maintain = getattr(child, "maintain", None)
            if maintain:
                maintain(now)
        if child is not None and child.poll() == 0 and declined_until <= now:
            declined_until = now + 30.0
        if running and (child is None or child.poll() is not None) and adopt():
            if child is not None:
                child.terminate()
            child = _Adopted()          # an overlay is already up (another launcher): watch it, do not start a second
        elif running and (child is None or child.poll() is not None) and now >= declined_until:
            if child is not None:
                child.terminate()
            child = launch()
        elif not running and child is not None:
            child.terminate()
            child = None
        sleep(poll)
    if child is not None:
        child.terminate()


def command():
    return f'"{pythonw()}" "{COMPANION / "autostart.pyw"}"'


def install():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command())
    return command()


def uninstall():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_NAME)
        return True
    except FileNotFoundError:
        return False


def status():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, RUN_NAME)[0]
    except FileNotFoundError:
        return None


def main(args):
    if args.install:
        print("installed; the watcher will start at your next login:", install())
        return 0
    if args.uninstall:
        print("removed" if uninstall() else "was not installed")
        return 0
    if args.status:
        entry = status()
        print("installed:", entry if entry else "no", "| game running now:", game_running())
        return 0
    if not single_instance():
        print("a watcher is already running")
        return 0
    print("watching for Fortnite (Ctrl+C to stop)")
    try:
        watch()
    except KeyboardInterrupt:
        pass
    return 0
