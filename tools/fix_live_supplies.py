"""Restore exact previous supplies and ordered spawn replenishment, preserving weapons."""
import json
import build_map as b
SPLASH='/ChronoConsumables/Gameplay/SlapSplash/WID_Chrono_SlapSplash.WID_Chrono_SlapSplash'
MED='/PaprikaConsumables/Gameplay/MedRefresh/WID_Paprika_MedBox.WID_Paprika_MedBox'
def main():
 m=b.Mcp();actors=m.tool(b.SCENE,'find_actors',collision_channels=[]);by={a['label']:a['actorPath'] for a in actors}
 def items(label,entries):
  r={'refPath':by[label]};p=json.loads(m.tool(b.OBJ,'list_properties',instance=r))
  key='pickupItemList' if 'pickupItemList' in p else 'itemList'
  obj=json.loads(m.tool(b.OBJ,'get_properties',instance=r,properties=[key]))[key]
  m.tool(b.OBJ,'list_properties',instance=obj);m.tool(b.OBJ,'reset_properties',instance=obj,properties=['itemListData'])
  for path,q in entries:
   old=json.loads(m.tool(b.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData']
   m.tool(b.OBJ,'set_properties',instance=obj,values=json.dumps({'itemListData':old+[{'itemDefinition':{'refPath':path},'itemQuantity':q}]}))
  actual=json.loads(m.tool(b.OBJ,'get_properties',instance=obj,properties=['itemListData']))['itemListData'];assert [(x['itemDefinition']['refPath'],x['itemQuantity']) for x in actual]==entries
  m.tool(b.SCENE,'save_actor',actor=r);return r
 def tag(r,name):
  cs=m.tool(b.ACTOR,'get_components',actor=r)
  # Native creative objects consume their primary tag markup; merge rather than add another.
  component=next((c for c in cs if 'VerseTagMarkup' in c['refPath'] or c['refPath'].endswith('.KT_ArenaTag')),None)
  if component is None:
   for c in cs:
    try:
     props=json.loads(m.tool(b.OBJ,'list_properties',instance=c))
     if 'internalTags' in props:component=c;break
    except Exception:pass
  if component is None:component=m.tool(b.ACTOR,'add_component',owner=r,component_type={'refPath':'/Script/VerseTags.VerseTagMarkupComponent'},name='KT_Spawn_'+name)
  m.tool(b.OBJ,'list_properties',instance=component)
  old=json.loads(m.tool(b.OBJ,'get_properties',instance=component,properties=['internalTags']))['internalTags']
  tags=old.get('internalTags',[]);new={'internalTag':{'refPath':b.MODULE+'/_Verse.KeystrokeTrainer-'+name}}
  if new not in tags:tags.append(new)
  m.tool(b.OBJ,'set_properties',instance=component,values=json.dumps({'internalTags':{'internalTags':tags}}));m.tool(b.SCENE,'save_actor',actor=r)
 g=items('KT9_Spawn_Pistol',[(SPLASH,6),(MED,1)]);r=items('KT10_Arena_SupplyRemove',[(SPLASH,1),(MED,1)]);tag(r,'kt_spawn_supply_remove_tag');tag(g,'kt_spawn_supplies_tag')
 a=items('KT10_Arena_Supplies',[(SPLASH,6),(MED,1)]);m.tool(b.OBJ,'list_properties',instance=a);m.tool(b.OBJ,'set_properties',instance=a,values=json.dumps({'grant':'All Items','grantCondition':'Always'}));m.tool(b.SCENE,'save_actor',actor=a)
 check={'refPath':by['KT10_Arena_SupplyCheck']};m.tool(b.OBJ,'list_properties',instance=check);m.tool(b.OBJ,'set_properties',instance=check,values=json.dumps({'keyItemsRequired':6}));m.tool(b.SCENE,'save_actor',actor=check)
 bindings=m.tool(b.DEVICE,'ListEventBindings',devicePath=g)
 for binding in bindings:
  tag(binding['sourceDevicePath'],'kt_default_spawn_tag');m.tool(b.DEVICE,'RemoveEventBinding',**binding)
 # Repeatability: retain the main spawner tag after the old event is removed.
 for actor in actors:
  if actor['label']=='Player Spawner':tag({'refPath':actor['actorPath']},'kt_default_spawn_tag')
 label='KT12_Spawn_Supply_Service';svc={'refPath':by[label]} if label in by else m.tool(b.DEVICE,'PlaceDevice',assetPath={'refPath':b.MODULE+'/_Verse.KeystrokeTrainer-kt_spawn_supply_service'},transform=b.xform(0,-59648,-1000))
 m.tool(b.ACTOR,'set_label',actor=svc,label=label);m.tool(b.SCENE,'save_actor',actor=svc)
 print('Verified spawn and arena lists: 6 Slap Splashes + 1 Medkit. Ordered replenishment installed.',flush=True)
if __name__=='__main__':main()
