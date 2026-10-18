"""Small MCP stdio bridge; all operations are scoped to the running Aion2 app."""
from __future__ import annotations

import json
import sys
from . import __version__
from .control import call_app


def schema(properties=None, required=None):
    result = {"type": "object", "properties": properties or {}, "additionalProperties": False}
    if required:
        result["required"] = required
    return result


TOOLS = [
    {"name": "farm_status", "description": "Read app state, foreground process, rights, profile and recent logs. Sends no input.",
     "inputSchema": schema(), "annotations": {"readOnlyHint": True}},
    {"name": "farm_test_input", "description": "Start a bounded Aion2 input test. Preview is the default. Live needs preview=false, game foreground and global F9. No automatic window activation.",
     "inputSchema": schema({"key": {"type": "string", "enum": ["alternate_mouse", "leftmouse", "rightmouse", "1", "2", "3", "tab", "space"]},
                            "method": {"type": "string", "enum": ["scancode", "virtual", "messages"]},
                            "seconds": {"type": "number", "minimum": 0.2, "maximum": 3},
                            "preview": {"type": "boolean"}}, ["key"])},
    {"name": "farm_stop", "description": "Stop current run and release all inputs owned by this app.", "inputSchema": schema()},
    {"name": "farm_capture_hud", "description": "Capture only the foreground Aion2 client for input diagnosis. Does not activate windows or send input. Returns a bounded image and original size.",
     "inputSchema": schema(), "annotations": {"readOnlyHint": True}},
]
METHODS = {"farm_status": "status", "farm_test_input": "test", "farm_stop": "stop", "farm_capture_hud": "capture"}


def dispatch(message, caller=call_app):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in message:
        return None
    identity = message["id"]
    method, params = message.get("method"), message.get("params") or {}
    try:
        if method == "initialize":
            supported = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
            version = params.get("protocolVersion", "2025-11-25")
            result = {"protocolVersion": version if version in supported else "2025-11-25",
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "aion2-farm", "version": __version__}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments") or {}
            if name not in METHODS or not isinstance(arguments, dict):
                raise ValueError("Unknown tool or invalid arguments")
            try:
                data = caller(METHODS[name], arguments)
                if "image" in data:
                    data = data.copy()
                    encoded = data.pop("image")
                    result = {"content": [{"type":"text", "text":json.dumps(data,ensure_ascii=False)},
                                           {"type":"image", "mimeType":"image/png", "data":encoded}]}
                else:
                    result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
            except Exception as exc:
                result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
        else:
            return {"jsonrpc":"2.0", "id":identity, "error":{"code":-32601,"message":"Method not found"}}
        return {"jsonrpc": "2.0", "id": identity, "result": result}
    except Exception as exc:
        return {"jsonrpc":"2.0", "id":identity, "error":{"code":-32602,"message":str(exc)}}


def main():
    # Windows console defaults may be CP1252; MCP stdio is always UTF-8.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    for line in sys.stdin:
        try:
            response = dispatch(json.loads(line))
        except ValueError:
            response = {"jsonrpc":"2.0", "id":None, "error":{"code":-32700,"message":"Parse error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
