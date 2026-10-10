"""Add candidate edits to shared/edits.json (idempotent): recognised and recorded, never suggested until reviewed.

    python tools/add_candidate_edits.py && python tools/migrate_edit_dictionary.py && python tools/gen_edits.py --check

Each candidate is `suggest:false, confirmed:false` with an explicit unverified validation record, so:
  * the overlay's attempt recorder can match it when a player makes it (EditDictionary.all),
  * the review page can approve or relabel attempts as it,
  * tools/promote_edits.py can verify it from reviewed attempts.
Only then should `suggest` be switched on and Jev priors rebuilt (tools/build_edit_policy.py / build_piece_policy.py).
Tile sets are taken from common competitive edit lists; the review pipeline is what confirms them in game.
Tiles: walls 0..8 row-major from the bottom-left as seen; 2x2 pieces 0 near-left, 1 near-right, 2 far-left, 3 far-right.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = "common competitive edit list (unconfirmed tile set; verify through edit review)"

CANDIDATES = {
    "wall_edits": [
        ("arch", "Arch (bottom two rows)", [0, 1, 2, 3, 4, 5], None, ["enter", "pass_through"], "very_high",
         "Open the bottom two rows: a full-width archway to walk or box through."),
        ("window_tall", "Tall window (centre column, top two)", [4, 7], None, ["peek", "shoot"], "medium",
         "A taller centre window: shoot from standing height with the low row still covering you."),
        ("window_wide", "Wide window (middle row)", [3, 4, 5], None, ["peek", "shoot"], "high",
         "The whole middle row: a wide firing slit across the wall."),
        ("side_door_left", "Side door (left)", [0, 3], "side_door_right", ["enter", "escape"], "medium",
         "Left column, bottom two: a door at the edge of the wall, hugging the corner."),
        ("side_door_right", "Side door (right)", [2, 5], "side_door_left", ["enter", "escape"], "medium",
         "Right column, bottom two: a door at the edge of the wall, hugging the corner."),
        ("crouch_hole", "Crouch hole (bottom middle)", [1], None, ["peek", "shoot"], "low",
         "One bottom-middle tile: a low hole to shoot through while crouched."),
    ],
    "floor_edits": [
        ("floor_three_keep_far_right", "Floor, three tiles (far right kept)", [0, 1, 2], "floor_three_keep_far_left",
         ["shoot_down", "drop"], "high", "Remove three tiles and keep one corner to stand on."),
        ("floor_three_keep_far_left", "Floor, three tiles (far left kept)", [0, 1, 3], "floor_three_keep_far_right",
         ["shoot_down", "drop"], "high", "Remove three tiles and keep one corner to stand on."),
        ("floor_three_keep_near_right", "Floor, three tiles (near right kept)", [0, 2, 3], "floor_three_keep_near_left",
         ["shoot_down", "drop"], "high", "Remove three tiles and keep one corner to stand on."),
        ("floor_three_keep_near_left", "Floor, three tiles (near left kept)", [1, 2, 3], "floor_three_keep_near_right",
         ["shoot_down", "drop"], "high", "Remove three tiles and keep one corner to stand on."),
        ("floor_diagonal_a", "Floor, diagonal (near left + far right)", [0, 3], "floor_diagonal_b",
         ["shoot_down"], "medium", "Two opposite corners: a diagonal opening."),
        ("floor_diagonal_b", "Floor, diagonal (near right + far left)", [1, 2], "floor_diagonal_a",
         ["shoot_down"], "medium", "Two opposite corners: a diagonal opening."),
    ],
    "roof_edits": [
        ("roof_three_keep_far_right", "Cone, three squares (far right kept)", [0, 1, 2], "roof_three_keep_far_left",
         ["protect", "peek"], "medium", "Three cone squares: a steep peak toward the kept corner."),
        ("roof_three_keep_far_left", "Cone, three squares (far left kept)", [0, 1, 3], "roof_three_keep_far_right",
         ["protect", "peek"], "medium", "Three cone squares: a steep peak toward the kept corner."),
        ("roof_three_keep_near_right", "Cone, three squares (near right kept)", [0, 2, 3], "roof_three_keep_near_left",
         ["protect", "peek"], "medium", "Three cone squares: a steep peak toward the kept corner."),
        ("roof_three_keep_near_left", "Cone, three squares (near left kept)", [1, 2, 3], "roof_three_keep_near_right",
         ["protect", "peek"], "medium", "Three cone squares: a steep peak toward the kept corner."),
    ],
}


def main():
    path = ROOT / "shared/edits.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    added = []
    for listname, entries in CANDIDATES.items():
        existing = {e["id"] for e in data.get(listname, [])}
        masks = {frozenset(e["tiles"]) for e in data.get(listname, [])}
        for eid, name, tiles, mirror, purpose, exposure, when in entries:
            if eid in existing or frozenset(tiles) in masks:
                continue
            data[listname].append({
                "id": eid, "name": name, "tiles": tiles, "kind": "wall" if listname == "wall_edits" else "grid",
                "mirror_of": mirror, "suggest": False, "confirmed": False, "purpose": purpose, "exposure": exposure,
                "difficulty": 2, "when_to_use": when, "source": SOURCE,
                "validation": {"status": "unverified", "game_version": None, "evidence": [], "result_confirmed": False,
                               "reason": "Candidate from edit lists; confirm through recorded and reviewed attempts."},
            })
            added.append(eid)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # Point the coverage ledger's masks at the new edits.
    ledger_path = ROOT / "shared/edit-coverage.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for piece, meta in data["pieces"].items():
        if piece not in ledger["pieces"]:
            continue
        for e in data[meta["list"]]:
            slot = ledger["pieces"][piece][sum(1 << t for t in e["tiles"])]
            if e["id"] not in slot["edit_ids"]:
                slot["edit_ids"].append(e["id"])
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print("added:", added or "nothing (already present)")


if __name__ == "__main__":
    main()
