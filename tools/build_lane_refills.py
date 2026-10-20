"""Fresh guns every rep on the shooting lanes (KT35_Refill_*): an item granter under each lane, read by DrillDevice.

RETIRED (player 2026-10-14): "for all the drills, users load in with the equipment they have in their inventory." The
granter replaced the player's inventory with the practice shotgun + SMG every rep. Running this now turns the refill
off on every lane in LANES and removes the KT35_Refill_* granters; --enable rebuilds the old behaviour.

    python tools/build_lane_refills.py              # off: keep the player's own inventory
    python tools/build_lane_refills.py --enable     # the old replace-inventory refill

Player 2026-10-13: "on reps for gun/ piece switch, it should auto reload the players magazines. same for edit peek".
Verse cannot refill a magazine, but an item granter can hand the guns over again: each lane in LANES gets a granter
tagged kt_lane_granter_tag 100 cm under its (sunk) lane device, holding the listed practice-loadout items, set to
replace the inventory and equip the first item; the lane's RefillEachRep makes DrillDevice grant it at every rep start.
A rerun replaces only KT35_Refill_* actors.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT35_Refill_"
GRANTER = "/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter"
LANES = {"W3": ("SHOTGUN", "SMG"), "E7": ("SHOTGUN", "SMG")}


def main():
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a["actorPath"] for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    for label, path in acts.items():
        if label.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    if "--enable" not in sys.argv:
        for code in LANES:
            lane = acts.get(f"KT_Lane_{code}")
            if lane:
                m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName="refillEachRep", value="false")
                m.tool(bm.SCENE, "save_actor", actor={"refPath": lane})
                print(f"{code}: refill off; the player keeps their own inventory")
        return
    loadout = json.loads((bm.ROOT / "shared" / "practice-loadout.json").read_text(encoding="utf-8"))["items"]
    for code, items in LANES.items():
        lane = acts.get(f"KT_Lane_{code}")
        if not lane:
            print(f"  {code}: no lane")
            continue
        loc = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": lane})["location"]
        g = b.device(GRANTER, f"{PREFIX}{code}", loc["x"], loc["y"], loc["z"] - 100.0)
        refused = []
        for action in ("Clear All Items", "Clear Inventory", "Keep All"):
            try:
                b.props(g, {"onGrantAction": action})
                break
            except RuntimeError:
                refused.append(action)
        for key, value in {"grant": "All Items", "grantCondition": "Always", "bEquipGrantedItem": True}.items():
            try:
                b.props(g, {key: value})
            except RuntimeError:
                refused.append(key)
        raw = m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["pickupItemList"])
        lst = (json.loads(raw) if isinstance(raw, str) else raw)["pickupItemList"]
        m.tool(bm.OBJ, "list_properties", instance=lst)
        m.tool(bm.OBJ, "reset_properties", instance=lst, properties=["itemListData"])
        b.props(lst["refPath"], {"itemListData": [{"itemDefinition": {"refPath": loadout[k]}, "itemQuantity": 1} for k in items]})
        b.tag(g, "kt_lane_granter_tag")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": g})
        m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": lane}, propertyName="refillEachRep", value="true")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": lane})
        got = m.tool(bm.OBJ, "get_properties", instance={"refPath": g}, properties=["onGrantAction"])
        print(f"{code}: granter with {items}; {got}; refused {refused}")


if __name__ == "__main__":
    main()
