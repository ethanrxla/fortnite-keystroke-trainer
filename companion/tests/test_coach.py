import unittest

from keystroke_lab import coach, drills, ktlog


def rec(line):
    return ktlog.parse_line(line)


LOG = [rec(x) for x in [
    "KT|set_start|box_reboxing|tempo=60|rep=0|step=0|result=ok|t=1.0",
    "KT|step|box_reboxing|tempo=60|rep=1|step=5|result=exposed|t=2.0|action=cone",
    "KT|step|box_reboxing|tempo=60|rep=2|step=5|result=exposed|t=4.0|action=cone",
    "KT|step|box_reboxing|tempo=60|rep=2|step=9|result=ok|t=5.0|action=wall|lat_ms=300",
    "KT|set_end|box_reboxing|tempo=60|rep=10|step=0|result=ok|t=30.0|clean=8|accuracy=0.8|decision=hold|hits=4|lat_ms=320|band=cleaning",
]]


class Coach(unittest.TestCase):
    def setUp(self):
        _, self.catalog = drills.load_catalog()
        self.principles = drills.load_principles()

    def test_every_drill_has_a_known_principle_and_reflection(self):
        for d in self.catalog.values():
            self.assertIn(d.principle, self.principles, d.id)
            self.assertTrue(d.why and d.reflect and d.tip, d.id)

    def test_last_set_and_errors(self):
        end, steps = coach.last_set(LOG)
        self.assertEqual(end["drill_id"], "box_reboxing")
        self.assertEqual(coach.error_summary(steps), [((5, "exposed"), 2)])

    def test_prompt_carries_principle_and_errors(self):
        end, steps = coach.last_set(LOG)
        d = self.catalog["box_reboxing"]
        text = coach.build_prompt(end, steps, d, self.principles[d.principle])
        self.assertIn(self.principles[d.principle]["name"], text)
        self.assertIn("step 5 exposed x2", text)
        self.assertIn("hits taken 4", text)

    def test_offline_returns_static_words(self):
        out = coach.coach(LOG, self.catalog, self.principles, offline=True)
        self.assertIn("Think:", out)
        self.assertIsNone(coach.coach([], self.catalog, self.principles, offline=True))

    def test_swap_drills_exist_and_target_the_right_tool(self):
        self.assertEqual(self.catalog["pickaxe_swap"].steps, ["pickaxe", "fire", "swap_weapon", "fire"])
        self.assertIn("pickaxe", drills.DEFAULT_BINDS)


if __name__ == "__main__":
    unittest.main()
