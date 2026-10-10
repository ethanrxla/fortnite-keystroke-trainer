"""Fresh structured UEFN telemetry. Never bind a multiplayer log to a local profile by guess."""
import math
import os
import time
import re
from datetime import datetime, timezone
from pathlib import Path

class TelemetryReader:
    def __init__(self,path=None,clock=time.monotonic,wall_clock=time.time,association=None):
        self.path=Path(path or Path(os.environ.get('LOCALAPPDATA',''))/'UnrealEditorFortnite/Saved/Logs/UnrealEditorFortnite.log')
        self.clock=clock;self.position=self.path.stat().st_size if self.path.exists() else 0
        self.buffer='';self.latest=None;self.received=-math.inf
        self.wall_clock=wall_clock;self.association=association;self.last_server=-math.inf
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
                # Receipt time cannot turn a delayed/backlogged event into a fresh one.
                stamp=re.search(r'\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]',line)
                if not stamp or not self.association:
                    self.latest=None;continue
                generated=datetime.strptime(stamp[1],'%Y.%m.%d-%H.%M.%S:%f').replace(tzinfo=timezone.utc).timestamp()
                age=self.wall_clock()-generated
                if not 0<=age<=.4:self.latest=None;continue
                fields=dict(part.split('=',1) for part in line.split(marker,1)[1].strip().split('|') if '=' in part)
                if int(fields['players'])!=1:self.latest=None;continue
                vector=lambda prefix:tuple(float(fields[prefix+k]) for k in 'xyz')
                data={'player_position':vector('p'),'view_origin':vector('v'),'view_direction':vector('a'),'server_time':float(fields['t']), 'source':'uefn_single_participant_telemetry','ownership':'unknown'}
                if not all(math.isfinite(v) for name in ['player_position','view_origin','view_direction'] for v in data[name]):continue
                if data['server_time']<self.last_server:
                    self.latest=None;self.association=None;continue
                self.last_server=data['server_time']
                data['association']=self.association
                self.latest=data;self.received=self.clock()-age
            except (ValueError,KeyError,TypeError):continue
        return self.latest if self.clock()-self.received<=.4 else None
