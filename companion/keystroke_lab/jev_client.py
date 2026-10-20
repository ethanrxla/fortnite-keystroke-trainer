"""Minimal client for Jev (TypeSafe System One): calibrated multiple-choice decisions for use inside code.

Docs: https://docs.typesafe.ai/api.md . One POST to /v1/systemone with a `state` and named `questions`; each choice
question answers with the top choice, a probability for every option and a 0..1 confidence. Jev does not generate
text, so every question lists its options up front.

The key is read from JEV_API_KEY (../.env via envfile) and is never printed or logged. Every failure (no key, no
network, 401, 422, 429, 529, bad JSON) returns None so the caller falls back to local rules.
"""

import json
import os
import time
import urllib.request

from . import envfile  # noqa: F401  (loads ../.env)

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"


class JevClient:
    def __init__(self, key=None, model=MODEL, post=None, max_calls=30, sleep=time.sleep, domain="keystroke", broker=None, shadow=True):
        self.domain=domain; self.shadow=shadow; self.model_version=model
        self.last_error=None
        if broker is None and post is None:
            from .jev_broker import JevBroker
            broker=JevBroker()
        self.broker=broker
        self.key = key if key is not None else os.environ.get("JEV_API_KEY")
        self.model = model
        self.post = post or self._http_post
        self.max_calls = max_calls
        self.sleep = sleep
        self.calls = 0
        self.tokens = {"input": 0, "output": 0}

    @property
    def available(self):
        return bool(self.key) and os.environ.get("KT_NO_AI") != "1" and self.calls < self.max_calls

    def _http_post(self, body):
        req = urllib.request.Request(URL, json.dumps(body).encode(), {
            "Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.load(resp)

    def decide(self, state, questions, retries=1):
        """Ask several named choice questions about one state. Returns {name: {choice, confidence, probabilities}}
        or None. Counts one call against the session cap per attempt."""
        self.last_error = None
        if not self.available or not isinstance(questions,dict) or not 1<=len(questions)<=8:
            self.last_error = 'unavailable_or_invalid_request'
            return None
        body = {"state": state, "model": self.model, "questions": questions}
        for attempt in range(retries + 1):
            token=None
            if not self.available:return None
            if self.broker:
                try:token=self.broker.acquire(self.domain,self.broker.key(self.domain,state,questions))
                except Exception:
                    self.last_error='broker_unavailable';return None
                if token is None:
                    self.last_error = 'admission_deferred'
                    return None
            self.calls += 1
            try:
                data = self.post(body)
            except Exception as exc:  # network, 4xx, 5xx: retry only on rate limit / overload
                code = getattr(exc, "code", None)
                self.last_error=code or "transport"
                delay=0.
                if code in (429,529):
                    import random
                    delay=min(60.,2.**attempt+random.random())
                    try:delay=max(delay,float(exc.headers.get("Retry-After",0)))
                    except (AttributeError,ValueError,TypeError):pass
                if self.broker:
                    try:self.broker.finish(token,delay)
                    except Exception:self.last_error="broker_release_failed"
                if code in (429, 529) and attempt < retries and self.calls < self.max_calls:
                    self.sleep(delay)
                    continue
                return None
            if self.broker:
                try:self.broker.finish(token)
                except Exception:self.last_error="broker_release_failed"
            if not isinstance(data, dict):
                self.last_error = 'invalid_response'
                return None
            self.model_version=data.get("model",self.model)
            usage = data.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            for direction in ("input", "output"):
                amount = usage.get(direction + "_tokens", 0)
                if isinstance(amount, int) and amount >= 0:
                    self.tokens[direction] += amount
            answers = data.get('answers')
            if not isinstance(answers, dict):
                self.last_error = 'invalid_response'
                return None
            return answers
        return None


def choice_question(instructions, options):
    """options: {name: description}. Builds one Jev choice question."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}
