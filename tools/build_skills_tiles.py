"""Skills Test: shoot a tile to pick the difficulty or start, additive (KT15_SkillsTile_* only).

    python tools/build_skills_tiles.py [--dry-run]

Player 2026-10-11: "i dont see any easy/ medium/ hard difficulty setting toggle, (we can have buttons on the wall
that shoot and color up based on the mode)". Four tiles float above the near end of lane A2, in front of the shoot
line and above the 5 m bot: WIDE, EASY, MEDIUM, HARD, START. Each is a coloured plate with a thin target dummy behind it;
the dummy's On Hit fires a tagged trigger under the floor, and kt_skills_test_device (SkillsTest.verse) picks the
level or starts a run. A tagged customizable light in front of each level tile is on for the chosen level.
The interact buttons behind the shoot line stay as they are.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402
from build_skills_test import SHOOT_X, LANE_Y  # noqa: E402

PREFIX = "KT15_SkillsTile_"
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
WALL_X = SHOOT_X + 450.0     # the plane the tiles sit in, facing back up the lane (-X)
Z = 540.0
SIZE = 240.0  # player 2026-10-11: shootable buttons bigger and easier to hit
# name, y offset, plate rgb (linear), trigger tag, light tag, light rgb
TILES = [("EASY", -420.0, (0.02, 0.25, 0.04), "kt_skills_easy_tag", "kt_skills_light_easy_tag", (0.2, 1.0, 0.3)),
         ("MEDIUM", -140.0, (0.30, 0.22, 0.01), "kt_skills_medium_tag", "kt_skills_light_medium_tag", (1.0, 0.8, 0.1)),
         ("HARD", 140.0, (0.30, 0.02, 0.02), "kt_skills_hard_tag", "kt_skills_light_hard_tag", (1.0, 0.15, 0.1)),
         ("START", 420.0, (0.25, 0.25, 0.28), "kt_skills_start_shot_tag", None, None),
         # Switches between the lane's bots and the whole plate's (tools/build_skills_wide.py); lit while wide.
         ("WIDE", -700.0, (0.12, 0.03, 0.30), "kt_skills_mode_shot_tag", "kt_skills_light_wide_tag", (0.6, 0.2, 1.0))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for t in TILES:
        print(t[0], (WALL_X, LANE_Y + t[1], Z))
    if args.dry_run:
        return
    g = ag.Grid()
    b, m = g.b, g.m
    old = [a for a in (m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []) if a["label"].startswith(PREFIX)]
    for a in old:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(old)} old tiles")
    yaw = 270.0                                       # faces -X, as the armory's east-wall tiles
    for name, dy, rgb, tag, light_tag, light_rgb in TILES:
        y = LANE_Y + dy
        saved = [g.plane(f"{PREFIX}{name}_Plate", WALL_X - 40.0, y, Z, SIZE, yaw,
                         g.colour_material(f"M_KT_SkillsTile_{name}", rgb))]
        label = b.device(bm.BILLBOARD, f"{PREFIX}{name}_Label", WALL_X - 46.0, y, Z - 30.0)
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": label},
               xform=bm.xform(WALL_X - 46.0, y, Z - 30.0, 0.5, 0.5, 0.5, yaw=yaw))
        b.props(label, {"text": name, "textSize": 60, "showBorder": False, "textFont": "Burbank",
                        "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                        "backgroundColor": {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": 1}})
        saved.append(label)
        trig = b.device(bm.TRIGGER, f"{PREFIX}{name}_Trigger", WALL_X, y, -400.0)
        b.tag(trig, tag)
        sy, sz = SIZE / 125.0, SIZE / 550.0             # play size (550 x 125 cm per unit): the whole plate
        dummy = b.device(bm.DUMMY, f"{PREFIX}{name}_Hit", WALL_X, y, Z - 550.0 * sz / 2)
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dummy},
               xform=bm.xform(WALL_X, y, Z - 550.0 * sz / 2, 0.15, sy, sz, yaw=180.0))
        b.props(dummy, {"infiniteHealth": True})
        b.bind(dummy, "On Hit", trig, "Trigger")
        saved += [trig, dummy]
        if light_tag:
            li = b.device(LIGHT, f"{PREFIX}{name}_Light", WALL_X - 180.0, y, Z)
            b.tag(li, light_tag)
            for key, value in {"initialState": False, "maximumRadius": 450.0,
                               "lightColor": {"r": light_rgb[0], "g": light_rgb[1], "b": light_rgb[2], "a": 1}}.items():
                try:
                    b.props(li, {key: value})
                except RuntimeError as exc:
                    print(f"  {name}: light {key} refused ({str(exc)[-60:]})")
            saved.append(li)
        for ref in saved:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
        print(f"  {name} placed")


if __name__ == "__main__":
    main()
