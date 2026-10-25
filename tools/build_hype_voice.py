"""The corny hype lines in the island (shared/hype-cues.json; HypeVoice.verse plays them). Three steps:

    1. python tools/render_arena_voice.py --set hype --render     # ElevenLabs, offline (assets/voice/hype/*.wav)
    2. In UEFN: Tools > Execute Python Script > this file          # imports the WAVs (the MCP cannot import audio)
    3. python tools/build_hype_voice.py                            # places and tags one Audio Player per line, binds it

Step 3 places KT45_Hype_<id> Audio Players (Instigator Only, not spatialized, out of sight under the hub) tagged with
their event's kt_hype_<event>_tag, and points each at its imported sound. A rerun replaces only KT45_Hype_* actors.
"""
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\ethan\OneDrive\Documents\Fortnite\KeystrokeTrainer')
SOURCE = ROOT / 'assets/voice/hype'
DEST = '/1f1b8d9c-3e3a-4bb9-b226-03d38d86582e/KT_Audio/Hype'
PREFIX = 'KT45_Hype_'
BASE = (0.0, -60000.0, -2500.0)       # under the hub, out of sight; the sound is not spatialized


def cues():
    return json.loads((ROOT / 'shared/hype-cues.json').read_text(encoding='utf-8'))['cues']


def import_assets():
    import unreal
    tasks = []
    for cue in cues():
        path = SOURCE / (cue['id'] + '.wav')
        if not path.is_file():
            raise RuntimeError('Missing rendered hype line: ' + cue['id'])
        task = unreal.AssetImportTask()
        task.filename = str(path)
        task.destination_path = DEST
        task.destination_name = cue['id']
        task.automated = True
        task.replace_existing = True
        task.save = True
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    mapping = {}
    for cue, task in zip(cues(), tasks):
        paths = task.imported_object_paths
        if len(paths) != 1 or not isinstance(unreal.load_asset(paths[0]), unreal.SoundWave):
            raise RuntimeError('Failed SoundWave import: ' + cue['id'])
        mapping[cue['id']] = paths[0]
    (SOURCE / 'uefn_assets.json').write_text(json.dumps(mapping, indent=2), encoding='utf-8')
    print(f'Imported {len(mapping)} hype lines to {DEST}. Now run: python tools/build_hype_voice.py')


def place():
    sys.path.insert(0, str(ROOT / 'tools'))
    import build_map as bm
    from build_upgrades import AUDIO
    mapping_path = SOURCE / 'uefn_assets.json'
    if not mapping_path.is_file():
        raise SystemExit('Import the WAVs first: in UEFN, Tools > Execute Python Script > tools/build_hype_voice.py')
    mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
    b = bm.Builder()
    m = b.m
    for a in m.tool(bm.SCENE, 'find_actors', name=PREFIX, collision_channels=[]) or []:
        m.tool(bm.SCENE, 'remove_from_scene', actor={'refPath': a['actorPath']})
    for n, cue in enumerate(cues()):
        asset = mapping.get(cue['id'])
        if not asset or not m.tool('editor_toolset.toolsets.asset.AssetTools', 'exists', path=asset.split('.')[0]):
            raise SystemExit('Imported sound missing for ' + cue['id'])
        x, y, z = BASE
        d = b.device(AUDIO, PREFIX + cue['id'], x + (n % 5) * 300.0, y + (n // 5) * 300.0, z)
        b.props(d, {'audio': {'refPath': asset}, 'can Be Heard By': 'Instigator Only', 'enable Spatialization': False,
                    'enable Volume Attenuation': False, 'volume': 0.7})
        b.tag(d, f"kt_hype_{cue['event']}_tag")
        m.tool(bm.SCENE, 'save_actor', actor={'refPath': d})
        print('placed', PREFIX + cue['id'], '->', cue['event'])
    print(f'placed {len(cues())} hype voice devices')


if __name__ == '__main__':
    try:
        import unreal  # noqa: F401
    except ImportError:
        place()
    else:
        import_assets()
