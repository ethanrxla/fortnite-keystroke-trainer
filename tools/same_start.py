"""Keep the thirteen remaining lanes on track one; never rebuild a district.

Dry-run by default. --apply configures and saves only the named lane devices and
KT31_Clear_<code>_Track1 barrels. Event bindings are idempotent. Edit lanes are
skipped unless their track-one authored wall reads back as damage-proof and
structurally supported. No drill catalog, section or plate is changed.
"""
import argparse
import sys
import json
from pathlib import Path
import build_map as bm

CODES = ('P2','P6','P7','B2','B3','B5','E2','E4','E5','E7','W1','W2','W3')
PROPS = {'blast Radius':8, 'player Damage':0, 'structure Damage':100000,
         'visible During Game':False, 'knockbackPlayer':0}

def decoded(value):
    return json.loads(value) if isinstance(value,str) else value

def run(apply=False, report='design/same-start-readback-2026-10-13.json'):
    # MILESTONE 2026-10-13 guard: superseded: only 90s and box up keep one track, and a barrel on a lane start blocks the teleport there. Pass --i-know to run anyway.
    if "--i-know" not in sys.argv:
        raise SystemExit("same_start.py: superseded: only 90s and box up keep one track, and a barrel on a lane start blocks the teleport there. (milestone 2026-10-13). Pass --i-know to run anyway.")
    sys.argv.remove("--i-know")
    b=bm.Builder();m=b.m
    if m.tool(bm.SCENE,'get_current_level') != bm.MODULE+'/KeystrokeTrainer':
        raise RuntimeError('Wrong level')
    actors=m.tool(bm.SCENE,'find_actors',name='',collision_channels=[])
    def one(label):
        matches=[a for a in actors if a['label']==label]
        if len(matches)!=1: raise RuntimeError(f'{label}: expected one actor, found {len(matches)}')
        return {'refPath':matches[0]['actorPath']}
    rows=[]
    for code in CODES:
        lane=one('KT_Lane_'+code);trigger=one('KT3_Clear_'+code)
        row={'code':code,'lane':lane,'trigger':trigger}
        if code.startswith('E'):
            wall=one('KT_EditWall_'+code+'_0')
            m.tool(bm.OBJ,'list_properties',instance=wall)
            state=decoded(m.tool(bm.OBJ,'get_properties',instance=wall,
                                 properties=['bCanBeDamaged','bForciblyStructurallySupported']))
            row['wall']=state
            if state.get('bCanBeDamaged') is not False or state.get('bForciblyStructurallySupported') is not True:
                row['skipped']='Authored edit wall is not verified damage-proof/supported'
                rows.append(row);continue
        row['before']=decoded(m.tool(bm.DEVICE,'GetDeviceProperties',device=lane,
                                     propertyNames=['sameTrack','clearEachRep','repRestSeconds']))
        # Rep 1 is exactly the placed lane origin, irrespective of catalog advance.
        origin=m.tool(bm.ACTOR,'get_actor_transform',actor=lane)['location']
        xf=bm.xform(origin['x'],origin['y'],origin['z'])
        label=f'KT31_Clear_{code}_Track1'
        row['barrel_label']=label;row['barrel_transform']=xf
        if apply:
            existing=[a for a in actors if a['label']==label]
            if len(existing)>1: raise RuntimeError('Duplicate barrel: '+label)
            path=existing[0]['actorPath'] if existing else b.device(bm.EXPLOSIVE,label,origin['x'],origin['y'],origin['z'])
            barrel={'refPath':path}
            m.tool(bm.OBJ,'list_properties',instance=barrel)
            b.props(path,PROPS)
            m.tool(bm.ACTOR,'set_actor_transform',actor=barrel,xform=xf)
            b.bind(trigger['refPath'],'OnTriggered',path,'Explode')
            b.bind(path,'On Exploded',path,'Reset')
            row['barrel_settings']=decoded(m.tool(bm.OBJ,'get_properties',instance=barrel,properties=list(PROPS)))
            if row['barrel_settings']!=PROPS: raise RuntimeError('Barrel settings differ: '+code)
            row['bindings']=m.tool(bm.DEVICE,'ListEventBindings',devicePath=barrel)
            for source,event,fn in [(trigger,'OnTriggered','Explode'),(barrel,'On Exploded','Reset')]:
                if not any(v['sourceDevicePath']==source and v['sourceEvent']==event and
                           v['targetDevicePath']==barrel and v['targetFunction']==fn for v in row['bindings']):
                    raise RuntimeError('Missing binding: '+code+' '+event)
            for name in ('sameTrack','clearEachRep'):
                m.tool(bm.DEVICE,'SetDeviceProperty',device=lane,propertyName=name,value='true')
            row['after']=decoded(m.tool(bm.DEVICE,'GetDeviceProperties',device=lane,
                                       propertyNames=['sameTrack','clearEachRep','repRestSeconds']))
            if not (row['after']['sameTrack'] is True and row['after']['clearEachRep'] is True):
                raise RuntimeError('Lane settings differ: '+code)
            m.tool(bm.SCENE,'save_actor',actor=barrel)
            m.tool(bm.SCENE,'save_actor',actor=lane)
        rows.append(row)
        print(code, 'saved' if apply else 'ready',flush=True)
    if apply: Path(report).write_text(json.dumps(rows,indent=2),encoding='utf-8')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    run(a.apply)
