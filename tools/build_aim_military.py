"""Military training-ground dressing for the existing Aim plate (additive; KT13_Mil_* only).

    python tools/build_aim_military.py --dry-run
    python tools/build_aim_military.py

Not a new area: it upgrades KT_Area_Aim (x -35840..-23552, y -90624..-83968; players stand on the KT_ShootLine_A*
strips at x -34560 and shoot +X down four lanes at y -89344 / -87808 / -86272 / -84736).
  * firing line: a sand-bag parapet in front of every lane (0.9 m, shoot over standing, crouch behind it) and
    Task Force barriers between lanes;
  * downrange cover: tank stacks and half walls (full / chest cover), crate stacks and sand bags on the north half,
    barriers on the strip between lanes A1 and A2. The practice bot (KT3_Upgrade_Practice_Bot) roams that area, so it
    now has cover to fight from;
  * a barbed-wire fence along the north edge (the south edge is the gun range wall; its door at x ~ -35330 stays open);
  * crate stacks either side of the entrance.
Every prop is kept out of the line from each shoot line to each target (checked in plan() before anything is placed),
and away from the walk from the portal to the shoot lines. Only Creative playset props (PPIDs) are used; UEFN rejects
raw meshes from other plugins on push. A rerun replaces only KT13_Mil_* actors.
"""
import argparse
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT13_Mil_"
P = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_{0}.PPID_CR_Legacy_{0}"
SANDBAG = [P.format("Apollo_TaskForce_Sand_Bag_Wall_01"), P.format("Apollo_TaskForce_Sand_Bag_Wall_02")]
BARRIER = P.format("Apollo_TaskForce_Barrier_01")
CRATE = P.format("MilitaryBase_Crate_01")
CRATE_LOW = P.format("MilitaryBase_Crate_03")
METAL = P.format("MilitaryBase_Metal_Crate_01")
TANKS = P.format("MilitaryBase_TankStack")
FENCE = P.format("Fence_Chainlink_A01_BarbedWire_Tarp")
HALFWALL = P.format("MilitaryBase_HalfWall")
# Measured footprints at yaw 0 (x = long axis for all but the tank stack, whose long axis is y), cm.
SIZE = {SANDBAG[0]: (275, 88), SANDBAG[1]: (280, 91), BARRIER: (258, 85), CRATE: (128, 115), CRATE_LOW: (163, 74),
        METAL: (99, 90), TANKS: (132, 410), FENCE: (526, 119), HALFWALL: (512, 32)}

SHOOT_X = -34560
LANES = [-89344, -87808, -86272, -84736]
# Targets in the plate (dummies, pop-up trackers, practice targets) as they stand in the level.
TARGETS = [(-32000, -89344), (-29440, -89344), (-24320, -89344), (-30464, -88320), (-29440, -87296), (-28416, -87808),
           (-29952, -87296), (-28928, -88320), (-32000, -86272), (-32000, -84736), (-32000, -88550), (-29500, -86850),
           (-27500, -85150)]
PORTAL = (-35072, -87296)
RECOIL_WALL_X = (-31300, -30650)


