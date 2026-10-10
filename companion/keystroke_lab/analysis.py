"""Bounded asynchronous input analysis: local observation, Jev classification, optional wording.

Uncertainty is preserved; adjacency cannot prove intended actions. Both answer
probability and model confidence survive into evidence summaries. Network calls
run only in the overlay worker and are bounded by session/cooldown budgets.
"""

import json
import os
import time
import threading
import math

from . import envfile  # noqa: F401  (loads ../.env)
from .jev_client import JevClient, choice_question

MIN_CONFIDENCE = 0.8        # actual model confidence; independent of answer probability
BATCH = 8                 # events per Jev call
MIN_QUEUE = 3             # strays needed before asking
JEV_COOLDOWN = 30.0       # seconds between Jev calls
LLM_COOLDOWN = 300.0       # seconds between LLM phrasings
LLM_CAP = 6               # LLM calls per session

INTENT_OPTIONS = {
    "insufficient_evidence": "cannot establish intention from these observations; adjacency alone is insufficient",
    "slip": "the player accidentally hit this key while aiming for one of the neighbouring bound keys",
    "deliberate": "the player pressed this on purpose for something that is not in their bind profile",
    "noise": "a bounce, stuck key or other noise, not a real decision",
}
INTENT_QUESTION = ("A Fortnite player pressed a key that is not in their keybind profile. Using the neighbouring "
                   "bound keys and the keys pressed just before it, decide why it was pressed.")


def describe(i, event):
    """The question text for one event, self-contained so Jev knows which event of the batch it is judging."""
    near = ", ".join(f"'{n['key']}' ({n['action']})" for n in event["next_to"]) or "none"
    before = ", ".join(f"'{b['key']}' {b['ms_ago']} ms earlier" for b in event["just_before"]) or "nothing recent"
    return (f"{INTENT_QUESTION} About event {i} only: the unbound key was '{event['key']}'. "
            f"Bound keys physically next to it: {near}. Keys pressed before it: {before}.")


