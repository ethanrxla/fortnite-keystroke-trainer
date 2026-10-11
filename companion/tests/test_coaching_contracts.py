import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from keystroke_lab.bind_profiles import Binding,BindProfile
from keystroke_lab.edit_dictionary import EditDictionary,TargetTracker,RoutePlanner,EditAnalyzer
from keystroke_lab.evidence import validate_choice
from keystroke_lab.input_analysis import InputEvent,KeystrokeAnalyzer,ActionResolver,SequenceAnalyzer
from keystroke_lab.jev_broker import JevBroker
from keystroke_lab.jev_client import JevClient

class BrokerTests(unittest.TestCase):
    def test_two_process_clients_share_one_lease_and_budget(self):
        with tempfile.TemporaryDirectory() as d:
            now=[100.];path=Path(d)/'budget.db'
            a=JevBroker(path,'session',lambda:now[0],cap=2)
            b=JevBroker(path,'session',lambda:now[0],cap=2)
            with ThreadPoolExecutor(2) as pool:
                tokens=list(pool.map(lambda p:p[0].acquire(p[1],'one'),[(a,'edit'),(b,'keystroke')]))
            self.assertEqual(sum(t is not None for t in tokens),1)
            owner=a if tokens[0] else b;owner.finish(next(t for t in tokens if t))
            self.assertEqual(a.attempts(),1);self.assertIsNone(b.acquire('keystroke','two'))
            now[0]+=31
            token=b.acquire('keystroke','three');self.assertIsNotNone(token)
            b.finish(token,60);now[0]+=31
            self.assertIsNone(a.acquire('edit','four'));self.assertEqual(b.attempts(),2)
    def test_no_ai_skips_admission_and_http(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            broker=JevBroker(Path(d)/'b','s')
            client=JevClient(key='test',broker=broker,post=lambda _:self.fail('network'))
            with patch.dict('os.environ',{'KT_NO_AI':'1'}):self.assertIsNone(client.decide({},{}))
            self.assertEqual(broker.attempts(),0)

class DictionaryTests(unittest.TestCase):
    def test_legacy_flags_do_not_certify_patterns(self):
        d=EditDictionary()
        for e in d.edits.values():self.assertEqual(e['validation']['status'],'game_verified')
        self.assertIn('floor_hole_near_left',d.all)
        self.assertIn('roof_two_near',d.all)
    def test_exhaustive_ledger(self):
        from keystroke_lab.edit_dictionary import ROOT
        d=json.loads((ROOT/'shared/edit-coverage.json').read_text())
        for piece,n in [('wall',512),('floor',16),('roof',16)]:
            self.assertEqual([e['mask'] for e in d['pieces'][piece]],list(range(n)))
    def test_stable_choice_locks_during_selection_and_resets(self):
        t=TargetTracker()
        self.assertIsNone(t.update('wall:1','left',(),0))
        self.assertEqual(t.update('wall:1','left',(),.16),'left')
        self.assertEqual(t.update('wall:1','right',(6,),.17),'left')
        self.assertEqual(t.update('wall:1','right',(6,7),.5),'left')
        self.assertIsNone(t.update('wall:2','right',(),.6))
        self.assertEqual(t.update('wall:2','right',(),.76),'right')
    def test_grid_and_ordered_ramp_routes(self):
        planner=RoutePlanner()
        route=planner.plan((.2,.2),{'piece':'floor','cols':2,'tiles':[0,1]})
        self.assertEqual(set(route[2]),{0,1})
        ramp={'piece':'ramp','gesture':{'nodes':{'a':[0,0],'b':[1,1]},'edges':[['a','b']],'routes':[['a','b']]}}
        self.assertEqual(planner.plan((0,0),ramp)[2],('a','b'))
        ramp['gesture']['edges']=[];self.assertIsNone(planner.plan((0,0),ramp))
    def test_observed_tiles_are_not_confirmed_success(self):
        a=EditAnalyzer();a.sample(0,(0,0),(0,));a.sample(.5,(1,1),(0,1))
        result=a.finish((0,1));self.assertFalse(result['complete_observation']);self.assertFalse(result['result_confirmed'])

class InputContractTests(unittest.TestCase):
    def profile(self):return BindProfile('a',35,(Binding('sprint',('1',),'move',True),Binding('rotate',('3',),'build',True),Binding('slot3',('r',),'combat',True),Binding('inventory',('4',),'ui',True),Binding('repair',('b',),'build',True),Binding('edit',('c','v'),'edit',True),Binding('edit_confirm',('c',),'edit',True)))
    def test_shared_and_contextual_verified_actions(self):
        r=ActionResolver(self.profile())
        self.assertEqual(r.resolve('c','editing'),{'edit','edit_confirm'})
        self.assertEqual(r.resolve('v','editing'),{'edit'})
        self.assertEqual(r.resolve('3','building'),{'rotate'})
        self.assertEqual(r.resolve('r','weapon'),{'slot3'})
        self.assertEqual(r.resolve('1','weapon'),{'sprint'})
        self.assertEqual(r.resolve('b','building'),{'repair'})
        self.assertEqual(r.resolve('4','unknown'),{'inventory'})
    def test_held_keys_focus_and_free_practice_never_missing(self):
        a=KeystrokeAnalyzer(self.profile())
        self.assertEqual(a.accept(InputEvent('1','down',0))['kind'],'observed')
        self.assertEqual(a.accept(InputEvent('1','down',.1))['kind'],'held_repeat')
        self.assertEqual(a.accept(InputEvent('print_screen','down',.2))['kind'],'ignored')
        a.accept(InputEvent('','focus_lost',.3));self.assertFalse(a.sequence.finish()['graded'])
    def test_alternate_sequences_and_missing_evidence(self):
        a=SequenceAnalyzer([['wall','floor'],['floor','wall']]);a.observe({'floor'},0);a.observe({'wall'},.1)
        self.assertTrue(a.finish()['completed'])
        a.reset();a.observe({'wall'},0);self.assertEqual(a.finish()['actions_not_observed'],['floor'])
        a.gaps=True;self.assertEqual(a.finish()['actions_not_observed'],[])
    def test_distributions_must_be_complete(self):
        self.assertFalse(validate_choice({'choice':'a','confidence':.9,'probabilities':{'a':.95}}, {'a','b'}))
        self.assertFalse(validate_choice({'choice':'a','confidence':True,'probabilities':{'a':1,'b':0}}, {'a','b'}))
        self.assertTrue(validate_choice({'choice':'a','confidence':.9,'probabilities':{'a':.95,'b':.05}}, {'a','b'}))

class EvidenceIsolationTests(unittest.TestCase):
    def test_deep_snapshot_and_association(self):
        from keystroke_lab.evidence import Evidence,ContextAssembler
        profile=BindProfile('a',1,());raw={'points':[[1,2]]}
        e=Evidence('one',raw,1.,'screen');raw['points'][0][0]=99
        self.assertEqual(e.value['points'][0][0],1)
        with self.assertRaises(TypeError):e.value['points']=()
        events=[e,Evidence('old',0,0.,'log'),Evidence('other',0,1.,'log',profile_id='b'),
                Evidence('duplicate',1,1.,'screen'),Evidence('duplicate',2,1.,'screen')]
        snap=ContextAssembler().assemble(profile,'session',1.1,events)
        self.assertEqual([e.id for e in snap.evidence],['one'])
        self.assertEqual(snap.to_dict()['evidence'][0]['value'],{'points':[[1,2]]})
    def test_old_profile_response_rejected_even_same_revision(self):
        from keystroke_lab.analysis import Analyzer
        from types import SimpleNamespace
        from threading import Event,Thread
        started=Event();release=Event()
        class Client:
            available=True;shadow=True;model='test';model_version='test'
            def decide(self,*args,**kwargs):
                started.set();release.wait(2)
                return {'e0':{'choice':'deliberate','confidence':1.,'probabilities':{'deliberate':1.,'slip':0.,'noise':0.,'insufficient_evidence':0.}}}
        a=Analyzer(SimpleNamespace(profile_id='a',profile_revision=1),jev=Client())
        a.add_stray('p',1,[]);result=[]
        worker=Thread(target=lambda:result.extend(a.resolve(1)));worker.start();self.assertTrue(started.wait(1))
        a.invalidate(1,'b');release.set();worker.join(2)
        self.assertEqual(result,[]);self.assertEqual(a.findings,[])
    def test_empty_and_oversized_batches_never_call(self):
        c=JevClient(key='test',post=lambda _:self.fail('network'))
        self.assertIsNone(c.decide({},{}));self.assertIsNone(c.decide({},{str(i):{} for i in range(9)}))
        self.assertEqual(c.calls,0)
    def test_disconnected_route_is_not_drawn_through_untouched_region(self):
        route=RoutePlanner().route((.1,.1),{'piece':'floor','cols':2,'tiles':[0,3]})
        self.assertEqual(route.mode, 'taps')  # no continuous line through untouched cells
