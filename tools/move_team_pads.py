"""Move the eight team-mode join pads into the hub lobby, in front of the RXLA TRAINING GROUND sign, and make the apron safe.

    python tools/move_team_pads.py            # print the plan
    python tools/move_team_pads.py --apply    # move KT24_Team_JoinPad0-7 / Reference0-7, place KT24_Team_PadSafe
    python tools/move_team_pads.py --apply --enable   # also switch on the queue for private playtests

Player 2026-10-11: "the glowing selector pads for the skirmish/ctf/zone should be located in the lobby in front of
RXLA TRAINING. players standing in it are invincible and cant deal damage". Two rows of four facing the title sign
(KT_Sign_Title, on x=1209 facing -X): the row nearer spawn is red (pads 0-3), the row nearer the sign blue (4-7).
TeamQueueDevice.verse holds health and shields on the apron; the mutator below stops weapon fire on it.
--enable sets AcceptQueue, ReadyForPlaytest and AmmoPolicyVerified for a private playtest; CTF stays gated
(CTFDevicesVerified) until its flags are wired.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT24_Team_"
MUTATOR = "/CRD_VolumetricRegion/SetupAssets/PID_Device_Mutator.PID_Device_Mutator"
ROWS_X = (350.0, 800.0)                         # red row, blue row
COLS_Y = (-61300.0, -60950.0, -60600.0, -60250.0)
SAFE_CENTRE = (575.0, -60775.0)
SAFE_TILES = 3.0                                # mutator zone size in 5.12 m tiles (the arena's no-build zone uses 16)


def positions():
    return [(ROWS_X[i // 4], COLS_Y[i % 4], 0.0) for i in range(8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--enable", action="store_true")
    args = ap.parse_args()
    print(json.dumps({"pads": positions(), "safe": SAFE_CENTRE}))
    if not args.apply:
        return
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a["actorPath"] for a in m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []}
    for i, (x, y, z) in enumerate(positions()):
        for kind in ("JoinPad", "Reference"):
            path = acts.get(f"{PREFIX}{kind}{i}")
            if not path:
                print("missing", kind, i)
                continue
            m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path}, xform=bm.xform(x, y, z, yaw=180.0))
            m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    safe = acts.get(PREFIX + "PadSafe") or b.device(MUTATOR, PREFIX + "PadSafe", SAFE_CENTRE[0], SAFE_CENTRE[1], 0.0)
    m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": safe}, xform=bm.xform(SAFE_CENTRE[0], SAFE_CENTRE[1], 0.0))
    b.props(safe, {"zoneWidth": SAFE_TILES, "zoneDepth": SAFE_TILES, "zoneHeight": 3.0, "bAllowWeaponFire": False,
                   "bAllowBuilding": False, "bAffectsPlayers": True, "bAffectsGuards": False,
                   "zoneVisibleDuringGame": False, "enabledOnPhase": "Always"})
    m.tool(bm.SCENE, "save_actor", actor={"refPath": safe})
    if args.enable:
        # Verse @editable fields are set through SetDeviceProperty with camelCase names.
        for label, prop in ((PREFIX + "Queue", "acceptQueue"),):
            if label in acts:
                m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": acts[label]}, propertyName=prop, value="true")
        match = [l for l in acts if l.startswith(PREFIX + "Match")]
        for label in match:
            for prop in ("readyForPlaytest", "ammoPolicyVerified"):
                m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": acts[label]}, propertyName=prop, value="true")
            m.tool(bm.SCENE, "save_actor", actor={"refPath": acts[label]})
        if PREFIX + "Queue" in acts:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": acts[PREFIX + "Queue"]})
        print("queue enabled for private playtests:", [PREFIX + "Queue"] + match)
    print("pads moved to the hub lobby; safe apron placed")


if __name__ == "__main__":
    main()
