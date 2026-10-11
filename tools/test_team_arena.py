import unittest
import build_team_arena as arena


class TeamArenaTests(unittest.TestCase):
    def test_routes_and_mirrors(self):
        arena.validate()

    def test_footprint_excludes_other_districts(self):
        for slab in arena.plan():
            x0,x1,y0,y1=slab["bounds"]
            self.assertGreaterEqual(x0, (140-.08)*512)
            self.assertLessEqual(x1, (156+.08)*512)
            self.assertGreaterEqual(y0, (-117-.08)*512)
            self.assertLessEqual(y1, (-101+.08)*512)

    def test_occupancy_checks_vertical_extent(self):
        floor=arena.plan()[0]
        x0,x1,y0,y1=floor["bounds"]
        actor={"bounds":{"min":{"x":x0,"y":y0,"z":0},
                         "max":{"x":x1,"y":y1,"z":100}}}
        self.assertTrue(arena.overlaps(actor,floor))
        actor["bounds"]["min"]["z"]=5000
        self.assertFalse(arena.overlaps(actor,floor))


if __name__ == "__main__":
    unittest.main()
