"""Keystroke Lab CLI.

    python -m keystroke_lab list
    python -m keystroke_lab practice wall_ramp_floor --tempo 60 [--binds keybinds.json]
    python -m keystroke_lab watch [--log PATH]     # print KT| lines from a UEFN playtest live
    python -m keystroke_lab record --out sessions/today.jsonl [--flicks]   # log your own build inputs
    python -m keystroke_lab analyze sessions/*.jsonl   # per-drill stats and weakest steps
    python -m keystroke_lab review sessions/*.jsonl --out review.html [--ai]   # replay your builds next to a suggested build
    python -m keystroke_lab plan sessions/*.jsonl [--minutes 15]   # a personal warm-up from your recordings
    python -m keystroke_lab coach [--log PATH] [--offline]   # explain the last set (Claude if ANTHROPIC_API_KEY is set)

`practice` needs `pip install pynput` (reads your own keyboard/mouse only).
"""

import argparse
import sys
import time

import json

from . import binds as binds_cmd, coach, drills, grader, keyboard_overlay, ktlog, profile, recorder, review


def cmd_list(_):
    ladder, catalog = drills.load_catalog()
    for d in catalog.values():
        print(f"T{d.tier}  {d.id:18} {', '.join(d.steps)}")
    print("tempo ladder:", " -> ".join(map(str, ladder)), "-> free")


def cmd_practice(args):
    try:
        from pynput import keyboard, mouse
    except ImportError:
        print("practice needs pynput: pip install pynput")
        return 2
    _, catalog = drills.load_catalog()
    drill = catalog[args.drill]
    binds = drills.load_binds(args.binds)
    keys = drills.expected_keys(drill, binds)
    watched = set(binds.values())
    presses = []

    def on_key(k):
        name = getattr(k, "char", None) or getattr(k, "name", str(k))
        presses.append((time.perf_counter(), str(name).lower()))

    def on_click(_x, _y, button, pressed):
        if pressed:
            presses.append((time.perf_counter(), f"mouse_{button.name}"))

    interval = grader.click_interval(args.tempo)
    reps = []
    with keyboard.Listener(on_press=on_key), mouse.Listener(on_click=on_click):
        for rep in range(1, drill.reps + 1):
            print(f"\nrep {rep}/{drill.reps}  ({args.tempo} APM)")
            time.sleep(interval)
            presses.clear()
            start = time.perf_counter()
            for i, action in enumerate(drill.steps):
                target = start + i * interval
                time.sleep(max(0.0, target - time.perf_counter()))
                print(f"\a  {action:>12}", flush=True)
            time.sleep(interval)
            r = grader.grade_rep(keys, list(presses), start, args.tempo, watched)
            reps.append(r)
            print("  " + "  ".join(s.result for s in r.steps) + ("  +extra" if r.extra_keys else ""))
    s = grader.grade_set(reps)
    print(f"\naccuracy {s.accuracy:.0%}  timing spread {s.timing_spread_ms:.0f} ms  errors {s.errors}")
    return 0


def cmd_watch(args):
    for rec in ktlog.follow(args.log):
        print(rec, flush=True)


def cmd_coach(args):
    _, catalog = drills.load_catalog()
    text = coach.coach(ktlog.read_records(args.log), catalog, drills.load_principles(), offline=args.offline)
    print(text or "no finished set in the log yet")


def _events(paths):
    out, offset = [], 0.0
    for p in paths:
        ev = recorder.load(p)
        out += [dict(e, t=e["t"] + offset) for e in ev]
        offset += (ev[-1]["t"] if ev else 0.0) + 60.0  # keep sessions apart so builds never join across files
    return out


def cmd_record(args):
    return recorder.run(args.out, drills.load_binds(args.binds), flicks=args.flicks)


