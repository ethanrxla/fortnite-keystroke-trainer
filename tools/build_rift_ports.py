"""Additive Rift integration devices, disabled until native acceptance.

Does not register guessed items, enable verification gates, push or restart a game.
Only KT29_Rift_ actors are modified. Save/readback reports distinguish wiring from validation.
"""
import argparse
import json
from pathlib import Path
import build_map as bm

PREFIX='KT29_Rift_'
DEV=bm.DEV
ASSETS={
 'barrier':'/CRD_VolumetricRegion/SetupAssets/PID_Device_Barrier.PID_Device_Barrier',
 'mutator':'/CRD_VolumetricRegion/SetupAssets/PID_Device_Mutator.PID_Device_Mutator',
 'teleporter':bm.TELEPORTER,'button':bm.BUTTON,
 'granter':DEV+'PID_Device_ItemGranter.PID_Device_ItemGranter',
 'spawner':bm.ITEM_SPAWNER,'vendor':DEV+'PID_Device_VendingMachine.PID_Device_VendingMachine',
 'vfx':'/CRD_VFX_Spawner/SetupAssets/PID_Device_VFX_Spawner_V2.PID_Device_VFX_Spawner_V2',
 'audio':'/CRD_AudioPlayer/SetupAssets/PID_CP_Devices_CRD_AudioPlayer.PID_CP_Devices_CRD_AudioPlayer'}

# Ground sockets outside safe strips, away from centre, authored cover and stairs.
# Collision and reachability MUST pass human/native acceptance before the gate changes.
SOCKETS=[dict(x=73728,y=-58112,z=0),dict(x=74240,y=-53504,z=0),
         dict(x=77824,y=-58112,z=0),dict(x=77312,y=-53000,z=0)]

