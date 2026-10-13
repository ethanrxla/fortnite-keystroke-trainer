"""Put the real guns on the armory benches: one item spawner per weapon on the bench top (KT6B_*).

    python tools/build_bench_display.py --dry-run
    python tools/build_bench_display.py            # place (a rerun replaces only KT6B_* actors)

Each KT_Gun_<class> granter already holds a validated weapon list (moddable Paprika weapons first). Each bench
(480 x 160 cm, 80 cm high, centred on the granter) gets up to 12 spawners in two rows. A spawner shows its weapon
in the world, respawns it after pickup, and the player picks it up to equip it. Moddable guns are the Paprika
core weapons, which the Weapon Mod Bench accepts; the bench is at KT5_Armory_ModBench.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT6B_"
CLASSES = ["AR", "SMG", "SHOTGUN", "SNIPER", "PISTOL", "EXPLOSIVES", "GRAPPLE", "MELEE", "HEALS"]
XS = [-200.0, -120.0, -40.0, 40.0, 120.0, 200.0]
YS = [-35.0, 35.0]
TOP = 95.0
# Shown on a bench besides its granter's list (player 2026-10-13: "we should see grappler, and theres another melee
# weapon that can go there"). All three passed push validation.
EXTRA = {"GRAPPLE": ["/Game/Athena/Items/Weapons/WID_Hook_Gun_VR_Ore_T03.WID_Hook_Gun_VR_Ore_T03",
                     # the Grapple Blade (player 2026-10-13: "i was thinking of the grapple blade")
                     "/GrappleWeapon/Items/GrappleKnife/V2/WID_GrappleKnife_VR.WID_GrappleKnife_VR"],
         "MELEE": ["/KatanaGameplay/Items/Katana/WID_Melee_Katana_R.WID_Melee_Katana_R",
                   "/CorruptionGameplay/Gameplay/Items/Weapons/Melee/Scythe/WID_PowerUp_Scythe_R.WID_PowerUp_Scythe_R"],
         # The heals bench showed one item (player 2026-10-13): the gun wall's heals as well.
         "HEALS": ["/Game/Athena/Items/Consumables/Flopper/WID_Athena_Flopper.WID_Athena_Flopper",
                   "/PaprikaConsumables/Gameplay/MedRefresh/WID_Paprika_MedBox.WID_Paprika_MedBox",
                   "/Game/Athena/Items/Consumables/SuperMedkit/Athena_SuperMedkit.Athena_SuperMedkit",
                   "/PaprikaConsumables/Gameplay/ShieldRefresh/WID_Paprika_ShieldPot.WID_Paprika_ShieldPot",
                   "/ChronoConsumables/Gameplay/SlapSplash/WID_Chrono_SlapSplash.WID_Chrono_SlapSplash"]}
BENCH = 480.0                     # bench length (cm); items are spread evenly along it


def spot(k, n):
    """Even spacing along the bench (player 2026-10-13: "placed too near to eachother"): one row up to six items,
    two rows of up to six beyond that."""
    per_row = n if n <= 6 else 6
    row, col = divmod(k, per_row)
    rows = 1 if n <= 6 else 2
    step = BENCH / per_row
    dx = (col - (per_row - 1) / 2) * step
    dy = 0.0 if rows == 1 else (YS[0] if row == 0 else YS[1])
    return dx, dy
dec = lambda v: json.loads(v) if isinstance(v, str) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    plan = []
    for c in CLASSES:
        g = acts.get(f"KT_Gun_{c}")
        if not g:
            continue
        ref = dec(m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["pickupItemList"]))["pickupItemList"]
        items = [i["itemDefinition"]["refPath"] for i in dec(m.tool(bm.OBJ, "get_properties", instance=ref, properties=["itemListData"]))["itemListData"] if i.get("itemDefinition")]
        items += [e for e in EXTRA.get(c, []) if e not in items]
        loc = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": g})["location"]
        plan.append((c, loc["x"], loc["y"], items[: len(XS) * len(YS)]))
        print(c, len(items), "items,", min(len(items), len(XS) * len(YS)), "shown at", round(loc["x"]), round(loc["y"]))
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    n = 0
    for c, x, y, items in plan:
        for k, item in enumerate(items):
            dx, dy = spot(k, len(items))
            px, py = x + dx, y + dy
            sp = b.device(bm.ITEM_SPAWNER, f"{PREFIX}{c}_{k:02d}", px, py, TOP)
            for name, value in {"items Respawn": True, "respawn Item On Timer": True, "time Between Spawns": 1.0,
                                "spawn Item On Timer": True, "time Before First Spawn": 0.5,
                                "initial Movement of Item": "None", "run Over Pickup": False, "item Scale": 1.0}.items():
                try:
                    b.props(sp, {name: value})
                except RuntimeError as exc:
                    print(f"  {c}_{k:02d}: could not set {name} ({str(exc)[-40:]})")
            comp = next(c for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": sp}) if c["refPath"].endswith("Minigame_Spawner_Component"))
            try:
                b.props(comp["refPath"], {"toSpawnList": [{"pickupToSpawn": {"refPath": item}, "pickupQuantity": 1}]})
            except RuntimeError as exc:
                print(f"  {c}_{k:02d}: item rejected {item.split('/')[-1]} ({str(exc)[-60:]})")
            m.tool(bm.SCENE, "save_actor", actor={"refPath": sp})
            n += 1
    print("placed", n, "spawners")


if __name__ == "__main__":
    main()
