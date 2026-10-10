"""Targeted practice-bot setup, preserving existing targets."""
import json
import build_map as b
GUARD=b.GUARD

def decode(v):return json.loads(v) if isinstance(v,str) else v

def main():
 m=b.Mcp();by={a['label']:a['actorPath'] for a in m.tool(b.SCENE,'find_actors',collision_channels=[])}
 def upsert(label,asset,pose,values=None):
  r={'refPath':by[label]} if label in by else m.tool(b.DEVICE,'PlaceDevice',assetPath={'refPath':asset},transform=pose)
  m.tool(b.ACTOR,'set_label',actor=r,label=label);by[label]=r['refPath']
  if values:m.tool(b.OBJ,'list_properties',instance=r);m.tool(b.OBJ,'set_properties',instance=r,values=json.dumps(values))
  m.tool(b.SCENE,'save_actor',actor=r);return r
 def edit(r,values):
  m.tool(b.DEVICE,'ListDeviceProperties',device=r)
  for repeat in range(2):
   for k,v in values.items():m.tool(b.DEVICE,'SetDeviceProperty',device=r,propertyName=k,value=json.dumps(v))
   actual=decode(m.tool(b.DEVICE,'GetDeviceProperties',device=r,propertyNames=list(values)))
   if actual==values:break
  assert actual==values,(actual,values);m.tool(b.SCENE,'save_actor',actor=r)
 guards=[]
 for i,(x,y) in enumerate([(-29952,-87808),(-27904,-87296)]):
  guards.append(upsert('KT12_Aim_Bot_'+str(i),GUARD,b.xform(x,y,0),{'enabledAtGameStart':False,'spawnOnTimer':True,'spawnTimer':3.0,'allowInfiniteSpawn':True,'spawnCount':1,'guardTeamOption':'Team Index','guard Team Index':{'teamType':'TeamIndex','teamIndex':2},'accuracy':'LOW','enablePatrol':False,'useDeviceSpawnLocation':True,'showHealthBar':True}))
 def tag_spawner(r,tag_name='kt_practice_bot_spawner_tag'):
  cs=m.tool(b.ACTOR,'get_components',actor=r);c=next((x for x in cs if x['refPath'].endswith('.KT_PracticeBot')),None)
  if c is None:c=m.tool(b.ACTOR,'add_component',owner=r,component_type={'refPath':'/Script/VerseTags.VerseTagMarkupComponent'},name='KT_PracticeBot')
  m.tool(b.OBJ,'list_properties',instance=c);m.tool(b.OBJ,'set_properties',instance=c,values=json.dumps({'internalTags':{'internalTags':[{'internalTag':{'refPath':b.MODULE+'/_Verse.KeystrokeTrainer-'+tag_name}}]}}));m.tool(b.SCENE,'save_actor',actor=r)
 for r in guards:tag_spawner(r)
 asset=b.MODULE+'/_Verse.KeystrokeTrainer-kt_practice_bot_control_device'
 toggle=upsert('KT12_Aim_Bots_Toggle',b.BUTTON,b.xform(-34000,-86200,120),{'interaction Text':'Practice bots: ON / OFF'})
 tag_spawner(toggle,'kt_practice_bot_toggle_tag')
 controller=upsert('KT12_Aim_Bots_Controller',asset,b.xform(-30720,-87296,-150))
 points=[{'x':float(x),'y':float(y),'z':0.0} for x,y in [(-29952,-88064),(-29184,-87552),(-29184,-86528),(-27904,-87552),(-26880,-87040),(-27648,-86272)]]
 edit(controller,{'centre':{'x':-29696.0,'y':-87296.0,'z':0.0},'halfExtent':{'x':6144.0,'y':3328.0,'z':3000.0},'defaultEnabled':True,'waypoints':points})
 old=[{'refPath':by['KT4_Arena_Bot_'+str(i)]} for i in range(2)]
 for r in old:tag_spawner(r);m.tool(b.OBJ,'list_properties',instance=r);m.tool(b.OBJ,'set_properties',instance=r,values=json.dumps({'enabledAtGameStart':False,'spawnOnTimer':False}));m.tool(b.SCENE,'save_actor',actor=r)
 toggle=upsert('KT12_Arena_Bots_Toggle',b.BUTTON,b.xform(-32400,-76800,120,yaw=90),{'interaction Text':'1v1 practice bots: OFF / ON'})
 tag_spawner(toggle,'kt_practice_bot_toggle_tag')
 controller=upsert('KT12_Arena_Bots_Controller',asset,b.xform(-30720,-76800,-150))
 edit(controller,{'centre':{'x':-30720.0,'y':-76800.0,'z':0.0},'halfExtent':{'x':5120.0,'y':3072.0,'z':3000.0},'defaultEnabled':False,'waypoints':[]})
 components=m.tool(b.ACTOR,'get_components',actor=controller);tag=next((x for x in components if x['refPath'].endswith('.KT_ArenaBotControl')),None)
 if tag is None:tag=m.tool(b.ACTOR,'add_component',owner=controller,component_type={'refPath':'/Script/VerseTags.VerseTagMarkupComponent'},name='KT_ArenaBotControl')
 m.tool(b.OBJ,'list_properties',instance=tag);m.tool(b.OBJ,'set_properties',instance=tag,values=json.dumps({'internalTags':{'internalTags':[{'internalTag':{'refPath':b.MODULE+'/_Verse.KeystrokeTrainer-kt_arena_bot_control_tag'}}]}}));m.tool(b.SCENE,'save_actor',actor=controller)
 print('Practice bots configured; arena bots default OFF; controls read back.',flush=True)
if __name__=='__main__':main()
