"""Exercise recorder callbacks with fake listeners; never inject desktop input."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from keystroke_lab import recorder
from keystroke_lab.bind_profiles import BindMap, BindProfile, Binding


class CapturePrivacyTests(unittest.TestCase):
    def test_standalone_recorder_uses_focus_chat_alternates_and_verified_binds(self):
        listeners = []
        class Listener:
            def __init__(self, **callbacks):
                self.callbacks = callbacks
                listeners.append(self)
            def start(self): pass
            def stop(self): pass
        fake = types.SimpleNamespace(keyboard=types.SimpleNamespace(Listener=Listener),
                                     mouse=types.SimpleNamespace(Listener=Listener))
        focus = [False]
        profile = BindProfile('p', 1, (
            Binding('wall', ('f',), verified=True),
            Binding('reload', ('mouse_middle',), verified=True),
            Binding('crouch', ('mouse_x2',), verified=True),
            Binding('chat', ('y',), 'ui', True),
            Binding('swap_weapon', ('o',), verified=False)))

        def exercise(_):
            k, m = (l.callbacks for l in listeners)
            def press(key): k['on_press'](types.SimpleNamespace(char=key, vk=None, name=key))
            def release(key): k['on_release'](types.SimpleNamespace(char=key, vk=None, name=key))
            press('f')                      # browser: dropped
            focus[0] = True
            press('f'); press('f'); release('f')  # one physical press
            press('o'); release('o')        # unverified: dropped
            press('y'); release('y')        # alternate chat opener
            press('f'); release('f')        # chat text: dropped
            focus[0] = False
            press('f'); release('f')
            focus[0] = True
            press('f'); release('f')        # chat remains open after Alt-Tab
            press('y'); release('y')
            for button in ('middle', 'x2'):
                m['on_click'](0, 0, types.SimpleNamespace(name=button), True)
                m['on_click'](0, 0, types.SimpleNamespace(name=button), False)
            m['on_scroll'](0, 0, 1, 0)      # horizontal wheel: no fake wheel_down
            raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as d, patch.dict('sys.modules', {'pynput': fake}), \
             patch('keystroke_lab.keyboard_overlay.game_rect', side_effect=lambda: (0,0,100,100) if focus[0] else None), \
             patch.object(recorder.time, 'sleep', side_effect=exercise):
            path = Path(d)/'inputs.jsonl'
            self.assertEqual(recorder.run(path, BindMap(profile)), 0)
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([e['name'] for e in events], ['f', 'mouse_middle', 'mouse_x2'])
