import copy
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from keystroke_lab import policy_learning as pl
from keystroke_lab.attempt_evidence import upgrade_record, travel_efficiency
from keystroke_lab.attempt_recorder import AttemptRecorder, default_matcher
from keystroke_lab.attempt_schema import errors
from keystroke_lab.build_pieces import get_piece, WallPiece, FloorPiece, ConePiece, RampPiece
from keystroke_lab.cloud.adapters import KeystrokeTrainerAdapter
from keystroke_lab.edit_dictionary import EditDictionary, TargetTracker
from keystroke_lab.guide_visuals import layout
from keystroke_lab.input_analysis import SequenceAnalyzer
from keystroke_lab.keyboard_overlay import SessionLog
from keystroke_lab.overlay_stats import overlay_layout, session_stats
from keystroke_lab.store import Store
from tests.test_attempt_recorder import frame
from tests.test_attempt_pipeline import record


class PieceObjectTests(unittest.TestCase):
    def test_registry_and_aliases(self):
        for name,kind in [('wall',WallPiece),('floor',FloorPiece),('roof',ConePiece),('stairs',RampPiece)]:
            self.assertIsInstance(get_piece(name),kind)
        with self.assertRaises(ValueError):get_piece('unknown')

    def test_dictionary_round_trips_all_edit_objects(self):
        d=EditDictionary()
        for key,edit in d.definitions.items():
            self.assertEqual(edit.to_dict(),d.all[key])

    def test_floor_cone_diagonals_are_numbered_taps(self):
        for piece in ('floor','cone'):
            e={'id':'diagonal','name':'Diagonal','piece':piece,'cols':2,'tiles':[0,3]}
            visual=layout(e,(.1,.1))
            self.assertEqual(visual.route_mode,'taps')
            self.assertEqual(len(visual.labels),2)
            self.assertEqual(len(visual.regions),4)

    def test_ramp_needs_order_and_directed_edges(self):
        p=get_piece('ramp')
        e={'id':'test','piece':'ramp','name':'Test','tiles':[0,2],
           'gesture':{'nodes':{'a':[0,0],'b':[0,1]},'edges':[['a','b']],'routes':[['a','b']]}}
        self.assertFalse(p.matches(e,[0,2]))
        self.assertTrue(p.matches(e,gesture=('a','b')))
        self.assertFalse(p.matches(e,gesture=('b','a')))
        route=p.route((0,0),e)
        self.assertEqual(route.points,((0.,0.),(0.,2.)))
        self.assertEqual(layout(p.display(e,None),(0,0)).regions,())
        e['gesture']['edges']=[]
        self.assertIsNone(p.route((0,0),e))

    def test_unknown_selection_does_not_reset_lock(self):
        t=TargetTracker(stability=0)
        t.update('wall:1','window_center',(),0)
        t.update('wall:1','window_center',(4,),.1)
        self.assertEqual(t.update('wall:1',None,None,.2),'window_center')


class EvidenceTests(unittest.TestCase):
    def recorder(self):
        return AttemptRecorder('s',matcher=default_matcher(EditDictionary()))

    def test_motion_does_not_create_reset_or_success(self):
        r=self.recorder()
        r.feed(frame(tiles=(4,)),100)
        unknown=frame(tiles=())
        unknown['observation'].update(source='optical_flow',selection_available=False)
        r.feed(unknown,100.1);r.close()
        out=r.closed[-1]
        self.assertIsNone(out['t_reset'])
        self.assertFalse(out['result_confirmed'])
        self.assertFalse(out['complete_observation'])
        self.assertIsNone(out['travel'])
        self.assertEqual(errors(out),[])

    def test_target_and_profile_changes_segment_attempts(self):
        for field,value in [('target_id','wall:2'),('profile_id','b')]:
            r=self.recorder()
            first=dict(frame(tiles=(4,)),target_id='wall:1',profile_id='a',revision=1)
            r.feed(first,1)
            r.feed(dict(first,**{field:value}),1.1)
            self.assertEqual(len(r.closed),1)
            self.assertFalse(r.closed[0]['complete_observation'])
            self.assertNotEqual(r.closed[0]['attempt_id'],r.current['attempt_id'])

    def test_legacy_completion_is_not_promoted(self):
        r=upgrade_record(record())
        self.assertFalse(r['result_confirmed'])
        self.assertEqual(r['outcome'],'unknown')
        self.assertEqual(errors(r),[])

    def test_efficiency_requires_reference_and_complete_observation(self):
        self.assertIsNone(travel_efficiency(record(travel=5)))
        r=upgrade_record(record(travel=4))
        r.update(complete_observation=True,reference_travel=2)
        self.assertEqual(travel_efficiency(r),50)

    def test_opt_in_captures_disabled_by_default(self):
        from keystroke_lab.edit_capture import EditCapture
        with tempfile.TemporaryDirectory() as d:
            capture=EditCapture(Path(d)/'crops')
            capture.sample(None,{},str(uuid.uuid4()))
            capture.close()
            self.assertFalse((Path(d)/'crops').exists())


