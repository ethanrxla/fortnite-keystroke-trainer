import unittest,tempfile
from pathlib import Path
try:
 import sys
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.vision_packages'))
 import cv2
 from keystroke_lab.edit_observation import observe_mode
 from keystroke_lab.edit_window import ContextPipeline
 from keystroke_lab.bind_profiles import ProfileStore
 from keystroke_lab.edit_telemetry import TelemetryReader
except ImportError:cv2=None
@unittest.skipIf(cv2 is None,'optional local vision dependencies missing')
class EditVisionTests(unittest.TestCase):
 def fixture(self,name):return cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision'/(name+'.png')))
 def test_visible_native_modes(self):
  for name,expected in [('close-edit','editing'),('full-edit','editing'),('front-edit','editing'),('blueprint','building'),('live-blueprint','building'),('editable-prompt','editable'),('pickaxe','unknown'),('weapon','unknown')]:
   with self.subTest(name=name):self.assertEqual(observe_mode(self.fixture(name))[0],expected)
 def test_clipped_wall_reference_not_guessed_geometry(self):
  with tempfile.TemporaryDirectory() as d:
   pipe=ContextPipeline(ProfileStore(Path(d)/'binds.json'))
   try:
    state=pipe.process(self.fixture('close-edit'))
    self.assertEqual(state['mode'],'editing');self.assertFalse(state['projected'])
    # A clipped grid has no verified aim: show no side rather than both (the reference follows the aimed side).
    self.assertEqual(state['reference_ids'],[])
    self.assertEqual(pipe.advisor.calls,0)
    self.assertEqual(pipe.process(self.fixture('weapon'))['mode'],'unknown')
    self.assertIsNone(pipe.locked)
   finally:pipe.advisor.close()
 def test_front_grid_projects_real_wall(self):
  with tempfile.TemporaryDirectory() as d:
   pipe=ContextPipeline(ProfileStore(Path(d)/'binds.json'))
   try:
    state=pipe.process(self.fixture('front-edit'));self.assertTrue(state['projected'])
    q=state['observation']['wall_quad'];self.assertLess(abs(q[0][0]-454),20)
    self.assertLess(abs(q[0][1]-149),20)
    self.assertEqual(state['reference_ids'],[]) # nothing before the 0.15 s stability window
    self.assertEqual(pipe.advisor.calls,0)
   finally:pipe.advisor.close()
 def test_wall_suggestion_from_aim_and_position_labelled_unverified(self):
  with tempfile.TemporaryDirectory() as d:
   now=[100.]
   pipe=ContextPipeline(ProfileStore(Path(d)/'binds.json'),clock=lambda:now[0])
   try:
    frame=self.fixture('front-edit')
    pipe.process(frame,captured_at=now[0]);now[0]+=.2
    state=pipe.process(frame,captured_at=now[0])
    self.assertEqual(state['piece_context']['kind'],'wall')
    self.assertEqual(state['reference_ids'],['window_center'])   # crosshair on the centre tile
    self.assertEqual(state['display_edit']['tiles'],[4])
    self.assertFalse(state['verified']);self.assertIn('not yet verified',state['status'])
    self.assertTrue(state['picks'])
   finally:pipe.advisor.close()
 def test_floor_is_observed_with_near_far_context(self):
  from keystroke_lab.piece_observation import VisualObserver
  from tests.test_edit_grid_general import render
  img=render(2,[(470,250),(810,250),(1110,600),(170,600)])
  obs=VisualObserver().observe(img,0.)
  self.assertEqual(obs.piece,'floor')
  self.assertEqual(obs.context['cells'],2)
  self.assertTrue(0<=obs.context['aim'][1]<2)
 def test_telemetry_old_stale_multiple_players_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'log';p.write_text('KT|context|players=1|t=0|px=0|py=0|pz=0|vx=0|vy=0|vz=0|ax=1|ay=0|az=0\n')
   now=[0.];reader=TelemetryReader(p,lambda:now[0],wall_clock=lambda:0.,association='test-single-player');self.assertIsNone(reader.poll())
   with p.open('a') as f:f.write('[1970.01.01-00.00.00:000] KT|context|players=1|t=1|px=1|py=2|pz=3|vx=0|vy=0|vz=0|ax=1|ay=0|az=0\n')
   self.assertEqual(reader.poll()['player_position'],(1.,2.,3.))
   now[0]=.5;self.assertIsNone(reader.poll())
   with p.open('a') as f:f.write('KT|context|players=2\n')
   self.assertIsNone(reader.poll())

