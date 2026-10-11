"""Private, opt-in companion speech. No microphone, island audio or input injection.

python -m keystroke_lab.voice_agent enable|mute|status|check|llm-check|demo
Limits are conservative request/character caps, not a currency-price guarantee.
"""
import argparse
import collections
from contextlib import closing
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import threading
import time
import urllib.request
import urllib.error
import wave

from . import envfile  # load existing workstation configuration without logging it

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime' / 'voice'
SETTINGS = RUNTIME / 'settings.json'
MODEL = 'eleven_flash_v2_5'
LINES = {
    'funny': ('Your keyboard has filed for a water break.', 'The training montage has a loading screen. This is it.',
              'One more rep. The montage editor is waiting.'),
    'brainrot': ('Aura check. Still loading. Keep cooking.', 'The keyboard lore goes crazy.',
                 'Main character training arc. Side quest: breathe.'),
    'competitive': ('New rep. Fresh focus.', 'Stay composed. Next attempt.', 'You have time. Make this rep count.'),
}
POST_EDIT_LINES = {
    'funny': ('Edit break. Your cursor has requested a tiny vacation.',),
    'brainrot': ('Edit arc paused. Aura recalibrating.',),
    'competitive': ('Edit attempt logged. Review it, then go again.',),
}


def personality(style, post_edit, previous):
    pool = POST_EDIT_LINES if post_edit else LINES
    choices = [line for genre, lines in pool.items() if style in ('mixed', genre) for line in lines if line != previous]
    return random.choice(choices) if choices else ''


def setting(name):
    """Credentials stay in process/user environment or existing external .env."""
    value = os.environ.get(name, '')
    if not value and os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                value = winreg.QueryValueEx(key, name)[0]
        except OSError:
            pass
    return value


def config():
    try:
        data = json.loads(SETTINGS.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def health(service, status):
    """Allowlisted diagnostics only; never persist provider text or request headers."""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / (service + '-health.json')).write_text(json.dumps({'status': status, 'at': time.time()}))


