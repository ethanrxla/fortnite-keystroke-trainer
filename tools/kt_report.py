"""Summarize drill results from a UEFN playtest log, for coding agents and humans.

    python tools/kt_report.py [--log PATH] [--since-last-start]

Prints one line per finished set and a per-step error table, as JSON with --json.
"""

import argparse
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "companion"))
from keystroke_lab import ktlog  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=ktlog.DEFAULT_LOG)
    ap.add_argument("--since-last-start", action="store_true", help="only the most recent set")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    recs = ktlog.read_records(args.log)
    if args.since_last_start:
        starts = [i for i, r in enumerate(recs) if r["event"] == "set_start"]
        recs = recs[starts[-1]:] if starts else recs
    sets = [r for r in recs if r["event"] == "set_end"]
    errors = Counter((r["drill_id"], r.get("step"), r.get("result")) for r in recs
                     if r["event"] == "step" and r.get("result") not in ("ok", "unchecked"))
    problems = [r for r in recs if r["event"] == "config_error"]
    if args.json:
        print(json.dumps({"sets": sets, "step_errors": [
            {"drill_id": d, "step": s, "result": res, "count": n} for (d, s, res), n in errors.most_common()],
            "config_errors": problems}, indent=2))
        return 0
    for r in problems:
        print(f"CONFIG {r['drill_id']}: {r.get('reason', '?')}")
    for r in sets:
        extra = f"  hits {r['hits']}  lat {r['lat_ms']} ms  {r['band']}" if "band" in r else ""
        print(f"{r['drill_id']:18} {r['tempo']:>3} APM  clean {r.get('clean', '?')}/{r.get('rep', '?')}  -> {r.get('decision', '?')}{extra}")
    for (d, s, res), n in errors.most_common():
        print(f"  {d} step {s}: {res} x{n}")
    if not (sets or errors or problems):
        print("no KT| lines found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
