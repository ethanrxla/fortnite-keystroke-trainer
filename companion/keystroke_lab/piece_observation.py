"""Piece-aware observation boundary. Ambiguous floor/cone silhouettes abstain.

The wall detector cannot certify a ramp or a flat piece merely because it finds
parallel lines. Authored/instrumented providers can supply other topologies via
the same immutable observation without changing the planner or renderer.
"""
from dataclasses import dataclass, asdict, replace
import math
from .edit_observation import EditGridObserver, _line_projection, _crosshair, _general_grid, _partial_grid, _tile_support, _segments, downscale
from .edit_geometry import piece_context
import cv2

DETECT_WIDTH=640.   # px the live detectors work at (see VisualObserver.observe)
import numpy as np

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
        projection=_line_projection(image)
        if projection is not None:
            count,H,quad=projection
            wall=self.wall._from_projection(image,H,quad,now,scale,count,.93 if count==9 else .88)
        else:
            aim=(self.wall._aim_screen[0]*scale,self.wall._aim_screen[1]*scale)
            # Close / oblique walls whose border runs off screen: rebuild the 3x3 from three lines per direction
            # (bounded ~0.05 s). Then the any-angle detector (walls with selected tiles, 2x2 floors / cones).
            # One line search per frame, shared by both detectors; tighter budgets keep the guide responsive (the
            # strongest line sets are tried first, so most answers come early).
            segs=_segments(image)
            found=_partial_grid(image,aim,budget=.05,segs=segs) or _general_grid(image,aim,budget=.035,segs=segs)
            if found is None:return PieceObservation(now,reason='bounded_detector_abstained')
            count,H,quad,n=found
            wall=self.wall._from_projection(image,H,quad,now,scale,count,.92 if count>=n*n-1 else .88,n)
        if wall.reason!='native_edit_grid_observed':return PieceObservation(now,reason=wall.reason)
        q=wall.wall_quad
        ctx=piece_context(wall,frame.shape[1],frame.shape[0])
        context=ctx.to_dict() if ctx else None
        if wall.cells==2:
            # A cropped 3x3 wall can supply four blue cells. Reject a 2x2
            # hypothesis when native grid tiles continue beyond its boundary.
            if self._continues(image,H):return PieceObservation(now,reason='partial_wall_not_flat_piece')
            if wall.supported_cells<4 or ctx is None:return PieceObservation(now,reason='piece_topology_ambiguous')
            # Floor below the camera / cone overhead, from the pose. A cone at floor height reads as a floor: the
            # orientation says it is an estimate and the UI labels it so.
            piece='floor' if ctx.kind=='floor' else 'cone'
            return PieceObservation(now,piece,q,wall.aim_uv,wall.selected_tiles,'screen_pose_estimate',wall.confidence,
                                    wall.supported_cells,'native_edit_grid_observed',context=context)
        if wall.supported_cells<6 or wall.confidence<.88:
            return PieceObservation(now,reason=wall.reason)
        # Require a substantial vertical axis. Ramp grids have gesture regions rather than nine equivalent wall tiles.
        width=(math.dist(q[0],q[1])+math.dist(q[2],q[3]))/2
        height=(math.dist(q[0],q[3])+math.dist(q[1],q[2]))/2
        vertical=abs((q[3][1]+q[2][1]-q[0][1]-q[1][1])/2)
        if height<.6*width or vertical<.65*height:
            return PieceObservation(now,reason='piece_topology_ambiguous')
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
