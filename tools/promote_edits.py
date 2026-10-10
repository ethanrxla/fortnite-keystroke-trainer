"""Promote catalogue edits to game-verified from reviewed attempts (Phase 3 of the edit-data plan).

    python tools/promote_edits.py --game-version 42.10            # dry run: what would change
    python tools/promote_edits.py --game-version 42.10 --apply    # write shared/edits.json + ledger, regenerate Verse

Rule: an edit becomes game_verified after MIN_APPROVED approved attempts across MIN_SESSIONS separate sessions, where
an attempt counts for edit X if the reviewer approved it with matched edit X, or relabelled it as X. An edit with more
rejected than approved attempts is reported, never auto-invalidated (that stays a manual validate_edit.py --invalid).
Evidence recorded: the attempt ids. Reviewer: the person who labelled them (labels.reviewer).
"""
import argparse
import json
import pathlib
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from keystroke_lab.store import Store  # noqa: E402

MIN_APPROVED = 3
MIN_SESSIONS = 2


def tally(store):
    """{edit_id: {"approved": [(attempt_id, session)], "rejected": n, "reviewers": set()}} from the newest label of each attempt."""
    out = defaultdict(lambda: {"approved": [], "rejected": 0, "reviewers": set()})
    for attempt_id, session, matched in store.rows("SELECT attempt_id, session_id, matched FROM edit_attempts"):
        label = store.label(attempt_id)
        if not label:
            continue
        if label["status"] == "approved" and matched:
            out[matched]["approved"].append((attempt_id, session))
            out[matched]["reviewers"].add(label["reviewer"])
        elif label["status"] == "relabelled" and label.get("edit_id"):
            out[label["edit_id"]]["approved"].append((attempt_id, session))
            out[label["edit_id"]]["reviewers"].add(label["reviewer"])
        elif label["status"] == "rejected" and matched:
            out[matched]["rejected"] += 1
    return out


def eligible(entry):
    return len(entry["approved"]) >= MIN_APPROVED and len({s for _, s in entry["approved"]}) >= MIN_SESSIONS


def promote(data, ledger, counts, game_version, now=None):
    """Mutates data/ledger in place; returns the ids promoted."""
    now = now or datetime.now(timezone.utc).isoformat()
    promoted = []
    for piece, meta in data["pieces"].items():
        for e in data.get(meta["list"], []):
            entry = counts.get(e["id"])
            if not entry or not eligible(entry) or (e.get("validation") or {}).get("status") == "game_verified":
                continue
            if piece == "stairs" and not (e.get("gesture") or {}).get("routes"):
                continue                       # ramp edits need a recorded gesture first (validate_edit.py rule)
            e["validation"] = {"status": "game_verified", "game_version": game_version,
                               "evidence": [f"attempt:{a}" for a, _ in entry["approved"]], "result_confirmed": True,
                               "reviewer": ",".join(sorted(r or "local" for r in entry["reviewers"])), "recorded_at": now,
                               "method": f"reviewed attempts >= {MIN_APPROVED} across >= {MIN_SESSIONS} sessions"}
            if ledger and piece in ledger.get("pieces", {}) and e.get("tiles"):
                mask = sum(1 << t for t in e["tiles"])
                slot = ledger["pieces"][piece][mask]
                slot.update(status="valid", validation=e["validation"])
            promoted.append(e["id"])
    return promoted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-version", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    counts = tally(Store())
    for edit_id, entry in sorted(counts.items()):
        sessions = len({s for _, s in entry["approved"]})
        flag = "READY" if eligible(entry) else "     "
        warn = "  more rejected than approved" if entry["rejected"] > len(entry["approved"]) else ""
        print(f"{flag} {edit_id:24} approved {len(entry['approved'])} in {sessions} sessions, rejected {entry['rejected']}{warn}")
    edits_path, ledger_path = ROOT / "shared/edits.json", ROOT / "shared/edit-coverage.json"
    data = json.loads(edits_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else None
    promoted = promote(data, ledger, counts, args.game_version)
    print("would promote:" if not args.apply else "promoted:", promoted or "nothing")
    if args.apply and promoted:
        edits_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if ledger:
            ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "tools/gen_edits.py")], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
