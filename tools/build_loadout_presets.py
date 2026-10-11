"""Armory loadout presets: three shootable slot tiles and a CLEAR tile beside the mod bench, additive (KT27_Preset_*).

    python tools/build_loadout_presets.py [--dry-run]
    (the wall tiles need tools/build_armory_grid.py from 2026-10-11 on: tagged granters and _Track triggers)

Player 2026-10-11: "3 buttons for loadout presets ... attached to a user specifically ... shooting it equips it,
button underneath (4th button) to clear the preset". The tiles are on the east wall left of the Weapon Mod Bench, below
the National Heroes panels; each has a coloured plate, a play-size hit dummy behind it and a hidden trigger the dummy
fires. kt_loadout_preset_device (LoadoutPresets.verse) keeps each player's slots with Verse persistence.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402

PREFIX = "KT27_Preset_"
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_loadout_preset_device"
FACE_X = 3584.0                  # armory east wall, facing -X into the room
H_UNIT, W_UNIT = 550.0, 125.0
# label, y, z, size, rgb (linear), trigger tag
TILES = [("PRESET 1", -63700.0, 250.0, 150.0, (0.05, 0.20, 0.32), "kt_preset_slot1_tag"),
         ("PRESET 2", -64050.0, 250.0, 150.0, (0.05, 0.20, 0.32), "kt_preset_slot2_tag"),
         ("PRESET 3", -64400.0, 250.0, 150.0, (0.05, 0.20, 0.32), "kt_preset_slot3_tag"),
         ("CLEAR", -64050.0, 85.0, 100.0, (0.30, 0.03, 0.03), "kt_preset_clear_tag")]
SIGN = "LOADOUT PRESETS  (yours only, kept between sessions)\nShoot an empty slot to save the wall guns you carry. Shoot a saved slot to equip it.\nCLEAR, then a slot, empties it. Mods from the bench are not saved."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for t in TILES:
        print(t[:4])
    if args.dry_run:
        return
    g = ag.Grid()
    b, m = g.b, g.m
    old = [a for a in (m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []) if a["label"].startswith(PREFIX)]
    for a in old:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    yaw = 270.0
    for name, y, z, size, rgb, tag in TILES:
        label = PREFIX + name.replace(" ", "")
        saved = [g.plane(label + "_Plate", FACE_X - 45.0, y, z, size, yaw, g.colour_material("M_KT_Preset_" + name.split()[0], rgb))]
        lab = b.device(bm.BILLBOARD, label + "_Label", FACE_X - 51.0, y, z - 20.0)
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": lab}, xform=bm.xform(FACE_X - 51.0, y, z - 20.0, 0.4, 0.4, 0.4, yaw=yaw))
        b.props(lab, {"text": name, "textSize": 48, "showBorder": False, "textFont": "Burbank",
                      "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                      "backgroundColor": {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": 1}})
        trig = b.device(bm.TRIGGER, label + "_Trigger", FACE_X - 300.0, y, -400.0)
        b.props(trig, {"visible in Game": False})
        b.tag(trig, tag)
        sy, sz = size * 0.85 / W_UNIT, size * 0.85 / H_UNIT
        dz = z - H_UNIT * sz / 2
        dummy = b.device(bm.DUMMY, label + "_Hit", FACE_X - 22.0, y, dz)
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dummy}, xform=bm.xform(FACE_X - 22.0, y, dz, 0.15, sy, sz, yaw=180.0))
        b.props(dummy, {"infiniteHealth": True})
        try:
            b.props(dummy, {"showHealthBar": False})
        except RuntimeError:
            pass
        b.bind(dummy, "On Hit", trig, "Trigger")
        saved += [lab, trig, dummy]
        for p in saved:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    sign = b.sign({"label": PREFIX + "Sign", "pos": (FACE_X - 40.0, -64050.0, 420.0), "yaw": 180, "zone": "Armory",
                   "size": 16, "text": SIGN})
    dev = b.device(DEVICE, PREFIX + "Device", FACE_X - 600.0, -64050.0, -700.0)
    for p in (sign, dev):
        m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    print(f"placed {len(TILES)} preset tiles, sign and device")


if __name__ == "__main__":
    main()
