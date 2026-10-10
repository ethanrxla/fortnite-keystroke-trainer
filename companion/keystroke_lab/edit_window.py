"""Local reference guide: visual mode evidence precedes geometry and bounded AI.
Screen capture is local, focused-game only, and never uploaded. No game inputs/memory.
"""
import sys
from pathlib import Path
VISION=Path(__file__).resolve().parents[1]/'.vision_packages'
if VISION.exists():sys.path.insert(0,str(VISION))
import json,time,threading
from dataclasses import replace
import tkinter as tk
import cv2,numpy as np
from .keyboard_overlay import game_rect,make_click_through,exclude_from_capture,single_instance,ROWS,BOTTOM_MARGIN,LEFT_MARGIN
from .bind_profiles import ProfileStore
from .drills import BINDS_FILE
from .edit_observation import observe_mode,EditGridObserver,cue_scores
from .edit_advisor import EditAdvisor,EditContext,safe_path
from .edit_telemetry import TelemetryReader
from .jev_client import JevClient
from .piece_observation import VisualObserver, PieceTargetTracker, GridMotionTracker
from .edit_ranker import Ranker, junction_corner, IntentMap
from .edit_geometry import PieceContext, tiles_to_grid, piece_to_grid, grid_to_tiles
from .build_pieces import PatternTable, piece_for
from .edit_dictionary import TargetTracker, RoutePlanner, RouteTracker, EditAnalyzer
from .evidence import Evidence, ContextAssembler
from .guide_layers import TraceGuideLayer, RegionGuideLayer, GuideDisplayLatch
from .attempt_recorder import AttemptRecorder, AttemptLog, default_matcher
from .frame_dataset import FrameDataset
from .screen_capture import Grabber
from .pieces import catalog_key
import os
BASE=Path(__file__).resolve().parents[1]

LEFT_CORNER = 'corner_upper_left'
RIGHT_CORNER = 'corner_upper_right'


def choose_corner(aim_u, current=None):
    """The corner edit on the side of the wall the crosshair is on. A dead band around the middle (1.35..1.65 of 3 tiles)
    keeps the current side, so the reference does not flicker while you cross the centre line. With no side yet, the
    nearer half wins. Never returns both sides."""
    if aim_u < 1.35:
        return LEFT_CORNER
    if aim_u > 1.65:
        return RIGHT_CORNER
    return current or (LEFT_CORNER if aim_u < 1.5 else RIGHT_CORNER)


class Presence:
    """Keeps something shown through brief detection dropouts. Mode detection is per frame, so one missed frame (motion
    blur, a flash, a slow capture) used to hide the red ring mid-edit; it now holds for `grace` seconds after the last hit."""
    def __init__(self,grace=1.5):self.grace=grace;self.last=None
    def update(self,active,now):
        if active:self.last=now
        return self.last is not None and now-self.last<=self.grace
    def reset(self):self.last=None


def grid_to_screen(quad,u,v,cols=3,rows=3):
    """Screen point for a wall-grid coordinate (u right, v up, both 0..3) given the observed outer quad
    (screen corners of image-top-left, top-right, bottom-right, bottom-left, as WallObservation.wall_quad)."""
    unit=np.array([[0,0],[cols,0],[cols,rows],[0,rows]],np.float32)
    H=cv2.getPerspectiveTransform(unit,np.asarray(quad,np.float32).reshape(4,2))
    x,y=cv2.perspectiveTransform(np.array([[[u,rows-v]]],np.float32),H)[0,0]
    return float(x),float(y)


