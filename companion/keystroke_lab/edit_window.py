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
from .keyboard_overlay import game_rect,make_click_through,exclude_from_capture,single_instance
from .bind_profiles import ProfileStore
from .drills import BINDS_FILE
from .edit_observation import observe_mode,EditGridObserver,cue_scores
from .edit_advisor import EditAdvisor,EditContext,safe_path
from .edit_telemetry import TelemetryReader
from .jev_client import JevClient
from .piece_observation import VisualObserver, PieceTargetTracker
from .edit_ranker import Ranker
from .edit_geometry import PieceContext, tiles_to_grid, piece_to_grid
from .edit_dictionary import TargetTracker, RoutePlanner, EditAnalyzer
from .evidence import Evidence, ContextAssembler
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


class ContextPipeline:
    def __init__(self,store,advisor=None,clock=time.monotonic,observer=None,telemetry=None):
        self.store=store;self.clock=clock
        self.advisor=advisor or EditAdvisor(jev=JevClient(domain='edit'),clock=clock)
        self.observer=observer or VisualObserver();self.targets=PieceTargetTracker();self.selection=TargetTracker()
        self.telemetry=telemetry or TelemetryReader(clock=clock);self.metrics=EditAnalyzer()
        self.ranker=Ranker()
        self.locked=None;self.profile_identity=None;self.last_target=None
    def process(self,frame,captured_at=None):
        captured=self.clock() if captured_at is None else captured_at;mode,score=observe_mode(frame);profile=self.store.refresh()
        identity=(profile.profile_id,profile.revision)
        if identity!=self.profile_identity:
            self.selection.reset();self.profile_identity=identity;self.metrics.reset()
        base={'mode':mode,'captured_at':captured,'revision':profile.revision,'projected':False,
              'reference_ids':[],'status':'Align with an editable piece','mode_score':score,
              'session_id':os.environ.get('KT_COACH_SESSION','standalone')}
        telemetry=self.telemetry.poll()
        if self.clock()-captured>.25 or captured>self.clock():return dict(base,mode='unknown',status='Stale observation')
        if mode=='unknown':
            self.locked=None;self.selection.reset();self.targets.last=None;self.last_target=None
            return base
        observation=self.observer.observe(frame,captured) if mode=='editing' else None
        target=self.targets.update(observation) if observation else None
        if not target:
            self.locked=None;self.selection.reset();return base
        if target!=self.last_target:self.metrics.reset();self.last_target=target
        base['snapshot']=ContextAssembler().assemble(profile,base['session_id'],self.clock(),[
            Evidence(f'{target}:{captured}:screen',observation.to_dict(),captured,'screen','observed',1-observation.confidence),
            Evidence(f'{target}:{captured}:orientation',observation.orientation,captured,'screen_projection','derived',1-observation.confidence),
            Evidence(f'{target}:{captured}:ownership',None,captured,'unavailable','unknown',1.)]).to_dict()
        candidates=self.advisor.dictionary.candidates(observation.piece,observation.selected_tiles)
        ctx=PieceContext(**observation.context) if observation.context else None
        # Ranking: crosshair travel from where you aim, Jev's prior for where you stand (side, near/far) and your
        # personal factors (edit_ranker). Game-verified edits win when any fit; until the review catalog has verified
        # them, suggested library edits are offered and labelled unverified.
        kind={'cone':'roof','ramp':'stairs'}.get(observation.piece,observation.piece)
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
        self.locked=self.selection.update((target,observation.orientation),best,observation.selected_tiles,captured)
        context=EditContext(profile.profile_id,profile.revision,captured,mode,target,True,True,
             observation.aim_uv,observation.selected_tiles,drill_edit_id=self.locked,
             source='native_hud_and_screen_projection',piece=observation.piece,orientation=observation.orientation,
             session_id=base['session_id'],dictionary_version=self.advisor.dictionary.version,
             player_position=(telemetry or {}).get('player_position'),view_origin=(telemetry or {}).get('view_origin'),
             view_direction=(telemetry or {}).get('view_direction'))
        self.metrics.sample(captured,observation.aim_uv,observation.selected_tiles)
        advice=self.advisor.request(context)
        if candidates:self.advisor.request(replace(context,drill_edit_id=None,objective="practice"))
        display=None
        if self.locked:
            edit=dict(self.advisor.dictionary.all.get(self.locked) or {})
            pick=next((p for p in picks if p.id==self.locked),None)
            if edit and edit.get('piece')!='ramp':
                # Draw in the observed screen grid: tiles in the ranker's drag order, remapped for 2x2 pieces.
                edit['tiles']=list(tiles_to_grid(ctx,pick.tiles)) if (ctx and pick) else edit.get('tiles',[])
                display=edit
        is_verified=bool(self.locked and self.locked in verified)
        base.update(projected=True,observation=observation.to_dict(),telemetry=telemetry,advice=advice.to_dict(),
                    reference_ids=[self.locked] if self.locked else [],display_edit=display,
                    piece_context=ctx.to_dict() if ctx else None,verified=is_verified,
                    picks=[{'id':p.id,'name':p.name,'cost':p.cost,'travel':p.travel} for p in fitting[:3]],
                    status=('Short safe route | green = select' if is_verified else
                            'Suggested from your aim and position | not yet verified in game') if self.locked
                           else 'No suggested edit fits this selection')
        return base


