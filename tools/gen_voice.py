"""Render the map's spoken lines from shared/drills.json with ElevenLabs text-to-speech.

A published UEFN island cannot call a TTS service, so voice is rendered once, offline, then imported
into UEFN as audio assets and played by an audio player device (one per lane, keyed by drill id).
The text is the same text the map shows, so the voice and the signs can never disagree.

    python tools/gen_voice.py                       # dry run: list lines and character counts, spend nothing
    python tools/gen_voice.py --render --voice <voice_id>    # needs ELEVENLABS_API_KEY in the environment

Lines per drill: <id>_brief (name, principle rule, why) and <id>_reflect (the question after a set).
Lines per principle: principle_<id> (name, rule, why, creative latitude).
Output: assets/voice/<line>.wav and assets/voice/manifest.json. The cache includes text, voice,
model, settings and format, so changing the voice cannot silently reuse an old recording.

The API key is read from the process or Windows user environment and never copied into the project.
Audio is requested as mono signed 16-bit PCM at 22.05 kHz and wrapped in a standard WAV container.
"""

import argparse
import hashlib
import json
import os
import pathlib
import sys
import urllib.request
import urllib.error
import io
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "shared" / "drills.json"
OUT = ROOT / "assets" / "voice"
def dotenv(name):
    """A non-secret setting from the process environment or the workspace .env (one folder above the repo)."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = ROOT.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == name:
                return value.split(" #", 1)[0].strip().strip("'\"")
    return ""


MODEL = dotenv("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True}


def api_key():
    """Read process, Windows user environment, or workspace .env without logging the secret."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as env:
                key = winreg.QueryValueEx(env, "ELEVENLABS_API_KEY")[0]
        except (OSError, FileNotFoundError):
            pass
    env_file = ROOT.parent / ".env"
    if not key and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            entry = line.strip()
            if entry.startswith("export "):
                entry = entry[7:].lstrip()
            name, sep, value = entry.partition("=")
            if sep and name.strip() == "ELEVENLABS_API_KEY":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                key = value
                if key:
                    break
    return key


def lines(data):
    for name, text in data.get("audio_cues", {}).items():
        yield name, text
    principles = {p["id"]: p for p in data.get("principles", [])}
    for p in data.get("principles", []):
        yield f"principle_{p['id']}", f"{p['name']}. {p['rule']} {p['why']} {p['creative']}"
    for d in data["drills"]:
        p = principles.get(d.get("principle", ""))
        rule = f"{p['name']}. {p['rule']} " if p else ""
        yield f"{d['id']}_brief", f"{d['name']}. {rule}Why: {d.get('why', '')}"
        if d.get("reflect"):
            yield f"{d['id']}_reflect", d["reflect"]


def render(text, voice, key):
    body = json.dumps({"text": text, "model_id": MODEL, "voice_settings": SETTINGS}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_22050", body,
        {"xi-api-key": key, "content-type": "application/json", "accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        pcm = resp.read()
    if not pcm or len(pcm) % 2:
        raise ValueError("Invalid PCM response")
    result = io.BytesIO()
    with wave.open(result, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(pcm)
    return result.getvalue()


def available_voices(key):
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("voices", [])


def select_female_narrator(voices):
    """Choose an available adult female voice with warm/confident/sultry cues when labelled."""
    candidates = []
    for voice in voices:
        labels = {str(k).lower(): str(v).lower() for k, v in (voice.get("labels") or {}).items()}
        gender = labels.get("gender", "")
        age = labels.get("age", "")
        if gender != "female" or any(term in age for term in ("child", "teen", "young child")):
            continue
        profile = " ".join([voice.get("name", ""), voice.get("description", ""),
                             voice.get("preview_url", ""), *labels.values()]).lower()
        score = sum(weight for word, weight in {
            "sultry": 8, "seductive": 8, "sensual": 8, "alluring": 6,
            "velvety": 9, "soft intimacy": 8, "warm": 4, "confident": 4,
            "smooth": 3, "expressive": 2,
            "narration": 2, "conversational": 1, "adult": 1,
        }.items() if word in profile)
        candidates.append((score, voice))
    if not candidates:
        raise ValueError("No adult female voice is available in this ElevenLabs account")
    candidates.sort(key=lambda entry: (entry[0], entry[1].get("category") == "premade"), reverse=True)
    return candidates[0][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true", help="actually call ElevenLabs (otherwise dry run)")
    ap.add_argument("--voice", default=dotenv("ELEVENLABS_VOICE_ID") or None, help="ElevenLabs voice id (default ELEVENLABS_VOICE_ID from .env)")
    ap.add_argument("--cues-only", action="store_true", help="render only short gameplay cues")
    ap.add_argument("--list-voices", action="store_true", help="list available voices without rendering")
    ap.add_argument("--render-recommended", action="store_true", help="choose an available adult female narrator and render cues")
    args = ap.parse_args()
    data = json.loads(SRC.read_text(encoding="utf-8"))
    key = api_key()
    if args.render_recommended:
        if not key:
            print("ELEVENLABS_API_KEY is unavailable in process or Windows user environment")
            return 2
        voice = select_female_narrator(available_voices(key))
        args.voice = voice["voice_id"]
        args.render = True
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "voice_selection.json").write_text(json.dumps({
            "voice_id": voice["voice_id"], "name": voice.get("name"),
            "labels": voice.get("labels"), "description": voice.get("description"),
            "model": MODEL, "settings": SETTINGS,
        }, indent=2), encoding="utf-8")
        print(f"Selected available adult female voice: {voice.get('name')} ({args.voice})")
        print(f"Voice labels: {json.dumps(voice.get('labels', {}), ensure_ascii=False)}")
    if args.list_voices:
        if not key:
            print("ELEVENLABS_API_KEY is unavailable in process or Windows user environment")
            return 2
        req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key})
        with urllib.request.urlopen(req, timeout=30) as resp:
            voices = json.load(resp).get("voices", [])
        for voice in voices:
            print(json.dumps({k: voice.get(k) for k in ("voice_id", "name", "labels", "category", "description")}))
        return 0
    todo = list(data.get("audio_cues", {}).items()) if args.cues_only else list(lines(data))
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    def signature(text):
        return hashlib.sha256(json.dumps({"text": text, "voice": args.voice, "model": MODEL,
                                          "settings": SETTINGS, "format": "pcm_22050"}, sort_keys=True).encode()).hexdigest()
    stale = [(n, t) for n, t in todo
             if manifest.get(n, {}).get("render_sha") != signature(t) or not (OUT / f"{n}.wav").exists()]
    chars = sum(len(t) for _, t in stale)
    print(f"{len(todo)} lines, {len(stale)} need rendering, {chars} characters")
    if not args.render:
        for n, t in stale:
            print(f"  {n}: {t[:90]}{'...' if len(t) > 90 else ''}")
        print("dry run: nothing was sent. Add --render --voice <id> to render.")
        return 0
    if not key or not args.voice:
        print("need ELEVENLABS_API_KEY in the environment and --voice <voice_id>")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in stale:
        try:
            audio = render(t, args.voice, key)
        except urllib.error.HTTPError as error:
            print(f"ElevenLabs returned HTTP {error.code} for {n}; no fallback voice used")
            return 3
        (OUT / f"{n}.wav").write_bytes(audio)
        manifest[n] = {"render_sha": signature(t), "text": t, "voice": args.voice, "model": MODEL,
                       "settings": SETTINGS, "format": "pcm_22050", "file": f"{n}.wav"}
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"rendered {n}")
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
