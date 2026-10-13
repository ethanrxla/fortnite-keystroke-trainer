"""Local visual edit-grid evidence. No game memory, input injection, or network.
An observed native 3x3 grid is distinct from an inferred build-grid plane.
"""
from dataclasses import dataclass, asdict
import time
import itertools
from pathlib import Path
import cv2
import numpy as np

@dataclass(frozen=True)
class WallObservation:
    captured_at: float
    mode: str = 'unknown'
    confidence: float = 0.0
    wall_quad: tuple = ()
    aim_uv: tuple = ()
    selected_tiles: tuple = ()
    supported_cells: int = 0
    reason: str = 'no_verified_edit_grid'
    # Grid size seen: 3 = a wall (3x3 edit grid), 2 = a floor, stairs or roof/cone (2x2).
    cells: int = 3
    # Image evidence cannot establish world pose, ownership, opponent or line of sight.
    world_pose: object = None
    editable_owner: object = None
    def to_dict(self): return asdict(self)


def _ordered(q):
    q=np.asarray(q,np.float32).reshape(4,2)
    centre=q.mean(0);angles=np.arctan2(q[:,1]-centre[1],q[:,0]-centre[0])
    q=q[np.argsort(angles)];q=np.roll(q,-int(np.argmin(q.sum(1))),axis=0)
    return q


def _clusters(values):
    centres=np.percentile(values,[10,50,90]).astype(float)
    for _ in range(15):
        labels=np.abs(values[:,None]-centres).argmin(1)
        updated=np.array([values[labels==i].mean() if (labels==i).any() else centres[i] for i in range(3)])
        if np.allclose(updated,centres):break
        centres=updated
    order=np.argsort(centres);centres=centres[order]
    return np.abs(values[:,None]-centres).argmin(1),centres


def _mask_hud(mask):
    """Blank the screen regions taken by HUD and by our own overlays, whose straight edges would pose as grid lines:
    the keyboard overlay and its text (bottom-left), the game status box (top-left), the minimap (top-right) and the
    hotbar / build bar (bottom-right). Fractions of the frame, measured on 1920x1080 captures."""
    h,w=mask.shape[:2]
    mask[int(h*.58):,:int(w*.24)]=0
    mask[:int(h*.12),:int(w*.24)]=0
    mask[:int(h*.33),int(w*.82):]=0
    mask[int(h*.64):,int(w*.70):]=0
    mask[int(h*.88):]=0
    return mask


def _line_projection(image):
    h,w=image.shape[:2]
    bright=cv2.inRange(image,np.array([120,120,120],np.uint8),np.array([255,255,255],np.uint8))
    bright[(image.max(2).astype(int)-image.min(2))>100]=0
    _mask_hud(bright)
    lines=cv2.HoughLinesP(cv2.Canny(bright,40,120),1,np.pi/360,35,minLineLength=max(40,w*.05),maxLineGap=10)
    if lines is None:return None
    groups={'h':[],'v':[]}
    for x1,y1,x2,y2 in lines.reshape(-1,4):
        dx=x2-x1;dy=y2-y1;length=float(np.hypot(dx,dy))
        if abs(dy)<abs(dx)*.25:
            slope=dy/dx;offset=y1-slope*x1;at=slope*w*.5+offset;kind='h'
        elif abs(dx)<abs(dy)*.25:
            slope=dx/dy;offset=x1-slope*y1;at=slope*h*.5+offset;kind='v'
        else:continue
        group=next((g for g in groups[kind] if abs(g['at']-at)<5 and abs(g['slope']-slope)<.045),None)
        if group is None:groups[kind].append(dict(at=at,slope=slope,offset=offset,length=length))
        elif length>group['length']:group.update(at=at,slope=slope,offset=offset,length=length)
    choices={}
    for kind,axis in [('h',h),('v',w)]:
        gs=sorted(sorted(groups[kind],key=lambda x:x['length'],reverse=True)[:12],key=lambda x:x['at'])
        options=[]
        for combo in itertools.combinations(gs,4):
            gaps=np.diff([g['at'] for g in combo])
            if gaps.min()<axis*.08 or gaps.max()/gaps.min()>(1.6 if kind=='h' else 2.3):continue
            if max(g['slope'] for g in combo)-min(g['slope'] for g in combo)>.30:continue
            options.append((sum(g['length'] for g in combo),combo))
        choices[kind]=[c for _,c in sorted(options,key=lambda x:x[0],reverse=True)[:8]]
    def intersect(v,hor):
        # x = v.slope*y + v.offset; y = hor.slope*x + hor.offset.
        x=(v['slope']*hor['offset']+v['offset'])/(1-v['slope']*hor['slope']);return [x,hor['slope']*x+hor['offset']]
    best=None
    for vs in choices['v']:
        for hs in choices['h']:
            quad=np.array([intersect(vs[0],hs[0]),intersect(vs[3],hs[0]),intersect(vs[3],hs[3]),intersect(vs[0],hs[3])],np.float32)
            if not cv2.isContourConvex(quad) or cv2.contourArea(quad)<.18*w*h:continue
            if not cv2.pointPolygonTest(quad,(w*.5,h*.5),False)>=0:continue
            if quad[:,0].min()<-w*.1 or quad[:,0].max()>w*1.1 or quad[:,1].min()<-h*.2:continue
            H=cv2.getPerspectiveTransform(np.array([[0,0],[3,0],[3,3],[0,3]],np.float32),quad)
            expected=np.array([[[col,row] for row in range(4) for col in range(4)]],np.float32)
            actual=np.array([[intersect(vs[col],hs[row]) for row in range(4) for col in range(4)]],np.float32)
            mapped=cv2.perspectiveTransform(actual,np.linalg.inv(H))
            residual=np.linalg.norm(mapped-expected,axis=2)
            if residual.mean()>.075 or residual.max()>.15:continue
            verified=_tile_support(image,H,3)
            if verified>=6 and (best is None or verified>best[0]):best=(verified,H,quad)
    return best


def _tile_support(image,H,n):
    """How many of the n x n reconstructed cells look like edit tiles (blue unselected or grey selected)."""
    size=25
    small=cv2.warpPerspective(image,np.diag([float(size),float(size),1.])@np.linalg.inv(H),(size*n,size*n)).astype(float)
    count=0
    for row in range(n):
        for col in range(n):
            tile=small[row*size+5:row*size+20,col*size+5:col*size+20]
            blue=((tile[:,:,0]>tile[:,:,2]*1.22)&(tile[:,:,0]>80)&(tile[:,:,1]>45)).mean()
            neutral=((tile.max(2)-tile.min(2)<25)&(tile.mean(2)>60)&(tile.mean(2)<180)).mean()
            red=((tile[:,:,2]>tile[:,:,0]*1.22)&(tile[:,:,2]>80)&(tile[:,:,1]<100)).mean()
            if blue+neutral+red>.65:count+=1
    return count


