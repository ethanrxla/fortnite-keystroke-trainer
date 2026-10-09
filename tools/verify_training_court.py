"""Read-only verification of the placed court and authored device settings."""
import json
from pathlib import Path
from build_map import Mcp, SCENE, ACTOR, OBJ, DEVICE, MODULE
from build_training_court import plan

ROOT=Path(__file__).resolve().parent.parent

def main():
    m=Mcp();actors=m.tool(SCENE,'find_actors',name='KT2_',collision_channels=[])
    labels=[x['label'] for x in actors];assert len(labels)==len(set(labels)),'duplicate court actor labels'
    found={x['label']:x['actorPath'] for x in actors}
    expected={x['label'] for x in plan()};assert expected<=set(found),'missing planned actors: '+str(expected-set(found))
    def get(label,keys):
        raw=m.tool(OBJ,'get_properties',instance={'refPath':found[label]},properties=keys)
        return json.loads(raw) if isinstance(raw,str) else raw
    floors={
        'KT2_Arrival':(0,1536,-35840,-25600),
        'KT2_Practice':(1536,6144,-35840,-25600),
        'KT2_Crosswalk':(6144,7168,-35840,-25600),
        'KT2_FreeBuild':(7168,12288,-35840,-30720),
        'KT2_Transfer':(7168,12288,-30720,-25600),
    }
    for label,(x0,x1,y0,y1) in floors.items():
        b=m.tool(ACTOR,'get_actor_bounds',actor={'refPath':found[label]})
        assert b['min']['x']==x0 and b['max']['x']==x1 and b['min']['y']==y0 and b['max']['y']==y1 and b['max']['z']==0,label
    outlines=[x for x in actors if x['class']['refPath']=='/Script/FortniteGame.BuildingProp']
    for a in outlines:
        d=get(a['label'],['bNoCollision','bRegisterWithStructuralGrid','bCanBeDamaged','bAllowCustomMaterial'])
        assert d['bNoCollision'] and not d['bRegisterWithStructuralGrid'] and not d['bCanBeDamaged'] and d['bAllowCustomMaterial'],a['label']
    rigs=[x for x in actors if x['label'].startswith('KT2_ResetRig_')];assert len(rigs)==13
    for a in rigs:
        d=get(a['label'],['player Damage','structure Damage','knockback','visible During Game','play Audio / VFX','blast Radius','time Until Reset Allowed'])
        assert d['player Damage']==0 and d['structure Damage']==10000 and d['knockback']=='None' and not d['visible During Game'] and not d['play Audio / VFX'],a['label']
        assert d['blast Radius']==(4.75 if '_free_' in a['label'] else 2.9),a['label']
        assert d['time Until Reset Allowed']==.1,a['label']
    d=get('KT2_CurrentBRMovement',['movementSettingPreset','bAddToPlayersOnStart']);assert d['movementSettingPreset']=='Current BR' and d['bAddToPlayersOnStart']
    raw=m.tool(DEVICE,'GetDeviceProperties',device={'refPath':found['KT2_Guide']},propertyNames=['drillId','enableGuide','releaseDistanceCm'])
    guide=json.loads(raw) if isinstance(raw,str) else raw
    assert guide['drillId']=='wall_ramp_floor' and guide['enableGuide'] and guide['releaseDistanceCm']==2500
    # Native direct bindings are stored on the receiving device/function.
    bindings=m.tool(DEVICE,'ListEventBindings',devicePath={'refPath':found['KT2_PracticeGranter']})
    assert any(b['sourceDevicePath']['refPath']==found['KT2_CourtArrival'] and b['sourceEvent']=='On Teleported' and b['targetFunction']=='GrantItem' for b in bindings),'arrival equipment event not bound'
    texture={'refPath':MODULE+'/KT_Training/T_GhostBuild_Onboarding_v1.T_GhostBuild_Onboarding_v1'}
    raw=m.tool(OBJ,'get_properties',instance=texture,properties=['powerOfTwoMode','neverStream','mipGenSettings']);d=json.loads(raw) if isinstance(raw,str) else raw
    assert d['powerOfTwoMode']=='StretchToPowerOfTwo' and not d['neverStream'] and d['mipGenSettings']!='TMGS_NoMipmaps'
    report={'planned_actors':len(expected),'placed_court_actors':len(actors),'native_outline_props':len(outlines),'reset_devices':len(rigs),'verified':'floor bounds, prop authoring flags, reset damage/radii, movement preset, guide settings, arrival event binding, texture streaming','limits':'Does not verify runtime Show collision, player build placement, actual structure clearing, learning outcomes or multiplayer fairness.'}
    (ROOT/'backups/session-2026-10-07/court-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
