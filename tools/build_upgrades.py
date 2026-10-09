"""Add RXLA panels, practical cover/targets and the 1v1 ready platform.

Default is dry-run. --apply upserts KT3_Upgrade_* actors and patches only named
existing signs/materials. Does not rebuild the map or reuse teleporter groups.
"""
import argparse
import json
from pathlib import Path
import build_map as bm

ROOT=bm.ROOT
PFX='KT3_Upgrade_'
AS='editor_toolset.toolsets.asset.AssetTools'
MT='editor_toolset.toolsets.material.MaterialTools'
MI='editor_toolset.toolsets.material_instance.MaterialInstanceTools'
BARRIER='/CRD_VolumetricRegion/SetupAssets/PID_Device_Barrier.PID_Device_Barrier'
AUDIO='/CRD_AudioPlayer/SetupAssets/PID_CP_Devices_CRD_AudioPlayer.PID_CP_Devices_CRD_AudioPlayer'
SENTRY='/CRD_SentryDevice/SetupAssets/Creative_Device_SentryProp_V2.Creative_Device_SentryProp_V2'
GRANTER='/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter'
C=512.0;H=384.0

def decode(v):return json.loads(v) if isinstance(v,str) else v

class Upgrade:
 def __init__(self):
  self.b=bm.Builder();self.m=self.b.m
  if self.m.tool(bm.SCENE,'get_current_level')!=bm.MODULE+'/KeystrokeTrainer':raise RuntimeError('Wrong open level')
  self.f={a['label']:a['actorPath'] for a in self.m.tool(bm.SCENE,'find_actors',collision_channels=[])}
  self.paths=[]
 def label(self,r,name):
  p=self.b.labelled(r['refPath'],name);self.f[name]=p;self.paths.append(p);return p
 def device(self,asset,name,pose,props=None,tag=None):
  name=PFX+name
  if name in self.f:p=self.f[name];self.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':p},xform=pose)
  else:
   r=self.m.tool(bm.DEVICE,'PlaceDevice',assetPath={'refPath':asset},transform=pose);p=self.label(r,name);self.m.tool(bm.ACTOR,'set_actor_transform',actor=r,xform=pose)
  if props:self.b.props(p,props)
  if tag:
   cs=self.m.tool(bm.ACTOR,'get_components',actor={'refPath':p});comp=next((x for x in cs if 'KT_Tags' in x['refPath']),None)
   if not comp:self.b.tag(p,tag)
  self.paths.append(p);return p
 def block(self,name,x,y,z,w,d,h,material=None):
  name=PFX+name;pose=bm.xform(x,y,z,w/100,d/100,h/100)
  if name in self.f:p=self.f[name];self.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':p},xform=pose)
  else:p=self.label(self.m.tool(bm.SCENE,'add_to_scene_from_asset',asset_path=bm.BOX,name=name,xform=pose),name)
  for comp in self.m.tool(bm.ACTOR,'get_components',actor={'refPath':p}):
   if 'StaticMeshComponent0' in comp['refPath']:self.b.props(comp['refPath'],{'overrideMaterials':[{'refPath':material or bm.MODULE+'/KT_Materials/MI_KT2_Neutral.MI_KT2_Neutral'}]})
  self.b.props(p,{'bCanBeDamaged':False});self.paths.append(p);return p
 def sign(self,name,x,y,z,text,yaw=90,scale=1.5):
  return self.device(bm.BILLBOARD,name,bm.xform(x,y,z,scale,scale,scale,yaw=yaw),{'text':text,'textSize':18,'showBorder':False,'textColor':{'r':1,'g':1,'b':1,'a':1},'backgroundColor':{'r':.008,'g':.012,'b':.02,'a':1}})
 def items(self,p,items):
  obj=decode(self.m.tool(bm.OBJ,'get_properties',instance={'refPath':p},properties=['pickupItemList']))['pickupItemList']
  self.m.tool(bm.OBJ,'reset_properties',instance=obj,properties=['itemListData'])
  for path in items:
   data=decode(self.m.tool(bm.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData']
   self.b.props(obj['refPath'],{'itemListData':data+[{'itemDefinition':{'refPath':path},'itemQuantity':1}]})
 def logo_material(self):
  tex={'refPath':bm.MODULE+'/KT_Brand/T_RXLA_Logo.T_RXLA_Logo'}
  self.b.props(tex['refPath'],{'powerOfTwoMode':'StretchToPowerOfTwo','neverStream':False,'mipGenSettings':'TMGS_FromTextureGroup'})
  path=bm.MODULE+'/KT_Materials/M_RXLA_Display.M_RXLA_Display'
  if not self.m.tool(AS,'exists',path=path):
   mat=self.m.tool(MT,'create_material',folder_path=bm.MODULE+'/KT_Materials',asset_name='M_RXLA_Display')
   node=self.m.tool(MT,'add_expression',material_or_function=mat,expression_class={'refPath':'/Script/Engine.MaterialExpressionTextureSample'},x=-300,y=0)
   self.b.props(node['refPath'],{'texture':tex})
   self.m.tool(MT,'connect_to_output',expression=node,output_name='RGB',material_property='MP_EmissiveColor')
   self.m.tool(MT,'connect_to_output',expression=node,output_name='A',material_property='MP_OpacityMask')
   self.b.props(path,{'shadingModel':'MSM_Unlit','blendMode':'BLEND_Masked','twoSided':True})
   self.m.tool(MT,'recompile',material_or_function=mat)
  return path
 def logo(self,name,x,y,z,size,normal,material):
  # Normal axis sets a physical panel; source mark remains square and unchanged.
  if normal=='x':
   self.block(name+'_Frame',x+8,y,z-size/2,16,size+32,size+32)
   pose=bm.xform(x,y,z,size/100,size/100,1,yaw=90);pose['rotation']['roll']=90
  else:
   self.block(name+'_Frame',x,y+8,z-size/2,size+32,16,size+32)
   pose=bm.xform(x,y,z,size/100,size/100,1);pose['rotation']['roll']=90
  label=PFX+name
  if label in self.f:p=self.f[label];self.m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':p},xform=pose)
  else:p=self.label(self.m.tool(bm.SCENE,'add_to_scene_from_asset',asset_path='/Engine/BasicShapes/Plane.Plane',name=label,xform=pose),label)
  for comp in self.m.tool(bm.ACTOR,'get_components',actor={'refPath':p}):
   if 'StaticMeshComponent0' in comp['refPath']:self.b.props(comp['refPath'],{'overrideMaterials':[{'refPath':material}],'castShadow':False,'bodyInstance':{'collisionEnabled':'NoCollision','collisionProfileName':'NoCollision'}})
  self.paths.append(p)
 def build(self):
  logo=self.logo_material()
  self.logo('Logo_Hub',2480,-61184,700,512,'x',logo)
  self.logo('Logo_Armory',256,-66380,760,512,'y',logo)
  self.logo('Logo_Arena',-35000,-79700,650,384,'y',logo)
  # Make architecture quieter; colored routes and signage continue to distinguish skills.
  colors={'Hub':(.12,.035,.01),'Build':(.025,.12,.3),'Piece':(.12,.04,.22),'Edit':(.24,.08,.015),'Armory':(.22,.035,.018),'Aim':(.015,.14,.11),'Arena':(.23,.1,.035),'Scenario':(.12,.17,.04)}
  for zone,col in colors.items():
   for param,val in [('Color',(.018,.022,.03)),('LineColor',col)]:
    self.m.tool(MI,'set_vector_parameter',instance={'refPath':bm.MAT[zone]},name=param,value={'r':val[0],'g':val[1],'b':val[2],'a':1})
  # 1v1 pads are build-grid aligned at one level, immediately against the separator.
  ax=-31744.0;ay=-76800.0
  for side,dy in [('A',-256),('B',256)]:
   self.block('Arena_Pad_'+side,ax,ay+dy,0,1024,512,H)
   self.sign('Arena_PadLabel_'+side,ax-430,ay+dy,630,'PLAYER '+side,90,1)
   self.device(bm.BUTTON,'Arena_Start_'+side,bm.xform(ax+340,ay+dy,500),{'interaction Text':'Start 1v1 countdown','interactionRadius':.6,'delay':0.0,'resetDelay':.25},'kt3_arena_start_tag')
   self.device(bm.BUTTON,'Arena_Mode_'+side,bm.xform(ax-340,ay+dy,500),{'interaction Text':'Toggle melee-only mode','interactionRadius':.6,'delay':0.0,'resetDelay':.25},'kt3_arena_mode_tag')
  # Width is local X; depth is local Y. The wall stays between pads through countdown.
  self.device(BARRIER,'Arena_Divider',bm.xform(-30720,ay,0),{'barrierWidth':20.0,'barrierDepth':.05,'barrierHeight':4.0,'zoneShape':'Box','blockWeaponFire':True,'collide with Camera':False,'baseVisibleDuringGame':False,'barrierMaterial':{'refPath':'/Game/Items/Traps/Materials/M_Barrier_BoundsTranslucent_Blue_Inst.M_Barrier_BoundsTranslucent_Blue_Inst'}},'kt3_arena_divider_tag')
  self.device(BARRIER,'Arena_Perimeter',bm.xform(-30720,ay,0),{'barrierWidth':20.0,'barrierDepth':12.0,'barrierHeight':8.0,'zoneShape':'Hollow Box','blockWeaponFire':True,'collide with Camera':False,'baseVisibleDuringGame':False,'barrierMaterial':None})
  self.sign('Arena_Status',ax-650,ay,900,'1v1\nStep onto both platforms\nPress START',90,2.5)
  self.b.tag(self.f[PFX+'Arena_Status'],'kt3_arena_status_tag')
  self.device(bm.MODULE+'/_Verse.KeystrokeTrainer-keystroke_arena_device','Arena_Controller',bm.xform(ax,ay,-100))
  self.device(bm.EXPLOSIVE,'Arena_Clear',bm.xform(-30720,ay,768),{'blast Radius':13.0,'player Damage':0,'structure Damage':10000,'knockback':'None','can be Damaged':False,'damage Indestructible Buildings':False,'visible During Game':False,'play Audio / VFX':False,'time Until Reset Allowed':.1,'has Timed Detonation From Game Start':False},'kt3_arena_reset_tag')
  preset=json.loads((ROOT/'shared/practice-loadout.json').read_text(encoding='utf-8'))['items']
  for name,items,tag in [('Arena_Standard',[preset['AR'],preset['SHOTGUN']],'kt3_arena_standard_tag'),('Arena_Melee',['/CRD_Melee/SetupAssets/WID_Creative_Melee_Sword_Ninja.WID_Creative_Melee_Sword_Ninja'],'kt3_arena_melee_tag')]:
   g=self.device(GRANTER,name,bm.xform(ax,ay,-150),{'onGrantAction':'Keep All','grant':'All Items','bEquipGrantedItem':True},tag);self.items(g,items)
  rem=self.device(bm.ITEM_REMOVER,'Arena_RemoveLoadout',bm.xform(ax,ay,-180),{'affectedItems':'Objects In Device','removalMethod':'Remove Items','percentageToRemove':100,'bRemoveAllVariationsOfTheSelectedItem':True},'kt3_arena_remover_tag')
  allitems=[]
  for label,path in self.f.items():
   if label.startswith('KT_Gun_') and not label.endswith(('_PREV','_GIVE','_NEXT')):
    obj=decode(self.m.tool(bm.OBJ,'get_properties',instance={'refPath':path},properties=['pickupItemList']))['pickupItemList']
    allitems += [i['itemDefinition']['refPath'] for i in decode(self.m.tool(bm.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData']]
  bm.fill_item_list(self.b,rem,list(dict.fromkeys(allitems)))
  for cue,tag in [('arena_three','kt3_arena_three_tag'),('arena_two','kt3_arena_two_tag'),('arena_one','kt3_arena_one_tag'),('arena_go','kt3_arena_go_tag'),('arena_ready','kt3_arena_ready_tag'),('arena_reset','kt3_arena_reset_voice_tag'),('arena_melee','kt3_arena_melee_voice_tag'),('arena_standard','kt3_arena_standard_voice_tag')]:
   self.device(AUDIO,'Voice_'+cue,bm.xform(ax,ay,-220),{'can Be Heard By':'Instigator Only','enable Spatialization':False,'enable Volume Attenuation':False,'volume':.8},tag)
  # Native targets with actual corners and protected approach geometry in the aim district.
  for n,(x,y) in enumerate([(-32000,-88900),(-29500,-87200),(-27500,-85500)]):
   self.block('Aim_Cover_'+str(n),x-600,y,0,24,512,H)
   self.block('Aim_Corner_'+str(n),x-600,y-256,0,512,24,H)
   self.device(bm.DUMMY,'Aim_Target_'+str(n),bm.xform(x,y+350,0,yaw=180),{'infiniteHealth':True})
  # A shootable native practice sentry, spawned on demand rather than firing in the hub.
  bot=self.device(SENTRY,'Practice_Bot',bm.xform(-27000,-87800,0,yaw=180),{'spawnOnGameStart':False,'sentryHealth':200,'accuracy':'Low','range':10,'respawnOnATimer':False})
  button=self.device(bm.BUTTON,'Spawn_Bot',bm.xform(-31000,-87800,120),{'interaction Text':'Spawn practice bot','interactionRadius':.6})
  self.b.bind(button,'On Interact',bot,'Spawn')
  self.sign('Bot_Label',-31000,-88050,330,'BOT PRACTICE\nPress to spawn a sentry',90,1.5)
  self.block('Bot_Cover',-27700,-87800,0,24,512,H)
  self.scenario_angles()
  for label in ['KT_Sign_Gate_Arena','KT_Sign_Area_Arena']:
   if label in self.f:self.b.props(self.f[label],{'text':'1v1 ARENA\nREADY / START / MELEE MODE','textSize':18})
  for label in ['KT3_Upgrade_Barrier_Probe','KT3_Upgrade_Audio_Probe','KT3_Upgrade_Sentry_Probe']:
   if label in self.f:self.m.tool(bm.SCENE,'remove_from_scene',actor={'refPath':self.f[label]})
  for p in set(self.paths):self.m.tool(bm.SCENE,'save_actor',actor={'refPath':p})
  print('saved',self.m.tool(AS,'save_assets',asset_paths=[]),flush=True)
  (ROOT/'backups/gun-rack-2026-10-08/upgrades-placed.json').write_text(json.dumps(self.paths,indent=2))

 def scenario_angles(self):
  # Standalone unscored labs stay inside the Scenario floor. They do not assume
  # moved drill devices and legacy shell rooms still share their original bounds.
  for code in ['P4','P5','P7','P8']:
   for suffix in ['Corner','OffsetCover','Target']:
    label=PFX+'Lane_'+code+'_'+suffix
    if label in self.f:self.m.tool(bm.SCENE,'remove_from_scene',actor={'refPath':self.f[label]})
  for n,y in enumerate([-68864,-67328,-65792,-64256]):
   side=-1 if n%2==0 else 1
   self.block('Scenario_'+str(n)+'_Corner',-29696,y+side*512,0,24,512,H)
   self.block('Scenario_'+str(n)+'_Angle',-29440,y+side*768-side*12,0,512,24,H)
   self.device(bm.DUMMY,'Scenario_'+str(n)+'_Target',bm.xform(-28160,y+side*256,0,yaw=180),{'infiniteHealth':True})
   self.sign('Scenario_'+str(n)+'_Brief',-33000,y,500,'ANGLE '+str(n+1)+' | FREE PRACTICE\nBuild cover, track target, peek safely',90,1.2)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 if not args.apply:
  print('Plan: 3 RXLA panels; neutral section architecture; 2 ready pads, divider/perimeter, 4 controls; fair gun/melee kits; 4 voice hooks; 7 added targets; native practice bot; corner/offset cover.');return
 Upgrade().build()

if __name__=='__main__':main()