def _segments(image,dark=False):
    """Long straight light edges (the gaps between edit tiles) as (x1,y1,x2,y2,length)."""
    h,w=image.shape[:2]
    bright=cv2.inRange(image,np.array([120,120,120],np.uint8),np.array([255,255,255],np.uint8))
    bright[(image.max(2).astype(int)-image.min(2))>100]=0
    # Dim walls (shade, night lighting): the gaps between tiles are only bright relative to the tiles around them.
    # A white top-hat on the brightest channel keeps thin bright strokes whatever the absolute exposure.
    value=image.max(2)
    tophat=cv2.morphologyEx(value,cv2.MORPH_TOPHAT,cv2.getStructuringElement(cv2.MORPH_RECT,(9,9)))
    bright[tophat>40]=255
    if dark:
        # Second pass (VisualObserver.observe, when the bright lines found nothing): seen at an angle in shade the gaps
        # can be darker than the tiles (live 2026-10-10: (84,63,54) between (145,76,28) tiles), so a black top-hat
        # keeps thin dark strokes too. Off by default: on clean walls the extra edges crowd out the real ones. Dark
        # wood seams are dropped by _beside_tiles, which keeps only segments with edit-tile colour beside them.
        blackhat=cv2.morphologyEx(value,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_RECT,(9,9)))
        bright[blackhat>40]=255
    _mask_hud(bright)
    lines=cv2.HoughLinesP(cv2.Canny(bright,40,120),1,np.pi/360,35,minLineLength=max(30,w*.04),maxLineGap=12)
    if lines is None:return []
    return _beside_tiles(image,[(float(a),float(b),float(c),float(d),float(np.hypot(c-a,d-b))) for a,b,c,d in lines.reshape(-1,4)])


def _beside_tiles(image,segs,offset=4,keep=.35):
    """Only segments with edit-tile colour beside them. A gap between edit tiles has tiles on both sides and a piece's
    border on one; the planks of a wooden build next to the wall have none, and their many long edges otherwise crowd
    the wall's own lines out of the detectors' shortlists (live 2026-10-10: close to a wall beside wooden builds the
    grid was never found). Per-pixel colour classes as _tile_support with a strict grey; 9 samples per side, all vectorised."""
    if not segs:return segs
    img=image.astype(np.int16);b,g,r=img[:,:,0],img[:,:,1],img[:,:,2]
    spread=img.max(2)-img.min(2);mean=img.mean(2)
    # Strict classes: edit-tile blue is strongly blue (145,76,28); wood at night is tinted (87,70,60). Grey only when
    # exactly grey (selected tiles: spread ~3; shaded wood 14..31).
    tile=((b>r*2)&(b*10>g*14)&(b>80))|((spread<10)&(mean>60)&(mean<180))|((r*100>b*122)&(r>80)&(g<100))
    h,w=tile.shape
    s=np.asarray(segs,np.float32)
    t=np.linspace(.1,.9,9,dtype=np.float32)
    x=s[:,0,None]+(s[:,2]-s[:,0])[:,None]*t;y=s[:,1,None]+(s[:,3]-s[:,1])[:,None]*t
    length=np.maximum(s[:,4],1e-6)
    nx=(-(s[:,3]-s[:,1])/length)[:,None];ny=((s[:,2]-s[:,0])/length)[:,None]
    def at(px,py):
        xi=np.clip(px.round().astype(int),0,w-1);yi=np.clip(py.round().astype(int),0,h-1)
        return tile[yi,xi]
    beside=at(x+nx*offset,y+ny*offset)|at(x-nx*offset,y-ny*offset)
    return [seg for seg,f in zip(segs,beside.mean(1)) if f>=keep]


def _merge_lines(segs):
    """Collinear segments -> lines in normal form (nx, ny, c) with nx*x+ny*y=c, weighted by total length."""
    out=[]
    for x1,y1,x2,y2,length in sorted(segs,key=lambda s:-s[4]):
        dx,dy=(x2-x1)/length,(y2-y1)/length
        nx,ny=-dy,dx
        if ny<0 or (ny==0 and nx<0):nx,ny=-nx,-ny
        c=nx*(x1+x2)/2+ny*(y1+y2)/2
        for line in out:
            if abs(line['n'][0]*nx+line['n'][1]*ny)>.995 and abs(line['n'][0]*(x1+x2)/2+line['n'][1]*(y1+y2)/2-line['c'])<12:
                line['length']+=length;break
        else:out.append({'n':(nx,ny),'c':c,'length':length,'angle':float(np.degrees(np.arctan2(dy,dx))%180)})
    return out


def _cross(a,b):
    # Two lines in normal form: Cramer's rule in plain floats (np.linalg.solve cost ~13 us a call, ~130k calls a second).
    (a0,a1),(b0,b1)=a['n'],b['n']
    det=a0*b1-a1*b0
    if abs(det)<1e-6:return None
    return np.array(((a['c']*b1-a1*b['c'])/det,(a0*b['c']-a['c']*b0)/det))


def _general_grid(image,aim,budget=.08,segs=None,sizes=(3,2),min_area=.08):
    """Any-angle n x n edit grid (n = 3 for walls, 2 for floors / stairs / roofs).

    The near-horizontal / near-vertical detector (_line_projection) misses floors seen at an angle and walls with
    selected tiles. Here lines are split into the two dominant directions, n+1 lines are chosen from each, and the
    result must be a projective grid (every interior crossing where a homography of the outer quad puts it) whose
    cells look like edit tiles and which contains the crosshair. Returns (count, H, quad, n) or None."""
    h,w=image.shape[:2]
    # segs: line segments computed once per frame by the caller and shared between detectors (~26 ms each).
    lines=sorted(_merge_lines(segs if segs is not None else _segments(image)),key=lambda l:-l['length'])[:24]
    deadline=time.perf_counter()+budget       # the budget is for the search, after any line search done here
    if len(lines)<6:return None
    # Direction families: up to three angle peaks (selected tiles add diagonal X marks, so the strongest two are not
    # always the grid); every pair at least 25 degrees apart is tried.
    hist=np.zeros(180)
    for l in lines:hist[int(l['angle'])%180]+=l['length']
    smooth=np.convolve(np.concatenate([hist[-6:],hist,hist[:6]]),np.ones(13),'valid')
    diff=lambda a,b:min(abs(a-b),180-abs(a-b))
    peaks=[]
    work=smooth.copy()
    for _ in range(3):
        k=int(np.argmax(work))
        if work[k]<=0:break
        peaks.append(k)
        work=np.array([0 if diff(i,k)<25 else v for i,v in enumerate(work)])
    # In perspective the lines of one family meet at a vanishing point, so their angles spread widely (a floor's
    # receding edges can run 50..130 degrees). Family A = lines near one angle peak, family B = every line at least 20
    # degrees away; the projective-grid check then rejects wrong mixtures.
    overall=None
    for k in peaks:
        fam=[[l for l in lines if diff(l['angle'],k)<14],[l for l in lines if diff(l['angle'],k)>=20]]
        found=_grid_from_families(image,aim,fam,deadline,sizes,min_area)
        if found is not None and (overall is None or found[0]>overall[0]):overall=found
    return overall[1] if overall else None


