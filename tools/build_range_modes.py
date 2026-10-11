"""Gun range NARROW / WIDE modes: shootable tiles on each lane's low wall and hidden WIDE targets, additive
(KT26_RangeMode_* only).

    python tools/build_range_modes.py [--dry-run]
    then BuildAll; the device is GunRange.verse (kt_gun_range_lane_device, one per pop-up lane)

Player 2026-10-11: buttons you shoot on "the walls that separate you from the dummies, its a low wall", a narrow mode
that is the original lane round, and a Valorant-style mode where "hidden dummies randomly pop up" across the range at
the same distances in different places, one per player playing it.

* Tiles: WIDE, NARROW, EASY, MEDIUM, HARD, START across the player side of each pop-up lane's counter
  (KT8_Range_Counter_n, 110 cm high). Each is a coloured plate standing proud of the wall, a play-size target dummy
  between plate and wall (550 x 125 cm per unit of scale in play), a hidden trigger under the floor that the dummy's
  On Hit fires, a label and (except START) a small light the device turns on for the current choices.
* Hidden targets: two per lane at each of 10 / 20 / 35 / 50 / 75 m (a little nearer or further), 380 cm either side
  of the lane centre, clear of the lane's own targets (120 cm off centre). Wired like tools/build_gun_range.py, with
  the kt_range_wide_* tags; the lane devices pop them down at game start.
* Lane devices KT8_Range_Lane_0..3 get kt_range_lane_tag (so WIDE rounds never pick a target another lane holds), and
  the booth buttons get back their original text.
"""
import argparse
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402
from build_gun_range import TARGET, FIRE_X, Y0, POPUP_LANES, POPUP_M, LIGHT  # noqa: E402

PREFIX = "KT26_RangeMode_"
C = bm.CELL
FACE_X = FIRE_X - 70.0          # player side of the counter
Z = 58.0                         # tile centre (counter top is 110)
SIZE = 100.0
PITCH = 155.0
# name, plate rgb (linear), trigger tag, light tag, light rgb
TILES = [("WIDE", (0.12, 0.03, 0.30), "kt_range_wide_shot_tag", "kt_range_light_wide_tag", (0.6, 0.2, 1.0)),
         ("NARROW", (0.02, 0.12, 0.30), "kt_range_narrow_shot_tag", "kt_range_light_narrow_tag", (0.2, 0.5, 1.0)),
         ("EASY", (0.02, 0.25, 0.04), "kt_range_easy_shot_tag", "kt_range_light_easy_tag", (0.2, 1.0, 0.3)),
         ("MEDIUM", (0.30, 0.22, 0.01), "kt_range_medium_shot_tag", "kt_range_light_medium_tag", (1.0, 0.8, 0.1)),
         ("HARD", (0.30, 0.02, 0.02), "kt_range_hard_shot_tag", "kt_range_light_hard_tag", (1.0, 0.15, 0.1)),
         ("START", (0.25, 0.25, 0.28), "kt_range_start_shot_tag", None, None)]
H_UNIT, W_UNIT = 550.0, 125.0
SEED = 20261011


def lane_centre(n):
    return Y0 + n * 2 * C + C


