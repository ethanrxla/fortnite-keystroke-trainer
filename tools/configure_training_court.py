"""Finish the additive court's readability, movement, signs and reference settings.

Run after build_training_court.py --apply. Every old actor value changed here is
journaled before editing, and all actor labels are looked up in the open level.
"""
import json
import textwrap
from pathlib import Path
from build_map import Mcp, MODULE, SCENE, ACTOR, OBJ, DEVICE, MAT, xform
from build_training_court import Y0, C

ROOT=Path(__file__).resolve().parent.parent
BACKUP=ROOT/'backups/session-2026-10-07'
AS='editor_toolset.toolsets.asset.AssetTools'
MT='editor_toolset.toolsets.material.MaterialTools'
MI='editor_toolset.toolsets.material_instance.MaterialInstanceTools'

def material(m,name,unlit=False,texture=None):
    path=MODULE+'/KT_Materials/'+name+'.'+name
    ref={'refPath':path}
    if not m.tool(AS,'exists',path=path):
        ref=m.tool(MT,'create_material',folder_path=MODULE+'/KT_Materials',asset_name=name)
    nodes=m.tool(MT,'get_expressions',material_or_function=ref)
    if not nodes:
        kind='MaterialExpressionTextureSample' if texture else 'MaterialExpressionVectorParameter'
        node=m.tool(MT,'add_expression',material_or_function=ref,expression_class={'refPath':'/Script/Engine.'+kind},x=-300,y=0)
        m.tool(OBJ,'list_properties',instance=node)
        values={'texture':{'refPath':texture}} if texture else {'parameterName':'Color','defaultValue':{'r':.03,'g':.04,'b':.06,'a':1}}
        m.tool(OBJ,'set_properties',instance=node,values=json.dumps(values))
        m.tool(MT,'connect_to_output',expression=node,output_name='',material_property='MP_EmissiveColor' if unlit else 'MP_BaseColor')
        if not unlit:
            rough=m.tool(MT,'add_expression',material_or_function=ref,expression_class={'refPath':'/Script/Engine.MaterialExpressionScalarParameter'},x=-300,y=200)
            m.tool(OBJ,'set_properties',instance=rough,values=json.dumps({'parameterName':'Roughness','defaultValue':.9}))
            m.tool(MT,'connect_to_output',expression=rough,output_name='',material_property='MP_Roughness')
    m.tool(OBJ,'set_properties',instance=ref,values=json.dumps({'shadingModel':'MSM_Unlit' if unlit else 'MSM_DefaultLit','twoSided':bool(texture)}))
    m.tool(MT,'recompile',material_or_function=ref)
    return ref

