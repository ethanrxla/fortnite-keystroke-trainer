"""Register finite ammo packs; leave unsupported heal items explicitly unregistered."""
import argparse
import json
import build_map as bm

PREFIX='KT24_Team_'

def apply():
    b=bm.Builder()
    cfg=json.loads((bm.ROOT/'shared/team-supplies.json').read_text())
    existing={a['label']:a['actorPath'] for a in b.m.tool(bm.SCENE,'find_actors',name=PREFIX,collision_channels=[])}
    def device(name,asset,pos,tag,values):
        path=existing.get(PREFIX+name) or b.device(asset,PREFIX+name,*pos)
        schema=b.m.tool(bm.OBJ,'list_properties',instance={'refPath':path})
        schema=json.loads(schema) if isinstance(schema,str) else schema
        accepted={k:v for k,v in values.items() if k in schema}
        if accepted:b.props(path,accepted)
        cs=b.m.tool(bm.ACTOR,'get_components',actor={'refPath':path})
        if not any(c['refPath'].endswith('.KT_Tags') for c in cs):b.tag(path,tag)
        return path
    def items(path,rows):
        ref={'refPath':path}
        for field in ('pickupItemList','itemList'):
            try:
                raw=b.m.tool(bm.OBJ,'get_properties',instance=ref,properties=[field])
                component=(json.loads(raw) if isinstance(raw,str) else raw)[field]
                if isinstance(component,dict) and 'refPath' in component:break
            except (RuntimeError,KeyError):continue
        else:raise RuntimeError('No item-list component on '+path)
        b.m.tool(bm.OBJ,'list_properties',instance=component)
        b.m.tool(bm.OBJ,'reset_properties',instance=component,properties=['itemListData'])
        for row in rows:
            current=b.m.tool(bm.OBJ,'get_properties',instance=component,properties=['itemListData'])
            current=(json.loads(current) if isinstance(current,str) else current)['itemListData']
            b.props(component['refPath'],{'itemListData':current+[{'itemDefinition':{'refPath':row['asset']},'itemQuantity':row['quantity']}]})
        raw=b.m.tool(bm.OBJ,'get_properties',instance=component,properties=['itemListData'])
        actual=(json.loads(raw) if isinstance(raw,str) else raw)['itemListData']
        if [(r['itemDefinition']['refPath'],r['itemQuantity']) for r in actual]!=[(r['asset'],r['quantity']) for r in rows]:
            raise RuntimeError('Ammo registration did not retain quantities')
        b.m.tool(bm.SCENE,'save_actor',actor=ref)
    granter=device('AmmoRespawn',bm.DEV+'PID_Device_ItemGranter.PID_Device_ItemGranter',(75776,-55808,-700),
                  'kt_team_ammo_grant_tag',{'enabledOnGameStart':False,'grant':'All Items','onGrantAction':'Keep All',
                  'bGrantOnGameStart':False,'bGrantOnTimer':False,'bEquipGrantedItem':False,'giveExtraAmmo':False})
    items(granter,cfg['ammo_on_respawn'])
    for i,x in enumerate((73984,77568)):
        path=device('AmmoCache'+str(i),bm.ITEM_SPAWNER,(x,-52736,20),'kt_team_ammo_stock_tag',
                    {'enabledOnGameStart':False,'spawnOnTimer':False,'respawnItemOnTimer':False,
                     'bAllowMultipleItems':False,'continuouslySpawnItems':False})
        items(path,cfg['ammo_on_respawn'])
        # Heal devices are ready for native item registration by the operator.
        # Do not falsely substitute Slap Splash or a cosmetic for Chug/fish.
        path=device('HealCache'+str(i),bm.ITEM_SPAWNER,(x,-52480,20),'kt_team_heal_stock_tag',
                    {'enabledOnGameStart':False,'spawnOnTimer':False,'respawnItemOnTimer':False,
                     'bAllowMultipleItems':False,'continuouslySpawnItems':False})
        b.m.tool(bm.SCENE,'save_actor',actor={'refPath':path})
    print('Registered six finite ammo packs and paired ammo caches. Chug/fish registration and infinite-ammo overrides remain unverified.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.apply:apply()
    else:print('Finite spawn ammo + paired randomized resupply; heal registration pending.')
