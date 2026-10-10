"""Piece-aware observation boundary. Ambiguous floor/cone silhouettes abstain.

The wall detector cannot certify a ramp or a flat piece merely because it finds
parallel lines. Authored/instrumented providers can supply other topologies via
the same immutable observation without changing the planner or renderer.
"""
from dataclasses import dataclass, asdict
import math
from .edit_observation import EditGridObserver, _line_projection, _crosshair, _general_grid
from .edit_geometry import piece_context
import cv2

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
        data=asdict(self);data['wall_quad']=self.quad
        return data

class VisualObserver:
    def __init__(self):self.wall=EditGridObserver()
    def observe(self,frame,now):
        # The full exploratory detector can enumerate hundreds of thousands of
        # line intersections. Keep that offline; this live provider is bounded.
        scale=min(1.,960./frame.shape[1])
        image=cv2.resize(frame[:,:,:3],(round(frame.shape[1]*scale),round(frame.shape[0]*scale)))
        self.wall._aim_screen=_crosshair(frame)
        projection=_line_projection(image)
        if projection is not None:
            count,H,quad=projection
            wall=self.wall._from_projection(image,H,quad,now,scale,count,.93 if count==9 else .88)
        else:
            # Any-angle fallback (bounded to ~0.08 s): walls with selected tiles, and 2x2 floors / cones.
            general=_general_grid(image,(self.wall._aim_screen[0]*scale,self.wall._aim_screen[1]*scale))
            if general is None:return PieceObservation(now,reason='bounded_detector_abstained')
            count,H,quad,n=general
            wall=self.wall._from_projection(image,H,quad,now,scale,count,.92 if count==n*n else .88,n)
        if wall.reason!='native_edit_grid_observed':return PieceObservation(now,reason=wall.reason)
        q=wall.wall_quad
        ctx=piece_context(wall,frame.shape[1],frame.shape[0])
        context=ctx.to_dict() if ctx else None
        if wall.cells==2:
            if wall.supported_cells<4 or ctx is None:return PieceObservation(now,reason='piece_topology_ambiguous')
            # Floor below the camera / cone overhead, from the pose. A cone at floor height reads as a floor: the
            # orientation says it is an estimate and the UI labels it so.
            piece='floor' if ctx.kind=='floor' else 'cone'
            return PieceObservation(now,piece,q,wall.aim_uv,wall.selected_tiles,'screen_pose_estimate',wall.confidence,
                                    wall.supported_cells,'native_edit_grid_observed',context=context)
        if wall.supported_cells<8 or wall.confidence<.88:
            return PieceObservation(now,reason=wall.reason)
        # Require a substantial vertical axis. Ramp grids have gesture regions rather than nine equivalent wall tiles.
        width=(math.dist(q[0],q[1])+math.dist(q[2],q[3]))/2
        height=(math.dist(q[0],q[3])+math.dist(q[1],q[2]))/2
        vertical=abs((q[3][1]+q[2][1]-q[0][1]-q[1][1])/2)
        if height<.6*width or vertical<.65*height:
            return PieceObservation(now,reason='piece_topology_ambiguous')
        return PieceObservation(now,'wall',q,wall.aim_uv,wall.selected_tiles,'screen_front',wall.confidence,
                                wall.supported_cells,'native_edit_grid_observed',context=context)

class PieceTargetTracker:
    """Continuity tracking never equates a fixed global grid plane with a build."""
    def __init__(self):self.last=None;self.serial=0
    def update(self,observation):
        if observation.piece=='unknown':self.last=None;return None
        if self.last is None or observation.piece!=self.last.piece or observation.captured_at-self.last.captured_at>.25:
            self.serial+=1
        elif len(observation.quad)==4 and len(self.last.quad)==4:
            diagonal=max(1.,math.dist(self.last.quad[0],self.last.quad[2]))
            if max(math.dist(a,b) for a,b in zip(observation.quad,self.last.quad))>diagonal*.25:self.serial+=1
        self.last=observation
        return f'{observation.piece}:{self.serial}'
