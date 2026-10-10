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
    for _ in range(100):
     time.sleep(.025)
     if self.callbacks:self.callbacks.pop(0)()
  class Capture:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def grab(self,region):return frame
  tk=types.SimpleNamespace(Tk=Widget,Toplevel=Widget,Canvas=Widget,LAST='last')
  with tempfile.TemporaryDirectory() as d:
   with patch.object(edit_window,'tk',tk),patch.object(edit_window,'game_rect',lambda:(0,0,1920,1080)),patch.object(edit_window,'make_click_through',lambda _:None),patch.object(edit_window,'exclude_from_capture',lambda _:None),patch.object(edit_window,'single_instance',lambda _:True),patch.object(edit_window,'BASE',Path(d)),patch.dict('sys.modules',{'mss':types.SimpleNamespace(MSS=Capture)}):
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