@unittest.skipIf(cv2 is None,'optional local vision dependencies missing')
class EditWindowRuntimeTests(unittest.TestCase):
 def run_window(self,fixture):
  import time,types
  from unittest.mock import patch
  from keystroke_lab import edit_window
  frame=cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision'/(fixture+'.png')))
  windows=[]
  class Widget:
   def __init__(self,*args,**kwargs):self.geometry_calls=[];self.callbacks=[];self.items=0;self.withdrawn=0;windows.append(self)
   def __getattr__(self,name):
    if name.startswith('create_'):
     def create(*args,**kwargs):self.items+=1;return self.items
     return create
    return lambda *args,**kwargs:None
   def geometry(self,value):self.geometry_calls.append(value)
   def after(self,ms,fn):self.callbacks.append(fn)
   def mainloop(self):
    for _ in range(200):   # ~5 s: frames must get processed even under full-suite load
     time.sleep(.025)
     if self.callbacks:self.callbacks.pop(0)()
  class Capture:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def grab(self,region):return frame
  class FakeGrabber:
   # stands in for screen_capture.Grabber (dxcam / mss): always the fixture frame, always fresh
   backend='fake'
   def grab(self,rect):return frame,True
   def close(self):pass
  tk=types.SimpleNamespace(Tk=Widget,Toplevel=Widget,Canvas=Widget,LAST='last')
  with tempfile.TemporaryDirectory() as d:
   with patch.object(edit_window,'tk',tk),patch.object(edit_window,'game_rect',lambda:(0,0,1920,1080)),patch.object(edit_window,'make_click_through',lambda _:None),patch.object(edit_window,'exclude_from_capture',lambda _:None),patch.object(edit_window,'single_instance',lambda _:True),patch.object(edit_window,'BASE',Path(d)),patch.dict('sys.modules',{'mss':types.SimpleNamespace(MSS=Capture)}),patch.object(edit_window,'Grabber',FakeGrabber):
    edit_window.run(Path(d)/'binds.json')
  return [g for w in windows for g in w.geometry_calls]
 def test_ring_shows_even_when_the_wall_is_not_projected(self):
  geometries=self.run_window('close-edit')
  self.assertTrue(any(g.startswith('74x74') for g in geometries),geometries)
  # no wall grid under the crosshair -> no corner panel and no lines
  self.assertFalse(any(g.startswith('420x240') for g in geometries),geometries)
 def test_panel_and_lines_follow_a_projected_wall(self):
  geometries=self.run_window('front-edit')
  self.assertTrue(any(g.startswith('74x74') for g in geometries),geometries)
  self.assertTrue(any(g.startswith('420x70') for g in geometries),geometries)
  self.assertTrue(any(g.startswith('1920x1080') for g in geometries),geometries)

class PresenceTests(unittest.TestCase):
 def setUp(self):
  from keystroke_lab.edit_window import Presence
  self.p=Presence(1.0)
 def test_holds_through_a_dropped_frame(self):
  self.assertTrue(self.p.update(True,0.))
  self.assertTrue(self.p.update(False,.5))
  self.assertFalse(self.p.update(False,1.5))
 def test_never_shown_before_first_hit(self):
  self.assertFalse(self.p.update(False,0.))
 def test_reset_hides_immediately(self):
  self.p.update(True,0.);self.p.reset();self.assertFalse(self.p.update(False,.1))

