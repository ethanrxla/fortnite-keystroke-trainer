"""Versioned edit definitions; only recorded game validation enables advice."""
import json
from pathlib import Path
from .build_pieces import EditDefinition, get_piece

ROOT=Path(__file__).resolve().parents[2]
ALIASES={'roof':'cone','stairs':'ramp'}

def game_verified(edit):
    record=edit.get('validation',{})
    return (record.get('status')=='game_verified' and bool(record.get('game_version'))
            and bool(record.get('evidence')) and record.get('result_confirmed') is True)

class EditDictionary:
    def __init__(self,path=None):
        data=json.loads(Path(path or ROOT/'shared/edits.json').read_text(encoding='utf-8'))
        self.version=data.get('version',1);self.all={};self.edits={};self.definitions={}
        for piece,meta in data['pieces'].items():
            for original in data.get(meta['list'],[]):
                e=dict(original);e['piece']=ALIASES.get(piece,piece)
                e['cols']=meta['cols'];e['rows']=meta['rows']
                if e['id'] in self.all:raise ValueError('Duplicate edit ID')
                tiles=e.get('tiles',[])
                if any(type(t) is not int or not 0<=t<meta['cols']*meta['rows'] for t in tiles):raise ValueError('Invalid tile')
                if len(set(tiles))!=len(tiles):raise ValueError('Repeated selection tile')
                self.all[e['id']]=e
                self.definitions[e['id']]=EditDefinition.from_dict(e)
                if game_verified(e) and e.get('suggest') and e['piece']!='ramp':self.edits[e['id']]=e
                if game_verified(e) and e.get('suggest') and e['piece']=='ramp' and get_piece('ramp').route((0,0),e):self.edits[e['id']]=e
    def matching(self,mask,piece='wall'):
        return [e for e in self.edits.values() if e['piece']==piece and set(e.get('tiles',[]))==set(mask)]
    def candidates(self,piece,selected=(),objective=None):
        return [e for e in self.edits.values() if e['piece']==piece and set(selected)<=set(e.get('tiles',[]))
                and (objective is None or objective in e.get('purpose',[]))]

class RoutePlanner:
    def __init__(self,inset=.15):self.inset=inset
    def route(self,aim,edit):
        return get_piece(edit['piece']).route(aim,edit,self.inset)
    def plan(self,aim,edit):
        route=self.route(aim,edit)
        return route.legacy() if route else None

class TargetTracker:
    """Piece-local identity; stability before selection and lock through tracing."""
    def __init__(self,stability=.15):self.stability=stability;self.reset()
    def reset(self):self.target=None;self.pending=None;self.since=0.;self.active=None;self.tracing=False;self.selection=()
    def update(self,target,candidate,selection,now,ended=False):
        if ended or target!=self.target:
            self.reset();self.target=target
        if selection is None:return self.active
        selection=tuple(selection)
        if self.selection and not selection: # visible reset or a new empty edit
            self.active=None;self.tracing=False;self.pending=None
        if selection and not self.tracing:
            # Never select a new goal halfway through an already-started trace.
            self.tracing=True
        self.selection=selection
        if self.tracing:return self.active
        if candidate!=self.pending:self.pending=candidate;self.since=now
        if now-self.since>=self.stability:self.active=candidate
        return self.active

class EditAnalyzer:
    def __init__(self):self.reset()
    def reset(self):self.samples=[];self.gaps=False
    def sample(self,at,uv,selection):
        if self.samples and at-self.samples[-1][0]>.15:self.gaps=True
        self.samples.append((at,tuple(uv),frozenset(selection)))
        self.samples=self.samples[-4096:]
    def finish(self,target,confirmed=False):
        import math
        selected=set().union(*(s[2] for s in self.samples)) if self.samples else set()
        wanted=set(target)
        return {'domain':'edit','complete_observation':not self.gaps and bool(self.samples),
                'matched_tiles':len(selected&wanted),'target_count':len(wanted),
                'observed_coverage':len(selected&wanted)/len(wanted) if wanted else None,
                'extra_selections':sorted(selected-wanted),'result_confirmed':bool(confirmed),
                'travel':sum(math.dist(a[1],b[1]) for a,b in zip(self.samples,self.samples[1:])),
                'duration':self.samples[-1][0]-self.samples[0][0] if self.samples else None}
