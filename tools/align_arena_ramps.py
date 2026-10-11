"""Targeted, backed-up lateral pivot correction. Never rebuilds the 1v1 arena."""
import argparse
import datetime
import json
import build_map as bm

TARGETS={'KT10_Arena_Ramp_A':(-31744,-77568,0,270),
         'KT10_Arena_Ramp_B':(-31232,-76032,0,90)}

def apply():
    m=bm.Mcp()
    actors=m.tool(bm.SCENE,'find_actors',name='KT10_Arena_Ramp_',collision_channels=[])
    by={a['label']:a for a in actors}
    if set(TARGETS)-by.keys():raise RuntimeError('Expected both native ramps')
    before={k:m.tool(bm.ACTOR,'get_actor_transform',actor={'refPath':by[k]['actorPath']}) for k in TARGETS}
    folder=bm.ROOT/'backups';folder.mkdir(exist_ok=True)
    (folder/('arena-ramp-pivots-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')).write_text(json.dumps(before,indent=2))
    for label,(x,y,z,yaw) in TARGETS.items():
        ref={'refPath':by[label]['actorPath']}
        m.tool(bm.ACTOR,'set_actor_transform',actor=ref,xform=bm.xform(x,y,z,yaw=yaw))
        actual=m.tool(bm.ACTOR,'get_actor_transform',actor=ref)
        if actual['location']!={'x':x,'y':y,'z':z}:raise RuntimeError('Transform did not retain')
        m.tool(bm.SCENE,'save_actor',actor=ref)
    print('Corrected only the two native 1v1 ramp pivots; client build-edge verification still required.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    print(TARGETS)
    if a.apply:apply()
