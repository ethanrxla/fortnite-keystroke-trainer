"""Shootable EXIT plates for the rooms the drill plates do not cover (KT41_Exit_*), additive.

    python tools/build_room_exits.py --dry-run
    python tools/build_room_exits.py
    then: python tools/refit_hitboxes.py --only KT41_Exit_

Player 2026-10-20: "all rooms should have a shoot to exit, including the sky box", "all rooms should have shootable
exit buttons, such as aim practice, skybox, freebuild, (some of them only have a rift)". The drill rooms already have
theirs (tools/build_drill_plates.py, KT30_Drill_Exit_*); this adds the same red EXIT plate, made the same way (plane
OFF in front of its wall, a grid of hit dummies between plate and wall from hitbox.place_grid, whose On Hit teleports
the shooter), to the aim practice room, gun range, tracking range, 1v1 arena, Piece Lab, Sky Box and free build.
Every one sends you to the hub (KT2_HubArrival: no target group of its own, so Teleport lands on it). The rooms' walk-in
rifts stay. Plates on a wall facing +X use yaw 270 (dummies 0), on a wall facing -X yaw 90 (dummies 180), as the drill
plates do; Sky Box and free build have no back wall there, so their plates stand free.
A rerun replaces only KT41_Exit_* actors.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402
import hitbox  # noqa: E402
from build_drill_plates import OFF, DUMMY_OFF, TEX_FOLDER, EXIT_Z, EXIT_SIZE, plate_texture  # noqa: E402

PREFIX = "KT41_Exit_"
ARRIVAL = "KT2_HubArrival"
# room: (wall face x, facing (+1 into +X / -1 into -X), [plate y...], plate centre z)
EXITS = {
    "Aim": (-35840.0, 1, [-89600.0, -85000.0], EXIT_Z),          # back wall behind the shoot lines (rift at -87296)
    "Range": (-35840.0, 1, [-95744.0, -91648.0], EXIT_Z),        # KT8_Range_Wall_Back, behind the booths
    "Track": (-35840.0, 1, [-101376.0, -98304.0], EXIT_Z),       # KT11_Track_Wall_W
    "Arena": (-35840.0, 1, [-78592.0, -75008.0], EXIT_Z),        # staging side (rift at -76544)
    "Lab": (-16384.0, -1, [-101120.0, -98560.0], EXIT_Z),        # KT12_Room_Wall_E
    "Sky": (20992.0 - 700.0, 1, [-44032.0], 7698.0 + 300.0),      # free-standing, behind the start platform's rift
    # free-standing past the end landing (KT18_Sky_End, east edge x 28416) and its rift, facing back down the strip
    # (player 2026-10-20: "add a rift and shoot to exit at the end of skybox")
    "SkyEnd": (28416.0 + 444.0, -1, [-44032.0], 7698.0 + 300.0),
    # the Operation's extraction corner (bombsite A, tools/build_operation.py EXTRACT): on the site's west wall
    "OpExtract": (-25600.0, 1, [-74240.0], EXIT_Z),
    # the crawl room, where an Operation run starts: its west wall (player 2026-10-21, one way in, so a way out here)
    "OpStart": (-35840.0, 1, [-69120.0], EXIT_Z),
    # free-standing at the free build's west edge; the second sits one cell north of the RESET button, in view of where
    # you land (KT2_FreeArrival, KT25_SignShot_KT2_FreeLabel_Arrive; player 2026-10-25: "there needs to be an exit
    # tile nearby")
    "Free": (7166.0 - 200.0, 1, [-34816.0, -32768.0], EXIT_Z),
}


def plan():
    out = []
    for room, (face, sign, ys, z) in EXITS.items():
        for k, y in enumerate(ys):
            out.append(dict(label=f"{PREFIX}{room}_{k}", x=face + sign * OFF, y=y, z=z, dx=face + sign * DUMMY_OFF,
                            plane_yaw=270.0 if sign > 0 else 90.0, dummy_yaw=0.0 if sign > 0 else 180.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    plates = plan()
    for p in plates:
        print(f"  {p['label']:18} ({p['x']:.0f}, {p['y']:.0f}, {p['z']:.0f}) yaw {p['plane_yaw']:.0f}")
    if args.dry_run:
        return
    g = ag.Grid()
    b, m = g.b, g.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    arrival = acts.get(ARRIVAL)
    if not arrival:
        raise SystemExit(f"{ARRIVAL} not found")
    old = [p for l, p in acts.items() if l.startswith(PREFIX)]
    for p in old:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": p})
    print("removed", len(old))
    png, tex = plate_texture("EXIT", "EXIT", (0.30, 0.02, 0.02))
    if not m.tool(ag.AS, "exists", path=tex.split(".")[0]):
        m.tool("editor_toolset.toolsets.texture.TextureTools", "import_file", folder_path=TEX_FOLDER,
               asset_name=tex.split(".")[-1], source_file=str(png))
        m.tool(ag.AS, "save_assets", asset_paths=[tex])
    mat = g.icon_material(tex)
    for p in plates:
        plate = g.plane(p["label"] + "_Plate", p["x"], p["y"], p["z"], EXIT_SIZE, p["plane_yaw"], mat)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": plate})
        hitbox.place_grid(b, p["label"] + "_Hit", (p["x"], p["y"], p["z"]), EXIT_SIZE, EXIT_SIZE, p["dummy_yaw"],
                          (p["dx"], p["y"]), [(arrival, "Teleport")])
    print(f"placed {len(plates)} EXIT plates -> {ARRIVAL}")


if __name__ == "__main__":
    main()