class RouteLineTests(unittest.TestCase):
 quad=((100,100),(400,100),(400,400),(100,400))
 def test_grid_to_screen_corners_and_centre(self):
  from keystroke_lab.edit_window import grid_to_screen
  self.assertAlmostEqual(grid_to_screen(self.quad,0,3)[0],100,1);self.assertAlmostEqual(grid_to_screen(self.quad,0,3)[1],100,1)
  self.assertAlmostEqual(grid_to_screen(self.quad,3,0)[1],400,1)
  self.assertAlmostEqual(grid_to_screen(self.quad,1.5,1.5)[0],250,1)
 def test_route_starts_at_the_crosshair_and_hits_each_target_tile(self):
  from keystroke_lab.edit_window import route_lines
  path,outlines=route_lines({'wall_quad':self.quad,'aim_uv':(.4,2.6)},[6,7])
  self.assertEqual(len(path),3);self.assertEqual(len(outlines),2)
  self.assertAlmostEqual(path[0][0],100+.4*100,1)
 def test_no_lines_without_a_projected_grid(self):
  from keystroke_lab.edit_window import route_lines
  self.assertEqual(route_lines({},[4]),([],[]));self.assertEqual(route_lines(None,[4]),([],[]))

@unittest.skipIf(cv2 is None,'optional local vision dependencies missing')
class GuideContinuityTests(unittest.TestCase):
 def test_slow_frames_and_one_missed_mode_do_not_restart_the_lesson(self):
  from unittest.mock import patch
  frame=cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision/front-edit.png'))
  with tempfile.TemporaryDirectory() as d:
   now=[1.]
   pipe=ContextPipeline(ProfileStore(Path(d)/'binds.json'),clock=lambda:now[0])
   try:
    first=pipe.process(frame)
    now[0]=1.35  # a real processing hitch must not create a different wall
    stable=pipe.process(frame)
    self.assertEqual(first['target_id'],stable['target_id'])
    self.assertTrue(stable['reference_ids'])
    now[0]=1.5
    with patch('keystroke_lab.edit_window.observe_mode',return_value=('unknown',0.)),patch.object(pipe.motion,'follow',return_value=None):
     missed=pipe.process(frame)
    self.assertEqual(missed['mode'],'unknown')  # no invented new observation
    self.assertEqual(pipe.locked,stable['reference_ids'][0])
    self.assertIsNone(pipe.last_attempt)
    now[0]=1.85
    recovered=pipe.process(frame)
    self.assertEqual(recovered['target_id'],stable['target_id'])
    self.assertEqual(recovered['reference_ids'],stable['reference_ids'])
    self.assertTrue(pipe.metrics.gaps)
    now[0]=3.2
    with patch('keystroke_lab.edit_window.observe_mode',return_value=('unknown',0.)),patch.object(pipe.motion,'follow',return_value=None):
     pipe.process(frame)
    self.assertIsNone(pipe.locked)
    self.assertIsNotNone(pipe.last_attempt)
   finally:pipe.advisor.close()
 def test_target_continuity_does_not_cross_piece_changes_or_expiry(self):
  from dataclasses import replace
  from keystroke_lab.piece_observation import PieceObservation,PieceTargetTracker
  obs=PieceObservation(1.,'wall',((0,0),(300,0),(300,300),(0,300)))
  tracker=PieceTargetTracker();target=tracker.update(obs)
  self.assertIsNone(tracker.update(PieceObservation(1.1)))
  self.assertEqual(tracker.update(replace(obs,captured_at=1.5)),target)
  self.assertNotEqual(tracker.update(replace(obs,captured_at=1.6,piece='floor')),target)
  tracker=PieceTargetTracker();target=tracker.update(obs)
  self.assertNotEqual(tracker.update(replace(obs,captured_at=2.3)),target)
  tracker=PieceTargetTracker();target=tracker.update(obs)
  shifted=tuple((x+400,y) for x,y in obs.quad)
  self.assertNotEqual(tracker.update(replace(obs,captured_at=1.1,quad=shifted)),target)
 def test_target_tracks_a_short_detector_dropout(self):
  from keystroke_lab.piece_observation import VisualObserver,GridMotionTracker
  frame=cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision/front-edit.png'))
  obs=VisualObserver().observe(frame,1.)
  tracker=GridMotionTracker();tracker.seed(frame,obs)
  tracked=tracker.follow(frame,1.1)
  self.assertIsNotNone(tracked);self.assertEqual(tracked.source,'optical_flow')
  self.assertEqual(tracked.piece,'wall');self.assertIsNotNone(tracker.follow(frame,2.));self.assertIsNone(tracker.follow(frame,3.1))
 def test_incompatible_upper_goal_recognizes_lower_four_tiles(self):
  from dataclasses import replace
  from keystroke_lab.piece_observation import VisualObserver
  frame=cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision/front-edit.png'))
  obs=VisualObserver().observe(frame,1.)
  class Observer:
   def observe(self,frame,now):return replace(obs,captured_at=now,selected_tiles=(0,1,3,4))
  with tempfile.TemporaryDirectory() as d:
   pipe=ContextPipeline(ProfileStore(Path(d)/'binds.json'),observer=Observer(),clock=lambda:1.)
   try:
    state=pipe.process(frame)
    self.assertEqual(state['reference_ids'],['half_arch_left'])
    self.assertEqual(set(state['display_edit']['tiles']),{0,1,3,4})
   finally:pipe.advisor.close()


