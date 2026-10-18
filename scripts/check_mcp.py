"""Check the packaged stdio protocol without opening the app or sending input."""
import json
import subprocess
import sys


requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": "Grüße", "method": "ping"},
]
process = subprocess.run([sys.argv[1]], input="".join(json.dumps(item) + "\n" for item in requests),
                         text=True, encoding="utf-8", capture_output=True, timeout=30,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
if process.returncode:
    raise RuntimeError(process.stderr or "MCP process failed")
responses = [json.loads(line) for line in process.stdout.splitlines()]
assert [item["id"] for item in responses] == [1, 2, "Grüße"], responses
assert responses[0]["result"]["serverInfo"]["name"] == "aion2-farm"
assert {item["name"] for item in responses[1]["result"]["tools"]} == {
    "farm_status", "farm_test_input", "farm_stop", "farm_capture_hud"}
assert responses[2]["result"] == {}
print("MCP-EXE: Initialisierung, Tool-Liste und Ping erfolgreich; keine Spieleingaben.")
