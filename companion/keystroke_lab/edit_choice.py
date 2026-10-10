"""Which wall edit the companion's edit reference shows, and the player's own edits kept as examples.

    python -m keystroke_lab edit-examples          # what you have edited, and selections the library lacks

Crosshair travel alone cannot tell a window from an arch: from a low centre aim both start on the same tiles. So the
choice uses, in order:
  1. the tiles already selected on screen: only edits containing them stay possible;
  2. your examples: edits you confirmed with the crosshair in the same part of the wall (EXAMPLE_MIN or more, one
     edit at least EXAMPLE_SHARE of them);
  3. the ranker (edit_ranker.py, the port of the in-game guide), keeping the current pick while it stays close.
Examples are written by the edit window when an observed selection leaves edit mode (companion/data, not committed).
Pure logic apart from the examples file; no screen, game or network access here.
"""
import collections
import json
import math
import pathlib
import time

EXAMPLES_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "edit-examples.jsonl"
EXAMPLE_MIN = 3
EXAMPLE_SHARE = 0.6
KEEP_MARGIN = 0.25     # keep the current pick while its cost is within this of the best (as EditGuide.verse)


def wall_library(edits_json=pathlib.Path(__file__).resolve().parents[2] / "shared" / "edits.json"):
    """Every wall edit in the library (suggested or not), id -> tiles, for naming recorded selections."""
    return {e["id"]: e["tiles"] for e in json.loads(pathlib.Path(edits_json).read_text(encoding="utf-8"))["wall_edits"]}


def bucket(aim):
    """Half-tile cell of the 3 x 3 wall the crosshair is in (6 x 6, the same buckets as the prior table)."""
    return tuple(max(0, min(5, math.floor(v * 2))) for v in aim)


class Examples:
    def __init__(self, path=EXAMPLES_FILE, library=None):
        self.path = pathlib.Path(path)
        self.library = wall_library() if library is None else library     # id -> tiles, to name a recorded mask
        self.records = []
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and len(r.get("aim", ())) == 2 and r.get("tiles"):
                    self.records.append(r)

    def name(self, tiles):
        wanted = set(tiles)
        return next((i for i, t in self.library.items() if set(t) == wanted), None)

    def add(self, aim, tiles, now=None):
        """Record one finished edit: the aim when edit mode opened and the final selected tiles."""
        record = {"ts": round(now if now is not None else time.time(), 3), "aim": [round(v, 3) for v in aim],
                  "tiles": sorted(tiles), "edit": self.name(tiles)}
        self.records.append(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def habitual(self, aim, allowed=None):
        """The edit you usually make from this part of the wall, or None without enough agreeing examples."""
        here = [r["edit"] for r in self.records if bucket(r["aim"]) == bucket(aim)]
        if len(here) < EXAMPLE_MIN:
            return None
        edit, n = collections.Counter(here).most_common(1)[0]
        if edit is None or n / len(here) < EXAMPLE_SHARE or (allowed is not None and edit not in allowed):
            return None
        return edit

    def summary(self):
        """[(tiles, edit or None, count)] most common first."""
        counts = collections.Counter((tuple(r["tiles"]), r["edit"]) for r in self.records)
        return [(t, e, n) for (t, e), n in counts.most_common()]


def choose_edit(aim, selected, ranker, examples=None, current=None):
    """(edit id or None, source). source: selection | examples | ranker | unknown_selection | none."""
    picks = ranker.rank("wall", tuple(aim), 1, False)
    library = {e["id"]: e["tiles"] for e in ranker.library.get("wall", [])}
    if selected:
        fits = [i for i, t in library.items() if set(selected) <= set(t)]
        if not fits:
            return None, "unknown_selection"
        if current in fits:
            return current, "selection"
        usual = examples.habitual(aim, fits) if examples else None
        if usual:
            return usual, "examples"
        exact = [i for i in fits if set(library[i]) == set(selected)]
        if exact:
            return exact[0], "selection"
        cost = {p.id: p.cost for p in picks}
        return min(fits, key=lambda i: (len(library[i]), cost.get(i, 99.0))), "selection"
    usual = examples.habitual(aim) if examples else None
    if usual:
        return usual, "examples"
    if not picks:
        return None, "none"
    best = picks[0]
    for p in picks:
        if p.id == current and p.cost <= best.cost + KEEP_MARGIN:
            return current, "ranker"
    return best.id, "ranker"


def run(path=None):
    path = path or EXAMPLES_FILE
    ex = Examples(path)
    if not ex.records:
        print("no edit examples yet:", path)
        print("they are recorded by the edit window (`keys` starts it) each time an observed selection leaves edit mode")
        return 1
    print(f"{len(ex.records)} edits recorded in {path}")
    for tiles, edit, n in ex.summary():
        print(f"  {n:>4}  tiles {list(tiles)!s:<22}{edit or 'NOT IN LIBRARY: add it to shared/edits.json'}")
    return 0