class CombinedGuideLayerTests(unittest.TestCase):
 def test_boxes_and_route_remain_independent_and_visible(self):
  from keystroke_lab.guide_layers import TraceGuideLayer,RegionGuideLayer
  class Canvas:
   def __init__(self):self.states={};self.points={}
   def coords(self,item,*coords):self.points[item]=coords
   def itemconfig(self,item,**kwargs):self.states[item]=kwargs.get('state')
  c=Canvas();trace=TraceGuideLayer(c,[1]);regions=RegionGuideLayer(c,[2,3])
  trace.show([0,0,40,40,80,40]);regions.show([[(0,0),(40,0),(40,40)],[(40,0),(80,0),(80,40)]],True)
  self.assertEqual(c.states,{1:'normal',2:'normal',3:'normal'})
  regions.hide();self.assertEqual(c.states[1],'normal')
 def test_upper_corner_has_a_visible_safe_tracing_line(self):
  from keystroke_lab.guide_visuals import layout
  visual=layout({'piece':'wall','cols':3,'tiles':[5,8,7],'name':'Upper corner'},(2.,2.))
  self.assertEqual(len(visual.path),3)
  self.assertGreater(sum(__import__('math').dist(a,b) for a,b in zip(visual.path,visual.path[1:])),.4)

@unittest.skipIf(cv2 is None,'optional local vision dependencies missing')
class RedGridTrackingTests(unittest.TestCase):
 def test_fast_detector_acquires_red_edit_grid(self):
  from tests.test_edit_grid_general import render
  from keystroke_lab.piece_observation import VisualObserver
  frame=render(3,[(330,70),(950,100),(940,590),(340,610)])
  blue=(frame[:,:,0]>frame[:,:,2]*1.22)&(frame[:,:,0]>80)&(frame[:,:,1]>45)
  frame[blue]=[20,30,170]
  obs=VisualObserver().observe(frame,0.)
  self.assertEqual(obs.piece,'wall')
  self.assertEqual(obs.selected_tiles,())
 def test_red_invalid_grid_remains_trackable_without_success(self):
  import numpy as np
  from keystroke_lab.edit_observation import _tile_support
  from keystroke_lab.edit_dictionary import EditAnalyzer
  image=np.zeros((300,300,3),np.uint8);image[:]=[20,30,170]
  self.assertEqual(_tile_support(image,np.diag([100.,100.,1.]),3),9)
  self.assertFalse(EditAnalyzer().finish([6,7,3])['result_confirmed'])


