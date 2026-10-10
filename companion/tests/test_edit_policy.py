"""The edit guide's recommendation is a pure function of (aim point, side, distance) over the edit library and Jev's
prior table. These tests port the Verse ranking (EditGuide.verse KTRankEdits) to Python and check the properties the
player asked for: consistent, left/right unbiased, never a disabled edit, and sane about where the crosshair is."""
import json
import math
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from gen_edits import mirror_tiles, suggested, validate  # noqa: E402

DATA = json.loads((ROOT / "shared" / "edits.json").read_text(encoding="utf-8"))
POLICY = json.loads((ROOT / "shared" / "edit-policy.json").read_text(encoding="utf-8"))
EDITS = suggested(DATA)
WEIGHT = 0.3


def centre(t):
    return (t % 3 + 0.5, t // 3 + 0.5)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def approach(aim, tiles):
    return dist(aim, centre(tiles[0]))


def drag(tiles):
    return sum(dist(centre(a), centre(b)) for a, b in zip(tiles, tiles[1:]))


def rank_cost(aim, tiles):
    return approach(aim, tiles) + 0.15 * drag(tiles)


def situation(aim, side, far):
    clamp = lambda f: max(0, min(5, f))
    return ((clamp(math.floor(aim[0] * 2)) * 6 + clamp(math.floor(aim[1] * 2))) * 3 + side) * 2 + int(far)


def prior(sit, j):
    ub, rest = divmod(sit, 36)
    vb, rest = divmod(rest, 6)
    side, far = divmod(rest, 2)
    return POLICY["priors"][f"{ub},{vb},{side},{far}"][j]


def shape_side(tiles):
    """-1 left, 0 centre, 1 right: mean column of the tiles (matches KTShapeSide in EditGuide.verse)."""
    mean = sum(t % 3 for t in tiles) / len(tiles)
    return -1 if mean < 0.8 else (1 if mean > 1.2 else 0)


def aim_side(aim):
    """Which half of the wall the crosshair is on, with a dead band in the middle (KTAimSide)."""
    return -1 if aim[0] < 1.35 else (1 if aim[0] > 1.65 else 0)


def rank(aim, side, far):
    sit = situation(aim, side, far)
    pmax = max(prior(sit, j) for j in range(len(EDITS)))
    out = []
    for j, e in enumerate(EDITS):
        if shape_side(e["tiles"]) and aim_side(aim) and shape_side(e["tiles"]) != aim_side(aim):
            continue        # never offer an edit on the opposite side of the wall from where the crosshair is
        penalty = WEIGHT * math.log(pmax / max(prior(sit, j), 0.001))
        orders = [e["tiles"], e["tiles"][::-1]]
        mirrored = mirror_tiles(e["tiles"])
        if set(mirrored) == set(e["tiles"]):
            orders += [mirrored, mirrored[::-1]]      # KTMirrored: symmetric shapes may be dragged mirrored too
        cost = min(rank_cost(aim, o) for o in orders) + penalty
        out.append((cost, e["id"]))
    return sorted(out)


def mirror_id(edit_id):
    e = next(x for x in EDITS if x["id"] == edit_id)
    if set(mirror_tiles(e["tiles"])) == set(e["tiles"]):
        return edit_id
    return e["mirror_of"]


class EditPolicyTests(unittest.TestCase):
    def test_library_is_valid_and_mirror_paired(self):
        validate(DATA)

    def test_policy_matches_library_order(self):
        self.assertEqual(POLICY["edits"], [e["id"] for e in EDITS])
        self.assertEqual(len(POLICY["priors"]), 6 * 6 * 3 * 2)

    def test_disabled_edits_never_recommended(self):
        for ub in range(6):
            for vb in range(6):
                top = rank(((ub + 0.5) / 2, (vb + 0.5) / 2), 1, False)[0][1]
                self.assertNotIn(top, ("door", "slim_wall_left", "slim_wall_right", "tiny_wall_left", "tiny_wall_right"))

    def test_same_input_same_answer(self):
        aim = (1.23, 0.77)
        self.assertEqual(rank(aim, 0, True), rank(aim, 0, True))

    def test_priors_are_exactly_mirror_symmetric(self):
        for ub in range(6):
            for vb in range(6):
                for side in range(3):
                    for far in range(2):
                        a = POLICY["priors"][f"{ub},{vb},{side},{far}"]
                        b = POLICY["priors"][f"{5 - ub},{vb},{2 - side},{far}"]
                        for j, e in enumerate(EDITS):
                            k = [x["id"] for x in EDITS].index(mirror_id(e["id"]))
                            self.assertAlmostEqual(a[j], b[k], places=3)

    def test_recommendation_is_left_right_unbiased(self):
        checked = 0
        for u in (0.2, 0.45, 0.8, 1.1, 1.3):
            for v in (0.3, 0.9, 1.5, 2.1, 2.7):
                for side in range(3):
                    for far in (False, True):
                        here = rank((u, v), side, far)
                        twin = rank((3.0 - u, v), 2 - side, far)
                        if abs(here[0][0] - here[1][0]) < 1e-6:
                            continue
                        self.assertEqual(mirror_id(here[0][1]), twin[0][1])
                        checked += 1
        self.assertGreater(checked, 100)

    def test_only_the_aimed_side_is_offered(self):
        for u in (0.2, 0.7, 1.2, 1.3):
            for v in (0.3, 1.5, 2.7):
                ids = [i for _, i in rank((u, v), 1, False)]
                self.assertTrue(all(shape_side(next(e["tiles"] for e in EDITS if e["id"] == i)) <= 0 for i in ids),
                                f"aim {(u, v)} offered a right-side edit: {ids}")
        for u in (1.7, 1.8, 2.3, 2.8):
            for v in (0.3, 1.5, 2.7):
                ids = [i for _, i in rank((u, v), 1, False)]
                self.assertTrue(all(shape_side(next(e["tiles"] for e in EDITS if e["id"] == i)) >= 0 for i in ids),
                                f"aim {(u, v)} offered a left-side edit: {ids}")

    def test_centre_shapes_are_always_available(self):
        for u in (0.2, 1.5, 2.8):
            ids = [i for _, i in rank((u, 1.5), 1, False)]
            self.assertIn("window_center", ids)

    def test_recommendation_starts_near_the_crosshair(self):
        for u in (0.4, 1.5, 2.6):
            for v in (0.4, 1.5, 2.6):
                best = rank((u, v), 1, False)[0][1]
                tiles = next(e["tiles"] for e in EDITS if e["id"] == best)
                nearest_start = min(approach((u, v), t) for t in (tiles, tiles[::-1]))
                self.assertLess(nearest_start, 1.6, f"aim {(u, v)} -> {best}")


if __name__ == "__main__":
    unittest.main()
