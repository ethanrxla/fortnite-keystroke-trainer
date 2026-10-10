"""Push to the running UEFN session; if validation rejects armory-wall items, drop those tiles and retry.

    python tools/push_and_prune_wall.py [--rounds 6]

UEFN only tells us an item is not Creative-legal when it validates a push, so the wall is built optimistically and
pruned here. Each rejected item's tile (KT9_ArmoryWall_NN_*) is removed, the item path is recorded in
shared/asset-exclusions.json and shared/armory-wall.json, so a rebuild never brings it back. Needs a connected session.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

LOG = pathlib.Path(os.environ["LOCALAPPDATA"]) / "UnrealEditorFortnite" / "Saved" / "Logs" / "UnrealEditorFortnite.log"
EXCL = bm.ROOT / "shared" / "asset-exclusions.json"
WALL = bm.ROOT / "shared" / "armory-wall.json"
PUSH = ("import sys;sys.path.insert(0,'tools');import build_map as bm;"
        "print(bm.Builder().m.tool('ValkyrieToolset.SessionToolset','PushChanges'))")


def push():
    try:
        out = subprocess.run([sys.executable, "-c", PUSH], cwd=str(bm.ROOT), capture_output=True, text=True, timeout=150)
        return (out.stdout + out.stderr).strip().splitlines()[-1:] or ["(no output)"]
    except subprocess.TimeoutExpired:
        return ["timed out (no session, or a dialog is open in UEFN)"]


def rejected_since(offset):
    text = LOG.read_bytes()[offset:].decode("utf-8", "replace")
    pairs = re.findall(r"Actor \((KT9_ArmoryWall_(\d+)_Granter)\) of Class \([^)]*\) referenced Disallowed Object \(([^)]+)\)", text)
    return {(tile, path.split(".")[0] + "." + path.split(".")[-1]) for _, tile, path in pairs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=6)
    args = ap.parse_args()
    m = bm.Builder().m
    for round_no in range(1, args.rounds + 1):
        offset = LOG.stat().st_size
        result = push()
        time.sleep(3)
        bad = rejected_since(offset)
        print(f"round {round_no}: push -> {result[0][:80]}; rejected items: {len(bad)}")
        if not bad:
            return 0 if "Completed" in result[0] else 1
        excl = json.loads(EXCL.read_text(encoding="utf-8"))
        wall = json.loads(WALL.read_text(encoding="utf-8"))
        for tile, path in sorted(bad):
            for a in m.tool(bm.SCENE, "find_actors", name=f"KT9_ArmoryWall_{tile}_", collision_channels=[]) or []:
                if a["label"].startswith(f"KT9_ArmoryWall_{tile}_"):
                    m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
            excl["rejected_item_paths"] = sorted(set(excl["rejected_item_paths"]) | {path})
            wall["items"] = [i for i in wall["items"] if i["item"].split(".")[0] != path.split(".")[0]]
            print(f"  removed tile {tile}: {path.split('/')[-1]}")
        EXCL.write_text(json.dumps(excl, indent=2), encoding="utf-8")
        WALL.write_text(json.dumps(wall, indent=1), encoding="utf-8")
        m.tool("editor_toolset.toolsets.asset.AssetTools", "save_assets", asset_paths=[])
    return 1


if __name__ == "__main__":
    sys.exit(main())
