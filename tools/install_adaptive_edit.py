"""Deploy adaptive edit source and compile; --configure updates the practice areas.
No unrelated devices or geometry are rebuilt. Native numbered HUD needs no raster import.
Configuration enables four coaches, adds a free-build coach and hides the fixed marks.
"""
import datetime
import argparse
import json
from pathlib import Path
import build_map as b
from build_training_court import Y0

ROOT=Path(__file__).resolve().parent.parent
VERSE='ValkyrieToolset.VerseToolset'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--configure',action='store_true',help='Configure coaches after a successful compile')
    args=ap.parse_args()
    m=b.Mcp()
    if m.tool(b.SCENE,'get_current_level')!=b.MODULE+'/KeystrokeTrainer': raise RuntimeError('Wrong level')
    backup=ROOT/'backups'/('adaptive-edit-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    for name in ['DrillCatalog.verse','CrosshairCoach.verse','AutoTest.verse','AutoTestDevice.verse','Tags.verse','RiftRoutes.verse','RiftRouter.verse']:
        path=b.MODULE+'/KeystrokeTrainer/'+name
        (backup/(name+'.json')).write_text(json.dumps(m.tool(VERSE,'ReadFile',path=path)))
        print('Write',name,m.tool(VERSE,'WriteFile',path=path,content=(ROOT/'verse/KeystrokeTrainer'/name).read_text(encoding='utf-8-sig'),bCreateIfMissing=True),flush=True)
    result=m.tool(VERSE,'BuildAll')
    (backup/'compile.json').write_text(json.dumps(result,indent=2))
    print('BUILD',result,flush=True)
    if not isinstance(result,list) or any(d.get('severity')=='Error' for d in result):
        raise RuntimeError('Compilation failed or returned an unrecognized result')
    if not args.configure:return
    actors=m.tool(b.SCENE,'find_actors',name='KT',collision_channels=[])
    by={a['label']:a['actorPath'] for a in actors}
    journal=[]
    def record(entry):
        journal.append(entry);(backup/'configuration.json').write_text(json.dumps(journal,indent=2))
    def settings(label,values):
        ref={'refPath':by[label]}
        m.tool(b.DEVICE,'ListDeviceProperties',device=ref)
        record(dict(label=label,path=ref['refPath'],before=m.tool(b.DEVICE,'GetDeviceProperties',device=ref,propertyNames=list(values)),after=values))
        for key,value in values.items():
            m.tool(b.DEVICE,'SetDeviceProperty',device=ref,propertyName=key,value=json.dumps(value))
        actual=m.tool(b.DEVICE,'GetDeviceProperties',device=ref,propertyNames=list(values))
        actual=json.loads(actual) if isinstance(actual,str) else actual
        assert all(actual[k]==v for k,v in values.items()),(label,actual)
        m.tool(b.SCENE,'save_actor',actor=ref)
        print('Configured',label,flush=True)
    for code in ['E2','E4','E5','E7']:
        settings('KT4_Coach_'+code,dict(adaptiveRoutes=True,freeBuildGrid=False,tilePixels=48.0,sampleSeconds=0.05))
        settings('KT_Lane_'+code,dict(showEditPanel=False))
    label='KT5_EditCoach_FreeBuild'
    if label not in by:
        asset=b.MODULE+'/_Verse.KeystrokeTrainer-kt_crosshair_coach_device'
        ref=m.tool(b.DEVICE,'PlaceDevice',assetPath={'refPath':asset},transform=b.xform(14*b.CELL,Y0,0))
        by[label]=ref['refPath']
        m.tool(b.ACTOR,'set_label',actor=ref,label=label)
        record(dict(created=label,path=ref['refPath']))
    settings(label,dict(drillId='edit_window',freeBuildGrid=True,adaptiveRoutes=True,gridCellsX=10,gridCellsY=10,gridLevels=4,tilePixels=48.0,sampleSeconds=0.05))
    for a in actors:
        if not a['label'].startswith('KT4_Guide_'):continue
        ref={'refPath':a['actorPath']}
        m.tool(b.OBJ,'list_properties',instance=ref)
        record(dict(label=a['label'],path=a['actorPath'],before=m.tool(b.OBJ,'get_properties',instance=ref,properties=['bHidden']),after={'bHidden':True}))
        m.tool(b.OBJ,'set_properties',instance=ref,values=json.dumps({'bHidden':True}))
        m.tool(b.SCENE,'save_actor',actor=ref)
    print('Configured coaches and hid conflicting fixed markers. Journal:',backup,flush=True)

if __name__=='__main__': main()
