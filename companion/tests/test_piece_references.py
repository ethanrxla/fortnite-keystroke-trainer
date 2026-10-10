import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.vision_packages'))
import cv2
from keystroke_lab.piece_references import PieceReferenceRecognizer

FIXTURES=Path(__file__).parent/'fixtures/edit-vision'

class PieceReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.recognizer=PieceReferenceRecognizer(FIXTURES/'piece-references.json')

    def test_reviewed_piece_views(self):
        for name,piece in [('floor-oblique-demo','floor'),('ramp-ghost-demo','ramp'),('cone-overhead-demo','cone')]:
            im=cv2.imread(str(FIXTURES/(name+'.png')))
            match=self.recognizer.recognize(im,(im.shape[1]/2,im.shape[0]/2))
            self.assertIsNotNone(match)
            self.assertEqual(match.piece,piece)
            self.assertGreaterEqual(match.inliers,8)
            self.assertEqual(match.source,'reviewed_visual_reference')

    def test_wrong_target_and_unrelated_frames_abstain(self):
        im=cv2.imread(str(FIXTURES/'ramp-ghost-demo.png'))
        self.assertIsNone(self.recognizer.recognize(im,(20,20)))
        for name in ('front-edit','weapon','pickaxe','cone-ghost-demo'):
            im=cv2.imread(str(FIXTURES/(name+'.png')))
            # Cone must abstain: its few features are concentrated at the HUD,
            # not distributed across the actual ghost mesh.
            self.assertIsNone(self.recognizer.recognize(im,(im.shape[1]/2,im.shape[0]/2)))

    def test_scaled_reference_view(self):
        im=cv2.imread(str(FIXTURES/'ramp-ghost-demo.png'))
        im=cv2.resize(im,None,fx=.8,fy=.8)
        match=self.recognizer.recognize(im,(im.shape[1]/2,im.shape[0]/2))
        self.assertIsNotNone(match)
        self.assertEqual(match.piece,'ramp')

    def test_cone_with_scale_and_brightness_change(self):
        im=cv2.imread(str(FIXTURES/'cone-overhead-demo.png'))
        im=cv2.convertScaleAbs(cv2.resize(im,None,fx=.8,fy=.8),alpha=.8,beta=12)
        match=self.recognizer.recognize(im,(952*.8,520*.8))
        self.assertIsNotNone(match)
        self.assertEqual(match.piece,'cone')

    def test_crosshair_alone_is_not_piece_evidence(self):
        im=cv2.imread(str(FIXTURES/'cone-overhead-demo.png'))
        isolated=im.copy()
        isolated[:]=0
        isolated[470:570,902:1002]=im[470:570,902:1002]
        self.assertIsNone(self.recognizer.recognize(isolated,(952,520)))
