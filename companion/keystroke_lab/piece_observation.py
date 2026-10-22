"""Piece-aware observation boundary. Ambiguous floor/cone silhouettes abstain.

The wall detector cannot certify a ramp or a flat piece merely because it finds
parallel lines. Authored/instrumented providers can supply other topologies via
the same immutable observation without changing the planner or renderer.
"""
from dataclasses import dataclass, asdict, replace
import math
from .edit_observation import EditGridObserver, _line_projection, _crosshair, _general_grid, _partial_grid, _lattice_shift, _tile_support, _segments, downscale, _wall_fit, _vp_grid
from .edit_geometry import piece_context
from .pieces import FLOOR_OR_CONE
import cv2

DETECT_WIDTH=640.   # px the live detectors work at (see VisualObserver.observe)
import numpy as np
UPRIGHT_DEG=5.      # VisualObserver._classify: a 3x3 grid's side edges must meet within this of the centre line
RAMP_DEG=10.        # VisualObserver._tile_piece: a tile-found 3x3 leaning at least this far is a ramp (walls lean <= 6.4)
RAMP_GAP=.12        # ... and real gaps between its tiles (split floor tiles: 0.03-0.12; ramps from 0.107)
from .tile_grid import find_tile_grid

def _upright_offset(q,width):
    """Degrees between where a grid's two side edges (quad 0-3, 1-2) meet and the screen's vertical centre line, seen
    from the grid's centre. 0 for parallel vertical sides. World-vertical edges read 0 when the camera has no roll."""
    q=np.asarray(q,float)
    line=lambda a,b:np.cross([a[0],a[1],1.],[b[0],b[1],1.])
    v=np.cross(line(q[0],q[3]),line(q[1],q[2]))
    if abs(v[2])<1e-9:   # parallel: compare their direction with straight down the screen
        d=q[3]-q[0];return abs(math.degrees(math.atan2(d[0],abs(d[1])+1e-9)))
    p=v[:2]/v[2];m=q.mean(0)
    return abs(math.degrees(math.atan2(p[0]-width/2,abs(p[1]-m[1])+1e-6)))

@dataclass(frozen=True)
class PieceObservation:
    captured_at: float
    piece: str = 'unknown'
    quad: tuple = ()
    aim_uv: tuple = ()
    selected_tiles: tuple = ()
    orientation: str = 'unknown'
    confidence: float = 0.
    supported_cells: int = 0
    reason: str = 'piece_type_unverified'
    source: str = 'screen'
    # Pose-derived context (edit_geometry.PieceContext as a dict): kind, aim in the ranker frame, side, far.
    context: dict | None = None
    def to_dict(self):
        data=asdict(self);data['wall_quad']=self.quad;data['cells']=3 if self.piece=='wall' else 2
        return data

