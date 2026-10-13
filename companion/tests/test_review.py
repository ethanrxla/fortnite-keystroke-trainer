import unittest

from keystroke_lab import drills, profile, review

BINDS = dict(drills.DEFAULT_BINDS)  # hermetic: never the player's own keybinds.json
_, CATALOG = drills.load_catalog()
PRINCIPLES = drills.load_principles()


def key(t, action):
    return {"t": t, "kind": "key", "name": BINDS[action]}


def build(start, steps, gaps):
    out, t = [], start
    for s, g in zip(steps, gaps):
        out.append({"t": t, "kind": "flick", "name": "turn"} if s == "turn_right" else key(t, s))
        t += g
    return out


class Alignment(unittest.TestCase):
    def test_match_swap_missing_extra(self):
        ops = review.align(["wall", "ramp", "floor"], ["wall", "floor", "ramp"])
        kinds = [k for k, _, _ in ops]
        self.assertEqual(kinds.count("match"), 1)
        self.assertEqual(review.align(["a", "b"], ["a", "b"]), [("match", 0, 0), ("match", 1, 1)])
        self.assertIn("missing", [k for k, _, _ in review.align(["wall"], ["wall", "cone"])])
        self.assertIn("extra", [k for k, _, _ in review.align(["wall", "wall", "cone"], ["wall", "cone"])])

    def test_closest_order_prefers_the_alternative_you_followed(self):
        d = CATALOG["box_up"]
        mine = ["wall", "wall", "wall", "wall", "floor", "cone"]
        self.assertEqual(review.closest_order(mine, d), mine)
        self.assertEqual(review.closest_order(d.steps, d), d.steps)


class Entries(unittest.TestCase):
    def events(self):
        ev = build(0, ["wall", "ramp", "floor", "turn_right", "jump"], [0.2, 0.2, 0.2, 0.2, 0.2])          # an accepted 90
        ev += build(10, ["ramp", "wall", "wall", "jump", "floor", "ramp", "turn_right"], [0.2, 0.5, 0.2, 0.2, 0.2, 0.2, 0.2])  # hesitation inside one build (a pause over 0.6 s would end it), odd order
        ev += build(20, ["floor", "wall", "floor", "wall", "wall", "wall"], [0.2] * 6)                    # box in the reference order
        ev += build(30, ["floor", "wall", "wall", "cone", "edit"], [0.2, 0.2, 0.2, 0.2, 0.2])
        ev += [key(30.9, "edit_confirm"), key(31.1, "edit")]                                              # tunnel edit, never reset
        # (the second edit keeps it closest to P7: piece switch also ends edit, confirm since 2026-10-13)
        return ev

    def test_worst_first_and_clean_build_is_labelled_clean(self):
        entries, summary = review.build_entries(self.events(), BINDS, CATALOG, PRINCIPLES)
        self.assertGreaterEqual(summary["matched"], 3)
        self.assertGreaterEqual(entries[0]["distance"], entries[-1]["distance"])
        box = next(e for e in entries if e["drill"] == "box_up")
        self.assertEqual(box["distance"], 0)
        self.assertIn("Same order", box["insights"][0]["text"])

    def test_missing_reset_and_hesitation_are_called_out(self):
        entries, _ = review.build_entries(self.events(), BINDS, CATALOG, PRINCIPLES)
        text = " ".join(i["text"] for e in entries for i in e["insights"])
        self.assertIn("No reset in your build", text)
        self.assertIn("Longest pause", text)

    def test_suggestion_is_paced_at_the_players_speed(self):
        entries, summary = review.build_entries(self.events(), BINDS, CATALOG, PRINCIPLES)
        s = entries[0]["suggested"]
        self.assertAlmostEqual(s[1]["t"] - s[0]["t"], summary["pace"], places=2)
        self.assertGreaterEqual(summary["pace"], review.PACE_FLOOR)

    def test_html_is_self_contained_and_escapes(self):
        entries, summary = review.build_entries(self.events(), BINDS, CATALOG, PRINCIPLES)
        page = review.render_html(entries, summary)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("src=", page)
        self.assertIn("Replay", page)
        self.assertIn("Yours", page)
        self.assertIn("Suggested", page)

    def test_empty_recording(self):
        entries, summary = review.build_entries([], BINDS, CATALOG, PRINCIPLES)
        self.assertEqual(entries, [])
        self.assertIn("Record some play", review.render_html(entries, summary))


if __name__ == "__main__":
    unittest.main()
