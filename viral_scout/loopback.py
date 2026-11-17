"""One OAuth callback on this PC: a tiny HTTP server that waits for the provider to redirect back with ?state=…&code=…

Used by the "Connect" sign-ins (connect_meta, connect_google, connect_tiktok). Requests whose state doesn't match
(favicon, stray tabs) get a 404 and are ignored.
"""
import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class CallbackError(RuntimeError):
    pass


def server(port, state, host="127.0.0.1"):
    """Bind now (so a busy port fails before the browser opens). Returns (srv, got); got fills on the callback."""
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
            if q.get("state") != state:
                self.send_response(404)
                self.end_headers()
                return
            got.update(q)
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h3>viral-scout: signed in, you can close this tab.</h3>".encode())

        def log_message(self, *a):
            pass

    try:
        srv = HTTPServer((host, port), H)
    except OSError as e:
        raise CallbackError(f"Port {port} is busy ({e}); another sign-in may still be open. Use --port N (and register "
                            "that redirect URL with the provider).") from e
    return srv, got


def wait(srv, got, timeout):
    """Serve until the callback arrives or timeout seconds pass. Returns the query dict."""
    srv.timeout = 2
    end = time.time() + timeout
    try:
        while time.time() < end and "state" not in got:
            srv.handle_request()
    finally:
        srv.server_close()
    if not got:
        raise CallbackError("No sign-in received (timed out).")
    return got


def parse_pasted(text, state=None):
    """The address the browser landed on (or just the code) → query dict. Checks state when both have one."""
    text = (text or "").strip()
    if "?" not in text and "=" not in text:
        return {"code": text, "auth_code": text}
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(text).query or text).items()}
    if state and q.get("state") and q["state"] != state:
        raise CallbackError("That address belongs to another sign-in (state doesn't match). Start again.")
    return q


class Status:
    """Progress for the dashboard (no tokens): {state: starting|waiting|done|failed, message, url?}."""

    def __init__(self, path):
        self.path = Path(path) if path else None

    def __call__(self, state, message, **kw):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"state": state, "message": message, "updated": time.time(), **kw}),
                                 encoding="utf-8")