class VisualObserver:
    def __init__(self):self.wall=EditGridObserver()
    def observe(self,frame,now):
        # The full exploratory detector can enumerate hundreds of thousands of
        # line intersections. Keep that offline; this live provider is bounded.
        # DETECT_WIDTH 640: same accuracy as 960 on 224 live frames (131 vs 126 walls), ~25% faster.
        scale=min(1.,DETECT_WIDTH/frame.shape[1])
        image=downscale(frame,scale)
        self.wall._aim_screen=_crosshair(frame)
        aim=(self.wall._aim_screen[0]*scale,self.wall._aim_screen[1]*scale)
        # Vanishing-point finder first (edit_observation._vp_grid, ~16 ms after the shared line search); the detectors
        # below are the fallback when it finds no wall.
        bright=_segments(image)
        found=_vp_grid(image,aim,bright)
        if found is not None:
            count,H,quad,n=found
            wall=self.wall._from_projection(image,H,quad,now,scale,count,.92 if count>=8 else .88,n)
            result=self._classify(image,frame,wall,H,now)
            if result.piece!='unknown':return result
        projection=_line_projection(image)
        if projection is not None:
            count,H,quad=projection
            H,quad,_=_lattice_shift(image,H,aim)
            wall=self.wall._from_projection(image,H,quad,now,scale,count,.93 if count==9 else .88)
            found=self._classify(image,frame,wall,H,now)
            # A rejected projection is not the end: wood planks beside a wall can give it a lattice of the wrong size
            # (live 2026-10-10), while the line detectors below still find the wall.
            if found.piece!='unknown':return found
        # Close / oblique walls whose border runs off screen: rebuild the 3x3 from three lines per direction
        # (bounded ~0.05 s). Then the any-angle detector (walls with selected tiles, 2x2 floors / cones).
        # One line search per frame, shared by both detectors; tighter budgets keep the guide responsive (the
        # strongest line sets are tried first, so most answers come early).
        result=None
        for dark in (False,True):
            # Bright tile gaps first; if nothing fits, once more with dark gaps too (walls in shade at an angle).
            segs=bright if not dark else _segments(image,dark)
            for detect in (_partial_grid,_general_grid):
                # Each detector's grid in turn; the first that passes the piece checks wins (the close-up detector can
                # overshoot into wood beside a wall where the any-angle one fits it).
                found=detect(image,aim,budget=.05 if detect is _partial_grid else .035,segs=segs)
                if found is None:continue
                count,H,quad,n=found
                if n==3:H,quad,_=_lattice_shift(image,H,aim)
                wall=self.wall._from_projection(image,H,quad,now,scale,count,.92 if count>=n*n-1 else .88,n)
                result=self._classify(image,frame,wall,H,now)
                if result.piece!='unknown':return result
        # Last: the tile finder (tile_grid.py) for grids the line finders miss at steep angles, ramps only: a 3x3 that
        # leans well away from upright, with real gaps between its tiles. Floors and cones (2x2) still abstain
        # (tools/eval_frames.py, player-labelled frames 2026-10-22).
        tiled=self._tile_piece(image,frame,aim,now,scale)
        if tiled is not None:return tiled
        return result or PieceObservation(now,reason='bounded_detector_abstained')

    def _tile_piece(self,image,frame,aim,now,scale):
        """Ramp (3x3) or floor / cone (2x2) from the tile finder, or None."""
        found=find_tile_grid(image,aim)
        if found is None:return None
        n,q,count,gap=found
        if n==3 and gap<RAMP_GAP:return None
        if n==2 and count<4:return None                  # a partial 3x3 ramp shows 3 tiles of a 2x2; a floor all 4
        quad=np.float32([q[3],q[2],q[1],q[0]])          # the other finders' corner order: top-left first
        H=cv2.getPerspectiveTransform(np.float32([[0,0],[n,0],[n,n],[0,n]]),quad)
        wall=self.wall._from_projection(image,H,quad,now,scale,count,.88,n)
        if wall.reason!='native_edit_grid_observed':return None
        q=wall.wall_quad
        near=math.dist(q[2],q[3]);far=math.dist(q[0],q[1])
        side=(math.dist(q[0],q[3])+math.dist(q[1],q[2]))/2
        # A sane grid (no edge many times another, far edge not longer than near), leaning at least RAMP_DEG away from
        # upright (a wall); grids between UPRIGHT_DEG and RAMP_DEG abstain.
        if not (.2<far/max(near,1)<1.2 and .15<side/max(near,1)<2) or _upright_offset(q,frame.shape[1])<RAMP_DEG:
            return None
        ctx=piece_context(wall,frame.shape[1],frame.shape[0])
        piece,orientation=('ramp','screen_tile_lattice') if n==3 else ('floor',FLOOR_OR_CONE)
        return PieceObservation(now,piece,q,wall.aim_uv,wall.selected_tiles,orientation,wall.confidence,
                                wall.supported_cells,'native_edit_grid_observed',context=ctx.to_dict() if ctx else None)

    def _classify(self,image,frame,wall,H,now):
        """Wall / floor / cone from one grid hypothesis, or an 'unknown' observation with the reason."""
        if wall.reason!='native_edit_grid_observed':return PieceObservation(now,reason=wall.reason)
        q=wall.wall_quad
        ctx=piece_context(wall,frame.shape[1],frame.shape[0])
        context=ctx.to_dict() if ctx else None
        if wall.cells==2:
            # A cropped 3x3 wall can supply four blue cells. Reject a 2x2
            # hypothesis when native grid tiles continue beyond its boundary.
            if self._continues(image,H):return PieceObservation(now,reason='partial_wall_not_flat_piece')
            if wall.supported_cells<4 or ctx is None:return PieceObservation(now,reason='piece_topology_ambiguous')
            # Floor or cone: the pose guessed (19 of 73 recorded cones read as floors), and both have the same 14 tile
            # selections, so a 2x2 is one "floor / cone" piece (player 2026-10-22; pieces.FLOOR_OR_CONE).
            return PieceObservation(now,'floor',q,wall.aim_uv,wall.selected_tiles,FLOOR_OR_CONE,wall.confidence,
                                    wall.supported_cells,'native_edit_grid_observed',context=context)
        if wall.supported_cells<6 or wall.confidence<.88:
            return PieceObservation(now,reason=wall.reason)
        # Never draw boxes outside the wall: a grid with 3+ cells that are not this wall's tiles is not the wall.
        if _wall_fit(image,H,selected=wall.selected_tiles)[1]>=3:return PieceObservation(now,reason='grid_off_wall')
        # Require a substantial vertical axis. Ramp grids have gesture regions rather than nine equivalent wall tiles.
        width=(math.dist(q[0],q[1])+math.dist(q[2],q[3]))/2
        height=(math.dist(q[0],q[3])+math.dist(q[1],q[2]))/2
        vertical=abs((q[3][1]+q[2][1]-q[0][1]-q[1][1])/2)
        if height<.6*width or vertical<.65*height:
            return PieceObservation(now,reason='piece_topology_ambiguous')
        # A wall's side edges are world-vertical, so (no camera roll) they meet on the screen's vertical centre line; a
        # ramp's, floor's or cone's do not (player 2026-10-21: ramps read as walls). Over 5 deg off: no wall lost on 161
        # recorded walls, 17 of 22 other pieces named wall rejected (tools/eval_frames.py).
        if _upright_offset(q,frame.shape[1])>UPRIGHT_DEG:
            return PieceObservation(now,reason='grid_not_upright')
        return PieceObservation(now,'wall',q,wall.aim_uv,wall.selected_tiles,'screen_front',wall.confidence,
                                wall.supported_cells,'native_edit_grid_observed',context=context)

    def from_quad(self,frame,tracked,now):
        """Re-read a tracked grid without searching for it: aim point, selected tiles and pose from the quad that
        optical flow carried forward (GridMotionTracker.follow). ~5 ms instead of a full detection, so consecutive
        frames of one edit stay fast; selection changes are still read from the pixels of this frame."""
        scale=min(1.,DETECT_WIDTH/frame.shape[1])
        image=downscale(frame,scale)
        n=3 if tracked.piece=='wall' else 2
        quad=np.float32(tracked.quad)*scale
        H=cv2.getPerspectiveTransform(np.float32([[0,0],[n,0],[n,n],[0,n]]),quad)
        self.wall._aim_screen=_crosshair(frame)
        count=_tile_support(image,H,n)
        if count<(6 if n==3 else 4):return None
        wall=self.wall._from_projection(image,H,quad,now,scale,count,.9,n)
        if wall.reason!='native_edit_grid_observed':return None
        # Walls: a grid optical flow slid off the wall (2+ cells that are not this wall's tiles) is dropped and the next
        # full detection replaces it; a wrongly dropped grid only costs that detection. Together with the 6-tile minimum
        # this drops 61% of grids slid by a tile on 143 recorded walls, and 6% of correct ones.
        if n==3 and _wall_fit(image,H,selected=wall.selected_tiles)[1]>=2:return None
        # A carried wall that no longer stands upright is not this wall any more (live 2026-10-22: the track of a wall
        # followed the view onto a ramp and kept calling it a wall); drop it so a full detection decides.
        if tracked.piece=='wall' and _upright_offset(wall.wall_quad,frame.shape[1])>UPRIGHT_DEG:return None
        ctx=piece_context(wall,frame.shape[1],frame.shape[0])
        return PieceObservation(now,tracked.piece,wall.wall_quad,wall.aim_uv,wall.selected_tiles,tracked.orientation,
                                wall.confidence,wall.supported_cells,'native_edit_grid_observed','tracked_refined',
                                context=ctx.to_dict() if ctx else tracked.context)

    @staticmethod
    def _continues(image,H):
        projected=cv2.warpPerspective(image,np.array([[100.,0,100.],[0,100.,100.],[0,0,1.]])@np.linalg.inv(H),(400,400))
        for c,r in ((0,1),(0,2),(3,1),(3,2),(1,0),(2,0),(1,3),(2,3)):
            tile=projected[r*100+20:r*100+80,c*100+20:c*100+80]
            blue=((tile[:,:,0]>tile[:,:,2]*1.2)&(tile[:,:,0]>80)).mean()
            # Native blue edit tiles continuing at matching scale are stronger
            # evidence than the planar-camera above/below heuristic.
            red=((tile[:,:,2]>tile[:,:,0]*1.2)&(tile[:,:,2]>80)&(tile[:,:,1]<100)).mean()
            if blue+red>.70:return True
        return False

