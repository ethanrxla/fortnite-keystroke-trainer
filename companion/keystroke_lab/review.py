"""Replay your builds next to a suggested build, and say what you may not be seeing.

Input is a recording from `python -m keystroke_lab record` (only your bound keys and mouse buttons).
Output is one self-contained HTML file: no network, no external scripts, nothing sent anywhere.

How the suggestion is made. The suggested build is never invented. It is the catalog's reference order
for the drill your build matched, or whichever accepted alternative is closest to what you did (so you
are not told to change more than needed). It is paced at your own median speed, so it is attainable.
`--ai` (optional) lets Claude write a short plain-language explanation of the differences, using the
same safeguards as coach.py; the sequence itself still comes from the catalog.

What it can and cannot see. It sees the order and timing of your presses. It cannot see where the
crosshair was, whether a piece landed, or what an enemy did, so every insight is about order, gaps
and missing or extra presses, and is worded as a likely cause, not a certainty.
"""

import html
import json
import statistics

from . import profile

ACTION_LABEL = {"turn_right": "turn", "turn_left": "turn", "edit_confirm": "confirm", "swap_weapon": "gun", "pickaxe": "pick"}
PACE_FLOOR, PACE_CEIL = 0.18, 0.7   # seconds per action for the suggested build


def label(a):
    return ACTION_LABEL.get(a, a)


