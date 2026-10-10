"""Named local player memories; explicit selection, never automatic server identity."""
import json,threading,uuid
from pathlib import Path
from dataclasses import replace
from .bind_profiles import parse
class PlayerProfiles:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock()
        try:self.entries=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.entries={}
        if not isinstance(self.entries,dict):self.entries={}
    def names(self):return tuple(self.entries)
    def load(self,name):return parse(self.entries[name])
    def save(self,name,snapshot):
        name=name.strip()
        if not name:raise ValueError('Player name is required')
        with self.lock:
            old=self.entries.get(name)
            pid=old['profile_id'] if old else str(uuid.uuid4())
            saved=replace(snapshot,profile_id=pid,revision=snapshot.revision+1)
            # Validate before saving; retain every alternate/context and verified flag.
            parse(saved.to_dict())
            self.entries[name]=saved.to_dict();self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix(self.path.suffix+'.tmp');temp.write_text(json.dumps(self.entries,indent=2),encoding='utf-8');temp.replace(self.path)
            return saved
