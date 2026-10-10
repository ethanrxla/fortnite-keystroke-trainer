import unittest
from dataclasses import replace
from keystroke_lab.edit_advisor import EditAdvisor, EditContext, safe_path, intersect_wall
from tests.dictionary_fixture import verified_dictionary
class EditAdviceTests(unittest.TestCase):
    def setUp(self):
        self.advisor=EditAdvisor(dictionary=verified_dictionary(),clock=lambda:10.)
        self.context=EditContext('local',35,10.,'editing','wall',True,True,(1.5,1.5),drill_edit_id='window_center',ownership='self')
    def tearDown(self):self.advisor.close()
    def test_evidence_gates(self):
        for change in [dict(mode='combat'),dict(target_verified=False),dict(geometry_verified=False),dict(observed_at=9.),dict(observed_at=11.),dict(aim_uv=(4.,1.)),dict(ownership='other')]:
            with self.subTest(change=change):self.assertEqual(self.advisor.local(replace(self.context,**change)).status,'hidden')
    def test_drill_and_mirrors(self):
        self.assertEqual(self.advisor.local(self.context).edit_id,'window_center')
        self.assertNotIn('door',self.advisor.dictionary.edits)
        for e in self.advisor.dictionary.edits.values():
            if e.get('mirror_of'):self.assertEqual({2-t%3+3*(t//3) for t in e['tiles']},set(self.advisor.dictionary.edits[e['mirror_of']]['tiles']))
    def test_no_goal_from_cursor(self):
        self.assertEqual(self.advisor.local(replace(self.context,drill_edit_id=None)).status,'reference')
    def test_revision_changes_cache(self):
        self.assertNotEqual(self.advisor.fingerprint(self.context),self.advisor.fingerprint(replace(self.context,revision=36)))
    def test_malformed_and_uncertain_model(self):
        for answer in [None,[],{},dict(choice='window_center',confidence=.1,probabilities={'window_center':1.}),dict(choice='window_center',confidence=.99,probabilities={'window_center':float('nan')})]:
            with self.subTest(answer=answer):self.assertNotEqual(self.advisor._consume(self.context,answer).status,'suggested')
    def test_routes_only_cross_selected_tiles(self):
        for e in self.advisor.dictionary.edits.values():
            route=safe_path((1.5,1.5),e['tiles']);self.assertIsNotNone(route,e['id'])
            _,points,order=route
            for p,t in zip(points,order):
                self.assertTrue(t%3+.15-1e-8<=p[0]<=t%3+.85+1e-8)
                self.assertTrue(t//3+.15-1e-8<=p[1]<=t//3+.85+1e-8)
            for a,b in zip(points,points[1:]):
                for i in range(101):
                    x=a[0]+(b[0]-a[0])*i/100;y=a[1]+(b[1]-a[1])*i/100
                    self.assertIn(int(x)+3*int(y),e['tiles'])
    def test_invalid_projection(self):self.assertIsNone(intersect_wall(None,None,{}))
    def test_no_ai(self):
        self.assertEqual(self.advisor.request(replace(self.context,drill_edit_id=None,objective='peek',threat={'known':True})).status,'reference')
        self.assertEqual(self.advisor.calls,0)
