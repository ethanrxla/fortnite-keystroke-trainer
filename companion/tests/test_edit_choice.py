import tempfile
import unittest
from pathlib import Path

from keystroke_lab.edit_advisor import safe_path
from keystroke_lab.edit_choice import EXAMPLE_MIN, Examples, choose_edit, wall_library
from keystroke_lab.edit_ranker import Ranker

LOW_CENTRE = (1.56, 0.77)     # where the crosshair was for the arch in the 2026-10-10 screenshot


class EditChoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ranker = Ranker(personal={})

    def examples(self, folder):
        return Examples(Path(folder) / "ex.jsonl")

    def test_arch_is_in_the_library_and_routable(self):
        self.assertEqual(set(wall_library()["arch_wide"]), {0, 1, 2, 4})
        length, points, order = safe_path(LOW_CENTRE, [4, 1, 0, 2])
        self.assertEqual(order[0], 4)
        self.assertEqual(set(order), {0, 1, 2, 4})

    def test_selection_beats_the_aim(self):
        with tempfile.TemporaryDirectory() as folder:
            ex = self.examples(folder)
            # The half arch selected on screen (shot 2): never the corner the old reference always showed.
            self.assertEqual(choose_edit((2.25, 1.19), (1, 2, 4, 5), self.ranker, ex, "corner_upper_right"),
                             ("half_arch_right", "selection"))
            self.assertEqual(choose_edit(LOW_CENTRE, (0, 1, 2, 4), self.ranker, ex)[0], "arch_wide")
            # Mid-drag: whatever is locked stays while it still contains the selection.
            self.assertEqual(choose_edit(LOW_CENTRE, (4, 1), self.ranker, ex, "arch_wide"), ("arch_wide", "selection"))
            self.assertEqual(choose_edit(LOW_CENTRE, (0, 1, 2), self.ranker, ex)[0], "arch_wide")    # mid-drag of the arch
            self.assertEqual(choose_edit(LOW_CENTRE, (0, 8), self.ranker, ex), (None, "unknown_selection"))

    def test_examples_teach_the_aim(self):
        with tempfile.TemporaryDirectory() as folder:
            ex = self.examples(folder)
            self.assertEqual(choose_edit(LOW_CENTRE, (), self.ranker, ex), ("window_center", "ranker"))
            for i in range(EXAMPLE_MIN):
                self.assertEqual(ex.add((1.6 + i * 0.05, 0.8), [0, 1, 2, 4], now=i)["edit"], "arch_wide")
            self.assertEqual(choose_edit(LOW_CENTRE, (), self.ranker, ex), ("arch_wide", "examples"))
            # Higher up the wall is another bucket: the quarter-wall area is untouched by these examples.
            self.assertEqual(choose_edit((1.5, 2.3), (), self.ranker, ex)[1], "ranker")
            reloaded = Examples(ex.path)
            self.assertEqual(reloaded.summary(), [((0, 1, 2, 4), "arch_wide", EXAMPLE_MIN)])

    def test_unknown_masks_are_kept_but_never_suggested(self):
        with tempfile.TemporaryDirectory() as folder:
            ex = self.examples(folder)
            for i in range(EXAMPLE_MIN):
                self.assertIsNone(ex.add(LOW_CENTRE, [0, 8], now=i)["edit"])
            self.assertEqual(choose_edit(LOW_CENTRE, (), self.ranker, ex)[1], "ranker")


if __name__ == "__main__":
    unittest.main()
