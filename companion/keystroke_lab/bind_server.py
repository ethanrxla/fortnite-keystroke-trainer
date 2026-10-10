"""A tiny local JSON port so other tools can read the overlay's live view of your keybinds.

    GET  http://127.0.0.1:8765/binds    -> {"binds": {action: key}, "habits": [keys], "categories": {action: category}}
    GET  http://127.0.0.1:8765/events   -> the last 50 verdicts the overlay made, newest last
    POST http://127.0.0.1:8765/binds    -> {"action": "sprint", "key": "1"}; writes keybinds.json.
                                           Needs the X-KT-Token header (companion/.bind_token, created on first run).

It listens on 127.0.0.1 only, never on a network interface. Reads expose key names only, no timing or typed text.
"""

import json
import pathlib
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import actions, drills
from .bind_profiles import ProfileStore

PORT = 8765
TOKEN_FILE = pathlib.Path(__file__).resolve().parents[1] / ".bind_token"


def token(path=TOKEN_FILE):
    path = pathlib.Path(path)
    if not path.exists():
        path.write_text(secrets.token_hex(16), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def make_handler(get_binds, get_habits, events, binds_file, secret, store=None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/binds":
                self._send(200, {"binds": (store.refresh().primary() if store else get_binds()), "profile": store.snapshot.to_dict() if store else None, "habits": get_habits(), "categories": actions.CATEGORY_OF})
            elif self.path == "/habits":
                self._send(200, {"habits": get_habits()})
            elif self.path in ("/events", "/events/recent"):
                self._send(200, {"events": list(events)[-50:]})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/binds":
                return self._send(404, {"error": "not found"})
            if self.headers.get("X-KT-Token") != secret:
                return self._send(403, {"error": "bad token"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 8192:
                    return self._send(400, {"error": "invalid request size"})
                body = json.loads(self.rfile.read(length) or b"{}")
                action = str(body["action"])
                keys = body.get("keys") or [str(body["key"]).lower()]
                if not isinstance(keys, list):
                    raise ValueError("keys must be list")
                key = keys[0]
            except (ValueError, KeyError):
                return self._send(400, {"error": "need action and key"})
            if action not in actions.DEFAULTS and action != "swap_weapon":
                return self._send(400, {"error": "unknown action"})
            try:
                active = store or ProfileStore(binds_file)
                snapshot = active.update(action, keys, body.get('context', 'any'), bool(body.get('verified', True)))
            except (ValueError, TypeError, IndexError):
                return self._send(400, {'error': 'invalid binding'})
            self._send(200, {'ok': True, 'profile': snapshot.to_dict(), 'action': action, 'key': key})

        def log_message(self, *args):  # keep the terminal quiet
            return

    return Handler


def start(get_binds, get_habits, events, binds_file=drills.BINDS_FILE, port=PORT, secret=None, store=None):
    """Start the server on a daemon thread. Returns the server (call .shutdown() to stop) or None if the port is busy."""
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(get_binds, get_habits, events, binds_file, secret or token(), store))
    except OSError:
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