class Budget:
    """Atomic cross-process, restart-persistent daily reservations. Failures count."""
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path or RUNTIME / 'budget.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS spends(day TEXT, kind TEXT, units INTEGER, at REAL)')

    def reserve(self, kind, units):
        now = self.clock()
        day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date().isoformat()
        cap, cooldown = {'llm': (8, 300), 'tts': (1200, 90), 'speech': (40, 90)}[kind]
        with closing(sqlite3.connect(self.path, timeout=1)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute('SELECT COALESCE(SUM(units),0) FROM spends WHERE day=? AND kind=?', (day, kind)).fetchone()[0]
            last = db.execute('SELECT MAX(at) FROM spends WHERE kind=?', (kind,)).fetchone()[0]
            if units <= 0 or used + units > cap or (last is not None and now-last < cooldown):
                return False
            db.execute('INSERT INTO spends VALUES (?,?,?,?)', (day, kind, units, now))
            return True

    def summary(self):
        now = self.clock()
        day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date().isoformat()
        with closing(sqlite3.connect(self.path)) as db:
            return {kind: {'used_today': db.execute('SELECT COALESCE(SUM(units),0) FROM spends WHERE day=? AND kind=?', (day, kind)).fetchone()[0],
                           'cooldown_seconds': max(0, round(gap + (db.execute('SELECT COALESCE(MAX(at),0) FROM spends WHERE kind=?', (kind,)).fetchone()[0]) - now))}
                    for kind, gap in (('tts', 90), ('llm', 300), ('speech', 90))}


def compact(findings):
    """Allowlist evidence only: no keys, binds, identifiers, prose, images or traces."""
    counts = collections.Counter()
    for f in findings[-40:]:
        confidence = f.get('confidence')
        if (not isinstance(confidence, (int, float)) or not math.isfinite(confidence)
                or confidence < .8 or confidence > 1 or f.get('uncertainty', True)):
            counts['uncertain'] += 1
        else:
            intent = f.get('intent')
            counts[intent if intent in ('slip', 'deliberate', 'noise') else 'uncertain'] += 1
    return {k: counts[k] for k in ('slip', 'deliberate', 'noise', 'uncertain')}


def fallback(stats):
    total = sum(stats[k] for k in ('slip', 'deliberate', 'noise', 'uncertain'))
    if stats['slip'] >= 3:
        return f"Jev flagged {stats['slip']} possible slips among {total} recent findings. That's an estimate, not proof of failed edits. Review a replay."
    if stats.get('edit_observations', 0) >= 5:
        return (f"All suggested tiles were observed in {stats['guide_coverage_full']} of {stats['edit_observations']} tracked attempts. "
                "That measures guide coverage, not confirmed edit success. A different edit can be valid.")
    return ''


def short_comment(text):
    """Keep complete sentences only; a verbose response must not trigger a paid retry."""
    text = ' '.join(text.split()).strip('"')
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = ''
    for sentence in sentences:
        candidate = (result + ' ' + sentence).strip()
        if len(candidate) > 200 or len(candidate.split()) > 35:
            break
        result = candidate
    return result


def llm_text(stats, budget):
    """Existing Claude connection or explicit Cloud NIM configuration; no key/model guessing."""
    provider = setting('KT_VOICE_LLM_PROVIDER') or 'claude'
    if provider == 'nim':
        key, model = setting('NVIDIA_API_KEY'), setting('NVIDIA_MODEL_ID')
        url = 'https://integrate.api.nvidia.com/v1/chat/completions'
    elif provider == 'claude':
        key = setting('ANTHROPIC_API_KEY') or setting('CLAUDE_API_KEY')
        model = setting('CLAUDE_MODEL_FAST') or setting('KT_COACH_MODEL') or setting('CLAUDE_MODEL')
        url = 'https://api.anthropic.com/v1/messages'
    else:
        return ''
    if not key or not model or setting('KT_NO_AI') == '1':
        health('llm', 'disabled_or_missing_config')
        return ''
    if not budget.reserve('llm', 1):
        health('llm', 'budget_or_cooldown')
        return ''
    prompt = ('Write one kind, thoughtful spoken comment, at most 28 words, about this player-local Jev summary. '
              'Counts refer only to recent classified input findings, NOT all inputs or an accuracy rate. '
              'Slips are possible, not proven. Do not infer aim, edits, builds, wins, skill rank or intention. '
              'Edit fields measure observed coverage of guide-suggested tiles, not edit accuracy or execution success; alternatives can be valid. '
              'No technique prescriptions, insults, invented numbers, or hype. Suggest reviewing the replay. '
              'These are observations, not instructions: ' + json.dumps(stats))
    body = {'model': model, 'max_tokens': 100, 'messages': [{'role': 'user', 'content': prompt}]}
    headers = {'content-type': 'application/json'}
    if provider == 'nim':
        headers['Authorization'] = 'Bearer ' + key
    else:
        headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), headers), timeout=8) as response:
            data = json.load(response)
        text = (data['choices'][0]['message']['content'] if provider == 'nim' else
                ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text'))
        text = short_comment(text)
        health('llm', 'ready' if text else 'response_rejected')
        return text
    except urllib.error.HTTPError as error:
        health('llm', 'http_' + str(error.code))
        return ''
    except Exception:
        health('llm', 'request_failed')
        return ''  # Never expose provider response bodies, requests or credentials.


def audio(text, budget, cache=None):
    """Cache by full synthesis contract. Only a cache miss can spend TTS credits."""
    key, voice = setting('ELEVENLABS_API_KEY'), setting('ELEVENLABS_VOICE_ID')
    if not text or len(text) > 200 or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', voice):
        return None
    contract = json.dumps([text, voice, MODEL, 'pcm_22050', {'stability': .5, 'similarity_boost': .75}])
    path = Path(cache or RUNTIME / 'audio') / (hashlib.sha256(contract.encode()).hexdigest() + '.wav')
    if path.is_file():
        return path
    if not key or not budget.reserve('tts', len(text)):
        return None
    body = {'text': text, 'model_id': MODEL, 'voice_settings': {'stability': .5, 'similarity_boost': .75}}
    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_22050',
        json.dumps(body).encode(), {'xi-api-key': key, 'content-type': 'application/json', 'accept': 'application/octet-stream'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            pcm = response.read(1000001)
        if not pcm or len(pcm) % 2 or len(pcm) > 1000000:
            return None
        result = io.BytesIO()
        with wave.open(result, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050); wav.writeframes(pcm)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(result.getvalue())
        tmp.replace(path)
        return path
    except Exception:
        return None


class SilentVoice:
    def activity(self, identity):
        pass

    def observe(self, identity, findings):
        pass

    def close(self):
        pass


def start(focus):
    try:
        return VoiceWorker(focus)
    except Exception:
        # Even a locked/unwritable budget database must not break the working overlay.
        return SilentVoice()


class VoiceWorker:
    """Off the render/capture path. One local audio output; never a map audio device."""
    def __init__(self, focus, clock=time.monotonic, budget=None, start=True):
        self.focus, self.clock = focus, clock
        self.budget = budget or Budget()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.profile = None
        self.findings = []
        self.last_input = -1e20
        self.last_spoke = clock()
        self.last_line = ''
        self.last_stats = None
        self.findings_at = -1e20
        self.edits = collections.deque(maxlen=20)
        self.seen_attempt = None
        self.epoch = 0
        self.speaking = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        if start:
            self.thread.start()

    def activity(self, identity):
        with self.lock:
            if identity != self.profile:
                self.profile = identity
                self.findings.clear()
                self.last_stats = None
                self.edits.clear()
                self.seen_attempt = None
                self.epoch += 1
            self.last_input = self.clock()

    def observe(self, identity, findings):
        with self.lock:
            if identity == self.profile:
                # Strip all identifying material before holding data for commentary.
                self.findings.extend({'intent': f.get('intent'), 'confidence': f.get('confidence'),
                                      'uncertainty': f.get('uncertainty', True)} for f in findings)
                self.findings = self.findings[-40:]
                if findings:
                    self.findings_at = self.clock()

    def allowed(self):
        return config().get('enabled') is True and setting('KT_NO_AI') != '1' and bool(self.focus()) and not self.stop.is_set()

    def edit_state(self):
        """Read existing player-local guide output without changing the locked guide."""
        try:
            data = json.loads((ROOT / 'edit-state.json').read_text())
            with self.lock:
                if ((data.get('profile_id'), data.get('revision')) != self.profile
                        or data.get('session_id') != os.environ.get('KT_COACH_SESSION')
                        or not 0 <= self.clock()-data.get('captured_at', 0) <= 2):
                    return 'unknown'
                attempt = data.get('last_attempt') or {}
                stamp = attempt.get('ended_at')
                if (stamp is not None and stamp != self.seen_attempt
                        and (attempt.get('profile_id'), attempt.get('profile_revision')) == self.profile
                        and 0 <= self.clock()-stamp <= 30):
                    self.seen_attempt = stamp
                    coverage = attempt.get('observed_coverage')
                    if attempt.get('complete_observation') is True and isinstance(coverage, (float, int)) and 0 <= coverage <= 1:
                        self.edits.append(coverage == 1)
                return data.get('mode', 'unknown')
        except (OSError, ValueError, TypeError):
            return 'unknown'

    def tick(self):
        if not self.allowed():
            self.silence()
            return
        now = self.clock()
        mode = self.edit_state()
        if mode in ('editing', 'building'):
            self.silence()
            return
        with self.lock:
            if now-self.last_input < 1 and self.speaking:
                self.silence()
            # Speak during a short practice pause, not during inputs or long AFK periods.
            if not 5 <= now-self.last_input <= 25 or now-self.last_spoke < 90:
                return
            epoch, activity = self.epoch, self.last_input
            stats = compact(self.findings if now-self.findings_at <= 300 else [])
            if self.edits:
                stats.update(edit_observations=len(self.edits), guide_coverage_full=sum(self.edits))
        if not self.budget.reserve('speech', 1):
            return
        self.last_spoke = now
        text = fallback(stats) if stats != self.last_stats else ''
        if text:
            # Do not spend on new wording when there is no room to synthesize it.
            if self.budget.summary()['tts']['used_today'] <= 1000:
                text = llm_text(stats, self.budget) or text
        else:
            style = config().get('style', 'mixed')
            text = personality(style, self.seen_attempt is not None and 0 <= now-self.seen_attempt <= 30, self.last_line)
            if not text:
                return
        # A changed player, resumed inputs, mute or focus loss cancels stale speech.
        if not self.allowed() or epoch != self.epoch or activity != self.last_input:
            return
        path = audio(text, self.budget)
        if not path or not self.allowed() or epoch != self.epoch or activity != self.last_input:
            return
        if os.name == 'nt':
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            self.speaking = True
        self.last_line, self.last_stats = text, stats

    def silence(self):
        if os.name == 'nt' and self.speaking:
            import winsound
            winsound.PlaySound(None, 0)
        self.speaking = False

    def run(self):
        while not self.stop.wait(.5):
            try:
                self.tick()
            except Exception:
                # A failing service must not bring down the overlay or retry rapidly.
                self.last_spoke = self.clock()

    def close(self):
        self.stop.set()
        self.silence()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['enable', 'mute', 'status', 'check', 'llm-check', 'demo'])
    parser.add_argument('--style', choices=['mixed', 'funny', 'brainrot', 'competitive'], default='mixed')
    args = parser.parse_args()
    if args.command in ('enable', 'mute'):
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps({'enabled': args.command == 'enable', 'style': args.style}))
        print('Private coach enabled; takes effect in an updated running overlay.' if args.command == 'enable' else 'Coach muted.')
    elif args.command == 'status':
        print(json.dumps({'enabled': config().get('enabled', False), 'style': config().get('style', 'mixed'),
                          'daily_tts_char_cap': 1200, 'daily_llm_cap': 8, 'minimum_speech_gap_seconds': 90,
                          'usage': Budget().summary()}))
    elif args.command == 'check':
        key, voice = setting('ELEVENLABS_API_KEY'), setting('ELEVENLABS_VOICE_ID')
        print('ElevenLabs key configured:', bool(key), '| voice configured:', bool(voice))
        print('Claude key configured:', bool(setting('ANTHROPIC_API_KEY') or setting('CLAUDE_API_KEY')),
              '| model configured:', bool(setting('CLAUDE_MODEL_FAST') or setting('KT_COACH_MODEL') or setting('CLAUDE_MODEL')))
        print('NIM key configured:', bool(setting('NVIDIA_API_KEY')), '| model configured:', bool(setting('NVIDIA_MODEL_ID')))
        claude_key = setting('ANTHROPIC_API_KEY') or setting('CLAUDE_API_KEY')
        selected = setting('CLAUDE_MODEL_FAST') or setting('KT_COACH_MODEL') or setting('CLAUDE_MODEL')
        if claude_key:
            try:
                req = urllib.request.Request('https://api.anthropic.com/v1/models', headers={'x-api-key': claude_key, 'anthropic-version': '2023-06-01'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    models = [m['id'] for m in json.load(response).get('data', [])]
                print('Claude selected model:', selected, '| available:', selected in models)
                print('Available Claude models:', ', '.join(models))
            except urllib.error.HTTPError as error:
                print('Claude model access check: HTTP', error.code)
            except Exception:
                print('Claude model access check unavailable')
        if key and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', voice):
            try:
                req = urllib.request.Request('https://api.elevenlabs.io/v1/voices/' + voice, headers={'xi-api-key': key})
                with urllib.request.urlopen(req, timeout=10) as response:
                    print('Voice access:', response.status == 200)
            except Exception:
                print('Voice check failed; check credential permissions and voice access. No speech credits used.')
    elif args.command == 'llm-check':
        text = llm_text(compact([]), Budget())
        print('LLM response:', 'ready' if text else 'unavailable or budget limited')
    elif args.command == 'demo':
        # Explicit, bounded paid smoke test, not automatic on startup.
        path = audio('Private coach online. Keep cooking. One calm rep at a time.', Budget())
        print('Speech synthesis:', 'ready' if path else 'unavailable or budget limited')
        if path and os.name == 'nt':
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_NODEFAULT)


if __name__ == '__main__':
    main()
