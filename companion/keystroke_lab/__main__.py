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
import pathlib
import sys
import time

import json

from . import autostart, binds as binds_cmd, coach, insights, drills, grader, keyboard_overlay, ktlog, profile, recorder, review


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
    if hasattr(binds, 'profile'):
        verified = {b.action for b in binds.profile.bindings if b.verified}
        missing = [a for a in drill.steps if a in binds and a not in verified]
        if missing:
            print('Calibrate these drill actions before grading: ' + ', '.join(dict.fromkeys(missing)))
            return 2
    keys = drills.expected_keys(drill, binds)
    watched = set(keys)
    alternates = {}
    if hasattr(binds, 'profile'):
        for binding in binds.profile.bindings:
            if binding.action in drill.steps and binding.verified:
                for key in binding.keys:
                    alternates.setdefault(key, binds[binding.action])
    presses = []

    def on_key(k):
        name = getattr(k, "char", None) or getattr(k, "name", str(k))
        name = str(name).lower()
        presses.append((time.perf_counter(), alternates.get(name, name)))

    def on_click(_x, _y, button, pressed):
        if pressed:
            name = f"mouse_{button.name}"
            presses.append((time.perf_counter(), alternates.get(name, name)))

    def on_scroll(_x, _y, dx, dy):
        name = "wheel_up" if dy > 0 else "wheel_down"
        presses.append((time.perf_counter(), alternates.get(name, name)))

    interval = grader.click_interval(args.tempo)
    reps = []
    with keyboard.Listener(on_press=on_key), mouse.Listener(on_click=on_click, on_scroll=on_scroll):
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
    base = None if args.no_log else (args.log or str(pathlib.Path("sessions") / time.strftime("keys-%Y%m%d-%H%M%S")))
    if base:
        print("recording to", base + ".jsonl / .events.jsonl (only while a Fortnite window is focused)")
    return keyboard_overlay.run(drills.load_binds(args.binds), drill, base, not args.no_ai, not args.no_port, binds_path=args.binds)


def cmd_binds(args):
    return binds_cmd.run(args.out, args.only, args.category)


def cmd_insights(args):
    records = []
    if args.uefn_log:
        try:
            records = ktlog.read_records(args.uefn_log)
        except OSError:
            print(f"(no UEFN log at {args.uefn_log}: key analysis only)")
    print(insights.report(args.files, records))
    return 0


def cmd_autostart(args):
    return autostart.main(args)


def cmd_collect(args):
    from . import collector
    from .store import Store
    store = Store()
    if args.once:
        a, b, c = collector.cycle(store, drills.load_binds())
        print(f"ingested {a} key events, {b} KT lines; correlated {c} edit locks")
        print(collector.summary(store))
        return 0
    from .keyboard_overlay import single_instance
    if not single_instance(r"Local\KeystrokeTrainerCollector"):
        print("a collector is already running")
        return 0
    print("collecting (Ctrl+C to stop): overlay recordings + UEFN log -> companion/data/player.db")
    try:
        collector.run(store)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_data(args):
    from . import collector
    from .store import Store
    print(collector.summary(Store()))
    return 0


def cmd_cloud(args):
    """Supabase backend: see your identity and consent, opt in or out, upload now, or delete everything."""
    from .cloud.client import CloudClient, CloudError
    from .cloud.sync import sync_once
    from .store import Store
    client = CloudClient()
    if not client.configured:
        print("Cloud is not configured: set SUPABASE_PROJECT_ID (or SUPABASE_URL) and SUPABASE_PUBLISHABLE_KEY in ../.env, or shared/cloud.json.")
        return 1
    try:
        if args.action == "status":
            me = client.rpc("me") or {}
            pending = Store().rows("SELECT COUNT(*) FROM edit_attempts WHERE synced=0")[0][0]
            print(f"player {client.player_id}  upload={bool(me.get('consent_upload'))} frames={bool(me.get('consent_frames'))} "
                  f"raw_keys={bool(me.get('consent_raw_keys'))}  attempts waiting: {pending}")
        elif args.action == "consent":
            me = client.rpc("register", {"upload": args.upload == "yes", "frames": args.frames == "yes",
                                         "raw_keys": args.raw_keys == "yes"})
            print("saved:", {k: me.get(k) for k in ("consent_upload", "consent_frames", "consent_raw_keys")})
        elif args.action == "sync":
            print(sync_once(Store(), client))
        elif args.action == "forget":
            if input("Delete every edit attempt, stat and label stored for this player? type DELETE: ") != "DELETE":
                print("cancelled")
                return 1
            client.rpc("delete_my_data")
            client.forget_local_identity()
            print("deleted on the server; this PC will get a new anonymous identity next time")
    except CloudError as exc:
        print("cloud error:", exc)
        return 1
    return 0