def plan():
    items = []

    def add(name, asset, x, y, z=0.0, yaw=0.0):
        items.append({"label": PREFIX + name, "asset": asset, "x": x, "y": y, "z": z, "yaw": yaw})

    # Firing line: a parapet segment in front of each lane, barriers between lanes.
    for i, y in enumerate(LANES):
        add(f"Parapet_{i}", SANDBAG[i % 2], -34150, y, yaw=90)
    for i, (a, b) in enumerate(zip(LANES, LANES[1:])):
        add(f"LaneBarrier_{i}", BARRIER, -34150, (a + b) / 2, yaw=90)
    # Strip between lanes A1 and A2: low barriers to move between.
    for i, x in enumerate((-31200, -27800, -25200)):
        add(f"StripBarrier_{i}", BARRIER, x, -88830)
    # Downrange cover, north half: full cover, chest cover, crate stacks, sand bags.
    add("Tanks_0", TANKS, -28950, -86000)
    add("Tanks_1", TANKS, -25600, -85000, yaw=90)
    add("HalfWall_0", HALFWALL, -27200, -86100, yaw=90)
    add("HalfWall_1", HALFWALL, -23950, -87600, yaw=90)
    add("Crates_0", CRATE, -26400, -86600)
    add("Crates_0_top", METAL, -26400, -86600, z=104)
    add("Crates_1", CRATE, -26250, -86600, yaw=15)
    add("Sandbags_0", SANDBAG[0], -24400, -86200)
    add("Sandbags_1", SANDBAG[1], -24400, -84800)
    add("Barrier_N", BARRIER, -28600, -86100, yaw=90)
    # Entrance: crate stacks either side, clear of the portal walk.
    add("Entry_S", CRATE, -35400, -90200)
    add("Entry_S_top", CRATE_LOW, -35400, -90200, z=104, yaw=10)
    add("Entry_S_side", METAL, -35250, -90020)
    add("Entry_N", CRATE, -35400, -84400)
    add("Entry_N_top", METAL, -35400, -84400, z=104)
    add("Entry_N_tanks", TANKS, -35500, -85300)
    # North edge fence, skipping the A4 recoil wall.
    x = -35500
    n = 0
    while x < -23800:
        if not RECOIL_WALL_X[0] <= x <= RECOIL_WALL_X[1] + 300:
            add(f"Fence_{n}", FENCE, x + 263, -84080)
            n += 1
        x += 526
    return items


def footprint(it):
    """The prop's footprint as an axis-aligned box (it is only ever placed at yaw 0/90 or a small tilt)."""
    length, depth = SIZE[it["asset"]]
    if abs(math.sin(math.radians(it["yaw"]))) > 0.7:
        length, depth = depth, length
    return it["x"] - length / 2, it["x"] + length / 2, it["y"] - depth / 2, it["y"] + depth / 2


def blocks_line(it, a, b, margin=60):
    """Does the segment a->b pass through the prop's footprint (grown by margin)?"""
    x0, x1, y0, y1 = footprint(it)
    x0, x1, y0, y1 = x0 - margin, x1 + margin, y0 - margin, y1 + margin
    for k in range(101):
        t = k / 100
        px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if x0 <= px <= x1 and y0 <= py <= y1:
            return True
    return False


def check(items):
    problems = []
    for it in items:
        if it["label"].startswith(PREFIX + "Parapet") or it["label"].startswith(PREFIX + "LaneBarrier"):
            continue    # 0.9 m at the shooter's feet: you shoot over it by design
        if it["z"] > 0:
            continue
        for tx, ty in TARGETS:
            lane = min(LANES, key=lambda y: abs(y - ty))      # each target is shot from its own lane
            if blocks_line(it, (SHOOT_X, lane), (tx, ty)):
                problems.append(f"{it['label']} blocks lane y={lane} -> target ({tx},{ty})")
        if blocks_line(it, PORTAL, (SHOOT_X, PORTAL[1]), margin=150):
            problems.append(f"{it['label']} blocks the walk from the portal")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    items = plan()
    problems = check(items)
    print(f"{len(items)} props planned")
    for p in problems:
        print("  PROBLEM", p)
    if args.dry_run or problems:
        return 1 if problems else 0
    m = bm.Mcp()
    for a in m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for it in items:
        xf = bm.xform(it["x"], it["y"], it["z"], yaw=it["yaw"])
        ref = m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=it["asset"], name=it["label"], xform=xf)
        m.tool(bm.ACTOR, "set_actor_transform", actor=ref, xform=xf)
        m.tool(bm.ACTOR, "set_label", actor=ref, label=it["label"])
        m.tool(bm.SCENE, "set_actor_folder", actor=ref, folder_path="KeystrokeTrainer/AimMilitary")
        m.tool(bm.SCENE, "save_actor", actor=ref)
    print("placed", len(items), "saved", m.tool("editor_toolset.toolsets.asset.AssetTools", "save_assets", asset_paths=[]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
