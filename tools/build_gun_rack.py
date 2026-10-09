"""Show the real guns: one item spawner per weapon on a floor rack in the armory (KT6_Rack_*).

    python tools/build_gun_rack.py --dry-run
    python tools/build_gun_rack.py                 # place the rack
    python tools/build_gun_rack.py --retire-buttons  # also remove the PREV / GIVE / NEXT buttons and their labels

Each spawner holds one weapon, spawns it at game start and again after it is picked up, so the player sees the
actual gun and walks over it to equip it. The weapon lists come from the existing KT_Gun_<class> item granters,
which already passed island validation. A rerun replaces only KT6_Rack_* actors.
"""

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT6_Rack_"
CLASSES = ["AR", "SMG", "SHOTGUN", "SNIPER", "PISTOL", "EXPLOSIVES", "HEALS", "GRAPPLE", "MELEE"]
X0, Y0 = -2900.0, -63200.0      # first slot; free floor between the granter benches and the hub gate
DX, DY = 190.0, 420.0           # slot spacing along x, row spacing along y
PER_ROW = 12


def granter_items(b, acts):
    out = {}
    for c in CLASSES:
        a = acts.get(f"KT_Gun_{c}")
        if not a:
            continue
        for prop in ("itemList", "pickupItemList"):
            try:
                comp = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": a["actorPath"]}, properties=[prop]))[prop]["refPath"]
                data = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": comp}, properties=["itemListData"]))["itemListData"]
            except (RuntimeError, KeyError, json.JSONDecodeError):
                continue
            paths = [x["itemDefinition"]["refPath"] for x in data]
            if paths:
                out[c] = paths
                break
    return out


def short(path):
    base = path.rsplit(".", 1)[-1]
    base = re.sub(r"^WID_(Figment_)?|_Athena|_Ore_T\d+$|(?<=_)(C|UC|R|VR|SR)$", "", base)
    return re.sub(r"[_ ]+", " ", base).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--retire-buttons", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    acts = {a["label"]: a for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    items = granter_items(b, acts)
    total = sum(len(v) for v in items.values())
    print({k: len(v) for k, v in items.items()}, "total", total)
    if args.dry_run or not total:
        return
    for label, a in acts.items():
        if label.startswith(PREFIX):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    n = 0
    for cls, paths in items.items():
        # new row for each class; a class with more than PER_ROW guns wraps
        row_start = n
        for k, path in enumerate(paths):
            slot = n
            x = X0 + (slot % PER_ROW) * DX
            y = Y0 + (slot // PER_ROW) * DY
            sp = b.device(bm.ITEM_SPAWNER, f"{PREFIX}{cls}_{k:02d}", x, y, 80.0)
            for name, value in {"items Respawn": True, "respawn Item On Timer": True, "time Between Spawns": 1.0,
                                "spawn Item On Timer": True, "time Before First Spawn": 0.5,
                                "initial Movement of Item": "None", "run Over Pickup": True, "item Scale": 1.0}.items():
                try:
                    b.props(sp, {name: value})
                except RuntimeError as exc:
                    print(f"  {cls}_{k:02d}: could not set {name} ({str(exc)[-40:]})")
            bm.fill_item_list(b, sp, [path])
            b.sign({"label": f"{PREFIX}Label_{cls}_{k:02d}", "pos": (x, y - 120.0, 40.0), "yaw": 90,
                    "text": short(path), "size": 10, "zone": "Armory"})
            n += 1
        print(f"{cls}: {len(paths)} guns from slot {row_start}")
    if args.retire_buttons:
        gone = 0
        for label, a in acts.items():
            if re.match(r"KT_Gun_[A-Z]+_(PREV|NEXT|GIVE)$", label) or label.startswith("KT3_GunRack_Label_"):
                b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
                gone += 1
        print("removed", gone, "button and label actors")
    print("rack placed:", n, "spawners")


if __name__ == "__main__":
    main()