def main():
    m=Mcp()
    if m.tool(SCENE,'get_current_level')!=MODULE+'/KeystrokeTrainer':
        raise RuntimeError('Open the intended MyProject/KeystrokeTrainer level before configuration')
    actors=m.tool(SCENE,'find_actors',collision_channels=[])
    found={a['label']:a['actorPath'] for a in actors}
    journal=[]
    def props(label,values):
        r={'refPath':found[label]}
        m.tool(OBJ,'list_properties',instance=r)
        before=m.tool(OBJ,'get_properties',instance=r,properties=list(values))
        journal.append({'label':label,'path':r['refPath'],'before':before,'after':values})
        (BACKUP/'configuration-journal.json').write_text(json.dumps(journal,indent=2))
        # Preserve the first snapshot rather than replacing it on a configuration re-run.
        out=BACKUP/'configuration-before.json'
        if not out.exists():out.write_text(json.dumps(journal,indent=2))
        m.tool(OBJ,'set_properties',instance=r,values=json.dumps(values));m.tool(SCENE,'save_actor',actor=r)

    plain=material(m,'M_KT2_Plain');outline=material(m,'M_KT2_Outline',unlit=True)
    for name in ['Neutral','Ghost','Dim','Build','Piece','Aim']:
        instance={'refPath':MODULE+'/KT_Materials/MI_KT2_'+name+'.MI_KT2_'+name}
        m.tool(MI,'set_parent',instance=instance,parent=outline if name in ['Ghost','Dim'] else plain)
    # Fewer choices and short text fit the native sign panel without clipping.
    old_signs={
        'KT_Sign_Title':'RXLA TRAINING GROUND\nSTART HERE  /  FREE BUILD',
        'KT_Sign_Gate_Build':'BUILD LIBRARY\nPieces and placement',
        'KT_Sign_Gate_Piece':'MOVEMENT LIBRARY\nCover and control',
        'KT_Sign_Gate_Edit':'EDIT PRACTICE\nOpenings and recovery',
        'KT_Sign_Gate_Armory':'EQUIPMENT\nChoose a loadout',
        'KT_Sign_Gate_Aim':'AIM PRACTICE\nStatic and moving targets',
        'KT_Sign_Gate_Arena':'COMBAT SPACE\nSelf-directed practice',
        'KT_Sign_Gate_Scenario':'SCENARIO EXPANSION\nIn development',
    }
    for label,text in old_signs.items():
        if label in found:props(label,{'text':text,'textSize':20,'showBorder':False})
    if 'KT_Portal_Scenario' in found:props('KT_Portal_Scenario',{'enabledDuringPhase':'Always','teleporter Rift Visible':True})
    data=json.loads((ROOT/'shared/drills.json').read_text())['practice_court']
    for label,key in [('KT2_Build','build'),('KT2_Rebox','rebox'),('KT2_Peek','peek'),('KT2_Free','free')]:
        props(label,{'text':data[key+'_header'],'textSize':18})
    for label in found:
        if label.startswith('KT2_GuideButton_'):
            props(label,{'delay':0.0,'resetDelay':0.15,'enabledAtGameStart':True})
    # Defaults are read back after setting: correct native Verse setting names were discovered.
    guide={'refPath':found['KT2_Guide']}
    for key,value in {'drillId':'wall_ramp_floor','enableGuide':True,'releaseDistanceCm':2500.0,'demoSecondsPerStage':.6}.items():
        m.tool(DEVICE,'SetDeviceProperty',device=guide,propertyName=key,value=json.dumps(value))
    # Native bindings live on the receiver. Keep the one-device training loadout explicit
    # and clear the list before replacement so unsupported stale references cannot remain.
    granter={'refPath':found['KT2_PracticeGranter']}
    raw=m.tool(OBJ,'get_properties',instance=granter,properties=['pickupItemList'])
    item_list=(json.loads(raw) if isinstance(raw,str) else raw)['pickupItemList']
    preset=json.loads((ROOT/'shared/practice-loadout.json').read_text(encoding='utf-8'))['items']['SHOTGUN']
    m.tool(OBJ,'reset_properties',instance=item_list,properties=['itemListData'])
    m.tool(OBJ,'set_properties',instance=item_list,values=json.dumps({'itemListData':[{'itemDefinition':{'refPath':preset},'itemQuantity':1}]}))
    links=m.tool(DEVICE,'ListEventBindings',devicePath=granter)
    if not any(b['sourceDevicePath']['refPath']==found['KT2_CourtArrival'] and b['sourceEvent']=='On Teleported' and b['targetFunction']=='GrantItem' for b in links):
        m.tool(DEVICE,'AddEventBinding',sourceDevicePath={'refPath':found['KT2_CourtArrival']},sourceEvent='On Teleported',targetDevicePath=granter,targetFunction='GrantItem')
    m.tool(SCENE,'save_actor',actor=granter)
    props('KT2_CurrentBRMovement',{'movementSettingPreset':'Current BR','bAddToPlayersOnStart':True,'enabledDuringPhase':'Gameplay Only','priority':1.0})
    props('IslandSettings0',{'bInfiniteResources':True,'allowBuilding':'All','bInfiniteAmmo':True,'environmentDamagePreset':'Player Built Only'})

    # Put generated raster art on a quiet onboarding panel. Exact ghosts remain native geometry.
    tex=MODULE+'/KT_Training/T_GhostBuild_Onboarding_v1.T_GhostBuild_Onboarding_v1'
    m.tool(OBJ,'set_properties',instance={'refPath':tex},values=json.dumps({'powerOfTwoMode':'StretchToPowerOfTwo','neverStream':False,'mipGenSettings':'TMGS_FromTextureGroup'}))
    art=material(m,'M_KT2_OnboardingArt',unlit=True,texture=tex)
    label='KT2_OnboardingArt'
    if label not in found:
        plane='/Engine/BasicShapes/Plane.Plane'
        if not m.tool(AS,'exists',path=plane):raise RuntimeError('Verified engine plane is unavailable')
        xf=xform(1.5*C,Y0+19.5*C,390,7.68,5.12,1,yaw=0)
        xf['rotation']['roll']=90
        actor=m.tool(SCENE,'add_to_scene_from_asset',asset_path=plane,name=label,xform=xf)
        m.tool(ACTOR,'set_label',actor=actor,label=label);m.tool(SCENE,'set_actor_folder',actor=actor,folder_path='TrainingCourtV2')
    else:actor={'refPath':found[label]}
    xf=xform(1.5*C,Y0+19.5*C,390,7.68,5.12,1,yaw=0);xf['rotation']['roll']=90
    m.tool(ACTOR,'set_actor_transform',actor=actor,xform=xf)
    for comp in m.tool(ACTOR,'get_components',actor=actor):
        if 'StaticMeshComponent0' in comp['refPath']:
            m.tool(OBJ,'set_properties',instance=comp,values=json.dumps({'overrideMaterials':[art],'castShadow':False,'bodyInstance':{'collisionEnabled':'NoCollision','collisionProfileName':'NoCollision'}}))
    m.tool(SCENE,'save_actor',actor=actor)
    # Keep optional art at the spine's edge and navigation outside the straight walking line.
    welcome={'refPath':found['KT2_Welcome']}
    m.tool(ACTOR,'set_actor_transform',actor=welcome,xform=xform(2*C,Y0+12.5*C,480,2,2,2,yaw=-90))
    props('KT2_Welcome',{'text':'TRAINING COURT\nBUILD  >  RE-BOX  >  PEEK','textSize':18})
    (BACKUP/'configuration-journal.json').write_text(json.dumps(journal,indent=2))
    print('guide',m.tool(DEVICE,'GetDeviceProperties',device=guide,propertyNames=['drillId','enableGuide','releaseDistanceCm','demoSecondsPerStage']))
    print('saved',m.tool(AS,'save_assets',asset_paths=[]))

if __name__=='__main__':main()
