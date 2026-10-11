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
    strokes: tuple = ()
    approaches: tuple = ()

def layout(edit,aim,strokes=None):
    n=edit['cols']
    strokes=RoutePlanner(inset=.35).strokes(aim,edit) if strokes is None else strokes
    paths=tuple(tuple((u/n,1-v/n) for u,v in s) for s in strokes)
    regions=tuple((c/n,r/n,(c+1)/n,(r+1)/n) for r in range(n) for c in range(n))
    labels=tuple((str(i+1),p) for i,p in enumerate(p for s in paths for p in s))
    approaches=[];previous=(aim[0]/n,1-aim[1]/n)
    for path in paths:
        approaches.append((previous,path[0]));previous=path[-1]
    return GuideVisual(edit['name'],regions,tuple(edit.get('tiles',())),paths[0] if paths else (),
                       approaches[0] if approaches else (),labels,edit.get('result_shape',''),paths,tuple(approaches))