def route_lines(observation,tiles,aim=None,cols=3):
    """Edit lines on the observed piece, in screen pixels: the short safe route from the crosshair through the tiles,
    plus each target tile's outline. Empty unless the grid was projected."""
    quad=observation.get('wall_quad') if observation else None
    aim=aim or (observation or {}).get('aim_uv')
    if not quad or len(quad)!=4 or not aim:return [],[]
    route=safe_path(tuple(aim),tiles,cols=cols)
    if route is None:return [],[]
    _,points,_=route
    path=[grid_to_screen(quad,*aim,cols,cols)]+[grid_to_screen(quad,*p,cols,cols) for p in points]
    outlines=[[grid_to_screen(quad,c+dc,r+dr,cols,cols) for dc,dr in ((0,0),(1,0),(1,1),(0,1))] for c,r in ((t%cols,t//cols) for t in tiles)]
    return path,outlines


def lattice_offset(held,new,n=3,tol=.25):
    """(dx, dy) whole tiles by which grid quad `new` is grid quad `held` shifted (both screen quads, TL TR BR BL), or
    None when they are not the same lattice. (0, 0) = the same grid."""
    unit=np.float32([[0,0],[n,0],[n,n],[0,n]])
    try:H=cv2.getPerspectiveTransform(unit,np.float32(held).reshape(4,2))
    except Exception:return None
    d=cv2.perspectiveTransform(np.float32(new).reshape(1,4,2),np.linalg.inv(H))[0]-unit
    shift=np.round(d.mean(0))
    if np.abs(d-shift).max()>tol:return None
    return int(shift[0]),int(shift[1])


class ContextPipeline:
    FULL_EVERY=3      # tracked frames between full detections (see process: fast path)
    SHIFT_VOTES=3     # detections in a row that must agree before the held grid moves by whole tiles
    def __init__(self,store,advisor=None,clock=time.monotonic,observer=None,telemetry=None,async_detect=False):
        self.store=store;self.clock=clock
        self.advisor=advisor or EditAdvisor(jev=JevClient(domain='edit'),clock=clock)
        self.observer=observer or VisualObserver();self.targets=PieceTargetTracker();self.selection=TargetTracker(stability=.06)   # 60 ms before a new pick shows (was 150); hysteresis already damps flicker
        self.telemetry=telemetry or TelemetryReader(clock=clock);self.metrics=EditAnalyzer()
        self.ranker=Ranker();self.intent=IntentMap();self.patterns=PatternTable();self.motion=GridMotionTracker();self.previous_display=None;self.last_attempt=None
        self.locked=None;self.profile_identity=None;self.last_target=None
        self.last_mode_seen=-float('inf');self.frames_since_full=0
        # async_detect: full detection (~80-130 ms) runs on its own thread with its own observer; every frame takes the
        # fast path (track + re-read, ~10 ms) and a finished detection re-seeds the tracker. Tests use the synchronous path.
        self.async_detect=async_detect;self.pending=None;self.shift_vote=None;self.held=None
        if async_detect:
            from concurrent.futures import ThreadPoolExecutor
            self.detector=ThreadPoolExecutor(max_workers=1,thread_name_prefix='edit-detect');self.bg_observer=VisualObserver()
        self.routes=RouteTracker()
    def reset_tracking(self):
        self.routes.reset()
        self.locked=None;self.selection.reset();self.targets.last=None;self.last_target=None
        self.motion.reset();self.previous_display=None;self.last_mode_seen=-float('inf')
    def _hold_lattice(self,det,det_frame):
        """A finished detection that is the held grid moved by whole tiles (same wall, anchored a row or column off:
        the lattice is periodic) does not move the guide until SHIFT_VOTES detections in a row agree. Until then the
        detection is re-anchored onto the held lattice, so tracking stays fresh and the crosshair keeps its tile.
        Live 2026-10-10: the grid jumped one row between detections and the guide flipped between the upper and lower
        corner with the crosshair still. Returns the observation to seed with (None = keep tracking as is)."""
        held=self.held
        if held is None or held.piece!=det.piece or det.captured_at-held.captured_at>.5:
            self.shift_vote=None;return det
        n=3 if det.piece=='wall' else 2
        off=lattice_offset(held.quad,det.quad,n)
        if off is None or off==(0,0):
            self.shift_vote=None;return det
        votes=self.shift_vote[1]+1 if self.shift_vote and self.shift_vote[0]==off else 1
        if votes>=self.SHIFT_VOTES:
            self.shift_vote=None;return det
        self.shift_vote=(off,votes)
        unit=np.float32([[0,0],[n,0],[n,n],[0,n]])
        H=cv2.getPerspectiveTransform(unit,np.float32(det.quad).reshape(4,2))
        quad=cv2.perspectiveTransform((unit-np.float32(off)).reshape(1,4,2),H)[0]
        return self.observer.from_quad(det_frame,replace(det,quad=tuple(map(tuple,quad.tolist()))),det.captured_at)

    def process(self,frame,captured_at=None):
        captured=self.clock() if captured_at is None else captured_at;mode,score=observe_mode(frame,throttle=self.async_detect);profile=self.store.refresh()
        identity=(profile.profile_id,profile.revision)
        if identity!=self.profile_identity:
            self.reset_tracking();self.profile_identity=identity;self.metrics.reset()
        mode_track=None
        if mode=='unknown' and self.previous_display:
            cues=cue_scores(frame,['confirm','reset'])
            if min(cues)>=.32 and sum(cues)/2>=.40:
                mode_track=self.motion.follow(frame,captured)
                if mode_track is not None:mode='editing'
        if mode!='unknown':self.last_mode_seen=captured
        base={'mode':mode,'captured_at':captured,'revision':profile.revision,'projected':False,
              'reference_ids':[],'status':'Align with an editable piece','mode_score':score,
              'session_id':os.environ.get('KT_COACH_SESSION','standalone'),'profile_id':profile.profile_id,'last_attempt':self.last_attempt}
        telemetry=self.telemetry.poll()
        if self.clock()-captured>.25 or captured>self.clock():return dict(base,mode='unknown',status='Stale observation')
        if mode=='unknown':
            # A missed HUD cue is not an observed confirm/cancel. Keep the
            # tracker and lesson available for reacquisition; the display latch
            # holds the original snapshot without refreshing its evidence age.
            if captured-self.last_mode_seen<=1.25:
                self.metrics.gaps=True
                return dict(base,tracking='reacquiring')
            self.finish_attempt(captured,profile)
            base['last_attempt']=self.last_attempt
            self.reset_tracking()
            return base
        # Fast path: during one edit consecutive frames barely move. Follow the last detected grid with optical flow
        # and re-read aim + selection from it (~10 ms); a full detection (~80-130 ms) runs every FULL_EVERY frames,
        # after 0.5 s, or whenever following fails, so drift and new pieces are still caught.
        fast=None
        if self.async_detect and mode=='editing' and mode_track is None:
            if self.pending is not None and self.pending[0].done():
                future,det_frame,_=self.pending;self.pending=None
                try:det=future.result()
                except Exception:det=None
                if det is not None and det.piece!='unknown':
                    det=self._hold_lattice(det,det_frame)
                    if det is not None:self.motion.seed(det_frame,det);self.frames_since_full=0
            if self.motion.observation is not None and captured-self.motion.detected_at<=1.:
                moved=self.motion.follow(frame,captured,verify=False)
                fast=self.observer.from_quad(frame,moved,captured) if moved else None
            # Detection runs back to back on its own thread (one in flight at a time): a grid the tracker carried from
            # a wrong start is corrected within one detection (~100 ms) instead of waiting for 12 tracked frames.
            if self.pending is None:
                snapshot=frame.copy()
                self.pending=(self.detector.submit(self.bg_observer.observe,snapshot,captured),snapshot,captured)
            observation=fast
            if fast is not None:self.frames_since_full+=1;self.held=fast
        elif (mode=='editing' and mode_track is None and self.motion.observation is not None
                and self.frames_since_full<self.FULL_EVERY and captured-self.motion.detected_at<=.5):
            moved=self.motion.follow(frame,captured)
            fast=self.observer.from_quad(frame,moved,captured) if moved else None
        if self.async_detect and mode=='editing' and mode_track is None:
            pass
        elif fast is not None:
            observation=fast;self.frames_since_full+=1
        else:
            observation=mode_track or (self.observer.observe(frame,captured) if mode=='editing' else None)
            self.frames_since_full=0
        if observation:base['detection_reason']=observation.reason if fast is None else 'tracked_refined'
        tracked=mode_track is not None
        if observation and observation.piece!='unknown' and not tracked and fast is None:self.motion.seed(frame,observation)
        elif mode=='editing' and not tracked and not self.async_detect:
            observation=self.motion.follow(frame,captured);tracked=observation is not None
        target=self.targets.update(observation) if observation else None
        if not target:
            self.metrics.gaps=True
            if mode=='editing' and self.previous_display and captured-self.previous_display['captured_at']<=.75:
                return dict(self.previous_display,captured_at=captured,projected=False,tracking='reacquiring',status='Tracking edit | reacquiring target')
            if self.previous_display and captured-self.previous_display['captured_at']<=1.25:
                self.metrics.gaps=True
                return dict(base,tracking='reacquiring')
            self.locked=None;self.selection.reset();return base
        if target!=self.last_target:
            self.finish_attempt(captured,profile);self.metrics.reset();self.last_target=target
        base['snapshot']=ContextAssembler().assemble(profile,base['session_id'],self.clock(),[
            Evidence(f'{target}:{captured}:screen',observation.to_dict(),captured,observation.source,'derived' if tracked else 'observed',1-observation.confidence),
            Evidence(f'{target}:{captured}:orientation',observation.orientation,captured,'screen_projection','derived',1-observation.confidence),
            Evidence(f'{target}:{captured}:ownership',None,captured,'unavailable','unknown',1.)]).to_dict()
        candidates=self.advisor.dictionary.candidates(observation.piece,observation.selected_tiles)
        ctx=PieceContext(**observation.context) if observation.context else None
        # Ranking: crosshair travel from where you aim, Jev's prior for where you stand (side, near/far) and your
        # personal factors (edit_ranker). Game-verified edits win when any fit; until the review catalog has verified
        # them, suggested library edits are offered and labelled unverified.
        kind=catalog_key(observation.piece) or observation.piece
        picks=self.ranker.rank(kind,ctx.aim,ctx.side,ctx.far) if ctx else []
        verified={e['id'] for e in candidates}
        fitting=[p for p in picks if set(observation.selected_tiles)<=set(tiles_to_grid(ctx,p.tiles))] if ctx else []
        best=next((p.id for p in fitting if p.id in verified),None) or (fitting[0].id if fitting else None)
        if best is None and candidates:
            ranked=[]
            for edit in candidates:
                route=RoutePlanner().plan(observation.aim_uv,edit)
                if route:ranked.append((route[0],edit['id']))
            best=min(ranked)[1] if ranked else None
        if self.locked and best and self.locked!=best and ctx:
            # Hysteresis (EditGuide.verse AutoLock): keep the current edit while it costs within 0.25 of the best.
            costs={p.id:p.cost for p in fitting}
            if self.locked in costs and costs[self.locked]<=costs.get(best,0)+.25:best=self.locked
        if ctx:
            # The player's aim map (shared/edit-intent.json -> IntentMap, one O(1) array read): corners at corners,
            # half wall on the top-middle tile, window in the centre, door bottom-middle... Applied after hysteresis so
            # it wins; skipped when the mapped edit does not contain what is already selected (Jev's ranking decides).
            intent=self.intent.lookup(observation.piece,ctx.aim)
            if intent and intent in self.advisor.dictionary.all:
                tiles=set(tiles_to_grid(ctx,self.advisor.dictionary.all[intent].get('tiles',[])))
                if set(observation.selected_tiles)<=tiles:best=intent
        self.locked=self.selection.update((target,observation.orientation),best,observation.selected_tiles,captured)
        # Free-practice suggestions cannot establish player intent.
        if observation.selected_tiles and not tracked:
            # Mid-trace: keep guiding with an edit that contains what is already selected. Tiles are compared in the
            # screen grid (tiles_to_grid maps 2x2 pieces). Exact match first, else the best-ranked edit that contains
            # the selection (selecting before the guide locked used to leave the guide empty).
            sel=set(observation.selected_tiles)
            grid=lambda e:set(tiles_to_grid(ctx,e.get('tiles',[]))) if ctx else set(e.get('tiles',[]))
            current=self.advisor.dictionary.all.get(self.locked,{})
            if not self.locked or not sel<=grid(current):
                # The pattern table (build_pieces) knows every real shape; a rare one is coached as its common
                # `prefer` edit. Else the best-ranked edit that contains the selection.
                exact=None
                if observation.piece in ('wall','floor','cone'):
                    own=grid_to_tiles(ctx,tuple(sorted(sel))) if (ctx and observation.piece!='wall') else tuple(sorted(sel))
                    outcome=self.patterns.match(piece_for(observation.piece),own)
                    shown=self.patterns.display(outcome.pattern) if outcome.valid else None
                    if shown and shown.id in self.advisor.dictionary.all:exact=shown.id
                self.locked=exact or (fitting[0].id if fitting else None)
                self.selection.active=self.locked
        context=EditContext(profile.profile_id,profile.revision,captured,mode,target,True,True,
             observation.aim_uv,observation.selected_tiles,drill_edit_id=self.locked,
             source='native_hud_and_screen_projection',piece=observation.piece,orientation=observation.orientation,
             session_id=base['session_id'],dictionary_version=self.advisor.dictionary.version,
             player_position=(telemetry or {}).get('player_position'),view_origin=(telemetry or {}).get('view_origin'),
             view_direction=(telemetry or {}).get('view_direction'))
        if not tracked:self.metrics.sample(captured,observation.aim_uv,observation.selected_tiles)
        else:self.metrics.gaps=True
        advice=self.advisor.request(context)
        if candidates:self.advisor.request(replace(context,drill_edit_id=None,objective="practice"))
        display=None
        if self.locked:
            edit=dict(self.advisor.dictionary.all.get(self.locked) or {})
            pick=next((p for p in picks if p.id==self.locked),None)
            if edit:
                # Draw in the observed screen grid: tiles in the ranker's drag order, remapped for 2x2 pieces.
                edit['tiles']=list(tiles_to_grid(ctx,pick.tiles)) if (ctx and pick and edit['piece']!='ramp') else edit.get('tiles',[])
                if ctx and edit['piece']=='ramp' and edit.get('strokes'):
                    edit['strokes']=[list(tiles_to_grid(ctx,stroke)) for stroke in edit['strokes']]
                    edit['tiles']=[t for stroke in edit['strokes'] for t in stroke]
                display=edit
        paths=()
        if display:
            paths=self.routes.update((identity,target,observation.orientation,display['id'],tuple(sorted(display.get('tiles',()))),
                                      tuple(tuple(s) for s in display.get('strokes',()))),
                                     observation.aim_uv,display,observation.selected_tiles)
        else:self.routes.reset()
        is_verified=bool(self.locked and self.locked in verified)
        base.update(projected=True,target_id=target,observation=observation.to_dict(),telemetry=telemetry,advice=advice.to_dict(),
                    reference_ids=[self.locked] if self.locked else [],display_edit=display,guide_strokes=paths,
                    piece_context=ctx.to_dict() if ctx else None,verified=is_verified,
                    picks=[{'id':p.id,'name':p.name,'cost':p.cost,'travel':p.travel} for p in fitting[:3]],
                    status=('Short safe route | green = select' if is_verified else
                            'Suggested from your aim and position | not yet verified in game') if self.locked
                           else 'No suggested edit fits this selection')
        base['tracking']='motion' if tracked else 'detected'
        self.previous_display=dict(base)
        return base
    def finish_attempt(self,now,profile):
        if not self.metrics.samples or not self.previous_display:return
        edit=self.previous_display.get('display_edit')
        if edit:
            self.last_attempt=dict(self.metrics.finish(edit.get('tiles',[])),edit_id=edit['id'],
                                   profile_id=profile.profile_id,profile_revision=profile.revision,
                                   ended_at=now,success='unverified')
        self.metrics.reset()


def run(profile_path=None):
    if not single_instance('Local\\KeystrokeLabEditReference'):return
    import mss
    cv2.setNumThreads(1)
    store=ProfileStore(profile_path or BINDS_FILE);pipeline=ContextPipeline(store,async_detect=True)
    shared={'result':None,'rect':None};mutex=threading.Lock();stop=threading.Event()
    # Every edit attempt (open edit mode -> confirm / reset / leave) goes to sessions/edit-<session>.attempts.jsonl
    # for the collector, the review page and the cloud sync. Recording never blocks or fails the guide.
    session=os.environ.get('KT_COACH_SESSION') or time.strftime('%Y%m%d-%H%M%S')
    recorder=AttemptRecorder(session,sink=AttemptLog(BASE/'sessions'/f'edit-{session}.attempts.jsonl').write,
                             matcher=default_matcher(table=pipeline.patterns),catalog_version=pipeline.advisor.dictionary.version)
    frames=FrameDataset(session)
    def record(result,utc):
        try:recorder.feed(result,utc)
        except Exception:recorder.current=None
    def worker():
        # dxcam (DXGI duplication, ~2 ms) with mss fallback; an unchanged screen is not re-processed. Frames are taken
        # as fast as the display produces them, capped at ~125 per second; the slow full detection runs on a
        # background thread inside the pipeline (async_detect), so each frame here is the fast path only.
        grabber=Grabber()
        last_start=0.
        try:
            while not stop.is_set():
                wait=.008-(time.monotonic()-last_start)
                if wait>0:stop.wait(wait)
                last_start=time.monotonic()
                rect=game_rect();result=None
                if rect:
                    try:
                        captured_at=time.monotonic();captured_utc=time.time()
                        frame,fresh=grabber.grab(rect)
                        if frame is None or not fresh:continue
                        result=pipeline.process(frame,captured_at=captured_at)
                        result['processing_ms']=round(1000*(time.monotonic()-captured_at),1)
                        result['capture']=grabber.backend
                        record(result,captured_utc)
                        # Training data: a few edit-mode frames a second with their auto labels, after the guide
                        # has its result (never delays it). companion/data/frames/<session>/, local only.
                        frames.maybe_save(frame,result,captured_utc,recorder.current['attempt_id'] if recorder.current else None)
                    except Exception as exc:
                        result={'mode':'unknown','captured_at':time.monotonic(),'error':type(exc).__name__}
                else:
                    pipeline.reset_tracking();pipeline.metrics.reset()
                    record({'mode':'unknown'},time.time())
                    stop.wait(.1)
                with mutex:shared.update(result=result,rect=rect)
        finally:grabber.close()
    thread=threading.Thread(target=worker,daemon=True,name='local-edit-observer');thread.start()
    root=tk.Tk();root.title('Training Lab - Edit reference');root.overrideredirect(True)
    root.attributes('-topmost',True);root.attributes('-transparentcolor','#010203');root.configure(bg='#010203')
    canvas=tk.Canvas(root,width=420,height=240,bg='#010203',highlightthickness=0);canvas.pack();root.update();make_click_through(root);exclude_from_capture(root);root.withdraw()
    ring=tk.Toplevel(root);ring.overrideredirect(True);ring.attributes('-topmost',True)
    ring.attributes('-transparentcolor','#010203');ring.configure(bg='#010203')
    ring_canvas=tk.Canvas(ring,width=74,height=74,bg='#010203',highlightthickness=0);ring_canvas.pack()
    ring_canvas.create_oval(5,5,69,69,outline='#ed2539',width=4)
    ring.update();make_click_through(ring);exclude_from_capture(ring);ring.withdraw()
    # Full-game overlay for the edit lines drawn on the piece itself. Excluded from screen capture so the lines never
    # feed back into the grid detection (the ring stays capturable: the observer finds the aim point from it).
    lines=tk.Toplevel(root);lines.overrideredirect(True);lines.attributes('-topmost',True)
    lines.attributes('-transparentcolor','#010203');lines.configure(bg='#010203')
    lines_canvas=tk.Canvas(lines,width=2,height=2,bg='#010203',highlightthickness=0);lines_canvas.pack(fill='both',expand=True)
    lines.update();make_click_through(lines);exclude_from_capture(lines);lines.withdraw()
    presence=Presence(1.2);display_latch=GuideDisplayLatch(1.25);panel_shown=False;lines_shown=False;lines_key=None
    last=None;shown=False;last_write=0.
    cells=[];numbers=[];routes=[];markers=[];side_labels=[]
    canvas.create_rectangle(0,0,420,230,fill='#0b1720',outline='#416574')
    heading=canvas.create_text(12,12,anchor='nw',fill='#e9ffff',font=('Segoe UI',11,'bold'))
    for j in range(2):
        cells.append([canvas.create_rectangle(0,0,1,1,outline='#38515c') for _ in range(9)])
        numbers.append([canvas.create_text(0,0,fill='white',font=('Segoe UI',11,'bold')) for _ in range(9)])
        routes.append(canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,arrow=tk.LAST))
        markers.append(canvas.create_oval(0,0,1,1,fill='#ffdc46',outline=''))
        side_labels.append(canvas.create_text(12+j*200,162,anchor='nw',fill='#b8dadd',font=('Segoe UI',9)))
    panel_approach=canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,dash=(4,4),arrow=tk.LAST,state='hidden')
    panel_paths=[routes[0]]+[canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,arrow=tk.LAST,state='hidden') for _ in range(8)]
    panel_approaches=[panel_approach]+[canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,dash=(4,4),arrow=tk.LAST,state='hidden') for _ in range(8)]
    caption_id=canvas.create_text(12,185,anchor='nw',fill='#e3eeed',font=('Segoe UI',10))
    status_id=canvas.create_text(12,208,anchor='nw',fill='#9bb7c1',font=('Segoe UI',9))
    def draw(data):
        from .guide_visuals import layout
        ids=data.get('reference_ids',[]);observation=data.get('observation') or {}
        for group in cells+numbers+[[*routes,*markers,*side_labels,*panel_paths,*panel_approaches]]:
            for item in group:canvas.itemconfig(item,state='hidden')
        canvas.coords(caption_id,12,185 if ids else 40)
        canvas.itemconfig(status_id,state='normal' if ids else 'hidden')
        canvas.itemconfig(heading,text='EDIT GUIDE | '+data['mode'].upper())
        canvas.itemconfig(caption_id,text=data.get('status','Align with an editable piece'))
        canvas.itemconfig(panel_approach,state='hidden')
        if not ids:return
        edit=data.get('display_edit')
        if not edit:return
        visual=layout(edit,observation['aim_uv'],data.get('guide_strokes'));unit=114;x=12;y=40
        piece=(data.get('piece_context') or {}).get('kind','')
        side=['left','centre','right'][(data.get('piece_context') or {}).get('side',1)]
        canvas.itemconfig(heading,text=f"{piece.upper()} | {visual.title.upper()}")
        canvas.itemconfig(status_id,text=f"you: {side} side, {'far' if (data.get('piece_context') or {}).get('far') else 'close'}" + ('' if data.get('verified') else ' | unverified'))
        for i,region in enumerate(visual.regions):
            l,b,r,t=region;item=cells[0][i]
            canvas.coords(item,x+l*unit+2,y+(1-t)*unit+2,x+r*unit-2,y+(1-b)*unit-2)
            canvas.itemconfig(item,state='normal',fill='#27d77b' if i in visual.selected else '#142c34')
        for item,approach in zip(panel_approaches,visual.approaches):
            canvas.coords(item,*[v for u,vv in approach for v in (x+u*unit,y+vv*unit)])
            canvas.itemconfig(item,state='normal')
        for item,path in zip(panel_paths,visual.strokes):
            coords=[v for u,vv in path for v in (x+u*unit,y+vv*unit)]
            canvas.coords(item,*(coords if len(coords)>2 else coords+coords));canvas.itemconfig(item,state='normal')
        if visual.path:
            u,v=visual.path[0];canvas.coords(markers[0],x+u*unit-4,y+v*unit-4,x+u*unit+4,y+v*unit+4)
            canvas.itemconfig(markers[0],state='normal')
            for item,(label,(u,v)) in zip(numbers[0],visual.labels):
                canvas.coords(item,x+u*unit,y+v*unit);canvas.itemconfig(item,state='normal',text=label)
        if visual.result_shape:canvas.itemconfig(status_id,text=visual.result_shape)

    # Pool world markers and lines; no create/delete loop while tracing.
    world_regions=[lines_canvas.create_polygon(0,0,1,0,1,1,outline='#27d77b',fill='',width=3,state='hidden') for _ in range(9)]
    world_path=lines_canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,arrow=tk.LAST,state='hidden')
    world_approach=lines_canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,dash=(4,4),arrow=tk.LAST,state='hidden')
    world_paths=[world_path]+[lines_canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,arrow=tk.LAST,state='hidden') for _ in range(8)]
    world_approaches=[world_approach]+[lines_canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,dash=(4,4),arrow=tk.LAST,state='hidden') for _ in range(8)]
    world_numbers=[lines_canvas.create_text(0,0,text='',fill='white',font=('Segoe UI',10,'bold'),state='hidden') for _ in range(9)]
    world_markers=[lines_canvas.create_oval(0,0,1,1,outline='#f6f7a0',fill='#142c34',width=2,state='hidden') for _ in range(9)]
    world_start=lines_canvas.create_oval(0,0,1,1,fill='#ffdc46',outline='',state='hidden')
    trace_layers=[TraceGuideLayer(lines_canvas,[item]) for item in world_paths]
    region_layer=RegionGuideLayer(lines_canvas,world_regions)
    def draw_lines(data,rect):
        for item in world_regions+world_numbers+world_markers+world_paths+world_approaches+[world_start]:lines_canvas.itemconfig(item,state='hidden')
        observation=data.get('observation') or {};ids=data.get('reference_ids') or []
        if not data.get('projected') or not ids:return False
        edit=data.get('display_edit')
        if not edit:return False
        paths=data.get('guide_strokes')
        if paths is None:paths=RoutePlanner(inset=.35).strokes(observation['aim_uv'],edit)
        if not paths:return False
        n=edit['cols'];quad=observation['wall_quad']
        screen_paths=[[grid_to_screen(quad,*p,n,n) for p in path] for path in paths]
        points=[p for path in screen_paths for p in path]
        aim=grid_to_screen(quad,*observation['aim_uv'],n,n)
        previous=aim
        for layer,approach,path in zip(trace_layers,world_approaches,screen_paths):
            lines_canvas.coords(approach,*previous,*path[0]);lines_canvas.itemconfig(approach,state='normal')
            layer.show([v for p in path for v in p])
            previous=path[-1]
        outlines=[]
        for tile in edit['tiles']:
            c,r=tile%n,tile//n
            outlines.append([grid_to_screen(quad,c+dc,r+dr,n,n) for dc,dr in ((0,0),(1,0),(1,1),(0,1))])
        region_layer.show(outlines,True)
        lines_canvas.coords(world_start,aim[0]-4,aim[1]-4,aim[0]+4,aim[1]+4);lines_canvas.itemconfig(world_start,state='normal')
        for item,p in zip(world_markers,points):
            lines_canvas.coords(item,p[0]-12,p[1]-12,p[0]+12,p[1]+12);lines_canvas.itemconfig(item,state='normal')
        for i,(item,p) in enumerate(zip(world_numbers,points),1):
            lines_canvas.coords(item,*p);lines_canvas.itemconfig(item,state='normal',text=str(i));lines_canvas.tag_raise(item)
        return True

    def poll_once():
        nonlocal last,shown,last_write,panel_shown,lines_shown,lines_key
        with mutex:data=shared['result'];rect=shared['rect']
        now=time.monotonic()
        fresh=bool(rect and data and data['mode'] in ('editing','building','editable') and 0<=now-data['captured_at']<.60)
        # The ring is the player's aim reference: hold it through dropped frames for the whole edit / build / blueprint.
        ring_on=bool(rect) and presence.update(fresh,now)
        if not rect:presence.reset()
        raw_data=data
        display_data=display_latch.update(data,now,focused=bool(rect))
        panel_on=display_data is not None or (fresh and bool(data.get("projected")))
        if display_data is not None:data=display_data;ring_on=True
        if ring_on:
            if rect:
                l,t,r,b=rect
                ring.geometry(f'74x74+{l+(r-l)//2-37}+{t+(b-t)//2-37}')
            if not shown:ring.deiconify();shown=True
        elif shown:ring.withdraw();shown=False
        if panel_on:
            observation=data.get('observation') or {}
            key=(data['mode'],data['projected'],tuple(data['reference_ids']),tuple(round(v,2) for v in observation.get('aim_uv',())),tuple(observation.get('selected_tiles',())),data['revision'])
            if key!=last:draw(data);last=key
            l,t,r,b=rect
            u=max(22,min(42,int((b-t)/54*1.5)))
            panel_height=240 if data['reference_ids'] else 70
            panel_x=l+int((r-l)*LEFT_MARGIN)
            panel_y=max(t+8,b-int((b-t)*BOTTOM_MARGIN)-(len(ROWS)+4)*u-panel_height-8)
            root.geometry(f"420x{panel_height}+{panel_x}+{panel_y}")
            if not panel_shown:root.deiconify();panel_shown=True
            if data['captured_at']!=lines_key:
                lines.geometry(f'{r-l}x{b-t}+{l}+{t}');lines_canvas.configure(width=r-l,height=b-t)
                lines_key=data['captured_at']
                if draw_lines(data,rect):
                    if not lines_shown:lines.deiconify();lines_shown=True
                elif lines_shown:lines.withdraw();lines_shown=False
        else:
            if panel_shown:root.withdraw();panel_shown=False;last=None
            if lines_shown:lines.withdraw();lines_shown=False;lines_key=None
        data=raw_data
        if data and now-last_write>1:
            try:
                temporary=BASE/'edit-state.tmp';temporary.write_text(json.dumps(data));temporary.replace(BASE/'edit-state.json')
            except OSError:pass
            last_write=now
    def poll():
        try:poll_once()
        except Exception:
            import traceback
            with (BASE/'edit-display-error.log').open('a') as errors:errors.write(traceback.format_exc())
        finally:root.after(8,poll)      # redraw check every 8 ms (was 33): new results reach the screen sooner
    root.after(8,poll)
    try:root.mainloop()
    finally:
        stop.set();pipeline.advisor.close()
        try:recorder.close(time.time())
        except Exception:pass

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else None)
