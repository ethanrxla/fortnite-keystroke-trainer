"""Repair only absent armory cells; preserve all working weapons and bindings.
Replacement item paths and actual rarity metadata are persisted in the shared spec.
"""
import json
import pathlib
import re
import build_armory_grid as ag
import build_map as bm

RARITY = {"Common": "C", "Uncommon": "UC", "Rare": "R", "VeryRare": "VR", "SuperRare": "SR"}
FAMILIES = [
    ("Thunder Burst SMG", "WID_SMG_Paprika_Burst_Athena_"),
    ("Flint-Knock", "WID_Figment_Pistol_Flintlock_Athena_"),
    ("Scoped AR", "WID_Assault_DragonCart_Scoped_Athena_"),
    ("Lever Shotgun", "WID_Shotgun_Lever_FlexLegend_Athena_"),
    ("Combat AR", "WID_Assault_MoonFlax_CombatAR_Athena_"),
    ("Suppressed Pistol", "WID_Pistol_Suppressed_Athena_"),
    ("Hand Cannon", "WID_SunRose_Pistol_HandCannon_HS_Athena_"),
]


def metadata(g, path):
    raw = ag.dec(g.m.tool(bm.OBJ, "get_properties", instance={"refPath": path}, properties=["dataList"]))
    tags = re.findall(r'"tagName"\s*:\s*"Rarity\.([^".]*)"', json.dumps(raw))
    codes = {RARITY[t] for t in tags if t in RARITY}
    if len(codes) != 1:
        raise ValueError(f"Cannot verify rarity for {path}: {tags}")
    return codes.pop()


