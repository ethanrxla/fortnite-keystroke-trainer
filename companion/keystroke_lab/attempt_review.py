"""Review recorded edit attempts: approve, reject or relabel the auto-labels, in a browser on this PC.

    python -m keystroke_lab review-edits            # opens http://127.0.0.1:8766/?token=...

Listens on 127.0.0.1 only. Reads come from companion/data/player.db; writes need the per-PC token (companion/.bind_token,
the same one the bind port uses) so another program on the machine cannot label for you. Labels feed
tools/promote_edits.py (an edit is game-verified after enough approved attempts) and, once uploaded, the shared data.
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .bind_server import token as local_token
from .edit_dictionary import EditDictionary
from .pieces import canonical
from .store import Store

PORT = 8766
STATUSES = ("approved", "rejected", "relabelled")


def attempts_for_review(store, status="unlabelled", limit=200):
    rows = store.rows("SELECT record FROM edit_attempts ORDER BY t_open DESC LIMIT ?", (limit * 4,))
    out = []
    for (raw,) in rows:
        rec = json.loads(raw)
        label = store.label(rec["attempt_id"])
        if status == "unlabelled" and label:
            continue
        if status not in ("unlabelled", "all") and (not label or label["status"] != status):
            continue
        rec["label"] = label
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def catalogue_by_piece(dictionary=None):
    d = dictionary or EditDictionary()
    out = {}
    for e in d.all.values():
        out.setdefault(canonical(e["piece"]), []).append({"id": e["id"], "name": e["name"], "tiles": e.get("tiles", [])})
    return out


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Edit review</title><style>
:root{--bg:#0e1419;--card:#16202a;--line:#2b3a47;--text:#e6eef3;--muted:#8fa3b2;--ok:#2fbf71;--bad:#e5484d;--sel:#f2c94c}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f5f7f9;--card:#fff;--line:#d6dde3;--text:#14202a;--muted:#5b6b78}}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{position:sticky;top:0;background:var(--bg);padding:12px 16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0 12px 0 0}select,button{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.row{display:flex;justify-content:space-between;gap:8px;color:var(--muted);font-size:12px}
.grid{display:grid;gap:3px;margin:10px 0;width:120px}.grid div{aspect-ratio:1;border:1px solid var(--line);border-radius:3px}
.grid .on{background:var(--sel)}.grid .want{outline:2px solid var(--ok);outline-offset:-3px}
.tag{display:inline-block;padding:1px 6px;border-radius:999px;border:1px solid var(--line);font-size:12px}
.completed{color:var(--ok)}.wrong_shape,.reset{color:var(--bad)}.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
button.ok{border-color:var(--ok)}button.bad{border-color:var(--bad)}.done{opacity:.45}
</style></head><body><header><h1>Edit attempts</h1>
<label>Show <select id="status"><option value="unlabelled">to review</option><option value="approved">approved</option>
<option value="rejected">rejected</option><option value="all">all</option></select></label><span id="count" class="row"></span></header>
<main id="list"></main><script>
const token=new URLSearchParams(location.search).get('token')||'';let catalogue={};
const n=p=>p==='wall'?3:2;
function grid(piece,tiles,want){const c=n(piece),g=document.createElement('div');g.className='grid';g.style.gridTemplateColumns=`repeat(${c},1fr)`;
 for(let r=c-1;r>=0;r--)for(let col=0;col<c;col++){const t=r*c+col,d=document.createElement('div');if(tiles.includes(t))d.className='on';if(want.includes(t))d.classList.add('want');g.appendChild(d)}return g}
async function load(){const s=document.getElementById('status').value;
 const r=await fetch(`/api/attempts?status=${s}`);const data=await r.json();catalogue=data.catalogue;
 const list=document.getElementById('list');list.innerHTML='';document.getElementById('count').textContent=`${data.attempts.length} attempts`;
 for(const a of data.attempts){const card=document.createElement('div');card.className='card';
  const opened=new Date(a.t_edit_open*1000).toLocaleString();const dur=(a.t_close-a.t_edit_open).toFixed(1);
  const want=(catalogue[a.piece]||[]).find(e=>e.id===a.suggested_edit_id);
  card.innerHTML=`<div class="row"><span>${opened}</span><span>${dur}s</span></div>
   <div><b>${a.piece}</b> <span class="tag">${a.piece_evidence}</span> <span class="tag ${a.outcome}">${a.outcome}</span></div>
   <div class="row"><span>suggested: ${a.suggested_edit_id||'-'}</span><span>made: ${a.matched_edit_id||'-'}</span></div>
   <div class="row"><span>confidence ${a.auto_label_confidence}</span><span>${a.label?('labelled '+a.label.status):''}</span></div>`;
  card.appendChild(grid(a.piece,a.final_tiles||[],want?want.tiles:[]));
  const acts=document.createElement('div');acts.className='acts';
  const sel=document.createElement('select');sel.innerHTML='<option value="">relabel as...</option>'+(catalogue[a.piece]||[]).map(e=>`<option value="${e.id}">${e.name}</option>`).join('');
  const mk=(txt,cls,fn)=>{const b=document.createElement('button');b.textContent=txt;b.className=cls;b.onclick=fn;return b};
  acts.append(mk('Approve','ok',()=>label(a,'approved',a.matched_edit_id,card)),mk('Reject','bad',()=>label(a,'rejected',null,card)),sel,
   mk('Save','',()=>sel.value&&label(a,'relabelled',sel.value,card)));card.appendChild(acts);list.appendChild(card)}}
async function label(a,status,edit,card){const r=await fetch('/api/label',{method:'POST',headers:{'Content-Type':'application/json','X-KT-Token':token},
 body:JSON.stringify({attempt_id:a.attempt_id,status,edit_id:edit})});if(r.ok)card.classList.add('done');else alert('Not saved: '+(await r.text()))}
document.getElementById('status').onchange=load;load();
</script></body></html>"""


def make_handler(store_factory, secret, catalogue):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload, kind="application/json"):
            body = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if url.path == "/api/attempts":
                status = (parse_qs(url.query).get("status") or ["unlabelled"])[0]
                store = store_factory()
                try:
                    return self._send(200, {"attempts": attempts_for_review(store, status), "catalogue": catalogue})
                finally:
                    store.close()
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/label":
                return self._send(404, {"error": "not found"})
            if self.headers.get("X-KT-Token") != secret:
                return self._send(403, {"error": "bad token"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(min(length, 4096)) or b"{}")
                status, attempt_id = body["status"], str(body["attempt_id"])
                if status not in STATUSES:
                    raise ValueError(status)
            except (ValueError, KeyError):
                return self._send(400, {"error": "need attempt_id and status"})
            store = store_factory()
            try:
                if not store.attempt(attempt_id):
                    return self._send(404, {"error": "unknown attempt"})
                store.add_label(attempt_id, status, body.get("edit_id"), reviewer="local", note=str(body.get("note", ""))[:200])
                store.commit()
            finally:
                store.close()
            self._send(200, {"ok": True})

        def log_message(self, *args):
            return
    return Handler


def serve(port=PORT, open_browser=True, store_factory=Store, secret=None):
    secret = secret or local_token()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store_factory, secret, catalogue_by_piece()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/?token={secret}"
    if open_browser:
        webbrowser.open(url)
    return server, url
