"""Score edit policies against reviewed attempts, and build a blended policy from them.

    python tools/eval_edit_policy.py                          # score the current shared policies
    python tools/eval_edit_policy.py --blend                  # also build Jev+player blends and score them side by side
    python tools/eval_edit_policy.py --blend --write          # write shared/edit-policy*.blend.json for the better ones
    python tools/eval_edit_policy.py --include-auto           # early on: count confident unreviewed auto-labels too

A blend is only written when it beats the current policy on the same examples (policy_learning.better: enough
examples, higher top-1 without a worse top-3). Promote it by copying it over the shared file and regenerating Verse
(tools/build_edit_policy.py --regen-verse / tools/build_piece_policy.py); the Supabase publish step uses the same rule.
"""
import argparse
import json
import pathlib
import sys
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from keystroke_lab import policy_learning as pl  # noqa: E402
from keystroke_lab.edit_ranker import POLICY_FILES, Ranker  # noqa: E402
from keystroke_lab.pieces import canonical  # noqa: E402
from keystroke_lab.store import Store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--include-auto", action="store_true")
    ap.add_argument("--alpha", type=float, default=pl.ALPHA)
    args = ap.parse_args()
    samples = pl.examples(Store(), include_auto=args.include_auto)
    print(f"{len(samples)} usable attempts ({sum(s['reviewed'] for s in samples)} reviewed)")
    split = pl.partition(samples)
    print("session-separated split:", {k: len(v) for k,v in split.items()})
    base = Ranker(personal={})
    safe = False
    if args.write:
        safe = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                              cwd=ROOT / "companion").returncode == 0
    for kind, name in POLICY_FILES.items():
        piece = canonical(kind)
        path = ROOT / "shared" / name
        if not path.exists():
            continue
        current = pl.evaluate(split["test"], base, piece, partition_name="test")
        print(f"\n{piece}: current   {json.dumps(current)}")
        if not args.blend:
            continue
        policy = json.loads(path.read_text(encoding="utf-8"))
        blended = pl.blend(policy, split["train"], piece, args.alpha)
        candidate = Ranker(personal={}, policies={piece: blended})
        print("validation", json.dumps(pl.evaluate(split["validation"], candidate, piece, partition_name="validation")))
        scored = pl.evaluate(split["test"], candidate, piece, partition_name="test")
        scored["safety_passed"] = safe
        verdict = "BETTER" if pl.better(scored, current) else "not better (or too few examples)"
        print(f"{piece}: blend     {json.dumps(scored)}  -> {verdict}")
        if args.write and pl.better(scored, current):
            blended["metrics"] = {"current": current, "blend": scored, "split_version": "edit-split-v1"}
            out = path.with_suffix(".blend.json")
            out.write_text(json.dumps(blended, indent=1) + "\n", encoding="utf-8")
            print("  wrote", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
