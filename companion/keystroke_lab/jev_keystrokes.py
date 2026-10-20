"""Jev for keystroke intent (contract ktkey/1): only the presses keystroke_math marks ambiguous.

What arithmetic settles never reaches Jev: clean / early / late / missing / double / modifier, and a wrong key that is
corrected within SELF_CORRECT_S (a slip). Jev answers two atomic questions per ambiguous press, batched (one call holds
up to EVENTS_PER_CALL presses; JevClient allows 8 questions):

  <event_id>.intended  choice  which bound action the press was reaching for: the candidate actions next to it, plus
                               none_deliberate and insufficient_evidence
  <event_id>.slip      noul    was it a finger slip rather than a decision

The event id is the question key, so an answer can only land on the press it was asked about (a late or reordered
reply for a profile revision that has since changed is dropped by `interpret`). Gating follows docs.typesafe.ai
/confidence: act when sure, show as "likely" when middling, otherwise unclassified; never an LLM fallback.
Thresholds are starting points, to be calibrated against reviewed labels.
"""

import math

from .evidence import validate_choice
from .keyboard_overlay import neighbours, normal

SCHEMA = "ktkey/1"
EVENTS_PER_CALL = 4
LIVE_CONFIDENCE = 0.80          # shown live on the overlay
LIVE_RATIO = 3.0                # and the chosen option beats the runner-up at least this many times
LIVE_PROBABILITY = 0.90         # and has at least this probability (analysis.py's existing gate)
LIKELY_CONFIDENCE = 0.50        # counted as "likely" in the stats box only
SLIP_YES = 0.70                 # noul: a slip when P(yes) is at least this
FALLBACK = ("none_deliberate", "insufficient_evidence")

INTENDED = ("A Fortnite player pressed `events.{id}.key` during a drill step that expected "
            "`events.{id}.expected_action`. Which of their bound actions was this press reaching for?")
SLIP = ("Was the press of `events.{id}.key` a finger slip (a mis-hit on a nearby key) rather than a deliberate "
        "press? Use `events.{id}.neighbours`, `events.{id}.just_before` and `events.{id}.offset_ms`.")


def candidates(event, bound):
    """{action: description} the press could have been reaching for: actions bound to physically adjacent keys, plus
    the step's expected action. bound: key -> set of verified actions."""
    key = normal(event["key"])
    out = {}
    for k in neighbours(key):
        for action in sorted(bound.get(k, ())):
            out.setdefault(action, {"key": k, "covers": f"the player meant '{k}' ({action}) and hit '{key}' beside it"})
    exp = event.get("expected_action")
    if exp and exp not in out:
        keys = sorted(k for k, acts in bound.items() if exp in acts)
        out[exp] = {"key": keys[0] if keys else None, "covers": f"the drill's expected action {exp}"}
    out["none_deliberate"] = {"key": None, "covers": "pressed on purpose for something outside the drill"}
    out["insufficient_evidence"] = {"key": None, "covers": "these observations cannot tell"}
    return out


def build(events, bound, profile_rev, context="drill"):
    """(state, questions, options_by_id) for up to EVENTS_PER_CALL events. Each event needs an `id` and `key`;
    optional expected_action, offset_ms, baseline, just_before."""
    events = list(events)[:EVENTS_PER_CALL]
    state = {"schema": SCHEMA, "profile_rev": profile_rev, "context": context, "events": {}}
    questions, options = {}, {}
    for e in events:
        opts = candidates(e, bound)
        options[e["id"]] = opts
        state["events"][e["id"]] = {
            "key": normal(e["key"]), "bound": bool(bound.get(normal(e["key"]))),
            "expected_action": e.get("expected_action"),
            "neighbours": {k: sorted(bound.get(k, ())) or None for k in neighbours(normal(e["key"]))},
            "offset_ms": e.get("offset_ms"), "baseline": e.get("baseline"), "just_before": e.get("just_before", [])}
        questions[f"{e['id']}.intended"] = {
            "type": "choice", "instructions": INTENDED.format(id=e["id"]),
            "criteria": {a: o["covers"] for a, o in opts.items()}}
        questions[f"{e['id']}.slip"] = {"type": "noul", "instructions": SLIP.format(id=e["id"])}
    return state, questions, options


def ratio(probabilities):
    top = sorted(probabilities.values(), reverse=True)
    return math.inf if len(top) < 2 or top[1] <= 0 else top[0] / top[1]


def gate(answer):
    """live | likely | unclassified for one validated choice answer."""
    if answer["choice"] in FALLBACK:
        return "unclassified"
    c = answer["confidence"]
    p = answer["probabilities"][answer["choice"]]
    if c >= LIVE_CONFIDENCE and p >= LIVE_PROBABILITY and ratio(answer["probabilities"]) >= LIVE_RATIO:
        return "live"
    if c >= LIKELY_CONFIDENCE:
        return "likely"
    return "unclassified"


def interpret(answers, events, options, profile_rev, current_rev):
    """Validated results, one per event. A reply for an old profile revision, an unknown option, probabilities that do
    not cover exactly the options or do not sum to 1, or a non-argmax choice is rejected, never shown."""
    if profile_rev != current_rev or not isinstance(answers, dict):
        return []
    out = []
    for e in events:
        opts = options.get(e["id"])
        a = answers.get(f"{e['id']}.intended")
        if not opts or not validate_choice(a, list(opts)):
            out.append({"kind": "jev", "event_id": e["id"], "key": normal(e["key"]), "accepted": "rejected"})
            continue
        slip = answers.get(f"{e['id']}.slip") or {}
        p_slip = slip.get("noul") if isinstance(slip.get("noul"), (int, float)) and 0 <= slip["noul"] <= 1 else None
        accepted = gate(a)
        out.append({"kind": "jev", "event_id": e["id"], "key": normal(e["key"]), "intended": a["choice"],
                    "intended_key": opts[a["choice"]]["key"], "p": round(a["probabilities"][a["choice"]], 3),
                    "confidence": round(a["confidence"], 3), "ratio": round(min(ratio(a["probabilities"]), 99), 2),
                    "slip_p": p_slip, "slip": p_slip is not None and p_slip >= SLIP_YES,
                    "accepted": accepted, "profile_rev": profile_rev})
    return out


def ask(client, events, bound, profile_rev, current_rev=None, context="drill"):
    """One call through JevClient (budget, broker, retries live there). [] when Jev is unavailable."""
    if not events or client is None or not client.available:
        return []
    state, questions, options = build(events, bound, profile_rev, context)
    answers = client.decide(state, questions)
    return interpret(answers, events[:EVENTS_PER_CALL], options, profile_rev,
                     profile_rev if current_rev is None else current_rev)
