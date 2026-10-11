"""Locked edit-guide files (player 2026-10-11: "fix this immediately and lock the files").

    python tools/check_locked.py            # fail if a locked file differs from shared/locked-files.json
    python tools/check_locked.py --update   # record the current contents (only with the player's say-so)

The Jev edit guide (in-map EditGuide + the companion overlay's detection, ranking and drawing) is known good. Any change
to these files needs the player's explicit approval first. .githooks/pre-commit runs this check.
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "shared" / "locked-files.json"
LOCKED = [
    "verse/KeystrokeTrainer/EditGuide.verse", "verse/KeystrokeTrainer/EditPolicy.verse",
    "verse/KeystrokeTrainer/EditPolicyPieces.verse", "verse/KeystrokeTrainer/EditIntent.verse",
    "verse/KeystrokeTrainer/EditCatalog.verse", "verse/KeystrokeTrainer/EditPatterns.verse",
    "verse/KeystrokeTrainer/EditTargets.verse", "verse/KeystrokeTrainer/EditObservation.verse",
    "companion/keystroke_lab/edit_window.py", "companion/keystroke_lab/edit_observation.py",
    "companion/keystroke_lab/edit_advisor.py", "companion/keystroke_lab/edit_ranker.py",
    "companion/keystroke_lab/edit_geometry.py", "companion/keystroke_lab/piece_observation.py",
    "companion/keystroke_lab/edit_dictionary.py", "companion/keystroke_lab/guide_visuals.py",
    "companion/keystroke_lab/guide_layers.py", "companion/keystroke_lab/autostart.py",
    "companion/autostart.pyw", "shared/edit-policy.json",
    "shared/edits.json", "shared/edit-intent.json",
]


def digest(path):
    data = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main():
    if "--update" in sys.argv:
        MANIFEST.write_text(json.dumps({p: digest(p) for p in LOCKED if (ROOT / p).exists()}, indent=2) + "\n")
        print("locked", len(LOCKED), "files")
        return 0
    want = json.loads(MANIFEST.read_text())
    changed = [p for p, h in want.items() if not (ROOT / p).exists() or digest(p) != h]
    if changed:
        print("LOCKED edit-guide files changed (need the player's approval):\n  " + "\n  ".join(changed))
        return 1
    print("locked files unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
