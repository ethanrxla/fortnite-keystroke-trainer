"""Level select: one row of labelled buttons on the hub's north wall that send you to every level.

    python tools/build_level_select.py --dry-run   # list what would be placed
    python tools/build_level_select.py             # place it (replaces earlier KT3_* actors only)

Additive: only KT3_01..08 Button/Src/Dest and KT3_Sign are owned by this builder.
Other KT3 actors are preserved. Four buttons trigger the Activate function of portals that
already exist (Quick Start, Free Build, Aim, Arena). The four library wings have no hub portal, so
each gets a hidden source teleporter and a destination teleporter at its gate.

Teleporter groups: the Greybox template used A, B, C, D and Z and the build scripts use E to U.
Wing destinations here use H, I, J, K. Do not reuse a group: teleporters that share one are picked between.
"""

import argparse
import json
import sys
import pathlib
import re

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT3_"

def owns_label(label):
    return label == "KT3_Sign" or re.fullmatch(r"KT3_0[1-8]_(Button|Src|Dest)", label) is not None
# (button text, existing portal label or None, wing destination cell (di, dj) from the hub centre, group)
ENTRIES = [
    ("1  Quick Start (practice court)", "KT2_QuickStart", None, None),
    ("2  Free Build", "KT2_FreeStart", None, None),
    ("3  Build basics", None, (8, 0), "Group_H"),
    ("4  Movement, tunnels and boxes", None, (0, 8), "Group_I"),
    ("5  Edit course", None, (-8, 0), "Group_J"),
    ("6  Armory and switching", None, (0, -8), "Group_K"),
    ("7  Aim range", "KT_Portal_Aim", None, None),
    ("8  Bot arena", "KT_Portal_Arena", None, None),
]
ROW_X = 2330.0                     # just inside the hub's north wall
ROW_Y0, ROW_DY = -61800.0, 160.0   # eight buttons, 1.6 m apart, in the north-west stretch of the wall


def plan():
    out = []
    for k, (text, portal, wing, group) in enumerate(ENTRIES):
        out.append({"index": k + 1, "text": text, "portal": portal, "wing": wing, "group": group,
                    "pos": (ROW_X, ROW_Y0 + k * ROW_DY)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    items = plan()
    for it in items:
        dest = f"portal {it['portal']}" if it["portal"] else f"new teleporter pair to wing cell {it['wing']} ({it['group']})"
        print(f"{it['index']}. {it['text']:34} button at ({it['pos'][0]:.0f}, {it['pos'][1]:.0f})  ->  {dest}")
    if args.dry_run:
        return

    b = bm.Builder()
    found = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    if 'KT5_RiftRouter' in found:
        raise RuntimeError('Explicit rift routing is installed; use install_rift_router.py to repair selectors. No actors changed.')
    missing = [it['portal'] for it in items if it['portal'] and it['portal'] not in found]
    if missing:
        raise RuntimeError(f"Missing destinations; no actors changed: {missing}")
    for label, path in found.items():
        if owns_label(label):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    for it in items:
        if it["portal"] and it["portal"] not in found:
            print(f"warning: {it['portal']} not found in the level; button {it['index']} will do nothing")

    def n(i):
        return f"{PREFIX}{i:02d}"

    for it in items:
        x, y = it["pos"]
        btn = b.device(bm.BUTTON, f"{n(it['index'])}_Button", x, y, 0.0, 180.0)
        b.props(btn, {"interaction Text": it["text"]})
        events = b.m.tool(bm.DEVICE, "GetBindingOptions", devicePath={"refPath": btn}) or {}
        ev = next((e for e in events.get("sourceEvents", []) if "nteract" in e), None)
        if not ev:
            print(f"button {it['index']}: no interact event, not wired")
            continue
        if it["portal"]:
            target = found.get(it["portal"])
        else:
            di, dj = it["wing"]
            dx, dy = bm.hub_cc(di, dj)
            dest = b.device(bm.TELEPORTER, f"{n(it['index'])}_Dest", dx, dy, 0.0)
            b.props(dest, {"knob_TeleporterGroup": it["group"], "knob_TargetTeleporterGroup": "Group_None", "teleporter Rift Visible": False, "enabledDuringPhase": "Always"})
            target = b.device(bm.TELEPORTER, f"{n(it['index'])}_Src", x, y + 80, 0.0)
            b.props(target, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": it["group"], "change Teleporter Target": "On Entry", "maintain Relative Position": False, "conserve Momentum": False, "teleporter Rift Visible": False, "enabledDuringPhase": "Always"})
        if target:
            b.bind(btn, ev, target, "Activate")
    lines = "\n".join(it["text"] for it in items)
    b.sign({"label": f"{PREFIX}Sign", "pos": (ROW_X + 140, ROW_Y0 + 3.5 * ROW_DY, 330), "yaw": 180,
            "text": "LEVEL SELECT\nstand at a button and interact, left to right\n" + lines, "size": 30, "zone": "Hub"})
    print("level select placed")


if __name__ == "__main__":
    main()
