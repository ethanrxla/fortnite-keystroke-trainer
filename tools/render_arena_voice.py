"""Offline cached arena banter. Dry run unless --render; never runs in gameplay."""
import argparse
import hashlib
import json
import wave
from pathlib import Path
import gen_voice as voice

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/voice/arena'


def signature(text, selection):
    return hashlib.sha256(json.dumps({
        'text': text, 'voice': selection['voice_id'], 'model': selection['model'],
        'settings': selection['settings'], 'format': 'pcm_22050',
    }, sort_keys=True).encode()).hexdigest()


def verify(path):
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 22050):
            raise ValueError('Expected mono 16-bit 22050Hz WAV')
        duration = wav.getnframes() / wav.getframerate()
        if not 0 < duration <= 12:
            raise ValueError('Arena cue must be shorter than twelve seconds')
        return duration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    selection = json.loads((ROOT / 'assets/voice/voice_selection.json').read_text())
    cues = json.loads((ROOT / 'shared/arena-cues.json').read_text())['cues']
    manifest_path = OUT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    stale = [cue for cue in cues if manifest.get(cue['id'], {}).get('render_sha') != signature(cue['text'], selection)
             or not (OUT / (cue['id'] + '.wav')).exists()]
    print(f"{len(cues)} cues, {len(stale)} need rendering, {sum(len(c['text']) for c in stale)} characters")
    if not args.render:
        return 0
    key = voice.api_key()
    if stale and not key:
        print('ElevenLabs key unavailable; no request sent')
        return 2
    voice.MODEL, voice.SETTINGS = selection['model'], selection['settings']
    OUT.mkdir(parents=True, exist_ok=True)
    for cue in stale:
        try:
            data = voice.render(cue['text'], selection['voice_id'], key)
        except Exception as error:
            print('Arena cue rendering failed:', type(error).__name__, getattr(error, 'code', ''))
            return 3
        path = OUT / (cue['id'] + '.wav')
        path.write_bytes(data)
        duration = verify(path)
        manifest[cue['id']] = dict(cue, render_sha=signature(cue['text'], selection),
                                 voice=selection['voice_id'], model=selection['model'],
                                 settings=selection['settings'], duration_seconds=duration)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(cue['id'], f'{duration:.2f}s', 'verified')
    for cue in cues:
        verify(OUT / (cue['id'] + '.wav'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
