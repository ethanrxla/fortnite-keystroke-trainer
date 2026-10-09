"""Light the enclosed rooms. The roofs we added shut out the sky, so the rooms are nearly black.

    python tools/build_lights.py --dry-run
    python tools/build_lights.py

Reads every KT_Ceil_* slab from the level (the roofs build_map.py --enclose-only places) and hangs
point lights just under it, spaced about one light radius apart along the room's long side. Actors are
labelled KT3_Light_*; only those are ever removed. The practice court (KT2_*) has its own lighting
and is not touched.

Cost note: every light is a device and a dynamic light. Rooms are separated by walls, so lights do
not need to overlap far. Raise SPACING if performance suffers, and measure in a populated session.
"""

import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT3_Light_"
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
SPACING = 3600.0      # cm between lights along a room's long side
RADIUS = 4200.0       # cm each light reaches
DROP = 150.0          # cm below the ceiling's underside


def lights_for(bounds):
    """[(x, y, z)] for one ceiling slab given its world bounds {'min': .., 'max': ..}."""
    lo, hi = bounds["min"], bounds["max"]
    dx, dy = hi["x"] - lo["x"], hi["y"] - lo["y"]
    z = lo["z"] - DROP
    along_x = dx >= dy
    length = dx if along_x else dy
    n = max(1, math.ceil(length / SPACING))
    out = []
    for k in range(n):
        f = (k + 0.5) / n
        if along_x:
            out.append((lo["x"] + dx * f, (lo["y"] + hi["y"]) / 2, z))
        else:
            out.append(((lo["x"] + hi["x"]) / 2, lo["y"] + dy * f, z))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    actors = b.m.tool(bm.SCENE, "find_actors", name="KT_Ceil_", collision_channels=[]) or []
    plan = []
    for a in actors:
        bounds = a.get("bounds")
        if isinstance(bounds, dict) and "min" in bounds:
            for p in lights_for(bounds):
                plan.append((a["label"], p))
    print(f"{len(actors)} ceilings -> {len(plan)} lights")
    if args.dry_run:
        return
    for a in b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for n, (label, (x, y, z)) in enumerate(plan):
        light = b.device(LIGHT, f"{PREFIX}{n:03d}", x, y, z)
        b.props(light, {"maximumRadius": RADIUS})
    print("lights placed:", len(plan))


if __name__ == "__main__":
    main()