def run(profile_path=None):
    if not single_instance('Local\\KeystrokeLabEditReference'):return
    import mss
    cv2.setNumThreads(1)
    store=ProfileStore(profile_path or BINDS_FILE);pipeline=ContextPipeline(store)
    shared={'result':None,'rect':None};mutex=threading.Lock();stop=threading.Event()
    def worker():
        with mss.MSS() as capture:
            while not stop.is_set():
                rect=game_rect();result=None
                if rect:
                    l,t,r,b=rect
                    try:
                        captured_at=time.monotonic()
                        result=pipeline.process(np.asarray(capture.grab({'left':l,'top':t,'width':r-l,'height':b-t}))[:,:,:3],captured_at=captured_at)
                    except Exception as exc:
                        result={'mode':'unknown','captured_at':time.monotonic(),'error':type(exc).__name__}
                else:pipeline.locked=None
                with mutex:shared.update(result=result,rect=rect)
                # Latest snapshot only; no frame queue or network on this worker.
                stop.wait(.025)
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
    presence=Presence(1.2);panel_shown=False;lines_shown=False;lines_key=None
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
    panel_approach=canvas.create_line(0,0,1,1,fill='#82a8b8',width=2,dash=(4,4),state='hidden')
    caption_id=canvas.create_text(12,185,anchor='nw',fill='#e3eeed',font=('Segoe UI',10))
    status_id=canvas.create_text(12,208,anchor='nw',fill='#9bb7c1',font=('Segoe UI',9))
    def draw(data):
        from .guide_visuals import layout
        ids=data.get('reference_ids',[]);observation=data.get('observation') or {}
        for group in cells+numbers+[[*routes,*markers,*side_labels]]:
            for item in group:canvas.itemconfig(item,state='hidden')
        canvas.coords(caption_id,12,185 if ids else 40)
        canvas.itemconfig(status_id,state='normal' if ids else 'hidden')
        canvas.itemconfig(heading,text='EDIT GUIDE | '+data['mode'].upper())
        canvas.itemconfig(caption_id,text=data.get('status','Align with an editable piece'))
        canvas.itemconfig(panel_approach,state='hidden')
        if not ids:return
        edit=data.get('display_edit')
        if not edit:return
        visual=layout(edit,observation['aim_uv']);unit=114;x=12;y=40
        piece=(data.get('piece_context') or {}).get('kind','')
        side=['left','centre','right'][(data.get('piece_context') or {}).get('side',1)]
        canvas.itemconfig(heading,text=f"{piece.upper()} | {visual.title.upper()}")
        canvas.itemconfig(status_id,text=f"you: {side} side, {'far' if (data.get('piece_context') or {}).get('far') else 'close'}" + ('' if data.get('verified') else ' | unverified'))
        for i,region in enumerate(visual.regions):
            l,b,r,t=region;item=cells[0][i]
            canvas.coords(item,x+l*unit+2,y+(1-t)*unit+2,x+r*unit-2,y+(1-b)*unit-2)
            canvas.itemconfig(item,state='normal',fill='#27d77b' if i in visual.selected else '#142c34')
        if visual.approach:
            canvas.coords(panel_approach,*[v for u,vv in visual.approach for v in (x+u*unit,y+vv*unit)])
            canvas.itemconfig(panel_approach,state='normal')
        if visual.path:
            coords=[v for u,vv in visual.path for v in (x+u*unit,y+vv*unit)]
            canvas.coords(routes[0],*(coords if len(coords)>2 else coords+coords));canvas.itemconfig(routes[0],state='normal')
            u,v=visual.path[0];canvas.coords(markers[0],x+u*unit-4,y+v*unit-4,x+u*unit+4,y+v*unit+4)
            canvas.itemconfig(markers[0],state='normal')
            for item,(label,(u,v)) in zip(numbers[0],visual.labels):
                canvas.coords(item,x+u*unit,y+v*unit);canvas.itemconfig(item,state='normal',text=label)
        if visual.result_shape:canvas.itemconfig(status_id,text=visual.result_shape)

    # Pool world markers and lines; no create/delete loop while tracing.
    world_regions=[lines_canvas.create_polygon(0,0,1,0,1,1,outline='#27d77b',fill='',width=3,state='hidden') for _ in range(9)]
    world_path=lines_canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,arrow=tk.LAST,state='hidden')
    world_approach=lines_canvas.create_line(0,0,1,1,fill='#82a8b8',width=2,dash=(4,4),state='hidden')
    world_numbers=[lines_canvas.create_text(0,0,text='',fill='white',font=('Segoe UI',10,'bold'),state='hidden') for _ in range(9)]
    def draw_lines(data,rect):
        for item in world_regions+world_numbers+[world_path,world_approach]:lines_canvas.itemconfig(item,state='hidden')
        observation=data.get('observation') or {};ids=data.get('reference_ids') or []
        if not data.get('projected') or not ids:return False
        edit=data.get('display_edit')
        if not edit:return False
        route=RoutePlanner().plan(observation['aim_uv'],edit)
        if not route:return False
        n=1 if edit['piece']=='ramp' else edit['cols'];quad=observation['wall_quad']
        points=[grid_to_screen(quad,*p,n,n) for p in route[1]]
        aim=grid_to_screen(quad,*observation['aim_uv'],n,n)
        lines_canvas.coords(world_approach,*aim,*points[0]);lines_canvas.itemconfig(world_approach,state='normal')
        coords=[v for p in points for v in p]
        lines_canvas.coords(world_path,*(coords if len(coords)>2 else coords+coords));lines_canvas.itemconfig(world_path,state='normal')
        if edit['piece']!='ramp':
            for item,tile in zip(world_regions,edit['tiles']):
                c,r=tile%n,tile//n
                outline=[grid_to_screen(quad,c+dc,r+dr,n,n) for dc,dr in ((0,0),(1,0),(1,1),(0,1))]
                lines_canvas.coords(item,*[v for p in outline for v in p]);lines_canvas.itemconfig(item,state='normal')
        for i,(item,p) in enumerate(zip(world_numbers,points),1):
            lines_canvas.coords(item,*p);lines_canvas.itemconfig(item,state='normal',text=str(i))
        return True

    def poll():
        nonlocal last,shown,last_write,panel_shown,lines_shown,lines_key
        with mutex:data=shared['result'];rect=shared['rect']
        now=time.monotonic()
        fresh=bool(rect and data and data['mode'] in ('editing','building','editable') and 0<=now-data['captured_at']<.25)
        # The ring is the player's aim reference: hold it through dropped frames for the whole edit / build / blueprint.
        ring_on=bool(rect) and presence.update(fresh,now)
        if not rect:presence.reset()
        # The panel is a piece reference: only while the crosshair is on a detected edit grid.
        panel_on=fresh and bool(data.get('projected'))
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
            l,t,r,b=rect;root.geometry(f"420x{240 if data['reference_ids'] else 70}+{l+max(8,min(int((r-l)*.23),r-l-428))}+{t+max(8,min(int((b-t)*.12),b-t-248))}")
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
        if data and now-last_write>1:
            try:
                temporary=BASE/'edit-state.tmp';temporary.write_text(json.dumps(data));temporary.replace(BASE/'edit-state.json')
            except OSError:pass
            last_write=now
        root.after(33,poll)
    root.after(33,poll)
    try:root.mainloop()
    finally:stop.set();pipeline.advisor.close()

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else None)