class DataTests(unittest.TestCase):
    def setUp(self):self.store=Store(':memory:')
    def tearDown(self):self.store.close()

    def test_review_correction_requeues_without_losing_label(self):
        r=record();self.store.add_attempt(r)
        self.store.db.execute('UPDATE edit_attempts SET synced=1')
        self.store.add_label(r['attempt_id'],'relabelled','window_high',result_confirmed=True)
        self.assertEqual(self.store.rows('SELECT synced FROM edit_attempts')[0][0],0)
        out=KeystrokeTrainerAdapter().payload('s',[self.store.attempt(r['attempt_id'])],{},self.store)['attempts'][0]
        self.assertEqual(out['reviewed_edit_id'],'window_high')
        self.assertTrue(out['review_result_confirmed'])
        self.assertEqual(errors(out),[])

    def test_wrong_piece_relabel_rejected(self):
        r=record();self.store.add_attempt(r)
        with self.assertRaises(ValueError):self.store.add_label(r['attempt_id'],'relabelled','floor_hole_near_left')

    def test_old_ack_does_not_hide_new_review(self):
        r=upgrade_record(record());self.store.add_attempt(r)
        adapter=KeystrokeTrainerAdapter();adapter.payload('s',[r],{},self.store)
        self.store.add_label(r['attempt_id'],'approved',result_confirmed=True)
        adapter.mark(self.store,[r['attempt_id']],[])
        self.assertEqual(self.store.rows('SELECT synced FROM edit_attempts')[0][0],0)

    def test_upload_removes_traces_frames_and_key_names(self):
        r=upgrade_record(record(frames=['private.png'],aim_trace=[{'t':1,'u':1,'v':1}]))
        self.store.add_key(100,'secret-key','unmapped')
        body=KeystrokeTrainerAdapter().payload('s',[r],{'consent_frames':True},self.store)
        self.assertNotIn('aim_trace',body['attempts'][0])
        self.assertEqual(body['attempts'][0]['frames'],[])
        self.assertNotIn('secret-key',json.dumps(body))

    def test_estimated_piece_is_not_accuracy(self):
        r=upgrade_record(record(piece='floor',piece_evidence='inferred'))
        r.update(complete_observation=True)
        self.store.add_attempt(r)
        s=session_stats(self.store,'s')
        self.assertEqual((s['attempts'],s['complete'],s['verified']),(1,0,0))

    def test_unconfigured_keys_never_written(self):
        with tempfile.TemporaryDirectory() as d:
            log=SessionLog(Path(d)/'keys',focus=lambda:'Fortnite')
            log.write('unmapped','private-letter',False)
            log.close()
            text=(Path(d)/'keys.events.jsonl').read_text()
            self.assertNotIn('private-letter',text)


class LearningAndLayoutTests(unittest.TestCase):
    def test_session_partition_is_stable_and_disjoint(self):
        samples=[{'session_id':f's{i//5}','attempt_id':str(i)} for i in range(1000)]
        a=pl.partition(samples);b=pl.partition(list(reversed(samples)))
        groups=[{x['session_id'] for x in a[k]} for k in a]
        for i in range(3):
            for j in range(i+1,3):self.assertFalse(groups[i]&groups[j])
        for k in a:self.assertEqual({s['attempt_id'] for s in a[k]},{s['attempt_id'] for s in b[k]})

    def test_publish_gate_requires_all_guards(self):
        base={'top1':.5,'top3':.9,'log_loss':.7}
        good={'examples':30,'reviewed_examples':30,'sessions':3,'partition':'test',
              'top1':.6,'top3':.9,'log_loss':.6,'safety_passed':True}
        self.assertTrue(pl.better(good,base))
        for change in ({'sessions':2},{'reviewed_examples':29},{'partition':'train'},
                       {'safety_passed':False},{'top3':.8},{'log_loss':.8},{'top1':.5}):
            self.assertFalse(pl.better(dict(good,**change),base))

    def test_sequence_fixtures_and_alternatives(self):
        for actions,missing,extra,order in [
            ('abc',0,0,0),('abxc',0,1,0),('ac',1,0,0),('bac',0,0,1),('abbc',0,1,0)]:
            s=SequenceAnalyzer([('a','b','c')])
            for i,a in enumerate(actions):s.observe({a},i)
            out=s.finish()
            self.assertEqual((len(out['actions_not_observed']),out['extra_inputs'],out['order_errors']),(missing,extra,order))
        s=SequenceAnalyzer([('a','b'),('b','a')])
        s.observe({'b'},0);s.observe({'a'},1)
        self.assertTrue(s.finish()['completed'])
        s.gaps=True
        self.assertFalse(s.finish()['graded'])
        self.assertFalse(SequenceAnalyzer().finish()['graded'])

    def test_layout_fits_common_resolutions_and_scales(self):
        for w,h in [(1280,720),(1920,1080),(2560,1440),(3840,2160)]:
            for scale in (1,1.5,2):
                p=overlay_layout((0,0,w,h),scale=scale)
                self.assertGreaterEqual(p.guide_y,8)
                self.assertLessEqual(p.guide_y+240,p.keyboard_y)
                self.assertLessEqual(p.stats_y+p.stats_height,p.keyboard_y+4+3*p.unit)


if __name__=='__main__':unittest.main()
