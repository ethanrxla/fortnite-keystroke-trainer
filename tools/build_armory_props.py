"""Dress the Armory with UEFN library props so it reads as a real armory.

    python tools/build_armory_props.py [--dry-run]

Additive and decorative only: the working rack (KT_Gun_<CLASS> item granters and hidden interaction
devices) is left alone. The selected weapon is visible as the Item Granter's in-game preview; players
cycle/equip through proximity prompts, with the stock button meshes hidden. Behind each front-row rack: a lit bank of lockers, with stacked
military and metal crates between them. A gun case sits on every bench, crates fill the ends, server
racks and a terminal stand at the sides and a weapon mod bench by the entrance. The guns themselves show
as each rack's hologram. Only Creative playset props (PPIDs) and devices are used: raw library meshes
(gun models, industrial shelving, Hera lockers) fail UEFN validation and block the session. Positions are read from the racks in the level (KT_Gun_<CLASS>). Labels are KT5_Armory_*.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT5_Armory_"
# Only Creative playset props (PPIDs) pass UEFN validation; raw meshes from other plugins are rejected.
LOCKERS = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_Athena_Prop_School_Lockers_01.PPID_CR_Legacy_Athena_Prop_School_Lockers_01"
METAL_CRATE = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_Athena_Prop_Storage_Metal_Crate_01.PPID_CR_Legacy_Athena_Prop_Storage_Metal_Crate_01"
ARMY_CRATE = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_MilitaryBase_Crate_01.PPID_CR_Legacy_MilitaryBase_Crate_01"
SERVER = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_MilitaryBase_ServerRack_01a.PPID_CR_Legacy_MilitaryBase_ServerRack_01a"
TERMINAL = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_MilitaryBase_ComputerTerminal.PPID_CR_Legacy_MilitaryBase_ComputerTerminal"
GUN_CASE = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_MilitaryBase_GunCase_02.PPID_CR_Legacy_MilitaryBase_GunCase_02"
TECH_CRATE = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_Apollo_MountainBase_GunCleaningCrate_01.PPID_CR_Legacy_Apollo_MountainBase_GunCleaningCrate_01"
MIL_CRATE = "/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_Athena_Prop_Military_Crate.PPID_CR_Legacy_Athena_Prop_Military_Crate"
LIGHT = "/CRD_PointLight/SetupAssets/PID_Device_PointLight.PID_Device_PointLight"
MOD_BENCH = "/CRD_WeaponModBench/SetupAssets/PID_CP_Devices_WeaponModBench.PID_CP_Devices_WeaponModBench"

FRONT = ("AR", "SMG", "SHOTGUN", "SNIPER", "PISTOL", "EXPLOSIVES")


def centre(a):
    bb = a["bounds"]
    return [(bb["min"][k] + bb["max"][k]) / 2 for k in "xyz"]


def place(b, label, asset, x, y, z, yaw=0.0, scale=1.0):
    xf = bm.xform(x, y, z, scale, scale, scale, yaw=yaw)
    ref = b.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=asset, name=label, xform=xf)["refPath"]
    b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": ref}, xform=xf)
    return b.labelled(ref, label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    racks = {lab[len("KT_Gun_"):]: centre(a) for lab, a in acts.items()
             if lab.startswith("KT_Gun_") and lab.count("_") == 2}
    front = {k: v for k, v in racks.items() if k in FRONT}
    back_y = min(v[1] for v in front.values()) - 900          # weapon wall line behind the front row
    print({k: [round(c) for c in v[:2]] for k, v in racks.items()}, "wall y", round(back_y))
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})

    xs = sorted(v[0] for v in front.values())
    for cls, (x, y, _) in front.items():
        # A bank of lockers behind each rack, lit from the front.
        place(b, f"{PREFIX}Lockers_{cls}", LOCKERS, x, back_y, 0.0, yaw=0, scale=1.0)
        light = b.device(LIGHT, f"{PREFIX}Light_{cls}", x, back_y + 350, 330.0)
        b.props(light, {"maximumRadius": 9})
    for n in range(len(xs) - 1):
        # Stacked crates in the gaps between lockers.
        mx = (xs[n] + xs[n + 1]) / 2
        place(b, f"{PREFIX}Stack_{n}_a", ARMY_CRATE, mx, back_y + 40, 0.0, yaw=0)
        place(b, f"{PREFIX}Stack_{n}_b", METAL_CRATE, mx, back_y + 40, 104.0, yaw=15)
    for cls, (x, y, _) in racks.items():
        # Keep physical cases below and behind the projected weapon preview. The earlier
        # raised/front placement overlapped the exact area where the Granter shows its gun.
        place(b, f"{PREFIX}Case_{cls}", GUN_CASE, x, y - 220, 0.0, yaw=0, scale=1.0)
    left, right = xs[0] - 700, xs[-1] + 700
    place(b, f"{PREFIX}Crate_0", TECH_CRATE, left, back_y + 150, 0.0, yaw=90, scale=1.5)
    place(b, f"{PREFIX}Crate_1", MIL_CRATE, left, back_y + 450, 0.0, yaw=90, scale=1.5)
    place(b, f"{PREFIX}Crate_2", TECH_CRATE, right, back_y + 150, 0.0, yaw=-90, scale=1.5)
    place(b, f"{PREFIX}Crate_3", MIL_CRATE, right, back_y + 450, 0.0, yaw=-90, scale=1.5)
    place(b, f"{PREFIX}Server_0", SERVER, right, back_y + 800, 0.0, yaw=-90)
    place(b, f"{PREFIX}Server_1", SERVER, right, back_y + 880, 0.0, yaw=-90)
    place(b, f"{PREFIX}Terminal", TERMINAL, left, back_y + 900, 0.0, yaw=90)
    bench = b.device(MOD_BENCH, f"{PREFIX}ModBench", right, back_y + 1500, 0.0)
    b.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": bench}, xform=bm.xform(right, back_y + 1500, 0.0, yaw=-90))
    print(f"armory dressed: {len(front)} locker banks, {len(xs) - 1} crate stacks, {len(racks)} gun cases")


if __name__ == "__main__":
    main()