def _grid_from_families(image,aim,fam,deadline=None,sizes=(3,2),min_area=.08):
    """Bounded search: the crosshair must lie between the first and last line of each family (it is on the piece), so
    only those line spans are tried, crossings are computed once, and the search stops at `deadline`."""
    h,w=image.shape[:2]
    best=None
    for n in sizes:
        if len(fam[0])<n+1 or len(fam[1])<n+1:continue
        def order(group,ref):
            # Position of each line along a line through the crosshair parallel to the other family's strongest line;
            # the crosshair sits at 0. Sorted by that, and a span is usable only if its outer lines straddle 0.
            through={'n':ref['n'],'c':ref['n'][0]*aim[0]+ref['n'][1]*aim[1]}
            tangent=np.array([-ref['n'][1],ref['n'][0]])
            keyed=[]
            for l in group:
                p=_cross(l,through)
                if p is not None:keyed.append((float((p-np.asarray(aim,float))@tangent),l))
            keyed.sort(key=lambda k:k[0])
            return [l for _,l in keyed],[k for k,_ in keyed]
        (A_lines,A_pos),(B_lines,B_pos)=order(fam[0][:10],fam[1][0]),order(fam[1][:10],fam[0][0])
        def spans(pos):
            out=[]
            for c in itertools.combinations(range(len(pos)),n+1):
                if not pos[c[0]]<0<pos[c[-1]]:continue
                if n==3:
                    # Four equally spaced lines keep the cross-ratio 4/3 under any perspective; this rejects almost
                    # every wrong set of four before any pairing.
                    p0,p1,p2,p3=(pos[i] for i in c)
                    if min(p1-p0,p2-p1,p3-p2)<=0:continue
                    if abs((p2-p0)*(p3-p1)/((p2-p1)*(p3-p0))-4/3)>.15:continue
                out.append(c)
            return out
        cross=[[_cross(a,b) for b in B_lines] for a in A_lines]
        expected=np.array([[[i,j] for j in range(n+1) for i in range(n+1)]],np.float32)
        unit=np.array([[0,0],[n,0],[n,n],[0,n]],np.float32)
        for A in spans(A_pos):
            for B in spans(B_pos):
                if deadline is not None and time.perf_counter()>deadline:return best
                pts=[[cross[A[i]][B[j]] for i in range(n+1)] for j in range(n+1)]
                if any(p is None for row in pts for p in row):continue
                quad=np.array([pts[0][0],pts[0][n],pts[n][n],pts[n][0]],np.float32)
                if not cv2.isContourConvex(quad):continue
                area=cv2.contourArea(quad)
                if area<min_area*w*h or quad[:,0].min()<-w*(.35 if n==3 else .05) or quad[:,0].max()>w*(1.35 if n==3 else 1.05) or quad[:,1].min()<-h*(.35 if n==3 else .05) or quad[:,1].max()>h*(1.35 if n==3 else 1.05):continue
                H=cv2.getPerspectiveTransform(unit,quad)
                actual=np.array([[pts[j][i] for j in range(n+1) for i in range(n+1)]],np.float32)
                residual=np.linalg.norm(cv2.perspectiveTransform(actual,np.linalg.inv(H))-expected,axis=2)
                if residual.mean()>.06 or residual.max()>.13:continue
                count=_tile_support(image,H,n)
                # A 2x2 piece must show all four tiles (a blueprint or a wall corner can fake three).
                if count<(6 if n==3 else 4):continue
                score=(n==3,count,-round(float(residual.mean()),2),area)
                if best is None or score>best[0]:
                    # Corners as image top-left, top-right, bottom-right, bottom-left (as _line_projection gives them).
                    quad=_ordered(quad)
                    best=(score,(count,cv2.getPerspectiveTransform(unit,quad),quad,n))
        if best is not None and best[0][0]:break
    return best


def _cell_colour(image,H,c,r):
    """Median BGR inside grid cell (c, r) of homography H (grid units -> image), or None when mostly off screen / HUD."""
    h,w=image.shape[:2]
    grid=np.float32([[[c+u,r+v] for u in (.2,.35,.5,.65,.8) for v in (.2,.35,.5,.65,.8)]])
    pts=cv2.perspectiveTransform(grid,H)[0]
    vals=[image[int(y),int(x)] for x,y in pts if 0<=x<w and 0<=y<h*.88]
    return np.median(np.asarray(vals,float),axis=0) if len(vals)>=10 else None


def _tile_like(colour):
    """An edit tile's colour: blue (unselected) or neutral grey (selected), as _tile_support classifies pixels."""
    b,g,r=colour
    # Unselected blue, selected grey, and red (the game marks the remaining tiles red while the current selection is
    # not a valid edit). Darker blues are NOT accepted: the navy sky / background would then pass as tiles.
    blue=b>r*1.22 and b>80 and g>45
    neutral=max(colour)-min(colour)<25 and 60<np.mean(colour)<180
    red=r>b*1.22 and r>80 and g<100
    return blue or neutral or red


# The player's own character and the CONFIRM / RESET prompts sit just left of and below the crosshair (over-the-
# shoulder camera); cells there are unseen, not off the wall. Fractions of the frame (x0, y0, x1, y1).
CHARACTER_BOX=(.29,.45,.48,1.)
_VISIBLE={}


def _visible(h,w):
    """Pixels where the wall can be judged: not the HUD, our overlays (_mask_hud) or the player's character."""
    key=(h,w)
    if key not in _VISIBLE:
        m=np.full((h,w),255,np.uint8);_mask_hud(m)
        x0,y0,x1,y1=CHARACTER_BOX;m[int(h*y0):int(h*y1),int(w*x0):int(w*x1)]=0
        _VISIBLE[key]=m>0
    return _VISIBLE[key]


