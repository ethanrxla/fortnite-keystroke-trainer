"""Focused gameplay capture state, independent of the edit observer."""
class InputGate:
    def __init__(self):
        self.paused = False
        self.text_entry = False
        self.held = set()

    def focus_lost(self):
        self.text_entry = False
        self.held.clear()

    def release(self, key):
        self.held.discard(key)

    def press(self, key, focused):
        if not focused:
            self.focus_lost()
            return False
        repeated = key in self.held
        self.held.add(key)
        if key == "enter":
            if not repeated:self.text_entry = not self.text_entry
            return False
        if key == "esc":self.text_entry = False
        if key == "f8":
            if not repeated:self.paused = not self.paused
            return False
        return self.allowed(focused)

    def allowed(self, focused):
        return bool(focused) and not self.paused and not self.text_entry