def apply(report):
    b=bm.Builder();m=b.m
    if m.tool(bm.SCENE,'get_current_level')!=bm.MODULE+'/KeystrokeTrainer':
        raise RuntimeError('Wrong island')
    actors=m.tool(bm.SCENE,'find_actors',name=PREFIX,collision_channels=[])
    by={a['label']:a for a in actors}
    if len(by)!=len(actors): raise RuntimeError('Duplicate Rift labels')
    records=[]
    def put(name,kind,x,y,z=0,settings=None):
        label=PREFIX+name
        path=by[label]['actorPath'] if label in by else b.device(ASSETS[kind],label,x,y,z)
        schema=m.tool(bm.OBJ,'list_properties',instance={'refPath':path})
        schema=json.loads(schema) if isinstance(schema,str) else schema
        values=dict(settings or {})
        if 'enabledOnPhase' in schema: values['enabledOnPhase']='None'
        missing=set(values)-set(schema)
        if missing: raise RuntimeError(f'{label} unsupported settings: {missing}')
        if values: b.props(path,values)
        components=m.tool(bm.ACTOR,'get_components',actor={'refPath':path})
        tag=next((c['refPath'] for c in components if c['refPath'].endswith('.KT_Tags')),None)
        if not tag: b.tag(path,'kt_rift_port_tag')
        m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':path},xform=bm.xform(x,y,z))
        m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
        records.append(dict(label=label,refPath=path,settings=values))
        print('saved',label,flush=True)
        return {'refPath':path}
    setup=put('SetupWall','barrier',75776,-55808,0,
              dict(barrierWidth=16,barrierDepth=.05,barrierHeight=4,blockWeaponFire=True,zoneShape='Box'))
    zones=[];walls=[];jails=[];sky=[];returns=[];vendors=[];effects=[]
    for side,x in [('Red',72192),('Blue',79360)]:
        room_x=70912 if side=='Red' else 80640
        zones.append(put(side+'Safe','mutator',room_x,-55808,0,
                    dict(zoneWidth=3,zoneDepth=4,zoneHeight=1,bAllowBuilding=False,bAllowEditing=False,bAllowWeaponFire=False)))
        walls.append(put(side+'SafeWall','barrier',room_x,-55808,0,
                    dict(barrierWidth=3,barrierDepth=4,barrierHeight=1,blockWeaponFire=True,zoneShape='Box')))
        jails.append(put(side+'Jail','teleporter',x,-58880,80))
        sky.append(put(side+'SkyReturn','teleporter',x,-55808,1800))
        rx=73984 if side=='Red' else 77568
        returns.append(put(side+'ReturnRift','teleporter',rx,-55808,0))
        vendor=put(side+'Vendor','vendor',70374.4 if side=='Red' else 81177.6,-56320,128)
        b.face(vendor['refPath'],0 if side=='Red' else 180)
        m.tool(bm.SCENE,'save_actor',actor=vendor)
        vendors.append(vendor)
        effects.append(put(side+'CaptureEffect','vfx',rx,-55808,0))
    flags=[];rifts=[]
    for i,s in enumerate(SOCKETS):
        flags.append(put(f'FlagChoice{i}','button',s['x'],s['y']-100,60))
        rifts.append(put(f'ReturnChoice{i}','button',s['x'],s['y']+100,60))
    gold=put('CaptureGold','granter',75776,-55808,-600)
    mats=put('SetupMaterials','granter',75776,-55808,-800)
    registration=[]
    for ref,items,action,grant in [
        # Creative resource definitions, not the disallowed Athena BR variants.
        (gold,[('/Game/Items/ResourcePickups/GoldItemData.GoldItemData',1)],'Keep All','Current Item'),
        (mats,[('/Game/Items/ResourcePickups/WoodItemData.WoodItemData',300),
               ('/Game/Items/ResourcePickups/StoneItemData.StoneItemData',200),
               ('/Game/Items/ResourcePickups/MetalItemData.MetalItemData',100)],'Clear Resources','All Items')]:
        b.props(ref['refPath'],{'onGrantAction':action,'grant':grant,'grantCondition':'Always',
                               'receivingPlayers':{'teamType':'TriggeringPlayer','teamIndex':1}})
        raw=m.tool(bm.OBJ,'get_properties',instance=ref,properties=['pickupItemList'])
        raw=json.loads(raw) if isinstance(raw,str) else raw
        itemlist=raw['pickupItemList']
        m.tool(bm.OBJ,'list_properties',instance=itemlist)
        for asset,count in items:
            if not m.tool('editor_toolset.toolsets.asset.AssetTools','exists',path=asset):
                raise RuntimeError('Missing registered item: '+asset)
        data=[{'itemDefinition':{'refPath':asset},'itemQuantity':count} for asset,count in items]
        m.tool(bm.OBJ,'reset_properties',instance=itemlist,properties=['itemListData'])
        # Native property change handlers normalize each edit; append one entry
        # at a time, retaining the actual normalized data rather than assuming it.
        for entry in data:
            current=m.tool(bm.OBJ,'get_properties',instance=itemlist,properties=['itemListData'])
            current=json.loads(current) if isinstance(current,str) else current
            b.props(itemlist['refPath'],{'itemListData':current['itemListData']+[entry]})
        read=m.tool(bm.OBJ,'get_properties',instance=itemlist,properties=['itemListData'])
        read=json.loads(read) if isinstance(read,str) else read
        actual=[(e.get('itemDefinition',{}).get('refPath'),e.get('itemQuantity')) for e in read['itemListData']]
        if actual!=items: raise RuntimeError('Item registration readback differs')
        m.tool(bm.SCENE,'save_actor',actor=ref)
        registration.append({'granter':ref,'items':data,'onGrantAction':action})
    shoes=put('OptionalShoes','spawner',75776,-55808,-1000)
    alarm=put('StartAlarm','audio',75776,-55808,-1200)
    voice=put('StartVoice','audio',75776,-55808,-1400)
    capture=put('CaptureAudio','audio',75776,-55808,-1600)
    controller=m.tool(bm.SCENE,'find_actors',name='KT24_Team_Match',collision_channels=[])[0]['actorPath']
    # Classic actor refs are not Verse wrapper refs. Runtime tag discovery binds
    # devices deterministically; do not manufacture nonexistent wrapper paths.
    read=m.tool(bm.DEVICE,'GetDeviceProperties',device={'refPath':controller},propertyNames=['RiftSetupVerified'])
    reboot=[]
    for a in m.tool(bm.SCENE,'find_actors',name='KT24_Team_Reboot',collision_channels=[]):
        if not a['label'].endswith('Use'): continue
        m.tool(bm.OBJ,'list_properties',instance={'refPath':a['actorPath']})
        b.props(a['actorPath'],{'interactTime':5.0})
        m.tool(bm.SCENE,'save_actor',actor={'refPath':a['actorPath']})
        reboot.append({'label':a['label'],'settings':m.tool(bm.OBJ,'get_properties',instance={'refPath':a['actorPath']},properties=['interactTime','interactTimeOverride'])})
    Path(report).write_text(json.dumps({'actors':records,'controller_readback':read,'reboot_hold_readback':reboot,'registered_items':registration,
                 'acceptance':'disabled; creative resources registered; upload/gameplay validation, audio, socket collision and multiplayer tests required'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--report',default='design/rift-ports-readback-2026-10-12.json');a=p.parse_args()
    if a.apply: apply(a.report)
    else: print(json.dumps({'prefix':PREFIX,'sockets':SOCKETS,'verified_flags':'unchanged/false'},indent=2))
