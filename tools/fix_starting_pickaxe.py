"""Restore the harvest/pickaxe slot in Island Settings.

    python tools/fix_starting_pickaxe.py          # inspect only
    python tools/fix_starting_pickaxe.py --apply  # back up and save the two settings

The editor snapshot confirms that IslandSettings0 is the island's Experience Settings device.
Its unusually named `enabled` property means Start with Pickaxe (not device enablement).
Its `bDisableHarvestSlot` property controls whether the harvest slot is visible and selectable;
`pickaxeDestructionPreset` controls normal pickaxe damage to the environment/buildings. This
script changes only those two properties and writes the previous values to a timestamped backup.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import build_map as bm

AS = "editor_toolset.toolsets.asset.AssetTools"


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    builder = bm.Builder()
    m = builder.m
    if m.tool(bm.SCENE, "get_current_level") != bm.MODULE + "/KeystrokeTrainer":
        raise RuntimeError("Wrong open level; expected the KeystrokeTrainer map")

    actors = m.tool(bm.SCENE, "find_actors", name="IslandSettings0", collision_channels=[]) or []
    settings = next((a for a in actors if a.get("label") == "IslandSettings0"), None)
    if not settings:
        raise RuntimeError("Could not find the map's IslandSettings0 device")

    path = settings["actorPath"]
    old = decoded(m.tool(bm.OBJ, "get_properties", instance={"refPath": path},
                         properties=["enabled", "bDisableHarvestSlot", "pickaxeDestructionPreset"]))
    desired = {"enabled": True, "bDisableHarvestSlot": False, "pickaxeDestructionPreset": "Default"}
    print("IslandSettings0 current:", json.dumps(old, sort_keys=True))
    print("IslandSettings0 desired:", json.dumps(desired, sort_keys=True))
    if not args.apply:
        print("Dry run; pass --apply to save the backed-up repair.")
        return

    backup_dir = bm.ROOT / "backups" / "pickaxe-slot-2026-10-08"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    (backup_dir / f"IslandSettings0-before-{stamp}.json").write_text(
        json.dumps({"actorPath": path, "properties": old, "after": desired}, indent=2),
        encoding="utf-8",
    )
    builder.props(path, desired)
    m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print("saved", m.tool(AS, "save_assets", asset_paths=[]))


if __name__ == "__main__":
    main()
