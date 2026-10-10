"""Vector layouts driven by topology, shared by previews and live UI."""
from dataclasses import dataclass
from .edit_dictionary import RoutePlanner

@dataclass(frozen=True)
class GuideVisual:
    title: str
    regions: tuple
    selected: tuple
    path: tuple
    approach: tuple
    labels: tuple
    result_shape: str

def layout(edit,aim):
    ramp=edit['piece']=='ramp'
    n=1 if ramp else edit['cols']
    route=RoutePlanner().plan(aim,edit)
    regions=tuple((c/n,r/n,(c+1)/n,(r+1)/n) for r in range(n) for c in range(n)) if not ramp else ()
    if route:
        _,points,order=route
        points=tuple((u/n,1-v/n) for u,v in points)
        labels=tuple((str(i+1),p) for i,p in enumerate(points))
        approach=((aim[0]/n,1-aim[1]/n),points[0])
    else:points=();labels=();approach=()
    return GuideVisual(edit['name'],regions,tuple(edit.get('tiles',())),points,approach,labels,edit.get('result_shape',''))
