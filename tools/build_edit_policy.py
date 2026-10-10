"""Build the edit guide's prior table with Jev, offline, so in-game advice is consistent.

    python tools/build_edit_policy.py [--dry-run] [--no-audit]
    python tools/build_edit_policy.py --extend      # offline: add placeholder columns for new library edits

A published island cannot call an AI, so nothing here runs in the game. Instead Jev (calibrated probabilities, no
free text) scores every situation the guide can be in against the edit library (shared/edits.json) and the result
is baked into verse/KeystrokeTrainer/EditPolicy.verse as a fixed table. The map then picks
    argmin( crosshair travel cost  -  PRIOR_WEIGHT * ln(prior) )
so geometry (how far the crosshair must move) and judgement (which edit suits this situation) both count and the
same situation always gives the same answer.

Situation = where the crosshair is on the wall (6 x 6 buckets of the 3 x 3 tile grid), which third of the wall the
player stands in (left, centre, right) and whether they are near or far from it. Features come from what the map can
measure: the player's position vector, the crosshair ray and the face the build ghost snaps to.

Bias control: each result is averaged with its left/right mirror, so the table is exactly symmetric and cannot
favour a side. An audit re-asks a sample of situations and reports how often Jev repeats itself.
"""
import argparse
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "companion"))

from gen_edits import mirror_tiles, suggested  # noqa: E402
from keystroke_lab.jev_client import JevClient, choice_question  # noqa: E402

EDITS = ROOT / "shared" / "edits.json"
OUT_JSON = ROOT / "shared" / "edit-policy.json"
OUT_VERSE = ROOT / "verse" / "KeystrokeTrainer" / "EditPolicy.verse"
BUCKETS = 6          # aim position buckets per axis
SIDES = ("left", "centre", "right")
BATCH = 8
PRIOR_FLOOR = 0.02   # a prior is never exactly zero, so no shape is ever ruled out by the table alone

INSTRUCTIONS = ("A Fortnite player stands {side} of a built wall and is {dist} it. Their crosshair is on the wall "
                "{u:.2f} tiles from its left edge and {v:.2f} tiles up from its bottom (the wall is 3 x 3 tiles). "
                "Which single edit would strong players most commonly make with the crosshair exactly here? "
                "Where the crosshair is matters most: the edit's first tile should be at or next to the crosshair so it "
                "barely moves. The side the player stands on and the distance matter only slightly.")


def mirror_index(edits):
    ids = [e["id"] for e in edits]
    out = []
    for e in edits:
        mirrored = set(mirror_tiles(e["tiles"]))
        if mirrored == set(e["tiles"]):
            out.append(ids.index(e["id"]))
        else:
            out.append(ids.index(e["mirror_of"]))
    return out


def describe(e):
    return (f"{e['name']}: select tiles {e['tiles']} starting at tile {e['tiles'][0]}; purpose {', '.join(e['purpose'])}; "
            f"exposure {e['exposure']}; {e['cover_left']} of 9 tiles stay.")


def situations():
    out = []
    for ub in range(BUCKETS):
        for vb in range(BUCKETS):
            for side in range(3):
                for far in range(2):
                    out.append((ub, vb, side, far))
    return out


def key(s):
    return ",".join(str(x) for x in s)


def ask(jev, edits, batch):
    options = {e["id"]: describe(e) for e in edits}
    questions, texts = {}, {}
    for i, (ub, vb, side, far) in enumerate(batch):
        texts[f"s{i}"] = INSTRUCTIONS.format(side=SIDES[side], dist="far from" if far else "close to",
                                             u=(ub + 0.5) * 3.0 / BUCKETS, v=(vb + 0.5) * 3.0 / BUCKETS)
        questions[f"s{i}"] = choice_question(texts[f"s{i}"], options)
    answers = jev.decide({"task": "choose a wall edit", "library_size": len(edits)}, questions)
    if not answers:
        return None
    return [answers.get(f"s{i}", {}).get("probabilities") for i in range(len(batch))]


def normalise(probs, ids):
    vec = [max(float(probs.get(i, 0.0)), 0.0) for i in ids]
    total = sum(vec) or 1.0
    return [v / total for v in vec]


