"""Place the in-map input HUD (InputHud.verse): rank, step accuracy, off-plan presses and join calibration.

    python tools/build_input_hud.py

One kt_input_hud_device serves every player. It sits below the floor like the other Verse devices (their consoles
render and collide in play). Labels are KT22_InputHud*; only those are replaced.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT22_InputHud"
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_input_hud_device"
SPAWN = (-318.0, -59633.0)


def main():
    b = bm.Builder()
    for a in b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
        if a["label"].startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    x, y = SPAWN
    ref = b.device(DEVICE, PREFIX, x + 200.0, y, -700.0)
    b.m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
    print("input hud placed")


if __name__ == "__main__":
    main()
