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


def _line_projection(image):
    h,w=image.shape[:2]
    bright=cv2.inRange(image,np.array([120,120,120],np.uint8),np.array([255,255,255],np.uint8))
    bright[(image.max(2).astype(int)-image.min(2))>100]=0
    bright[int(h*.88):]=0
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
            small=cv2.warpPerspective(image,np.diag([25.,25.,1.])@np.linalg.inv(H),(75,75)).astype(float)
            verified=0
            for row in range(3):
                for col in range(3):
                    tile=small[row*25+5:row*25+20,col*25+5:col*25+20]
                    blue=((tile[:,:,0]>tile[:,:,2]*1.22)&(tile[:,:,0]>80)&(tile[:,:,1]>45)).mean()
                    neutral=((tile.max(2)-tile.min(2)<25)&(tile.mean(2)>60)&(tile.mean(2)<180)).mean()
                    if blue+neutral>.65:verified+=1
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
            if blue+neutral>.65:count+=1
    return count


def _segments(image):
    """Long straight light edges (the gaps between edit tiles) as (x1,y1,x2,y2,length)."""
    h,w=image.shape[:2]
    bright=cv2.inRange(image,np.array([120,120,120],np.uint8),np.array([255,255,255],np.uint8))
    bright[(image.max(2).astype(int)-image.min(2))>100]=0
    bright[int(h*.88):]=0
    lines=cv2.HoughLinesP(cv2.Canny(bright,40,120),1,np.pi/360,35,minLineLength=max(30,w*.04),maxLineGap=12)
    if lines is None:return []
    return [(float(a),float(b),float(c),float(d),float(np.hypot(c-a,d-b))) for a,b,c,d in lines.reshape(-1,4)]


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
    m=np.array([a['n'],b['n']],float)
    if abs(np.linalg.det(m))<1e-6:return None
    return np.linalg.solve(m,np.array([a['c'],b['c']],float))


def _general_grid(image,aim,budget=.08):
    """Any-angle n x n edit grid (n = 3 for walls, 2 for floors / stairs / roofs).

    The near-horizontal / near-vertical detector (_line_projection) misses floors seen at an angle and walls with
    selected tiles. Here lines are split into the two dominant directions, n+1 lines are chosen from each, and the
    result must be a projective grid (every interior crossing where a homography of the outer quad puts it) whose
    cells look like edit tiles and which contains the crosshair. Returns (count, H, quad, n) or None."""
    deadline=time.perf_counter()+budget
    h,w=image.shape[:2]
    lines=sorted(_merge_lines(_segments(image)),key=lambda l:-l['length'])[:24]
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
        found=_grid_from_families(image,aim,fam,deadline)
        if found is not None and (overall is None or found[0]>overall[0]):overall=found
    return overall[1] if overall else None


def _grid_from_families(image,aim,fam,deadline=None):
    """Bounded search: the crosshair must lie between the first and last line of each family (it is on the piece), so
    only those line spans are tried, crossings are computed once, and the search stops at `deadline`."""
    h,w=image.shape[:2]
    best=None
    for n in (3,2):
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
                if area<.08*w*h or quad[:,0].min()<-w*(.35 if n==3 else .05) or quad[:,0].max()>w*(1.35 if n==3 else 1.05) or quad[:,1].min()<-h*(.35 if n==3 else .05) or quad[:,1].max()>h*(1.35 if n==3 else 1.05):continue
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


