import json
import tempfile
import threading
import unittest
from pathlib import Path
from keystroke_lab.bind_profiles import ProfileStore, parse
from keystroke_lab.keyboard_overlay import KeyTracker, explain
from keystroke_lab.analysis import Analyzer, template_tip, JEV_COOLDOWN, LLM_COOLDOWN
from keystroke_lab.jev_client import JevClient


class VerifiedControls(unittest.TestCase):
    def test_migration_only_confirms_user_sprint(self):
        p = parse({'sprint':'shift','edit':'c'}, confirm_sprint=True)
        self.assertEqual(p.primary()['sprint'], '1')
        self.assertEqual([b.action for b in p.bindings if b.verified], ['sprint'])
        self.assertFalse(KeyTracker(p, ['edit']).grade)

    def test_profiles_alternates_revision_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            a = ProfileStore(Path(folder)/'a.json')
            b = ProfileStore(Path(folder)/'b.json')
            old = a.snapshot
            a.update('reset', ['mouse_right','wheel_down'], 'edit')
            self.assertNotEqual(old, a.snapshot)
            self.assertGreater(a.snapshot.revision, old.revision)
            self.assertNotIn('wheel_down', KeyTracker(b.snapshot).bound)
            self.assertIn('reset', KeyTracker(a.snapshot).actions['wheel_down'])
            mirror = ProfileStore(a.path)
            a.update('sprint', ['1'], 'move')
            self.assertEqual(mirror.refresh(), a.snapshot)

    def test_unmapped_movement_repeats_focus_loss(self):
        t = KeyTracker({'forward':'w','sprint':'1','edit':'c'}, ['edit'])
        self.assertEqual(t.press('w', 0)[0], 'ok')
        self.assertEqual(t.press('w', .04)[0], 'repeat')
        self.assertEqual(t.press('1', .05)[0], 'ok')
        self.assertEqual(t.press('x', .06)[0], 'unmapped')
        self.assertNotIn('meant', explain('unmapped', 'x', t))
        self.assertEqual(t.press('print_screen', .07)[0], 'ignore')
        t.focus_lost()
        self.assertEqual(t.press('w', .08)[0], 'ok')

    def test_port_returns_updated_snapshot_and_tracker_invalidates(self):
        import urllib.request
        from keystroke_lab.bind_server import start
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'binds.json')
            tracker=KeyTracker(store.snapshot)
            server=start(lambda:store.snapshot.primary(),lambda:[],[],binds_file=store.path,
                         port=0,secret='mock-token',store=store)
            base='http://127.0.0.1:'+str(server.server_address[1])
            try:
                request=urllib.request.Request(base+'/binds',json.dumps({'action':'sprint','keys':['1','wheel_up']}).encode(),
                                               {'X-KT-Token':'mock-token','Content-Type':'application/json'})
                with urllib.request.urlopen(request) as response:
                    changed=json.load(response)['profile']
                with urllib.request.urlopen(base+'/binds') as response:
                    active=json.load(response)
                self.assertEqual(changed,active['profile'])
                tracker.set_profile(store.refresh())
                self.assertEqual(tracker.press('wheel_up',0)[0],'ok')
                self.assertEqual(tracker.profile_revision,active['profile']['revision'])
            finally:
                server.shutdown();server.server_close()

    def test_companion_analysis_accepts_verified_alternates_only(self):
        from keystroke_lab.bind_profiles import BindMap
        from keystroke_lab.profile import to_actions
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(Path(folder)/'binds.json')
            self.assertEqual(to_actions([{'t':0,'kind':'key','name':'q'}],BindMap(store.snapshot)),[])
            store.update('reset',['mouse_right','wheel_down'],'edit')
            self.assertEqual(to_actions([{'t':0,'kind':'key','name':'wheel_down'}],BindMap(store.snapshot)),[(0,'reset')])


class SafeAnalysis(unittest.TestCase):
    def analyzer(self, answer):
        return Analyzer(KeyTracker({'edit':'c'}), jev=JevClient(key='mock', post=lambda b: {'answers': {'e0':answer}}), llm=lambda *a:'')

    def test_probability_does_not_replace_confidence(self):
        a=self.analyzer({'choice':'slip','confidence':.1,'probabilities':{'slip':.99}})
        a.add_stray('x',0,[('c','edit')])
        f=a.resolve(0)[0]
        self.assertEqual(f['confidence'],.1)
        self.assertTrue(f['uncertainty'])
        self.assertEqual(template_tip(a.findings),'')

    def test_malformed_answers_and_offline_abstain(self):
        for value in [None, [], {'choice':'slip','confidence':float('nan'),'probabilities':{}}, {'choice':'invented','confidence':1,'probabilities':{'invented':1}}]:
            a=self.analyzer(value)
            a.add_stray('x',0,[('c','edit')])
            self.assertTrue(a.resolve(0)[0]['uncertainty'])
        calls=[]
        a=Analyzer(KeyTracker({'edit':'c'}),jev=JevClient(key='',post=lambda x:calls.append(x)),llm=lambda *a:calls.append(a))
        a.add_stray('x',0,[('c','edit')]);a.resolve(0);a.tip(0)
        self.assertEqual(calls,[])

    def test_single_flight_and_stale_profile_discard(self):
        entered, release = threading.Event(), threading.Event()
        def post(body):
            entered.set();release.wait(2)
            return {'answers': {'e0': {'choice':'deliberate','confidence':.9,'probabilities':{'deliberate':.9}}}}
        a=Analyzer(KeyTracker({'edit':'c'}),jev=JevClient(key='mock',post=post),llm=lambda *a:'')
        for i in range(3):a.add_stray('x',i,[])
        self.assertTrue(a.claim(0))
        worker=threading.Thread(target=lambda:a.resolve(0));worker.start();self.assertTrue(entered.wait(1))
        self.assertFalse(a.claim(100))
        a.invalidate(1);release.set();worker.join();a.release_claim()
        self.assertEqual(a.findings,[])

    def test_attempt_cap_and_cooldowns(self):
        c=JevClient(key='mock',post=lambda b:{'answers':{}},max_calls=30)
        for _ in range(40):c.decide({}, {})
        self.assertEqual(c.calls,30)
        self.assertEqual(JEV_COOLDOWN,30)
        self.assertEqual(LLM_COOLDOWN,300)
