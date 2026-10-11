"""Armory item wall: shoot a tile and its item is added to your inventory (additive; KT9_ArmoryWall_* only).

    python tools/discover_armory_wall.py        # first: writes shared/armory-wall.json (items + icon textures)
    python tools/build_armory_wall.py --dry-run
    python tools/build_armory_wall.py --test    # three tiles only, to check hit detection and size in game
    python tools/build_armory_wall.py           # the whole wall, on the back (south) wall
    python tools/build_armory_wall.py --side north   # the old place, by the hub entrance

Player 2026-10-10: the guns belong on the BACK wall, behind the bench rows (south, y = -66560), facing the room. The
face stands just in front of the lockers and crates along that wall. Per tile, facing the room:
  * an unlit image plane with the item's own in-game icon (collision off, so shots pass through);
  * a target dummy just behind it, scaled to the tile, with infinite health: its On Hit event is the "shot" signal;
  * one single-item Item Granter hidden below the floor (Keep All, equip on grant), bound to the dummy's On Hit
    through the native GrantItem function, so it works without Verse and keeps whatever you already carry;
  * a small name label under the tile. Items with no usable icon get a text tile instead of an image.
Nothing existing is touched: the benches, spawners, granters, props and art stay as they are. A rerun replaces only
KT9_ArmoryWall_* actors. VERIFY in a playtest: the shooter receives the item (On Hit's instigator), and the item
validates on push; anything the validator rejects goes into shared/asset-exclusions.json.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
from import_armory_art import AS, ArmoryArt  # noqa: E402

PREFIX = "KT9_ArmoryWall_"
SRC = bm.ROOT / "shared" / "armory-wall.json"
EXCL = bm.ROOT / "shared" / "asset-exclusions.json"
GRANTER = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
PLANE = "/Engine/BasicShapes/Plane.Plane"
# Per side: the y of the icon faces, and which way they face (+1 = toward +Y). The hit dummy stands 55 cm behind
# the face, the granter below the floor behind it.
SIDES = {"south": {"face_y": -66300.0, "dir": 1.0},     # back wall (KT_Wall_Hub_0 at -66560), in front of the lockers
         "north": {"face_y": -63588.0, "dir": -1.0}}    # the original place, 100 cm in front of y = -63488
X_CENTER = 256.0       # middle of the armory (x -3072..3584)
PITCH = 150.0
TILE = 118.0
ROWS_Z = [380.0, 220.0, 60.0]
PER_ROW = 22
dec = lambda v: json.loads(v) if isinstance(v, str) else v


def layout(items):
    cols = min(PER_ROW, len(items))
    out = []
    for i, item in enumerate(items):
        row, col = divmod(i, PER_ROW)
        x = X_CENTER + (col - (cols - 1) / 2.0) * PITCH
        out.append((item, x, ROWS_Z[row % len(ROWS_Z)]))
    return out


def clean_name(text):
    return re.sub(r"[^A-Za-z0-9_]", "_", text)[:48]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true", help="three tiles only")
    ap.add_argument("--side", choices=sorted(SIDES), default="south")
    args = ap.parse_args()
    items = json.loads(SRC.read_text(encoding="utf-8"))["items"]
    rejected = set(json.loads(EXCL.read_text(encoding="utf-8")).get("rejected_item_paths", [])) if EXCL.exists() else set()
    items = [i for i in items if i["item"] not in rejected]
    if args.test:
        items = [i for i in items if i["icon"]][:2] + [i for i in items if not i["icon"]][:1]
    placed = layout(items)
    for item, x, z in placed:
        print(f"{item['category']:17} {item['label']:24} x={x:7.0f} z={z:4.0f} {'icon' if item['icon'] else 'text tile'}")
    if args.dry_run:
        return
    art = ArmoryArt()
    b, m = art.b, art.m
    for a in m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    side = SIDES[args.side]
    y_face, face = side["face_y"], side["dir"]
    yaw = 0.0 if face < 0 else 180.0              # icon plane and label: yaw 0 faces -Y
    for n, (item, x, z) in enumerate(placed):
        tag = f"{PREFIX}{n:02d}"
        # 1. the tile face
        if item["icon"]:
            mat = art.material("M_ArmoryWall_" + clean_name(item["icon"].split("/")[-1].split(".")[0]), item["icon"])
            pose = bm.xform(x, y_face, z, TILE / 100.0, TILE / 100.0, 1.0, yaw=yaw)
            pose["rotation"]["roll"] = 90.0
            plane = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=tag + "_Icon", xform=pose)["refPath"], tag + "_Icon")
            for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": plane}) or []:
                if "StaticMeshComponent0" in c["refPath"]:
                    b.props(c["refPath"], {"overrideMaterials": [{"refPath": mat}], "castShadow": False,
                                           "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
            m.tool(bm.SCENE, "save_actor", actor={"refPath": plane})
        # 2. the name label (under an icon, or the whole tile when there is no icon)
        ly, lz = y_face + 2.0 * face, (z - (TILE / 2 + 22.0) if item["icon"] else z)
        label = b.device(bm.BILLBOARD, tag + "_Label", x, ly, lz)
        scale = 0.32 if item["icon"] else 0.42
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": label}, xform=bm.xform(x, ly, lz, scale, scale, scale, yaw=yaw))
        b.props(label, {"text": item["label"], "textSize": 14 if item["icon"] else 22, "showBorder": False,
                        "textColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                        "backgroundColor": {"r": 0.008, "g": 0.01, "b": 0.015, "a": 1}})
        # 3. the hit object, just behind the face
        dy = y_face - 55.0 * face
        dummy = b.device(bm.DUMMY, tag + "_Hit", x, dy, z - 26.0)
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": dummy}, xform=bm.xform(x, dy, z - 26.0, 0.28, 0.28, 0.28, yaw=90.0 * face))
        b.props(dummy, {"infiniteHealth": True})
        # 4. the single-item granter, below the floor, driven by the hit
        granter = b.device(GRANTER, tag + "_Granter", x, y_face - 200.0 * face, -300.0)
        for name, value in {"onGrantAction": "Keep All", "grant": "Current Item", "grantCondition": "Always",
                            "bEquipGrantedItem": True, "bShowFirstInteractPrompt": False}.items():
            try:
                b.props(granter, {name: value})
            except RuntimeError as exc:
                print(f"  {tag}: could not set {name} ({str(exc)[-40:]})")
        ref = dec(m.tool(bm.OBJ, "get_properties", instance={"refPath": granter}, properties=["pickupItemList"]))["pickupItemList"]
        try:
            m.tool(bm.OBJ, "reset_properties", instance=ref, properties=["itemListData"])
            b.props(ref["refPath"], {"itemListData": [{"itemDefinition": {"refPath": item["item"]}, "itemQuantity": 1}]})
        except RuntimeError as exc:
            print(f"  {tag}: item rejected {item['label']} ({str(exc)[-60:]})")
        b.bind(dummy, "On Hit", granter, "GrantItem")
        for p in (dummy, granter, label):
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    found = dec(m.tool(AS, "find_assets", name="M_ArmoryWall_"))
    m.tool(AS, "save_assets", asset_paths=[p for p in found if "M_ArmoryWall_" in p])   # unsaved packages fail validation
    print("placed", len(placed), "tiles; remember PushChanges and watch the log for validation errors")


if __name__ == "__main__":
    main()
