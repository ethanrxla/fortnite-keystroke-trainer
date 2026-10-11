"""Add eight glowing selector pads, registered player references and three native points.

Does not delete actors, alter other districts or enable unfinished match gates.
"""
import argparse
import json
import build_map as bm

PREFIX='KT24_Team_'
REFERENCE='/CRD_PlayerRef/SetupAssets/PID_Device_PlayerReference.PID_Device_PlayerReference'
SELECTOR=bm.DEV+'PID_Device_ClassSelector.PID_Device_ClassSelector'
CAPTURE=bm.DEV+'PID_CP_Devices_CaptureArea_V2.PID_CP_Devices_CaptureArea_V2'
VAN='/CRD_RebootVan/SetupAssets/PID_CP_Devices_RebootVan.PID_CP_Devices_RebootVan'
MUTATOR='/CRD_VolumetricRegion/SetupAssets/PID_Device_Mutator.PID_Device_Mutator'

def pad_positions():
    return [((144.5+2*(i%4))*512,(-121.5+2*(i//4))*512,0) for i in range(8)]

def apply():
    b=bm.Builder()
    if b.m.tool(bm.SCENE,'get_current_level')!=bm.MODULE+'/KeystrokeTrainer':
        raise RuntimeError('Wrong open island')
    actors=b.m.tool(bm.SCENE,'find_actors',name='',collision_channels=[])
    existing={a['label']:a['actorPath'] for a in actors}
    # Reuse schema-probe actors; do not leave an extra van or active class switch.
    if probe:=existing.get(PREFIX+'RebootMid'):
        b.m.tool(bm.ACTOR,'set_label',actor={'refPath':probe},label=PREFIX+'RebootCentre')
        existing[PREFIX+'RebootCentre']=probe
    if probe:=existing.get(PREFIX+'JoinPadVisualProbe'):
        b.m.tool(bm.OBJ,'list_properties',instance={'refPath':probe})
        b.props(probe,{'enabledDuringPhase':'None','classToSwitchTo_Override':False,'teamToSwitchTo_Override':False})
        b.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':probe},xform=bm.xform(74752,-61184,-50000))
        b.m.tool(bm.SCENE,'save_actor',actor={'refPath':probe})
    floor=dict(label=PREFIX+'QueueFloor',bounds=(143*512,153*512,-123*512,-117.08*512),top=0,thick=100,mat='Hub')
    ref_positions=[b.m.tool(bm.ACTOR,'get_actor_transform',actor={'refPath':path})['location']
                   for label,path in existing.items() if label.startswith(PREFIX+'Reference')]
    # Refuse foreign collision within the new apron, excluding the global sky.
    for a in actors:
        q=a.get('bounds',{});lo=q.get('min',{});hi=q.get('max',{})
        cls=a.get('class',{}).get('refPath','')
        diagnostic=cls=='/Script/SmartObjectsModule.SmartObjectSubsystemRenderingActor'
        owned_preview=cls=='/Game/Creative/Devices/Common/ChildActors/Creative_Mannequin.Creative_Mannequin_C' and any(
            abs((lo.get('x',1e9)+hi.get('x',1e9))/2-p['x'])<100 and abs((lo.get('y',1e9)+hi.get('y',1e9))/2-p['y'])<100 for p in ref_positions)
        if not a['label'].startswith(PREFIX) and 'DaySequence' not in cls and not diagnostic and not owned_preview:
            if lo.get('x',1e9)<floor['bounds'][1] and hi.get('x',-1e9)>floor['bounds'][0] and lo.get('y',1e9)<floor['bounds'][3] and hi.get('y',-1e9)>floor['bounds'][2] and lo.get('z',1e9)<2304 and hi.get('z',-1e9)>0:
                raise RuntimeError('Queue footprint occupied by '+a['label'])
    if floor['label'] not in existing:
        path=b.slab(floor);b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
    def place(name,asset,pos,props=None,tag=None):
        label=PREFIX+name
        path=existing.get(label) or b.device(asset,label,*pos)
        b.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':path},xform=bm.xform(*pos))
        b.m.tool(bm.OBJ,'list_properties',instance={'refPath':path})
        if props:
            b.props(path,props)
            actual=b.m.tool(bm.OBJ,'get_properties',instance={'refPath':path},properties=list(props))
            actual=json.loads(actual) if isinstance(actual,str) else actual
            # float values serialize through native float32; compare those loosely.
            for k,v in props.items():
                if isinstance(v,float) and abs(actual[k]-v)<1e-4:continue
                if actual[k]!=v:raise RuntimeError(f'{label}: {k} did not retain value')
        if tag:
            cs=b.m.tool(bm.ACTOR,'get_components',actor={'refPath':path})
            if not any(c['refPath'].endswith('.KT_Tags') for c in cs):b.tag(path,tag)
        b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
        return path
    for i,pos in enumerate(pad_positions()):
        place('JoinPad'+str(i),SELECTOR,pos,{'teamToSwitchTo_Override':False,'classToSwitchTo_Override':False,
              'bRespawnPlayerOnSwitch':False,'restoreHealthAndShieldsOnSwitch':False,'clearItemsOnSwitch':False,
              'clearItemOnSwitchRule':'NeverClear','visibleDuringGame':True,'volumeVisibleInGame':True,
              'sizeOfVolume':.5,'enabledDuringPhase':'Always','accentColorType':'Direct Color',
              'accentColor':({'r':1,'g':.125,'b':.125,'a':1} if i<4 else {'r':.125,'g':.25,'b':1,'a':1})})
        place('Reference'+str(i),REFERENCE,pos,{'bShowBase':False,'bShowHologram':True,'visible In Game':True},'kt_team_queue_pad_tag')
    for name,x in [('PointRed',72448),('PointMid',75776),('PointBlue',79104)]:
        place(name,CAPTURE,(x,-55808,0),{'enableDuringPhase':'None','periodicScoreValue':0,'scoreOnTakingControl':0,
              'itemDeliveryScore':0,'captureAllowedOnGameStart':False,'consumeItemOnScoring':False,'consumeItemWhenDropped':False},'kt_team_point_tag')
    for name,x in [('CTFRed',72448),('CTFBlue',79104)]:
        place(name,CAPTURE,(x,-55808,0),{'enableDuringPhase':'None','periodicScoreValue':0,'scoreOnTakingControl':0,
              'itemDeliveryScore':0,'captureAllowedOnGameStart':False,'consumeItemOnScoring':True,'consumeItemWhenDropped':False},'kt_team_ctf_base_tag')
    place('NoBuild',MUTATOR,(75776,-55808,0),{'zoneWidth':16.0,'zoneDepth':16.0,'zoneHeight':12.0,
          'bAllowBuilding':False,'bAllowWeaponFire':True,'bAffectsPlayers':True,'bAffectsGuards':False,
          'zoneVisibleDuringGame':False,'enabledOnPhase':'None'},'kt_team_nobuild_tag')
    # Three neutral lane locations, not one van assigned to either base.
    for name,pos in [('RebootNorth',(75776,-52736,0)),('RebootCentre',(75776,-56832,0)),('RebootSouth',(75776,-58880,0))]:
        place(name,VAN,pos,{'enabledOnGameStart':False,'recharge Time':30.0,'can Purchase Reboot Card':False})
        place(name+'Use',bm.BUTTON,(pos[0],pos[1]+600,100),{'interaction Text':'REBOOT TEAM (4s hold)',
              'delay':4.0,'resetDelay':1.0,'enabledAtGameStart':False},'kt_team_reboot_button_tag')
    access=existing.get(PREFIX+'Access')
    if access:
        cs=b.m.tool(bm.ACTOR,'get_components',actor={'refPath':access})
        if not any(c['refPath'].endswith('.KT_AccessQueueTag') for c in cs):
            c=b.m.tool(bm.ACTOR,'add_component',owner={'refPath':access},component_type={'refPath':'/Script/VerseTags.VerseTagMarkupComponent'},name='KT_AccessQueueTag')
            b.props(c['refPath'],{'internalTags':{'internalTags':[{'internalTag':{'refPath':bm.TAG_CLASS.format('kt_team_access_tag')}}]}})
            b.m.tool(bm.SCENE,'save_actor',actor={'refPath':access})
    place('Queue',bm.MODULE+'/_Verse.KeystrokeTrainer-kt_team_queue_device',(75776,-61184,-700))
    # Move arrivals onto the queue apron; still use an explicit endpoint.
    if path:=existing.get(PREFIX+'Arrival'):
        b.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':path},xform=bm.xform(73984,-61696,50))
        b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
    if path:=existing.get(PREFIX+'Leave'):
        b.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':path},xform=bm.xform(73728,-61696,100))
        b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
    print('Saved 8 glowing pads/references, 3 capture areas, no-build volume, 3 staged reboot vans and queue controller.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
    print(json.dumps({'pads':pad_positions(),'points':'red base, middle, blue base','vans':'neutral north, middle, south'}))
    if args.apply:apply()
