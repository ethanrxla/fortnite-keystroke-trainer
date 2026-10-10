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
MODEL = "jev-latest"


class JevClient:
    def __init__(self, key=None, model=MODEL, post=None, max_calls=30, sleep=time.sleep):
        self.key = key if key is not None else os.environ.get("JEV_API_KEY")
        self.model = model
        self.post = post or self._http_post
        self.max_calls = max_calls
        self.sleep = sleep
        self.calls = 0
        self.tokens = {"input": 0, "output": 0}

    @property
    def available(self):
        return bool(self.key) and self.calls < self.max_calls

    def _http_post(self, body):
        req = urllib.request.Request(URL, json.dumps(body).encode(), {
            "Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.load(resp)

    def decide(self, state, questions, retries=1):
        """Ask several named choice questions about one state. Returns {name: {choice, confidence, probabilities}}
        or None. Counts one call against the session cap per attempt."""
        if not self.available:
            return None
        body = {"state": state, "model": self.model, "questions": questions}
        for attempt in range(retries + 1):
            self.calls += 1
            try:
                data = self.post(body)
            except Exception as exc:  # network, 4xx, 5xx: retry only on rate limit / overload
                code = getattr(exc, "code", None)
                if code in (429, 529) and attempt < retries and self.calls < self.max_calls:
                    self.sleep(0.5 * (attempt + 1))
                    continue
                return None
            if not isinstance(data, dict):
                return None
            usage = data.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            for direction in ("input", "output"):
                amount = usage.get(direction + "_tokens", 0)
                if isinstance(amount, int) and amount >= 0:
                    self.tokens[direction] += amount
            return data.get("answers")
        return None


def choice_question(instructions, options):
    """options: {name: description}. Builds one Jev choice question."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}
