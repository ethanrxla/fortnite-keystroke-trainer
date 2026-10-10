"""Targeted arena update. Owns KT10_Arena_* and existing KT3 arena start fixtures only."""
import argparse, json, datetime
from pathlib import Path
import build_map as b
from build_upgrades import Upgrade, BARRIER, GRANTER, AUDIO
ROOT=Path(__file__).resolve().parent.parent
SPLASH='/ChronoConsumables/Gameplay/SlapSplash/WID_Chrono_SlapSplash.WID_Chrono_SlapSplash'  # Slap Splash; never labelled as Chug Splash
MEDKIT='/PaprikaConsumables/Gameplay/MedRefresh/WID_Paprika_MedBox.WID_Paprika_MedBox'
GRAPPLER='/Figment_Hook_Gun/Gameplay/WID_Figment_Hook_Gun_VR_Ore_T03.WID_Figment_Hook_Gun_VR_Ore_T03'
SWORD='/CRD_Melee/SetupAssets/WID_Creative_Melee_Sword_Ninja.WID_Creative_Melee_Sword_Ninja'
HAMMER='/CRD_Melee/SetupAssets/WID_Creative_Melee_Hammer_SledgeWrapped.WID_Creative_Melee_Hammer_SledgeWrapped'
CONDITIONAL='/CreativeCoreDevices/SetupAssets/PID_Devices_ConditionalButton_V2.PID_Devices_ConditionalButton_V2'
def decode(v):return json.loads(v) if isinstance(v,str) else v

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 if not args.apply:
  print('512cm flush pads; opposing ramps; wall controls120cm; supplies/checker; Sword/Hammer+Grappler; no-build zone. Existing armory untouched.');return
 u=Upgrade();m=u.m;bb=u.b
 folder=ROOT/'backups'/('arena-layout-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));folder.mkdir()
 journal=[]
 def note(v):journal.append(v);(folder/'journal.json').write_text(json.dumps(journal,indent=2))
 def tag(path,t):
  ref={'refPath':path};cs=m.tool(b.ACTOR,'get_components',actor=ref)
  comp=next((x for x in cs if x['refPath'].endswith('.KT_ArenaV2Tags')),None)
  if comp is None:comp=m.tool(b.ACTOR,'add_component',owner=ref,component_type={'refPath':'/Script/VerseTags.VerseTagMarkupComponent'},name='KT_ArenaV2Tags')
  m.tool(b.OBJ,'list_properties',instance=comp);m.tool(b.OBJ,'set_properties',instance=comp,values=json.dumps({'internalTags':{'internalTags':[{'internalTag':{'refPath':b.MODULE+'/_Verse.KeystrokeTrainer-'+t}}]}}))
 def props(path,values):
  ref={'refPath':path};m.tool(b.OBJ,'list_properties',instance=ref)
  note(dict(path=path,before=decode(m.tool(b.OBJ,'get_properties',instance=ref,properties=list(values))),after=values));bb.props(path,values)
  assert decode(m.tool(b.OBJ,'get_properties',instance=ref,properties=list(values)))==values,(path,values)
 def device(name,asset,pose,values,t=None):
  if name in u.f:path=u.f[name]
  else:
   ref=m.tool(b.DEVICE,'PlaceDevice',assetPath={'refPath':asset},transform=pose);path=ref['refPath'];m.tool(b.ACTOR,'set_label',actor=ref,label=name);u.f[name]=path;note(dict(created=name,path=path))
  m.tool(b.ACTOR,'set_actor_transform',actor={'refPath':path},xform=pose)
  if values:props(path,values)
  if t:tag(path,t)
  u.paths.append(path);return path
 def items(path,entries):
  ref={'refPath':path}
  try:obj=decode(m.tool(b.OBJ,'get_properties',instance=ref,properties=['pickupItemList']))['pickupItemList']
  except RuntimeError:obj=decode(m.tool(b.OBJ,'get_properties',instance=ref,properties=['itemList']))['itemList']
  m.tool(b.OBJ,'list_properties',instance=obj)
  old=decode(m.tool(b.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData'];data=[{'itemDefinition':{'refPath':p},'itemQuantity':q} for p,q in entries]
  note(dict(path=obj['refPath'],before=old,after=data))
  normalize=lambda ds:[(d['itemDefinition']['refPath'],d['itemQuantity']) for d in ds]
  if normalize(old)!=entries:
   m.tool(b.OBJ,'reset_properties',instance=obj,properties=['itemListData'])
   for d in data:
    current=decode(m.tool(b.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData']
    bb.props(obj['refPath'],{'itemListData':current+[d]})
  actual=decode(m.tool(b.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData']
  assert normalize(actual)==entries,(path,normalize(actual),entries)
 ax=-31488.;ay=-76800.
 for side,dy,face in [('A',-256,90),('B',256,-90)]:
  name='KT3_Upgrade_Arena_Pad_'+side;path=u.f[name];note(dict(path=path,transform=m.tool(b.ACTOR,'get_actor_transform',actor={'refPath':path})))
  m.tool(b.ACTOR,'set_actor_transform',actor={'refPath':path},xform=b.xform(ax,ay+dy,-4,5.12,5.12,.04));u.paths.append(path)
  for kind,dx,text,t in [('Start',-90,'START: 3 second countdown','kt3_arena_start_tag'),('Mode',90,'Mode: Build / No-build guns / Melee','kt3_arena_mode_tag')]:
   device('KT3_Upgrade_Arena_'+kind+'_'+side,b.BUTTON,b.xform(ax+dx,ay+(-12 if side=='A' else 12),120,yaw=face),{'interaction Text':text,'interactionRadius':.8,'delay':0.0},t)
  device('KT10_Arena_Weapon_'+side,b.BUTTON,b.xform(ax+210,ay+(-12 if side=='A' else 12),120,yaw=face),{'interaction Text':'My melee weapon: Sword / Hammer','interactionRadius':.6},'kt10_arena_weapon_choice_tag')
  device('KT10_Arena_Mute_'+side,b.BUTTON,b.xform(ax-210,ay+(-12 if side=='A' else 12),120,yaw=face),{'interaction Text':'My arena voice: mute / unmute','interactionRadius':.6},'kt10_arena_mute_tag')
  label='KT10_Arena_Ramp_'+side
  if label not in u.f:
   r=m.tool(b.SCENE,'add_to_scene_from_asset',asset_path='/Game/Building/ActorBlueprints/Player/Wood/L1/PBWA_W1_StairW.PBWA_W1_StairW_C',name=label,xform=b.xform(ax,ay+dy*3,0,yaw=270 if side=='A' else 90));u.f[label]=r['refPath'];note(dict(created=label,path=r['refPath']))
  props(u.f[label],{'bCanBeDamaged':False});u.paths.append(u.f[label])
  old=u.f['KT3_Upgrade_Arena_PadLabel_'+side];m.tool(b.ACTOR,'set_actor_transform',actor={'refPath':old},xform=b.xform(ax-600,ay+dy,180,yaw=face));u.paths.append(old)
 divider=u.f['KT3_Upgrade_Arena_Divider'];props(divider,{'barrierWidth':20.0,'barrierDepth':.05,'barrierHeight':8.0,'blockWeaponFire':True,'collide with Camera':False})
 controller=u.f['KT3_Upgrade_Arena_Controller'];ref={'refPath':controller}
 m.tool(b.DEVICE,'ListDeviceProperties',device=ref)
 values={'padA':{'x':ax,'y':ay-256,'z':0},'padB':{'x':ax,'y':ay+256,'z':0},'padHalfLength':230.0,'padHalfWidth':215.0}
 note(dict(path=controller,before=m.tool(b.DEVICE,'GetDeviceProperties',device=ref,propertyNames=list(values)),after=values))
 for k,v in values.items():m.tool(b.DEVICE,'SetDeviceProperty',device=ref,propertyName=k,value=json.dumps(v))
 assert decode(m.tool(b.DEVICE,'GetDeviceProperties',device=ref,propertyNames=list(values)))==values
 tag(controller,'kt10_arena_test_tag')
 status=u.f['KT3_Upgrade_Arena_Status'];m.tool(b.ACTOR,'set_actor_transform',actor={'refPath':status},xform=b.xform(ax-700,ay,320,yaw=90));u.paths.append(status)
 device('KT10_Arena_Score',b.BILLBOARD,b.xform(-35000,ay,450,2,2,2,yaw=0),{'text':'SESSION SCORE\nWins and deaths appear after your first round','textSize':18,'showBorder':False},'kt10_arena_score_tag')
 zone=device('KT10_Arena_NoBuild','/CRD_VolumetricRegion/SetupAssets/PID_Device_Mutator.PID_Device_Mutator',b.xform(-30720,ay,0),{'zoneWidth':20.0,'zoneDepth':12.0,'zoneHeight':8.0,'bAllowBuilding':False,'bAllowWeaponFire':True,'bAffectsPlayers':True,'bAffectsGuards':False,'zoneVisibleDuringGame':False,'enabledOnPhase':'None'},'kt10_arena_nobuild_tag')
 grant={'onGrantAction':'Keep All','grant':'All Items','bEquipGrantedItem':False,'dropItemsAtPlayerLocation':'Never','grantCondition':'Only If Space'}
 g=device('KT10_Arena_Supplies',GRANTER,b.xform(ax,ay,-150),grant,'kt10_arena_supplies_tag');items(g,[(SPLASH,6),(MEDKIT,1)])
 r=device('KT10_Arena_SupplyRemove',b.ITEM_REMOVER,b.xform(ax,ay,-180),{'affectedItems':'Objects In Device','removalMethod':'Remove Items','percentageToRemove':100},'kt10_arena_supply_remove_tag');items(r,[(SPLASH,1),(MEDKIT,1)])
 for name,weapon,t in [('KT3_Upgrade_Arena_Melee',SWORD,'kt3_arena_melee_tag'),('KT10_Arena_Hammer',HAMMER,'kt10_arena_hammer_tag')]:
  g=device(name,GRANTER,b.xform(ax,ay,-210),{**grant,'bEquipGrantedItem':True},t);items(g,[(weapon,1),(GRAPPLER,1)])
 check=device('KT10_Arena_SupplyCheck',CONDITIONAL,b.xform(ax,ay,-250),{'consumeKeyItems':False,'numberOfKeyItemSlots':2,'keyItemsRequired':6,'keyItemsRequired_Override':True,'secondKeyItemsRequired':1,'secondKeyItemsRequired_Override':True,'allowInteraction':False,'visibleDuringGame':'No'},'kt10_arena_supply_check_tag')
 locks=decode(m.tool(b.OBJ,'get_properties',instance={'refPath':check},properties=['bP_KeyLockComponent','bP_KeyLockComponent2']))
 for lock,item in zip(locks.values(),[SPLASH,MEDKIT]):
  m.tool(b.OBJ,'list_properties',instance=lock);bb.props(lock['refPath'],{'unlockKeyItem':{'itemDefinition':{'refPath':item},'itemVariantGuid':'00000000-0000-0000-0000-000000000000'}})
 # Melee removal covers registered armory guns and the two melee choices, preserving pickaxe.
 guns=[]
 for label,path in u.f.items():
  if label.startswith('KT_Gun_') and not label.endswith(('_PREV','_GIVE','_NEXT')):
   try:
    obj=decode(m.tool(b.OBJ,'get_properties',instance={'refPath':path},properties=['pickupItemList']))['pickupItemList'];guns += [d['itemDefinition']['refPath'] for d in decode(m.tool(b.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData']]
   except (RuntimeError,TypeError,KeyError):pass
 guns += [SWORD,HAMMER,GRAPPLER];items(u.f['KT3_Upgrade_Arena_RemoveLoadout'],[(p,1) for p in dict.fromkeys(guns)])
 mapping_file=ROOT/'assets/voice/arena/uefn_assets.json'
 if mapping_file.exists():
  mapping=json.loads(mapping_file.read_text())
  for cue,t in [('arena_win','kt10_arena_win_voice_tag'),('arena_comeback','kt10_arena_comeback_voice_tag')]:
   assert m.tool('editor_toolset.toolsets.asset.AssetTools','exists',path=mapping[cue])
   device('KT10_Arena_Voice_'+cue,AUDIO,b.xform(ax,ay,-300),{'audio':{'refPath':mapping[cue]},'can Be Heard By':'Instigator Only','enable Spatialization':False,'enable Volume Attenuation':False,'volume':.65},t)
 u.paths += [divider,controller]
 for path in set(u.paths):m.tool(b.SCENE,'save_actor',actor={'refPath':path})
 print('Arena configured. Journal:',folder,flush=True)
if __name__=='__main__':main()
