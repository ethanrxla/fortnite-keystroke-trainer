"""Repair existing racks additively; preserve their current registered weapon lists.

Dry run by default. --apply updates only the rack and its own KT3_GunRack_* fixtures.
The native item granters keep all inventory; utility items are validated by UEFN on push.

Root cause recorded from the current editor snapshot: every Item Granter was explicitly hidden
during the minigame (`bIsVisibleDuringMinigame=False`), so its actual weapon preview vanished
when the game started. This pass turns the in-game preview on, preserves the verified contents,
and hides the stock button meshes. Players still get the short interaction prompts at the rack;
there are no floating red control boxes or extra floating PREV/GIVE/NEXT label cards.
"""
import argparse
import json
from pathlib import Path
import build_map as bm
from armory import weapon_classes

ROOT=bm.ROOT
PFX='KT3_GunRack_'
GRANTER='/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter.PID_Device_ItemGranter'
UTILITIES={
 'GRAPPLE':['/GrappleGloves/Items/GrappleGloves/WID_GrappleGloves.WID_GrappleGloves'],
 'MELEE':['/CRD_Melee/SetupAssets/WID_Creative_Melee_Sword_Ninja.WID_Creative_Melee_Sword_Ninja','/CRD_Melee/SetupAssets/WID_Creative_Melee_Hammer_SledgeWrapped.WID_Creative_Melee_Hammer_SledgeWrapped'],
}

