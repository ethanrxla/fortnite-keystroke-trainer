import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('validate_edit',ROOT/'tools/validate_edit.py')
validation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)

class RampValidationTests(unittest.TestCase):
    def test_current_ordered_strokes_can_receive_human_evidence(self):
        data=json.loads((ROOT/'shared/edits.json').read_text())
        entries=data[data['pieces']['stairs']['list']]
        actual=[e for e in entries if e.get('strokes')]
        self.assertTrue(actual)
        for edit in actual:
            self.assertTrue(validation.ramp_gesture_recorded(edit),edit['id'])

    def test_masks_alone_and_broken_gestures_cannot_be_promoted(self):
        for strokes in (None,[[0]],[[0,3]],[[1,2]],[[0,2],[2,3]],[[0,4]],[[False,2]]):
            self.assertFalse(validation.ramp_gesture_recorded({'tiles':[0,2],'strokes':strokes}))
        self.assertFalse(validation.ramp_gesture_recorded({'tiles':[0,2],'strokes':[[1,3]]}))

    def test_legacy_routes_require_nodes_and_edges(self):
        self.assertFalse(validation.ramp_gesture_recorded({'gesture':{'routes':[['a','b']]}}))
        self.assertTrue(validation.ramp_gesture_recorded({'gesture':{'routes':[['a','b']],
            'nodes':{'a':[0,0],'b':[0,1]},'edges':[['a','b']]}}))
