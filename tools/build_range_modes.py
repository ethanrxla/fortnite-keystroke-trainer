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
* Hidden side targets (player 2026-10-20: WIDE stays in the lane; "add dummies to the immediate left or right in the
  lanes ... dont move any of the dummies"): one SIDE_CM either side of each of the lane's own targets
  (KT8_Range_Target_n_m, 120 cm off the lane centre), at the same distance, so a WIDE round spreads over the lane's
  width and never past its line (lane centre +-512). Wired like tools/build_gun_range.py, with the kt_range_wide_*
  tags; the lane devices pop them down at game start and only use their own lane's.
* Lane devices KT8_Range_Lane_0..3 get kt_range_lane_tag, and the booth buttons get back their original text.

    python tools/build_range_modes.py --hidden-only     # rebuild only the side targets, keep the wall tiles
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
SIZE = 95.0   # fits under the 110 cm counter top (player 2026-10-12: "a little smaller cause they go over the short wall")
PITCH = 160.0
# A second, bigger set of the same buttons above each counter (player 2026-10-20: "put another button so its easier to
# hit"). Same trigger as the counter tile, so GunRange.verse sees one button; high enough to stay clear of the sight
# line to the targets.
BIG_SIZE, BIG_PITCH, BIG_Z = 150.0, 165.0, 650.0
# Range targets never pop back up by themselves: GunRange.verse raises them (rounds, and free fire 2 s after a hit).
# The 2 s default reset brought knocked targets back mid-round and the round counted real hits as misses.
NO_AUTO_RESET = {"resetDelaySetting": 9999}
# name, plate rgb (linear), trigger tag, light tag, light rgb
TILES = [("WIDE", (0.12, 0.03, 0.30), "kt_range_wide_shot_tag", "kt_range_light_wide_tag", (0.6, 0.2, 1.0)),
         ("NARROW", (0.02, 0.12, 0.30), "kt_range_narrow_shot_tag", "kt_range_light_narrow_tag", (0.2, 0.5, 1.0)),
         ("EASY", (0.02, 0.25, 0.04), "kt_range_easy_shot_tag", "kt_range_light_easy_tag", (0.2, 1.0, 0.3)),
         ("MEDIUM", (0.30, 0.22, 0.01), "kt_range_medium_shot_tag", "kt_range_light_medium_tag", (1.0, 0.8, 0.1)),
         ("HARD", (0.30, 0.02, 0.02), "kt_range_hard_shot_tag", "kt_range_light_hard_tag", (1.0, 0.15, 0.1)),
         ("START", (0.25, 0.25, 0.28), "kt_range_start_shot_tag", None, None)]
H_UNIT, W_UNIT = 550.0, 125.0
SEED = 20261011
SIDE_CM = 260.0                  # side target offset from its lane target (target prop is about 150 cm wide)


def lane_centre(n):
    return Y0 + n * 2 * C + C


def hidden():
    """(label, x, y): beside each lane target (build_gun_range.py: x FIRE_X + m*100, y centre -120 / +120 for odd m)."""
    out = []
    for n in range(POPUP_LANES):
        yc = lane_centre(n)
        for m in POPUP_M:
            yt = yc + (120.0 if m % 2 else -120.0)
            for side in (-1, 1):
                y = yt + side * SIDE_CM
                assert abs(y - yc) + 75.0 <= C - 50.0, (n, m, y)       # target edge stays 50 cm inside the lane line
                out.append((f"{PREFIX}Hidden_{n}_{m}m_{'S' if side < 0 else 'N'}", FIRE_X + m * 100.0, y))
    return out


TEX_FOLDER = bm.MODULE + "/KT_UI"
FONT = bm.ROOT / "assets" / "fonts" / "bitcount-ink"


def tile_texture(name, rgb):
    """The tile's face as one image (colour + its word), imported once: a billboard label on these small tiles
    drifted off the plate when the sign renderer turned it into a panel, and fresh billboards did not draw at all."""
    from PIL import Image, ImageDraw, ImageFont
    out = bm.ROOT / "assets" / "ui" / "range_tiles" / f"T_KT_RangeTile_{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    srgb = tuple(int(255 * min(1.0, (c * 1.6) ** (1 / 2.2))) for c in rgb)
    im = Image.new("RGBA", (512, 512), srgb + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle((10, 10, 501, 501), outline=(255, 255, 255, 200), width=10)
    font_file = next(FONT.glob("*.ttf"))
    size = 150
    while size > 40:
        f = ImageFont.truetype(str(font_file), size)
        w = d.textlength(name, font=f)
        if w <= 440:
            break
        size -= 6
    d.text((256, 256), name, font=f, fill=(255, 255, 255, 255), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0, 220))
    im.save(out)
    asset = f"T_KT_RangeTile_{name}"
    path = f"{TEX_FOLDER}/{asset}.{asset}"
    return out, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tiles-only", action="store_true", help="rebuild the shootable tiles, keep the hidden targets")
    ap.add_argument("--hidden-only", action="store_true", help="rebuild the hidden side targets, keep the tiles")
    ap.add_argument("--big-only", action="store_true", help="(re)place only the big copies above the counters")
    args = ap.parse_args()
    targets = hidden()
    print(f"{POPUP_LANES} lanes x {len(TILES)} tiles, {len(targets)} hidden targets")
    if args.big_only and not args.dry_run:
        g = ag.Grid()
        place_big(g, g.m)
        return
    if args.dry_run:
        for t in targets[:6]:
            print(" ", t)
        return
    g = ag.Grid()
    b, m = g.b, g.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    old = [p for l, p in acts.items() if l.startswith(PREFIX) and not (args.tiles_only and l.startswith(PREFIX + "Hidden_"))
           and not (args.hidden_only and not l.startswith(PREFIX + "Hidden_"))]
    if not args.tiles_only:
        # Their aim-evidence relays (install_aim_accuracy.py, KT40_Aim_<label>_*) are bound to the targets being
        # replaced; drop them too so ensure_target_evidence builds fresh ones bound to the new targets.
        old += [p for l, p in acts.items() if l.startswith("KT40_Aim_" + PREFIX + "Hidden_")]
    for p in old:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": p})
    print(f"removed {len(old)} old actors")
    if args.hidden_only:
        place_hidden(b, m, targets)
        return
    yaw = 270.0                                   # faces -X, towards the booth
    sy, sz = SIZE / W_UNIT, SIZE / H_UNIT          # the whole plate is the hitbox
    for n in range(POPUP_LANES):
        yc = lane_centre(n)
        for k, (name, rgb, tag, light_tag, light_rgb) in enumerate(TILES):
            y = yc + (k - (len(TILES) - 1) / 2) * PITCH
            label = f"{PREFIX}{n}_{name}"
            png, tex = tile_texture(name, rgb)
            if not m.tool(ag.AS, "exists", path=tex):
                m.tool("editor_toolset.toolsets.texture.TextureTools", "import_file", folder_path=TEX_FOLDER,
                       asset_name=tex.split(".")[-1], source_file=str(png))
                m.tool(ag.AS, "save_assets", asset_paths=[tex])
            # yaw 90: the textured front faces -X, towards the booth (yaw 270 showed the words mirrored).
            saved = [g.plane(label + "_Plate", FACE_X - 45.0, y, Z, SIZE, 90.0, g.icon_material(tex))]
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
            saved += [trig, dummy]
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
    place_big(g, m)
    if args.tiles_only:
        print("tiles rebuilt; hidden targets kept")
        return
    place_hidden(b, m, targets)


def place_big(g, m):
    """The big copies: plate and hit dummy only, the dummy firing the counter tile's own trigger. Run
    tools/refit_hitboxes.py --only KT26_RangeMode_ afterwards (the whole plate becomes the hitbox)."""
    b = g.b
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or [])}
    for l, p in acts.items():
        if "_Big_" in l:
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": p})
    sy, sz = BIG_SIZE / W_UNIT, BIG_SIZE / H_UNIT
    placed = 0
    for n in range(POPUP_LANES):
        yc = lane_centre(n)
        for k, (name, *_rest) in enumerate(TILES):
            trig = acts.get(f"{PREFIX}{n}_{name}_Trigger")
            if not trig:
                print(f"  lane {n + 1} {name}: no counter tile trigger, skipped")
                continue
            y = yc + (k - (len(TILES) - 1) / 2) * BIG_PITCH
            label = f"{PREFIX}{n}_{name}_Big"
            tex = f"{TEX_FOLDER}/T_KT_RangeTile_{name}.T_KT_RangeTile_{name}"
            plate = g.plane(label + "_Plate", FACE_X - 45.0, y, BIG_Z, BIG_SIZE, 90.0, g.icon_material(tex))
            dz = BIG_Z - H_UNIT * sz / 2
            dummy = b.device(bm.DUMMY, label + "_Hit", FACE_X - 22.0, y, dz)
            m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dummy},
                   xform=bm.xform(FACE_X - 22.0, y, dz, 0.15, sy, sz, yaw=180.0))
            b.props(dummy, {"infiniteHealth": True})
            try:
                b.props(dummy, {"showHealthBar": False})
            except RuntimeError:
                pass
            b.bind(dummy, "On Hit", trig, "Trigger")
            for p in (plate, dummy):
                m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
            placed += 1
    print(f"placed {placed} big copies")


def place_hidden(b, m, targets):
    for label, x, y in targets:
        ref = m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=TARGET, name=label, xform=bm.xform(x, y, 0.0, yaw=180))
        path = b.labelled(ref["refPath"] if isinstance(ref, dict) else ref, label)
        b.props(path, NO_AUTO_RESET)
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
                from install_aim_accuracy import ensure_target_evidence
                ensure_target_evidence(b, label, path, trig)
            saved.append(trig)
        for p in saved:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    print(f"placed {len(targets)} hidden targets")


if __name__ == "__main__":
    main()
