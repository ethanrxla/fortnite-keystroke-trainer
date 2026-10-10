import unittest

from keystroke_lab import drills, profile

BINDS = dict(drills.DEFAULT_BINDS)  # hermetic: never the player's own keybinds.json
LADDER, CATALOG = drills.load_catalog()


def key(t, action):
    return {"t": t, "kind": "key", "name": BINDS[action]}


def flick(t):
    return {"t": t, "kind": "flick", "name": "turn"}


def build(start, steps, gap):
    """Events for one build: steps is a list of actions or ('flick',)."""
    out, t = [], start
    for s in steps:
        out.append(flick(t) if s == "turn_right" else key(t, s))
        t += gap
    return out


NINETY = ["wall", "floor", "ramp", "turn_right", "jump"]


class Segmentation(unittest.TestCase):
    def test_pause_splits_builds_and_clicks_resolve(self):
        ev = build(0, ["wall", "ramp"], 0.2) + build(5, ["edit"], 0.2) + [key(5.3, "edit_confirm")]
        actions = profile.to_actions(ev, BINDS)
        self.assertIn("edit_confirm", [a for _, a in actions])  # a click right after edit is a confirm
        builds = profile.segment(actions)
        self.assertEqual([[a for _, a in b] for b in builds], [["wall", "ramp"], ["edit", "edit_confirm"]])

    def test_unbound_keys_are_ignored(self):
        ev = [{"t": 0, "kind": "key", "name": "x"}, {"t": 0.1, "kind": "key", "name": "x"}]
        self.assertEqual(profile.to_actions(ev, BINDS), [])


class Classification(unittest.TestCase):
    def test_clean_90_matches_nineties(self):
        b = profile.segment(profile.to_actions(build(0, NINETY, 0.18), BINDS))[0]
        self.assertEqual(profile.classify(b, CATALOG), ("nineties", 0))

    def test_reference_and_accepted_orders_are_both_clean(self):
        ref = profile.segment(profile.to_actions(build(0, CATALOG["nineties"].steps, 0.18), BINDS))[0]
        alt = profile.segment(profile.to_actions(build(0, ["wall", "floor", "ramp", "turn_right", "jump"], 0.18), BINDS))[0]
        self.assertEqual(profile.classify(ref, CATALOG), ("nineties", 0))
        self.assertEqual(profile.classify(alt, CATALOG), ("nineties", 0))

    def test_box_orders(self):
        for order in (CATALOG["box_up"].steps, ["wall"] * 4 + ["floor", "cone"], ["wall", "wall", "floor", "ramp"]):
            b = profile.segment(profile.to_actions(build(0, order, 0.15), BINDS))[0]
            self.assertEqual(profile.classify(b, CATALOG), ("box_up", 0), order)

    def test_one_slip_is_close_but_not_clean(self):
        slip = ["wall", "ramp", "ramp", "turn_right", "jump"]  # second ramp instead of floor (one edit from an accepted order)
        b = profile.segment(profile.to_actions(build(0, slip, 0.18), BINDS))[0]
        self.assertEqual(profile.classify(b, CATALOG), ("nineties", 1))

    def test_random_mashing_matches_nothing(self):
        junk = ["cone", "jump", "crouch", "cone", "jump", "crouch", "fire", "swap_weapon"]
        b = profile.segment(profile.to_actions(build(0, junk, 0.15), BINDS))[0]
        self.assertEqual(profile.classify(b, CATALOG)[0], None)


class Stats(unittest.TestCase):
    def events(self):
        ev, t = [], 0.0
        for _ in range(10):                      # ten clean, fast box-ups
            ev += build(t, CATALOG["box_up"].steps, 0.15)
            t += 5
        for i in range(10):                      # ten 90s, half of them sloppy and slow
            steps = NINETY if i % 2 == 0 else ["wall", "ramp", "ramp", "turn_right", "jump"]
            ev += build(t, steps, 0.4)
            t += 5
        return ev

    def test_stats_and_weakness_rank_the_90_worse(self):
        stats = profile.analyze(self.events(), BINDS, CATALOG)
        self.assertEqual(stats["box_up"]["clean_rate"], 1.0)
        self.assertAlmostEqual(stats["nineties"]["clean_rate"], 0.5)
        scores = profile.weakness(stats)
        self.assertGreater(scores["nineties"], scores["box_up"])
        self.assertGreater(profile.measured_apm(stats["box_up"]), profile.measured_apm(stats["nineties"]))

    def test_few_builds_do_not_swing_the_score(self):
        ev = build(0, ["wall", "ramp", "ramp", "turn_right", "jump"], 0.2)  # a single sloppy 90
        scores = profile.weakness(profile.analyze(ev, BINDS, CATALOG))
        self.assertLess(scores["nineties"], 0.1)


class Planning(unittest.TestCase):
    def test_plan_has_three_blocks_and_targets_the_weak_drill(self):
        ev, t = [], 0.0
        for i in range(12):
            ev += build(t, ["wall", "ramp", "ramp", "turn_right", "jump"], 0.4)  # always slipping on 90s
            t += 5
        stats = profile.analyze(ev, BINDS, CATALOG)
        p = profile.plan(stats, CATALOG, minutes=15)
        self.assertEqual([b["block"] for b in p["blocks"]], ["edits", "building combos", "fight practice"])
        combos = [d["drill"] for d in p["blocks"][1]["drills"]]
        self.assertIn("nineties", combos)
        item = next(d for d in p["blocks"][1]["drills"] if d["drill"] == "nineties")
        self.assertLessEqual(item["tempo"], 80)  # slow first for a player who is slipping

    def test_new_player_gets_a_broad_slow_plan(self):
        p = profile.plan({}, CATALOG)
        for b in p["blocks"]:
            self.assertTrue(b["drills"])
            self.assertTrue(all(d["tempo"] == LADDER[0] for d in b["drills"]))

    def test_clean_players_move_up_a_rung(self):
        stats = {"box_up": {"builds": 20, "clean_rate": 1.0, "mean_gap": 0.4, "gap_spread": 0.03,
                            "mean_duration": 2.0, "slowest_transition": ("wall>wall", 0.4)}}
        base = profile.next_tempo(dict(stats["box_up"], clean_rate=0.8), LADDER)
        up = profile.next_tempo(stats["box_up"], LADDER)
        self.assertGreater(up, base)


if __name__ == "__main__":
    unittest.main()
