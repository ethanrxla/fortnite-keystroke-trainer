"""Local action evidence and sequence metrics; no networking or edit geometry."""
from dataclasses import dataclass
import queue
from collections import deque

@dataclass(frozen=True)
class InputEvent:
    key: str
    kind: str
    at: float
    context: str = 'unknown'

class InputObserver:
    def __init__(self):self.events=queue.Queue(maxsize=4096);self.dropped=0
    def capture(self,event):
        try:self.events.put_nowait(event)
        except queue.Full:self.dropped+=1

class ActionResolver:
    def __init__(self,profile):self.profile=profile
    def resolve(self,key,context):
        domains={'building':{'build','move','combat'},'editing':{'edit','move','combat'},
                 'weapon':{'combat','move'},'editable':{'edit','combat','move'}}
        allowed=domains.get(context,set())|{'any','ui','utility',context}
        return frozenset(b.action for b in self.profile.bindings if b.verified and key in b.keys
                         and (b.context in allowed or context=='unknown'))

class SequenceAnalyzer:
    def __init__(self,sequences=()):
        self.sequences=tuple(tuple(s) for s in sequences);self.reset()
    def reset(self):self.progress=[0]*len(self.sequences);self.observed=deque(maxlen=4096);self.gaps=False
    def observe(self,actions,at):
        if len(self.observed)>=256:self.gaps=True;return
        self.observed.append((at,tuple(sorted(actions))))
        for i,s in enumerate(self.sequences):
            if self.progress[i]<len(s) and s[self.progress[i]] in actions:self.progress[i]+=1
    def finish(self):
        if not self.sequences:return {'graded':False}
        if self.gaps:return {'graded':False,'complete_observation':False,'actions_not_observed':[]}
        # Align against every declared alternative; shared bindings remain alternatives, not multiple presses.
        observed=[set(actions) for _,actions in self.observed]
        def align(expected):
            table={(0,0):(0,(),0,0)}
            for i in range(len(expected)+1):
                for j in range(len(observed)+1):
                    if not (i or j):continue
                    choices=[]
                    if i:
                        cost,missing,extra,order=table[i-1,j]
                        choices.append((cost+1,missing+(expected[i-1],),extra,order))
                    if j:
                        cost,missing,extra,order=table[i,j-1]
                        choices.append((cost+1,missing,extra+1,order))
                    if i and j and expected[i-1] in observed[j-1]:choices.append(table[i-1,j-1])
                    if i>1 and j>1 and expected[i-1] in observed[j-2] and expected[i-2] in observed[j-1]:
                        cost,missing,extra,order=table[i-2,j-2]
                        choices.append((cost+1,missing,extra,order+1))
                    table[i,j]=min(choices,key=lambda x:(x[0],len(x[1]),x[2],x[3]))
            return table[len(expected),len(observed)]
        cost,missing,extra,order=min((align(s) for s in self.sequences),key=lambda x:x[0])
        return {'graded':not self.gaps,'complete_observation':not self.gaps,
                'actions_not_observed':list(missing) if not self.gaps else [],
                'extra_inputs':extra if not self.gaps else None,'order_errors':order if not self.gaps else None,
                'completed':cost==0 and not self.gaps,'observed_count':len(self.observed)}

class KeystrokeAnalyzer:
    IGNORED={'print_screen','esc','escape','windows','cmd','cmd_l','cmd_r'}
    def __init__(self,profile,sequences=()):
        self.resolver=ActionResolver(profile);self.sequence=SequenceAnalyzer(sequences)
        self.held={};self.intervals=deque(maxlen=4096);self.durations=deque(maxlen=4096);self.last=None
    def accept(self,event):
        if event.kind=='focus_lost':
            self.held.clear();self.sequence.gaps=True;self.last=None;return {'kind':'gap'}
        if event.kind=='up':
            start=self.held.pop(event.key,None)
            if start is not None:self.durations.append(max(0,event.at-start))
            return {'kind':'release'}
        if event.key in self.IGNORED:return {'kind':'ignored'}
        if event.key in self.held:return {'kind':'held_repeat'}
        if not event.key.startswith('wheel_'):self.held[event.key]=event.at
        actions=self.resolver.resolve(event.key,event.context)
        if self.last is not None:self.intervals.append(max(0,event.at-self.last))
        self.last=event.at
        expected={a for s in self.sequence.sequences for a in s}
        mechanics={'wall','floor','cone','ramp','edit','edit_confirm','reset','fire'}
        if actions and (not self.sequence.sequences or actions & (expected|mechanics)):
            self.sequence.observe(actions,event.at)
        return {'kind':'observed' if actions else 'unmapped','actions':tuple(sorted(actions)),
                'profile_revision':self.resolver.profile.revision}
