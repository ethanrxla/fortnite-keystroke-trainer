"""Audit all teleporters; --apply repairs known routing without rebuilding actors."""
import argparse
import datetime
import json
import re
from pathlib import Path
import build_map as b

KEYS = ['enabledDuringPhase', 'knob_TeleporterGroup', 'knob_TargetTeleporterGroup',
        'teleporter Rift Visible', 'selected Team', 'selected Class', 'change Teleporter Target',
        'maintain Relative Position', 'conserve Momentum']

def decoded(value):
    return json.loads(value) if isinstance(value, str) else value

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--apply', action='store_true'); args = ap.parse_args()
    m = b.Mcp()
    if m.tool(b.SCENE, 'get_current_level') != b.MODULE + '/KeystrokeTrainer':
        raise RuntimeError('Wrong level')
    actors = m.tool(b.SCENE, 'find_actors', collision_channels=[])
    if any(a['label'] == 'KT5_RiftRouter' for a in actors):
        print('Explicit routing is installed. Use tools/install_rift_router.py to repair its endpoints; legacy group repair skipped.')
        return
    names = {a['actorPath']: a['label'] for a in actors}
    records = []
    for a in actors:
        if 'Teleporter' not in a['class']['refPath']: continue
        ref = {'refPath': a['actorPath']}
        m.tool(b.OBJ, 'list_properties', instance=ref)
        records.append(dict(label=a['label'], ref=ref,
            props=decoded(m.tool(b.OBJ, 'get_properties', instance=ref, properties=KEYS)),
            bindings=m.tool(b.DEVICE, 'ListEventBindings', devicePath=ref)))
    folder = Path(__file__).resolve().parent.parent / 'backups' / ('rifts-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True); (folder/'before.json').write_text(json.dumps(records, indent=2))
    changes=[]
    for r in records:
        p=r['props']; target=p['knob_TargetTeleporterGroup']; label=r['label']; patch={}
        if not label.startswith('KT'): continue
        destinations=[x['label'] for x in records if x['props']['knob_TeleporterGroup']==target] if target!='Group_None' else []
        print(label, '->', destinations or 'receive only', 'phase='+p['enabledDuringPhase'])
        if target!='Group_None' and len(destinations)!=1:
            raise RuntimeError(f'{label}: expected one destination, found {destinations}; no repairs applied')
        if label=='KT_Portal_Scenario': patch={'enabledDuringPhase':'Always','teleporter Rift Visible':True}
        if target!='Group_None':
            patch.update({'change Teleporter Target':'On Entry', 'maintain Relative Position':False, 'conserve Momentum':False})
        # Receive-only endpoints are not usable entrances. Stop advertising them as rifts.
        if target=='Group_None' or re.fullmatch(r'KT3_0[3-6]_Src',label): patch['teleporter Rift Visible']=False
        patch={k:v for k,v in patch.items() if p[k]!=v}
        bindings=[]
        for link in r['bindings']:
            source=names.get(link['sourceDevicePath']['refPath'],'')
            if re.fullmatch(r'KT3_0[1-8]_Button',source) and target!='Group_None' and link['targetFunction']=='Teleport':
                bindings.append(link)
        if patch or bindings: changes.append(dict(record=r,patch=patch,bindings=bindings))
    (folder/'plan.json').write_text(json.dumps(changes,indent=2))
    if not args.apply: print('Audit saved:',folder); return
    for c in changes:
        r=c['record']; ref=r['ref']
        if c['patch']:
            m.tool(b.OBJ,'set_properties',instance=ref,values=json.dumps(c['patch']))
            got=decoded(m.tool(b.OBJ,'get_properties',instance=ref,properties=list(c['patch'])))
            assert all(got[k]==v for k,v in c['patch'].items()),(r['label'],got)
        for link in c['bindings']:
            replacement={**link,'targetFunction':'Activate'}
            options=m.tool(b.DEVICE,'GetBindingOptions',devicePath=ref)
            assert 'Activate' in options['targetFunctions'],options
            m.tool(b.DEVICE,'AddEventBinding',**replacement)
            m.tool(b.DEVICE,'RemoveEventBinding',**link)
            links=m.tool(b.DEVICE,'ListEventBindings',devicePath=ref)
            assert replacement in links and link not in links,links
        m.tool(b.SCENE,'save_actor',actor=ref)
        print('Repaired and verified',r['label'])
    print('Saved repair journal:',folder)

if __name__=='__main__': main()
