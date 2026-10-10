"""Fresh structured UEFN telemetry. Never bind a multiplayer log to a local profile by guess."""
import math
import os
import time
from pathlib import Path

class TelemetryReader:
    def __init__(self,path=None,clock=time.monotonic):
        self.path=Path(path or Path(os.environ.get('LOCALAPPDATA',''))/'UnrealEditorFortnite/Saved/Logs/UnrealEditorFortnite.log')
        self.clock=clock;self.position=self.path.stat().st_size if self.path.exists() else 0
        self.buffer='';self.latest=None;self.received=-math.inf
    def poll(self):
        try:
            with self.path.open('r',encoding='utf-8',errors='replace') as f:
                if self.path.stat().st_size<self.position:self.position=0;self.latest=None;self.buffer=''
                f.seek(self.position);chunk=f.read(131072);self.position=f.tell()
        except OSError:return None
        lines=(self.buffer+chunk).split('\n');self.buffer=lines.pop()
        for line in lines:
            marker='KT|context|'
            if marker not in line:continue
            try:
                fields=dict(part.split('=',1) for part in line.split(marker,1)[1].strip().split('|') if '=' in part)
                if int(fields['players'])!=1:self.latest=None;continue
                vector=lambda prefix:tuple(float(fields[prefix+k]) for k in 'xyz')
                data={'player_position':vector('p'),'view_origin':vector('v'),'view_direction':vector('a'),'server_time':float(fields['t']), 'source':'uefn_single_participant_telemetry','ownership':'unknown'}
                if not all(math.isfinite(v) for name in ['player_position','view_origin','view_direction'] for v in data[name]):continue
                self.latest=data;self.received=self.clock()
            except (ValueError,KeyError,TypeError):continue
        return self.latest if self.clock()-self.received<=.4 else None
