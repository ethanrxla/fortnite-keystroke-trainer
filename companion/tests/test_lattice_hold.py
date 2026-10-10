"""A detection that is the held grid moved by whole tiles must not flip the guide (live 2026-10-10: the grid jumped one
row between detections and the suggestion flipped between the upper and lower corner with the crosshair still)."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.vision_packages'))
    from keystroke_lab.edit_window import ContextPipeline, lattice_offset
    from keystroke_lab.piece_observation import PieceObservation
except ImportError:
    ContextPipeline = None

WALL = ((400., 100.), (1000., 100.), (1000., 700.), (400., 700.))          # 200 px tiles
ROW_DOWN = ((400., 300.), (1000., 300.), (1000., 900.), (400., 900.))      # the same lattice one row lower


@unittest.skipIf(ContextPipeline is None, 'optional local vision dependencies missing')
class LatticeHoldTests(unittest.TestCase):
    def test_offset_of_the_same_lattice(self):
        self.assertEqual(lattice_offset(WALL, WALL), (0, 0))
        self.assertEqual(lattice_offset(WALL, ROW_DOWN), (0, 1))
        self.assertEqual(lattice_offset(WALL, ((200., 100.), (800., 100.), (800., 700.), (200., 700.))), (-1, 0))

    def test_different_grid_is_not_a_shift(self):
        self.assertIsNone(lattice_offset(WALL, ((500., 100.), (1100., 100.), (1100., 700.), (500., 700.))))   # half a tile

    def pipe(self):
        # The real method on a minimal stand-in: from_quad just records the quad it was asked to re-read.
        observer = SimpleNamespace(from_quad=lambda frame, obs, now: obs)
        return SimpleNamespace(held=PieceObservation(10., 'wall', WALL), shift_vote=None, observer=observer,
                               SHIFT_VOTES=ContextPipeline.SHIFT_VOTES)

    def test_one_row_jump_is_held_until_detections_agree(self):
        p = self.pipe()
        det = PieceObservation(10.1, 'wall', ROW_DOWN)
        for _ in range(ContextPipeline.SHIFT_VOTES - 1):
            out = ContextPipeline._hold_lattice(p, det, None)
            for got, want in zip(out.quad, WALL):              # re-anchored onto the held lattice
                self.assertAlmostEqual(got[0], want[0], 3); self.assertAlmostEqual(got[1], want[1], 3)
        out = ContextPipeline._hold_lattice(p, det, None)      # the shift kept coming back: accept it
        self.assertEqual(out.quad, ROW_DOWN)

    def test_same_grid_or_stale_hold_passes_straight_through(self):
        p = self.pipe()
        self.assertEqual(ContextPipeline._hold_lattice(p, PieceObservation(10.1, 'wall', WALL), None).quad, WALL)
        p.held = replace(p.held, captured_at=9.)
        self.assertEqual(ContextPipeline._hold_lattice(p, PieceObservation(10.1, 'wall', ROW_DOWN), None).quad, ROW_DOWN)


if __name__ == '__main__':
    unittest.main()