def hidden():
    rng = random.Random(SEED)
    out = []
    for n in range(POPUP_LANES):
        yc = lane_centre(n)
        for m in POPUP_M:
            for side in (-1, 1):
                dm = rng.uniform(-2.0, 2.0)
                out.append((f"{PREFIX}Hidden_{n}_{m}m_{'S' if side < 0 else 'N'}", FIRE_X + (m + dm) * 100.0, yc + side * 380.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    targets = hidden()
    print(f"{POPUP_LANES} lanes x {len(TILES)} tiles, {len(targets)} hidden targets")
    if args.dry_run:
        for t in targets[:6]:
            print(" ", t)
        return
    g = ag.Grid()
    b, m = g.b, g.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    old = [p for l, p in acts.items() if l.startswith(PREFIX)]
    for p in old:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": p})
    print(f"removed {len(old)} old actors")
    yaw = 270.0                                   # faces -X, towards the booth
    sy, sz = SIZE * 0.85 / W_UNIT, SIZE * 0.85 / H_UNIT
    for n in range(POPUP_LANES):
        yc = lane_centre(n)
        for k, (name, rgb, tag, light_tag, light_rgb) in enumerate(TILES):
            y = yc + (k - (len(TILES) - 1) / 2) * PITCH
            label = f"{PREFIX}{n}_{name}"
            saved = [g.plane(label + "_Plate", FACE_X - 45.0, y, Z, SIZE, yaw, g.colour_material(f"M_KT_SkillsTile_{name}", rgb))]
            lab = b.device(bm.BILLBOARD, label + "_Label", FACE_X - 51.0, y, Z - 20.0)
            m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": lab},
                   xform=bm.xform(FACE_X - 51.0, y, Z - 20.0, 0.3, 0.3, 0.3, yaw=yaw))
            b.props(lab, {"text": name, "textSize": 60, "showBorder": False, "textFont": "Burbank",
                          "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                          "backgroundColor": {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": 1}})
            trig = b.device(bm.TRIGGER, label + "_Trigger", FIRE_X + 50.0, y, -400.0)
            b.props(trig, {"visible in Game": False})
            b.tag(trig, tag)
            dz = Z - H_UNIT * sz / 2
            dummy = b.device(bm.DUMMY, label + "_Hit", FACE_X - 22.0, y, dz)
            m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dummy},
                   xform=bm.xform(FACE_X - 22.0, y, dz, 0.15, sy, sz, yaw=180.0))
            b.props(dummy, {"infiniteHealth": True})
            try:
                b.props(dummy, {"showHealthBar": False})
            except RuntimeError:
                pass
            b.bind(dummy, "On Hit", trig, "Trigger")
            saved += [lab, trig, dummy]
            if light_tag:
                li = b.device(LIGHT, label + "_Light", FACE_X - 250.0, y, 160.0)
                b.tag(li, light_tag)
                for key, value in {"initialState": False, "maximumRadius": 220.0,
                                   "lightColor": {"r": light_rgb[0], "g": light_rgb[1], "b": light_rgb[2], "a": 1}}.items():
                    try:
                        b.props(li, {key: value})
                    except RuntimeError as exc:
                        print(f"  {label}: light {key} refused ({str(exc)[-50:]})")
                saved.append(li)
            for p in saved:
                m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
        print(f"  lane {n + 1}: tiles placed")
        lane = acts.get(f"KT8_Range_Lane_{n}")
        if lane:
            comps = m.tool(bm.ACTOR, "get_components", actor={"refPath": lane}) or []
            if not any(c["refPath"].endswith(".KT_Tags") for c in comps):
                b.tag(lane, "kt_range_lane_tag")
            m.tool(bm.SCENE, "save_actor", actor={"refPath": lane})
        start = acts.get(f"KT8_Range_Start_{n}")
        if start:
            b.props(start, {"interaction Text": f"Start pop-up round, lane {n + 1}"})
            m.tool(bm.SCENE, "save_actor", actor={"refPath": start})
    for label, x, y in targets:
        ref = m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=TARGET, name=label, xform=bm.xform(x, y, 0.0, yaw=180))
        path = b.labelled(ref["refPath"] if isinstance(ref, dict) else ref, label)
        saved = [path]
        for kind, tag in (("Up", "kt_range_wide_up_tag"), ("Down", "kt_range_wide_down_tag"), ("Hit", "kt_range_wide_hit_tag")):
            trig = b.device(bm.TRIGGER, f"{label}_{kind}", x, y, -400.0)
            b.props(trig, {"visible in Game": False})
            b.tag(trig, tag)
            if kind == "Up":
                b.bind(trig, "OnTriggered", path, "Pop-Up")
            elif kind == "Down":
                b.bind(trig, "OnTriggered", path, "Pop-Down")
            else:
                b.bind(path, "On Hit", trig, "Trigger")
            saved.append(trig)
        for p in saved:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    print(f"placed {len(targets)} hidden targets")


if __name__ == "__main__":
    main()
