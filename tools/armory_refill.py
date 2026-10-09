"""Fill the existing armory stations (KT_Gun_<CLASS>) with every base-game weapon family, not one gun each.

    python tools/armory_refill.py --dry-run     # what each station would hold
    python tools/armory_refill.py               # reset and refill the item lists, update the station signs
    python tools/armory_refill.py --drop <path> [--drop <path> ...]   # remove items the editor rejected

Source: item definitions in /Game/Athena/Items/Weapons whose names end _Ore_T03 (the naming the editor
accepted for the validated presets in shared/practice-loadout.json), best rarity per weapon family, minus
seasonal novelty items. The editor decides what is allowed, not this script: after a push, look for
"illegally references" in %LOCALAPPDATA%\\UnrealEditorFortnite\\Saved\\Logs\\UnrealEditorFortnite.log and
pass each offending path to --drop. Paths in shared/asset-exclusions.json are never added.

"This is the installed content, not a statement about the live loot pool": the project cannot see which
weapons are in the current season's rotation.
"""

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
from armory import weapon_classes as figment_classes  # noqa: E402

ASSET = "editor_toolset.toolsets.asset.AssetTools"
RARITY = ["SR", "VR", "R", "UC", "C"]
FOLDER = "/Game/Athena/Items/Weapons"
NOVELTY = ("Launcher_Egg", "Launcher_Snowball", "Launcher_Pumpkin", "Special_FiendHunter", "Sniper_Valentine", "Pistol_Sixshooter")
SMG_FAMILIES = ("Pistol_AutoHeavy", "Pistol_AutoHeavyPDW", "Pistol_AutoHeavySuppressed", "Pistol_BurstFireSMG", "Pistol_RapidFireSMG")
# (station label, predicate on the weapon family name); first match wins
CLASSES = [
    ("AR", lambda f: f.startswith("Assault_")),
    ("SMG", lambda f: f in SMG_FAMILIES),
    ("SHOTGUN", lambda f: f.startswith("Shotgun_")),
    ("SNIPER", lambda f: f.startswith("Sniper_")),
    ("PISTOL", lambda f: f.startswith(("Pistol_", "DualPistol", "Spytech_"))),
    ("EXPLOSIVES", lambda f: f.startswith("Launcher_")),
    ("TRAPS", lambda f: "Trap" in f or "SpikeTrap" in f),
]
RX = re.compile(r"WID_(.+?)_Athena_(C|UC|R|VR|SR)_Ore_T0(\d)\.")


def candidates(mcp):
    raw = mcp.tool(ASSET, "find_assets", folder_path=FOLDER, name="WID_")
    paths = json.loads(raw) if isinstance(raw, str) else raw
    excl = bm.ROOT / "shared" / "asset-exclusions.json"
    rejected = set(json.loads(excl.read_text(encoding="utf-8")).get("rejected_item_paths", [])) if excl.exists() else set()
    # The validator blocks a weapon at every rarity once it blocks one, so exclude whole families.
    bad_families = {RX.search(r).group(1) for r in rejected if RX.search(r)}
    best = {}
    for p in paths:
        if p in rejected:
            continue
        m = RX.search(p)
        if m and m.group(1) in bad_families:
            continue
        if not m or any(m.group(1).startswith(n) for n in NOVELTY):
            continue
        fam, rar = m.group(1), m.group(2)
        if fam not in best or RARITY.index(rar) < RARITY.index(best[fam][0]):
            best[fam] = (rar, p)
    out = {}
    taken = set()
    for label, pred in CLASSES:
        items = [(fam, rar, p) for fam, (rar, p) in sorted(best.items()) if pred(fam) and fam not in taken]
        taken |= {i[0] for i in items}
        out[label] = items
    # Keep validated practice presets as choices; don't overwrite the healing and throwable
    # families with a single shield/grenade entry.
    preset = json.loads((bm.ROOT / "shared" / "practice-loadout.json").read_text(encoding="utf-8"))["items"]
    for label in ("EXPLOSIVES", "HEALS"):
        if label in preset and preset[label] not in {item[2] for item in out.get(label, [])}:
            out.setdefault(label, []).insert(0, (pretty(preset[label].rsplit("/", 1)[-1]), "", preset[label]))
    # The current Fortnite content registry exposes healing and some trap items in the
    # Figment namespace. Add those families to their utility rack after local exclusions.
    figment = figment_classes(mcp)
    for label in ("HEALS", "TRAPS"):
        existing = {item[2] for item in out.get(label, [])}
        for name, rarity, path in figment.get(label, []):
            if path not in rejected and path not in existing:
                out.setdefault(label, []).append((name, rarity, path))
                existing.add(path)
    return out


def pretty(fam):
    return re.sub(r"_+", " ", fam)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--drop", action="append", default=[], help="item path the editor rejected; remove it and remember it")
    args = ap.parse_args()
    b = bm.Builder()
    excl = bm.ROOT / "shared" / "asset-exclusions.json"
    if args.drop:
        data = json.loads(excl.read_text(encoding="utf-8"))
        data["rejected_item_paths"] = sorted(set(data.get("rejected_item_paths", [])) | set(args.drop))
        excl.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("recorded", len(args.drop), "rejected path(s) in shared/asset-exclusions.json")
    classes = candidates(b.m)
    for label, items in classes.items():
        print(f"{label}: {len(items)}  " + ", ".join(pretty(f) for f, _, _ in items))
    if args.dry_run:
        return
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT_", collision_channels=[]) or [])}
    for label, items in classes.items():
        g = acts.get(f"KT_Gun_{label}")
        if not g or not items:
            print(f"{label}: station missing or nothing to add, skipped")
            continue
        comp = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["pickupItemList"]))["pickupItemList"]["refPath"]
        b.m.tool(bm.OBJ, "reset_properties", instance={"refPath": comp}, properties=["itemListData"])
        for fam, rar, p in items:
            cur = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": comp}, properties=["itemListData"]))["itemListData"]
            try:
                b.m.tool(bm.OBJ, "set_properties", instance={"refPath": comp},
                         values=json.dumps({"itemListData": cur + [{"itemDefinition": {"refPath": p}, "itemQuantity": 1}]}))
            except RuntimeError as exc:
                print(f"  {label}: could not add {fam} ({str(exc)[-60:]})")
        sign = acts.get(f"KT_Sign_Armory_{label}")
        if sign:
            names = " > ".join(pretty(f) for f, _, _ in items)
            text = f"{label}\nPREV / EQUIP / NEXT\n{names}"
            b.props(sign, {"text": text, "textSize": 24 if len(text) > 220 else 28 if len(text) > 120 else 40})
        n = len(json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": comp}, properties=["itemListData"]))["itemListData"])
        print(f"{label}: {n} items in the list")


if __name__ == "__main__":
    main()
