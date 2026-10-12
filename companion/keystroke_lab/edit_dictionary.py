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
# map"). The best route only changes with the crosshair cell, so it is planned once per edit and 0.1-tile cell, on that
# edit's first use, and every later route is one array read plus the waypoints from the exact crosshair (~1 us).
# Planner (player 2026-10-12): A* over (crosshair tile, tiles selected so far, button held). A drag moves only to a
# neighbouring tile of the edit (entering any other tile would select it); releasing and clicking another edit tile
# costs RELEASE_COST extra, so shapes in separate pieces (window_double, door_window_*) get routes too; walls only,
# 2x2 pieces keep their tap-each-region fallback. Cost = crosshair travel between inset waypoints; the heuristic (the
# farthest unselected tile's distance) never overestimates, so the route is the shortest under that cost.
ROUTE_RES=10
RELEASE_COST=.75
_ROUTE_ORDERS={}

def _clamp(point,tile,cols,inset):
    c,r=tile%cols,tile//cols
    return (min(max(point[0],c+inset),c+1-inset),min(max(point[1],r+inset),r+1-inset))

def astar_strokes(aim,tiles,cols=3,inset=.15,releases=True):
    """Shortest selection plan for `tiles` from `aim`: a tuple of strokes, each a tuple of tiles dragged in order
    (a stroke after the first starts with a release + click). None when no plan exists."""
    import heapq,math
    want=frozenset(tiles)
    if not want:return None
    index={t:i for i,t in enumerate(sorted(want))};full=(1<<len(want))-1
    def near(t):
        c,r=t%cols,t//cols
        return [n for n in (t-1 if c>0 else None,t+1 if c<cols-1 else None,t-cols if r>0 else None,t+cols)
                if n is not None and n in want]
    def h(point,mask):
        far=0.
        for t,i in index.items():
            if not mask>>i&1:
                c,r=t%cols,t//cols
                dx=max(c+inset-point[0],0,point[0]-(c+1-inset));dy=max(r+inset-point[1],0,point[1]-(r+1-inset))
                far=max(far,math.hypot(dx,dy))
        return far
    queue=[];seen={};count=0
    for t in sorted(want):
        p=_clamp(aim,t,cols,inset);g=math.dist(aim,p)
        heapq.heappush(queue,(g+h(p,1<<index[t]),count,g,t,1<<index[t],p,((t,),)));count+=1
    while queue:
        f,_,g,t,mask,p,plan=heapq.heappop(queue)
        if mask==full:return plan
        key=(t,mask)
        if seen.get(key,math.inf)<=g-1e-9:continue
        seen[key]=g
        moves=[(n,False) for n in near(t)]
        if releases:moves+=[(n,True) for n in sorted(want) if not mask>>index[n]&1 and n not in near(t)]
        for n,release in moves:
            q=_clamp(p,n,cols,inset);ng=g+math.dist(p,q)+(RELEASE_COST if release else 0.)
            nmask=mask|1<<index[n]
            if seen.get((n,nmask),math.inf)<=ng:continue
            nplan=plan+((n,),) if release else plan[:-1]+(plan[-1]+(n,),)
            heapq.heappush(queue,(ng+h(q,nmask),count,ng,n,nmask,q,nplan));count+=1
    return None

def _route_orders(edit,inset):
    # Brute force (2026-10-11), kept for reference: every connected tile order via edit_advisor.safe_path.
    # from .edit_advisor import safe_path
    cols=edit['cols'];tiles=tuple(edit['tiles']);key=(cols,tiles,inset)
    grid=_ROUTE_ORDERS.get(key)
    if grid is None:
        size=cols*ROUTE_RES
        # grid=[[(best[2] if (best:=safe_path(((c+.5)/ROUTE_RES,(r+.5)/ROUTE_RES),tiles,cols=cols,inset=inset)) else None)
        #        for c in range(size)] for r in range(size)]
        grid=[[astar_strokes(((c+.5)/ROUTE_RES,(r+.5)/ROUTE_RES),tiles,cols=cols,inset=inset,releases=cols==3)
               for c in range(size)] for r in range(size)]
        _ROUTE_ORDERS[key]=grid
    return grid

ROUTE_CACHE=Path(__file__).resolve().parents[1]/'data'/'route-table.json'
ROUTE_VERSION=1        # bump when the planner or its costs change

