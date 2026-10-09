"""Bind imported ElevenLabs WAVs to the arena audio devices. Dry run by default.

Import assets/voice/*.wav into the project's KT_Audio folder first. Only existing
SoundWave assets are bound; missing audio never replaces a working assignment.
"""
import argparse
import json
import build_upgrades as u

CUES = {
    'arena_three': 'kt3_arena_three_tag',
    'arena_two': 'kt3_arena_two_tag',
    'arena_one': 'kt3_arena_one_tag',
    'arena_go': 'kt3_arena_go_tag',
    'arena_ready': 'kt3_arena_ready_tag',
    'arena_reset': 'kt3_arena_reset_voice_tag',
    'arena_melee': 'kt3_arena_melee_voice_tag',
    'arena_standard': 'kt3_arena_standard_voice_tag',
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    builder = u.Upgrade()
    manifest_path = u.ROOT / 'assets/voice/manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    mapping_path = u.ROOT / 'assets/voice/uefn_assets.json'
    imported = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    missing = []
    for cue, tag in CUES.items():
        asset = imported.get(cue, u.bm.MODULE + '/KT_Audio/' + cue + '.' + cue)
        if cue not in manifest or not builder.m.tool(u.AS, 'exists', path=asset):
            missing.append(cue)
            continue
        print(cue, 'ready')
        if args.apply:
            builder.device(u.AUDIO, 'Voice_' + cue, u.bm.xform(-31744, -76800, -220), {
                'audio': {'refPath': asset}, 'can Be Heard By': 'Instigator Only',
                'enable Spatialization': False, 'enable Volume Attenuation': False, 'volume': .8,
            }, tag)
    if args.apply:
        print('Saved', builder.m.tool(u.AS, 'save_assets', asset_paths=[]))
    if missing:
        print('Missing rendered/imported cues:', ', '.join(missing))
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
