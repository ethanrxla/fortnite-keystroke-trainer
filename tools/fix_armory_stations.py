"""Refill the armory's PREV / GIVE / NEXT stations (KT_Gun_<CLASS> item granters) with complete item lists.

    python tools/fix_armory_stations.py            # show what each station holds and what it would get
    python tools/fix_armory_stations.py --apply

Player 2026-10-11: "shields only has a big pot where it says shields / 4 choices; same for grapple, some of the stuff
is missing; there's a grapple gun and a grapple hook; previously there were more grapple options and melee". The HEALS
and EXPLOSIVES lists had empty (None) entries left behind by earlier pruning, so cycling showed one or four items, and
GRAPPLE held only the gloves. Each item is added one at a time and kept only if the granter accepts it; items UEFN
rejects on push (shared/asset-exclusions.json) are never added.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

dec = lambda v: json.loads(v) if isinstance(v, str) else v
W = "/Game/Athena/Items/Weapons/"
WANT = {
    "HEALS": ["/Game/Athena/Items/Consumables/Shields/Athena_Shields.Athena_Shields",
              "/PaprikaConsumables/Gameplay/ShieldRefresh/WID_Paprika_ShieldPot.WID_Paprika_ShieldPot",
              "/PaprikaConsumables/Gameplay/ShieldSmallRefresh/WID_Paprika_ShieldSmall.WID_Paprika_ShieldSmall",
              "/PaprikaConsumables/Gameplay/MedRefresh/WID_Paprika_MedBox.WID_Paprika_MedBox",
              "/PaprikaConsumables/Gameplay/BandageRefresh/WID_Paprika_Bandage.WID_Paprika_Bandage",
              "/ChronoConsumables/Gameplay/SlapSplash/WID_Chrono_SlapSplash.WID_Chrono_SlapSplash",
              # Player 2026-10-11: "there should be fish & heals".
              "/Game/Athena/Items/Consumables/Flopper/WID_Athena_Flopper.WID_Athena_Flopper",
              "/Game/Athena/Items/Consumables/Flopper/ShieldFlopper/WID_Athena_Flopper_Shield.WID_Athena_Flopper_Shield",
              "/Game/Athena/Items/Consumables/Flopper/HopFlopper/WID_Athena_Flopper_HopFlopper.WID_Athena_Flopper_HopFlopper"],
    "GRAPPLE": ["/GrappleGloves/Items/GrappleGloves/WID_GrappleGloves.WID_GrappleGloves",
                f"{W}WID_Hook_Gun_VR_Ore_T03.WID_Hook_Gun_VR_Ore_T03",
                "/GrappleWeapon/Items/GrappleKnife/V2/WID_GrappleKnife_R.WID_GrappleKnife_R",
                "/GrappleWeapon/Items/GrappleKnife/V2/WID_GrappleKnife_VR.WID_GrappleKnife_VR",
                "/CorruptionGameplay/Gameplay/Items/Consumables/IcyGrapple/WID_Athena_IcyGrapple.WID_Athena_IcyGrapple",
                "/GrappleGlider/Items/WID_GrappleGlider.WID_GrappleGlider",
                "/PrimalGameplay/Items/Exotics/GrapplerBow/WID_Athena_Bow_Grappler.WID_Athena_Bow_Grappler"],
    "MELEE": ["/CRD_Melee/SetupAssets/WID_Creative_Melee_Sword_Ninja.WID_Creative_Melee_Sword_Ninja",
              "/CRD_Melee/SetupAssets/WID_Creative_Melee_Hammer_SledgeWrapped.WID_Creative_Melee_Hammer_SledgeWrapped",
              "/KatanaGameplay/Items/Katana/WID_Melee_Katana_R.WID_Melee_Katana_R",
              "/KatanaGameplay/Items/Katana/WID_Melee_Katana_SR.WID_Melee_Katana_SR",
              "/VampireKatanaGameplay/Items/VampireKatana/WID_Melee_Vampire_Katana.WID_Melee_Vampire_Katana"],
}
CLEAN_ONLY = ("EXPLOSIVES",)     # keep what is there, drop the empty entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    rejected = set(json.loads((bm.ROOT / "shared" / "asset-exclusions.json").read_text())["rejected_item_paths"])
    found = {a["label"]: a["actorPath"] for a in m.tool(bm.SCENE, "find_actors", name="KT_Gun_", collision_channels=[]) or []}
    for cat in list(WANT) + list(CLEAN_ONLY):
        if args.only and cat != args.only:
            continue
        g = found.get("KT_Gun_" + cat)
        if not g:
            print(cat, "no station")
            continue
        lst = dec(m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["pickupItemList"]))["pickupItemList"]
        cur = dec(m.tool(bm.OBJ, "get_properties", instance=lst, properties=["itemListData"]))["itemListData"]
        have = [(e.get("itemDefinition") or {}).get("refPath") for e in cur]
        want = WANT.get(cat) or [p for p in have if p]
        want = [p for p in want if p and p not in rejected]
        print(f"{cat}: has {len(have)} ({sum(1 for p in have if not p)} empty) -> wants {len(want)}")
        if not args.apply:
            continue
        m.tool(bm.OBJ, "reset_properties", instance=lst, properties=["itemListData"])
        kept = []
        for p in want:
            now = dec(m.tool(bm.OBJ, "get_properties", instance=lst, properties=["itemListData"]))["itemListData"]
            now = [e for e in now if (e.get("itemDefinition") or {}).get("refPath")]
            try:
                b.props(lst["refPath"], {"itemListData": now + [{"itemDefinition": {"refPath": p}, "itemQuantity": 1}]})
            except RuntimeError as exc:
                print("   refused", p.split(".")[-1], str(exc)[-60:])
                continue
            after = dec(m.tool(bm.OBJ, "get_properties", instance=lst, properties=["itemListData"]))["itemListData"]
            if any((e.get("itemDefinition") or {}).get("refPath") == p for e in after):
                kept.append(p.split(".")[-1])
        m.tool(bm.SCENE, "save_actor", actor={"refPath": g})
        print("   now:", kept)


if __name__ == "__main__":
    main()
