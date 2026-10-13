"""Remove the lanes and areas consolidated away on 2026-10-13 (player: "i want to consolidate, so we can remove areas
taking up too much space ... for boxes, i like sky box the most. tunnel run and tunnel window ... just consolidate it").

    python tools/remove_consolidated.py --dry-run
    python tools/remove_consolidated.py

Removes the P4 (box up), P5 (tunnel run) and P8 (box and re-box) lane rooms with everything labelled for them or standing
inside them, and the Rebox Arena (KT14_Rebox_*, x 24576..30720, y -34816..-28672) except its court-side rift, return point
and sign (bay 02 of the court still sends players to the Sky Box through them). The removed labels go to
backups/consolidated-removed-2026-10-13.json.
"""
import argparse
import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

CODES = ("P4", "P5", "P8")       # first pass; later passes name their codes on the command line
KEEP = {"KT14_Rebox_Rift_In", "KT14_Rebox_Rift_Home", "KT14_Rebox_Sign_Court", "KT20_SignArt_KT14_Rebox_Sign_Court",
        "KT25_SignBack_KT14_Rebox_Sign_Court"}
ARENA = (24576.0, 30720.0, -34816.0, -28672.0)


def centre(a):
    b = a.get("bounds") or {}
    if "min" not in b:
        return None
    return [(b["min"][k] + b["max"][k]) / 2 for k in "xyz"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--codes", help="comma-separated lane codes to remove instead of CODES (no Rebox Arena)")
    ap.add_argument("--tag", default="2026-10-13", help="backup file suffix")
    args = ap.parse_args()
    codes = tuple(args.codes.split(",")) if args.codes else CODES
    m = bm.Mcp()
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    by = {a["label"]: a for a in acts}
    rooms = []
    for c in codes:
        ceil = by.get(f"KT_Ceil_Lane_{c}")
        if ceil:
            b = ceil["bounds"]
            rooms.append((b["min"]["x"] - 10, b["max"]["x"] + 10, b["min"]["y"] - 10, b["max"]["y"] + 10))
    if not args.codes:
        rooms.append(ARENA)
    doomed = []
    for a in acts:
        lab = a["label"]
        if lab in KEEP or not lab.startswith("KT"):
            continue
        # Rooms side by side share a boundary: never take a kept lane's wall or anything labelled for it.
        kept = re.compile(r"(?:^|_)(?:B5|E[47]|W[23]|P[2467])(?:_|$)")
        if kept.search(lab) and not any(re.search(rf"(?:^|_){c}(?:_|$)", lab) for c in codes):
            continue
        p = centre(a)
        size = [a["bounds"]["max"][k] - a["bounds"]["min"][k] for k in "xy"] if p else [0, 0]
        named = any(re.search(rf"(?:^|_){c}(?:_|$)", lab) for c in codes) or (not args.codes and lab.startswith("KT14_Rebox_"))
        inside = p and max(size) < 20000 and any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for x0, x1, y0, y1 in rooms)
        if named or inside:
            doomed.append(a)
    groups = {}
    for a in doomed:
        g = re.sub(r"(_\d+|_[A-Za-z]?\d+)$", "", a["label"])[:28]
        groups[g] = groups.get(g, 0) + 1
    for g, n in sorted(groups.items()):
        print(f"  {n:4} {g}")
    print(f"{len(doomed)} actors")
    if args.dry_run:
        return
    removed = []
    for a in doomed:
        try:
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
            removed.append(a["label"])
        except RuntimeError as exc:
            print("could not remove", a["label"], str(exc)[-60:])
    (bm.ROOT / "backups").mkdir(exist_ok=True)
    (bm.ROOT / "backups" / f"consolidated-removed-{args.tag}.json").write_text(json.dumps(sorted(removed), indent=1))
    print("removed", len(removed))


if __name__ == "__main__":
    main()
