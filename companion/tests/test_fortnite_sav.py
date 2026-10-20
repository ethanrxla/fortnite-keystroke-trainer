import struct
import tempfile
import pathlib
import unittest
import zlib

from keystroke_lab import fortnite_binds as fb


def fs(text):
    data = text.encode() + b"\0"
    return struct.pack("<i", len(data)) + data


def mapping(action, key1, key2="None", scale=None):
    out = fs("ActionName") + fs("NameProperty") + b"\0" * 9 + fs(action)
    out += fs("KeyBind1") + fs("StructProperty") + fs("Key") + fs("/Script/InputCore") + fs("KeyName") + fs("NameProperty") + fs(key1)
    out += fs("KeyBind2") + fs("StructProperty") + fs("Key") + fs("/Script/InputCore") + fs("KeyName") + fs("NameProperty") + fs(key2)
    if scale is not None:
        out += fs("InputScale") + fs("FloatProperty") + struct.pack("<iiB", 4, 0, 0) + struct.pack("<f", scale)
    return out + fs("None")


def save(*mappings, compressed=True):
    raw = fs("UserBindingsPerSubGame") + fs("ESubGame::Invalid") + fs("UserActionBindings") + mapping("Reload", "R")
    raw += fs("ESubGame::Athena") + fs("UserActionBindings") + b"".join(mappings) + fs("CustomGamepadActionBindings")
    raw += mapping("Fire", "Gamepad_RightTrigger")
    return b"ECFD" + struct.pack("<iii", 1, 1, len(raw)) + zlib.compress(raw) if compressed else raw


class SavImportTest(unittest.TestCase):
    def test_athena_user_binds_win_over_the_default_section(self):
        found, _ = fb.parse_sav(fb.decode_sav(save(mapping("Reload", "MiddleMouseButton"), mapping("HotbarKeyF1", "F"),
                                                     mapping("HotbarKeyF5", "T"), mapping("PushToTalk", "G"))))
        self.assertEqual(found["reload"], ["mouse_middle"])
        self.assertEqual(found["wall"], ["f"])
        self.assertEqual(found["trap"], ["t"])
        self.assertEqual(found["push_to_talk"], ["g"])

    def test_axis_sign_separates_directions(self):
        found, _ = fb.parse_sav(fb.decode_sav(save(mapping("MoveForward", "W", scale=1.0), mapping("MoveRight", "A", scale=-1.0),
                                                     mapping("MoveForward", "S", scale=-1.0), mapping("MoveRight", "D", scale=1.0))))
        self.assertEqual((found["forward"], found["left"], found["back"], found["right"]), (["w"], ["a"], ["s"], ["d"]))

    def test_alternates_gamepad_and_duplicates(self):
        found, skipped = fb.parse_sav(fb.decode_sav(save(mapping("BuildingEditReset", "MouseScrollDown", "MouseScrollDown"),
                                                           mapping("Crouch", "ThumbMouseButton2", "K"),
                                                           mapping("BiplaneBoost", "SpaceBar"), compressed=False)))
        self.assertEqual(found["reset"], ["wheel_down"])
        self.assertEqual(found["crouch"], ["mouse_x2", "k"])
        self.assertNotIn("fire", found)                 # gamepad section after the user bindings is ignored
        self.assertIn("action BiplaneBoost", skipped)

    def test_no_athena_section(self):
        self.assertEqual(fb.parse_sav(fs("nothing here"))[0], {})

    def test_read_sav_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "ClientSettings.Sav"
            path.write_bytes(save(mapping("Jump", "SpaceBar")))
            self.assertEqual(fb.read_sav(path)[0], {"jump": ["space"]})


if __name__ == "__main__":
    unittest.main()


class SavSyncTest(unittest.TestCase):
    def test_imports_once_per_change(self):
        from keystroke_lab.bind_profiles import ProfileStore
        with tempfile.TemporaryDirectory() as d:
            sav = pathlib.Path(d) / "ClientSettings.Sav"
            sav.write_bytes(save(mapping("Reload", "MiddleMouseButton"), mapping("PushToTalk", "G")))
            store = ProfileStore(pathlib.Path(d) / "keybinds.json", confirm_sprint=False)
            sync = fb.SavSync(store, files=lambda: [sav])
            self.assertEqual(sorted(sync.poll()), ["push_to_talk", "reload"])
            self.assertEqual(sync.poll(), [])                    # unchanged file: no re-import
            b = {x.action: x for x in store.snapshot.bindings}
            self.assertEqual((b["reload"].keys, b["reload"].verified), (("mouse_middle",), True))
