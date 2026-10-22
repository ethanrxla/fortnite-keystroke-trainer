import unittest

from keystroke_lab.build_pieces import WallPiece, FloorPiece, ConePiece, StairPiece
from keystroke_lab.edit_dictionary import EditDictionary, RoutePlanner, RouteTracker
from keystroke_lab.guide_visuals import layout


class PieceRouteTests(unittest.TestCase):
    def setUp(self):
        self.edits = EditDictionary().all

    # Ramps are 3 x 3 (player 2026-10-22); a ramp edit is one drag through tile centres, bottom tile of the climb first.
    def test_ramp_route_follows_the_drag(self):
        paths = RoutePlanner().strokes((1.5, 1.5), self.edits['ramp_full_toward'])
        self.assertEqual(paths, (((1.5, 2.5), (1.5, 1.5), (1.5, .5)),))
        visual = layout(self.edits['ramp_full_toward'], (1.5, 1.5))
        self.assertEqual((len(visual.strokes), len(visual.approaches), len(visual.labels), len(visual.regions)), (1, 1, 3, 9))
        self.assertEqual(RoutePlanner().strokes((.5, .5), self.edits['stair_l_away_right']),
                         (((.5, .5), (.5, 1.5), (.5, 2.5), (1.5, 2.5), (2.5, 2.5)),))

    def test_diagonal_floor_is_two_taps_not_one_drag(self):
        edit = self.edits['floor_diagonal_b']
        visual = layout(edit, (.5, .5))
        self.assertEqual([len(s) for s in visual.strokes], [1, 1])
        self.assertEqual(len(visual.approaches), 2)
        self.assertEqual(set(visual.selected), {1, 2})

    def test_route_does_not_reverse_mid_trace_and_unlocks_on_reset(self):
        edit = self.edits['corner_upper_right']; tracker = RouteTracker()
        first = tracker.update('wall:1', (2.7, 1.5), edit, ())
        moved = tracker.update('wall:1', (1.5, 2.7), edit, (5,))
        self.assertEqual(moved, first)
        self.assertEqual(layout(edit, (1.5, 2.7), moved).strokes,
                         layout(edit, (2.7, 1.5), first).strokes)
        reset = tracker.update('wall:1', (1.5, 2.7), edit, ())
        self.assertNotEqual(reset, first)
        self.assertEqual(tracker.update('wall:2', (2.7, 1.5), edit, (5,)), first)

    def test_invalid_ramp_stroke_is_not_drawn(self):
        edit = dict(self.edits['ramp_full_toward'], strokes=[[0, 4]])     # diagonal step
        self.assertEqual(RoutePlanner().strokes((1., 1.), edit), ())


class PieceGridStateTests(unittest.TestCase):
    def test_boolean_grids_roundtrip_for_each_grid_piece(self):
        for piece in (WallPiece(), FloorPiece(), ConePiece()):
            grid = [[False]*piece.cols for _ in range(piece.rows)]
            grid[0][0] = True; grid[-1][-1] = True
            piece.set_selection_rows(grid)
            self.assertEqual(piece.selection_rows(), grid)
            grid[0][0] = False
            self.assertTrue(piece.selection_rows()[0][0])

    def test_invalid_grid_is_atomic_and_generator_input_is_not_consumed(self):
        piece = WallPiece();piece.set_selection(t for t in (1, 4))
        self.assertEqual(piece.selection, (1, 4))
        for grid in ([[True]], [[0]*3 for _ in range(3)]):
            with self.assertRaises(ValueError):piece.set_selection_rows(grid)
            self.assertEqual(piece.selection, (1, 4))

    def test_ramps_cannot_lose_direction_in_a_boolean_grid(self):
        piece = StairPiece();piece.set_strokes([[0, 2]])
        with self.assertRaises(ValueError):piece.set_selection_rows([[True, False], [True, False]])
        with self.assertRaises(ValueError):piece.set_strokes([[0, 9]])
        self.assertEqual(piece.strokes, [[0, 2]])
