"""Remove item references explicitly rejected by UEFN's latest validation.

Asset-registry presence does not imply Creative availability. This tool uses the
editor's own rejection evidence, records the original item lists, and never
substitutes or unlocks unsupported assets. Default is read-only; --apply saves.
"""
import argparse
import json
import os
import re
from pathlib import Path
from build_map import Mcp, SCENE, OBJ

ROOT=Path(__file__).resolve().parent.parent
ASSET='editor_toolset.toolsets.asset.AssetTools'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    log=Path(os.environ['LOCALAPPDATA'])/'UnrealEditorFortnite/Saved/Logs/UnrealEditorFortnite.log'
    text=log.read_text(encoding='utf-8',errors='replace')
    section=text[text.rfind('Starting basic user validation'):]
    rejected=sorted(set(re.findall(r'Disallowed reference to (\S+),',section)))
    if not rejected:raise RuntimeError('Latest validation has no explicit rejected item paths')
    print('rejected references',len(rejected))
    excludes=ROOT/'shared/asset-exclusions.json'
    old=json.loads(excludes.read_text()) if excludes.exists() else {}
    paths=sorted(set(old.get('rejected_item_paths',[]))|set(rejected))
    excludes.write_text(json.dumps({'reason':'Explicitly rejected by current local UEFN session validation on 2026-10-07; registry presence is not Creative permission.','rejected_item_paths':paths},indent=2))
    m=Mcp();changes=[]
    for actor in m.tool(SCENE,'find_actors',name='KT_Gun_',collision_channels=[]):
        if actor['label'].endswith(('_PREV','_GIVE','_NEXT')):continue
        ref={'refPath':actor['actorPath']}
        raw=m.tool(OBJ,'get_properties',instance=ref,properties=['pickupItemList'])
        obj=json.loads(raw) if isinstance(raw,str) else raw
        items=obj.get('pickupItemList')
        if not items:continue
        raw=m.tool(OBJ,'get_properties',instance=items,properties=['itemListData'])
        data=(json.loads(raw) if isinstance(raw,str) else raw)['itemListData']
        allowed=[x for x in data if x.get('itemDefinition',{}).get('refPath') not in paths]
        if len(allowed)==len(data):continue
        change={'label':actor['label'],'path':actor['actorPath'],'item_list':items,'before':data,'after':allowed}
        changes.append(change);print(actor['label'],len(data),'->',len(allowed))
        backup=ROOT/'backups/session-2026-10-07/loadout-rejections-before.json'
        if not backup.exists():backup.write_text(json.dumps(changes,indent=2))
        if args.apply:
            m.tool(OBJ,'reset_properties',instance=items,properties=['itemListData'])
            m.tool(OBJ,'set_properties',instance=items,values=json.dumps({'itemListData':allowed}))
            raw=m.tool(OBJ,'get_properties',instance=items,properties=['itemListData'])
            actual=(json.loads(raw) if isinstance(raw,str) else raw)['itemListData']
            if any(x.get('itemDefinition',{}).get('refPath') in paths for x in actual):
                raise RuntimeError('Rejected references remain after filtering '+actor['label'])
            m.tool(SCENE,'save_actor',actor=ref)
    out=ROOT/'backups/session-2026-10-07/loadout-rejections-journal.json'
    out.write_text(json.dumps(changes,indent=2))
    if args.apply:print('saved',m.tool(ASSET,'save_assets',asset_paths=[]))

if __name__=='__main__':main()
