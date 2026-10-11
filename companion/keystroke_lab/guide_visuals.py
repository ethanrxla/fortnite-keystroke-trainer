"""Vector layouts driven by topology, shared by previews and live UI."""
from dataclasses import dataclass
from .edit_dictionary import RoutePlanner
from .build_pieces import get_piece

@dataclass(frozen=True)
class GuideVisual:
    title: str
    regions: tuple
    selected: tuple
    path: tuple
    approach: tuple
    labels: tuple
    result_shape: str
    route_mode: str = 'drag'

def layout(edit,aim):
    piece=get_piece(edit['piece']);n=piece.cells
    planned=RoutePlanner(inset=.35).route(aim,edit)
    route=planned.legacy() if planned else None
    regions=piece.regions()
    if route:
        _,points,order=route
        points=tuple((u/n,1-v/n) for u,v in points)
        labels=tuple((str(i+1),p) for i,p in enumerate(points))
        approach=((aim[0]/n,1-aim[1]/n),points[0])
    else:points=();labels=();approach=()
    return GuideVisual(edit['name'],regions,tuple(edit.get('tiles',())),points,approach,labels,edit.get('result_shape',''),planned.mode if planned else 'drag')
