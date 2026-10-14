"""Armory gun wall as a weapon x rarity grid on the back wall, plus a heals shelf (shared/armory-grid.json).

    python tools/build_armory_grid.py --dry-run
    python tools/build_armory_grid.py --test     # two tiles and one heal, to check look and hit detection
    python tools/build_armory_grid.py            # the whole grid and shelf

Replaces build_armory_wall.py's free-standing rows (KT9_ArmoryWall_* is removed and reused). Player 2026-10-10:
tiles ON the back wall, slightly forward of it; bigger; every gun's picture; rarity-coloured backgrounds (gold
legendary, purple epic, blue rare, green uncommon, white common); purple guns to take to the mod bench; medkits and
the other heals in the room. Per tile, facing the room:
  * a plate in the rarity colour 60 cm proud of the wall (unlit, no collision);
  * the item's own large icon (from the item's data list, T-Icon-...-L) in a masked material, just in front;
  * the name on a small label in the plate's lower edge;
  * a target dummy behind the plate, squashed thin, whose On Hit grants the item through a single-item granter
    below the floor (Keep All, equip on grant). An item UEFN does not accept leaves a dark plate and no granter.
The back-wall lockers and crates in the grid's span move to the corners and the armory logo moves up.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT9_ArmoryWall_"
SRC = bm.ROOT / "shared" / "armory-grid.json"
MT = "editor_toolset.toolsets.material.MaterialTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
MATERIALS = bm.MODULE + "/KT_Materials"
PLANE = "/Engine/BasicShapes/Plane.Plane"
GRANTER = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
WALL_Y = -66560.0          # back wall face (KT_Wall_Hub_0)
PROUD = 60.0               # plates stand this far off the wall
TILE = 215.0               # 25 gun columns + the item block on the back wall (player 2026-10-13: all guns back)
PITCH = 235.0              # column pitch
ROW_PITCH = 290.0
BLOCK_GAP = 150.0          # extra space between the weapons and items blocks
X_CENTER = 256.0
ROW_Z0 = 150.0             # centre of the bottom (common) row
# The grid fills the back wall left to right (player 2026-10-11), so every locker and crate on that wall moves to the
# entrance side, against the north wall, facing into the room; the logo moves above the entrance.
NORTH_Y = -63150.0
# AR and EXPLOSIVES lockers, the last stack and two crates stood in front of the bottom row (player 2026-10-11).
MOVE = {"KT5_Armory_Lockers_AR": -1250.0, "KT5_Armory_Lockers_EXPLOSIVES": -850.0, "KT5_Armory_Stack_4_a": 2550.0,
        "KT5_Armory_Stack_4_b": 2550.0, "KT5_Armory_Crate_2": 2850.0, "KT5_Armory_Crate_3": 3100.0,
        "KT5_Armory_Lockers_SMG": -2850.0, "KT5_Armory_Lockers_SHOTGUN": -2450.0,
        "KT5_Armory_Lockers_SNIPER": -2050.0, "KT5_Armory_Lockers_PISTOL": -1650.0,
        "KT5_Armory_Stack_0_a": 1350.0, "KT5_Armory_Stack_0_b": 1350.0, "KT5_Armory_Stack_1_a": 1650.0,
        "KT5_Armory_Stack_1_b": 1650.0, "KT5_Armory_Stack_2_a": 1950.0, "KT5_Armory_Stack_2_b": 1950.0,
        "KT5_Armory_Stack_3_a": 2250.0, "KT5_Armory_Stack_3_b": 2250.0}
LOGO_Y, LOGO_Z = -62996.0, 1150.0
# Glowing plates must not light the room: unlit emissive surfaces feed Lumen's indirect light, and 40 coloured plates
# tinted the whole armory (player 2026-10-11: "did you change the color of the room?").
# A target dummy in play stands about 550 cm per unit of Z scale and 125 cm per unit of Y (twice its editor height:
# 0.82 poked 2 m above the top row). These fill most of a 220 cm tile and stay inside it.
# Player 2026-10-11: bigger hit boxes, "easier to shoot": now a little wider and taller than the 220 cm plate.
HIT_SCALE = (0.15, 2.4, 0.53)      # player 2026-10-11 'increase hitbox': the whole 300 x 290 cm cell, gaps included
HIT_DROP = 146.0
NO_BOUNCE = {"bAffectDynamicIndirectLighting": False, "bAffectDistanceFieldLighting": False}
dec = lambda v: json.loads(v) if isinstance(v, str) else v


class Grid:
    def __init__(self):
        self.b = bm.Builder()
        self.m = self.b.m
        self.mats = {}

    # --- materials -------------------------------------------------------------------------------------------------
    def colour_material(self, name, rgb):
        path = f"{MATERIALS}/{name}.{name}"
        if self.m.tool(AS, "exists", path=path):
            return path
        mat = self.m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=name)
        k = self.m.tool(MT, "add_expression", material_or_function=mat,
                        expression_class={"refPath": "/Script/Engine.MaterialExpressionConstant3Vector"}, x=-300, y=0)
        self.b.props(k["refPath"], {"constant": {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": 1.0}})
        try:
            self.m.tool(MT, "connect_to_output", expression=k, output_name="", material_property="MP_EmissiveColor")
        except RuntimeError:
            self.m.tool(MT, "connect_to_output", expression=k, output_name="RGB", material_property="MP_EmissiveColor")
        self.b.props(path, {"shadingModel": "MSM_Unlit", "twoSided": True})
        self.m.tool(MT, "recompile", material_or_function=mat)
        return path

    def icon_material(self, texture):
        name = "M_ArmoryIcon_" + re.sub(r"[^A-Za-z0-9_]", "_", texture.split(".")[-1])[:48]
        path = f"{MATERIALS}/{name}.{name}"
        if self.m.tool(AS, "exists", path=path):
            return path
        mat = self.m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=name)
        s = self.m.tool(MT, "add_expression", material_or_function=mat,
                        expression_class={"refPath": "/Script/Engine.MaterialExpressionTextureSample"}, x=-300, y=0)
        self.b.props(s["refPath"], {"texture": {"refPath": texture}})
        self.m.tool(MT, "connect_to_output", expression=s, output_name="RGB", material_property="MP_EmissiveColor")
        self.m.tool(MT, "connect_to_output", expression=s, output_name="A", material_property="MP_OpacityMask")
        self.b.props(path, {"shadingModel": "MSM_Unlit", "twoSided": True, "blendMode": "BLEND_Masked"})
        self.m.tool(MT, "recompile", material_or_function=mat)
        return path

    def icon_of(self, item):
        """The item's large icon texture (T-Icon-...-L) from its data list, or None."""
        try:
            s = str(self.m.tool(bm.OBJ, "get_properties", instance={"refPath": item}, properties=["dataList"]))
        except RuntimeError:
            return None
        refs = re.findall(r'"refPath":"([^"]+)"', s)
        large = [r for r in refs if re.search(r"T-Icon-[^/]*-L\.", r) or re.search(r"/T_[^/]*_L\.", r)]
        icons = large or [r for r in refs if "Icon" in r and "-32" not in r and "-16" not in r]
        if not icons:
            # Some items (Chug Splash, Shockwave grenade) keep their icon outside the data list; the asset registry
            # still lists it as a dependency.
            try:
                deps = dec(self.m.tool(AS, "get_dependencies", asset_path=item.split(".")[0])) or []
            except RuntimeError:
                deps = []
            icons = [d for d in deps if "/Icons/" in d and re.search(r"-L\.", d)]
        return icons[0] if icons else None

    # --- pieces of a tile ------------------------------------------------------------------------------------------
    def plane(self, label, x, y, z, size, yaw, material):
        pose = bm.xform(x, y, z, size / 100.0, size / 100.0, 1.0, yaw=yaw)
        pose["rotation"]["roll"] = 90.0
        ref = self.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=label, xform=pose)["refPath"]
        ref = self.b.labelled(ref, label)
        for c in self.m.tool(bm.ACTOR, "get_components", actor={"refPath": ref}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                self.b.props(c["refPath"], {"overrideMaterials": [{"refPath": material}], "castShadow": False,
                                            "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
                for key, value in NO_BOUNCE.items():
                    try:
                        self.b.props(c["refPath"], {key: value})
                    except RuntimeError:
                        pass
        return ref

    def accepted(self, granter, item):
        lst = dec(self.m.tool(bm.OBJ, "get_properties", instance={"refPath": granter}, properties=["pickupItemList"]))["pickupItemList"]
        self.m.tool(bm.OBJ, "list_properties", instance=lst)
        self.m.tool(bm.OBJ, "reset_properties", instance=lst, properties=["itemListData"])
        try:
            self.b.props(lst["refPath"], {"itemListData": [{"itemDefinition": {"refPath": item}, "itemQuantity": 1}]})
        except RuntimeError:
            return False
        now = dec(self.m.tool(bm.OBJ, "get_properties", instance=lst, properties=["itemListData"]))["itemListData"]
        return any((e.get("itemDefinition") or {}).get("refPath") == item for e in now)

    def tile(self, tag, name, item, rgb_name, rgb, x, y, z, facing, icon_override=None):
        """facing: 'S' = on the back wall facing +Y, 'E' = on the east wall facing -X."""
        yaw = 180.0 if facing == "S" else 270.0
        out = (0.0, 1.0) if facing == "S" else (-1.0, 0.0)          # unit vector into the room
        at = lambda d: (x + out[0] * d, y + out[1] * d)
        saved = []
        # Below the floor at a depth unique to the tile's row, so LoadoutPresets.verse can key a tile by its granter.
        gz = -1000.0 - z
        granter = self.b.device(GRANTER, tag + "_Granter", *at(-200.0), gz)
        ok = bool(item) and self.accepted(granter, item)
        if not ok:          # player 2026-10-11: a gun that can't be granted gets no tile at all
            self.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": granter})
            return False, False
        px, py = at(PROUD)
        plate_mat = self.colour_material(f"M_KT_Rarity2_{rgb_name}", rgb) if ok else self.colour_material("M_KT_Rarity_None", (0.04, 0.05, 0.07))
        saved.append(self.plane(tag + "_Plate", px, py, z, TILE, yaw, plate_mat))
        icon = (icon_override or self.icon_of(item)) if ok else None
        if icon:
            ix, iy = at(PROUD + 2.0)
            saved.append(self.plane(tag + "_Icon", ix, iy, z + 12.0, TILE * 0.78, yaw, self.icon_material(icon)))
        lx, ly = at(PROUD + 4.0)
        label = self.b.device(bm.BILLBOARD, tag + "_Label", lx, ly, z - TILE / 2 + 18.0)
        self.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": label},
                    xform=bm.xform(lx, ly, z - TILE / 2 + 18.0, 0.36, 0.36, 0.36, yaw=yaw))
        self.b.props(label, {"text": name if ok else f"{name}\n(not in this build)", "textSize": 16, "showBorder": False,
                             "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                             "backgroundColor": {"r": rgb[0], "g": rgb[1], "b": rgb[2], "a": 1} if ok else {"r": 0.02, "g": 0.02, "b": 0.03, "a": 1}})
        saved.append(label)
        if ok:
            dx, dy = at(20.0)
            dummy = self.b.device(bm.DUMMY, tag + "_Hit", dx, dy, z - HIT_DROP)
            # Thin along the facing axis so it stays behind the plate; a dummy at yaw 0 faces +X.
            self.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dummy},
                        xform=bm.xform(dx, dy, z - HIT_DROP, *HIT_SCALE, yaw=90.0 if facing == "S" else 180.0))
            self.b.props(dummy, {"infiniteHealth": True})
            for key, value in {"onGrantAction": "Keep All", "grant": "Current Item", "grantCondition": "Always",
                               "bEquipGrantedItem": True}.items():
                try:
                    self.b.props(granter, {key: value})
                except RuntimeError as exc:
                    print(f"  {tag}: granter {key} refused ({str(exc)[-40:]})")
            self.b.bind(dummy, "On Hit", granter, "GrantItem")
            # Loadout presets (LoadoutPresets.verse): the same hit fires a trigger 30 cm above the granter, so Verse
            # learns which tile the next item in the shooter's hotbar came from.
            self.b.tag(granter, "kt_armory_granter_tag")
            trig = self.b.device(bm.TRIGGER, tag + "_Track", *at(-200.0), gz + 30.0)
            self.b.props(trig, {"visible in Game": False})
            self.b.tag(trig, "kt_armory_tile_tag")
            self.b.bind(dummy, "On Hit", trig, "Trigger")
            saved += [dummy, granter, trig]
        else:
            self.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": granter})
        for ref in saved:
            self.m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
        return ok, bool(icon)


def linear(hex_colour, scale):
    """sRGB hex -> linear RGB times scale (material constants are linear)."""
    out = []
    for i in (1, 3, 5):
        c = int(hex_colour[i:i + 2], 16) / 255.0
        out.append(round((c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) * scale, 4))
    return out


def plan(spec, test=False):
    """Columns left to right: each weapon over the five rarity rows, then each item and heal alone in its rarity's
    row. A weapon rarity UEFN lacks gets a dark tile; items and heals only fill their own row."""
    for r in spec["rarities"]:
        r["colour"] = linear(r["hex"], spec.get("plate_brightness", 0.35))
    rar = {r["code"]: (k, r) for k, r in enumerate(spec["rarities"])}
    cols = []
    for w in spec["weapons"]:
        cols.append([(r["code"], w.get("names", {}).get(r["code"], w["name"]),
                     w.get("paths", {}).get(r["code"]) or w["pattern"].format(r=r["code"]),
                     w.get("icons", {}).get(r["code"])) for r in spec["rarities"]])
    blocks = [len(cols)]
    rows = spec.get("block_rows")
    if rows:
        # One compact block (player 2026-10-11, "uniform"): items, melee and heals fill columns top to bottom, each
        # plate in its own rarity's colour, so no column has holes.
        extra = [(it["rarity"], it["name"], it["item"], it.get("icon")) for g in ("items", "heals") for it in spec.get(g, [])]
        for k in range(0, len(extra), rows):
            cols.append([("@" + str(rows - 1 - n),) + e for n, e in enumerate(extra[k:k + rows])])
        blocks.append(len(cols))
    else:
        for group in ("items", "heals"):
            for it in spec.get(group, []):
                cols.append([(it["rarity"], it["name"], it["item"], it.get("icon"))])
            blocks.append(len(cols))
    width = (len(cols) - 1) * PITCH + sum(1 for end in blocks[:-1] if len(cols) - 1 >= end) * BLOCK_GAP
    x0 = X_CENTER - width / 2
    tiles = []
    for c, col in enumerate(cols):
        gaps = sum(1 for e in blocks[:-1] if c >= e)
        x = x0 + c * PITCH + gaps * BLOCK_GAP
        for entry in col:
            if entry[0].startswith("@"):            # block slot: row from the slot, colour from the item's rarity
                k = int(entry[0][1:])
                _, r = rar[entry[1]]
                name, item, icon = entry[2:]
            else:
                code, name, item, icon = entry
                k, r = rar[code]
            tiles.append(dict(tag=f"{PREFIX}{c:02d}{k}", name=name, item=item, icon=icon, rgb_name=r["name"], rgb=r["colour"],
                              x=x, y=WALL_Y, z=ROW_Z0 + k * ROW_PITCH, facing="S"))
    for tile in tiles:
        override = spec.get("tile_overrides", {}).get(tile["tag"])
        if override:
            _, rarity = rar[override["rarity"]]
            tile.update(name=override["name"], item=override["item"], icon=override.get("icon"),
                        rgb_name=rarity["name"], rgb=rarity["colour"])
    blocked = set(spec.get("disallowed_items", {}))
    rejected = [t["tag"] for t in tiles if t["item"] in blocked]
    if rejected:
        raise ValueError("Armory plan contains island-disallowed items: " + ", ".join(rejected))
    if test:
        tiles = tiles[:2] + tiles[-2:]
    return tiles


def tidy(g):
    """Lockers and crates off the back wall to the entrance side, turned to face the room; logo above the entrance."""
    acts = {a["label"]: a["actorPath"] for a in g.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []}
    for label, nx in MOVE.items():
        if label in acts:
            t = g.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[label]})
            l = t["location"]
            if l["y"] < -65900:                    # still on the back wall: move once
                rot = dict(t["rotation"], yaw=(t["rotation"]["yaw"] + 180.0) % 360)
                g.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": acts[label]},
                         xform={"location": dict(l, x=nx, y=NORTH_Y), "rotation": rot, "scale": t["scale"]})
                g.m.tool(bm.SCENE, "save_actor", actor={"refPath": acts[label]})
    for label in ("KT3_Upgrade_Logo_Armory", "KT3_Upgrade_Logo_Armory_Frame"):
        if label in acts:
            t = g.m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[label]})
            l = t["location"]
            if l["y"] < -66000:
                rot = dict(t["rotation"], yaw=(t["rotation"]["yaw"] + 180.0) % 360)
                # Mirror the logo/frame pair onto the north wall: same offsets, the room now on the -Y side.
                ny = LOGO_Y - (l["y"] + 66380.0)
                nz = l["z"] + (LOGO_Z - 760.0)          # its old centre was z 760
                g.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": acts[label]},
                         xform={"location": dict(l, y=ny, z=nz), "rotation": rot, "scale": t["scale"]})
                g.m.tool(bm.SCENE, "save_actor", actor={"refPath": acts[label]})


