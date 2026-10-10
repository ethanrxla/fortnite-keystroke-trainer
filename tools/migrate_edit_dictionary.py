"""Idempotent metadata migration and exhaustive mask coverage ledger. No game validation is invented."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    path=ROOT/'shared/edits.json';data=json.loads(path.read_text(encoding='utf-8'));data['version']=2
    for piece,meta in data['pieces'].items():
        for e in data[meta['list']]:
            e.setdefault('validation',{'status':'unverified','game_version':None,'evidence':[], 'result_confirmed':False,
                'reason':'Legacy confirmed flag is not recorded in-game verification.'})
            e['topology']='gesture_graph' if piece=='stairs' else 'selection_grid'
            e['mask']=[[int(r*meta['cols']+c in e['tiles']) for c in range(meta['cols'])] for r in range(meta['rows'])] if piece!='stairs' else None
            e.setdefault('result_shape',e['name']);e.setdefault('preconditions',['editable_target','standard_editing'])
            e.setdefault('reset','native_reset');e.setdefault('transforms',{'mirror':e.get('mirror_of'),'rotations':[]})
            if piece=='stairs':
                e.setdefault('gesture',{'nodes':{'near_left':[0.,0.],'near_middle':[.5,0.],'near_right':[1.,0.],
                   'left_middle':[0.,.5],'right_middle':[1.,.5],'far_left':[0.,1.],'far_middle':[.5,1.],'far_right':[1.,1.]},
                   'edges':[],'routes':[],'status':'requires_recorded_gesture'})
    coverage={}
    for piece,n in [('wall',9),('floor',4),('roof',4)]:
        entries=data[data['pieces'][piece]['list']]
        coverage[piece]=[{'mask':m,'status':'unverified','edit_ids':[e['id'] for e in entries if sum(1<<t for t in e['tiles'])==m]} for m in range(1<<n)]
    data['coverage_ledger']='edit-coverage.json'
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    out=ROOT/'shared/edit-coverage.json'
    if not out.exists():out.write_text(json.dumps({'version':1,'pieces':coverage,'ramp':'Gesture graphs require separate validation.'},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