def _wall_fit(image,H,n=3,selected=()):
    """(on, off): visible cells of the n x n grid that are / are not this wall's own tiles. On = blue within 45 of the
    other blue cells' median colour, exactly grey (a selected tile), or the red of an invalid selection. Night lighting
    tints wood and sky blue, so 'looks blue' alone is not enough (player 2026-10-12: boxes drawn a column past the wall's
    edge). On 143 recorded walls, slid one tile sideways / up / down: 2+ off cells or under 7 tile cells catches 81% of
    the slid grids and 6% of the correct ones; 3+ off cells catches 18% and under 1%. `selected`: tile numbers the
    projection already read as selected (their grey X tiles count as on the wall whatever the lighting)."""
    h,w=image.shape[:2];vis=_visible(h,w)
    grid=np.float32([[[c+u,r+v] for u in (.2,.35,.5,.65,.8) for v in (.2,.35,.5,.65,.8)] for c in range(n) for r in range(n)])
    pts=cv2.perspectiveTransform(grid.reshape(1,-1,2),H)[0].reshape(n*n,25,2)
    blues,others=[],[]
    for i,cell in enumerate(pts):
        c,r=divmod(i,n)
        if (n-1-r)*n+c in selected:others.append(True);continue
        xs=cell[:,0].astype(int);ys=cell[:,1].astype(int)
        ok=(xs>=0)&(xs<w)&(ys>=0)&(ys<h)
        ok[ok]&=vis[ys[ok],xs[ok]]
        if ok.sum()<10:continue
        b,g,r=np.median(image[ys[ok],xs[ok]].astype(float),axis=0)
        if b>r*1.22 and b>80 and g>45:blues.append((b,g,r))
        elif max(b,g,r)-min(b,g,r)<12 and 60<(b+g+r)/3<200:others.append(True)
        elif r>b*1.22 and r>80 and g<100:others.append(True)
        else:others.append(False)
    near=[]
    if blues:
        model=np.median(np.asarray(blues),axis=0)
        near=[np.linalg.norm(np.asarray(x)-model)<45 for x in blues]
    on=sum(near)+sum(others)
    return on,len(near)+len(others)-on


def _lattice_shift(image,H,aim,n=3):
    """The tile lattice is periodic, so a detector can lock onto the right spacing one tile off: a wooden pillar or a
    floor plank edge next to a close wall poses as its border (live 2026-10-10: the grid sat one column left and one row
    low, so the crosshair read as the wrong tile). Try the lattice shifted by -1..1 tile on each axis and keep the
    shift whose n x n cells most look like edit tiles. A shift must win by MARGIN cells: next to stacked or adjacent
    walls every position looks like tiles, and the detected lines are then the better evidence. Selected tiles are an
    exact grey here (shaded wood is greyish but warmer). Returns (H, quad, count)."""
    def strict(colour):
        return _tile_like(colour) and (max(colour)-min(colour)<10 or not 60<np.mean(colour)<180 or colour[0]>colour[2]*1.22 or colour[2]>colour[0]*1.22)
    def score(Hs):
        return sum(1 for c in range(n) for r in range(n) if (x:=_cell_colour(image,Hs,c,r)) is not None and strict(x))
    base=score(H)
    best=(base,H)
    a=cv2.perspectiveTransform(np.float32([[aim]]),np.linalg.inv(H))[0,0]
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            # The crosshair is on the piece, so only shifts that keep it inside the grid are candidates.
            if dx==dy==0 or not (0<=a[0]-dx<n and 0<=a[1]-dy<n):continue
            Hs=H@np.array([[1.,0,dx],[0,1.,dy],[0,0,1.]])
            s=score(Hs)
            if s>=base+_SHIFT_MARGIN and s>best[0]:best=(s,Hs)
    H=best[1]
    unit=np.float32([[[0,0],[n,0],[n,n],[0,n]]])
    return H,cv2.perspectiveTransform(unit,H)[0],best[0]


_SHIFT_MARGIN=2


def _partial_grid(image,aim,budget=.06,segs=None):
    """A 3x3 wall whose outer border is partly off screen (close, oblique views): rebuild it from three visible lines
    per direction.

    Three consecutive lines of each family give a 3x3 lattice of crossings that must fit one homography. Which side the
    missing (fourth) line is on comes from colour: the cells just beyond the outer visible line look like the wall's own
    tiles when the grid continues there, and like background when that line is the wall's edge. A side that is off
    screen counts as 'continues' only if the opposite side is clearly background. Any tie abstains, so a wrong cell is
    never guessed. Returns (count, H, quad, 3) like _general_grid, with quad corners possibly off screen."""
    h,w=image.shape[:2]
    lines=sorted(_merge_lines(segs if segs is not None else _segments(image)),key=lambda l:-l['length'])[:20]
    deadline=time.perf_counter()+budget       # the budget is for the search, after any line search done here
    if len(lines)<6:return None
    hist=np.zeros(180)
    for l in lines:hist[int(l['angle'])%180]+=l['length']
    smooth=np.convolve(np.concatenate([hist[-6:],hist,hist[:6]]),np.ones(13),'valid')
    diff=lambda a,b:min(abs(a-b),180-abs(a-b))
    k=int(np.argmax(smooth))
    # Oblique views spread one direction's angles widely (6..23 degrees on a real close-up), so the families are wide.
    fams=[[l for l in lines if diff(l['angle'],k)<35][:7],[l for l in lines if diff(l['angle'],k)>=40][:7]]
    if len(fams[0])<3 or len(fams[1])<3:return None
    def order(group,ref):
        through={'n':ref['n'],'c':ref['n'][0]*aim[0]+ref['n'][1]*aim[1]}
        tangent=np.array([-ref['n'][1],ref['n'][0]])
        keyed=[]
        for l in group:
            q=_cross(l,through)
            if q is not None:keyed.append((float((q-np.asarray(aim,float))@tangent),l))
        keyed.sort(key=lambda t:t[0])
        return [l for _,l in keyed],[t for t,_ in keyed]
    (A,Apos),(B,Bpos)=order(fams[0],fams[1][0]),order(fams[1],fams[0][0])
    def triples(pos,group):
        out=[]
        for t in itertools.combinations(range(len(pos)),3):
            g1,g2=pos[t[1]]-pos[t[0]],pos[t[2]]-pos[t[1]]
            if min(g1,g2)>w*.03 and .45<g1/g2<2.2:out.append(t)
        # Strongest (longest) line sets first: the real wall lines are long, so the answer is found early in the budget.
        return sorted(out,key=lambda t:-sum(group[i]['length'] for i in t))
    grid9=np.float32([[i,j] for j in range(3) for i in range(3)])
    best=None
    # Every A x B crossing once (at most 7 x 7), not nine times per tried pair of triples.
    XC=[[_cross(a,b) for b in B] for a in A]
    for ta in triples(Apos,A):
        for tb in triples(Bpos,B):
            if time.perf_counter()>deadline:return best[1] if best else None
            pts=[XC[ta[i]][tb[j]] for j in range(3) for i in range(3)]
            if any(p is None for p in pts):continue
            pts=np.float32(pts)
            H0,_=cv2.findHomography(grid9,pts,0)
            if H0 is None:continue
            back=cv2.perspectiveTransform(pts[None],np.linalg.inv(H0))[0]
            if np.linalg.norm(back-grid9,axis=1).max()>.12:continue
            # The player's own character often covers a middle cell: model the tile colour from the cells that look
            # like tiles and require at least two of the four inner cells.
            inside=[_cell_colour(image,H0,c,r) for c in (0,1) for r in (0,1)]
            inside=[x for x in inside if x is not None and _tile_like(x)]
            if len(inside)<2:continue
            model=np.median(np.asarray(inside),axis=0)
            if max(np.linalg.norm(x-model) for x in inside)>45:continue
            def side(cells):
                cols=[_cell_colour(image,H0,c,r) for c,r in cells]
                seen=[x for x in cols if x is not None]
                if not seen:return 'off'
                like=sum(_tile_like(x) and np.linalg.norm(x-model)<45 for x in seen)
                return 'tile' if like*2>len(seen) else 'background'
            offsets=[]
            for before,after in (([(-1,0),(-1,1)],[(2,0),(2,1)]),([(0,-1),(1,-1)],[(0,2),(1,2)])):
                b,a=side(before),side(after)
                if (b,a) in (('tile','background'),('off','background')):offsets.append(1)     # missing line is before
                elif (b,a) in (('background','tile'),('background','off')):offsets.append(0)   # missing line is after
                else:offsets.append(None)
            if None in offsets:continue
            oa,ob=offsets
            H,_=cv2.findHomography(grid9+np.float32([oa,ob]),pts,0)
            quad=cv2.perspectiveTransform(np.float32([[[0,0],[3,0],[3,3],[0,3]]]),H)[0]
            if not cv2.isContourConvex(quad):continue
            a=cv2.perspectiveTransform(np.float32([[aim]]),np.linalg.inv(H))[0,0]
            if not (0<=a[0]<3 and 0<=a[1]<3):continue
            count=sum(1 for c in range(3) for r in range(3) if (x:=_cell_colour(image,H,c,r)) is not None and _tile_like(x))
            if count<6:continue           # a wall needs 6 of 9 tile cells anyway (VisualObserver); a blueprint has ~4
            score=(count,-float(np.linalg.norm(back-grid9,axis=1).mean()))
            if best is None or score>best[0]:
                quad=_ordered(quad)
                best=(score,(count,cv2.getPerspectiveTransform(np.float32([[0,0],[3,0],[3,3],[0,3]]),quad),quad,3))
    return best[1] if best else None