def cmd_analyze(args):
    _, catalog = drills.load_catalog()
    stats = profile.analyze(_events(args.sessions), drills.load_binds(args.binds), catalog)
    scores = profile.weakness(stats)
    if not stats:
        print("no builds matched a drill yet; record some play first")
        return
    for did in sorted(stats, key=lambda d: -scores[d]):
        s = stats[did]
        slow = s["slowest_transition"]
        print(f"{did:18} builds {s['builds']:>3}  clean {s['clean_rate']:.0%}  {profile.measured_apm(s):>5.0f} APM  "
              f"spread {s['gap_spread'] * 1000:>4.0f} ms  weakness {scores[did]:.2f}  slowest {slow[0]} ({slow[1] * 1000:.0f} ms)")


def cmd_plan(args):
    _, catalog = drills.load_catalog()
    stats = profile.analyze(_events(args.sessions), drills.load_binds(args.binds), catalog) if args.sessions else {}
    result = profile.plan(stats, catalog, minutes=args.minutes)
    for b in result["blocks"]:
        print(f"{b['block']} ({b['minutes']} min)")
        for d in b["drills"]:
            print(f"  {d['code']:3} {d['name']:22} at {d['tempo']} APM  - {d['why']}")
    if args.out:
        import pathlib
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")


def cmd_review(args):
    _, catalog = drills.load_catalog()
    principles = drills.load_principles()
    entries, summary = review.build_entries(_events(args.sessions), drills.load_binds(args.binds), catalog, principles, limit=args.limit)
    if args.ai:
        entries = review.explain_with_claude(entries, principles)
    import pathlib
    pathlib.Path(args.out).write_text(review.render_html(entries, summary), encoding="utf-8")
    print(f"wrote {args.out}: {len(entries)} builds shown ({summary['matched']} of {summary['builds']} recorded builds matched a drill)")


def cmd_keys(args):
    _, catalog = drills.load_catalog()
    drill = catalog[args.drill] if args.drill else None
    return keyboard_overlay.run(drills.load_binds(args.binds), drill)


def cmd_binds(args):
    return binds_cmd.run(args.out, args.only)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="keystroke_lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("practice")
    p.add_argument("drill")
    p.add_argument("--tempo", type=int, default=40)
    p.add_argument("--binds")
    p.set_defaults(fn=cmd_practice)
    w = sub.add_parser("watch")
    w.add_argument("--log", default=ktlog.DEFAULT_LOG)
    w.set_defaults(fn=cmd_watch)
    c = sub.add_parser("coach")
    c.add_argument("--log", default=ktlog.DEFAULT_LOG)
    c.add_argument("--offline", action="store_true")
    c.set_defaults(fn=cmd_coach)
    r = sub.add_parser("record")
    r.add_argument("--out", required=True)
    r.add_argument("--binds")
    r.add_argument("--flicks", action="store_true")
    r.set_defaults(fn=cmd_record)
    a = sub.add_parser("analyze")
    a.add_argument("sessions", nargs="+")
    a.add_argument("--binds")
    a.set_defaults(fn=cmd_analyze)
    rv = sub.add_parser("review")
    rv.add_argument("sessions", nargs="+")
    rv.add_argument("--binds")
    rv.add_argument("--out", default="review.html")
    rv.add_argument("--limit", type=int, default=6)
    rv.add_argument("--ai", action="store_true", help="add a short Claude explanation (needs ANTHROPIC_API_KEY)")
    rv.set_defaults(fn=cmd_review)
    b = sub.add_parser("binds")
    b.add_argument("--out", default=str(drills.BINDS_FILE))
    b.add_argument("--only", nargs="*")
    b.set_defaults(fn=cmd_binds)
    k = sub.add_parser("keys")
    k.add_argument("--drill", help="drill id: highlights the next expected key and reports missed steps")
    k.add_argument("--binds")
    k.set_defaults(fn=cmd_keys)
    pl = sub.add_parser("plan")
    pl.add_argument("sessions", nargs="*")
    pl.add_argument("--binds")
    pl.add_argument("--minutes", type=int, default=15)
    pl.add_argument("--out")
    pl.set_defaults(fn=cmd_plan)
    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
