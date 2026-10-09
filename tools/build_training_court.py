"""Add the v2 practice court without rebuilding or deleting the existing map.

Dry-run is default. --apply upserts only KT2_* labels. Existing KT_* content is
untouched except for the separately documented hub sign readability patch.
All layout distances are centimetres, +X forward, +Y right. Source mesh is a
100 cm box with bottom-centre pivot, verified in the current editor.
"""
import argparse
import json
import math
import textwrap
from pathlib import Path
from build_map import Mcp, MODULE, BOX, SCENE, ACTOR, OBJ, DEVICE, BILLBOARD, BUTTON, TELEPORTER, DUMMY, EXPLOSIVE, xform

ROOT = Path(__file__).resolve().parent.parent
C = 512.0
H = 384.0
Y0 = -35840.0
FOLDER = 'TrainingCourtV2'
ASSET = 'editor_toolset.toolsets.asset.AssetTools'
MI = 'editor_toolset.toolsets.material_instance.MaterialInstanceTools'
PROGRAM = 'editor_toolset.toolsets.programmatic.ProgrammaticToolset'

def plan():
    items = []
    teaching=json.loads((ROOT/'shared/drills.json').read_text(encoding='utf-8'))['practice_court']
    def block(label, x, y, z, sx, sy, sz, mat='Neutral', ghost=False, pitch=0, tag=None):
        xf = xform(x, y, z, sx/100, sy/100, sz/100)
        xf['rotation']['pitch'] = pitch
        items.append(dict(label='KT2_'+label, kind='ghost' if ghost else 'mesh', xf=xf, mat=mat, tag=tag))
    def slab(label, i0, i1, j0, j1, mat='Neutral'):
        block(label,(i0+i1)*C/2,Y0+(j0+j1)*C/2,-48,(i1-i0)*C,(j1-j0)*C,48,mat)
    def sign(label, i, j, text, zone='Neutral', z=320, yaw=-90, scale=2):
        items.append(dict(label='KT2_'+label,kind='device',asset=BILLBOARD,
            xf=xform(i*C,Y0+j*C,z,scale,scale,scale,yaw=yaw),
            props=dict(text=text,textSize=18,showBorder=False,textJustification='Center',
                textColor=dict(r=1,g=1,b=1,a=1),backgroundColor=dict(r=.008,g=.012,b=.02,a=1))))
    def edge(label,a,b,stage=None,mat='Ghost'):
        dx,dy,dz=[b[n]-a[n] for n in range(3)]
        length=math.sqrt(dx*dx+dy*dy+dz*dz)
        yaw=math.degrees(math.atan2(dy,dx));pitch=math.degrees(math.atan2(dz,math.hypot(dx,dy)))
        # Six centimetre beam; bottom-pivot offset is negligible at a reference-only display.
        block(label,(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2-3,length,6,6,mat,True,pitch,
              'kt_ghost_stage'+str(stage)+'_tag' if stage is not None else None)
        items[-1]['xf']['rotation']['yaw']=yaw
    def frame(label,points,stage=None):
        for n in range(len(points)):
            edge(label+'_'+str(n),points[n],points[(n+1)%len(points)],stage)
    def wall(label,x,y,z,stage=None):
        frame(label,[(x,y,z),(x,y+C,z),(x,y+C,z+H),(x,y,z+H)],stage)
    def floor(label,x,y,z,stage=None):
        frame(label,[(x,y,z),(x+C,y,z),(x+C,y+C,z),(x,y+C,z)],stage)

    # Exact 24 x 20 tile campus. A three-tile arrival strip is a clear shared spine.
    slab('Arrival',0,3,0,20)
    slab('Practice',3,12,0,20)
    slab('Crosswalk',12,14,0,20)
    slab('FreeBuild',14,24,0,10)
    slab('Transfer',14,24,10,20)
    # Muted bay strips carry color only at edges, leaving silhouettes easy to read.
    for k,mat in enumerate(['Build','Piece','Aim']):
        j=1+k*6
        block('BayStripe_'+str(k),7.5*C,Y0+j*C,1,9*C,12,2,mat)
        block('BayEnd_'+str(k),11.98*C,Y0+(j+2.5)*C,1,12,5*C,2,mat)
    # Low outer perimeter: never roofs over build space. Eight levels of clear air above free build.
    for label,x,y,sx,sy in [('West',12*C,Y0-12,24*C,24),('East',12*C,Y0+20*C+12,24*C,24),('Back',24*C+12,Y0+10*C,24,20*C)]:
        block('Perimeter_'+label,x,y,0,sx,sy,96)
    # A full-size isolated example in bay 1. Player replication starts two tiles to its right.
    gx,gy=6*C,Y0+1*C
    wall('GhostWall',gx+C,gy,0,0)
    frame('GhostRamp',[(gx,gy,0),(gx+C,gy,H),(gx+C,gy+C,H),(gx,gy+C,0)],1)
    edge('GhostRampMid',(gx,gy+C/2,0),(gx+C,gy+C/2,H),1)
    floor('GhostFloor',gx+C,gy,H,2)
    # Blank copy tiles remain buildable: the reference lives in its own display cell.
    for k in range(3):
        floor('CopyOutline_'+str(k),6*C,Y0+(3+k)*C,3)
    # Re-box reference: two adjacent 1x1 footprints, explicitly marking a safe destination.
    floor('ReboxStart',6*C,Y0+8*C,3)
    floor('ReboxExit',6*C,Y0+9*C,3)
    wall('ReboxThreat',7*C,Y0+8*C,0)
    wall('ReboxExitThreat',7*C,Y0+9*C,0)
    # Real cover for crosshair/peek drill, shoulder-side target lines at 1 and 2 tile distances.
    block('PeekCover',6*C,Y0+14*C,0,24,C,H,'Neutral')
    for k,dist in enumerate([1,2]):
        items.append(dict(label='KT2_PeekTarget_'+str(k),kind='device',asset=DUMMY,
            xf=xform((6+dist)*C,Y0+15.15*C,0,yaw=180),props={'infiniteHealth':True}))
    # Tall free-build volume is intentionally empty; tile boundaries, entry and exit are unambiguous.
    for j in range(0,11):
        block('FreeGridY_'+str(j),19*C,Y0+j*C,1,10*C,3,2,'Dim')
    for i in range(14,25):
        block('FreeGridX_'+str(i),i*C,Y0+5*C,1,3,10*C,2,'Dim')
    # Realistic transfer: four offset, one-tile covers leave two-tile movement routes.
    for k,(i,j) in enumerate([(16,13),(19,15),(22,13),(16,17)]):
        block('TransferCover_'+str(k),i*C,Y0+j*C,0,24,C,H,'Neutral')
    sign('Build',10,3,teaching['build_header'])
    sign('Rebox',10,9,teaching['rebox_header'])
    sign('Peek',10,15,teaching['peek_header'])
    sign('Free',23,5,teaching['free_header'],z=650,scale=3)
    sign('SignTransfer',23,15,'TRANSFER\nMove between cover',z=650,scale=3)
    sign('Welcome',2,10,'TRAINING COURT\n01 Build  >  02 Re-box  >  03 Peek',z=340,scale=2.5)
    sign('Return',1,1,'HUB',z=220,scale=1.2)
    for kind,right in [('build',3.5),('rebox',9.5),('peek',15.5)]:
        sign('Instruction_'+kind,3.6,right,'\n'.join(textwrap.wrap(teaching[kind+'_instruction'],width=40)),z=355,scale=2.1)
        items[-1]['props']['textSize']=8
    sign('ResetBuffer',14,11.5,'KEEP CLEAR\nFree-build reset buffer',z=230,scale=1.2)
    for n,mode in enumerate(['watch','copy','recall','next','slower','faster','stop']):
        items.append(dict(label='KT2_GuideButton_'+mode,kind='device',asset=BUTTON,
            xf=xform(4*C,Y0+(.8+n*.7)*C,90,yaw=180),props={},tag='kt_ghost_'+mode+'_tag'))
        sign('ButtonLabel_'+mode,4.3,.8+n*.7,mode.upper(),z=155,scale=.55)
    items.append(dict(label='KT2_Guide',kind='device',asset=MODULE+'/_Verse.KeystrokeTrainer-keystroke_ghost_guide_device',xf=xform(6*C,Y0+2*C,-30),props={},tag='kt_ghost_guide_tag'))
    # Hub entry and return pairs use reserved v2 groups; momentum is cleared for predictable arrivals.
    for label,x,y,group,target,yaw in [('QuickStart',768,-59648,'Group_M','Group_N',0),('CourtArrival',C,Y0+10*C,'Group_N','Group_None',0),('CourtReturn',C,Y0+C,'Group_O','Group_P',180),('HubArrival',-256,-59648,'Group_P','Group_None',0),('FreeStart',256,-58624,'Group_Q','Group_R',0),('FreeArrival',15*C,Y0+5*C,'Group_R','Group_None',0)]:
        items.append(dict(label='KT2_'+label,kind='device',asset=TELEPORTER,xf=xform(x,y,15,yaw=yaw),props={'knob_TeleporterGroup':group,'knob_TargetTeleporterGroup':target,'change Teleporter Target':'On Entry','maintain Relative Position':False,'conserve Momentum':False,'play Visual Effects':False,'play Sound Effects':False,'teleporter Rift Visible':target!='Group_None'}))
    # Hub labels are world-coordinate by design, in front of spawn rather than at wing ends.
    for label,x,y,txt in [('QuickLabel',1280,-59648,'START HERE\nGuided practice'),('FreeLabel',768,-58624,'FREE BUILD\nYour pace')]:
        items.append(dict(label='KT2_'+label,kind='device',asset=BILLBOARD,xf=xform(x,y,280,1.6,1.6,1.6,yaw=-90),props=dict(text=txt,textSize=20,showBorder=False,textColor=dict(r=1,g=1,b=1,a=1),backgroundColor=dict(r=.008,g=.012,b=.02,a=1))))
    # Each reset is explicitly shared and labelled. Neighboring bay centroids remain outside
    # the 2.9-tile blast envelopes. Free build's 4.75-tile spheres require a 3-tile buffer
    # at the front of Transfer (r=10..13); no active cover/target lives in that strip.
    for kind,right in [('build',3.5),('rebox',9.5),('peek',15.5)]:
        for n,forward in enumerate([4.5,7.5,10.5]):
            items.append(dict(label='KT2_ResetRig_'+kind+'_'+str(n),kind='device',asset=EXPLOSIVE,
                xf=xform(forward*C,Y0+right*C,1.5*H),tag='kt_court_clear_'+kind+'_tag',
                props={'blast Radius':2.9,'player Damage':0,'structure Damage':10000,'knockback':'None','can be Damaged':False,'damage Indestructible Buildings':False,'visible During Game':False,'play Audio / VFX':False,'time Until Reset Allowed':.1,'has Timed Detonation From Game Start':False}))
        items.append(dict(label='KT2_ResetButton_'+kind,kind='device',asset=BUTTON,
            xf=xform(3*C,Y0+right*C,90,yaw=180),tag='kt_court_reset_'+kind+'_tag',props={'interaction Text':'Reset this bay (shared)','delay':0.0,'resetDelay':.5}))
        sign('ResetLabel_'+kind,3.3,right,'RESET BAY\nShared area',z=205,scale=.8)
    for n,(f,r) in enumerate([(16.5,2.5),(16.5,7.5),(21.5,2.5),(21.5,7.5)]):
        items.append(dict(label='KT2_ResetRig_free_'+str(n),kind='device',asset=EXPLOSIVE,
            xf=xform(f*C,Y0+r*C,4*H),tag='kt_court_clear_free_tag',
            props={'blast Radius':4.75,'player Damage':0,'structure Damage':10000,'knockback':'None','can be Damaged':False,'damage Indestructible Buildings':False,'visible During Game':False,'play Audio / VFX':False,'time Until Reset Allowed':.1,'has Timed Detonation From Game Start':False}))
    items.append(dict(label='KT2_ResetButton_free',kind='device',asset=BUTTON,
        xf=xform(14.5*C,Y0+5*C,90,yaw=180),tag='kt_court_reset_free_tag',props={'interaction Text':'Clear free-build space (shared)','delay':0.0,'resetDelay':.5}))
    sign('ResetLabel_free',14.8,5,'RESET BUILDS\nShared free-build area',z=220,scale=1.0)
    items.append(dict(label='KT2_CourtControls',kind='device',asset=MODULE+'/_Verse.KeystrokeTrainer-keystroke_court_controls_device',xf=xform(12*C,Y0+10*C,-30),props={},tag='kt_court_controls_tag'))
    items.append(dict(label='KT2_PracticeGranter',kind='device',asset='/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter',xf=xform(C,Y0+10*C,-200),props={'bEquipGrantedItem':True}))
    items.append(dict(label='KT2_CurrentBRMovement',kind='device',asset='/CRD_PlayerMovement/SetupAssets/PID_CP_Devices_PlayerMovement.PID_CP_Devices_PlayerMovement',xf=xform(0,Y0+10*C,-50),props={'movementSettingPreset':'Current BR','bAddToPlayersOnStart':True,'enabledDuringPhase':'Gameplay Only','priority':1.0}))
    return items

def ensure_materials(m):
    colors={'Neutral':(.025,.032,.045),'Ghost':(.03,.8,1),'Dim':(.08,.17,.23),'Build':(.05,.25,.6),'Piece':(.34,.13,.55),'Aim':(.02,.4,.33)}
    result={}
    for name,color in colors.items():
        path=MODULE+'/KT_Materials/MI_KT2_'+name+'.MI_KT2_'+name
        base='M_KT2_Outline' if name in ['Ghost','Dim'] else 'M_KT2_Plain'
        parent_path=MODULE+'/KT_Materials/'+base+'.'+base
        parent_exists=m.tool(ASSET,'exists',path=parent_path)
        if not parent_exists:parent_path=MODULE+'/KT_Materials/MI_KT_Hub.MI_KT_Hub'
        if not m.tool(ASSET,'exists',path=path):
            m.tool(MI,'create',folder_path=MODULE+'/KT_Materials',asset_name='MI_KT2_'+name,parent={'refPath':parent_path})
        for param in (['Color'] if parent_exists else ['Color','LineColor']):
            m.tool(MI,'set_vector_parameter',instance={'refPath':path},name=param,value=dict(zip(['r','g','b','a'],[*color,1])))
        result[name]=path
    return result

def apply(m,items,materials):
    # Bounded batches keep the editor responsive and journal every successful chunk.
    script_prefix='''import json
def call(tool_name,**args):
    return execute_tool(tool_name,json.dumps(args)).get('returnValue')
def props(obj,values):
    return call('editor_toolset.toolsets.object.ObjectTools.set_properties',instance=obj,values=json.dumps(values))
def run():
    found={a['label']:a['actorPath'] for a in call('editor_toolset.toolsets.scene.SceneTools.find_actors',name='KT2_',collision_channels=[])}
    done=[]
    for item in ITEMS:
        label=item['label']
        if label in found:
            actor={'refPath':found[label]}
            call('editor_toolset.toolsets.actor.ActorTools.set_actor_transform',actor=actor,xform=item['xf'])
        elif item['kind']=='device':
            actor=call('ValkyrieToolset.DeviceToolset.PlaceDevice',assetPath={'refPath':item['asset']},transform=item['xf'])
            call('editor_toolset.toolsets.actor.ActorTools.set_actor_transform',actor=actor,xform=item['xf'])
        elif item['kind']=='ghost':
            actor=call('editor_toolset.toolsets.scene.SceneTools.add_to_scene_from_class',actor_type={'refPath':'/Script/FortniteGame.BuildingProp'},name=label,xform=item['xf'])
        else:
            actor=call('editor_toolset.toolsets.scene.SceneTools.add_to_scene_from_asset',asset_path=BOX,name=label,xform=item['xf'])
        call('editor_toolset.toolsets.actor.ActorTools.set_label',actor=actor,label=label)
        call('editor_toolset.toolsets.scene.SceneTools.set_actor_folder',actor=actor,folder_path='TrainingCourtV2')
        if item['kind'] in ['mesh','ghost']:
            for comp in call('editor_toolset.toolsets.actor.ActorTools.get_components',actor=actor):
                if 'StaticMeshComponent0' in comp['refPath']:
                    values={'overrideMaterials':[{'refPath':MATERIALS[item['mat']]}]}
                    if item['kind']=='ghost':
                        values.update({'staticMesh':{'refPath':BOX},'castShadow':False,'bodyInstance':{'collisionEnabled':'NoCollision','collisionProfileName':'NoCollision'}})
                    props(comp,values)
            if item['kind']=='ghost':
                props(actor,{'bAllowCustomMaterial':True,'bNoCollision':True,'bRegisterWithStructuralGrid':False,'bCanBeDamaged':False})
        if item.get('props'):props(actor,item['props'])
        if item.get('tag'):
            components=call('editor_toolset.toolsets.actor.ActorTools.get_components',actor=actor)
            tag=next((c for c in components if 'KT2_Tags' in c['refPath'] or '.KT_Tags' in c['refPath']),None)
            if tag is None:
                tag=call('editor_toolset.toolsets.actor.ActorTools.add_component',owner=actor,component_type={'refPath':'/Script/VerseTags.VerseTagMarkupComponent'},name='KT2_Tags')
            props(tag,{'internalTags':{'internalTags':[{'internalTag':{'refPath':MODULE+'/_Verse.KeystrokeTrainer-'+item['tag']}}]}})
        call('editor_toolset.toolsets.scene.SceneTools.save_actor',actor=actor)
        done.append({'label':label,'path':actor['refPath']})
    return {'placed':done}
'''
    journal=[]
    for start in range(0,len(items),12):
        script='ITEMS='+repr(items[start:start+12])+'\nBOX='+repr(BOX)+'\nMODULE='+repr(MODULE)+'\nMATERIALS='+repr(materials)+'\n'+script_prefix
        r=m.tool(PROGRAM,'execute_tool_script',script=script)
        if isinstance(r,str):r=json.loads(r)
        journal.append(r)
        (ROOT/'backups/session-2026-10-07/court-build-journal.json').write_text(json.dumps(journal,indent=2))
        print('batch',start,'result',str(r)[:160],flush=True)
    return journal

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--only-prefix',help='Apply only an exact KT2_ label prefix from the complete manifest');args=ap.parse_args()
    items=plan()
    labels=[item['label'] for item in items]
    if len(labels)!=len(set(labels)):
        raise ValueError('Actor labels must be unique before any editor writes')
    out=ROOT/'design/training-court-plan.json';out.write_text(json.dumps(items,indent=2))
    print(len(items),'actors; 24 x 20 tiles, 122.88 x 102.40 metres; plan:',out)
    if args.only_prefix:
        if not args.only_prefix.startswith('KT2_'):raise ValueError('Scoped prefix must start KT2_')
        items=[x for x in items if x['label'].startswith(args.only_prefix)]
        if not items:raise ValueError('No planned actors match this prefix')
    if args.apply:
        m=Mcp()
        if m.tool(SCENE,'get_current_level')!=MODULE+'/KeystrokeTrainer':
            raise RuntimeError('Open the intended MyProject/KeystrokeTrainer level before applying this project-specific plan')
        apply(m,items,ensure_materials(m))
        print('saved',m.tool(ASSET,'save_assets',asset_paths=[]))

if __name__=='__main__':main()