def align(yours, ref):
    """Edit-distance alignment. Returns ops [(kind, yours_index|None, ref_index|None)] with kind
    match | swap | extra (yours only) | missing (ref only)."""
    n, m = len(yours), len(ref)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (yours[i - 1] != ref[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (yours[i - 1] != ref[j - 1]):
            ops.append(("match" if yours[i - 1] == ref[j - 1] else "swap", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("extra", i - 1, None))
            i -= 1
        else:
            ops.append(("missing", None, j - 1))
            j -= 1
    return list(reversed(ops))


def closest_order(seq, drill):
    """The accepted order nearest to what the player did; the reference wins ties."""
    best = None
    for order in [drill.steps] + [list(a) for a in drill.accepts]:
        dist = profile.edit_distance(seq, order)
        if best is None or dist < best[0]:
            best = (dist, order)
    return best[1]


def suggested_times(order, pace):
    return [round(k * pace, 3) for k in range(len(order))]


def insights(build, order, ops, drill, principle, median_gap):
    """Plain-language, order-and-timing observations. Each is (principle id or '', text)."""
    seq = [a for _, a in build]
    t = [x for x, _ in build]
    out = []
    p = drill.principle
    why_shown = False
    # Order problems: for a swapped pair, say what the order cost in time.
    for kind, yi, rj in ops:
        if kind == "swap":
            want = order[rj]
            # where did the wanted action land in the player's own build, if at all?
            later = [k for k in range(len(seq)) if seq[k] == want and k > yi]
            if later:
                lag = t[later[0]] - t[yi]
                out.append((p, f"You pressed {label(seq[yi])} where the suggested order has {label(want)}. {label(want).capitalize()} came {lag:.2f} s later, "
                               f"so for that time the build was in a different state than the one the order is designed around."
                               + (f" ({principle['name']}: {principle['rule']})" if principle else "")))
            else:
                out.append((p, f"You pressed {label(seq[yi])} where the suggested order has {label(want)}, and {label(want)} never followed."))
        elif kind == "missing":
            note = f"No {label(order[rj])} in your build; the suggested order has one at step {rj + 1}."
            if drill.why and not why_shown:
                note += f" Why this drill is built this way: {drill.why}"
                why_shown = True
            out.append((p, note))
        elif kind == "extra":
            out.append(("", f"An extra {label(seq[yi])} at step {yi + 1} that the suggested order does not use. If it was a correction, the press before it is the one to look at."))
    # Hesitation: the slowest gap, if it stands out from your own pace.
    if len(t) > 1:
        gaps = [(t[k + 1] - t[k], k) for k in range(len(t) - 1)]
        g, k = max(gaps)
        if median_gap and g > 1.8 * median_gap and g > 0.35:
            out.append(("slow_is_smooth", f"Longest pause: {g:.2f} s between {label(seq[k])} and {label(seq[k + 1])}, about {g / median_gap:.1f} times your usual gap. "
                                          f"That is where the build slowed; practise that one transition on its own."))
    # An edit left open.
    already = any(k == "missing" and order[r] == "reset" for k, _, r in ops)
    if "edit_confirm" in seq and "reset" not in seq and "reset" in order and not already:
        out.append(("reset_always", "You edited and never reset. An open wall is a free shot for the other player."))
    if not out:
        out.append(("", "Same order as the suggestion. The next gain is rhythm: keep the gaps even."))
    return out


def build_entries(events, binds, catalog, principles, limit=6):
    """One entry per recognised build, worst first (those that differ from the suggestion), then clean ones."""
    builds = profile.segment(profile.to_actions(events, binds))
    gaps = [b[k + 1][0] - b[k][0] for b in builds for k in range(len(b) - 1)]
    median_gap = statistics.median(gaps) if gaps else 0.4
    pace = max(PACE_FLOOR, min(PACE_CEIL, median_gap))
    entries = []
    for b in builds:
        did, dist = profile.classify(b, catalog)
        if did is None:
            continue
        drill = catalog[did]
        seq = [a for _, a in b]
        order = closest_order(seq, drill)
        ops = align(seq, order)
        t0 = b[0][0]
        entries.append({
            "drill": did, "name": drill.name, "code": drill.code, "distance": profile.drill_distance(seq, drill),
            "yours": [{"a": a, "t": round(t - t0, 3)} for t, a in b],
            "suggested": [{"a": a, "t": x} for a, x in zip(order, suggested_times(order, pace))],
            "ops": [list(o) for o in ops],
            "insights": [{"principle": p, "text": s} for p, s in insights(b, order, ops, drill, principles.get(drill.principle), median_gap)],
            "principle": principles.get(drill.principle, {}).get("name", ""),
            "start": t0,
        })
    entries.sort(key=lambda e: (-e["distance"], -e["start"]))
    return entries[:limit], {"median_gap": round(median_gap, 3), "pace": round(pace, 3), "builds": len(builds), "matched": len(entries)}


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RXLA build review</title><style>
:root{--bg:#050506;--panel:#101114;--line:#2a2c33;--ink:#f2f2f2;--mute:#a4a8b3;--fire:#ff6a0a;--ok:#5fd38d;--bad:#ff8a6b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:28px 18px 60px}
h1{font:800 34px/1.1 system-ui;margin:0 0 4px}h2{font:700 20px/1.2 system-ui;margin:0}
.eyebrow{font:600 12px ui-monospace,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--fire)}
.sub{color:var(--mute);margin:6px 0 20px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;margin:16px 0}
.row{display:grid;grid-template-columns:84px minmax(0,1fr);gap:10px;align-items:center;margin:8px 0}
.lbl{font:600 12px ui-monospace,Consolas,monospace;color:var(--mute);text-transform:uppercase}
.scrollx{overflow-x:auto;scrollbar-color:#ff6a0a #101114;scrollbar-width:thin}.track{position:relative;height:40px;border-bottom:1px solid var(--line)}
.chip{position:absolute;top:2px;padding:5px 9px;border-radius:5px;font:700 13px system-ui;background:#23252c;color:#8b8f9a;border:1px solid var(--line);white-space:nowrap;transition:background .15s,color .15s}
.chip.on{background:var(--fire);color:#050506;border-color:var(--fire)}.chip.off{outline:2px solid var(--bad)}.chip.sug.on{background:var(--ok);border-color:var(--ok)}
button{background:var(--fire);color:#050506;font:700 14px system-ui;border:0;border-radius:6px;padding:9px 16px;cursor:pointer;min-height:44px}
button:focus-visible{outline:3px solid #fff;outline-offset:2px}ul{margin:10px 0 0;padding-left:20px}li{margin:6px 0}.tag{color:var(--fire);font-weight:700}
.meta{display:flex;gap:18px;flex-wrap:wrap;color:var(--mute);font-size:13px;margin:6px 0 10px}.ok{color:var(--ok)}
.note{color:var(--mute);font-size:13px;margin-top:22px}
</style></head><body><div class="wrap">
<div class="eyebrow">RXLA · Training Ground · Build review</div><h1>What you did, next to what is suggested</h1>
<p class="sub">__SUMMARY__</p>__CARDS__
<p class="note">The suggested build is the catalog's order for the drill your build matched (or the accepted alternative closest to yours), paced at your own speed. This page sees the order and timing of your presses, not your crosshair, so each note is a likely cause, not a certainty. Nothing here left your computer.</p>
</div><script>
const DATA=__DATA__;
function play(i){const e=DATA[i];const span=Math.max(e.yours[e.yours.length-1].t,e.suggested[e.suggested.length-1].t)||1;
 const chips=[...document.querySelectorAll('#b'+i+' .chip')];chips.forEach(c=>c.classList.remove('on'));
 const t0=performance.now();const speed=Math.max(1,span)<2?1:1;(function tick(now){const t=(now-t0)/1000*speed;
  chips.forEach(c=>{if(parseFloat(c.dataset.t)<=t)c.classList.add('on')});if(t<span+0.3)requestAnimationFrame(tick)})(t0)}
</script></body></html>"""


def render_html(entries, summary):
    cards = []
    for i, e in enumerate(entries):
        span = max(e["yours"][-1]["t"], e["suggested"][-1]["t"]) or 1.0
        times = sorted({c["t"] for c in e["yours"] + e["suggested"]})
        min_gap = min((b - a for a, b in zip(times, times[1:]) if b - a > 0.001), default=0.5)
        pxps = max(120.0, 70.0 / min_gap)          # at least 70 px between neighbouring presses
        width = max(320.0, span * pxps + 90.0)
        wrong = {yi for kind, yi, _ in e["ops"] if kind in ("swap", "extra") and yi is not None}

        def chips(items, cls, bad=()):
            out = []
            for k, c in enumerate(items):
                left = c["t"] * pxps
                out.append(f'<span class="chip {cls}{" off" if k in bad else ""}" style="left:{left:.0f}px" data-t="{c["t"]}">{html.escape(label(c["a"]))}</span>')
            return "".join(out)

        state = '<span class="ok">same order as suggested</span>' if e["distance"] == 0 else f'{e["distance"]} change{"s" if e["distance"] != 1 else ""} from the suggestion'
        notes = "".join(f'<li>{"<span class=tag>" + html.escape(x["principle"].replace("_", " ")) + ":</span> " if x["principle"] else ""}{html.escape(x["text"])}</li>' for x in e["insights"])
        cards.append(
            f'<div class="card" id="b{i}"><h2>{html.escape(e["code"])}  {html.escape(e["name"])}</h2>'
            f'<div class="meta"><span>{state}</span><span>your build {e["yours"][-1]["t"]:.2f} s</span><span>suggested {e["suggested"][-1]["t"]:.2f} s</span>'
            f'<span>principle: {html.escape(e["principle"])}</span></div>'
            f'<div class="row"><div class="lbl">Yours</div><div class="scrollx"><div class="track" style="width:{width:.0f}px">{chips(e["yours"], "you", wrong)}</div></div></div>'
            f'<div class="row"><div class="lbl">Suggested</div><div class="scrollx"><div class="track" style="width:{width:.0f}px">{chips(e["suggested"], "sug")}</div></div></div>'
            f'<button onclick="play({i})" aria-label="Replay this build and the suggestion">Replay</button>'
            f'<ul>{notes}</ul></div>')
    s = (f'{summary["matched"]} of {summary["builds"]} recorded builds matched a drill. Your median gap between presses is {summary["median_gap"]:.2f} s; '
         f'the suggestions are paced at {summary["pace"]:.2f} s.' if summary["builds"] else "No builds found in this recording yet.")
    data = json.dumps([{"yours": e["yours"], "suggested": e["suggested"]} for e in entries])
    return PAGE.replace("__SUMMARY__", html.escape(s)).replace("__CARDS__", "".join(cards) or "<p>Record some play first.</p>").replace("__DATA__", data.replace("</", "<\\/"))


def explain_with_claude(entries, principles):
    """Optional: one short paragraph per top build, from coach.ask_claude. Falls back to nothing."""
    import os
    from . import coach
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return entries
    for e in entries[:3]:
        if e["distance"] == 0:
            continue
        prompt = (f"Drill {e['name']}. Principle: {e['principle']}. The player pressed: {' > '.join(c['a'] for c in e['yours'])}. "
                  f"The suggested order is: {' > '.join(c['a'] for c in e['suggested'])}. Observations: "
                  + " ".join(x["text"] for x in e["insights"]) + " Explain, in two or three plain sentences, what the player may not be seeing and what to try next.")
        try:
            e["insights"].append({"principle": "", "text": coach.ask_claude(prompt, key)})
        except Exception as exc:  # never block the review on a network error
            e["insights"].append({"principle": "", "text": f"(AI note unavailable: {type(exc).__name__})"})
    return entries
