"""Targeted, repeatable team-room and military-cover pass. Never rebuilds the map.

Owns KT30_Balance_; intentionally relocates named perimeter, vendor and truck actors.
Default prints the plan. --apply saves changes and a before/readback audit.
Does not enable Rift acceptance gates or change match/guide source.
"""
import argparse
import json
from pathlib import Path
import build_map as bm

PREFIX = 'KT30_Balance_'
P = '/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_{0}.PPID_CR_Legacy_{0}'
ASSETS = {k:P.format(v) for k,v in {
    'truck':'Car_SemiTruck_Tractor', 'shield':'Athena_Prop_SilkyTanker',
    'wall':'MilitaryBase_HalfWall', 'crate':'MilitaryBase_Metal_Crate_01',
    'bags':'Apollo_TaskForce_Sand_Bag_Wall_01'}.items()}

def world(x,y):
    return (140+x)*512,(-117+y)*512

def room_slabs():
    result=[]
    def slab(name,x0,x1,y0,y1,top,thick,mat='Armory'):
        ax,ay=world(x0,y0);bx,by=world(x1,y1)
        result.append(dict(label=PREFIX+name,bounds=(ax,bx,ay,by),top=top,thick=thick,mat=mat))
    for side,left,right,mat in [('Red',-3,0,'Build'),('Blue',16,19,'Piece')]:
        slab(side+'RoomFloor',left,right,6,10,0,100)
        slab(side+'RoomRoof',left,right,6,10,384,24)
        back=left if side=='Red' else right
        slab(side+'RoomBack',back-.04,back+.04,6,10,384,384,mat)
        for y in (6,10): slab(side+'RoomSide'+str(y),left,right,y-.04,y+.04,384,384,mat)
        # Door has a full two-cell opening. Inner baffle prevents a straight
        # sightline from the centre objective to the vending alcove.
        front=right if side=='Red' else left
        for y0,y1 in [(6,7),(9,10)]: slab(side+'Door'+str(y0),front-.04,front+.04,y0,y1,384,384,mat)
        bx=left+1.5
        slab(side+'Baffle',bx-.04,bx+.04,7.5,8.5,384,384,mat)
        slab(side+'EntryStripe',left,right,7,7.08,1,1,mat)
    return result

def cover_plan():
    # Equal asset budgets and objective distances; staggered crate dressing.
    items=[]
    for side,x,yaw in [('Red',6,0),('Blue',10,180)]:
        items.append((side+'ServiceTruck','truck',x,2.5,16,yaw))
        wx=x+(.5 if side=='Red' else -.5)
        items.append((side+'MidWall','wall',wx,6,0,90))
        items.append((side+'MidWallRear','wall',wx,10,0,90))
        for i,dy in enumerate((-.25,.25)):
            items.append((side+'MetalCrate'+str(i),'crate',x+(0.75 if side=='Red' else -.75),11+dy,0,yaw))
        items.append((side+'Sandbags','bags',x+(.75 if side=='Red' else -.75),4.5,0,yaw))
    return items

