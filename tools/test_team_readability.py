import unittest
import build_team_readability as r


class CourtReadabilityTests(unittest.TestCase):
    def test_plan_stays_inside_court_and_below_cover(self):
        r.validate_plan()
        self.assertEqual(len(r.plan()), 24)

    def test_ground_marks_match_objective_corners(self):
        marks = [s for s in r.plan() if 'Objective' in s['label']]
        self.assertEqual(len(marks), 8)
        for s in marks:
            x0, x1, y0, y1 = s['bounds']
            self.assertTrue(r.OX+7*512 <= x0 < x1 <= r.OX+9*512)
            self.assertTrue(r.OY+7*512 <= y0 < y1 <= r.OY+9*512)
            self.assertEqual(s['top'], 2)

    def volume(self, bottom=2112, height=4608):
        return {'bounds': {'min': {'x': r.OX, 'y': r.OY, 'z': bottom},
                           'max': {'x': r.OX+8192, 'y': r.OY+8192, 'z': bottom+height}}}

    def test_measured_bad_offset_fixed_once(self):
        self.assertEqual(r.volume_delta(self.volume()), -2112)
        self.assertEqual(r.volume_delta(self.volume(0)), 0)

    def test_volume_drift_is_not_silently_overwritten(self):
        for actor in (self.volume(300), self.volume(height=3000)):
            with self.assertRaises(RuntimeError):
                r.volume_delta(actor)

    def test_fascia_heights_do_not_add_cover(self):
        for s in r.plan():
            if any(str(level) in s['label'] for level in (384, 768)):
                self.assertIn(s['top'], (382, 766))


if __name__ == '__main__':
    unittest.main()
