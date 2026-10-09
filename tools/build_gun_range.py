"""Enclosed gun range on the bot range strip south of the Aim area.

    python tools/build_gun_range.py --dry-run
    python tools/build_gun_range.py            # removes KT8_Range_* and the old KT4_Bot_* range pieces first

Replaces the open-air bot range (KT4_Bot_* rails, patrol bots, cover and sign; the KT4_Bot_Floor slab stays)
with an indoor range laid out like a real one, 24 x 12 cells (123 x 61 m):

  * a walkway behind the firing line, then booths: partitions, a waist-high counter, a lane number and a
    START button per pop-up lane;
  * lanes 1-4 (2 cells wide each): shooting-range pop-up targets at 10, 20, 35, 50 and 75 m.
    GunRange.verse (kt_gun_range_lane_device, one per lane) runs a pop-up round on START: one random
    target pops for ~1.6 s (+0.1 s per 10 m), 15 reps, then shows hits, misses and average time to hit;
  * lane 5 (4 cells wide): moving dummies on rails at 15, 30, 50 and 75 m, faster with distance;
  * side walls, a dark backstop, a ceiling with hanging baffles and distance boards, and lights.
The doorway is in the north wall behind the firing line, so the walk in from the Aim plate stays the same.
"""

import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT8_Range_"
OLD = ("KT4_Bot_", "KT4_BotCover_")
KEEP_OLD = {"KT4_Bot_Floor"}
C = bm.CELL
TARGET = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_B_ShootingTarget_Master_4df2564c.PPID_CR_Legacy_B_ShootingTarget_Master_4df2564c"
LANE_DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_gun_range_lane_device"
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
X0, X1 = -35840.0, -23552.0          # back wall .. backstop (the old strip)
Y0, Y1 = -96768.0, -90624.0          # south wall .. north wall (Aim plate side)
FIRE_X = X0 + 3 * C                  # firing line (counter front edge)
BOOTH_X = X0 + C                     # walkway behind the booths
HEIGHT = 1150.0                      # ceiling underside
POPUP_LANES = 4
POPUP_M = (10, 20, 35, 50, 75)
RAILS = [(15, 0.6), (30, 0.8), (50, 1.0), (75, 1.3)]   # metres down range, speed factor
BAFFLES_M = (15, 30, 45, 60, 80)


def lane_bounds():
    """[(y_lo, y_hi, kind)] from south to north: four 2-cell pop-up lanes, then the 4-cell moving lane."""
    out, y = [], Y0
    for _ in range(POPUP_LANES):
        out.append((y, y + 2 * C, "popup"))
        y += 2 * C
    out.append((y, Y1, "moving"))
    return out