_DOWNSCALE = {}


def downscale(frame, scale):
    """frame resized by scale, computed once per frame and size: the tracker, the re-reader and the HUD check all
    work on the same shrunken image instead of resizing the 1920x1080 capture again each (~1-2 ms per resize)."""
    if scale >= 1:
        return frame[:, :, :3]
    key = round(scale, 4)
    hit = _DOWNSCALE.get(key)
    if hit is not None and hit[0] is frame:
        return hit[1]
    small = cv2.resize(frame[:, :, :3], (round(frame.shape[1] * scale), round(frame.shape[0] * scale)))
    _DOWNSCALE[key] = (frame, small)          # keeps a reference, so the identity check cannot alias a new frame
    return small


_TEMPLATE_CACHE = {}
_CUE_SCALE = {}     # (name, roi, scale) -> template size index of a confident (>= 0.6) match: the HUD's fixed scale
_CUE_MISSES = {}    # (name, roi, scale) -> misses in a row since the cue was last found (relearn the size every 15th)
_CUE_HINT = {}      # (name, roi) -> (template index, x, y) of the last confident match: searched first next frame


def _cue_mask(image):
    """White, unsaturated HUD text: every channel >= 180 and channel spread <= 45. OpenCV per-channel min/max instead of
    numpy reductions over the colour axis (~10x faster on the cue regions)."""
    b,g,r=cv2.split(image)
    spread=cv2.subtract(cv2.max(cv2.max(b,g),r),cv2.min(cv2.min(b,g),r))
    mask=cv2.inRange(image,np.array([180,180,180],np.uint8),np.array([255,255,255],np.uint8))
    return cv2.bitwise_and(mask,cv2.compare(spread,45,cv2.CMP_LE))


def cue_scores(frame, names, roi=None):
    """Best template-match score per HUD cue (CONFIRM, RESET, build labels...) in a region of the frame.

    Fast path: the HUD does not move between frames, so each cue is first re-checked where it was last found, at the
    same template scale, on a small patch cut from the full frame and resized on its own (~0.3 ms per cue). Only if a
    cue is not as good as last time (< 90% of its score) is the region resized, masked and searched at all six scales,
    so a cue that moved or disappeared is still found or correctly scored low."""
    height,width=frame.shape[:2]
    scale=min(1.,960./width)
    w,h=round(width*scale),round(height*scale)
    if roi is None:roi=(.20,.30,1.,.76)
    x1,y1,x2,y2=roi
    ox,oy=int(w*x1),int(h*y1)
    rw,rh=int(w*x2)-ox,int(h*y2)-oy
    region=None
    def full_mask():
        nonlocal region
        if region is None:
            region=_cue_mask(downscale(frame,scale)[oy:oy+rh,ox:ox+rw])   # default interpolation: templates tuned on it
        return region
    scores=[]
    for name in names:
        key=(name,round(scale,3))
        if key not in _TEMPLATE_CACHE:
            template=cv2.imread(str(Path(__file__).resolve().parents[1]/'assets/edit-observer'/(name+'.png')),0)
            _TEMPLATE_CACHE[key]=[] if template is None else [cv2.resize(template,None,fx=k*scale,fy=k*scale) for k in [.7,.85,1.,1.15,1.3,1.5]]
        templates=_TEMPLATE_CACHE[key]
        hint_key=(name,roi,round(scale,3))
        hint=_CUE_HINT.get(hint_key)
        if hint is not None:
            i,x,y,last_score=hint
            t=templates[i];pad=24
            ya,yb=max(0,y-pad),min(rh,y+t.shape[0]+pad)
            xa,xb=max(0,x-pad),min(rw,x+t.shape[1]+pad)
            if yb-ya>=t.shape[0] and xb-xa>=t.shape[1]:
                # Patch in full-resolution pixels, resized alone to the region's scale.
                patch=frame[int((oy+ya)/scale):int((oy+yb)/scale),int((ox+xa)/scale):int((ox+xb)/scale),:3]
                window=_cue_mask(cv2.resize(patch,(xb-xa,yb-ya)))
                _,best,_,loc=cv2.minMaxLoc(cv2.matchTemplate(window,t,cv2.TM_CCOEFF_NORMED))
                # As good as last time (>= 90% of that score) at the same place: the cue has not moved. Cues whose
                # absolute score is modest (RESET ~0.55) stay on the fast path; a vanished cue drops far below.
                if best>=max(.45,.9*last_score):
                    _CUE_HINT[hint_key]=(i,xa+loc[0],ya+loc[1],max(last_score*.98,best))
                    scores.append(float(best));continue
        mask=full_mask()
        score=0.;found=None
        # Too few white pixels in the whole region for this cue to be there: score 0 without matching.
        if cv2.countNonZero(mask)<int((templates[0]>0).sum()*.3) if templates else True:
            _CUE_HINT.pop(hint_key,None);scores.append(0.);continue
        # The HUD scale is fixed for a given resolution: once a cue was found, a miss is searched at that one learned
        # size only (1 match instead of 6). All sizes are tried only until the size is learned.
        learned=_CUE_SCALE.get(hint_key)
        ui=_CUE_SCALE.get(('ui',round(scale,3)))
        # A learned size is never proof: live 2026-10-12 a wrong one stuck and CONFIRM / RESET were never found again,
        # so the guide stayed blind to every edit until restarted (a fresh process saw them all). After a run of
        # misses at the learned size, every 15th miss searches all sizes again and relearns.
        misses=_CUE_MISSES.get(hint_key,0)
        if (learned is not None or ui is not None) and misses and misses%15==0:sizes=range(len(templates))
        elif learned is not None:sizes=[learned]
        elif ui is not None:sizes=[i for i in (ui-1,ui,ui+1) if 0<=i<len(templates)]   # all prompts share one UI scale
        else:sizes=range(len(templates))
        for i in sizes:
            current=templates[i]
            if current.shape[0]>mask.shape[0] or current.shape[1]>mask.shape[1]:continue
            _,best,_,loc=cv2.minMaxLoc(cv2.matchTemplate(mask,current,cv2.TM_CCOEFF_NORMED))
            if best>score:score=float(best);found=(i,loc[0],loc[1])
        if found and score>=.50:
            _CUE_HINT[hint_key]=found+(score,);_CUE_MISSES[hint_key]=0
            if score>=.60:_CUE_SCALE[hint_key]=found[0];_CUE_SCALE[('ui',round(scale,3))]=found[0]
        else:_CUE_HINT.pop(hint_key,None);_CUE_MISSES[hint_key]=_CUE_MISSES.get(hint_key,0)+1
        scores.append(score)
    return tuple(scores)


