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


def grid_to_screen(quad,u,v):
    """Screen point for a wall-grid coordinate (u right, v up, both 0..3) given the observed outer quad
    (screen corners of image-top-left, top-right, bottom-right, bottom-left, as WallObservation.wall_quad)."""
    unit=np.array([[0,0],[3,0],[3,3],[0,3]],np.float32)
    H=cv2.getPerspectiveTransform(unit,np.asarray(quad,np.float32).reshape(4,2))
    x,y=cv2.perspectiveTransform(np.array([[[u,3-v]]],np.float32),H)[0,0]
    return float(x),float(y)


def route_lines(observation,tiles,aim=None):
    """Edit lines on the observed piece, in screen pixels: the short safe route from the crosshair through the tiles,
    plus each target tile's outline. Empty unless the grid was projected."""
    quad=observation.get('wall_quad') if observation else None
    aim=aim or (observation or {}).get('aim_uv')
    if not quad or len(quad)!=4 or not aim:return [],[]
    route=safe_path(tuple(aim),tiles)
    if route is None:return [],[]
    _,points,_=route
    path=[grid_to_screen(quad,*aim)]+[grid_to_screen(quad,*p) for p in points]
    outlines=[[grid_to_screen(quad,c+dc,r+dr) for dc,dr in ((0,0),(1,0),(1,1),(0,1))] for c,r in ((t%3,t//3) for t in tiles)]
    return path,outlines


class ContextPipeline:
    def __init__(self,store,advisor=None,clock=time.monotonic):
        self.store=store;self.advisor=advisor or EditAdvisor(jev=JevClient(),clock=clock)
        self.clock=clock;self.observer=EditGridObserver();self.telemetry=TelemetryReader(clock=clock)
        self.locked=None;self.active=False;self.profile_identity=None
    def process(self,frame):
        captured=self.clock();mode,score=observe_mode(frame);profile=self.store.refresh();telemetry=self.telemetry.poll()
        identity=(profile.profile_id,profile.revision)
        if identity!=self.profile_identity:self.locked=None;self.profile_identity=identity
        if mode=='unknown':self.active=False;self.locked=None;return {'mode':'unknown','captured_at':captured,'revision':profile.revision,'edit_cue_scores':cue_scores(frame,['confirm','reset']),'build_cue_scores':cue_scores(frame,['change-material','rotate'],(0.,.35,.23,.76))}
        observation=self.observer.observe(frame,captured) if mode=='editing' else None
        # Mode confidence and geometric support are separate. A clipped grid stays a reference.
        projected=observation is not None and observation.reason=='native_edit_grid_observed' and observation.supported_cells>=8 and observation.confidence>=.90
        if projected:
            # Follow the crosshair: the side updates as you aim across the wall (it used to lock to the first side seen).
            self.locked=choose_corner(observation.aim_uv[0],self.locked)
        telemetry=self.telemetry.poll()
        context=EditContext(profile.profile_id,profile.revision,captured,mode,
             target_id='visible_native_edit_grid' if projected else None,target_verified=projected,geometry_verified=projected,
             aim_uv=observation.aim_uv if projected else (),selected_tiles=observation.selected_tiles if projected else (),
             drill_edit_id=self.locked if projected else None,source='native_hud_and_screen_projection',
             player_position=(telemetry or {}).get('player_position'),view_origin=(telemetry or {}).get('view_origin'),
             view_direction=(telemetry or {}).get('view_direction'))
        advice=self.advisor.request(context)
        return {'mode':mode,'mode_score':score,'captured_at':captured,'revision':profile.revision,'projected':projected,
                'observation':observation.to_dict() if observation else None,'telemetry':telemetry,'advice':advice.to_dict(),
                'reference_ids':[self.locked] if self.locked else []}

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
                    try:result=pipeline.process(np.asarray(capture.grab({'left':l,'top':t,'width':r-l,'height':b-t}))[:,:,:3])
                    except Exception as exc:
                        result={'mode':'unknown','captured_at':time.monotonic(),'error':type(exc).__name__}
                else:pipeline.locked=None
                with mutex:shared.update(result=result,rect=rect)
                # Latest snapshot only; no frame queue or network on this worker.
                stop.wait(.12)
    thread=threading.Thread(target=worker,daemon=True,name='local-edit-observer');thread.start()
    root=tk.Tk();root.title('Training Lab - Edit reference');root.overrideredirect(True)
    root.attributes('-topmost',True);root.attributes('-transparentcolor','#010203');root.configure(bg='#010203')
    canvas=tk.Canvas(root,width=420,height=240,bg='#010203',highlightthickness=0);canvas.pack();root.update();make_click_through(root);root.withdraw()
    ring=tk.Toplevel(root);ring.overrideredirect(True);ring.attributes('-topmost',True)
    ring.attributes('-transparentcolor','#010203');ring.configure(bg='#010203')
    ring_canvas=tk.Canvas(ring,width=74,height=74,bg='#010203',highlightthickness=0);ring_canvas.pack()
    ring_canvas.create_oval(5,5,69,69,outline='#ed2539',width=4)
    ring.update();make_click_through(ring);ring.withdraw()
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
        numbers.append([canvas.create_text(0,0,fill='white',font=('Segoe UI',11,'bold')) for _ in range(3)])
        routes.append(canvas.create_line(0,0,1,1,fill='#f6f7a0',width=3,arrow=tk.LAST))
        markers.append(canvas.create_oval(0,0,1,1,fill='#ffdc46',outline=''))
        side_labels.append(canvas.create_text(12+j*200,162,anchor='nw',fill='#b8dadd',font=('Segoe UI',9)))
    caption_id=canvas.create_text(12,185,anchor='nw',fill='#e3eeed',font=('Segoe UI',10))
    status_id=canvas.create_text(12,208,anchor='nw',fill='#9bb7c1',font=('Segoe UI',9))
    def draw(data):
        ids=data['reference_ids'];verified=data['projected'];observation=data.get('observation') or {}
        canvas.itemconfig(heading,text='UPPER CORNER | '+('EDIT' if data['mode']=='editing' else 'EDITABLE TARGET' if data['mode']=='editable' else 'BUILD'))
        for j in range(2):
            present=j<len(ids)
            for item in cells[j]+numbers[j]+[routes[j],markers[j],side_labels[j]]:canvas.itemconfig(item,state='normal' if present else 'hidden')
            if not present:continue
            edit_id=ids[j];edit=pipeline.advisor.dictionary.edits[edit_id];x=12+j*200;y=40;unit=38
            aim=observation.get('aim_uv') if verified else None
            route=safe_path(tuple(aim) if aim else (1.5,1.5),edit['tiles'])
            for tile,item in enumerate(cells[j]):
                col,row=tile%3,tile//3;xx=x+col*unit;yy=y+(2-row)*unit
                canvas.coords(item,xx+2,yy+2,xx+unit-2,yy+unit-2)
                canvas.itemconfig(item,fill='#27d77b' if tile in edit['tiles'] else '#142c34')
            if route:
                _,points,order=route
                if not verified:points=tuple((tile%3+.5,tile//3+.5) for tile in order)
                coords=[v for p in points for v in (x+p[0]*unit,y+(3-p[1])*unit)]
                canvas.coords(routes[j],*coords)
                for i,p in enumerate(points):
                    tile=order[i]
                    canvas.coords(numbers[j][i],x+(tile%3+.5)*unit,y+(2.5-tile//3)*unit)
                    canvas.itemconfig(numbers[j][i],text=str(i+1))
            if aim:canvas.coords(markers[j],x+aim[0]*unit-4,y+(3-aim[1])*unit-4,x+aim[0]*unit+4,y+(3-aim[1])*unit+4)
            else:canvas.itemconfig(markers[j],state='hidden')
            canvas.itemconfig(side_labels[j],text='Left' if 'left' in edit_id else 'Right')
        canvas.itemconfig(caption_id,text='Short safe route | green = select' if verified else 'Reference only | aim tile is not verified')
        canvas.itemconfig(status_id,text='Native edit controls observed' if data['mode']=='editing' else 'Native Edit prompt observed | reference only' if data['mode']=='editable' else 'Blueprint HUD observed | preview geometry unknown')
    def draw_lines(data,rect):
        l,t,r,b=rect;lines_canvas.delete('all')
        observation=data.get('observation') or {}
        ids=data.get('reference_ids') or []
        if not data.get('projected') or not ids:return False
        path,outlines=route_lines(observation,pipeline.advisor.dictionary.edits[ids[0]]['tiles'])
        if not path:return False
        for outline in outlines:
            lines_canvas.create_polygon([v for p in outline for v in p],outline='#27d77b',fill='',width=3)
        lines_canvas.create_line([v for p in path for v in p],fill='#f6f7a0',width=5,arrow=tk.LAST,arrowshape=(16,20,8))
        for i,p in enumerate(path[1:],1):
            lines_canvas.create_oval(p[0]-11,p[1]-11,p[0]+11,p[1]+11,fill='#0b1720',outline='#f6f7a0',width=2)
            lines_canvas.create_text(p[0],p[1],text=str(i),fill='white',font=('Segoe UI',10,'bold'))
        return True
    def poll():
        nonlocal last,shown,last_write,panel_shown,lines_shown,lines_key
        with mutex:data=shared['result'];rect=shared['rect']
        now=time.monotonic()
        fresh=bool(rect and data and data['mode'] in ('editing','building','editable') and now-data['captured_at']<.6)
        # The ring is the player's aim reference: hold it through dropped frames for the whole edit / build / blueprint.
        ring_on=bool(rect) and presence.update(fresh,now)
        if not rect:presence.reset()
        # The corner panel is a wall reference: only while the crosshair is on a detected wall grid.
        panel_on=fresh and bool(data['projected']) and bool(data['reference_ids'])
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
            l,t,r,b=rect;root.geometry(f'420x240+{l+int((r-l)*.23)}+{t+int((b-t)*.12)}')
            if not panel_shown:root.deiconify();panel_shown=True
            if data['captured_at']!=lines_key:
                lines.geometry(f'{r-l}x{b-t}+{l}+{t}');lines_canvas.configure(width=r-l,height=b-t)
                lines_key=data['captured_at']
                if draw_lines(data,rect) and not lines_shown:lines.deiconify();lines_shown=True
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