def prune(g, tiles):
    """Player 2026-10-11: keep only guns that can be granted and show their picture. A tile without a granter (the item
    does not exist or is not allowed) or without an icon is removed; every hit dummy gets the play-size scale."""
    acts = {a["label"]: a["actorPath"] for a in g.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []}
    removed = resized = 0
    for t in tiles:
        tag = t["tag"]
        mine = {l: p for l, p in acts.items() if l.startswith(tag + "_")}
        if not mine:
            continue
        if tag + "_Granter" not in mine or tag + "_Icon" not in mine:
            for p in mine.values():
                g.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": p})
            removed += 1
            print(f"  removed {tag} {t['name']} {t['rgb_name']}")
            continue
    # Hit boxes are sized by tools/refit_hitboxes.py (a grid of dummies per plate); run it after this.
    print(f"pruned {removed} tiles")


def fill_icons(g, tiles):
    """A tile with an item but no icon of its own (some rarities carry none) gets its weapon's icon from another
    rarity: the gun looks the same, only the plate colour changes."""
    acts = {a["label"] for a in g.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []}
    icons = {}
    for t in tiles:
        icon = g.icon_of(t["item"]) if t["tag"] + "_Granter" in acts else None
        if icon:
            icons.setdefault(t["tag"][:-1], icon)
    added = 0
    for t in tiles:
        if t["tag"] + "_Granter" in acts and t["tag"] + "_Icon" not in acts and t["tag"][:-1] in icons:
            yaw = 180.0 if t["facing"] == "S" else 270.0
            out = (0.0, 1.0) if t["facing"] == "S" else (-1.0, 0.0)
            ref = g.plane(t["tag"] + "_Icon", t["x"] + out[0] * (PROUD + 2.0), t["y"] + out[1] * (PROUD + 2.0),
                          t["z"] + 12.0, TILE * 0.78, yaw, g.icon_material(icons[t["tag"][:-1]]))
            g.m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
            added += 1
    print(f"icons filled from another rarity: {added}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--fill-icons", action="store_true", help="only add missing icons to tiles already placed")
    ap.add_argument("--prune", action="store_true", help="remove tiles with no item or no image; resize hit dummies")
    ap.add_argument("--tiles", help="comma-separated tile tags (e.g. KT9_ArmoryWall_000) to rebuild alone")
    args = ap.parse_args()
    spec = json.loads(SRC.read_text(encoding="utf-8"))
    tiles = plan(spec, args.test)
    if args.fill_icons:
        fill_icons(Grid(), tiles)
        return
    if args.prune:
        g = Grid()
        prune(g, tiles)
        tidy(g)
        return
    if args.tiles:
        want = set(args.tiles.split(","))
        g = Grid()
        for a in g.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
            if any(a["label"].startswith(w + "_") for w in want):
                g.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
        for t in tiles:
            if t["tag"] in want:
                ok, icon = g.tile(t["tag"], t["name"], t["item"], t["rgb_name"], t["rgb"], t["x"], t["y"], t["z"], t["facing"], t.get("icon"))
                print(f"  {t['tag']} {t['name']:14} {t['rgb_name']:9} {'item' if ok else 'DARK'} {'icon' if icon else 'no icon'}")
        found = (dec(g.m.tool(AS, "find_assets", name="M_ArmoryIcon_")) or []) + (dec(g.m.tool(AS, "find_assets", name="M_KT_Rarity")) or [])
        g.m.tool(AS, "save_assets", asset_paths=[p for p in found if "M_ArmoryIcon_" in p or "M_KT_Rarity" in p])
        return
    for t in tiles:
        print(f"{t['tag']:20} {t['name']:14} {t['rgb_name']:9} x={t['x']:7.0f} y={t['y']:7.0f} z={t['z']:5.0f} {t['facing']}")
    if args.dry_run:
        return
    g = Grid()
    old = g.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []
    for a in old:
        if a["label"].startswith(PREFIX):
            g.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(old)} old {PREFIX}* actors")
    tidy(g)
    done = []
    for t in tiles:
        ok, icon = g.tile(t["tag"], t["name"], t["item"], t["rgb_name"], t["rgb"], t["x"], t["y"], t["z"], t["facing"], t.get("icon"))
        done.append((t["name"], t["rgb_name"], ok, icon))
        print(f"  {t['name']:14} {t['rgb_name']:9} {'item' if ok else 'DARK'} {'icon' if icon else ('no icon' if ok else '')}")
    found = dec(g.m.tool(AS, "find_assets", name="M_ArmoryIcon_")) or []
    found += dec(g.m.tool(AS, "find_assets", name="M_KT_Rarity")) or []
    g.m.tool(AS, "save_assets", asset_paths=[p for p in found if "M_ArmoryIcon_" in p or "M_KT_Rarity" in p])
    print(f"placed {len(done)} tiles: {sum(d[2] for d in done)} with items, {sum(d[3] for d in done)} with icons")
    fill_icons(g, tiles)


if __name__ == "__main__":
    main()
