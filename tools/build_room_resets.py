"""Builds vanish from the whole of every drill room: a grid of hidden reset barrels per room (KT39_RoomReset_*).

    python tools/build_room_resets.py --dry-run
    python tools/build_room_resets.py

Player 2026-10-20: "builds need to periodically reset in each room, especially when doing 90s and box up after each
rep the builds should dissapear, and the same goes for all other drills where players might start placing builds";
picked "every 60 s when idle". The rooms already had a few overhead barrels (KT34_Reset_*, KT_Boom_*), but each
reaches only about 13 m at floor level, so corners and room ends kept their builds.
* Each room's interior (from its KT_Wall / KT_Ceil_Lane / KT_Ledge bounds) gets barrels on a GRID_CM square grid,
  one layer LOW_CM above the floor and, for rooms taller than TALL_CM, a second at HIGH_CM, so every floor cell and
  every build up to the ceiling is inside a 4.75-tile blast. Settings copy the KT34_Reset_* rigs: structure damage
  only, hidden, no collision, no audio, no line of sight, never indestructible buildings (the pre-built enemy boxes
  and lab pieces stay), re-armed on explode. Nothing sits within START_CLEAR_CM of a lane start.
* Lane rooms: the room's existing kt_clear_tag trigger fires its grid, so DrillDevice clears it at set start, after
  every rep (ClearEachRep, set on here for every build lane) and on leaving, and every 60 s while no lane in the room
  runs a set (DrillDevice IdleClearSeconds). P6 and P4 share one room and both triggers fire its grid.
* Piece Lab (no lane device): a 60 s restarting timer fires its grid.
* Not W2 wall take: its enemy walls are meant to be shot and taken (damageable), and a reset would destroy them.
A rerun replaces only KT39_RoomReset_* actors (and only adds bindings to the existing triggers).
"""
import argparse
import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT39_RoomReset_"
TIMER = "/CreativeCoreDevices/SetupAssets/PID_Device_Timer.PID_Device_Timer"
GRID_CM = 3000.0
LOW_CM, HIGH_CM, TALL_CM = 700.0, 1900.0, 1700.0
INSET_CM = 300.0
START_CLEAR_CM = 450.0
BARREL = {"blast Radius": 4.75, "player Damage": 0, "structure Damage": 10000, "visible During Game": False,
          "collision During Games": "Off", "requires Line of Sight": False, "play Audio": False,
          "time Until Reset Allowed": 0, "knockbackPlayer": 0, "damage Indestructible Buildings": False,
          "display Damage Numbers": False, "blastLineOfSight": False}
# room -> (lanes whose start must stay clear, existing clear triggers to wire)
ROOMS = {"B5": (["B5"], ["KT3_Clear_B5"]), "P2": (["P2"], ["KT3_Clear_P2"]),
         "P6": (["P6", "P4"], ["KT34_Reset_P6_Trigger", "KT34_Reset_P4_Trigger"]),
         "P7": (["P7"], ["KT3_Clear_P7"]), "W3": (["W3"], ["KT3_Clear_W3"]), "E7": (["E7"], ["KT3_Clear_E7"])}
LANES = ["B5", "P2", "P6", "P4", "P7", "W3", "E7"]


def room_box(acts, code):
    if code == "LAB":
        parts = [a for a in acts if a["label"].startswith("KT12_Room_Wall_")]
    else:
        parts = [a for a in acts if re.match(rf"KT_(Wall|Ceil_Lane|Ledge)_{code}(_|$)", a["label"])]
    if not parts:
        return None
    lo = {k: min(a["bounds"]["min"][k] for a in parts) for k in "xyz"}
    hi = {k: max(a["bounds"]["max"][k] for a in parts) for k in "xyz"}
    return lo, hi


def grid(lo, hi, floor, starts):
    xs = max(1, math.ceil((hi["x"] - lo["x"] - 2 * INSET_CM) / GRID_CM))
    ys = max(1, math.ceil((hi["y"] - lo["y"] - 2 * INSET_CM) / GRID_CM))
    layers = [floor + LOW_CM] + ([floor + HIGH_CM] if hi["z"] - floor > TALL_CM else [])
    out = []
    for i in range(xs + 1):
        for j in range(ys + 1):
            x = lo["x"] + INSET_CM + (hi["x"] - lo["x"] - 2 * INSET_CM) * i / xs
            y = lo["y"] + INSET_CM + (hi["y"] - lo["y"] - 2 * INSET_CM) * j / ys
            for sx, sy in starts:
                if math.hypot(x - sx, y - sy) < START_CLEAR_CM:
                    x += START_CLEAR_CM if x < hi["x"] - START_CLEAR_CM else -START_CLEAR_CM
            for z in layers:
                out.append((round(x), round(y), round(z)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []
    by = {a["label"]: a for a in acts}
    plan = {}
    for code in list(ROOMS) + ["LAB"]:
        box = room_box(acts, code)
        if not box:
            print(f"  {code}: no room geometry, skipped")
            continue
        lo, hi = box
        lanes = ROOMS.get(code, ([], []))[0]
        starts = []
        for lane in lanes:
            a = by.get(f"KT_Lane_{lane}")
            if a:
                starts.append(((a["bounds"]["min"]["x"] + a["bounds"]["max"]["x"]) / 2,
                               (a["bounds"]["min"]["y"] + a["bounds"]["max"]["y"]) / 2))
        plan[code] = grid(lo, hi, 0.0, starts)
        print(f"  {code}: x {lo['x']:.0f}..{hi['x']:.0f} y {lo['y']:.0f}..{hi['y']:.0f} top {hi['z']:.0f} -> {len(plan[code])} barrels")
    if args.dry_run:
        return
    for a in acts:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for code, pts in plan.items():
        barrels = []
        for n, (x, y, z) in enumerate(pts):
            boom = b.device(bm.EXPLOSIVE, f"{PREFIX}{code}_{n:02d}", x, y, z)
            for key, value in BARREL.items():
                try:
                    b.props(boom, {key: value})
                except RuntimeError as exc:
                    print(f"  {code}: barrel {key} refused ({str(exc)[-60:]})")
            b.bind(boom, "On Exploded", boom, "Reset")
            barrels.append(boom)
        if code == "LAB":
            lo, hi = room_box(acts, "LAB")
            timer = b.device(TIMER, f"{PREFIX}LAB_Timer", lo["x"] + 200, lo["y"] + 200, -400.0)
            schema = json.loads(m.tool(bm.OBJ, "list_properties", instance={"refPath": timer}))
            restart = next((e for e in (schema.get("completionBehavior") or {}).get("enum", []) if "estart" in e), None)
            props = {"duration": 60.0, "startAtGameStart": True, "visibleDuringGame": False, "successOnTimerEnd": True}
            if restart:
                props["completionBehavior"] = restart
            b.props(timer, props)
            sources = [(timer, "OnSuccess")]
            barrels.append(timer)
        else:
            sources = [(by[t]["actorPath"], "OnTriggered") for t in ROOMS[code][1] if t in by]
        for src, event in sources:
            for boom in barrels:
                if boom != src and not boom.endswith("_Timer"):
                    b.bind(src, event, boom, "Explode")
        for p in barrels:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
        print(f"  {code}: {len(pts)} barrels wired to {[s[1] for s in sources]} x{len(sources)}")
    for lane in LANES:
        a = by.get(f"KT_Lane_{lane}")
        if a:
            m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": a["actorPath"]}, propertyName="clearEachRep", value="true")
            m.tool(bm.SCENE, "save_actor", actor={"refPath": a["actorPath"]})
    print("clearEachRep on for", LANES)


if __name__ == "__main__":
    main()
