"""Gun range mode buttons: rebuild every tile's hit dummies cleanly and check each one is wired (KT26_RangeMode_*).

    python tools/fix_range_buttons.py [--dry-run]

2026-10-20: an interrupted refit_hitboxes run left the range tiles with extra dummies and lost On Hit links, on both
the counter tiles and the big copies above them (build_range_modes.py place_big). For every lane and tile this removes
all of that tile's hit dummies (_Hit, _Hit_n, _Big_Hit, _Big_Hit_n), places a fresh grid over each plate's real
bounds with hitbox.place_grid, wired On Hit -> the tile's own trigger (the big copy shares it), and reads the links back.
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import hitbox  # noqa: E402
from build_range_modes import PREFIX, TILES, FACE_X  # noqa: E402
from build_gun_range import POPUP_LANES  # noqa: E402

YAW = 180.0          # dummies face -X, towards the booth (build_range_modes.py)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    every = m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []
    acts = {a["label"]: a for a in every}          # plates and triggers (unique labels)
    bad = []
    for n in range(POPUP_LANES):
        for name, *_ in TILES:
            base = f"{PREFIX}{n}_{name}"
            trig = acts.get(base + "_Trigger")
            if not trig:
                bad.append(f"{base}: no trigger")
                continue
            for kind in ("",):        # the big copies were removed 2026-10-20
                plate = acts.get(base + kind + "_Plate")
                if not plate:
                    if not kind:
                        bad.append(f"{base}: no plate")
                    continue
                hit = base + kind + "_Hit"
                # A list, not the label map: an interrupted refit can leave two dummies under one label.
                old = [a for a in every if re.fullmatch(re.escape(hit) + r"(_\d+)*", a["label"])]
                mn, mx = plate["bounds"]["min"], plate["bounds"]["max"]
                centre = tuple((mn[k] + mx[k]) / 2 for k in "xyz")
                w, h = mx["y"] - mn["y"], mx["z"] - mn["z"]
                if args.dry_run:
                    print(f"  {hit}: {len(old)} old dummies, plate {w:.0f} x {h:.0f} -> {len(hitbox.plan_grid(w, h))}")
                    continue
                for a in old:
                    m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
                paths = hitbox.place_grid(b, hit, centre, w, h, YAW, (FACE_X - 22.0, centre[1]),
                                          [(trig["actorPath"], "Trigger")])
                for p in paths:
                    m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
                linked = {l["sourceDevicePath"]["refPath"] for l in
                          m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": trig["actorPath"]}) or []}
                missing = [p for p in paths if p not in linked]
                if missing:
                    bad.append(f"{hit}: {len(missing)}/{len(paths)} dummies not wired")
        print(f"  lane {n + 1} done")
    print("all range buttons wired" if not bad else "problems:\n  " + "\n  ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
