"""Rewrite the action-sequence line on every station and lane sign from shared/drills.json.

    python tools/refresh_signs.py [--dry-run]

The signs are placed with text baked in, so changing a drill's steps leaves the old order on the wall.
This replaces only the line that holds the sequence (the one containing "  >  ") and leaves every other
line alone. Both KT_Sign_<code> (pad) and KT_Sign_Lane_<code> are updated.
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

SEP = "  >  "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    drills = json.loads((bm.ROOT / "shared" / "drills.json").read_text(encoding="utf-8"))["drills"]
    b = bm.Builder()
    found = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT_Sign_", collision_channels=[]) or [])}
    changed = 0
    for d in drills:
        chain = SEP.join(d["steps"])
        for label in (f"KT_Sign_{d['code']}", f"KT_Sign_Lane_{d['code']}"):
            path = found.get(label)
            if not path:
                continue
            text = json.loads(b.m.tool(bm.OBJ, "get_properties", instance={"refPath": path}, properties=["text"]))["text"]
            lines = text.split("\n")
            idx = next((i for i, ln in enumerate(lines) if SEP in ln), None)
            if idx is None or lines[idx] == chain:
                continue
            lines[idx] = chain
            changed += 1
            print(f"{label}: {text.splitlines()[idx]!r} -> {chain!r}")
            if not args.dry_run:
                b.props(path, {"text": "\n".join(lines)})
    print(f"{changed} sign texts {'would change' if args.dry_run else 'updated'}")


if __name__ == "__main__":
    main()