def _native_edit_cues(frame):
    scores=cue_scores(frame,['confirm','reset'])
    return min(scores)>=.56 and sum(scores)/2>=.60

_MODE_STATE = {'idle': 0, 'last': ('unknown', 0.)}


def observe_mode(frame,throttle=False):
    """throttle=True (live overlay only): outside edit mode, build/blueprint/editable prompts every 3rd call."""
    if frame is None or frame.ndim!=3:return 'unknown',0.
    edit=cue_scores(frame,['confirm','reset'])
    if min(edit)>=.56 and sum(edit)/2>=.60:
        _MODE_STATE['idle']=0
        return 'editing',min(edit)
    # Outside edit mode the build / blueprint / editable prompts are re-checked every 3rd frame (~24 ms at the live
    # cadence); in between the last answer stands. Edit mode itself is checked every frame, so opening an edit is
    # never delayed.
    _MODE_STATE['idle']+=1
    if throttle and _MODE_STATE['last'][0]=='unknown' and _MODE_STATE['idle']%3:
        return 'unknown',0.
    _MODE_STATE['last']=_observe_other_modes(frame)
    return _MODE_STATE['last']


def _observe_other_modes(frame):
    build=cue_scores(frame,['change-material','rotate','change-material-current','rotate-current','build-label'],(0.,.35,.23,.76))
    material=max(build[0],build[2]);other=max(build[1],build[3],build[4])
    if material>=.60 and other>=.60:return 'building',min(material,other)
    editable=cue_scores(frame,['editable-label','editable-key'],(.35,.28,.65,.78))
    if editable[0]>=.75 and editable[1]>=.60:return 'editable',min(editable)
    return 'unknown',0.


