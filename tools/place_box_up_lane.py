"""Box up (P4) in the 90s room: one room where players rep boxes and 90s (player 2026-10-13: "box up is just for
building a tower ... we should have like one room as well as sky box. thats where players can rep boxes and 90s").

    python tools/place_box_up_lane.py --dry-run
    python tools/place_box_up_lane.py

The 90s lane (KT_Lane_P6) runs every rep on its first track, so the room's other tracks are free. KT_Lane_P4 goes on
the room's sixth track (5 x 1024 cm along +Y from the 90s start, same x and z), on the build grid: a cell centre.
Like every lane it starts from its drill plate (no pad), keeps every rep on one track, clears between reps through the
room's clear trigger (KT3_Clear_P6, the nearest kt_clear_tag), with a barrel of its own on its start
(KT31_Clear_P4_Track1). The room's exit rift (KT30_Drill_P6_Exit) serves both drills.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

DRILL_DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-keystroke_drill_device"
OFFSET_Y = 5 * 1024.0
BARREL = {"blast Radius": 8, "player Damage": 0, "structure Damage": 100000, "visible During Game": False,
          "knockbackPlayer": 0}
LANE = {"drillId": "box_up", "autoPad": False, "sameTrack": True, "clearEachRep": True, "flowStepSeconds": 1.5,
        "repRestSeconds": 2.5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    p6 = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts["KT_Lane_P6"]["actorPath"]})["location"]
    x, y, z = p6["x"], p6["y"] + OFFSET_Y, p6["z"]
    ledge = acts["KT_Ledge_P6"]["bounds"]
    box_x = x + bm.CELL                                       # box up builds one cell forward of the start
    on_floor = (ledge["min"]["x"] <= x - 256 and box_x + 256 <= ledge["max"]["x"]
                and ledge["min"]["y"] <= y - 256 and y + 256 <= ledge["max"]["y"])
    print(f"KT_Lane_P4 at ({x:.0f}, {y:.0f}, {z:.0f}); grid: x mod 512 = {x % 512:.0f}, y mod 512 = {y % 512:.0f}; "
          f"start and box cells on the 90s ledge: {on_floor}")
    if not on_floor:
        raise SystemExit("the 90s ledge does not reach the box cell; not placing")
    if args.dry_run:
        return
    for label in ("KT_Lane_P4", "KT31_Clear_P4_Track1"):
        if label in acts:
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": acts[label]["actorPath"]})
    lane = b.device(DRILL_DEVICE, "KT_Lane_P4", x, y, z)
    for key, value in LANE.items():
        m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName=key, value=json.dumps(value))
    b.tag(lane, "kt_lane_tag")
    m.tool(bm.SCENE, "save_actor", actor={"refPath": lane})
    print(m.tool(bm.DEVICE, "GetDeviceProperties", device={"refPath": lane}, propertyNames=list(LANE)))
    barrel = b.device(bm.EXPLOSIVE, "KT31_Clear_P4_Track1", x, y, z)
    b.props(barrel, BARREL)
    b.bind(acts["KT3_Clear_P6"]["actorPath"], "OnTriggered", barrel, "Explode")
    b.bind(barrel, "On Exploded", barrel, "Reset")
    m.tool(bm.SCENE, "save_actor", actor={"refPath": barrel})
    print("placed KT_Lane_P4 and its clear barrel; now run tools/build_drill_plates.py")


if __name__ == "__main__":
    main()
