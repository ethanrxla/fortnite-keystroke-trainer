"""Run in UEFN Execute Python Script to import arena WAVs; CLI --bind assigns existing KT10 devices.

Import uses native AssetImportTask, saves only imported assets, and never pushes a session.
Binding fails rather than silently assigning an unrelated or missing audio device.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(r'C:\Users\ethan\OneDrive\Documents\Fortnite\KeystrokeTrainer')
SOURCE = ROOT / 'assets/voice/arena'


def import_assets():
    import unreal
    cues = json.loads((ROOT / 'shared/arena-cues.json').read_text())['cues']
    tasks = []
    for cue in cues:
        path = SOURCE / (cue['id'] + '.wav')
        if not path.is_file():
            raise RuntimeError('Missing rendered arena cue: ' + cue['id'])
        task = unreal.AssetImportTask()
        task.filename = str(path)
        task.destination_path = '/1f1b8d9c-3e3a-4bb9-b226-03d38d86582e/KT_Audio/Arena'
        task.destination_name = cue['id']
        task.automated = True
        task.replace_existing = True
        task.save = True
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    mapping = {}
    for cue, task in zip(cues, tasks):
        paths = task.imported_object_paths
        if len(paths) != 1 or not isinstance(unreal.load_asset(paths[0]), unreal.SoundWave):
            raise RuntimeError('Failed SoundWave import: ' + cue['id'])
        mapping[cue['id']] = paths[0]
        print('Imported arena cue:', cue['id'], paths[0])
    (SOURCE / 'uefn_assets.json').write_text(json.dumps(mapping, indent=2), encoding='utf-8')


def bind_assets():
    import build_map as bm
    cues = json.loads((ROOT / 'shared/arena-cues.json').read_text())['cues']
    mapping = json.loads((SOURCE / 'uefn_assets.json').read_text())
    builder = bm.Builder()
    actors = builder.m.tool(bm.SCENE, 'find_actors', collision_channels=[])
    by_label = {actor['label']: actor['actorPath'] for actor in actors}
    pending = []
    for cue in cues:
        label = 'KT10_Arena_Voice_' + cue['id']
        asset = mapping[cue['id']]
        if label not in by_label or not builder.m.tool('editor_toolset.toolsets.asset.AssetTools', 'exists', path=asset):
            raise RuntimeError('Missing arena device or imported asset: ' + label)
        pending.append((by_label[label], asset, cue['id']))
    for actor, asset, cue_id in pending:
        builder.props(actor, {'audio': {'refPath': asset}, 'can Be Heard By': 'Instigator Only',
                             'enable Spatialization': False, 'enable Volume Attenuation': False, 'volume': .65})
        builder.m.tool(bm.SCENE, 'save_actor', actor={'refPath': actor})
        values = builder.m.tool(bm.DEVICE, 'GetDeviceProperties', device={'refPath': actor})
        print('Bound', cue_id, json.dumps(values))


if __name__ == '__main__':
    try:
        import unreal
    except ImportError:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--bind', action='store_true', required=True)
        parser.parse_args()
        bind_assets()
    else:
        import_assets()
