"""Team arena pickups from the handoff: a shield truck at each base and mirrored ammo boxes (additive, KT24_Team_ only).

    python tools/build_team_pickups.py            # print the plan
    python tools/build_team_pickups.py --apply

* Shield truck: Fortnite's breakable slurp container device (PID_CP_Devices_SlurpContainer), with a tanker truck prop
  (PPID SilkyTanker) behind it so it reads as a truck. One per base, same distance from each base's spawn cells.
* Ammo boxes: the tiered ammo box (shared/team-supplies.json "ammo_boxes"), three mirrored pairs (red side / blue side).
Positions avoid the compound's floors and walls (checked against actor bounds before placing).
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT24_Team_"
SLURP = "/CR_Legacy/Playsets/PID_CP_Devices_SlurpContainer.PID_CP_Devices_SlurpContainer"
TANKER = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_Athena_Prop_SilkyTanker.PPID_CR_Legacy_Athena_Prop_SilkyTanker"
AMMO = "/CRP_Foundation/SetupAssets/Maps/PPIDs/PPID_CRP_Foundation_Tiered_Ammo_Athena.PPID_CRP_Foundation_Tiered_Ammo_Athena"
MID_X = 75776.0
# Bases sit at x 72448 (red) and 79104 (blue); spawn cells span y -56832..-55296.
TRUCKS = [("TruckRed", 72448.0, -58400.0, 0.0), ("TruckBlue", 79104.0, -58400.0, 180.0)]
AMMO_SPOTS = [(73600.0, -57600.0), (73400.0, -53300.0), (74700.0, -57900.0)]   # red half; mirrored for blue


def ammo_spots():
    out = []
    for k, (x, y) in enumerate(AMMO_SPOTS):
        out.append((f"AmmoBox{k}R", x, y))
        out.append((f"AmmoBox{k}B", 2 * MID_X - x, y))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print("trucks", TRUCKS)
    print("ammo", ammo_spots())
    if not args.apply:
        return
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []}

    def clear(x, y, r=150.0):
        for a in acts.values():
            mn, mx = a["bounds"]["min"], a["bounds"]["max"]
            if mx["x"] - mn["x"] > 3000 or mx["y"] - mn["y"] > 3000 or mx["z"] < 20 or mn["z"] > 250:
                continue
            if a["label"].startswith((PREFIX + "Truck", PREFIX + "AmmoBox")):
                continue
            if mn["x"] < x + r and mx["x"] > x - r and mn["y"] < y + r and mx["y"] > y - r:
                return a["label"]
        return None

    def put(label, asset, x, y, yaw, device):
        if label in acts:
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": acts[label]["actorPath"]})
        hit = clear(x, y)
        if hit:
            print(f"  {label}: blocked by {hit}; skipped")
            return None
        if device:
            ref = b.device(asset, label, x, y, 0.0)
        else:
            ref = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=asset, name=label,
                                    xform=bm.xform(x, y, 0.0, yaw=yaw))["refPath"], label)
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": ref}, xform=bm.xform(x, y, 0.0, yaw=yaw))
        m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
        print("  placed", label)
        return ref

    for name, x, y, yaw in TRUCKS:
        put(PREFIX + name + "Prop", TANKER, x, y - 500.0, yaw, False)
        put(PREFIX + name, SLURP, x, y, yaw, True)
    for name, x, y in ammo_spots():
        put(PREFIX + name, AMMO, x, y, 0.0, False)


if __name__ == "__main__":
    main()
