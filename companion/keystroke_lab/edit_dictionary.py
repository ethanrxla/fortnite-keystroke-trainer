"""Versioned edit definitions; only recorded game validation enables advice."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ALIASES={'roof':'cone','stairs':'ramp'}

def game_verified(edit):
    record=edit.get('validation',{})
    return (record.get('status')=='game_verified' and bool(record.get('game_version'))
            and bool(record.get('evidence')) and record.get('result_confirmed') is True)

class EditDictionary:
    def __init__(self,path=None):
        data=json.loads(Path(path or ROOT/'shared/edits.json').read_text(encoding='utf-8'))
        self.version=data.get('version',1);self.all={};self.edits={}
        for piece,meta in data['pieces'].items():
            for original in data.get(meta['list'],[]):
                e=dict(original);e['piece']=ALIASES.get(piece,piece)
                e['cols']=meta['cols'];e['rows']=meta['rows']
                if e['id'] in self.all:raise ValueError('Duplicate edit ID')
                tiles=e.get('tiles',[])
                if any(type(t) is not int or not 0<=t<meta['cols']*meta['rows'] for t in tiles):raise ValueError('Invalid tile')
                if len(set(tiles))!=len(tiles):raise ValueError('Repeated selection tile')
                self.all[e['id']]=e
                if game_verified(e) and e.get('suggest') and e['piece']!='ramp':self.edits[e['id']]=e
                if game_verified(e) and e.get('suggest') and e['piece']=='ramp' and e.get('gesture'):self.edits[e['id']]=e
    def matching(self,mask,piece='wall'):
        return [e for e in self.edits.values() if e['piece']==piece and set(e.get('tiles',[]))==set(mask)]
    def candidates(self,piece,selected=(),objective=None):
        return [e for e in self.edits.values() if e['piece']==piece and set(selected)<=set(e.get('tiles',[]))
                and (objective is None or objective in e.get('purpose',[]))]

# Route table (player 2026-10-11: "store every route for every edit and crosshair cell in a lookup table, like the aim
# map"). safe_path searches every connected tile order (~22 us a route); the best order only changes with the crosshair
# cell, so it is searched once per edit and 0.1-tile cell, on that edit's first use (~15 ms), and every later route is
# one array read plus the waypoints from the exact crosshair (~1 us). On 20,000 random aims 87% of routes are identical
# to the full search and the rest are ties, at most 0.1 tile longer.
ROUTE_RES=10
_ROUTE_ORDERS={}

def _route_orders(edit,inset):
    from .edit_advisor import safe_path
    cols=edit['cols'];tiles=tuple(edit['tiles']);key=(cols,tiles,inset)
    grid=_ROUTE_ORDERS.get(key)
    if grid is None:
        size=cols*ROUTE_RES
        grid=[[(best[2] if (best:=safe_path(((c+.5)/ROUTE_RES,(r+.5)/ROUTE_RES),tiles,cols=cols,inset=inset)) else None)
               for c in range(size)] for r in range(size)]
        _ROUTE_ORDERS[key]=grid
    return grid

def table_path(aim,edit,inset=.15):
    """safe_path's (length, points, order) with the tile order read from the route table."""
    import math
    cols=edit['cols'];size=cols*ROUTE_RES
    if not edit.get('tiles') or not all(math.isfinite(v) for v in aim):
        from .edit_advisor import safe_path
        return safe_path(aim,edit.get('tiles',[]),cols=cols,inset=inset)
    order=_route_orders(edit,inset)[min(size-1,max(0,int(aim[1]*ROUTE_RES)))][min(size-1,max(0,int(aim[0]*ROUTE_RES)))]
    if order is None:return None
    current=aim;points=[]
    for tile in order:
        c,r=tile%cols,tile//cols
        current=(min(max(current[0],c+inset),c+1-inset),min(max(current[1],r+inset),r+1-inset))
        points.append(current)
    length=math.dist(aim,points[0])+sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    return length,tuple(points),order

class RoutePlanner:
    def __init__(self,inset=.15):self.inset=inset
    def strokes(self,aim,edit):
        """Piece-local selection strokes. Gaps require release, never a drag."""
        cols=edit['cols'];rows=edit.get('rows',cols)
        tiles=edit.get('tiles',[])
        valid=lambda t:type(t) is int and 0<=t<cols*rows
        if any(not valid(t) for t in tiles):return ()
        if edit['piece']=='ramp' and edit.get('strokes'):
            strokes=edit['strokes'];flat=[t for stroke in strokes for t in stroke]
            if any(not valid(t) for t in flat) or len(flat)!=len(set(flat)):return ()
            if any(len(s)<2 or any(abs(a%cols-b%cols)+abs(a//cols-b//cols)!=1
                                  for a,b in zip(s,s[1:])) for s in strokes):return ()
            return tuple(tuple((t%cols+.5,t//cols+.5) for t in s) for s in strokes)
        route=self.plan(aim,edit)
        if route:
            # Legacy ramp gesture nodes are normalized; grid strokes use tiles.
            return (tuple((u*cols,v*rows) for u,v in route[1]),) if edit['piece']=='ramp' else (route[1],)
        if edit['piece'] in ('floor','cone') and tiles:
            # Disconnected regions must be tapped separately. Do not join them
            # with a selecting line across an untouched region.
            import math
            remaining=set(tiles);result=[];point=aim
            while remaining:
                t=min(remaining,key=lambda t:(math.dist(point,(t%cols+.5,t//cols+.5)),t))
                point=(t%cols+.5,t//cols+.5);result.append((point,));remaining.remove(t)
            return tuple(result)
        return ()
    def plan(self,aim,edit):
        if edit['piece']!='ramp':return table_path(aim,edit,self.inset)
        import math
        gesture=edit.get('gesture',{});nodes=gesture.get('nodes',{});edges={tuple(e) for e in gesture.get('edges',[])}
        routes=[]
        for order in gesture.get('routes',[]):
            if not order or any(n not in nodes for n in order) or any((a,b) not in edges for a,b in zip(order,order[1:])):continue
            points=tuple(tuple(nodes[n]) for n in order)
            length=math.dist(aim,points[0])+sum(math.dist(a,b) for a,b in zip(points,points[1:]))
            routes.append((length,points,tuple(order)))
        return min(routes,key=lambda r:r[0]) if routes else None

class RouteTracker:
    """Lock piece-local waypoints through selection, while the screen pose moves."""
    def __init__(self):self.reset()
    def reset(self):self.key=None;self.paths=();self.tracing=False
    def update(self,key,aim,edit,selected):
        if key!=self.key:self.reset();self.key=key
        if self.tracing and not selected:self.paths=();self.tracing=False
        if not self.paths or not selected:
            self.paths=RoutePlanner(inset=.35).strokes(aim,edit)
        self.tracing=bool(selected)
        return self.paths

class TargetTracker:
    """Piece-local identity; stability before selection and lock through tracing."""
    def __init__(self,stability=.15):self.stability=stability;self.reset()
    def reset(self):self.target=None;self.pending=None;self.since=0.;self.active=None;self.tracing=False;self.selection=()
    def update(self,target,candidate,selection,now,ended=False):
        selection=tuple(selection)
        if ended or target!=self.target:
            self.reset();self.target=target
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
                'observed_coverage':len(selected&wanted)/len(wanted) if wanted else None,
                'extra_selections':sorted(selected-wanted),'result_confirmed':bool(confirmed),
                'travel':sum(math.dist(a[1],b[1]) for a,b in zip(self.samples,self.samples[1:])),
                'duration':self.samples[-1][0]-self.samples[0][0] if self.samples else None}
