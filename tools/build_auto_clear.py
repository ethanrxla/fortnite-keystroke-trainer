"""Clear player builds from the main area on a timer (about once a minute).

    python tools/build_auto_clear.py [--dry-run] [--seconds 60]

One hidden Timer device (starts with the match, restarts when it ends) fires:
  * the practice court's reset barrels (KT2_ResetRig_*, placed by the court builder), and
  * new clearing barrels spread over the hub, the four wings and the bridges (KT3_HubClear_*).
Every barrel does structure damage only (player damage 0, no knockback, hidden) and re-arms itself, so it
can fire every cycle. Lanes are not touched: they clear themselves at the start of every set and rep.

All new actors are labelled KT3_AutoClear_* or KT3_HubClear_*; only those are replaced on a rerun. The
court's barrels are only given extra bindings, never moved or re-configured.

Notes:
  * A clear happens even while someone is mid-build; there is no warning yet.
  * The timer starts at match start. After a push the match restarts, which restarts the cycle.
"""

import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

TIMER = "/CreativeCoreDevices/SetupAssets/PID_Device_Timer.PID_Device_Timer"
SPACING = 6          # cells between clearing barrels inside a region
BLAST = 4            # tiles
PREFIXES = ("KT3_AutoClear_", "KT3_HubClear_")


def barrel_points(drills_plan):
    """[(x, y, label)] covering the hub, wings and bridges from build_map's own slab list."""
    pts, n = [], 0
    for sl in drills_plan["slabs"]:
        if not sl["label"].startswith(("KT_Hub", "KT_Wing_", "KT_Bridge_")):
            continue
        x0, x1, y0, y1 = sl["bounds"]
        ni, nj = int(round((x1 - x0) / bm.CELL)), int(round((y1 - y0) / bm.CELL))
        gi, gj = max(1, math.ceil(ni / SPACING)), max(1, math.ceil(nj / SPACING))
        for a in range(gi):
            for c in range(gj):
                x = x0 + (a + 0.5) * (x1 - x0) / gi
                y = y0 + (c + 0.5) * (y1 - y0) / gj
                pts.append((x, y, f"KT3_HubClear_{n:02d}"))
                n += 1
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seconds", type=float, default=60.0)
    args = ap.parse_args()
    drills = [d for d in json.loads((bm.ROOT / "shared" / "drills.json").read_text(encoding="utf-8"))["drills"] if not d.get("retired")]
    pts = barrel_points(bm.plan(drills))
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    court = sorted(v for k, v in acts.items() if k.startswith("KT2_ResetRig_"))
    print(f"{len(pts)} hub and wing barrels, {len(court)} court barrels, every {args.seconds:.0f} s")
    if args.dry_run:
        return
    for label, path in acts.items():
        if label.startswith(PREFIXES):
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    hx, hy = bm.hub_cc(0, 0)
    timer = b.device(TIMER, "KT3_AutoClear_Timer", hx - 2 * bm.CELL, hy - 3 * bm.CELL, 0.0)
    schema = json.loads(b.m.tool(bm.OBJ, "list_properties", instance={"refPath": timer}))
    behaviours = (schema.get("completionBehavior") or {}).get("enum", [])
    restart = next((e for e in behaviours if "estart" in e), None)
    props = {"duration": args.seconds, "startAtGameStart": True, "visibleDuringGame": False, "successOnTimerEnd": True}
    if restart:
        props["completionBehavior"] = restart
    else:
        print("warning: no restart option on the timer; options were", behaviours)
    b.props(timer, props)
    barrels = []
    for x, y, label in pts:
        boom = b.device(bm.EXPLOSIVE, label, x, y, bm.LEVEL_H / 2)
        b.props(boom, {"blast Radius": BLAST, "player Damage": 0, "structure Damage": 100000,
                       "visible During Game": False, "knockbackPlayer": 0})
        b.bind(boom, "On Exploded", boom, "Reset")
        barrels.append(boom)
    for boom in barrels + court:
        b.bind(timer, "OnSuccess", boom, "Explode")
    for rig in court:
        b.bind(rig, "On Exploded", rig, "Reset")      # re-arm so the next cycle fires too (a repeat reset is harmless)
    print("auto clear placed: timer, ", len(barrels), "hub barrels,", len(court), "court barrels wired")


if __name__ == "__main__":
    main()