def cmd_review_edits(args):
    from . import attempt_review
    server, url = attempt_review.serve(open_browser=not args.no_browser)
    print("Edit review running at", url, "(Ctrl+C to stop)")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def cmd_personalize(args):
    from . import personalize
    stats, factors = personalize.run()
    for edit_id, s in sorted(stats.items()):
        print(f"{edit_id:22} attempts {s['attempts']:3}  factor {factors[edit_id]:.2f}")
    print("wrote", personalize.PERSONAL_JSON)
    return 0


def cmd_first_run(args):
    from . import first_run
    if args.reset:
        first_run.reset()
        print("calibration prompts reset: the next game start will offer calibration again if binds are unconfirmed")
        return 0
    missing = first_run.unverified()
    state = first_run.load_state()
    print("unconfirmed core actions:", ", ".join(missing) if missing else "none (calibrated)")
    print(f"prompts so far: {state.get('prompts', 0)} of {first_run.MAX_PROMPTS}")
    return 0


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
    b.add_argument("--category", nargs="*", choices=["move", "combat", "build", "edit", "ui"])
    b.set_defaults(fn=cmd_binds)
    au = sub.add_parser("autostart")
    au.add_argument("--install", action="store_true", help="run the watcher at every Windows login")
    au.add_argument("--uninstall", action="store_true")
    au.add_argument("--status", action="store_true")
    au.set_defaults(fn=cmd_autostart)
    co = sub.add_parser("collect")
    co.add_argument("--once", action="store_true", help="ingest and correlate what is there now, then exit")
    co.set_defaults(fn=cmd_collect)
    da = sub.add_parser("data")
    da.set_defaults(fn=cmd_data)
    cl = sub.add_parser("cloud", help="Supabase backend: status | consent | sync | forget")
    cl.add_argument("action", choices=["status", "consent", "sync", "forget"])
    cl.add_argument("--upload", choices=["yes", "no"], default="yes")
    cl.add_argument("--frames", choices=["yes", "no"], default="no")
    cl.add_argument("--raw-keys", choices=["yes", "no"], default="no")
    cl.set_defaults(fn=cmd_cloud)
    rv = sub.add_parser("review-edits", help="approve / reject recorded edit attempts in a local browser page")
    rv.add_argument("--no-browser", action="store_true")
    rv.set_defaults(fn=cmd_review_edits)
    pe = sub.add_parser("personalize")
    pe.set_defaults(fn=cmd_personalize)
    fr = sub.add_parser("first-run")
    fr.add_argument("--reset", action="store_true", help="forget earlier prompts so calibration is offered again")
    fr.set_defaults(fn=cmd_first_run)
    i = sub.add_parser("insights")
    i.add_argument("files", nargs="+", help="sessions/*.events.jsonl from `keys`")
    i.add_argument("--uefn-log", nargs="?", const=ktlog.DEFAULT_LOG, default=None,
                   help="also read drill step results (missing / wrong / late / early) from the UEFN editor log")
    i.set_defaults(fn=cmd_insights)
    k = sub.add_parser("keys")
    k.add_argument("--drill", help="drill id: highlights the next expected key and reports missed steps")
    k.add_argument("--binds")
    k.add_argument("--log", help="session file base name (default sessions/keys-<time>)")
    k.add_argument("--no-log", action="store_true")
    k.add_argument("--no-port", action="store_true", help="do not start the local JSON port on 127.0.0.1:8765")
    k.add_argument("--no-ai", action="store_true", help="local explanations only; send nothing to any API")
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