def decoded(value):return json.loads(value) if isinstance(value,str) else value

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 b=bm.Builder();m=b.m
 if m.tool(bm.SCENE,'get_current_level')!=bm.MODULE+'/KeystrokeTrainer':raise RuntimeError('Wrong open level')
 actors=m.tool(bm.SCENE,'find_actors',name='',collision_channels=[]);found={a['label']:a['actorPath'] for a in actors}
 backup=ROOT/'backups/gun-rack-2026-10-08';backup.mkdir(parents=True,exist_ok=True)
 journal=[]
 def change(path,values):
  r={'refPath':path};m.tool(bm.OBJ,'list_properties',instance=r)
  old=m.tool(bm.OBJ,'get_properties',instance=r,properties=list(values))
  journal.append({'path':path,'before':decoded(old),'after':values})
  (backup/'repair-journal.json').write_text(json.dumps(journal,indent=2),encoding='utf-8')
  return b.props(path,values)
 def device(asset,label,pose):
  if label in found:
   p=found[label];m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':p},xform=pose);return p
  r=m.tool(bm.DEVICE,'PlaceDevice',assetPath={'refPath':asset},transform=pose)
  p=b.labelled(r['refPath'],label);m.tool(bm.ACTOR,'set_actor_transform',actor=r,xform=pose);found[label]=p;return p
 def mesh(label,x,y,z,w,d,h):
  pose=bm.xform(x,y,z,w/100,d/100,h/100)
  if label in found:p=found[label];m.tool(bm.ACTOR,'set_actor_transform',actor={'refPath':p},xform=pose)
  else:p=b.labelled(m.tool(bm.SCENE,'add_to_scene_from_asset',asset_path=bm.BOX,name=label,xform=pose)['refPath'],label);found[label]=p
  for c in m.tool(bm.ACTOR,'get_components',actor={'refPath':p}):
   if 'StaticMeshComponent0' in c['refPath']:b.props(c['refPath'],{'overrideMaterials':[{'refPath':bm.MODULE+'/KT_Materials/MI_KT2_Neutral.MI_KT2_Neutral'}]})
  b.props(p,{'bCanBeDamaged':False});m.tool(bm.SCENE,'save_actor',actor={'refPath':p})
  return p
 stations=[]
 for n,cat in enumerate(['AR','SMG','SHOTGUN','SNIPER','PISTOL','EXPLOSIVES']):
  stations.append((cat,bm.hub_cc(-5+2*n,-11.5)))
 for cat,off in [('GRAPPLE',-5),('MELEE',-2),('HEALS',1),('TRAPS',4)]:stations.append((cat,bm.hub_cc(off,-8.4)))
 catalog=weapon_classes(m)
 for cat,(x,y) in stations:
  lab='KT_Gun_'+cat;existing=found.get(lab)
  if existing:
   ref=decoded(m.tool(bm.OBJ,'get_properties',instance={'refPath':existing},properties=['pickupItemList']))['pickupItemList']
   data=decoded(m.tool(bm.OBJ,'get_properties',instance=ref,properties=['itemListData']))['itemListData']
  else:data=[{'itemDefinition':{'refPath':p},'itemQuantity':1} for p in UTILITIES.get(cat,[])]
  # Preserve every current weapon; restore registry-listed healing, throwable and trap choices
  # instead of letting the one-item practice preset replace a whole category. Registry presence
  # is not UEFN validation; every newly added path still needs a successful editor cook.
  rej=set(json.load(open(ROOT/'shared/asset-exclusions.json'))['rejected_item_paths']);discovered=[item[2] for item in catalog.get(cat,[]) if item[2] not in rej] if cat in ['HEALS','EXPLOSIVES','TRAPS'] else []
  known={item['itemDefinition']['refPath'] for item in data}
  additions=[p for p in discovered if p not in known]
  data += [{'itemDefinition':{'refPath':p},'itemQuantity':1} for p in additions]
  if not data:
   print(cat,'no eligible registered items available; skipping station',flush=True)
   continue
  print(cat,len(data),'items', 'position',(round(x),round(y)),flush=True)
  if not args.apply:continue
  g=device(GRANTER,lab,bm.xform(x,y,80,yaw=180))
  if existing and additions:
   ref=decoded(m.tool(bm.OBJ,'get_properties',instance={'refPath':g},properties=['pickupItemList']))['pickupItemList']
   for item in additions:
    cur=decoded(m.tool(bm.OBJ,'get_properties',instance=ref,properties=['itemListData']))['itemListData']
    b.props(ref['refPath'],{'itemListData':cur+[{'itemDefinition':{'refPath':item},'itemQuantity':1}]})
  if not existing:
   ref=decoded(m.tool(bm.OBJ,'get_properties',instance={'refPath':g},properties=['pickupItemList']))['pickupItemList']
   m.tool(bm.OBJ,'reset_properties',instance=ref,properties=['itemListData'])
   for item in data:
    cur=decoded(m.tool(bm.OBJ,'get_properties',instance=ref,properties=['itemListData']))['itemListData']
    b.props(ref['refPath'],{'itemListData':cur+[item]})
  change(g,{'onGrantAction':'Keep All','grant':'Current Item','grantCondition':'Always','cycleBehavior':'Wrap','bEquipGrantedItem':True,'bShowFirstInteractPrompt':True})
  visibility=decoded(m.tool(bm.OBJ,'get_properties',instance={'refPath':g},properties=['visibleInGameComponent']))['visibleInGameComponent']
  change(visibility['refPath'],{'visibleDuringPhase':'Always Visible'})
  mesh(PFX+'Bench_'+cat,x,y,0,480,160,80)
  for dx,key,fn in [(-160,'PREV','CycleToPreviousItem'),(0,'GIVE','GrantItem'),(160,'NEXT','CycleToNextItem')]:
   btn=device(bm.BUTTON,lab+'_'+key,bm.xform(x+dx,y+170,110,yaw=180))
   text=('Equip' if key=='GIVE' else 'Previous' if key=='PREV' else 'Next')+' '+cat.lower()
   change(btn,{'interaction Text':text,'interactionRadius':.6,'delay':0.0,'resetDelay':.15,'visibleDuringGame':False})
   links=m.tool(bm.DEVICE,'ListEventBindings',devicePath={'refPath':g})
   if not any(v['sourceDevicePath']['refPath']==btn and v['targetFunction']==fn for v in links):b.bind(btn,'On Interact',g,fn)
   # Keep the interaction device itself invisible. The weapon preview and physical gun case
   # make the rack legible; the native interaction prompt supplies the action only in range.
  sign=device(bm.BILLBOARD,'KT_Sign_Armory_'+cat,bm.xform(x,y-90,290,1.3,1.3,1.3,yaw=180))
  title='SHIELDS / HEALS' if cat=='HEALS' else cat
  change(sign,{'text':title,'textSize':18,'showBorder':False,'textColor':{'r':1,'g':1,'b':1,'a':1},'backgroundColor':{'r':.008,'g':.01,'b':.015,'a':1}})
  m.tool(bm.SCENE,'save_actor',actor={'refPath':g})
 if args.apply:
  for a in m.tool(bm.SCENE,'find_actors',name='KT3_GunRack_SpawnTools',collision_channels=[]):
   if a['label']=='KT3_GunRack_SpawnTools':m.tool(bm.SCENE,'remove_from_scene',actor={'refPath':a['actorPath']})
  for a in m.tool(bm.SCENE,'find_actors',name='KT3_GunRack_Label_',collision_channels=[]):
   if a['label'].startswith('KT3_GunRack_Label_'):m.tool(bm.SCENE,'remove_from_scene',actor={'refPath':a['actorPath']})
  print('saved',m.tool('editor_toolset.toolsets.asset.AssetTools','save_assets',asset_paths=[]))

if __name__=='__main__':main()
