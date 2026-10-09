"""Call one Verse tool on the open UEFN project through the MCP, e.g.

    python tools/verse_call.py BuildAll
    python tools/verse_call.py ListFiles '{"path":"","bRecursive":false}'
"""
import sys,json
sys.path.insert(0,'tools')
from mcp_call import post
_, sid = post({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"kt","version":"1"}}})
post({"jsonrpc":"2.0","method":"notifications/initialized"}, sid)
tool=sys.argv[1]; args=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
res,_=post({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"call_tool","arguments":{"toolset_name":"ValkyrieToolset.VerseToolset","tool_name":tool,"arguments":args}}},sid)
print("\n".join(c.get("text","") for c in res["result"].get("content",[]))[:6000])
