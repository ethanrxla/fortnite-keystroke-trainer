"""Add a three-story grid shell with distinct but equally sized base buildings.

Native stair pivots are measured after placement, then aligned to the planned
512 cm cell footprint. No old actors are deleted. --apply is opt-in.
"""
import argparse
import json
import build_map as bm

PREFIX='KT25_Compound_'
ANCHOR=(140,-117)
C=512
H=384
STAIR='/Game/Building/ActorBlueprints/Player/Wood/L1/PBWA_W1_StairW.PBWA_W1_StairW_C'

def cells(side,level):
    start=0 if side=='Red' else 10
    holes={('Red',1):{(3,5),(1,8)},('Red',2):{(0,9),(4,8)},
           ('Blue',1):{(12,10),(14,8)},('Blue',2):{(15,6),(11,8)}}[(side,level)]
    return {(x,y) for x in range(start,start+6) for y in range(5,11)}-holes

def floors():
    return [dict(label=f'{PREFIX}{side}_Floor_{level}_{x}_{y}',
                 bounds=((140+x)*C,(141+x)*C,(-117+y)*C,(-116+y)*C),
                 top=level*H,thick=16,mat='Armory')
            for side in ('Red','Blue') for level in (1,2) for x,y in sorted(cells(side,level))]

def stairs():
    return [('Red_Up1',3,5,0,0),('Red_Up2',0,9,1,90),
            ('Blue_Up1',12,10,0,180),('Blue_Up2',15,6,1,270)]

def walls():
    result=[]
    # A vertical corridor in Red, a horizontal corridor in Blue. Each has three
    # wall cells, a full-width player-build doorway and the same total cover.
    for side in ('Red','Blue'):
        for level in (1,2):
            for n in (0,1,3):
                if side=='Red':x0,x1,y0,y1=3-.03125,3+.03125,6+n,7+n
                else:x0,x1,y0,y1=11+n,12+n,9-.03125,9+.03125
                result.append(dict(label=f'{PREFIX}{side}_Wall_{level}_{n}',
                    bounds=((140+x0)*C,(140+x1)*C,(-117+y0)*C,(-117+y1)*C),
                    top=(level+1)*H,thick=H,mat='Build' if side=='Red' else 'Piece'))
    return result

def validate():
    for level in (1,2):
        if len(cells('Red',level))!=len(cells('Blue',level)):
            raise ValueError('Unequal floor area')
        if {(15-x,y) for x,y in cells('Red',level)}==cells('Blue',level):
            raise ValueError('The two buildings should have distinct openings')
    for s in floors():
        if s['top']%H or any(v%C for v in s['bounds']):raise ValueError('Off build grid')

def apply():
    validate();b=bm.Builder()
    if b.m.tool(bm.SCENE,'get_current_level')!=bm.MODULE+'/KeystrokeTrainer':raise RuntimeError('Wrong island')
    actors=b.m.tool(bm.SCENE,'find_actors',name='',collision_channels=[])
    existing={a['label']:a['actorPath'] for a in actors}
    if 'KT21_Team_Floor' not in existing:raise RuntimeError('Missing team floor')
    for s in floors()+walls():
        if s['label'] in existing:continue
        path=b.slab(s);b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
    for name,i,j,level,yaw in stairs():
        label=PREFIX+name
        if label in existing:continue
        x,y=(140+i+.5)*C,(-117+j+.5)*C
        r=b.m.tool(bm.SCENE,'add_to_scene_from_asset',asset_path=STAIR,name=label,xform=bm.xform(x,y,level*H,yaw=yaw))
        path=b.labelled(r['refPath'],label)
        # Read the native mesh's bounds; rotated stair roots are not tile centres.
        found=b.m.tool(bm.SCENE,'find_actors',name=label,collision_channels=[])
        bounds=next(a['bounds'] for a in found if a['label']==label)
        midx=(bounds['min']['x']+bounds['max']['x'])/2
        midy=(bounds['min']['y']+bounds['max']['y'])/2
        dx=round((x-midx)/256)*256;dy=round((y-midy)/256)*256
        b.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':path},xform=bm.xform(x+dx,y+dy,level*H,yaw=yaw))
        b.m.tool(bm.OBJ,'list_properties',instance={'refPath':path})
        b.props(path,{'bCanBeDamaged':False})
        b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
    print('Added grid-aligned three-story shell: 136 floor cells, 12 corridor walls, 4 stairs. Live traversal/balance still required.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();validate()
    print(json.dumps({'floors':len(floors()),'walls':len(walls()),'stairs':len(stairs()),'floor_levels_cm':[0,384,768]}))
    if a.apply:apply()
