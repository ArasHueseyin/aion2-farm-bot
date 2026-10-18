"""Authenticated loopback transport for the optional MCP bridge."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.request import ProxyHandler, Request, build_opener

from .models import profile_directory


def session_file():
    return profile_directory().parent / "control-session.json"


class ControlServer:
    def __init__(self, submit, path=None):
        self.path = Path(path) if path else session_file()
        self.token = secrets.token_urlsafe(32)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def log_message(self, *args):
                pass

            def do_POST(self):
                authorization = self.headers.get("Authorization", "").encode("utf-8")
                if self.path != "/rpc" or not secrets.compare_digest(authorization, ("Bearer " + owner.token).encode("ascii")):
                    self.send_error(403)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 65536:
                        raise ValueError("Ungültige Anfragengröße.")
                    payload = json.loads(self.rfile.read(size))
                    if not isinstance(payload, dict) or not isinstance(payload.get("method"), str):
                        raise ValueError("Ungültige Anfrage.")
                    arguments = payload.get("arguments", {})
                    if not isinstance(arguments, dict):
                        raise ValueError("Argumente müssen ein Objekt sein.")
                    result = submit(payload["method"], arguments)
                    body = json.dumps({"result": result}, ensure_ascii=False).encode("utf-8")
                except Exception as exc:
                    body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"pid": os.getpid(), "port": self.http.server_port, "token": self.token}), encoding="utf-8")
        self.thread = threading.Thread(target=self.http.serve_forever, name="mcp-loopback", daemon=True)
        self.thread.start()

    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=1)
        try:
            if json.loads(self.path.read_text(encoding="utf-8")).get("token") == self.token:
                self.path.unlink()
        except (OSError, ValueError):
            pass


def call_app(method, arguments=None, *, path=None):
    path = Path(path) if path else session_file()
    try:
        session = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("Keine MCP-Sitzung. App mit --mcp-control starten.") from None
    port = session.get("port")
    if type(port) is not int or not 1 <= port <= 65535 or not isinstance(session.get("token"), str):
        raise RuntimeError("Ungültige lokale MCP-Sitzung.")
    data = json.dumps({"method": method, "arguments": arguments or {}}).encode("utf-8")
    request = Request(f"http://127.0.0.1:{port}/rpc", data=data,
                      headers={"Authorization": "Bearer " + session["token"], "Content-Type": "application/json"})
    # Never forward a local capability token through an environment-configured proxy.
    with build_opener(ProxyHandler({})).open(request, timeout=8) as response:
        result = json.load(response)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["result"]
