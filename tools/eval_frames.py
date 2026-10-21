"""Score the companion's piece detector on recorded edit frames (read only).

    python tools/eval_frames.py                 # confusion table, per-piece accuracy
    python tools/eval_frames.py --save base     # also write the result to companion/data/eval/<name>.json
    python tools/eval_frames.py --compare base  # and show the change against a saved result

Frames: every frame in companion/data/frames with a `truth` piece (frame_dataset.py), plus a fixed sample of WALLS
frames the detector already named "wall" with high confidence. Those walls are not reviewed, so they guard against a
change losing walls the guide finds today; they are not proof each one is a wall. Player 2026-10-21: the guide reads
ramps as walls and misses floors and cones; any change must keep walls as they are.
"""
import argparse
import collections
import json
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPANION = ROOT / "companion"
sys.path.insert(0, str(COMPANION / ".vision_packages"))
sys.path.insert(0, str(COMPANION))
import cv2  # noqa: E402
from keystroke_lab.piece_observation import VisualObserver  # noqa: E402

FRAMES = COMPANION / "data" / "frames"
EVAL = COMPANION / "data" / "eval"
WALLS = 200
PIECES = ("wall", "floor", "ramp", "cone")


def frames():
    truth, walls = [], []
    for manifest in sorted(FRAMES.glob("*/manifest.jsonl")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            image = manifest.parent / f"{r['frame_id']}.jpg"
            if not image.exists():
                continue
            if r.get("truth") and r["truth"].get("piece"):
                truth.append((str(image), r["truth"]["piece"], "reviewed"))
            elif r.get("auto", {}).get("piece") == "wall" and r["auto"].get("confidence", 1.0) >= 0.9:
                walls.append((str(image), "wall", "auto"))
    random.Random(20261021).shuffle(walls)
    return truth + walls[:WALLS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save")
    ap.add_argument("--compare")
    args = ap.parse_args()
    items = frames()
    table = collections.defaultdict(collections.Counter)
    per = {}
    spent = 0.0
    for path, want, source in items:
        image = cv2.imread(path)
        if image is None:
            continue
        start = time.perf_counter()
        got = VisualObserver().observe(image, time.time()).piece
        spent += time.perf_counter() - start
        table[want][got] += 1
        per[path] = got
    print(f"{len(per)} frames, {1000 * spent / max(len(per), 1):.0f} ms each")
    print(f"{'truth':8}" + "".join(f"{p:>9}" for p in PIECES + ("unknown",)) + "   correct")
    result = {}
    for want in PIECES:
        row = table.get(want)
        if not row:
            continue
        n = sum(row.values())
        result[want] = {"n": n, "correct": row[want], "as": dict(row)}
        print(f"{want:8}" + "".join(f"{row[p]:>9}" for p in PIECES + ("unknown",)) + f"   {row[want]}/{n} "
              f"({100 * row[want] / n:.0f}%)")
    wrong = sum(r["n"] - r["correct"] - r["as"].get("unknown", 0) for r in result.values())
    print(f"named the wrong piece: {wrong} (worse than abstaining: the guide then draws the wrong grid)")
    if args.compare:
        old = json.loads((EVAL / f"{args.compare}.json").read_text(encoding="utf-8"))
        for want, r in result.items():
            o = old["pieces"].get(want)
            if o:
                print(f"  {want:6} {o['correct']}/{o['n']} -> {r['correct']}/{r['n']}")
        changed = [p for p, g in per.items() if old["frames"].get(p) not in (None, g)]
        print(f"  frames whose answer changed: {len(changed)}")
    if args.save:
        EVAL.mkdir(parents=True, exist_ok=True)
        (EVAL / f"{args.save}.json").write_text(json.dumps({"pieces": result, "frames": per}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
