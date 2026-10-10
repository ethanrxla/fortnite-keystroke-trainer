"""Resolve the armory wall's items to exact asset paths and their in-game icon textures (read-only).

    python tools/discover_armory_wall.py        # writes shared/armory-wall.json

For each wanted item, finds the item definition by name in the asset registry and picks the icon texture that
lives in the same plugin and best matches the item (preferring the '-L' large icon). Nothing in the level is
changed. Items the registry cannot resolve are listed under "missing" so nothing is guessed.
Registry presence is not Creative permission: anything the island validator rejects on push goes into
shared/asset-exclusions.json and is skipped on the next run.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

ASSET = "editor_toolset.toolsets.asset.AssetTools"
OUT = bm.ROOT / "shared" / "armory-wall.json"
EXCL = bm.ROOT / "shared" / "asset-exclusions.json"

# (category, label, asset-name to find, optional path fragment that must appear)
WANT = [
    ("moddable AR", "Paprika AR (DPS)", "WID_Assault_Paprika_DPS_Athena_SR", "PaprikaAR_DPS/"),
    ("moddable AR", "Paprika AR (Heavy)", "WID_Assault_Paprika_Heavy_Athena_SR", "PaprikaAR_Heavy/"),
    ("moddable AR", "Paprika AR (Infantry)", "WID_Assault_Paprika_Infantry_Athena_SR", "PaprikaAR_Infantry/"),
    ("moddable SMG", "Paprika SMG (Burst)", "WID_SMG_Paprika_Burst_Athena_SR", ""),
    ("moddable SMG", "Paprika SMG (DPS)", "WID_SMG_Paprika_DPS_Athena_SR", ""),
    ("moddable shotgun", "Paprika Shotgun (Auto)", "WID_Shotgun_Auto_Paprika_Athena_SR", ""),
    ("moddable shotgun", "Paprika Shotgun (Pump)", "WID_Shotgun_Pump_Paprika_Athena_SR", ""),
    ("moddable pistol", "Paprika Pistol", "WID_Pistol_Paprika_Auto_Athena_SR", ""),
    ("moddable sniper", "Paprika Sniper", "WID_Sniper_Paprika_Athena_SR", "PaprikaSniper/WID"),
    ("heals", "Medkit", "WID_Paprika_MedBox", "PaprikaConsumables"),
    ("heals", "Bandage", "WID_Paprika_Bandage", "PaprikaConsumables"),
    ("heals", "Shield potion", "WID_Paprika_ShieldPot", "PaprikaConsumables"),
    ("heals", "Mini shield", "WID_Paprika_ShieldSmall", "PaprikaConsumables"),
    ("heals", "Chug Jug", "Figment_Athena_ChugJug", "Figment_Athena_ChugJug"),
    ("heals", "Slurp juice", "Figment_Athena_PurpleStuff", "Figment_Athena_PurpleStuff"),
    ("heals", "Chug Splash", "WID_Chrono_SlapSplash", "ChronoConsumables"),
    ("traps", "Floor spikes", "TID_Floor_Spikes_Athena_R_T03", "CreativeCoreDevices"),
    ("traps", "Oil slick", "TID_Trap_Floor_OilSlick", "CreativeCoreDevices"),
    ("traps", "Damage rail", "TID_Floor_DamageRailFull", "CreativeCoreDevices"),
    ("traps", "Launch pad", "TID_Floor_Player_Launch_Pad_Super_UEFN", "LaunchPadItemGameplay"),
    ("mobility", "Grapple gloves", "WID_GrappleGloves", "GrappleGloves"),
    ("mobility", "Grapple knife", "WID_GrappleKnife_VR", "GrappleWeapon"),
]


def find(m, name):
    raw = m.tool(ASSET, "find_assets", name=name)
    return json.loads(raw) if isinstance(raw, str) else raw


def root(path):
    return "/" + path.strip("/").split("/")[0]


def main():
    m = bm.Builder().m
    rejected = set(json.loads(EXCL.read_text(encoding="utf-8")).get("rejected_item_paths", [])) if EXCL.exists() else set()
    icons = [p for p in find(m, "Icon") if re.search(r"/[^/]*[Ii]con[^/]*$", p.split(".")[0])]
    out, missing = [], []
    for category, label, name, fragment in WANT:
        hits = [p for p in find(m, name) if p.split("/")[-1].split(".")[0] == name and fragment in p]
        if not hits:
            missing.append(label)
            continue
        wid = hits[0]
        if wid in rejected:
            missing.append(label + " (rejected earlier)")
            continue
        same = [p for p in icons if root(p) == root(wid)]
        words = [w.lower() for w in re.split(r"[_\W]+", name) if len(w) > 2 and w.upper() not in ("WID", "TID", "ATHENA", "PAPRIKA", "FIGMENT", "UEFN", "FLOOR", "TRAP", "SUPER", "FULL", "HALF", "PLAYER")]
        folder = wid.rsplit("/", 1)[0]

        def score(p):
            fname = p.split("/")[-1].lower()
            hits = sum(w in fname for w in words)
            near = 3 if p.startswith(folder) or p.rsplit("/", 2)[0] == folder else 0
            return (hits + near if hits else 0, "-L" in p or "_L" in p, -len(p))

        scored = sorted(same, key=score, reverse=True)
        icon = scored[0] if scored and score(scored[0])[0] > 0 else None
        out.append({"category": category, "label": label, "item": wid, "icon": icon})
    # Everything else already on the armory stations (their lists passed island validation): one tile each.
    have = {e["item"] for e in out}
    dec = lambda v: json.loads(v) if isinstance(v, str) else v
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT_Gun_", collision_channels=[]) or [])}
    for station in ("AR", "SMG", "SHOTGUN", "SNIPER", "PISTOL", "EXPLOSIVES", "MELEE", "HEALS", "GRAPPLE"):
        if f"KT_Gun_{station}" not in acts:
            continue
        ref = dec(m.tool(bm.OBJ, "get_properties", instance={"refPath": acts[f"KT_Gun_{station}"]}, properties=["pickupItemList"]))["pickupItemList"]
        for entry in dec(m.tool(bm.OBJ, "get_properties", instance=ref, properties=["itemListData"]))["itemListData"]:
            path = (entry.get("itemDefinition") or {}).get("refPath")
            if not path or path in have or path in rejected:
                continue
            have.add(path)
            name = path.split("/")[-1].split(".")[0]
            pretty = re.sub(r"^WID_|_Athena|_Ore_T\d+|Figment_", "", name).replace("_", " ").strip()
            words = [w.lower() for w in re.split(r"[_\W]+", name) if len(w) > 3 and w.upper() not in ("ATHENA", "FIGMENT", "ORE")]
            same = [p for p in icons if root(p) == root(path)]
            hits = lambda p: sum(w in p.split("/")[-1].lower() for w in words)
            best = max(same, key=lambda p: (hits(p), "-L" in p or "_L" in p), default=None)
            out.append({"category": station.lower(), "label": pretty[:26], "item": path,
                        "icon": best if best and hits(best) >= (1 if root(path) != "/Game" else 2) else None})
    OUT.write_text(json.dumps({"items": out, "missing": missing}, indent=1), encoding="utf-8")
    for e in out:
        print(f"{e['category']:17} {e['label']:24} icon={'yes' if e['icon'] else 'NO '}  {e['icon'] or ''}"[:200])
    print("missing:", missing)


if __name__ == "__main__":
    main()
