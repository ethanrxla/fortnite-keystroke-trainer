"""Place the map-wide edit guide (EditGuide.verse) and its on/off button in the hub.

    python tools/build_edit_guide.py

One kt_edit_guide_device runs the guide for every player everywhere except the Arena and the Fight Lab box
fight. A button next to spawn (tag kt_edit_guide_toggle_tag) turns it off and on per player, for recall
practice. Labels are KT9_EditGuide*; only those are replaced. Needs /KT_UI/T_KT_EditRing in the island
(import assets/ui/T_KT_EditRing.png first).
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT9_EditGuide"
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_edit_guide_device"
SPAWN = (-318.0, -59633.0)


def main():
    b = bm.Builder()
    for a in b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
        if a["label"].startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    x, y = SPAWN
    b.device(DEVICE, PREFIX, x, y, -60.0)
    bx, by = x + 300.0, y + 900.0
    btn = b.device(bm.BUTTON, f"{PREFIX}_Toggle", bx, by, 0.0)
    b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": btn}, xform=bm.xform(bx, by, 0.0, yaw=270.0))
    b.props(btn, {"interaction Text": "Edit guide on / off", "delay": 0.0, "resetDelay": 0.3})
    b.tag(btn, "kt_edit_guide_toggle_tag")
    b.sign({"label": f"{PREFIX}_Sign", "pos": (bx, by + 60, 180), "yaw": 270, "zone": "Edit", "size": 30,
            "text": "EDIT GUIDE\nRed ring = your edit aim point. The radar picks the edit with the\n"
                    "least crosshair travel from where you aim. Press to turn it off\nand edit from memory."})
    print("edit guide placed")


if __name__ == "__main__":
    main()
