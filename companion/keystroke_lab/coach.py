"""AI coaching from the last finished set (design/training-ground-spec.md, section 5).

A published UEFN island cannot call the internet, so live AI coaching lives here, on the player's
own PC. It reads the same KT| lines the map prints (a UEFN playtest) and asks Claude for a short
explanation that sticks to the drill's principle. Without an API key, or with --offline, it prints
the static coaching text from shared/drills.json, so the feature degrades to the same words the map
already shows.

The model never changes the rules: the prompt hands it the principle and the drill's own wording
and tells it to explain, not to invent technique. The API key stays in ANTHROPIC_API_KEY on the
player's machine; nothing here is written to disk or sent anywhere else.
"""

import json
import os
import urllib.request

from . import envfile  # noqa: F401  (loads ../.env and maps CLAUDE_* to the names used below)
from collections import Counter

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("KT_COACH_MODEL", "claude-sonnet-5-5")

SYSTEM = (
    "You are a calm Fortnite building coach. You explain WHY a technique works so the player can "
    "think for themselves, not just what to press. Rules: use only the principle and wording given; "
    "do not invent new techniques or numbers; keep the player's creativity open (the principle fixes "
    "the goal, not the exact moves); if the player seems stuck, say that is normal while a habit is "
    "changing and suggest dropping one tempo; at most 70 words; plain sentences, no lists, no emoji."
)


def last_set(records):
    """The most recent set: its set_end record and the step records that led to it."""
    ends = [i for i, r in enumerate(records) if r.get("event") == "set_end"]
    if not ends:
        return None, []
    end = ends[-1]
    starts = [i for i, r in enumerate(records[:end]) if r.get("event") == "set_start"]
    begin = starts[-1] if starts else 0
    return records[end], [r for r in records[begin:end] if r.get("event") == "step"]


def error_summary(steps):
    """(step, result) -> count for every step that was not ok, worst first."""
    bad = Counter((r.get("step"), r.get("result")) for r in steps if r.get("result") not in ("ok", "unchecked"))
    return bad.most_common()


def static_text(drill, principle):
    parts = [f"{principle['name']}: {principle['rule']}" if principle else "", drill.tip, f"Think: {drill.reflect}"]
    return "\n".join(p for p in parts if p)


def build_prompt(set_end, steps, drill, principle):
    errors = error_summary(steps)
    lines = [
        f"Drill: {drill.name} ({drill.code}). Steps: {', '.join(drill.steps)}.",
        f"Principle: {principle['name']}. Rule: {principle['rule']} Reason: {principle['why']}" if principle else "",
        f"Room to be creative: {principle['creative']}" if principle else "",
        f"Result: {set_end.get('clean', '?')} of {set_end.get('rep', '?')} reps clean at {set_end.get('tempo', '?')} APM,"
        f" band {set_end.get('band', '?')}, hits taken {set_end.get('hits', 0)},"
        f" average latency {set_end.get('lat_ms', '?')} ms, decision {set_end.get('decision', '?')}.",
        "Errors by step: " + (", ".join(f"step {s} {r} x{n}" for (s, r), n in errors) if errors else "none."),
        f"Drill coaching sentence: {drill.tip}",
        f"Reflection question: {drill.reflect}",
        "Explain what the errors mean in terms of the principle, then ask the reflection question.",
    ]
    return "\n".join(x for x in lines if x)


def ask_claude(prompt, api_key, timeout=30):
    body = json.dumps({"model": MODEL, "max_tokens": 220, "system": SYSTEM,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API_URL, body, {
        "content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def coach(records, catalog, principles, offline=False):
    """Coaching text for the last set, or None when there is no finished set."""
    set_end, steps = last_set(records)
    if not set_end or set_end.get("drill_id") not in catalog:
        return None
    drill = catalog[set_end["drill_id"]]
    principle = principles.get(drill.principle)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if offline or not key:
        return static_text(drill, principle)
    try:
        return ask_claude(build_prompt(set_end, steps, drill, principle), key)
    except Exception as exc:  # network or API failure must never stop practice
        return static_text(drill, principle) + f"\n(AI coach unavailable: {type(exc).__name__})"
