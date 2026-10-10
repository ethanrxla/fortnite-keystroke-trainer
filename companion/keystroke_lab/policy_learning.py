"""Learn edit priors from reviewed attempts and measure how good a policy is.

    examples(store)                      reviewed attempts as (piece, aim, side, far, edit made, outcome, followed)
    blend(policy, examples, piece)       Jev's prior + what players actually did, per situation (Dirichlet posterior)
    evaluate(examples, ranker)           top-1 / top-3 / MRR, calibration, completion when the guide was followed

Blend: Jev's prior for a situation acts as ALPHA pseudo-attempts. Each completed, approved attempt adds one count to the
edit made (and one to its mirror image in the mirrored situation, so the table stays left/right unbiased). With no data a
situation keeps Jev's prior exactly; with many attempts the players' real choices dominate. Priors stay floored at the
policy's prior_floor and sum to 1, so EditGuide.verse and edit_ranker read the result unchanged.
"""
import json
import math
import pathlib
from collections import defaultdict

from .edit_ranker import situation_key
from .pieces import canonical, catalog_key, cells

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALPHA = 20.0


def examples(store, include_auto=False, min_confidence=0.75):
    """Reviewed attempts usable for learning. Approved -> the matched edit; relabelled -> the reviewer's edit.
    include_auto adds unreviewed attempts whose auto-label confidence is high (for early, small datasets)."""
    out = []
    for (raw,) in store.rows("SELECT record FROM edit_attempts"):
        r = json.loads(raw)
        ctx = r.get("context") or {}
        if not ctx.get("aim_uv") or r["piece"] == "unknown":
            continue
        label = store.label(r["attempt_id"])
        if label and label["status"] == "rejected":
            continue
        if label and label["status"] == "relabelled":
            edit = label.get("edit_id")
        elif label and label["status"] == "approved":
            edit = r.get("matched_edit_id")
        elif include_auto and r.get("auto_label_confidence", 0) >= min_confidence:
            edit = r.get("matched_edit_id")
        else:
            continue
        out.append({"piece": canonical(r["piece"]), "aim": tuple(ctx["aim_uv"]), "side": int(ctx.get("side", 1)),
                    "far": bool(ctx.get("far")), "edit": edit, "outcome": r["outcome"],
                    "followed": r.get("followed_suggestion"), "suggested": r.get("suggested_edit_id"),
                    "reviewed": bool(label)})
    return out


def _mirror_map(piece):
    data = json.loads((ROOT / "shared" / "edits.json").read_text(encoding="utf-8"))
    meta = data["pieces"][catalog_key(piece)]
    return {e["id"]: e.get("mirror_of") or e["id"] for e in data.get(meta["list"], [])}


def mirror_key(key, piece):
    ub, vb, side, far = (int(x) for x in key.split(","))
    buckets = cells(piece) * 2
    return f"{buckets - 1 - ub},{vb},{2 - side},{far}"


def blend(policy, samples, piece, alpha=ALPHA):
    """New policy dict (same format as shared/edit-policy*.json) with method/alpha/counts recorded."""
    piece = canonical(piece)
    ids = list(policy["edits"])
    floor = float(policy.get("prior_floor", 0.02))
    mirror = _mirror_map(piece)
    counts = defaultdict(lambda: [0.0] * len(ids))
    used = 0
    for s in samples:
        if s["piece"] != piece or s["outcome"] != "completed" or s["edit"] not in ids:
            continue
        key = situation_key(s["aim"], s["side"], s["far"], cells(piece))
        counts[key][ids.index(s["edit"])] += 0.5
        m = mirror.get(s["edit"], s["edit"])
        counts[mirror_key(key, piece)][ids.index(m) if m in ids else ids.index(s["edit"])] += 0.5
        used += 1
    priors = {}
    for key, row in policy["priors"].items():
        c = counts.get(key, [0.0] * len(ids))
        n = sum(c)
        post = [(alpha * p + k) / (alpha + n) for p, k in zip(row, c)]
        post = [max(v, floor) for v in post]
        total = sum(post)
        priors[key] = [round(v / total, 4) for v in post]
    out = {k: v for k, v in policy.items() if k != "priors"}
    out.update(priors=priors, method="blend", alpha=alpha, examples_used=used,
               situations_with_data=sum(1 for c in counts.values() if sum(c) > 0))
    return out


def evaluate(samples, ranker, piece=None):
    """Scores of a ranker (its policy tables + travel cost) against what reviewed players actually did."""
    ranks, logloss, bins = [], [], defaultdict(lambda: [0, 0.0, 0])
    followed = {"followed": [0, 0], "ignored": [0, 0]}
    for s in samples:
        if piece and s["piece"] != canonical(piece):
            continue
        if s["followed"] is not None:
            bucket = followed["followed" if s["followed"] else "ignored"]
            bucket[0] += 1
            bucket[1] += s["outcome"] == "completed"
        if s["outcome"] != "completed" or not s["edit"]:
            continue
        picks = ranker.rank(s["piece"], s["aim"], s["side"], s["far"])
        ids = [p.id for p in picks]
        ranks.append(ids.index(s["edit"]) + 1 if s["edit"] in ids else None)
        # The ranker's choice distribution: softmax of negative cost (what the guide would show, as probabilities).
        if picks:
            weights = [math.exp(-3.0 * p.cost) for p in picks]
            total = sum(weights)
            probs = {p.id: w / total for p, w in zip(picks, weights)}
            logloss.append(-math.log(max(probs.get(s["edit"], 1e-6), 1e-6)))
            top = max(probs, key=probs.get)
            b = min(9, int(probs[top] * 10))
            bins[b][0] += 1
            bins[b][1] += probs[top]
            bins[b][2] += top == s["edit"]
    n = len(ranks)
    found = [r for r in ranks if r]
    ece = sum(abs(conf / cnt - hit / cnt) * cnt for cnt, conf, hit in bins.values() if cnt) / n if n else None
    rate = lambda b: round(b[1] / b[0], 3) if b[0] else None
    return {
        "examples": n,
        "top1": round(sum(r == 1 for r in found) / n, 3) if n else None,
        "top3": round(sum(r <= 3 for r in found) / n, 3) if n else None,
        "mrr": round(sum(1 / r for r in found) / n, 3) if n else None,
        "not_offered": sum(r is None for r in ranks),
        "log_loss": round(sum(logloss) / len(logloss), 3) if logloss else None,
        "ece": round(ece, 3) if ece is not None else None,
        "completion_when_followed": rate(followed["followed"]),
        "completion_when_ignored": rate(followed["ignored"]),
        "followed_attempts": followed["followed"][0],
        "ignored_attempts": followed["ignored"][0],
    }


def better(candidate, baseline, min_examples=30):
    """Publish rule: enough examples, and higher top-1 without worse top-3 (ties broken by log loss)."""
    if (candidate.get("examples") or 0) < min_examples:
        return False
    if candidate["top1"] != baseline["top1"]:
        return candidate["top1"] > baseline["top1"] and candidate["top3"] >= baseline["top3"]
    return (candidate["log_loss"] or 9) < (baseline["log_loss"] or 9)
