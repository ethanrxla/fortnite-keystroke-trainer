import json
import tempfile
import unittest
from pathlib import Path

from keystroke_lab import collector, personalize
from keystroke_lab.store import Store

BINDS = {"edit": "b", "edit_confirm": "o", "reset": "v"}
LOCK = ("KT|lock|edit_guide|tempo=0|rep=0|step=0|result=unchecked|t=10.0|face=X1:2:0|edit=window_center|u_h=150|v_h=150|"
        "side=1|far=0|px=100|py=200|pz=300|ax_h=90|ay_h=10|az_h=-5")
FINISH = "KT|crosshair|edit_guide|tempo=0|rep=1|step=0|result=unchecked|t=11.0|face=X1:2:0|edit=Window|samples=9|travel_h=120|ideal_h=60"


def log_line(stamp, text):
    return f"[{stamp}][ 1]LogVerse: : {text}\n"


class CollectorTests(unittest.TestCase):
    def test_log_timestamp_is_wall_clock_utc(self):
        ts = collector.log_ts("[2026.10.10-00.16.01:656][197]LogVerse: x")
        self.assertAlmostEqual(ts, 1791591361.656, places=2)
        self.assertIsNone(collector.log_ts("no timestamp"))

    def test_lock_is_joined_to_the_keys_that_followed_it(self):
        with tempfile.TemporaryDirectory() as d:
            uefn = Path(d) / "uefn.log"
            uefn.write_text(log_line("2026.10.10-00.00.10:000", LOCK) + log_line("2026.10.10-00.00.12:000", FINISH), encoding="utf-8")
            sessions = Path(d) / "sessions"
            sessions.mkdir()
            base = collector.log_ts("[2026.10.10-00.00.10:000]")
            events = [{"ts": base + 1.0, "kind": "ok", "key": "b"}, {"ts": base + 1.6, "kind": "ok", "key": "o"},
                      {"ts": base + 2.4, "kind": "ok", "key": "v"}, {"ts": base + 3.0, "kind": "stray", "key": "x"}]
            (sessions / "s.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
            store = Store(":memory:")
            a, b, c = collector.cycle(store, BINDS, log_path=uefn, folder=sessions)
            self.assertEqual((a, b, c), (4, 2, 1))
            row = store.rows("SELECT edit_id, side, edit_ts, confirm_ts, reset_ts, travel_h, ideal_h, px FROM attempts")[0]
            self.assertEqual(row[0], "window_center")
            self.assertAlmostEqual(row[3] - row[2], 0.6, places=2)      # confirm 0.6 s after edit
            self.assertIsNotNone(row[4])                                  # then reset
            self.assertEqual((row[5], row[6], row[7]), (120, 60, 100))    # travel vs ideal, player x position

    def test_rereading_the_same_files_adds_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            uefn = Path(d) / "uefn.log"
            uefn.write_text(log_line("2026.10.10-00.00.10:000", LOCK), encoding="utf-8")
            store = Store(":memory:")
            self.assertEqual(collector.ingest_uefn_log(store, uefn), 1)
            self.assertEqual(collector.ingest_uefn_log(store, uefn), 0)      # offset remembered
            store.set_offset(uefn, 0)
            collector.ingest_uefn_log(store, uefn)
            self.assertEqual(collector.summary(store)["kt_lines"], 1)         # and rows are unique anyway

    def test_lock_with_no_edit_press_stays_unacted(self):
        store = Store(":memory:")
        store.add_kt(100.0, {"event": "lock", "drill_id": "edit_guide", "face": "F", "edit": "half_wall"})
        collector.correlate(store, BINDS)
        self.assertIsNone(store.rows("SELECT edit_ts FROM attempts")[0][0])

    def test_repeat_is_not_confirm(self):
        store = Store(":memory:")
        store.add_kt(100, {"event": "lock", "drill_id": "edit_guide", "face": "F", "edit": "half_wall"})
        store.add_key(101, "c", "ok", None, "test")
        store.add_key(101.2, "c", "repeat", None, "test")
        collector.correlate(store, {"edit": "c", "edit_confirm": "c"})
        self.assertEqual(store.rows("SELECT edit_ts, confirm_ts FROM attempts")[0], (101.0, None))
        store.close()

    def test_verified_alternatives(self):
        from keystroke_lab.bind_profiles import Binding, BindProfile, BindMap
        binds = BindMap(BindProfile("p", 1, (
            Binding("edit_confirm", ("c", "mouse_middle"), verified=True),
            Binding("reset", ("mouse_x2",), verified=False),
        )))
        self.assertEqual(collector._action_keys(binds, "edit_confirm"), {"c", "mouse_middle"})
        self.assertEqual(collector._action_keys(binds, "reset"), set())


class PersonalizeTests(unittest.TestCase):
    def seed(self, store, n, edit="window_center"):
        import uuid
        from tests.test_attempt_pipeline import record
        for i in range(n):
            store.add_attempt(record(attempt_id=str(uuid.uuid4()), matched_edit_id=edit, suggested_edit_id=edit,
                                     t_edit_open=float(i), t_close=i + 1.5))

    def test_too_little_data_means_no_opinion(self):
        store = Store(":memory:")
        self.seed(store, 3)

        class Boom:
            available = True

            def decide(self, *a):
                raise AssertionError("must not call Jev without enough data")

        self.assertEqual(personalize.factors(personalize.edit_stats(store), Boom()), {"window_center": 1.0})

    def test_jev_rating_becomes_a_bounded_factor(self):
        store = Store(":memory:")
        self.seed(store, 8)

        class Jev:
            available = True

            def decide(self, state, questions):
                return {q: {"probabilities": {"strong": 0.9, "average": 0.1, "weak": 0.0}} for q in questions}

        f = personalize.factors(personalize.edit_stats(store), Jev())["window_center"]
        self.assertAlmostEqual(f, 1.27, places=2)
        self.assertLessEqual(f, 1.3)

    def test_more_than_eight_edits_are_sent_in_batches(self):
        store = Store(":memory:")
        ids = ["window_center", "window_high", "half_wall", "quarter_wall", "corner_lower_left", "corner_lower_right",
               "corner_upper_left", "corner_upper_right", "half_arch_left", "half_arch_right"]
        for e in ids:
            self.seed(store, 5, e)
        sizes = []

        class Jev:
            available = True

            def decide(self, state, questions):
                sizes.append(len(questions))
                return {q: {"probabilities": {"strong": 0.0, "average": 0.0, "weak": 1.0}} for q in questions}

        f = personalize.factors(personalize.edit_stats(store), Jev())
        self.assertEqual(sorted(sizes), [2, 8])
        self.assertTrue(all(v == 0.7 for v in f.values()))

    def test_rejected_attempts_do_not_count(self):
        store = Store(":memory:")
        self.seed(store, 2)
        aid = store.rows("SELECT attempt_id FROM edit_attempts LIMIT 1")[0][0]
        store.add_label(aid, "rejected")
        self.assertEqual(personalize.edit_stats(store)["window_center"]["attempts"], 1)

    def test_policy_blend_keeps_rows_normalised_and_floored(self):
        out = personalize.apply_to_policy({(0, 0, 0, 0): [0.5, 0.5]}, ["a", "b"], {"a": 1.3, "b": 0.7})
        vec = out[(0, 0, 0, 0)]
        self.assertAlmostEqual(sum(vec), 1.0, places=6)
        self.assertGreater(vec[0], vec[1])


if __name__ == "__main__":
    unittest.main()