class Analyzer:
    def __init__(self, tracker, jev=None, llm=None, clock=time.perf_counter, min_confidence=MIN_CONFIDENCE):
        self.tracker = tracker
        self.jev = jev if jev is not None else JevClient()
        self.llm = llm if llm is not None else ask_llm_tip
        self.clock = clock
        self.min_confidence = min_confidence
        self.lock = threading.RLock()
        self.in_flight = False
        self.profile_revision = getattr(tracker, "profile_revision", 0)
        self.queue = []
        self.recent = []                 # last few presses as (key, t)
        self.cache = {}                  # (key, neighbours) -> (intent, confidence)
        self.findings = []
        self.last_jev = -999.0
        self.last_llm = -999.0
        self.llm_calls = 0
        self.stats = {"jev_calls": 0, "cache_hits": 0, "llm_calls": 0}

    def invalidate(self, revision):
        with self.lock:
            self.profile_revision = revision
            self.queue.clear()
            self.recent.clear()
            self.cache.clear()
            self.findings.clear()

    def claim(self, now):
        with self.lock:
            if self.in_flight or not self.ready(now):
                return False
            self.in_flight = True
            return True

    def release_claim(self):
        with self.lock:
            self.in_flight = False

    def note(self, key, now):
        with self.lock:
            self.recent = (self.recent + [(key, now)])[-6:]

    def add_stray(self, key, now, neighbours):
        with self.lock:
            prev = [(k, round((now-t)*1000)) for k,t in self.recent if k != key][-3:]
            self.queue.append({'key': key, 'next_to': [{'key':k,'action':a} for k,a in neighbours[:3]],
                               'just_before': [{'key':k,'ms_ago':ms} for k,ms in prev],
                               'profile_revision': self.profile_revision})
            self.queue = self.queue[-BATCH*2:]

    def ready(self, now):
        return len(self.queue) >= MIN_QUEUE and now-self.last_jev >= JEV_COOLDOWN

    def cache_key(self, event):
        return (self.profile_revision, event['key'],
                tuple((n['key'],n['action']) for n in event['next_to']),
                tuple((n['key'], n['ms_ago']//100) for n in event['just_before']))

    def resolve(self, now):
        with self.lock:
            if now-self.last_jev < JEV_COOLDOWN:
                return []
            batch, self.queue = self.queue[:BATCH], self.queue[BATCH:]
            revision = self.profile_revision
            self.last_jev = now
            pending, results = [], []
            for event in batch:
                cached = self.cache.get(self.cache_key(event))
                if cached:
                    self.stats['cache_hits'] += 1
                    results.append(dict(cached, evidence=event))
                else:
                    pending.append(event)
        answers = None
        if pending and self.jev and self.jev.available:
            questions = {f'e{i}': choice_question(describe(i,e), INTENT_OPTIONS) for i,e in enumerate(pending)}
            try:
                answers = self.jev.decide({'events': pending}, questions, retries=0)
            except Exception:
                answers = None
            self.stats['jev_calls'] += 1
        for i,event in enumerate(pending):
            answer = answers.get(f'e{i}') if isinstance(answers,dict) else None
            choice, confidence, probabilities = 'insufficient_evidence', 0.0, {}
            if isinstance(answer,dict):
                proposed = answer.get('choice')
                raw = answer.get('confidence')
                probs = answer.get('probabilities')
                valid = (isinstance(raw,(float,int)) and not isinstance(raw,bool) and math.isfinite(raw)
                         and 0 <= raw <= 1 and isinstance(probs,dict)
                         and all(isinstance(v,(float,int)) and math.isfinite(v) and 0 <= v <= 1 for v in probs.values()))
                if valid:
                    confidence, probabilities = float(raw), dict(probs)
                    if proposed in INTENT_OPTIONS and confidence >= self.min_confidence and probs.get(proposed,0) >= .8:
                        choice = proposed
            finding = dict(key=event['key'], intent=choice, proposed_interpretation=answer.get('choice') if isinstance(answer,dict) else None,
                           confidence=confidence, probabilities=probabilities, uncertainty=choice == 'insufficient_evidence',
                           profile_revision=revision, next_to=event['next_to'], evidence=event)
            with self.lock:
                if revision != self.profile_revision:
                    return []
                self.cache[self.cache_key(event)] = finding
            results.append(finding)
        with self.lock:
            if revision != self.profile_revision:
                return []
            self.findings = (self.findings + results)[-40:]
        return results

    def can_use_llm(self, now):
        return self.llm_calls < LLM_CAP and now - self.last_llm >= LLM_COOLDOWN

    def tip(self, now, binds=None):
        """The player-facing sentence for the recent findings. Template text, rephrased by the LLM when allowed."""
        text = template_tip(self.findings)
        if not text:
            return ""
        if self.can_use_llm(now):
            self.last_llm = now
            self.llm_calls += 1
            self.stats["llm_calls"] += 1
            worded = self.llm(compact_for_llm(self.findings), binds or {})
            if worded:
                return worded
        return text


def local_guess(event):
    return 'insufficient_evidence', 0.0


def template_tip(findings):
    supported = [f for f in findings if not f.get('uncertainty',True) and f.get('confidence',0) >= MIN_CONFIDENCE]
    if not supported:
        return ''
    latest = supported[-1]
    if latest['intent'] == 'deliberate':
        return f"'{latest['key']}' may be an unmapped game action. Confirm it in calibration."
    if latest['intent'] == 'slip':
        return f"Possible input slip involving '{latest['key']}'. Review the recorded sequence before changing a bind."
    return ''


def compact_for_llm(findings):
    return [dict(key=f['key'], intent=f['intent'], confidence=f['confidence'], probabilities=f['probabilities'],
                 uncertainty=f['uncertainty'], profile_revision=f['profile_revision'],
                 next_to=[n['key']+':'+n['action'] for n in f['next_to']])
            for f in findings if not f['uncertainty']][-3:]


def ask_llm_tip(summary, binds, timeout=12.0):
    """One short coaching tip from Claude (fast model), or "" so the caller keeps the template. Never raises."""
    import urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("CLAUDE_MODEL_FAST") or "claude-haiku-5-5"
    if not key or not summary:
        return ""
    near = {a for s in summary for n in s["next_to"] for a in [n.split(":")[1]]}
    relevant = {a: k for a, k in binds.items() if a in near}
    prompt = ("Fortnite keyboard coach. Evidence-backed tentative findings: " + json.dumps(summary) + ". Relevant binds: "
              + json.dumps(relevant) + ". Write at most two short casual sentences to the player naming the exact "
              "keys. Preserve all uncertainty and never infer the intended target from adjacency. Suggest verification. No preamble.")
    body = json.dumps({"model": model, "max_tokens": 120, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body,
                                 {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    except Exception:
        return ""