class DisplayLatchTests(unittest.TestCase):
 def snapshot(self):return {'mode':'editing','captured_at':0.,'projected':True,'reference_ids':['corner_upper_right'],'display_edit':{'id':'corner_upper_right'},'profile_id':'a','revision':1}
 def test_at_least_one_second_through_missed_frames(self):
  from keystroke_lab.guide_layers import GuideDisplayLatch
  latch=GuideDisplayLatch();data=self.snapshot()
  self.assertIs(latch.update(data,0.),data)
  missed=dict(data,captured_at=.4,projected=False,reference_ids=[],display_edit=None)
  self.assertTrue(latch.update(missed,1.0)['display_held'])
  self.assertIsNone(latch.update(missed,1.26))
 def test_same_frame_cannot_keep_old_projection_alive(self):
  from keystroke_lab.guide_layers import GuideDisplayLatch
  latch=GuideDisplayLatch();data=self.snapshot();latch.update(data,0.)
  self.assertIsNone(latch.update(data,1.3))
 def test_focus_loss_and_confirmed_weapon_override_hold(self):
  from keystroke_lab.guide_layers import GuideDisplayLatch
  latch=GuideDisplayLatch();data=self.snapshot();latch.update(data,0.)
  self.assertIsNone(latch.update(data,.1,focused=False))
  latch.update(data,0.)
  self.assertIsNone(latch.update(dict(data,negative_mode='weapon'),.1))


@unittest.skipIf(cv2 is None,'optional local vision dependencies missing')
class CornerGuideRegressionTests(unittest.TestCase):
 """The guide the player asked for (IMG_9081): pointing at a wall corner shows that corner edit, three green tiles and
 a numbered 1-2-3 route; oblique close-ups whose border is off screen still get it; a trace already under way keeps a
 guide. Regression for 2026-10-10, when the corner showed one box (window) and close-ups showed nothing."""
 def run_pipeline(self,name,frames=2):
  from keystroke_lab.guide_visuals import layout
  frame=cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision'/(name+'.png')))
  with tempfile.TemporaryDirectory() as d:
   now=[100.]
   pipe=ContextPipeline(ProfileStore(Path(d)/'binds.json'),clock=lambda:now[0])
   try:
    for _ in range(frames):
     state=pipe.process(frame,captured_at=now[0]);now[0]+=.2
   finally:pipe.advisor.close()
  edit=state.get('display_edit')
  return state,edit,(layout(edit,state['observation']['aim_uv']) if edit else None)
 def test_junction_snaps_to_the_corner_edit(self):
  from keystroke_lab.edit_ranker import junction_corner
  self.assertEqual(junction_corner((1.98,1.91)),'corner_upper_right')
  self.assertEqual(junction_corner((1.05,2.1)),'corner_upper_left')
  self.assertEqual(junction_corner((2.2,0.9)),'corner_lower_right')
  self.assertIsNone(junction_corner((1.5,1.5)))
 def test_oblique_close_up_with_border_off_screen_gets_the_corner_guide(self):
  state,edit,visual=self.run_pipeline('live-oblique-edit')
  self.assertTrue(state['projected'])
  self.assertEqual(edit['id'],'corner_upper_right')
  self.assertEqual(sorted(edit['tiles']),[5,7,8])
  self.assertEqual([l for l,_ in visual.labels],['1','2','3'])
 def test_centre_aim_still_gets_the_window(self):
  state,edit,visual=self.run_pipeline('front-edit')
  self.assertEqual(edit['id'],'window_center')
 def test_trace_already_under_way_keeps_a_guide(self):
  state,edit,visual=self.run_pipeline('full-edit')
  self.assertTrue(set(state['observation']['selected_tiles'])<=set(edit['tiles']))
  self.assertEqual(len(visual.labels),len(edit['tiles']))
 def test_partial_grid_abstains_without_a_wall(self):
  from keystroke_lab import edit_observation as eo
  for name in ('blueprint','weapon','pickaxe'):
   f=cv2.imread(str(Path(__file__).parent/'fixtures/edit-vision'/(name+'.png')))
   img=cv2.resize(f,(960,540))
   self.assertIsNone(eo._partial_grid(img,(480.,270.),budget=1),name)
