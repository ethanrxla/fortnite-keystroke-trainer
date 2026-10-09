"""Minimal client for Epic's UEFN MCP (streamable HTTP) for quick calls from a shell.

    python tools/mcp_call.py tools/list
    python tools/mcp_call.py call <tool_name> '<json args>'
"""

import json
import os
import sys
import urllib.request

URL = "http://127.0.0.1:8000/mcp"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def post(body, session=None):
    headers = dict(HEADERS)
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(URL, json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=600) as resp:
        text = resp.read().decode("utf-8", "replace")
        sid = resp.headers.get("Mcp-Session-Id") or session
    if text.startswith("event:") or text.startswith("data:"):
        text = "\n".join(l[5:].strip() for l in text.splitlines() if l.startswith("data:"))
    return (json.loads(text) if text.strip() else None), sid


def main():
    _, sid = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "kt-shell", "version": "1"}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    if sys.argv[1] == "describe":
        res, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "describe_toolset", "arguments": {"toolset_name": sys.argv[2]}}}, sid)
        d = json.loads(res["result"]["content"][0]["text"])
        for t in d["tools"]:
            print("-", t["name"].split(".")[-1], ":", t["description"][:300].replace("\n", " "))
            print("    args:", json.dumps(t["inputSchema"].get("properties", {}))[:1200])
        return
    if sys.argv[1] == "call":
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": sys.argv[2], "arguments": args}}
    else:
        msg = {"jsonrpc": "2.0", "id": 2, "method": sys.argv[1], "params": {}}
    res, _ = post(msg, sid)
    content = (res or {}).get("result", {}).get("content")
    if content:
        text = "\n".join(c.get("text", json.dumps(c)) for c in content)
        if os.environ.get("MCP_OUT"):
            with open(os.environ["MCP_OUT"], "w", encoding="utf-8") as f:
                f.write(text)
        print(text[:60000])
    else:
        print(json.dumps(res, indent=1)[:60000])


if __name__ == "__main__":
    main()
