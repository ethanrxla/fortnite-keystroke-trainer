"""Supabase client for the companion: anonymous identity, the `api` RPCs and the Edge Functions. Standard library only.

Configuration: see load_config (../.env, else shared/cloud.json). The publishable / anon key is public by design
(row-level security protects the data); secret and service-role keys must never be on a player's PC.

Identity: the first time it is needed, the client signs in anonymously (no account, no login screen) and keeps the
session in companion/.cloud-session.json (gitignored). Tokens are refreshed before they expire. Nothing here sends
data on its own: callers (sync.py, the CLI) decide, and only after the player opted in.
"""
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

from .. import envfile  # noqa: F401  (loads ../.env)

ROOT = pathlib.Path(__file__).resolve().parents[3]
SESSION_FILE = pathlib.Path(__file__).resolve().parents[2] / ".cloud-session.json"
CONFIG_FILE = ROOT / "shared" / "cloud.json"
API_SCHEMA = "api"


class CloudError(Exception):
    def __init__(self, code, message, headers=None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.headers = code, message, headers or {}


def _urllib_http(method, url, headers, body, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, dict(resp.headers), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = {"error": raw[:200].decode("utf-8", "replace")}
        return exc.code, dict(exc.headers or {}), payload


def load_config():
    """(url, public key). URL: SUPABASE_URL, else https://<SUPABASE_PROJECT_ID>.supabase.co. Key: the publishable key
    (SUPABASE_PUBLISHABLE_KEY, Supabase's recommended client key), else the legacy anon key. Secret / service-role keys
    are never read here: this code runs on players' PCs."""
    env = os.environ
    url = env.get("SUPABASE_URL") or (f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else "")
    key = env.get("SUPABASE_PUBLISHABLE_KEY") or env.get("SUPABASE_ANON_KEY") or env.get("SUPABASE_ANON_PUBLIC_KEY") or ""
    if (not url or not key) and CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        url, key = url or data.get("url", ""), key or data.get("publishable_key") or data.get("anon_key", "")
    return (url or "").rstrip("/"), key or ""


class CloudClient:
    def __init__(self, url=None, anon_key=None, session_file=SESSION_FILE, http=None, clock=time.time):
        cfg_url, cfg_key = load_config()
        self.url = (url or cfg_url).rstrip("/")
        self.anon_key = anon_key or cfg_key
        self.session_file = pathlib.Path(session_file) if session_file else None
        self.http = http or _urllib_http
        self.clock = clock
        self.session = None
        if self.session_file and self.session_file.exists():
            try:
                self.session = json.loads(self.session_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.session = None

    @property
    def configured(self):
        return bool(self.url and self.anon_key)

    @property
    def player_id(self):
        return ((self.session or {}).get("user") or {}).get("id")

    # -- identity ------------------------------------------------------------------------------------------
    def _save(self, data):
        self.session = {"access_token": data["access_token"], "refresh_token": data["refresh_token"],
                        "expires_at": self.clock() + float(data.get("expires_in", 3600)),
                        "user": {"id": (data.get("user") or {}).get("id")}}
        if self.session_file:
            self.session_file.write_text(json.dumps(self.session), encoding="utf-8")

    def _auth(self, path, body):
        status, headers, data = self.http("POST", f"{self.url}/auth/v1/{path}",
                                          {"apikey": self.anon_key, "Content-Type": "application/json"}, body)
        if status >= 300 or not isinstance(data, dict) or "access_token" not in data:
            raise CloudError(status, (data or {}).get("msg") or (data or {}).get("error_description") or "auth failed", headers)
        self._save(data)

    def sign_in(self):
        """Ensure a valid anonymous session; returns the player id."""
        if not self.configured:
            raise CloudError(0, "cloud not configured (SUPABASE_URL / SUPABASE_ANON_KEY)")
        if self.session and self.session.get("expires_at", 0) - self.clock() > 60:
            return self.player_id
        if self.session and self.session.get("refresh_token"):
            try:
                self._auth("token?grant_type=refresh_token", {"refresh_token": self.session["refresh_token"]})
                return self.player_id
            except CloudError:
                self.session = None             # refresh token revoked or expired: start a new anonymous identity
        self._auth("signup", {"data": {}})
        return self.player_id

    def forget_local_identity(self):
        self.session = None
        if self.session_file and self.session_file.exists():
            self.session_file.unlink()

    # -- calls -----------------------------------------------------------------------------------------------
    def _headers(self, extra=None):
        h = {"apikey": self.anon_key, "Authorization": f"Bearer {self.session['access_token']}",
             "Content-Type": "application/json"}
        h.update(extra or {})
        return h

    def rpc(self, name, args=None):
        self.sign_in()
        status, headers, data = self.http("POST", f"{self.url}/rest/v1/rpc/{name}",
                                          self._headers({"Content-Profile": API_SCHEMA, "Accept-Profile": API_SCHEMA}),
                                          args or {})
        if status >= 300:
            raise CloudError(status, (data or {}).get("message") or str(data), headers)
        return data

    def function(self, name, body):
        self.sign_in()
        status, headers, data = self.http("POST", f"{self.url}/functions/v1/{name}", self._headers(), body)
        if status >= 300:
            raise CloudError(status, (data or {}).get("error") or str(data), headers)
        return data

    def jev_post(self, body):
        """Drop-in `post` for jev_client.JevClient: the request goes through the jev-proxy Edge Function, so the Jev
        key stays on the server. Raises CloudError with .code / .headers, which JevClient's retry logic reads."""
        return self.function("jev-proxy", body)
