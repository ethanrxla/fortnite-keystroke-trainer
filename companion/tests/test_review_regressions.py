import unittest
from keystroke_lab.input_gate import InputGate
from keystroke_lab.edit_capture import EditCapture
from tests.test_policy_learning import WALL, sample
from keystroke_lab import policy_learning as pl

class ReviewRegressions(unittest.TestCase):
    def test_normal_gameplay_without_edit_observer(self):
        gate=InputGate()
        for key in ('w','mouse_left','r'):
            self.assertTrue(gate.press(key,True))
    def test_chat_send_repeat_and_focus(self):
        gate=InputGate()
        self.assertFalse(gate.press('enter',True))
        self.assertFalse(gate.press('enter',True))
        self.assertFalse(gate.press('w',True))
        gate.release('enter')
        self.assertFalse(gate.press('enter',True))
        self.assertTrue(gate.press('w',True))
        gate.release('enter');gate.press('enter',True)
        gate.focus_lost()
        self.assertTrue(gate.press('w',True))
    def test_pause_survives_focus_loss(self):
        gate=InputGate();gate.press('f8',True);gate.focus_lost()
        self.assertFalse(gate.press('w',True))
    def test_legacy_completion_not_training(self):
        out=pl.blend(WALL,[sample('corner_upper_right',outcome='completed')]*60,'wall')
        self.assertEqual(out['examples_used'],0)
    def test_invalid_capture_id_skips_before_frame_access(self):
        capture=EditCapture('.',enabled=False);capture.enabled=True
        capture.sample(None,{'mode':'editing','projected':True},'invalid')
        self.assertEqual(capture.counts,{})