_TEMPLATE_CACHE = {}
def cue_scores(frame, names, roi=None):
    height,width=frame.shape[:2]
    scale=min(1.,960./width)
    image=cv2.resize(frame[:,:,:3],(round(width*scale),round(height*scale)))
    h,w=image.shape[:2]
    if roi is None:roi=(.20,.30,1.,.76)
    x1,y1,x2,y2=roi
    image=image[int(h*y1):int(h*y2),int(w*x1):int(w*x2)]
    mask=cv2.inRange(image,np.array([180,180,180],np.uint8),np.array([255,255,255],np.uint8))
    mask[(image.max(2).astype(int)-image.min(2))>45]=0
    scores=[]
    for name in names:
        key=(name,round(scale,3))
        if key not in _TEMPLATE_CACHE:
            template=cv2.imread(str(Path(__file__).resolve().parents[1]/'assets/edit-observer'/(name+'.png')),0)
            _TEMPLATE_CACHE[key]=[] if template is None else [cv2.resize(template,None,fx=k*scale,fy=k*scale) for k in [.7,.85,1.,1.15,1.3,1.5]]
        score=0.
        for current in _TEMPLATE_CACHE[key]:
            if current.shape[0]>mask.shape[0] or current.shape[1]>mask.shape[1]:continue
            score=max(score,float(cv2.minMaxLoc(cv2.matchTemplate(mask,current,cv2.TM_CCOEFF_NORMED))[1]))
        scores.append(score)
    return tuple(scores)

def _native_edit_cues(frame):
    scores=cue_scores(frame,['confirm','reset'])
    return min(scores)>=.56 and sum(scores)/2>=.60

def observe_mode(frame):
    if frame is None or frame.ndim!=3:return 'unknown',0.
    edit=cue_scores(frame,['confirm','reset'])
    if min(edit)>=.56 and sum(edit)/2>=.60:return 'editing',min(edit)
    build=cue_scores(frame,['change-material','rotate','change-material-current','rotate-current','build-label'],(0.,.35,.23,.76))
    material=max(build[0],build[2]);other=max(build[1],build[3],build[4])
    if material>=.60 and other>=.60:return 'building',min(material,other)
    editable=cue_scores(frame,['editable-label','editable-key'],(.35,.28,.65,.78))
    if editable[0]>=.75 and editable[1]>=.60:return 'editable',min(editable)
    return 'unknown',0.


def _crosshair(frame):
    h,w=frame.shape[:2]
    red=cv2.inRange(frame,np.array([0,0,170],np.uint8),np.array([110,110,255],np.uint8))
    contours,_=cv2.findContours(red,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for c in contours:
        x,y,cw,ch=cv2.boundingRect(c);area=cv2.contourArea(c)
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
        scale=min(1.,960./width);image=cv2.resize(frame[:,:,:3],(round(width*scale),round(height*scale)))
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
        selected=[]
        for row in range(n):
            for col in range(n):
                tile=projected[row*100+20:row*100+80,col*100+20:col*100+80].astype(float)
                neutral=((tile.max(2)-tile.min(2)<25)&(tile.mean(2)>60)&(tile.mean(2)<180)).mean()
                blue=((tile[:,:,0]>tile[:,:,2]*1.2)&(tile[:,:,0]>80)).mean()
                tile_u8=tile.astype(np.uint8)
                edges=cv2.Canny(cv2.cvtColor(tile_u8,cv2.COLOR_BGR2GRAY),40,120)
                lines=cv2.HoughLinesP(edges,1,np.pi/180,12,minLineLength=20,maxLineGap=5)
                positive=negative=False
                if lines is not None:
                    for x1,y1,x2,y2 in lines.reshape(-1,4):
                        if abs(x2-x1)<1:continue
                        slope=(y2-y1)/(x2-x1)
                        positive |= .55<slope<1.6
                        negative |= -1.6<slope<-.55
                if neutral>.25 and blue<.2 and positive and negative:selected.append((n-1-row)*n+col)
        # Image-grid coordinates: u left->right, v bottom->top of the quad as drawn on screen. For a wall that is
        # the wall's own frame; floors / roofs are re-oriented to near / far by edit_geometry.piece_context.
        return WallObservation(now,'editing',round(confidence,3),tuple(tuple(float(v/scale) for v in p) for p in outer),
                               (float(aim[0]),float(n-aim[1])),tuple(sorted(selected)),count,'native_edit_grid_observed',cells=n)
