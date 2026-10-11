"""Recorded user demonstrations; geometry acquisition is not piece classification."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.vision_packages'))
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
if cv2 is not None:
    from keystroke_lab.flat_grid import flat_grid
    from keystroke_lab.edit_observation import _segments,downscale

FIXTURES=Path(__file__).parent/'fixtures/edit-vision'

@unittest.skipIf(cv2 is None, "Install optional vision dependencies; see companion/README.md")
class FlatGridTests(unittest.TestCase):
    def read(self,name):
        im=cv2.imread(str(FIXTURES/name))
        if im is None:self.skipTest('Missing Git LFS fixture: '+name)
        return downscale(im,640/im.shape[1])

    def test_oblique_floor_acquires_four_regions(self):
        im=self.read('floor-oblique-demo.png')
        found=flat_grid(im,(im.shape[1]/2,im.shape[0]/2),_segments(im),budget=.1)
        self.assertIsNotNone(found)
        count,H,quad,n=found
        self.assertEqual((count,n),(4,2))
        # The target occupies the lower-right of this recorded frame.
        self.assertGreater(quad[:,0].min(),190)
        self.assertGreater(quad[:,1].min(),140)
        self.assertLess(quad[:,1].max(),280)
        uv=cv2.perspectiveTransform(np.float32([[[320,im.shape[0]/2]]]),np.linalg.inv(H))[0,0]
        self.assertTrue(all(0<=v<=2 for v in uv))

    def test_weapons_and_pickaxe_do_not_create_grid(self):
        for name in ('weapon.png','pickaxe.png'):
            im=self.read(name)
            self.assertIsNone(flat_grid(im,(im.shape[1]/2,im.shape[0]/2),_segments(im),budget=.1))
