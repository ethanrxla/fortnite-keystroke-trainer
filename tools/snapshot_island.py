"""Mirror the UEFN island into this repo so git tracks the level and its assets.

UEFN keeps the island in `Documents/Fortnite Projects/MyProject` and versions it with its own
`.lore` store. Git lives here in the kit, so before committing level work run:

    python tools/snapshot_island.py            # copy changed files, delete removed ones
    python tools/snapshot_island.py --dry-run  # list what would change

Save All in UEFN first; unsaved actors are not on disk. The copy is one-way (island -> repo).
To restore, copy `island/MyProject/Content` back while UEFN is closed.
"""
import argparse
import os
import shutil
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("KT_ISLAND", Path.home() / "OneDrive/Documents/Fortnite Projects/MyProject"))
DST = KIT / "island" / "MyProject"
SKIP_DIRS = {".lore", "Binaries", "DerivedDataCache", "Intermediate", "Saved", ".vs", ".vscode"}


def wanted(rel: Path) -> bool:
    return not any(part in SKIP_DIRS for part in rel.parts)


def files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if wanted(rel):
                yield rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not (SRC / "MyProject.uefnproject").exists():
        raise SystemExit(f"island not found at {SRC} (set KT_ISLAND)")
    src = set(files(SRC))
    dst = set(files(DST)) if DST.exists() else set()
    copied = removed = 0
    for rel in sorted(src):
        s, d = SRC / rel, DST / rel
        if d.exists() and d.stat().st_size == s.stat().st_size and d.stat().st_mtime >= s.stat().st_mtime:
            continue
        copied += 1
        if a.dry_run:
            print("copy", rel)
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
    for rel in sorted(dst - src):
        removed += 1
        print("remove", rel)
        if not a.dry_run:
            (DST / rel).unlink()
    print(f"{'would copy' if a.dry_run else 'copied'} {copied}, {'would remove' if a.dry_run else 'removed'} {removed}, tracked {len(src)}")


if __name__ == "__main__":
    main()