def main():
    spec = json.loads(ag.SRC.read_text())
    blocked = set(spec.get("disallowed_items", {}))
    tiles = ag.plan(spec)
    g = ag.Grid()
    actors = g.m.tool(bm.SCENE, "find_actors", name=ag.PREFIX, collision_channels=[]) or []
    labels = {a["label"] for a in actors}
    missing = [t for t in tiles if t["tag"] + "_Granter" not in labels or t["tag"] + "_Icon" not in labels]
    recolour = set()
    for t in tiles:
        if t["tag"] + "_Granter" not in labels:
            continue
        actual = metadata(g, t["item"])
        expected = next(r["code"] for r in spec["rarities"] if r["name"] == t["rgb_name"])
        if actual != expected:
            spec.setdefault("tile_overrides", {})[t["tag"]] = dict(
                name=t["name"], item=t["item"], rarity=actual, icon=t.get("icon"))
            recolour.add(t["tag"])
            print(f"Correcting rarity {t['tag']}: {expected} -> {actual}", flush=True)
    ag.SRC.write_text(json.dumps(spec, indent=2) + "\n")
    tiles = ag.plan(spec)
    # Same weapon/rarity aliases are duplicates even if their asset paths differ.
    live_pairs = {}
    duplicates = []
    for t in sorted(tiles, key=lambda t: t["tag"] in spec.get("tile_overrides", {})):
        if t["tag"] + "_Granter" in labels and t["tag"] + "_Icon" in labels:
            pair = (t["name"], t["rgb_name"])
            if pair in live_pairs:
                duplicates.append(t)
            else:
                live_pairs[pair] = t["tag"]
    missing.extend(duplicates)
    used_pairs = set(live_pairs)
    used = set()
    for a in actors:
        if a["label"].endswith("_Granter"):
            lst = ag.dec(g.m.tool(bm.OBJ, "get_properties", instance={"refPath": a["actorPath"]}, properties=["pickupItemList"]))["pickupItemList"]
            entries = ag.dec(g.m.tool(bm.OBJ, "get_properties", instance=lst, properties=["itemListData"]))["itemListData"]
            used.update((e.get("itemDefinition") or {}).get("refPath") for e in entries)
    assets = ag.dec(g.m.tool(ag.AS, "find_assets", name="WID_")) or []
    rarities = {r["code"]: r for r in spec["rarities"]}
    repairs = []
    for tile in missing:
        desired = next(r["code"] for r in spec["rarities"] if r["name"] == tile["rgb_name"])
        candidates = [(tile["name"], tile["item"])]
        candidates += [(name, path) for name, prefix in FAMILIES for path in assets
                       if path.rsplit("/", 1)[-1].split(".")[0] == prefix + desired]
        # Fallbacks still get their true rarity colour, never the empty cell's colour.
        candidates += [(name, path) for name, prefix in FAMILIES for path in assets
                       if path.rsplit("/", 1)[-1].split(".")[0] in {prefix + c for c in RARITY.values()}]
        repaired = False
        for name, path in candidates:
            if path in used or path in blocked or path.startswith("none:"):
                continue
            try:
                tags = g.m.tool(ag.AS, "get_asset_tags", asset_path=path)
                # Editor acceptance alone does not establish island reference permission.
                if not tags.get("CreativeTagsHelper") or tags["CreativeTagsHelper"] == "(CreativeTags=)":
                    continue
                name = tags.get("DisplayName") or name
                code = metadata(g, path)
                if (name, rarities[code]["name"]) in used_pairs:
                    continue
                icon = g.icon_of(path) or tags.get("CustomThumbnail")
                if not icon and "WID_Assault_DragonCart_Scoped_Athena_" in path:
                    icon = "/DragonCartWeaponGameplay/Gameplay/DragonCart_ScopedAR/Icons/T_Icon_Weapons_Rifle_Assault_ScopedRecoil_L.T_Icon_Weapons_Rifle_Assault_ScopedRecoil_L"
                if not icon:
                    continue
            except (RuntimeError, ValueError):
                continue
            # Remove only partial remnants belonging to this missing cell.
            for actor in actors:
                if actor["label"].startswith(tile["tag"] + "_"):
                    g.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": actor["actorPath"]})
            actors = [a for a in actors if not a["label"].startswith(tile["tag"] + "_")]
            rarity = rarities[code]
            ok, has_icon = g.tile(tile["tag"], name, path, rarity["name"], rarity["colour"],
                                  tile["x"], tile["y"], tile["z"], tile["facing"], icon)
            if not ok:
                continue
            if not has_icon:
                raise RuntimeError("Accepted tile missing its verified icon")
            override = dict(name=name, item=path, rarity=code, icon=icon)
            spec.setdefault("tile_overrides", {})[tile["tag"]] = override
            ag.SRC.write_text(json.dumps(spec, indent=2) + "\n")
            used.add(path)
            used_pairs.add((name, rarity["name"]))
            repairs.append(dict(tag=tile["tag"], **override))
            print(f"Filled {tile['tag']}: {name} ({rarity['name']})", flush=True)
            repaired = True
            break
        if not repaired:
            raise RuntimeError(f"No accepted distinct replacement for {tile['tag']}")
    # Align existing cells with the centered plan; move every component by the same offset.
    actors = g.m.tool(bm.SCENE, "find_actors", name=ag.PREFIX, collision_channels=[]) or []
    by_tag = {t["tag"]: t for t in ag.plan(spec)}
    offsets = {}
    for a in actors:
        if a["label"].endswith("_Plate"):
            tag = a["label"][:-6]
            if tag in by_tag:
                pose = g.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": a["actorPath"]})
                offsets[tag] = by_tag[tag]["x"] - pose["location"]["x"]
    for a in actors:
        tag = "_".join(a["label"].split("_", 3)[:3])
        dx = offsets.get(tag, 0)
        if abs(dx) > .01:
            pose = g.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": a["actorPath"]})
            pose["location"]["x"] += dx
            g.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": a["actorPath"]}, xform=pose)
            g.m.tool(bm.SCENE, "save_actor", actor={"refPath": a["actorPath"]})
    for actor in actors:
        if actor["label"].endswith("_Plate") and actor["label"][:-6] in recolour:
            tile = by_tag[actor["label"][:-6]]
            material = g.colour_material("M_KT_Rarity2_" + tile["rgb_name"], tile["rgb"])
            for component in g.m.tool(bm.ACTOR, "get_components", actor={"refPath": actor["actorPath"]}) or []:
                if "StaticMeshComponent0" in component["refPath"]:
                    g.b.props(component["refPath"], {"overrideMaterials": [{"refPath": material}]})
            g.m.tool(bm.SCENE, "save_actor", actor={"refPath": actor["actorPath"]})
    for actor in actors:
        if actor["label"].endswith("_Label") and actor["label"][:-6] in recolour:
            tile = by_tag[actor["label"][:-6]]
            rgb = tile["rgb"]
            g.b.props(actor["actorPath"], {"backgroundColor": {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": 1}})
            g.m.tool(bm.SCENE, "save_actor", actor={"refPath": actor["actorPath"]})
    materials = ag.dec(g.m.tool(ag.AS, "find_assets", name="M_ArmoryIcon_")) or []
    materials += ag.dec(g.m.tool(ag.AS, "find_assets", name="M_KT_Rarity")) or []
    g.m.tool(ag.AS, "save_assets", asset_paths=materials)
    pathlib.Path("design/armory-repairs.local.json").write_text(json.dumps(repairs, indent=2))
    print(f"Repaired {len(repairs)} cells; centered all cells.", flush=True)


if __name__ == "__main__":
    main()
