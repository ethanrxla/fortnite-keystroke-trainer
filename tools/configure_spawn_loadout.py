"""Spawn loadout: what every player gets on joining the map and on every respawn (shared/spawn-loadout.json).

    python tools/configure_spawn_loadout.py

Player 2026-10-10: "we stopped spawning in with slurp fish and meds, shields, a pistol". The granter (KT9_Spawn_Pistol)
and the remover (KT10_Arena_SupplyRemove) were still in the level, but the Verse service that fires them on spawn
(kt_spawn_supply_service, SpawnSupplies.verse) had been removed. This sets both item lists from the JSON (read back to
check), tags the granter, the remover and every player spawner, and places the service again if it is missing.
An item UEFN refuses is reported and left out; nothing else is changed.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

SRC = bm.ROOT / "shared" / "spawn-loadout.json"
GRANTER, REMOVER, SERVICE = "KT9_Spawn_Pistol", "KT10_Arena_SupplyRemove", "KT12_Spawn_Supply_Service"
SERVICE_ASSET = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_spawn_supply_service"
dec = lambda v: json.loads(v) if isinstance(v, str) else v


def set_items(m, ref, entries):
    """Replace the item list of a granter / remover; returns the entries UEFN kept."""
    props = dec(m.tool(bm.OBJ, "list_properties", instance=ref))
    names = [p.get("name") if isinstance(p, dict) else p for p in props] if isinstance(props, list) else list(props)
    key = "pickupItemList" if "pickupItemList" in names else "itemList"
    obj = dec(m.tool(bm.OBJ, "get_properties", instance=ref, properties=[key]))[key]
    m.tool(bm.OBJ, "list_properties", instance=obj)
    m.tool(bm.OBJ, "reset_properties", instance=obj, properties=["itemListData"])
    kept = []
    for e in entries:
        old = dec(m.tool(bm.OBJ, "get_properties", instance=obj, properties=["itemListData"]))["itemListData"]
        try:
            m.tool(bm.OBJ, "set_properties", instance=obj, values=json.dumps(
                {"itemListData": old + [{"itemDefinition": {"refPath": e["item"]}, "itemQuantity": e["count"]}]}))
        except RuntimeError as exc:
            print(f"  refused {e['name']}: {str(exc)[-90:]}")
            continue
        now = dec(m.tool(bm.OBJ, "get_properties", instance=obj, properties=["itemListData"]))["itemListData"]
        if any((x.get("itemDefinition") or {}).get("refPath") == e["item"] for x in now):
            kept.append(e["name"])
        else:
            print(f"  dropped {e['name']}: not kept after setting (not a grantable item)")
    m.tool(bm.SCENE, "save_actor", actor=ref)
    return kept


def tag(m, ref, name):
    """Add a Verse tag to the actor's existing tag markup (native devices consume their first markup), or a new one."""
    comps = m.tool(bm.ACTOR, "get_components", actor=ref) or []
    comp = next((c for c in comps if "VerseTagMarkup" in c["refPath"] or "KT_" in c["refPath"].rsplit(".", 1)[-1]), None)
    if comp is None:
        for c in comps:
            try:
                if "internalTags" in json.dumps(dec(m.tool(bm.OBJ, "list_properties", instance=c))):
                    comp = c
                    break
            except Exception:
                pass
    if comp is None:
        comp = m.tool(bm.ACTOR, "add_component", owner=ref,
                      component_type={"refPath": "/Script/VerseTags.VerseTagMarkupComponent"}, name="KT_Spawn_" + name)
    m.tool(bm.OBJ, "list_properties", instance=comp)
    old = dec(m.tool(bm.OBJ, "get_properties", instance=comp, properties=["internalTags"]))["internalTags"]
    tags = old.get("internalTags", [])
    new = {"internalTag": {"refPath": bm.TAG_CLASS.format(name)}}
    if new not in tags:
        tags.append(new)
        m.tool(bm.OBJ, "set_properties", instance=comp, values=json.dumps({"internalTags": {"internalTags": tags}}))
    m.tool(bm.SCENE, "save_actor", actor=ref)


def main():
    entries = json.loads(SRC.read_text(encoding="utf-8"))["items"]
    b = bm.Builder()
    m = b.m
    actors = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    by = {a["label"]: a["actorPath"] for a in actors}
    granter, remover = {"refPath": by[GRANTER]}, {"refPath": by[REMOVER]}
    kept = set_items(m, granter, entries)
    for name, value in {"grant": "All Items", "grantCondition": "Always", "onGrantAction": "Keep All"}.items():
        try:
            b.props(granter["refPath"], {name: value})
        except RuntimeError as exc:
            print(f"  granter {name}: {str(exc)[-60:]}")
    m.tool(bm.SCENE, "save_actor", actor=granter)
    print("granted on spawn:", kept)
    # Remove the same consumables first (not the pistol: removing a weapon you chose at the armory would hurt).
    removed = set_items(m, remover, [e for e in entries if not e["item"].split("/")[-1].startswith("WID_Pistol")])
    print("removed first:", removed)
    tag(m, granter, "kt_spawn_supplies_tag")
    tag(m, remover, "kt_spawn_supply_remove_tag")
    spawners = [a for a in actors if "Player_Spawner" in a["class"]["refPath"] or "PlayerSpawn" in a["class"]["refPath"]]
    for a in spawners:
        tag(m, {"refPath": a["actorPath"]}, "kt_default_spawn_tag")
    print("player spawners tagged:", [a["label"] for a in spawners])
    if SERVICE not in by:
        ref = m.tool(bm.DEVICE, "PlaceDevice", assetPath={"refPath": SERVICE_ASSET}, transform=bm.xform(0, -59648, -1000))
        b.labelled(ref["refPath"], SERVICE)
        m.tool(bm.SCENE, "save_actor", actor=ref)
        print("placed", SERVICE, "(below the hub floor)")
    else:
        print(SERVICE, "already placed")


if __name__ == "__main__":
    main()
