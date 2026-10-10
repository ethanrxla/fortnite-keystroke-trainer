"""Jev prior tables for floors, roofs/cones and stairs (the 2 x 2 pieces), baked into EditPolicyPieces.verse.

    python tools/build_piece_policy.py [--piece floor|roof|stairs ...] [--dry-run] [--no-audit]

Same method as build_edit_policy.py (walls): Jev scores every situation against that piece's edit library, each result is
averaged with its left/right mirror, and the map ranks  crosshair travel - weight * ln(prior).  Situation = where the
crosshair is on the piece (4 x 4 buckets over the 2 x 2 grid), which third of the piece the player stands in, near or far.

Jev's intake (what it is told, per question): the piece (floor / roof-cone / stairs), the 2 x 2 grid with tile numbering
(0 near-left .. 3 far-right as the player sees it), the crosshair position in tiles, the player's side and distance, and
the full list of confirmed edits for that piece with tiles, purpose, exposure and cover. Nothing else, so the answer
cannot depend on text the map does not measure. A piece with no suggested edits (stairs today) is skipped and keeps an
empty table: the guide then shows the grid without a recommendation instead of inventing one.
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
OUT_VERSE = ROOT / "verse" / "KeystrokeTrainer" / "EditPolicyPieces.verse"
COLS = 2
BUCKETS = 4
BATCH = 8
PRIOR_FLOOR = 0.02
SIDES = ("left", "centre", "right")
NAMES = {"floor": ("floor", "Floor", "KTFloor"), "roof": ("roof or cone", "Roof", "KTRoof"), "stairs": ("stairs or ramp", "Stairs", "KTStairs")}

INSTRUCTIONS = ("A Fortnite player stands {side} of a built {noun} and is {dist} it. Their crosshair is {u:.2f} tiles from its "
                "left edge and {v:.2f} tiles away from its near edge (the piece is 2 x 2 tiles, tile 0 near-left, 1 near-right, "
                "2 far-left, 3 far-right). Which single edit would strong players most commonly make with the crosshair exactly "
                "here? The edit's first tile should be at or next to the crosshair so it barely moves. The side the player "
                "stands on and the distance matter only slightly.")


def policy_json(piece):
    return ROOT / "shared" / f"edit-policy-{piece}.json"


def situations():
    return [(ub, vb, side, far) for ub in range(BUCKETS) for vb in range(BUCKETS) for side in range(3) for far in range(2)]


def describe(e):
    return (f"{e['name']}: select tiles {e['tiles']} starting at tile {e['tiles'][0]}; purpose {', '.join(e['purpose'])}; "
            f"exposure {e['exposure']}; {e['cover_left']} of 4 tiles stay.")


def mirror_index(edits):
    ids = [e["id"] for e in edits]
    return [ids.index(e["id"]) if set(mirror_tiles(e["tiles"], COLS)) == set(e["tiles"]) else ids.index(e["mirror_of"]) for e in edits]


def ask(jev, piece, edits, batch):
    options = {e["id"]: describe(e) for e in edits}
    questions = {}
    for i, (ub, vb, side, far) in enumerate(batch):
        text = INSTRUCTIONS.format(side=SIDES[side], noun=NAMES[piece][0], dist="far from" if far else "close to",
                                   u=(ub + 0.5) * COLS / BUCKETS, v=(vb + 0.5) * COLS / BUCKETS)
        questions[f"s{i}"] = choice_question(text, options)
    answers = jev.decide({"task": f"choose a {piece} edit", "piece": piece, "grid": "2x2", "library_size": len(edits)}, questions)
    if not answers:
        return None
    return [answers.get(f"s{i}", {}).get("probabilities") for i in range(len(batch))]


def normalise(probs, ids):
    vec = [max(float(probs.get(i, 0.0)), 0.0) for i in ids]
    total = sum(vec) or 1.0
    return [v / total for v in vec]


def symmetrise(raw, mirror):
    out = {}
    for (ub, vb, side, far), vec in raw.items():
        twin = raw.get((BUCKETS - 1 - ub, vb, 2 - side, far))
        merged = [0.5 * (vec[j] + (twin[mirror[j]] if twin else vec[j])) for j in range(len(vec))]
        total = sum(merged) or 1.0
        merged = [max(v / total, PRIOR_FLOOR) for v in merged]
        total = sum(merged)
        out[(ub, vb, side, far)] = [v / total for v in merged]
    return out


def build(jev, piece, edits, audit):
    ids = [e["id"] for e in edits]
    todo = situations()
    raw = {}
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        answers = ask(jev, piece, edits, batch)
        if answers is None:
            return None
        for s, probs in zip(batch, answers):
            if probs:
                raw[s] = normalise(probs, ids)
    if len(raw) != len(todo):
        print(f"{piece}: incomplete, {len(raw)}/{len(todo)} answered")
        return None
    report = {}
    if audit:
        random.seed(7)
        sample = random.sample(todo, 16)
        again = ask(jev, piece, edits, sample) or []
        same = 0
        for s, probs in zip(sample, again):
            if probs:
                vec = normalise(probs, ids)
                same += int(max(range(len(ids)), key=lambda j: vec[j]) == max(range(len(ids)), key=lambda j: raw[s][j]))
        report = {"resampled": len(sample), "same_top_choice": same}
        print(f"{piece} consistency audit:", report)
    policy = symmetrise(raw, mirror_index(edits))
    table = {",".join(map(str, s)): [round(p, 4) for p in v] for s, v in policy.items()}
    policy_json(piece).write_text(json.dumps({"edits": ids, "buckets": BUCKETS, "prior_floor": PRIOR_FLOOR, "audit": report, "priors": table}, indent=1), encoding="utf-8")
    return policy


def load_saved(piece):
    path = policy_json(piece)
    if not path.exists():
        return [], {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    return saved["edits"], {tuple(int(x) for x in k.split(",")): v for k, v in saved["priors"].items()}


def write_verse():
    lines = ["# GENERATED by tools/build_piece_policy.py from Jev's scores over shared/edits.json. Do not edit by hand.",
             "# Per piece: priors per situation (1..1000 = prior x 1000), one value per edit in that piece's catalog order.",
             f"# Situation index = ((AimColBucket * {BUCKETS} + AimRowBucket) * 3 + Side) * 2 + Far. A piece with no table has no recommendation.",
             ""]
    for piece, (_, _, prefix) in NAMES.items():
        ids, policy = load_saved(piece)
        lines.append(f"{prefix}Count<public>:int = {len(ids)}")
        if not ids:
            lines += [f"{prefix}Priors<public>:[]int = array{{}}", ""]
            continue
        rows = []
        for s in situations():
            rows.append("    " + ", ".join(str(max(1, round(p * 1000))) for p in policy[s]))
        lines += [f"{prefix}Priors<public>:[]int = array{{", (",\n").join(rows), "}", ""]
    lines += ["KTPiecePrior<public>(Kind:string, Sit:int, J:int)<transacts>:float =",
              '    if (Kind = "floor"):',
              "        if (V := KTFloorPriors[Sit * KTFloorCount + J]) then V * 0.001 else 0.1",
              '    else if (Kind = "roof"):',
              "        if (V := KTRoofPriors[Sit * KTRoofCount + J]) then V * 0.001 else 0.1",
              '    else if (Kind = "stairs"):',
              "        if (V := KTStairsPriors[Sit * KTStairsCount + J]) then V * 0.001 else 0.1",
              "    else:",
              "        0.1", ""]
    OUT_VERSE.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--piece", action="append", choices=list(NAMES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--regen-verse", action="store_true", help="rewrite EditPolicyPieces.verse from the saved JSON, no Jev calls")
    args = ap.parse_args()
    data = json.loads(EDITS.read_text(encoding="utf-8"))
    if not args.regen_verse:
        pieces = args.piece or list(NAMES)
        jev = JevClient(max_calls=120, broker=False, domain="offline_policy")   # offline batch: not the live 30 s broker
        for piece in pieces:
            edits = suggested(data, piece)
            if not edits:
                print(f"{piece}: no confirmed edits, skipped (no recommendation will be shown)")
                continue
            print(f"{piece}: {len(edits)} edits, {len(situations())} situations, about {-(-len(situations()) // BATCH)} Jev calls")
            if args.dry_run:
                continue
            if not jev.available:
                print("JEV_API_KEY is not set (../.env)")
                return 2
            if build(jev, piece, edits, not args.no_audit) is None:
                print(f"{piece}: failed, table not written")
                return 1
        if not args.dry_run:
            print(f"Jev calls {jev.calls}, tokens {jev.tokens}")
    if not args.dry_run:
        write_verse()
        print("wrote", OUT_VERSE.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