def plan():
    slabs, devices, signs, targets, rails = [], [], [], [], []

    def slab(label, x0, x1, y0, y1, top, thick, mat):
        slabs.append({"label": PREFIX + label, "bounds": (x0, x1, y0, y1), "top": top, "thick": thick, "mat": mat})

    t = 40.0
    # Shell: back wall, side walls, backstop, north wall with a 2-cell doorway into the walkway, ceiling.
    slab("Wall_Back", X0 - t, X0, Y0 - t, Y1 + t, HEIGHT, HEIGHT + 100, "Armory")
    slab("Wall_S", X0, X1, Y0 - t, Y0, HEIGHT, HEIGHT + 100, "Armory")
    door0, door1 = X0, X0 + 2 * C
    slab("Wall_N", door1, X1, Y1, Y1 + t, HEIGHT, HEIGHT + 100, "Armory")
    slab("Wall_N_Lintel", door0, door1, Y1, Y1 + t, HEIGHT, HEIGHT - 450, "Armory")
    slab("Backstop", X1, X1 + 300, Y0 - t, Y1 + t, HEIGHT, HEIGHT + 100, "Void")
    slab("Ceiling", X0 - t, X1 + 300, Y0 - t, Y1 + t, HEIGHT + 100, 100, "Hub")
    slab("Walkway", X0, BOOTH_X, Y0, Y1, 2.0, 2.0, "Hub")

    lanes = lane_bounds()
    for n, (ya, yb, kind) in enumerate(lanes):
        yc = (ya + yb) / 2
        # Booth partition on the lane's north edge (not on the outer wall), counter at the firing line.
        if n < len(lanes) - 1:
            slab(f"Partition_{n}", BOOTH_X, FIRE_X, yb - 10, yb + 10, 260, 260, "Armory")
            slab(f"LaneLine_{n}", FIRE_X, X1, yb - 8, yb + 8, 2.0, 2.0, "Aim")
        slab(f"Counter_{n}", FIRE_X - 70, FIRE_X, ya + 30, yb - 30, 110, 110, "Hub")
        signs.append({"label": f"{PREFIX}LaneSign_{n}", "pos": (FIRE_X + 150, yc, 520), "yaw": 180, "zone": "Aim",
                      "size": 40, "text": f"LANE {n + 1}" + ("  POP-UP" if kind == "popup" else "  MOVING")})
        devices.append({"label": f"{PREFIX}Light_Booth_{n}", "asset": LIGHT, "pos": (FIRE_X - C, yc, HEIGHT - 120),
                        "props": {"maximumRadius": 1400.0}})
        if kind == "popup":
            for m in POPUP_M:
                targets.append({"label": f"{PREFIX}Target_{n}_{m}m", "pos": (FIRE_X + m * 100.0, yc + (120 if m % 2 else -120))})
            devices.append({"label": f"{PREFIX}Lane_{n}", "asset": LANE_DEVICE, "pos": (FIRE_X, yc, 0.0), "props": {}})
            devices.append({"label": f"{PREFIX}Start_{n}", "asset": bm.BUTTON, "pos": (FIRE_X - 140, ya + 140, 0.0),
                            "props": {"interaction Text": f"Start pop-up round, lane {n + 1}", "delay": 0.0, "resetDelay": 0.5},
                            "yaw": 0.0, "tag": "kt_range_start_tag"})
        else:
            for k, (m, factor) in enumerate(RAILS):
                rails.append({"label": f"{PREFIX}Rail_{k}_{m}m", "pos": (FIRE_X + m * 100.0, yc),
                              "factor": factor})

    # Overhead baffles across the range with distance boards, and lights down the middle.
    for m in BAFFLES_M:
        x = FIRE_X + m * 100.0
        slab(f"Baffle_{m}m", x - 30, x + 30, Y0, Y1, HEIGHT, 260, "Armory")
        signs.append({"label": f"{PREFIX}Distance_{m}m", "pos": (x - 40, (Y0 + Y1) / 2, HEIGHT - 300), "yaw": 180,
                      "zone": "Hub", "size": 44, "text": f"{m} m"})
    for k, f in enumerate((0.1, 0.3, 0.5, 0.7, 0.9)):
        x = FIRE_X + (X1 - FIRE_X) * f
        for side, y in (("S", Y0 + (Y1 - Y0) * 0.3), ("N", Y0 + (Y1 - Y0) * 0.75)):
            devices.append({"label": f"{PREFIX}Light_{k}{side}", "asset": LIGHT, "pos": (x, y, HEIGHT - 300),
                            "props": {"maximumRadius": 3200.0}})
    signs.append({"label": f"{PREFIX}Title", "pos": (X0 + 60, (Y0 + Y1) / 2, 380), "yaw": 0, "zone": "Aim", "size": 40,
                  "text": "GUN RANGE\nLanes 1-4: press START at your booth for a pop-up round\n"
                          "Lane 5: moving targets, lead them\nWhy: first shot on a target you didn't expect"})
    return slabs, devices, signs, targets, rails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    slabs, devices, signs, targets, rails = plan()
    print(f"plan: {len(slabs)} slabs, {len(devices)} devices, {len(signs)} signs, {len(targets)} pop-up targets, {len(rails)} rails")
    if args.dry_run:
        return
    b = bm.Builder()
    acts = b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []
    gone = [a for a in acts if a["label"].startswith(PREFIX) or
            (a["label"].startswith(OLD) and a["label"] not in KEEP_OLD)]
    backup = bm.ROOT / "backups" / f"gun-range-{datetime.date.today()}"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "removed.json").write_text(json.dumps(gun_list(gone), indent=1))
    for a in gone:
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(gone)} actors (list in {backup / 'removed.json'})")

    for s in slabs:
        b.slab(s)
    for d in devices:
        x, y, z = d["pos"]
        path = b.device(d["asset"], d["label"], x, y, z)
        if "yaw" in d:
            b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path}, xform=bm.xform(x, y, z, yaw=d["yaw"]))
        if d["props"]:
            b.props(path, d["props"])
        if d.get("tag"):
            b.tag(path, d["tag"])
    for tg in targets:
        x, y = tg["pos"]
        ref = b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=TARGET, name=tg["label"], xform=bm.xform(x, y, 0.0, yaw=180))
        path = b.labelled(ref["refPath"] if isinstance(ref, dict) else ref, tg["label"])
        b.tag(path, "kt_range_target_tag")
    for r in rails:
        x, y = r["pos"]
        rail = b.device(bm.DUMMY_TRACK, r["label"], x, y, 0.0)
        b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": rail}, xform=bm.xform(x, y, 0.0, yaw=90))
        speed = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": rail}, properties=["speed"])).get("speed")
        if isinstance(speed, (int, float)):
            b.props(rail, {"speed": speed * r["factor"]})
    for s in signs:
        b.sign(s)
    print("gun range placed")


def gun_list(actors):
    return [{"label": a["label"], "path": a["actorPath"], "bounds": a.get("bounds")} for a in actors]


if __name__ == "__main__":
    main()
