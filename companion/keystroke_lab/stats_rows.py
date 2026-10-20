"""The SESSION STATS box's four keystroke rows, from keystroke_math.summary(). Pure; stats_panel.py draws them.

Every row always says something: drill wording when the map has graded steps this session, free-play wording when not.
A row is (label, value, bar) where bar is None, ("meter", fraction), ("centre", signed fraction) or
("stack", [(cause, count)]).
"""

from .keystroke_math import CAUSES, fix_next

CAUSE_LABEL = {"wrong_key": "wrong key", "slip": "slip", "early": "early", "late": "late", "missing": "missed",
               "double": "double", "modifier": "modifier", "unmapped": "unbound"}


def rows(s, action_of=None):
    out = []
    if s["steps"]:
        where = " · ".join(str(x) for x in (s.get("drill"), f"{s['tempo']} apm" if s.get("tempo") else None) if x)
        out.append(("Accuracy", f"{s['step_pct']}% clean · {s['clean']}/{s['steps']} steps"
                    + (f" ({where})" if where else ""), ("meter", s["clean"] / s["steps"])))
    elif s["presses"]:
        unbound = (s.get("causes") or {}).get("unmapped", 0)
        out.append(("Accuracy (free play)", f"{s['bound_pct']}% bound presses · {unbound} unbound",
                    ("meter", (s["bound_pct"] or 0) / 100)))
    else:
        out.append(("Accuracy", "no presses yet", None))

    if s.get("spread_ms") is not None:
        bits = [f"spread {s['spread_ms']} ms"]
        if s.get("beat_to_result_ms") is not None:
            bits.insert(0, f"beat→build {s['beat_to_result_ms']} ms")
        if s.get("drift"):
            bits.append(f"drift x{s['drift']}")
        off = s.get("median_offset_ms") or 0
        out.append(("Timing", " · ".join(bits), ("centre", max(-1.0, min(1.0, off / 150.0)))))
    else:
        out.append(("Timing", "needs a few clean drill steps", None))

    causes = s.get("causes") or {}
    if causes:
        top = max(causes, key=causes.get)
        label = f"{CAUSE_LABEL[top]} x{causes[top]}"
        if top in ("wrong_key", "slip") and s.get("top_pair"):
            (wrong, meant), n = s["top_pair"]
            label += f" ({wrong.upper()}→{meant.upper()} x{n})"
        out.append(("Misses by cause", label, ("stack", [(c, causes[c]) for c in CAUSES if causes.get(c)])))
    else:
        out.append(("Misses by cause", "none", None))

    out.append(("Fix next", fix_next(s, action_of) or "keep going", None))
    return out