def symmetrise(raw, edits, mirror):
    """Average each situation with its mirror image (aim column flipped, side flipped, edit swapped)."""
    out = {}
    for (ub, vb, side, far), vec in raw.items():
        twin = raw.get((BUCKETS - 1 - ub, vb, 2 - side, far))
        merged = [0.5 * (vec[j] + (twin[mirror[j]] if twin else vec[j])) for j in range(len(vec))]
        total = sum(merged) or 1.0
        merged = [max(v / total, PRIOR_FLOOR) for v in merged]
        total = sum(merged)
        out[(ub, vb, side, far)] = [v / total for v in merged]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--personal", action="store_true", help="blend in shared/edit-policy-personal.json (from `keystroke_lab personalize`)")
    ap.add_argument("--regen-verse", action="store_true", help="rewrite EditPolicy.verse from the saved edit-policy.json, no Jev calls")
    ap.add_argument("--extend", action="store_true",
                    help="no Jev calls: give suggested edits missing from edit-policy.json a placeholder column, then rewrite the Verse")
    args = ap.parse_args()
    if args.extend:
        saved = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        ids = [e["id"] for e in suggested(json.loads(EDITS.read_text(encoding="utf-8")))]
        saved = extend(saved, ids)
        OUT_JSON.write_text(json.dumps(saved, indent=1), encoding="utf-8")
        write_verse(ids, {tuple(int(x) for x in k.split(",")): v for k, v in saved["priors"].items()})
        print("unscored (placeholder = row median, rerun with Jev to score):", ", ".join(saved["unscored"]) or "none")
        return 0
    if args.regen_verse:
        saved = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        policy = {tuple(int(x) for x in k.split(",")): v for k, v in saved["priors"].items()}
        if args.personal:
            from keystroke_lab import personalize
            personal = json.loads(personalize.PERSONAL_JSON.read_text(encoding="utf-8"))["factors"]
            policy = personalize.apply_to_policy(policy, saved["edits"], personal)
            print("blended personal factors:", {k: v for k, v in personal.items() if v != 1.0} or "none differ from 1.0")
        write_verse(saved["edits"], policy)
        print("rewrote", OUT_VERSE.name)
        return 0
    data = json.loads(EDITS.read_text(encoding="utf-8"))
    edits = suggested(data)
    ids = [e["id"] for e in edits]
    mirror = mirror_index(edits)
    todo = situations()
    print(f"{len(edits)} suggested edits, {len(todo)} situations, batch {BATCH}: about {-(-len(todo) // BATCH)} Jev calls")
    if args.dry_run:
        return 0
    jev = JevClient(max_calls=200, broker=False, domain="offline_policy")   # offline batch: not the live 30 s broker
    if not jev.available:
        print("JEV_API_KEY is not set (../.env)")
        return 2
    raw, failed = {}, 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        answers = ask(jev, edits, batch)
        if answers is None:
            failed += len(batch)
            continue
        for s, probs in zip(batch, answers):
            if probs:
                raw[s] = normalise(probs, ids)
    if failed or len(raw) != len(todo):
        print(f"incomplete: {len(raw)}/{len(todo)} situations answered; not writing the policy")
        return 1
    policy = symmetrise(raw, edits, mirror)
    audit = {}
    if not args.no_audit:
        random.seed(7)
        sample = random.sample(todo, 16)
        again = ask(jev, edits, sample) or []
        same, drift = 0, 0.0
        for s, probs in zip(sample, again):
            if not probs:
                continue
            vec = normalise(probs, ids)
            same += int(max(range(len(ids)), key=lambda j: vec[j]) == max(range(len(ids)), key=lambda j: raw[s][j]))
            drift = max(drift, max(abs(vec[j] - raw[s][j]) for j in range(len(ids))))
        audit = {"resampled": len(sample), "same_top_choice": same, "max_probability_drift": round(drift, 3)}
        print("consistency audit:", audit)
    table = {key(s): [round(p, 4) for p in v] for s, v in policy.items()}
    OUT_JSON.write_text(json.dumps({"edits": ids, "buckets": BUCKETS, "sides": SIDES, "prior_floor": PRIOR_FLOOR,
                                    "jev_tokens": jev.tokens, "jev_calls": jev.calls, "audit": audit,
                                    "priors": table}, indent=1), encoding="utf-8")
    write_verse(ids, policy)
    print(f"wrote {OUT_JSON.name} and {OUT_VERSE.name}; Jev calls {jev.calls}, tokens {jev.tokens}")
    return 0


def extend(saved, ids):
    """Reorder the saved table to the library's suggested order. An edit Jev has not scored yet gets the median of
    its situation's row: no opinion either way, so crosshair travel decides. Listed under "unscored"."""
    old = saved["edits"]
    if set(old) - set(ids):
        raise SystemExit(f"edit-policy.json scores edits no longer suggested: {sorted(set(old) - set(ids))}; rerun with Jev")
    new = [i for i in ids if i not in old]
    priors = {}
    for k, row in saved["priors"].items():
        median = sorted(row)[len(row) // 2]
        vec = [row[old.index(i)] if i in old else median for i in ids]
        total = sum(vec) or 1.0
        priors[k] = [round(v / total, 4) for v in vec]
    unscored = [i for i in dict.fromkeys(saved.get("unscored", []) + new) if i in ids]
    return dict(saved, edits=ids, priors=priors, unscored=unscored)


def write_verse(ids, policy):
    """Flat int table, per-mille, indexed ((ub * 6 + vb) * 3 + side) * 2 + far, then edit index."""
    lines = [
        "# GENERATED by tools/build_edit_policy.py from Jev's scores over shared/edits.json. Do not edit by hand.",
        "# KTEditPriors holds, per situation, one value (1..1000 = prior x 1000) for each edit in KTWallEdits order.",
        f"# Situation index = ((AimColBucket * {BUCKETS} + AimRowBucket) * 3 + Side) * 2 + Far.",
        "",
        f"KTEditCount<public>:int = {len(ids)}",
        f"KTEditBuckets<public>:int = {BUCKETS}",
        "",
        "KTEditPriors<public>:[]int = array{",
    ]
    rows = []
    for ub in range(BUCKETS):
        for vb in range(BUCKETS):
            for side in range(3):
                for far in range(2):
                    vec = policy[(ub, vb, side, far)]
                    rows.append("    " + ", ".join(str(max(1, round(p * 1000))) for p in vec))
    lines.append((","+chr(10)).join(rows))   # no trailing comma: Verse rejects it before the closing brace
    lines.append("}")
    OUT_VERSE.write_text(chr(10).join(lines) + chr(10), encoding="utf-8", newline=chr(10))


if __name__ == "__main__":
    sys.exit(main())
