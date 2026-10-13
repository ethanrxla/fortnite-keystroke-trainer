"""Armory stations: one Item Granter per weapon class, with every current weapon in its item list.

Players cycle through the list with PREV and NEXT buttons (the granter's hologram shows the selected
weapon) and press GIVE to equip it. That gives a wide choice in a small footprint, instead of one
pedestal per gun. Weapons are read from the project's own asset registry (the WID_Figment_* item
definitions), so the list follows whatever the installed game content currently ships. Each family
uses its highest rarity.

    python tools/armory.py                 # list what would be placed, change nothing
    python tools/armory.py --place         # replace the old armory pedestals in the open level

build_map.py calls place_armory() on a full rebuild and has --armory-only for just this.
"""

import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

ASSET = "editor_toolset.toolsets.asset.AssetTools"
RARITY = ["SR", "VR", "R", "UC", "C", ""]  # best first; "" = a family with a single, unrated item
PATH_RE = re.compile(r"^/(Figment_[A-Za-z0-9_]+)/.*?/(WID_[A-Za-z0-9_]+?)(?:_(C|UC|R|VR|SR))?\.(WID_[A-Za-z0-9_]+)$")

# (class label, predicate on the family name). First match wins, so order matters.
CLASSES = [
    ("AR", lambda f: f.startswith("Figment_Assault_")),
    ("SMG", lambda f: "SMG" in f or f.startswith("Figment_Pistol_AutoHeavy")),
    ("SHOTGUN", lambda f: "Shotgun" in f),
    ("SNIPER", lambda f: f.startswith("Figment_Sniper_")),
    ("PISTOL", lambda f: f.startswith("Figment_Pistol_")),
    ("EXPLOSIVES", lambda f: f.startswith(("Figment_Launcher_", "Figment_Grenade_Launcher", "Figment_ExplosiveBow"))),
    ("HEALS", lambda f: f in ("Figment_Athena_BandageV2", "Figment_Athena_MedKitV2", "Figment_Athena_ShieldPotV2", "Figment_Athena_SmallShieldV2")),
    ("TRAPS", lambda f: "Trap" in f or "SpikeTrap" in f),
]


def pretty(family):
    name = re.sub(r"^Figment_|_Athena$|_Athena_", " ", family)
    return re.sub(r"[_ ]+", " ", name).strip()


def pretty_wid(path):
    """Readable name from the item definition itself, e.g. WID_Figment_Shotgun_SlugFire_Athena_SR -> Shotgun SlugFire."""
    base = path.rsplit(".", 1)[-1]
    base = re.sub(r"_Ore_T\d+$", "", base)
    base = re.sub(r"^WID_Figment_?|_Athena|(?<=_)(C|UC|R|VR|SR)$", "", base)
    base = re.sub(r"_Athena", "", base)
    return re.sub(r"[_ ]+", " ", base).strip() or base


def best_per_family(paths):
    """family -> (rarity, path), the highest rarity present, skipping child/variant helper assets."""
    found = {}
    for p in paths:
        mm = PATH_RE.match(p)
        if not mm or "Child" in p:
            continue
        family, rarity = mm.group(1), mm.group(3) or ""
        cur = found.get(family)
        if cur is None or RARITY.index(rarity) < RARITY.index(cur[0]):
            found[family] = (rarity, p)
    return found


def weapon_classes(mcp):
    raw = mcp.tool(ASSET, "find_assets", name="WID_Figment")
    paths = json.loads(raw) if isinstance(raw, str) else raw
    exclusion_file = pathlib.Path(__file__).resolve().parent.parent / 'shared' / 'asset-exclusions.json'
    rejected = set(json.loads(exclusion_file.read_text(encoding='utf-8')).get('rejected_item_paths', [])) if exclusion_file.exists() else set()
    fams = best_per_family([p for p in paths if p not in rejected])
    out = {}
    for label, pred in CLASSES:
        out[label] = [(pretty_wid(p), r, p) for f, (r, p) in sorted(fams.items()) if pred(f)
                      and not any(pred2(f) for l2, pred2 in CLASSES[:[c[0] for c in CLASSES].index(label)])]
    # Keep registry candidates (notably the full heals family) and add validated practice
    # presets as choices instead of overwriting a whole rack with one item.
    preset_file = pathlib.Path(__file__).resolve().parent.parent / 'shared' / 'practice-loadout.json'
    if preset_file.exists():
        for label, path in json.loads(preset_file.read_text(encoding='utf-8')).get('items', {}).items():
            if path not in rejected:
                choices = out.setdefault(label, [])
                if not any(entry[2] == path for entry in choices):
                    choices.insert(0, (pretty_wid(path), '', path))
    return out


