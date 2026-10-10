import json
import pathlib
import unittest

from keystroke_lab.build_pieces import (ConePiece, FloorPiece, PatternTable, StairPiece, WallPiece, class_path,
                                        piece_for)

SHARED = pathlib.Path(__file__).resolve().parents[2] / "shared"


class PieceClassTests(unittest.TestCase):
    def test_aliases_pick_the_four_classes(self):
        self.assertIsInstance(piece_for("wall"), WallPiece)
        self.assertIsInstance(piece_for("floor"), FloorPiece)
        self.assertIsInstance(piece_for("roof"), ConePiece)
        self.assertIsInstance(piece_for("stairs"), StairPiece)
        with self.assertRaises(ValueError):
            piece_for("pyramid")

    def test_grids_match_the_library(self):
        data = json.loads((SHARED / "edits.json").read_text(encoding="utf-8"))
        for key, meta in data["pieces"].items():
            p = piece_for(key)
            self.assertEqual((p.cols, p.rows), (meta["cols"], meta["rows"]), key)
            self.assertEqual(p.base_class, meta["base_class"], key)
            self.assertEqual(p.semantics, meta["edit_semantics"], key)

    def test_select_toggles_and_reset_restores(self):
        w = WallPiece()
        w.select(4), w.select(1), w.select(4)
        self.assertEqual(w.selection, (1,))
        with self.assertRaises(ValueError):
            w.select(9)
        w.reset()
        self.assertEqual(w.visual().visible, tuple(range(9)))

    def test_rotate_and_mirror_two_by_two(self):
        f = FloorPiece()
        self.assertEqual(f.rotate((0,)), (2,))
        self.assertEqual(f.rotate((0, 1), 4), (0, 1))
        self.assertEqual(f.mirror((0, 2)), (1, 3))
        self.assertEqual(WallPiece().mirror((0, 3, 5)), (2, 5, 3))

    def test_snap(self):
        self.assertEqual(WallPiece.snap((1030.0, -10.0, 400.0)), (2, -1, 1))


class PatternTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = PatternTable()

    def confirm(self, piece, tiles):
        piece.set_selection(tiles)
        return piece.confirm(self.table)

    def test_window_updates_visual_and_class(self):
        w = WallPiece()
        out = self.confirm(w, [4])
        self.assertTrue(out.valid)
        self.assertEqual(out.pattern.id, "window_center")
        v = w.visual()
        self.assertNotIn(4, v.visible)
        self.assertEqual(v.visible, v.collision)
        self.assertEqual(v.result_class, "WindowC")
        self.assertTrue(v.class_path.endswith("PBWA_W1_WindowC.PBWA_W1_WindowC_C"))

    def test_rejected_edits_leave_the_piece_unchanged(self):
        w = WallPiece()
        self.assertEqual(self.confirm(w, [0, 8]).reason, "unsupported_shape")      # two far corners: no such edit
        self.assertEqual(self.confirm(w, range(9)).reason, "nothing_left")
        self.assertEqual(self.confirm(w, []).reason, "no_edit")
        self.assertEqual(w.visual().result_class, "Solid")

    def test_floating_shape_is_rejected_but_a_door_joining_halves_is_not(self):
        out = self.confirm(WallPiece(), [3, 4, 5])          # whole middle row: top row would float
        self.assertFalse(out.valid)
        self.assertEqual(out.reason, "floating")
        out = self.confirm(WallPiece(), [6, 7, 8, 4, 1])    # half wall + door: two halves held by the door
        self.assertTrue(out.valid)
        self.assertEqual(out.pattern.result_class, "HalfWallDoor")

    def test_every_two_by_two_selection_is_an_edit(self):
        for piece in ("floor", "cone"):
            cov = self.table.coverage(piece)
            self.assertEqual(len(cov), 15)
            self.assertEqual([m for m, ids in cov.items() if not ids], [15], piece)   # only "remove all" is missing

    def test_floor_and_cone_classes_follow_what_is_left(self):
        self.assertEqual(self.confirm(FloorPiece(), [0]).pattern.result_class, "BalconyI")
        self.assertEqual(self.confirm(FloorPiece(), [0, 3]).pattern.result_class, "BalconyD")
        self.assertEqual(self.confirm(ConePiece(), [2, 3]).pattern.result_class, "RoofS")
        self.assertEqual(self.confirm(ConePiece(), [0, 1, 2]).pattern.result_class, "RoofO")

    def test_ramps_match_by_path_and_order(self):
        r = StairPiece()
        for t in (0, 2):
            r.select(t)
        out = r.confirm(self.table)
        self.assertTrue(out.valid)
        self.assertEqual(out.pattern.id, "ramp_half_nl_fl")
        self.assertEqual(r.visual().visible, (0, 2))
        self.assertEqual(self.confirm(StairPiece(), [2, 0]).pattern.id, "ramp_half_fl_nl")
        self.assertEqual(self.confirm(StairPiece(), [0, 1, 3, 2]).pattern.result_class, "StairSpiral")
        self.assertEqual(self.confirm(StairPiece(), [0, 3]).reason, "broken_path")     # diagonal step
        self.assertEqual(self.confirm(StairPiece(), [0]).reason, "broken_path")

    def test_ramp_drag_back_undoes_a_step(self):
        r = StairPiece()
        for t in (0, 1, 3, 1):
            r.select(t)
        self.assertEqual(r.selection, (0, 1))

    def test_all_24_ramp_paths(self):
        paths = [p.path for p in self.table.patterns("ramp") if p.id.startswith("ramp_")]
        self.assertEqual(len(paths), 24)
        self.assertEqual(len(set(paths)), 24)

    def test_rows_view(self):
        p = self.table.all["door"]
        self.assertEqual(p.rows(3, 3), [[False, True, False], [False, True, False], [False, False, False]])

    def test_class_path_materials(self):
        self.assertIsNone(class_path(None))
        self.assertIn("/Metal/", class_path("Floor", "metal"))


if __name__ == "__main__":
    unittest.main()
