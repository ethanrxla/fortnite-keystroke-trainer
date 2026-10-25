"""Privacy gate for passive gameplay input; UI controls are never recorded.

Besides the Enter/Esc latches, a cadence detector (typing_detector.TypingDetector) closes the gate on text entry the
latches cannot see: party chat, search boxes, chat opened with the mouse. When it fires, `revoked_from` is the start of
the burst, so the overlay can drop the burst's first presses that were already let through.
"""
import threading
import time

from .typing_detector import TypingDetector


class GameplayInputGate:
    # A latch can stick: Esc or Enter closed by the mouse leaves it "open", and every press after that is dropped
    # (2026-10-25: a whole session recorded nothing). After STALE_S seconds latched, STALE_PRESSES presses in a row that
    # the typing detector reads as gameplay, not typing, release it.
    STALE_S = 20.0
    STALE_PRESSES = 8

    def __init__(self, profile=None, clock=time.perf_counter):
        self.clock = clock
        self.typing = TypingDetector(())
        self.typing_until = 0.0
        self.revoked_from = None
        self.focused = False
        self.menu = False
        self.chat = False
        self.latched_at = 0.0
        self.stale_presses = 0
        self.generation = 0
        self._held_controls = set()
        self._lock = threading.RLock()
        self.chat_keys = {'enter', 'return'}
        self.configure(profile)

    def configure(self, profile):
        """Privacy suppression includes alternate chat binds, even pending calibration.

        This is a transition guard, not a detector of Fortnite's actual UI. Starting
        while chat is already open or opening it with a mouse still needs a fresh
        UI observation before recording can be considered privacy-verified.
        """
        profile = getattr(profile, 'profile', profile)
        with self._lock:
            self.chat_keys = {'enter', 'return'} | {
                key for b in getattr(profile, 'bindings', ()) if b.action == 'chat'
                for key in b.keys}
            self.typing = TypingDetector({key for b in getattr(profile, 'bindings', ()) for key in b.keys})
            self.typing_until = 0.0
            self.generation += 1

    def invalidate(self):
        with self._lock:
            self.generation += 1

    def focus(self, focused):
        with self._lock:
            if self.focused != bool(focused):
                self.focused = bool(focused)
                self.generation += 1
                self._held_controls.clear()
                # Alt-tab does not close Fortnite chat. Keep both UI latches.

    def press(self, key, focused, now=None):
        now = self.clock() if now is None else now
        with self._lock:
            self.focus(focused)
            if key in {'cmd', 'cmd_l', 'cmd_r', 'windows'}:
                self.focus(False)
                return None
            if key in {'esc', 'escape'} | self.chat_keys:
                if self.focused and key not in self._held_controls:
                    self._held_controls.add(key)
                    if key in {'esc', 'escape'}:
                        if self.chat:
                            self.chat = False
                        else:
                            self.menu = not self.menu
                    elif self.typing_until > now and not self.chat:
                        # Enter while typing that the latch never saw open (mouse-opened chat): the message was sent.
                        self.typing_until = 0.0
                        self.typing.reset()
                    elif not self.menu:
                        self.chat = not self.chat
                    self.latched_at = now
                    self.stale_presses = 0
                    self.generation += 1
                return None
            if self.focused and (self.menu or self.chat) and now - self.latched_at >= self.STALE_S:
                if self.typing.press(key, now):
                    self.stale_presses = 0
                else:
                    self.stale_presses += 1
                    if self.stale_presses >= self.STALE_PRESSES:
                        self.menu = self.chat = False
                        self.stale_presses = 0
                        self.typing.reset()
                        self.generation += 1
                return None
            if self.focused and not self.menu and not self.chat and self.typing.press(key, now):
                if self.typing_until <= now:
                    self.revoked_from = self.typing.burst_start()
                    self.generation += 1
                self.typing_until = now + TypingDetector.IDLE_S
                return None
            return self.generation if self.active else None

    def release(self, key):
        with self._lock:
            self._held_controls.discard(key)

    def token(self, focused):
        with self._lock:
            self.focus(focused)
            return self.generation if self.active else None

    @property
    def active(self):
        return self.focused and not self.menu and not self.chat and self.clock() >= self.typing_until

    def accepts(self, generation):
        with self._lock:
            return self.active and generation == self.generation
