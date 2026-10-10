"""Immutable per-player calibrated bindings; legacy guesses retain unverified provenance."""
import json
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from .actions import DEFAULTS, CATEGORY_OF


@dataclass(frozen=True)
class Binding:
    action: str
    keys: tuple
    context: str = 'any'
    verified: bool = False


@dataclass(frozen=True)
class BindProfile:
    profile_id: str
    revision: int
    bindings: tuple
    version: int = 1

    def primary(self):
        return {b.action: b.keys[0] for b in self.bindings if b.keys}

    def to_dict(self):
        return dict(version=self.version, profile_id=self.profile_id, revision=self.revision,
                    bindings=[dict(action=b.action, keys=list(b.keys), context=b.context, verified=b.verified)
                              for b in self.bindings])


class BindMap(dict):
    """Legacy primary-key mapping retaining the same immutable profile snapshot."""
    def __init__(self, profile):
        super().__init__(profile.primary())
        self.profile = profile

    def all_keys(self):
        return {key for binding in self.profile.bindings for key in binding.keys}


def parse(data, profile_id='local', confirm_sprint=False):
    if "version" in data and data.get("version") != 1:
        raise ValueError("Unsupported binding profile version")
    if data.get('version') == 1:
        bindings = tuple(Binding(b['action'], tuple(str(k).lower() for k in b['keys']),
                                 b.get('context', 'any'), bool(b.get('verified', False))) for b in data['bindings'])
        if any(not b.keys or any(not k for k in b.keys) for b in bindings):
            raise ValueError('Bindings need nonempty key names')
        return BindProfile(str(data['profile_id']), int(data['revision']), bindings)
    guessed = dict(DEFAULTS)
    guessed.update(data)
    bindings = [Binding(a, (str(k).lower(),), CATEGORY_OF.get(a, 'any'), False) for a, k in guessed.items()]
    # This is the sole user-confirmed mapping; all inherited/default entries remain unverified.
    if confirm_sprint:
        bindings = [b for b in bindings if b.action != 'sprint'] + [Binding('sprint', ('1',), 'move', True)]
    return BindProfile(profile_id, 0, tuple(bindings))


class ProfileStore:
    def __init__(self, path, confirm_sprint=False):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.confirm_sprint = confirm_sprint
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.snapshot = parse(data, str(self.path.resolve()), confirm_sprint)
        self.stamp = self._file_stamp()

    def _file_stamp(self):
        try:
            stat = self.path.stat()
            return (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
        except FileNotFoundError:
            return None

    def refresh(self):
        with self.lock:
            stamp = self._file_stamp()
            if stamp != self.stamp and stamp is not None:
                try:
                    # Same parse as at start-up: without confirm_sprint a reload of a legacy file dropped sprint = 1.
                    candidate = parse(json.loads(self.path.read_text()), self.snapshot.profile_id, self.confirm_sprint)
                except (ValueError, KeyError, TypeError, OSError):
                    return self.snapshot
                if candidate != self.snapshot:
                    candidate = replace(candidate, revision=max(candidate.revision, self.snapshot.revision + 1))
                    self.snapshot = candidate
                self.stamp = stamp
            return self.snapshot

    def activate(self, profile):
        with self.lock:
            candidate = parse(profile.to_dict())
            self.snapshot = replace(candidate, revision=max(candidate.revision, self.snapshot.revision + 1))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + '.tmp')
            temporary.write_text(json.dumps(self.snapshot.to_dict(), indent=2), encoding='utf-8')
            os.replace(temporary, self.path)
            self.stamp = self._file_stamp()
            return self.snapshot

    def merge(self, imported, overwrite_verified=False):
        """Add bindings read from elsewhere (the game's own settings) in one revision. Actions the player already
        confirmed keep their keys unless overwrite_verified. Returns the actions that changed."""
        with self.lock:
            old = self.refresh()
            existing = {}
            for b in old.bindings:
                existing.setdefault(b.action, []).append(b)
            incoming = {}
            for b in imported:
                had = existing.get(b.action, [])
                if any(h.verified for h in had) and not overwrite_verified:
                    continue
                if [(h.keys, h.verified) for h in had] != [(b.keys, b.verified)]:
                    incoming[b.action] = b
            if not incoming:
                return []
            bindings, placed = [], set()
            for b in old.bindings:
                if b.action not in incoming:
                    bindings.append(b)
                elif b.action not in placed:
                    bindings.append(incoming[b.action])
                    placed.add(b.action)
            bindings += [b for a, b in incoming.items() if a not in placed]
            self.snapshot = replace(old, version=1, revision=old.revision + 1, bindings=tuple(bindings))
            self._write()
            return list(incoming)

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(json.dumps(self.snapshot.to_dict(), indent=2), encoding='utf-8')
        os.replace(temporary, self.path)
        self.stamp = self._file_stamp()

    def update(self, action, keys, context='any', verified=True):
        if action not in DEFAULTS and action != 'swap_weapon':
            raise ValueError('Unknown action')
        keys = tuple(str(k).strip().lower() for k in keys)
        if not keys or any(not k for k in keys):
            raise ValueError('Need key names')
        with self.lock:
            old = self.refresh()
            bindings = tuple(b for b in old.bindings if not (b.action == action and (context == "any" or b.context == context)))
            self.snapshot = replace(old, revision=old.revision + 1,
                                    bindings=bindings + (Binding(action, keys, context, verified),))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + '.tmp')
            temporary.write_text(json.dumps(self.snapshot.to_dict(), indent=2), encoding='utf-8')
            os.replace(temporary, self.path)
            self.stamp = self._file_stamp()
            return self.snapshot