def _crosshair(frame):
    """The red aim ring if visible near the centre, else the screen centre (Fortnite's crosshair is always there).
    Only the central 24% box is searched: the ring can only be there, and the full-frame search cost ~2.6 ms."""
    h,w=frame.shape[:2]
    x0,y0=int(w*.38),int(h*.38)
    red=cv2.inRange(frame[y0:h-y0,x0:w-x0],np.array([0,0,170],np.uint8),np.array([110,110,255],np.uint8))
    contours,_=cv2.findContours(red,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for c in contours:
        x,y,cw,ch=cv2.boundingRect(c);area=cv2.contourArea(c);x+=x0;y+=y0
        if 25<cw<110 and .8<cw/max(ch,1)<1.25 and area>400:
            cx=x+cw*.5;cy=y+ch*.5
            if abs(cx-w*.5)<w*.12 and abs(cy-h*.5)<h*.12:candidates.append((np.hypot(cx-w*.5,cy-h*.5),(cx,cy)))
    return min(candidates,key=lambda v:v[0])[1] if candidates else (w*.5,h*.5)


class EditGridObserver:
    def observe(self, frame, captured_at=None):
        now=time.monotonic() if captured_at is None else captured_at
        empty=lambda reason:WallObservation(now,reason=reason)
        if frame is None or frame.ndim!=3 or frame.shape[2]<3:return empty('invalid_frame')
        if not _native_edit_cues(frame):return empty('native_edit_mode_unverified')
        self._aim_screen=_crosshair(frame)
        height,width=frame.shape[:2]
        scale=min(1.,960./width);image=downscale(frame,scale)
        h,w=image.shape[:2];grey=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        projection=_line_projection(image)
        if projection is not None:
            count,H,quad=projection
            return self._from_projection(image,H,quad,now,scale,count,.93 if count==9 else .88)
        general=_general_grid(image,(self._aim_screen[0]*scale,self._aim_screen[1]*scale))
        if general is not None:
            count,H,quad,n=general
            return self._from_projection(image,H,quad,now,scale,count,.92 if count==n*n else .88,n)

        bright=cv2.inRange(image,np.array([95,95,95],np.uint8),np.array([255,255,255],np.uint8))
        bright[(image.max(2).astype(int)-image.min(2))>110]=0
        masks=[bright,cv2.Canny(grey,35,110)]
        candidates=[]
        for mask in masks:
            mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
            contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area=cv2.contourArea(contour)
                if not .008*w*h<area<.14*w*h:continue
                q=cv2.approxPolyDP(contour,.025*cv2.arcLength(contour,True),True)
                if len(q)!=4 or not cv2.isContourConvex(q):continue
                q=_ordered(q)
                edge_w=(np.linalg.norm(q[1]-q[0])+np.linalg.norm(q[2]-q[3]))/2
                edge_h=(np.linalg.norm(q[3]-q[0])+np.linalg.norm(q[2]-q[1]))/2
                if not .55<edge_w/max(edge_h,1)<2.8:continue
                if abs(q[1,1]-q[0,1])>edge_h*.45 or abs(q[2,1]-q[3,1])>edge_h*.45:continue
                target=np.array([[0,0],[59,0],[59,59],[0,59]],np.float32)
                tile=cv2.warpPerspective(image,cv2.getPerspectiveTransform(q,target),(60,60))[10:50,10:50].astype(float)
                blue=((tile[:,:,0]>tile[:,:,2]*1.22)&(tile[:,:,0]>80)&(tile[:,:,1]>45)).mean()
                neutral=((tile.max(2)-tile.min(2)<30)&(tile.mean(2)>45)&(tile.mean(2)<175)).mean()
                if blue+neutral<.55:continue
                centre=q.mean(0)
                if not .13*w<centre[0]<.90*w or not .08*h<centre[1]<.88*h:continue
                if any(np.linalg.norm(centre-c[0].mean(0))<min(edge_w,edge_h)*.23 for c in candidates):continue
                candidates.append((q,edge_w,edge_h,blue,neutral))
        if len(candidates)<5:return empty('insufficient_grid_cells')
        # Prefer a consistent panel scale; the small guide/minimap must not become evidence.
        med=np.median([c[1]*c[2] for c in candidates])
        candidates=[c for c in candidates if .5*med<c[1]*c[2]<1.8*med]
        centres=np.array([c[0].mean(0) for c in candidates])
        if len(centres)<5:return empty('inconsistent_panel_scale')
        rows,ys=_clusters(centres[:,1]);cols,xs=_clusters(centres[:,0])
        ew=np.median([c[1] for c in candidates]);eh=np.median([c[2] for c in candidates])
        if np.min(np.diff(xs))<.6*ew or np.min(np.diff(ys))<.6*eh:return empty('grid_spacing_unverified')
        cells={}
        for i,c in enumerate(candidates):
            key=(int(rows[i]),int(cols[i]));previous=cells.get(key)
            if previous is None or c[3]+c[4]>previous[3]+previous[4]:cells[key]=c
        if len(cells)<5:return empty('insufficient_unique_cells')
        source=[];dest=[]
        for (row,col),c in cells.items():
            source.extend([[col,row],[col+1,row],[col+1,row+1],[col,row+1]])
            dest.extend(c[0])
        H,inliers=cv2.findHomography(np.asarray(source,np.float32),np.asarray(dest,np.float32),cv2.RANSAC,3.)
        if H is None or inliers is None or inliers.mean()<.72:return empty('wall_projection_unverified')
        outer=cv2.perspectiveTransform(np.array([[[0,0],[3,0],[3,3],[0,3]]],np.float32),H)[0]
        if cv2.contourArea(outer)<.16*w*h:return empty('grid_too_small')
        return self._from_projection(image,H,outer,now,scale,len(cells),min(.97,.70+len(cells)*.025)*float(inliers.mean()))

    def _from_projection(self,image,H,outer,now,scale,count,confidence,n=3):
        h,w=image.shape[:2]
        inverse=np.linalg.inv(H)
        aim=cv2.perspectiveTransform(np.array([[[self._aim_screen[0]*scale,self._aim_screen[1]*scale]]],np.float32),inverse)[0,0]
        if not (0<=aim[0]<n and 0<=aim[1]<n):return WallObservation(now,reason='crosshair_off_wall',cells=n)
        # Sample all reconstructed cells; selected tiles in native edit mode are neutral grey.
        projected=cv2.warpPerspective(image,np.diag([100.,100.,1.])@inverse,(100*n,100*n))
        # Vectorised: colour fractions of every tile's centre at once (n x n x 60 x 60 view), then the X-mark line
        # check only on tiles that already look selected (neutral grey, not blue): usually 0-3 instead of 9 Hough runs.
        cells=projected.reshape(n,100,n,100,3)[:,20:80,:,20:80].astype(np.int16)
        spread=cells.max(4)-cells.min(4);mean=cells.mean(4)
        neutral=((spread<25)&(mean>60)&(mean<180)).mean(axis=(1,3))
        blue=((cells[...,0]>cells[...,2]*1.2)&(cells[...,0]>80)).mean(axis=(1,3))
        selected=[]
        for row,col in zip(*np.nonzero((neutral>.25)&(blue<.2))):
            tile_u8=projected[row*100+20:row*100+80,col*100+20:col*100+80]
            edges=cv2.Canny(cv2.cvtColor(tile_u8,cv2.COLOR_BGR2GRAY),40,120)
            lines=cv2.HoughLinesP(edges,1,np.pi/180,12,minLineLength=20,maxLineGap=5)
            positive=negative=False
            if lines is not None:
                for x1,y1,x2,y2 in lines.reshape(-1,4):
                    if abs(x2-x1)<1:continue
                    slope=(y2-y1)/(x2-x1)
                    positive |= .55<slope<1.6
                    negative |= -1.6<slope<-.55
            if positive and negative:selected.append(int((n-1-row)*n+col))
        # Image-grid coordinates: u left->right, v bottom->top of the quad as drawn on screen. For a wall that is
        # the wall's own frame; floors / roofs are re-oriented to near / far by edit_geometry.piece_context.
        return WallObservation(now,'editing',round(confidence,3),tuple(tuple(float(v/scale) for v in p) for p in outer),
                               (float(aim[0]),float(n-aim[1])),tuple(sorted(selected)),count,'native_edit_grid_observed',cells=n)


# ---- Vanishing-point grid finder (player approved 2026-10-12) -------------------------------------------------------
# A wall's grid lines meet at two vanishing points. Group the line segments by them (RANSAC on homogeneous cross
# products), send both points to infinity (affine rectification) so the grid lines become equally spaced parallels,
# read the tile spacing as a 1-D problem, and pick the 3x3 window round the crosshair by tile colour and by how many of
# its 24 cell edges are seen as lines. No combinatorial search: ~16 ms. On 600 recorded frames, run before the line
# search detectors (which stay as the fallback): 329 walls vs 298 (none lost), detection median ~4 ms slower because
# frames with no wall now pay for both finders.
def _hlines(segs):
    s = np.asarray(segs, np.float64)
    p1 = np.c_[s[:, 0], s[:, 1], np.ones(len(s))]
    p2 = np.c_[s[:, 2], s[:, 3], np.ones(len(s))]
    L = np.cross(p1, p2)
    L /= np.linalg.norm(L[:, :2], axis=1, keepdims=True) + 1e-12
    mid = (s[:, :2] + s[:, 2:4]) / 2
    d = s[:, 2:4] - s[:, :2]
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-12
    return L, mid, d, s[:, 4]


def _consistent(v, mid, d, tol_deg):
    """Segments whose direction points at vanishing point v (homogeneous), within tol degrees."""
    if abs(v[2]) < 1e-9:
        to = np.broadcast_to(v[:2], mid.shape)
    else:
        to = v[:2] / v[2] - mid
    to = to / (np.linalg.norm(to, axis=1, keepdims=True) + 1e-12)
    return np.abs(np.sum(to * d, axis=1)) > np.cos(np.radians(tol_deg))


def _vanishing_point(L, mid, d, w, rng, tries=120, tol=1.5):
    n = len(L)
    if n < 2:
        return None, None
    best, best_score = None, -1.0
    order = np.argsort(-w)[:min(n, 24)]          # sample among the longest segments
    for _ in range(tries):
        i, j = rng.choice(order, 2, replace=False)
        v = np.cross(L[i], L[j])
        if not np.isfinite(v).all() or np.linalg.norm(v) < 1e-12:
            continue
        v = v / np.linalg.norm(v)
        inl = _consistent(v, mid, d, tol)
        score = w[inl].sum()
        if score > best_score:
            best, best_score = v, score
    if best is None:
        return None, None
    inl = _consistent(best, mid, d, tol)
    A = L[inl] * w[inl, None]
    if len(A) >= 2:
        _, _, vt = np.linalg.svd(A)
        v = vt[-1]
        if np.linalg.norm(v) > 0:
            best = v / np.linalg.norm(v)
            inl = _consistent(best, mid, d, tol)
    return best, inl


def _lattice(pos, w, lo, hi):
    """Spacing and phase of an equally spaced line set, from 1-D line positions weighted by length. Only positions in
    [lo, hi] (around the crosshair) vote. Returns (spacing, phase, support) or None."""
    keep = (pos >= lo) & (pos <= hi)
    pos, w = pos[keep], w[keep]
    if len(pos) < 3:
        return None
    best = None
    idx = np.argsort(-w)[:12]
    for a in idx:
        for b in idx:
            if pos[b] <= pos[a]:
                continue
            for k in (1, 2, 3):
                s = (pos[b] - pos[a]) / k
                if s < (hi - lo) * .06:
                    continue
                r = (pos - pos[a]) / s
                near = np.abs(r - np.round(r)) < .07
                score = w[near].sum()
                if best is None or score > best[2]:
                    best = (s, pos[a], score)
    return best


def _vp_grid(image, aim, segs, rng=None):
    if not segs or len(segs) < 6:
        return None
    rng = rng or np.random.default_rng(0)
    h, w = image.shape[:2]
    L, mid, d, length = _hlines(segs)
    vertical = np.abs(d[:, 1]) > np.cos(np.radians(30))
    fams = [vertical, ~vertical]
    vps, inls = [], []
    for f in fams:
        idx = np.nonzero(f)[0]
        if len(idx) < 3:
            return None
        v, inl = _vanishing_point(L[idx], mid[idx], d[idx], length[idx], rng)
        if v is None:
            return None
        sel = np.zeros(len(L), bool); sel[idx[inl]] = True
        vps.append(v); inls.append(sel)
    # Affine rectification: the line through both vanishing points goes to infinity.
    l = np.cross(vps[0], vps[1])
    if np.linalg.norm(l[:2]) < 1e-12 and abs(l[2]) < 1e-12:
        return None
    l = l / (np.abs(l[2]) if abs(l[2]) > 1e-9 else np.linalg.norm(l))
    # Scale so a typical image point has w ~ 1 and positive.
    c = np.array([w / 2, h / 2, 1.0])
    wc = l @ c
    if abs(wc) < 1e-9:
        return None
    l = l / wc
    Hr = np.array([[1, 0, 0], [0, 1, 0], l], np.float64)
    def rect(p):
        q = Hr @ np.array([p[0], p[1], 1.0]); return q[:2] / q[2]
    if (np.c_[mid, np.ones(len(mid))] @ l <= 0).any():
        pass  # segments across the vanishing line would be nonsense; they are rare for a wall in front of the camera
    rmid = np.c_[mid, np.ones(len(mid))] @ Hr.T
    rmid = rmid[:, :2] / rmid[:, 2:3]
    ra = rect(aim)
    out_lines = []
    for fam, v in zip(inls, vps):
        rv = Hr @ v                                       # now a direction (at infinity)
        dirv = rv[:2] / (np.linalg.norm(rv[:2]) + 1e-12)
        normal = np.array([-dirv[1], dirv[0]])
        pos = rmid[fam] @ normal
        pa = ra @ normal
        span = np.ptp(rmid @ normal) + 1e-6
        lat = _lattice(pos, length[fam], pa - span, pa + span)
        if lat is None:
            return None
        s, ph, sup = lat
        out_lines.append((normal, s, ph, pa))
    Hinv = np.linalg.inv(Hr)
    # Line evidence: the observed segments rasterised once; a window's 24 cell edges are checked against it, so a
    # window that runs onto a floor or the sky below / beside the wall (same colour, same vanishing points, but no
    # grid lines of this wall there) loses to the one whose edges are all seen.
    seen = np.zeros((h, w), np.uint8)
    for x1, y1, x2, y2, _ in segs:
        cv2.line(seen, (int(x1), int(y1)), (int(x2), int(y2)), 255, 5)
    def coverage(H):
        t = np.linspace(.15, .85, 7)
        pts = []
        for i in range(4):
            for j in range(3):
                pts += [(i, j + u) for u in t] + [(j + u, i) for u in t]
        p = cv2.perspectiveTransform(np.float32([pts]), H)[0]
        x = p[:, 0].astype(int); y = p[:, 1].astype(int)
        ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
        hit = np.zeros(len(p), bool); hit[ok] = seen[y[ok], x[ok]] > 0
        return int(hit.reshape(24, 7).mean(1).__ge__(.5).sum())
    unit = np.float32([[0, 0], [3, 0], [3, 3], [0, 3]])
    best = None
    (na, sa, pha, paa), (nb, sb, phb, pab) = out_lines
    ka0 = np.floor((paa - pha) / sa); kb0 = np.floor((pab - phb) / sb)
    for da in (0, 1, 2):
        for db in (0, 1, 2):
            a0 = pha + (ka0 - da) * sa; b0 = phb + (kb0 - db) * sb
            corners = []
            for i, j in ((0, 0), (3, 0), (3, 3), (0, 3)):
                M = np.array([na, nb]); rhs = np.array([a0 + i * sa, b0 + j * sb])
                try:
                    x = np.linalg.solve(M, rhs)
                except np.linalg.LinAlgError:
                    return None
                q = Hinv @ np.array([x[0], x[1], 1.0]); corners.append(q[:2] / q[2])
            quad = _ordered(np.float32(corners))
            if not cv2.isContourConvex(quad) or cv2.contourArea(quad) < .02 * w * h:
                continue
            if quad[:, 0].min() < -w * .6 or quad[:, 0].max() > w * 1.6 or quad[:, 1].min() < -h * .6 or quad[:, 1].max() > h * 1.6:
                continue
            H = cv2.getPerspectiveTransform(unit, quad)
            count = _tile_support(image, H, 3)
            on, off = _wall_fit(image, H)
            cov = coverage(H)
            score = (count - 2 * off + cov / 3, count, cov)
            if best is None or score > best[0]:
                best = (score, (count, H, quad, 3))
    # 7 of 9 tile cells, or 6 with at least 18 of the 24 cell edges seen as lines: a clipped close-up wall whose grid
    # continues off screen can line up with a window frame or glass beside it; those go to the fallback detectors.
    if best is None or best[1][0] < 6 or (best[1][0] == 6 and best[0][2] < 18):
        return None
    return best[1]