def warm_route_tables(edits,insets=(.15,.35),cache=None,build=True):
    """Every edit's table ready before its first use: loaded from companion/data/route-table.json (~0.05 s), or, when
    the file is missing or stale, planned once (~20 s for the catalogue) in a separate low-priority process so the
    planning never holds this process's interpreter while the guide runs, then loaded."""
    import json,subprocess,sys
    cache=Path(cache or ROUTE_CACHE)
    if build and not _load_route_cache(cache,edits,insets):
        try:
            subprocess.run([sys.executable,'-m','keystroke_lab.edit_dictionary','--build-routes',str(cache)],
                           cwd=str(Path(__file__).resolve().parents[1]),timeout=600,
                           creationflags=(0x4000|0x08000000) if sys.platform=='win32' else 0)   # below normal, no window
        except (OSError,subprocess.SubprocessError):
            pass
        _load_route_cache(cache,edits,insets)
        return
    _build_route_cache(cache,edits,insets)

def _load_route_cache(cache,edits,insets):
    """Load saved tables; True when every edit's table is now present."""
    import json
    try:
        saved=json.loads(cache.read_text())
        if saved.get('version')==ROUTE_VERSION and saved.get('res')==ROUTE_RES:
            for k,grid in saved['tables'].items():
                cols,inset,tiles=k.split('|');key=(int(cols),tuple(int(t) for t in tiles.split(',')),float(inset))
                _ROUTE_ORDERS.setdefault(key,[[tuple(tuple(s) for s in plan) if plan else None for plan in row] for row in grid])
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return all((e['cols'],tuple(e['tiles']),i) in _ROUTE_ORDERS for e in edits if e.get('piece')!='ramp' and e.get('tiles') for i in insets)

def _build_route_cache(cache,edits,insets):
    import json
    _load_route_cache(cache,edits,insets)
    changed=False
    for e in edits:
        if e.get('piece')=='ramp' or not e.get('tiles'):continue
        for inset in insets:
            if (e['cols'],tuple(e['tiles']),inset) not in _ROUTE_ORDERS:_route_orders(e,inset);changed=True
    if changed:
        tables={f"{c}|{i}|{','.join(map(str,t))}":g for (c,t,i),g in list(_ROUTE_ORDERS.items())}
        try:
            cache.parent.mkdir(parents=True,exist_ok=True)
            cache.write_text(json.dumps({'version':ROUTE_VERSION,'res':ROUTE_RES,'tables':tables}))
        except OSError:
            pass

def table_path(aim,edit,inset=.15):
    """(length, points, order, strokes) with the plan read from the route table: points and order are the whole route
    flattened (safe_path's shape), strokes the waypoints per drag (a new stroke = release and click)."""
    import math
    cols=edit['cols'];size=cols*ROUTE_RES
    if not edit.get('tiles') or not all(math.isfinite(v) for v in aim):
        from .edit_advisor import safe_path
        return safe_path(aim,edit.get('tiles',[]),cols=cols,inset=inset)
    plan=_route_orders(edit,inset)[min(size-1,max(0,int(aim[1]*ROUTE_RES)))][min(size-1,max(0,int(aim[0]*ROUTE_RES)))]
    if plan is None:return None
    current=aim;strokes=[];length=0.;releases=0
    for stroke in plan:
        points=[]
        for tile in stroke:
            nxt=_clamp(current,tile,cols,inset);length+=math.dist(current,nxt);current=nxt;points.append(nxt)
        strokes.append(tuple(points))
    length+=RELEASE_COST*(len(plan)-1)
    return length,tuple(p for s in strokes for p in s),tuple(t for s in plan for t in s),tuple(strokes)

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
            # Legacy ramp gesture nodes are normalized; grid strokes use tiles. Table routes carry one waypoint tuple per
            # drag (a release between them); the guide draws each with its own arrow and keeps numbering 1, 2, 3...
            if edit['piece']=='ramp':return (tuple((u*cols,v*rows) for u,v in route[1]),)
            return route[3] if len(route)>3 else (route[1],)
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

if __name__=='__main__':
    import sys
    if len(sys.argv)>2 and sys.argv[1]=='--build-routes':
        warm_route_tables(list(EditDictionary().all.values()),cache=sys.argv[2],build=False)