def place_armory(b):
    """Replace the old pedestals with class stations. Needs build_map's Builder and helpers."""
    import build_map as bm
    classes = weapon_classes(b.m)
    # Remove the old single-item pedestals, their signs and any earlier class stations.
    for a in b.m.tool(bm.SCENE, "find_actors", name="KT_", collision_channels=[]) or []:
        lab = a["label"]
        if lab.startswith(("KT_Armory_AR", "KT_Armory_SMG", "KT_Armory_SHOTGUN", "KT_Armory_PISTOL", "KT_Armory_HEALS",
                           "KT_Sign_Armory_", "KT_Gun_")):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    granter = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
    hi, hj = bm.HUB_CELL
    for k, (label, items) in enumerate(classes.items()):
        if not items:
            print(f"armory {label}: nothing found, skipped")
            continue
        ci, cj = hi - 6 + 2 * k, hj - 10
        x, y = bm.cc(ci, cj)
        g = b.device(granter, f"KT_Gun_{label}", x, y, 0.0)
        ref = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["pickupItemList"]))["pickupItemList"]["refPath"]
        data = [{"itemDefinition": {"refPath": p}, "itemQuantity": 1} for _, _, p in items]
        b.m.tool(bm.OBJ, "set_properties", instance={"refPath": ref}, values=json.dumps({"itemListData": data}))
        b.props(g, {"bEquipGrantedItem": True, "onGrantAction": "Keep All",
                    "grant": "Current Item", "grantCondition": "Always",
                    "cycleBehavior": "Wrap", "bIsVisibleDuringMinigame": True,
                    "bShowFirstInteractPrompt": True})
        preview = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": g},
                                      properties=["visibleInGameComponent"]))["visibleInGameComponent"]["refPath"]
        b.props(preview, {"visibleDuringPhase": "Visible in Game Only"})
        # Three buttons on the hub-facing side: PREV, GIVE, NEXT.
        for dx, name, fn in ((-160, "PREV", "CycleToPreviousItem"), (0, "GIVE", "GrantItem"), (160, "NEXT", "CycleToNextItem")):
            btn = b.device(bm.BUTTON, f"KT_Gun_{label}_{name}", x + dx, y + 2 * bm.CELL // 3, 0.0, 90.0)
            b.props(btn, {"visibleDuringGame": False,
                          "interaction Text": f"{'Equip' if name == 'GIVE' else 'Previous' if name == 'PREV' else 'Next'} {label.lower()}",
                          "interactionRadius": 0.6})
            events = b.m.tool(bm.DEVICE, "GetBindingOptions", devicePath={"refPath": btn}) or {}
            ev = next((e for e in events.get("sourceEvents", []) if "nteract" in e), None)
            if ev:
                b.bind(btn, ev, g, fn)
        names = " > ".join(n for n, _, _ in items)
        text = label                     # player 2026-10-13: no "N choices" line
        b.sign({"label": f"KT_Sign_Armory_{label}", "pos": (x, y - bm.CELL, 250), "yaw": 90,
                "text": text, "size": 30, "zone": "Armory"})
        print(f"armory {label}: {len(items)} weapons")


def main():
    import build_map as bm
    mcp = bm.Mcp()
    classes = weapon_classes(mcp)
    for label, items in classes.items():
        print(f"{label}: {len(items)}")
        for name, rarity, path in items:
            print(f"   {name:34} {rarity or '-':3} {path.split('/')[-1]}")
    if "--place" in sys.argv:
        b = bm.Builder()
        place_armory(b)


if __name__ == "__main__":
    main()