def apply():
    b=bm.Builder();m=b.m
    if m.tool(bm.SCENE,'get_current_level')!=bm.MODULE+'/KeystrokeTrainer':
        raise RuntimeError('Wrong island')
    if m.tool('ValkyrieToolset.SessionToolset','GetGameState')!='CanStart':
        raise RuntimeError('Stop the match before applying geometry')
    all_actors=m.tool(bm.SCENE,'find_actors',name='',collision_channels=[])
    by={a['label']:a for a in all_actors}
    audit=Path('design/team-balance-before.local.json')
    if not audit.exists(): audit.write_text(json.dumps(all_actors,indent=2))
    touched=[]
    def save(path):
        m.tool(bm.SCENE,'save_actor',actor={'refPath':path});touched.append(path)
    def move(label,x,y,z=0,yaw=0,scale=None):
        path=by[label]['actorPath'];xf=bm.xform(*world(x,y),z,yaw=yaw)
        if scale: xf['scale']=dict(zip(('x','y','z'),scale))
        m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':path},xform=xf);save(path)
    for s in room_slabs():
        if s['label'] not in by: save(b.slab(s))
    # Split the existing end walls to connect the extensions, never delete them.
    for side,x in [('West',0),('East',16)]:
        move('KT21_Team_Edge'+side,x,3,0,scale=(.4096,30.72,3.84))
        label=PREFIX+side+'EdgeUpper'
        if label not in by:
            wx,wy=world(x,10);_,ey=world(x,16)
            save(b.slab(dict(label=label,bounds=(wx-20.48,wx+20.48,wy,ey),top=384,thick=384,mat='Armory')))
    def prop(label,kind,x,y,z=0,yaw=0):
        label=PREFIX+label
        if label in by:
            move(label,x,y,z,yaw)
            return by[label]['actorPath']
        xf=bm.xform(*world(x,y),z,yaw=yaw)
        ref=m.tool(bm.SCENE,'add_to_scene_from_asset',asset_path=ASSETS[kind],name=label,xform=xf)
        m.tool(bm.ACTOR,'set_actor_transform',actor=ref,xform=xf)
        b.labelled(ref['refPath'],label);save(ref['refPath'])
        return ref['refPath']
    for entry in cover_plan(): prop(*entry)
    # Preserve the original destructible tanker and add the same native asset.
    move('KT24_Team_TruckRedProp',1.5,4,0,90)
    prop('BlueShieldTruck','shield',14.5,4,0,90)
    # Existing upper-lane trucks now have equal distance from the centre.
    move('KT26_TeamDetail_LoadingTruckRed',6,13,16,0)
    move('KT26_TeamDetail_LoadingTruckBlue',10,13,16,180)
    for side,x,yaw in [('Red',-2.55,0),('Blue',18.55,180)]:
        move('KT29_Rift_'+side+'Vendor',x,7,128,yaw)
        label=PREFIX+side+'RoomNoFire'
        if label not in by:
            path=b.device('/CRD_VolumetricRegion/SetupAssets/PID_Device_Mutator.PID_Device_Mutator',label,*world(-1.5 if side=='Red' else 17.5,8),0)
        else:
            path=by[label]['actorPath']
        schema=m.tool(bm.OBJ,'list_properties',instance={'refPath':path})
        schema=json.loads(schema) if isinstance(schema,str) else schema
        settings=dict(zoneWidth=3,zoneDepth=4,zoneHeight=1,bAllowBuilding=False,bAllowEditing=False,
                      bAllowWeaponFire=False,bAffectsPlayers=True,enabledOnPhase='Gameplay Only',
                      zoneVisibleDuringGame=False)
        if set(settings)-set(schema): raise RuntimeError('Mutator schema changed')
        b.props(path,settings);save(path)
        # Move the existing tagged Rift protection into the visible rooms too.
        # Runtime team ignore lists and acceptance gates remain unchanged.
        rx=-1.5 if side=='Red' else 17.5
        for suffix,values in [('Safe',dict(zoneWidth=3,zoneDepth=4,zoneHeight=1)),
                              ('SafeWall',dict(barrierWidth=3,barrierDepth=4,barrierHeight=1))]:
            existing='KT29_Rift_'+side+suffix
            move(existing,rx,8)
            ref={'refPath':by[existing]['actorPath']}
            m.tool(bm.OBJ,'list_properties',instance=ref)
            b.props(ref['refPath'],values);save(ref['refPath'])
    # All three reboot locations are on the neutral centre line, outside rooms.
    # Keep their native five-second buttons beside each van and clear of C.
    for name,y in [('South',2),('Centre',5.5),('North',14)]:
        move('KT24_Team_Reboot'+name,8,y,0,90)
        move('KT24_Team_Reboot'+name+'Use',8,y+.8,100,0)
    read=m.tool(bm.SCENE,'find_actors',name='',collision_channels=[])
    selected=[a for a in read if a['actorPath'] in touched or a['label'].startswith(PREFIX)]
    Path('design/team-balance-readback-2026-10-13.json').write_text(json.dumps(selected,indent=2))
    print('Saved',len(touched),'actors; native playtest and upload validation still required.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.apply: apply()
    else: print(json.dumps({'rooms':room_slabs(),'cover':cover_plan()},indent=2))
