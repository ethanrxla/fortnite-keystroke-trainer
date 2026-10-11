"""Target tracking range: bots roam sporadically over ramps and a raised platform (additive; KT11_Track_* only).

    python tools/build_tracking_range.py --dry-run
    python tools/build_tracking_range.py

Placed straight south of the bot range (KT4_Bot_Floor) so players walk on from it. The arena is a closed room with a
floor, side and end walls, a ceiling and lights. Shoot line at the near end; beyond it a raised platform (one level
high) with ramps up and down on both ends and two smaller raised blocks, so the bots change height as well as direction.
  * waypoints: hidden triggers tagged kt_tracking_waypoint_tag on the floor, ramp feet, the platform top and the blocks;
  * guards: Guard Spawners tagged kt_tracking_spawner_tag, enemy team, lowest accuracy, infinite respawn;
  * one kt_tracking_range_device (TrackingRange.verse) sends every spawned guard to random waypoints at random speeds.
Ramps are the same 36.87 degree plates the terrain builder uses (one level over one cell). A rerun replaces only
KT11_Track_* actors. VERIFY in a playtest that guards obey NavigateTo; the device logs KT|tracking_range lines.
"""
import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT11_Track_"
GUARD = "/CRD_HenchmanSpawner/SetupAssets/PID_Device_GuardSpawner_V2.PID_Device_GuardSpawner_V2"
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_tracking_range_device"
DEPTH_CELLS = 12
HEIGHT = 1000.0
RISE = bm.LEVEL_H
RUN = bm.CELL


