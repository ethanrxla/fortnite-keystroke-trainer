"""Context-aware edit advice. Geometry and hard evidence gates precede Jev.
No inventory writes, game input, screen capture, or API calls on the input thread.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import threading
import time

ROOT=Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class EditContext:
    player_id: str
    revision: int
    observed_at: float
    mode: str
    target_id: str | None = None
    target_verified: bool = False
    geometry_verified: bool = False
    aim_uv: tuple = ()
    selected_tiles: tuple = ()
    objective: str | None = None
    drill_edit_id: str | None = None
    player_position: tuple | None = None
    view_origin: tuple | None = None
    view_direction: tuple | None = None
    wall_pose: dict | None = None
    ownership: str = 'unknown'
    threat: dict | None = None
    source: str = 'unknown'
    piece: str = 'wall'
    orientation: str = 'screen_local'
    session_id: str = ''
    dictionary_version: int = 2

@dataclass(frozen=True)
class EditAdvice:
    status: str
    revision: int
    reason: str
    edit_id: str | None = None
    path: tuple = ()
    approach: tuple = ()
    travel: float = 0.
    probabilities: dict = field(default_factory=dict)
    confidence: float | None = None
    uncertain: bool = True
    source: str = 'local'
    evidence: dict = field(default_factory=dict)
    def to_dict(self):return asdict(self)

from .edit_dictionary import EditDictionary, RoutePlanner

def intersect_wall(view_origin,view_direction,pose):
    """Verified XYZ wall pose: origin is lower-left; right/up are unit axes.
    Returns normalized 3x3 coordinates or None. Never infer pose from a snapped grid.
    """
    try:
        origin=tuple(pose['origin']);right=tuple(pose['right']);up=tuple(pose['up']);normal=tuple(pose['normal'])
        width=float(pose['width']);height=float(pose['height'])
        vectors=[view_origin,view_direction,origin,right,up,normal]
        if width<=0 or height<=0 or any(len(v)!=3 or not all(math.isfinite(x) for x in v) for v in vectors):return None
        dot=lambda a,b:sum(x*y for x,y in zip(a,b))
        if any(abs(dot(v,v)-1)>.01 for v in [right,up,normal]) or abs(dot(right,up))>.01 or abs(dot(right,normal))>.01 or abs(dot(up,normal))>.01:return None
        denominator=dot(view_direction,normal)
        if abs(denominator)<1e-6:return None
        delta=tuple(x-y for x,y in zip(origin,view_origin));t=dot(delta,normal)/denominator
        if t<=0:return None
        hit=tuple(view_origin[i]+view_direction[i]*t-origin[i] for i in range(3))
        uv=(3*dot(hit,right)/width,3*dot(hit,up)/height)
        return uv if all(0<=v<3 for v in uv) else None
    except (KeyError,TypeError,ValueError,OverflowError):return None


def _routes(tiles,cols=3):
    wanted=set(tiles)
    def walk(route):
        if len(route)==len(wanted):yield route;return
        last=route[-1]
        for tile in sorted(wanted-set(route)):
            if abs(last%cols-tile%cols)+abs(last//cols-tile//cols)==1:yield from walk(route+(tile,))
    for tile in sorted(wanted):yield from walk((tile,))


def safe_path(aim,tiles,inset=.15,cols=3):
    """Minimize length over connected tile orders and inset waypoints.
    The approach occurs before selection; selection segments stay in selected tiles.
    This is a short safe route, not a claim of a globally shortest continuous path.
    """
    best=None
    for order in _routes(tiles,cols):
        current=aim;points=[]
        for tile in order:
            c,r=tile%cols,tile//cols
            current=(min(max(current[0],c+inset),c+1-inset),min(max(current[1],r+inset),r+1-inset))
            points.append(current)
        length=math.dist(aim,points[0])+sum(math.dist(a,b) for a,b in zip(points,points[1:]))
        if best is None or length<best[0]:best=(length,tuple(points),order)
    return best

class EditAdvisor:
    def __init__(self,dictionary=None,jev=None,clock=time.monotonic):
        self.dictionary=dictionary or EditDictionary();self.jev=jev;self.clock=clock
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='edit-advice')
        self._lock=threading.Lock();self._pending=None;self._cache={};self._last_call=-math.inf;self.calls=0
    def _abstain(self,c,reason):return EditAdvice('hidden',c.revision,reason)
    def local(self,c):
        if self.clock()-c.observed_at>.25 or self.clock()<c.observed_at:return self._abstain(c,'stale_observation')
        if c.mode not in ('building','editing','editable'):return self._abstain(c,'build_or_edit_mode_unverified')
        if not c.target_verified or not c.target_id:return self._abstain(c,'target_wall_unverified')
        if not c.geometry_verified:return self._abstain(c,'wall_projection_unverified')
        if len(c.aim_uv)!=2 or not all(math.isfinite(v) and 0<=v<(3 if c.piece=='wall' else 1 if c.piece=='ramp' else 2) for v in c.aim_uv):return self._abstain(c,'crosshair_off_target')
        if c.wall_pose is not None:
            measured=intersect_wall(c.view_origin,c.view_direction,c.wall_pose)
            if measured is None or math.dist(measured,c.aim_uv)>.08:return self._abstain(c,'screen_world_projection_disagreement')
        if c.ownership=='other':return self._abstain(c,'wall_not_editable_by_player')
        if c.drill_edit_id:
            edit=self.dictionary.edits.get(c.drill_edit_id)
            if edit is None or edit['piece']!=c.piece:return self._abstain(c,'drill_edit_unconfirmed')
            if not set(c.selected_tiles)<=set(edit['tiles']):return EditAdvice('reference',c.revision,'Selection differs from the drill target.',edit['id'],evidence={'observed_selection':c.selected_tiles,'target_selection':edit['tiles']})
            return self._make(c,edit,'Follow this drill target.','drill')
        if c.selected_tiles:
            matching=self.dictionary.matching(c.selected_tiles,c.piece)
            if len(matching)==1:return self._make(c,matching[0],'Selected pattern matches the edit dictionary.','observed_mask')
        # No threat/objective evidence means no invented tactical "best edit".
        if c.objective is None:return EditAdvice('reference',c.revision,'Choose a drill or an edit goal.',evidence={'aim_uv':c.aim_uv,'observed_selection':c.selected_tiles})
        candidates=self.candidates(c)
        if not candidates:return EditAdvice('reference',c.revision,'Insufficient context for this edit goal.')
        if c.objective in ('peek','escape','enter') and c.threat is None:return EditAdvice('reference',c.revision,'Threat context is unknown; available edits are reference only.',evidence={'candidate_ids':[e['id'] for e in candidates]})
        return EditAdvice('reference',c.revision,'Assessing this situation.',evidence={'candidate_ids':[e['id'] for e in candidates]})
    def candidates(self,c):
        return self.dictionary.candidates(c.piece,c.selected_tiles,None if c.objective=='practice' else c.objective)
    def _make(self,c,edit,reason,source,answer=None):
        route=RoutePlanner().plan(c.aim_uv,edit)
        if route is None:return self._abstain(c,'no_safe_connected_path')
        length,points,_=route
        return EditAdvice('suggested',c.revision,reason,edit['id'],points,(c.aim_uv,points[0]),round(length,3),
                          probabilities=(answer or {}).get('probabilities',{}),confidence=(answer or {}).get('confidence'),
                          uncertain=source=='jev',source=source,evidence={'aim_uv':c.aim_uv,'selected_tiles':c.selected_tiles,'domain':'edit','profile_id':c.player_id,'profile_revision':c.revision,'dictionary_version':self.dictionary.version,'model_version':getattr(self.jev,'model_version','local'),'evidence_ids':[f'{c.session_id}:{c.target_id}:{c.observed_at}'],'target_id':c.target_id,'objective':c.objective,'source':c.source})
    def fingerprint(self,c):
        data={'model':getattr(self.jev,'model','local'),'piece':c.piece,'orientation':c.orientation,'session':c.session_id,'dictionary':self.dictionary.version,'player':c.player_id,'revision':c.revision,'target':c.target_id,'mode':c.mode,'aim_bucket':tuple(int(v*6) for v in c.aim_uv),'selection':c.selected_tiles,
              'objective':c.objective,'drill':c.drill_edit_id,'ownership':c.ownership,'threat':c.threat,'wall_pose':c.wall_pose}
        return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    def request(self,c):
        local=self.local(c)
        if local.status!='reference' or local.reason!='Assessing this situation.' or self.jev is None:return local
        key=self.fingerprint(c);now=self.clock()
        with self._lock:
            cache=self._cache.get(key)
            if cache and 0<=now-cache[0]<=.25:return self._consume(c,cache[1])
            if self._pending is not None:
                future,old_key,observed_at=self._pending
                if future.done():
                    self._pending=None
                    try:answer=future.result()
                    except Exception:answer=None
                    if answer is not None and 0<=now-observed_at<=.25:
                        self._cache[old_key]=(observed_at,answer)
                        if old_key==key:return self._consume(c,answer)
            if self._pending is None and now-self._last_call>=30 and self.calls<30:
                self._last_call=now;self.calls+=1
                self._pending=(self._executor.submit(self._classify,c),key,c.observed_at)
        return local
    def _classify(self,c):
        candidates=self.candidates(c)
        options={e['id']:{'name':e['name'],'tiles':e['tiles'],'purpose':e.get('purpose',[]),'exposure':e.get('exposure')} for e in candidates}
        options['insufficient_evidence']='The observed facts do not establish a suitable edit.'
        state={'domain':'edit','profile_id':c.player_id,'profile_revision':c.revision,'dictionary_version':self.dictionary.version,'session_id':c.session_id,'piece':c.piece,'orientation':c.orientation,'mode':c.mode,'objective':c.objective,'aim_uv':c.aim_uv,'selected_tiles':c.selected_tiles,'ownership':c.ownership,
               'player_position':c.player_position,'view_origin':c.view_origin,'view_direction':c.view_direction,'verified_wall_pose':c.wall_pose,'threat':c.threat,
               'provenance':c.source,'unknowns':['build ownership' if c.ownership=='unknown' else None]}
        questions={'edit':{'type':'choice','instructions':'Choose only an edit supported by the verified objective, player/target geometry and threat facts. Unknown fields are unknown. Preserve the intended shape during a selection. Cursor distance alone does not establish tactical safety. Abstain if essential facts are absent.','criteria':options}}
        result=self.jev.decide(state,questions,retries=0)
        return result.get('edit') if isinstance(result,dict) else None
    def _consume(self,c,answer):
        if not isinstance(answer,dict):return EditAdvice('reference',c.revision,'Model result is unavailable or invalid.')
        from .evidence import validate_choice
        options={e['id'] for e in self.candidates(c)}|{'insufficient_evidence'}
        if not validate_choice(answer,options):return EditAdvice('reference',c.revision,'Invalid model distribution.')
        choice=answer.get('choice');confidence=answer.get('confidence');probabilities=answer.get('probabilities')
        valid=isinstance(confidence,(int,float)) and math.isfinite(confidence) and 0<=confidence<=1 and isinstance(probabilities,dict)
        if not valid:return EditAdvice('reference',c.revision,'Model result is unavailable or invalid.')
        if any(not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>.05:return EditAdvice('reference',c.revision,'Model probabilities are invalid.')
        probability=probabilities.get(choice,0)
        if choice=='insufficient_evidence' or confidence<.8 or probability<.90:return EditAdvice('reference',c.revision,'The model is uncertain; keep the reference.',probabilities=probabilities,confidence=confidence,source='jev')
        allowed={e['id']:e for e in self.candidates(c)}
        if choice not in allowed:return EditAdvice('reference',c.revision,'Model selected an unsupported edit.')
        if getattr(self.jev,'shadow',True):return EditAdvice('reference',c.revision,'Model evaluation recorded in shadow mode.',probabilities=probabilities,confidence=confidence,source='jev')
        return self._make(c,allowed[choice],'Possible edit for this observed situation.','jev',answer)
    def close(self):self._executor.shutdown(wait=False,cancel_futures=True)
