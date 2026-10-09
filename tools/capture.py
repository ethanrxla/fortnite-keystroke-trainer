"""Save a UEFN editor viewport capture through the MCP.

    python tools/capture.py out.png X Y Z PITCH YAW
"""

import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mcp_call import post  # noqa: E402


def main():
    out, x, y, z, pitch, yaw = sys.argv[1], *map(float, sys.argv[2:7])
    _, sid = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "kt-capture", "version": "1"}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    pose = {"location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": pitch, "yaw": yaw, "roll": 0},
            "scale": {"x": 1, "y": 1, "z": 1}}
    res, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "call_tool", "arguments": {
        "toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "CaptureViewport",
        "arguments": {"captureTransform": pose}}}}, sid)
    for c in res["result"].get("content", []):
        if c.get("type") == "image":
            pathlib.Path(out).write_bytes(base64.b64decode(c["data"]))
            print("saved", out)
            return
    print(json.dumps(res)[:800])


if __name__ == "__main__":
    main()
