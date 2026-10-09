"""Offline regressions: protect other builders and validate authored edit paths."""
import json
import unittest
from pathlib import Path
from build_level_select import owns_label
from gen_drills import render, validate

ROOT=Path(__file__).resolve().parent.parent

class TrainingRegressions(unittest.TestCase):
    def test_level_selector_never_owns_armory_or_lane_helpers(self):
        for label in ['KT3_Armory_AR','KT3_Upgrade_Arena_Start_B','KT3_Boom_E2_0','KT3_GunRack_Shotgun','KT4_Coach_E2','KT3_01_Button_extra']:
            self.assertFalse(owns_label(label),label)
        for label in ['KT3_01_Button','KT3_08_Button','KT3_04_Src','KT3_06_Dest','KT3_Sign']:
            self.assertTrue(owns_label(label),label)

    def test_corner_routes_are_contiguous_and_mirrored(self):
        routes=json.loads((ROOT/'shared/drills.json').read_text())['adaptive_edit']['routes']
        self.assertEqual(routes[4]['tiles'],[4])
        for route in routes[:4]:
            tiles=route['tiles']; self.assertEqual(len(set(tiles)),3)
            for a,c in zip(tiles,tiles[1:]):
                self.assertEqual(abs(a//3-c//3)+abs(a%3-c%3),1)
        mirror=lambda tiles:{(t//3)*3+2-t%3 for t in tiles}
        self.assertEqual(mirror(routes[0]['tiles']),set(routes[1]['tiles']))
        self.assertEqual(mirror(routes[2]['tiles']),set(routes[3]['tiles']))

    def test_generated_catalog_matches_source(self):
        data=json.loads((ROOT/'shared/drills.json').read_text()); validate(data)
        self.assertEqual(render(data),(ROOT/'verse/KeystrokeTrainer/DrillCatalog.verse').read_text())

if __name__=='__main__':unittest.main()
