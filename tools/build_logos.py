"""Put the RXLA logo on the map: flat panels with the logo material, no collision.

    python tools/build_logos.py [--dry-run]

Uses T_RXLA_Logo (imported from assets/brand/rxla-1205.png into KT_Brand) through M_KT_Logo, an unlit,
masked, two-sided material whose texture parameter is "Logo". The panel mesh is the 100 x 100 cm
ShapeTools rectangle; a logo faces a viewer direction `facing` (degrees, 0 = +X) with
rotation (pitch 0, yaw facing - 90, roll 90), found by checking the panel in the editor camera.
Labels are KT4_Logo_*; only those are replaced.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT4_Logo_"
RECT = bm.MODULE + "/Content/ShapeTools/Meshes/Rectangle_9A61793C.Rectangle_9A61793C"
LOGO_MAT = bm.MODULE + "/KT_Brand/M_KT_Logo.M_KT_Logo"


def spots():
    hi, hj = bm.HUB_CELL
    north_face = (hi + 5) * bm.CELL - 30          # inside face of the hub's north wall
    south_face = (hi - 4) * bm.CELL + 30          # inside face of the hub's south wall, behind spawn
    out = []
    for name, dj in (("HubNorthWest", -3), ("HubNorthEast", 3)):
        _, y = bm.hub_cc(0, dj)
        out.append((name, north_face, y, 800, 700, 180))
    _, y = bm.hub_cc(0, 0)
    out.append(("HubSouth", south_face, y, 1150, 650, 0))     # above the Edit doorway and its gate sign
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    places = spots()
    arena = acts.get("KT_ArenaWall_N")
    if arena:
        bb = arena["bounds"]
        places.append(("Arena", bb["min"]["x"] - 30, (bb["min"]["y"] + bb["max"]["y"]) / 2, 700, 800, 180))
    for p in places:
        print(p)
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for name, x, y, z, size, facing in places:
        xf = {"location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": 0, "yaw": facing - 90, "roll": 90},
              "scale": {"x": size / 100.0, "y": size / 100.0, "z": 1}}
        ref = b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=RECT, name=PREFIX + name, xform=xf)["refPath"]
        b.labelled(ref, PREFIX + name)
        mesh = next(c["refPath"] for c in b.m.tool(bm.ACTOR, "get_components", actor={"refPath": ref})
                    if "StaticMeshComponent" in c["refPath"])
        b.props(mesh, {"OverrideMaterials": [{"refPath": LOGO_MAT}], "bUseDefaultCollision": False,
                       "bodyInstance": {"collisionEnabled": "NoCollision"}})
    print(f"logos placed: {len(places)}")


if __name__ == "__main__":
    main()