def ramp(b, label, cx, cy, base, direction, mat):
    """A 36.87 degree plate rising toward +X (direction 1) or toward -X (direction -1) across one cell."""
    length = math.hypot(RUN, RISE)
    xf = bm.xform(cx, cy, base + RISE / 2.0 - 12.0, length / 100.0, bm.CELL / 100.0, 0.24)
    xf["rotation"]["pitch"] = math.degrees(math.atan2(RISE, RUN)) * direction
    path = b.labelled(b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=bm.BOX, name=label, xform=xf)["refPath"], label)
    mesh = next((c["refPath"] for c in b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []
                 if "StaticMeshComponent" in c["refPath"]), None)
    if mesh:
        b.props(mesh, {"OverrideMaterials": [{"refPath": bm.MAT[mat]}]})
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    bounds = m.tool(bm.ACTOR, "get_actor_bounds", actor={"refPath": acts["KT4_Bot_Floor"]})
    x0, x1 = bounds["min"]["x"], bounds["max"]["x"]
    yb = bounds["min"]["y"]                       # the bot range's south edge is this arena's north edge
    ya = yb - DEPTH_CELLS * bm.CELL
    yc = (ya + yb) / 2.0
    line_x = x0 + 3 * bm.CELL
    px = x0 + 10 * bm.CELL                        # platform centre
    print(f"tracking arena: x {x0:.0f}..{x1:.0f}, y {ya:.0f}..{yb:.0f}; shoot line x {line_x:.0f}; platform at x {px:.0f}")
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})

    # Room
    b.slab({"label": PREFIX + "Floor", "bounds": (x0, x1, ya, yb), "top": 0.0, "thick": 100.0, "mat": "Aim"})
    b.slab({"label": PREFIX + "Wall_W", "bounds": (x0 - 20, x0, ya, yb), "top": HEIGHT, "thick": HEIGHT, "mat": "Aim"})
    b.slab({"label": PREFIX + "Wall_E", "bounds": (x1, x1 + 20, ya, yb), "top": HEIGHT, "thick": HEIGHT, "mat": "Aim"})
    b.slab({"label": PREFIX + "Wall_S", "bounds": (x0, x1, ya - 20, ya), "top": HEIGHT, "thick": HEIGHT, "mat": "Aim"})
    b.slab({"label": PREFIX + "Ceiling", "bounds": (x0, x1, ya, yb), "top": HEIGHT + 100, "thick": 100, "mat": "Aim"})
    b.slab({"label": PREFIX + "ShootLine", "bounds": (line_x - 40, line_x + 40, ya + 256, yb - 256), "top": 2.0, "thick": 2.0, "mat": "Hub"})
    b.sign({"label": PREFIX + "Sign", "pos": (line_x - 2 * bm.CELL, yc, 380), "yaw": 180, "zone": "Aim", "size": 48,
            "text": "TARGET TRACKING\nkeep your crosshair on the bots as they change speed, direction and height\nwhy: tracking is steady mouse control, not flicking"})

    # Platform with ramps up (from -X) and down (to +X), and two raised side blocks, each with a ramp.
    half = 2 * bm.CELL
    b.slab({"label": PREFIX + "Platform", "bounds": (px - half, px + half, yc - half, yc + half), "top": RISE, "thick": RISE, "mat": "Aim"})
    for k, dy in enumerate((-1.0, 1.0)):
        ramp(b, f"{PREFIX}RampUp_{k}", px - half - RUN / 2, yc + dy * bm.CELL, 0.0, 1, "Aim")
        ramp(b, f"{PREFIX}RampDown_{k}", px + half + RUN / 2, yc + dy * bm.CELL, 0.0, -1, "Aim")
    for k, dy in enumerate((-5.0, 5.0)):
        sy = yc + dy * bm.CELL
        b.slab({"label": f"{PREFIX}Block_{k}", "bounds": (px - bm.CELL, px + bm.CELL, sy - bm.CELL, sy + bm.CELL), "top": RISE, "thick": RISE, "mat": "Aim"})
        ramp(b, f"{PREFIX}BlockRamp_{k}", px - bm.CELL - RUN / 2, sy, 0.0, 1, "Aim")

    # Lights
    for k, f in enumerate((0.2, 0.5, 0.8)):
        for j, g in enumerate((0.3, 0.7)):
            b.device(LIGHT, f"{PREFIX}Light_{k}{j}", x0 + (x1 - x0) * f, ya + (yb - ya) * g, HEIGHT - 150)

    # Waypoints: hidden triggers tagged for the Verse device
    spots = [(line_x + 6 * bm.CELL, yc - 3 * bm.CELL, 0), (line_x + 6 * bm.CELL, yc + 3 * bm.CELL, 0),
             (px - half - 1.5 * RUN, yc - bm.CELL, 0), (px - half - 1.5 * RUN, yc + bm.CELL, 0),
             (px + half + 1.5 * RUN, yc - bm.CELL, 0), (px + half + 1.5 * RUN, yc + bm.CELL, 0),
             (px, yc - 3.5 * bm.CELL, 0), (px, yc + 3.5 * bm.CELL, 0),
             (x1 - 2 * bm.CELL, yc - 4 * bm.CELL, 0), (x1 - 2 * bm.CELL, yc + 4 * bm.CELL, 0), (x1 - 2 * bm.CELL, yc, 0),
             (px - half + 100, yc, RISE), (px + half - 100, yc, RISE), (px, yc - half + 100, RISE), (px, yc + half - 100, RISE), (px, yc, RISE),
             (px, yc - 5 * bm.CELL, RISE), (px, yc + 5 * bm.CELL, RISE)]
    for n, (x, y, z) in enumerate(spots):
        t = b.device(bm.TRIGGER, f"{PREFIX}Waypoint_{n:02d}", x, y, z)
        b.props(t, {"visible in Game": False})
        b.tag(t, "kt_tracking_waypoint_tag")

    # Guards
    schema = json.loads(m.tool(bm.OBJ, "list_properties", instance={"refPath": b.device(GUARD, PREFIX + "Probe", x0, ya, -5000)}))
    accuracy = (schema.get("accuracy", {}).get("enum") or ["LOW"])[0]
    for a in m.tool(bm.SCENE, "find_actors", name=PREFIX + "Probe", collision_channels=[]) or []:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for n in range(4):
        gx, gy = line_x + (7 + n) * bm.CELL, yc + (n - 1.5) * 2 * bm.CELL
        g = b.device(GUARD, f"{PREFIX}Guard_{n}", gx, gy, 0.0)
        b.face(g, 180.0)              # face the shoot line (west); they were side-on at yaw -90
        b.props(g, {"guardTeamOption": "Team Index", "guard Team Index": {"teamType": "TeamIndex", "teamIndex": 2},
                    "enablePatrol": False, "showHealthBar": True, "accuracy": accuracy, "enabledAtGameStart": True,
                    "allowInfiniteSpawn": True})
        b.tag(g, "kt_tracking_spawner_tag")

    d = b.device(DEVICE, PREFIX + "Controller", line_x, yc, 0.0)
    m.tool(bm.SCENE, "save_actor", actor={"refPath": d})
    print(f"placed: room, platform, {len(spots)} waypoints, 4 guards, controller (guard accuracy {accuracy})")


if __name__ == "__main__":
    main()
