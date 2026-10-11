"""Team arena high ground: a sniper tower on each side and a small ammo room on each side (additive, KT27_TeamTower_).

    python tools/build_team_towers.py            # print the plan and check every piece against existing actors
    python tools/build_team_towers.py --apply    # place what is missing (reruns never duplicate)

Player 2026-10-11: "high ground rooftop sightlines ... a tower on each side (like a sniper tower), and a couple small
buildings here or there like ammo rooms. it should be neat and flow 1:1 with player builds."

Everything sits on the build grid of the shared team arena (tools/build_team_details.py: tile (u, v) spans
x 71680 + 512u, y -59904 + 512v; levels every 384 cm), so player walls, floors and ramps snap flush against it.
Red is the low-u side, Blue the mirror (u -> 15 - u).

* Tower: two tiles along v, three storeys and a roof deck at 1152 cm. Native stairs zigzag up inside it
  (0 -> 384 -> 768 -> 1152; yaw 0 climbs +v, yaw 180 climbs -v, as the compound stairs measured by
  build_team_details.py). Solid walls on three sides up to the deck, the arena-facing side open at the ground (door) and
  with a 1 m sill above it at each floor (window slots), and a 1.1 m parapet round the deck: the deck is the sniper
  spot, the parapet is crouch cover.
* Ammo room: one tile, walls on three sides, doorway towards the middle, a roof at 384 cm. The team supply service
  (TeamSupplies.verse) can use the room centre as a stock socket.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT27_TeamTower_"
STAIR = "/Game/Building/ActorBlueprints/Player/Wood/L1/PBWA_W1_StairW.PBWA_W1_StairW_C"
OX, OY, CELL, LEVEL = 71680.0, -59904.0, 512.0, 384.0
T = 12.0 / CELL                   # half wall thickness in tiles (24 cm walls, as the arena's screens)
FLOOR = 20.0                      # floor slab thickness, cm
MAT = "Armory"

# Tower base cell (u, v) per side: the two tiles (u, v) and (u, v + 1). The arena corners on the Service edge, outside
# the Service corridor (u 2..13), clear of the compounds (v 5..10) and the shield-truck props (v 1.7..3).
TOWERS = {"Red": (0, 0), "Blue": (15, 0)}
# Ammo room cell per side, on the Loading edge outside the Loading corridor (v 11..13) and the trucks.
ROOMS = {"Red": (1, 14), "Blue": (14, 14)}


def world(u, v):
    return OX + CELL * u, OY + CELL * v


def box(name, u0, u1, v0, v1, z0, z1):
    x0, y0 = world(u0, v0)
    x1, y1 = world(u1, v1)
    return dict(label=PREFIX + name, bounds=(x0, x1, y0, y1), top=z1, thick=z1 - z0, mat=MAT)


def tower(side, u, v):
    """Slabs and stairs of one tower. `inward` is the arena-facing u edge (towards the middle)."""
    inward = u + 1 if u < 8 else u          # the u edge that faces the middle
    outward = u if u < 8 else u + 1
    # The outer u edge and the v = 0 edge are the arena boundary (KT21_Team_Edge*, 384 cm): those walls sit just
    # inside the boundary line instead of straddling it.
    back = (outward, outward + 2 * T) if u < 8 else (outward - 2 * T, outward)
    s, out = [], []
    # Floors: 384 on the far tile (stair 0 lands there), 768 on the near tile (stair 1 lands there), deck 1152 on the
    # far tile (stair 2 lands there). The near tile at 1152 stays open: it is the stair well.
    s.append(box(f"{side}Floor1", u, u + 1, v + 1, v + 2, LEVEL - FLOOR, LEVEL))
    s.append(box(f"{side}Floor2", u, u + 1, v, v + 1, 2 * LEVEL - FLOOR, 2 * LEVEL))
    s.append(box(f"{side}Deck", u, u + 1, v + 1, v + 2, 3 * LEVEL - FLOOR, 3 * LEVEL))
    # Walls to the deck (1152 cm) on the outer u side and both v ends.
    s.append(box(f"{side}WallBack", *back, v, v + 2, 0, 3 * LEVEL))
    s.append(box(f"{side}WallSouth", u, u + 1, v, v + 2 * T, 0, 3 * LEVEL))
    s.append(box(f"{side}WallNorth", u, u + 1, v + 2 - T, v + 2 + T, 0, 3 * LEVEL))
    # Arena side: open at the ground (doorway), 1 m sills at the first and second floors (window slots).
    s.append(box(f"{side}Sill1", inward - T, inward + T, v, v + 2, LEVEL, LEVEL + 100))
    s.append(box(f"{side}Sill2", inward - T, inward + T, v, v + 2, 2 * LEVEL, 2 * LEVEL + 100))
    # Deck parapet (crouch cover) round the deck tile, and the stair-well edge on the arena side.
    top = 3 * LEVEL + 110
    s.append(box(f"{side}ParapetIn", inward - T, inward + T, v, v + 2, 3 * LEVEL, top))
    s.append(box(f"{side}ParapetBack", *back, v, v + 2, 3 * LEVEL, top))
    s.append(box(f"{side}ParapetNorth", u, u + 1, v + 2 - T, v + 2 + T, 3 * LEVEL, top))
    s.append(box(f"{side}ParapetSouth", u, u + 1, v, v + 2 * T, 3 * LEVEL, top))
    # Stairs: (name, cell v, level, yaw). Stair 0 climbs from the near tile onto Floor1, stair 1 from Floor1 back onto
    # Floor2, stair 2 from Floor2 onto the deck.
    out = [(f"{side}Stair0", u, v, 0, 0), (f"{side}Stair1", u, v + 1, 1, 180), (f"{side}Stair2", u, v, 2, 0)]
    return s, out


def room(side, u, v):
    inward = u + 1 if u < 8 else u
    outward = u if u < 8 else u + 1
    return [box(f"{side}RoomBack", outward - T, outward + T, v, v + 1, 0, LEVEL),
            box(f"{side}RoomNorth", u, u + 1, v + 1 - T, v + 1 + T, 0, LEVEL),
            # The doorway faces the middle (inward u edge); the south side stays open towards the Loading lane.
            box(f"{side}RoomDoorJamb", inward - T, inward + T, v + .75, v + 1, 0, LEVEL),
            box(f"{side}RoomRoof", u, u + 1, v, v + 1, LEVEL - FLOOR, LEVEL)]


def plan():
    slabs, stairs = [], []
    for side, (u, v) in TOWERS.items():
        s, st = tower(side, u, v)
        slabs += s
        stairs += st
    for side, (u, v) in ROOMS.items():
        slabs += room(side, u, v)
    return slabs, stairs


def stair_bounds(u, v, k):
    x0, y0 = world(u, v)
    return x0, x0 + CELL, y0, y0 + CELL, k * LEVEL, (k + 1) * LEVEL


def blockers(acts, x0, x1, y0, y1, z0, z1, pad=2.0):
    """Labels of existing actors (not ours, not ground or huge shells) whose bounds overlap the box."""
    hit = []
    for a in acts:
        lab = a["label"]
        if lab.startswith(PREFIX):
            continue
        mn, mx = a["bounds"]["min"], a["bounds"]["max"]
        if mx["x"] - mn["x"] > 9000 or mx["y"] - mn["y"] > 9000 or mx["z"] <= 5:
            continue
        if mn["x"] < x1 - pad and mx["x"] > x0 + pad and mn["y"] < y1 - pad and mx["y"] > y0 + pad \
                and mn["z"] < z1 - pad and mx["z"] > z0 + pad:
            hit.append(lab)
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    slabs, stairs = plan()
    b = bm.Builder()
    m = b.m
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    ours = {a["label"]: a for a in acts if a["label"].startswith(PREFIX)}
    problems = 0
    for s in slabs:
        x0, x1, y0, y1 = s["bounds"]
        hit = blockers(acts, x0, x1, y0, y1, s["top"] - s["thick"], s["top"])
        if hit:
            problems += 1
        print(f"{s['label']:34s} {'present' if s['label'] in ours else 'new':7s} {'BLOCKED by ' + ', '.join(hit[:3]) if hit else 'clear'}")
    for name, u, v, k, yaw in stairs:
        hit = blockers(acts, *stair_bounds(u, v, k))
        if hit:
            problems += 1
        print(f"{PREFIX + name:34s} {'present' if PREFIX + name in ours else 'new':7s} {'BLOCKED by ' + ', '.join(hit[:3]) if hit else 'clear'}")
    if not args.apply:
        return
    if problems:
        raise SystemExit(f"{problems} pieces overlap existing actors; move them before --apply")
    if m.tool(bm.SCENE, "get_current_level") != bm.MODULE + "/KeystrokeTrainer":
        raise SystemExit("wrong level open")
    for s in slabs:
        if s["label"] in ours:
            continue
        path = b.slab(s)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
        print("placed", s["label"], flush=True)
    offsets = {0: (.5, 0), 180: (.5, 1)}      # native stair pivot per yaw, measured in build_team_details.py
    report = []
    for name, u, v, k, yaw in stairs:
        label = PREFIX + name
        if label not in ours:
            du, dv = offsets[yaw]
            x, y = world(u + du, v + dv)
            ref = m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=STAIR, name=label, xform=bm.xform(x, y, k * LEVEL, yaw=yaw))
            path = b.labelled(ref["refPath"], label)
            b.props(path, {"bCanBeDamaged": False})
            m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
            print("placed", label, flush=True)
        got = [a for a in m.tool(bm.SCENE, "find_actors", name=label, collision_channels=[]) or [] if a["label"] == label]
        want = stair_bounds(u, v, k)
        bd = got[0]["bounds"] if got else None
        ok = bool(bd) and all(abs(g - w) <= 20 for g, w in zip(
            (bd["min"]["x"], bd["max"]["x"], bd["min"]["y"], bd["max"]["y"], bd["min"]["z"], bd["max"]["z"]), want))
        report.append((label, ok))
    for label, ok in report:
        print(label, "bounds ok" if ok else "BOUNDS OFF (check in editor)")


if __name__ == "__main__":
    main()