class PieceTargetTracker:
    """Continuity tracking never equates a fixed global grid plane with a build."""
    def __init__(self,grace=1.25):self.last=None;self.serial=0;self.grace=grace
    def update(self,observation):
        if observation.piece=='unknown':return None
        if self.last is None or observation.piece!=self.last.piece or observation.captured_at-self.last.captured_at>self.grace:
            self.serial+=1
        elif len(observation.quad)==4 and len(self.last.quad)==4:
            diagonal=max(1.,math.dist(self.last.quad[0],self.last.quad[2]))
            if max(math.dist(a,b) for a,b in zip(observation.quad,self.last.quad))>diagonal*.25:self.serial+=1
        self.last=observation
        return f'{observation.piece}:{self.serial}'


class GridMotionTracker:
    """Carry a detected target through short segmentation gaps using image motion.

    A carried selection is unknown: tracking supplies position, never new edit
    accuracy evidence. Lost features, target changes and expired tracks abstain.
    """
    def __init__(self, grace=2.):
        self.grace=grace;self.reset()
    def reset(self):self.grey=None;self.points=None;self.observation=None;self.detected_at=-math.inf;self.scale=1.
    def seed(self,frame,observation):
        self.scale=min(1.,DETECT_WIDTH/frame.shape[1])   # same size as the detectors: one shared resize
        small=downscale(frame,self.scale)
        grey=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
        mask=np.zeros(grey.shape,np.uint8)
        cv2.fillConvexPoly(mask,(np.asarray(observation.quad)*self.scale).astype(np.int32),255)
        points=cv2.goodFeaturesToTrack(grey,60,.02,10,mask=mask)   # 60 points: enough for a robust homography, faster LK
        self.grey=grey;self.points=points;self.observation=observation;self.detected_at=observation.captured_at
    def follow(self,frame,now,verify=True):
        if self.observation is None or self.points is None or now-self.detected_at>self.grace:return None
        small=downscale(frame,self.scale)
        grey=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
        if grey.shape!=self.grey.shape:self.reset();return None
        nxt,status,error=cv2.calcOpticalFlowPyrLK(self.grey,grey,self.points,None)
        if nxt is None:return None
        good=(status.ravel()==1)&(error.ravel()<20)
        if good.sum()<12:return None
        H,inliers=cv2.findHomography(self.points[good],nxt[good],cv2.RANSAC,2.5)
        if H is None or inliers.sum()<12 or inliers.mean()<.75:return None
        old=np.asarray(self.observation.quad,np.float32)*self.scale
        quad=cv2.perspectiveTransform(old.reshape(1,4,2),H)[0]
        area=abs(cv2.contourArea(quad));oldarea=abs(cv2.contourArea(old))
        if not .65*oldarea<area<1.5*oldarea:return None
        quad=quad/self.scale
        if self.observation.piece=='wall' and _upright_offset(quad,frame.shape[1])>UPRIGHT_DEG:return None
        cross=_crosshair(frame)
        if cv2.pointPolygonTest(quad,cross,True)<-min(frame.shape[:2])*.025:return None
        n=3 if self.observation.piece=='wall' else 2
        native=cv2.getPerspectiveTransform(np.array([[0,0],[n,0],[n,n],[0,n]],np.float32),quad)
        # verify=False when the caller re-reads the grid anyway (VisualObserver.from_quad checks tile support itself).
        if verify and _tile_support(frame[:,:,:3],native,n)<(6 if n==3 else 4):return None
        grid=np.array([[0,n],[n,n],[n,0],[0,0]],np.float32)
        projection=cv2.getPerspectiveTransform(quad,grid)
        aim=cv2.perspectiveTransform(np.array([[cross]],np.float32),projection)[0,0]
        obs=replace(self.observation,captured_at=now,quad=tuple(map(tuple,quad.tolist())),
                    aim_uv=tuple(float(min(max(v,0.),n-1e-4)) for v in aim),source='optical_flow',reason='target_motion_tracked')
        ctx=piece_context(obs.to_dict(),frame.shape[1],frame.shape[0])
        if ctx:obs=replace(obs,context=ctx.to_dict())
        self.grey=grey;self.points=nxt[good].reshape(-1,1,2);self.observation=obs
        return obs
