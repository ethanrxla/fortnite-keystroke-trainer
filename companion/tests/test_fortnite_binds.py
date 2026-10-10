import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from keystroke_lab import fortnite_binds
from keystroke_lab.bind_profiles import ProfileStore
from keystroke_lab.keyboard_overlay import KeyTracker, key_name

INI = """[/Script/Engine.InputSettings]
ActionMappings=(ActionName="Jump",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=SpaceBar)
ActionMappings=(ActionName="Sprint",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=One)
ActionMappings=(ActionName="Jump",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=MouseScrollDown)
ActionMappings=(ActionName="Jump",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=Gamepad_FaceButton_Bottom)
ActionMappings=(ActionName="Edit",bShift=True,bCtrl=False,bAlt=False,bCmd=False,Key=E)
ActionMappings=(ActionName="Weapon Slot 1",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=Two)
ActionMappings=(ActionName="Unknown Thing",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=K)
AxisMappings=(AxisName="MoveForward",Scale=1.000000,Key=E)
AxisMappings=(AxisName="MoveForward",Scale=-1.000000,Key=D)
AxisMappings=(AxisName="MoveRight",Scale=-1.000000,Key=S)
AxisMappings=(AxisName="MoveRight",Scale=1.000000,Key=F)
"""


class FortniteBinds(unittest.TestCase):
    def test_parses_actions_axes_and_skips_gamepad_and_combos(self):
        found, skipped = fortnite_binds.parse_text(INI)
        self.assertEqual(found["jump"], ["space", "wheel_down"])
        self.assertEqual(found["sprint"], ["1"])
        self.assertEqual(found["slot1"], ["2"])
        self.assertEqual((found["forward"], found["back"], found["left"], found["right"]), (["e"], ["d"], ["s"], ["f"]))
        self.assertNotIn("edit", found)
        self.assertTrue(any("Gamepad" in s for s in skipped))
        self.assertTrue(any("Unknown Thing" in s for s in skipped))

    def test_merge_keeps_calibrated_actions_and_unbinds_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "keybinds.json"
            ini = Path(folder) / "Input.ini"
            ini.write_text(INI)
            store = ProfileStore(path)
            store.update("jump", ["mouse_x1"], "move", verified=True)
            found, _, used = fortnite_binds.read_binds([ini, Path(folder) / "missing.ini"])
            self.assertEqual(used, [ini])
            changed = store.merge(fortnite_binds.to_bindings(found))
            self.assertNotIn("jump", changed)
            self.assertIn("forward", changed)
            primary = store.snapshot.primary()
            self.assertEqual((primary["jump"], primary["forward"], primary["swap_weapon"]), ("mouse_x1", "e", "2"))
            # ESDF movement now reads as bound, not stray, and stays ungraded until calibrated.
            tracker = KeyTracker(store.snapshot, ["edit"])
            self.assertEqual(tracker.press("e", 0)[0], "ok")
            self.assertEqual(tracker.press("f", 0.1)[0], "ok")
            self.assertEqual(store.merge(fortnite_binds.to_bindings(found)), [])
            self.assertEqual(json.loads(path.read_text())["version"], 1)

    def test_run_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / "Input.ini"
            ini.write_text(INI)
            store = ProfileStore(Path(folder) / "keybinds.json")
            self.assertEqual(fortnite_binds.run(store, [ini]), 0)
            self.assertFalse(store.path.exists())
            self.assertEqual(fortnite_binds.run(store, [Path(folder) / "none.ini"]), 1)


class PhysicalKeys(unittest.TestCase):
    def test_modifiers_do_not_change_the_key(self):
        shifted_one = SimpleNamespace(vk=0x31, char="!")
        ctrl_w = SimpleNamespace(vk=0x57, char="\x17")
        tilde = SimpleNamespace(vk=0xC0, char="~")
        self.assertEqual(key_name(shifted_one, "win32"), "1")
        self.assertEqual(key_name(ctrl_w, "win32"), "w")
        self.assertEqual(key_name(tilde, "win32"), "`")
        self.assertEqual(key_name(SimpleNamespace(vk=None, char="q"), "linux"), "q")
        self.assertEqual(key_name(SimpleNamespace(vk=0x57, char="\x17", name="w"), "linux"), "w")
        self.assertEqual(key_name(SimpleNamespace(char=None, name="shift_r"), "win32"), "shift_r")

    def test_legacy_reload_keeps_confirmed_sprint(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "keybinds.json"
            path.write_text(json.dumps({"edit": "g"}))
            store = ProfileStore(path, confirm_sprint=True)
            self.assertEqual(store.snapshot.primary()["sprint"], "1")
            path.write_text(json.dumps({"edit": "c"}))
            self.assertEqual(store.refresh().primary()["sprint"], "1")
            self.assertIn("1", KeyTracker(store.snapshot).bound)


if __name__ == "__main__":
    unittest.main()
