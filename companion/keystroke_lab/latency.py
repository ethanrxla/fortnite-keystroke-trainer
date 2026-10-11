"""Bounded, numeric-only latency telemetry. No frames, keys or credentials."""
from collections import defaultdict, deque
import math


class Latency:
    def __init__(self, limit=10000):self.samples=defaultdict(lambda:deque(maxlen=limit))
    def add(self, stage, ms):
        if isinstance(ms,(int,float)) and math.isfinite(ms) and ms>=0:self.samples[stage].append(ms)
    def report(self):
        out={}
        for stage,values in self.samples.items():
            ordered=sorted(values)
            def pct(p):return round(ordered[min(len(ordered)-1,math.ceil(p*len(ordered))-1)],2)
            out[stage]={"n":len(ordered),"p50_ms":pct(.5),"p95_ms":pct(.95),"p99_ms":pct(.99)}
        return out
