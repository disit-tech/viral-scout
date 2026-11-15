"""Owner notes: replies from the Telegram group → work for the notes job (port of solar's site/scripts/notes.mjs).

  python -m viral_scout notes <profile> [list] [--brief] | all | pending
  python -m viral_scout notes <profile> reply|done|skip <id> "text"
  python -m viral_scout notes <profile> send <file> "caption" [--reply <id>]

Backends (jobs: block of the profile):
  api      (default) the ideas API / service: {url}/api/notes, "Authorization: Bearer <secret>", ?project=<project>
             GET  ?status=new | ?status=all&limit=20 → {notes: [...]}     GET ?pending=1 → {pending: n}
             PATCH {id, project, status: done|skipped|open, result?, reply?}  (reply = answer in the note's thread)
             POST  multipart: project, caption, reply_to?, file → {message_id}
           URL and secret come from the env vars named in jobs.api (url_env, secret_env), the env file jobs.api.env_file
           or the ideas: block. A note is {id, created_at, from, kind, status, text, about, file_url, result}.
  command  jobs.notes_command: a CLI with the same verbs (e.g. "node D:/repo/solar-site/site/scripts/notes.mjs");
           arguments are passed through unchanged.
"""
import json
import os
import shlex
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import config


def api_settings(cfg):
    from .jobs import settings as S
    from .publish.pack import read_env_file
    s = S.settings(cfg)
    a = s["api"]
    env = {**read_env_file(a.get("env_file")), **os.environ}
    return {"url": (env.get(a["url_env"], "") or "").rstrip("/"), "secret": env.get(a["secret_env"], ""), "project": a["project"],
            "command": s.get("notes_command") or ""}


class Client:
    """HTTP client for the notes contract above. `opener(req) -> (status, bytes)` can be injected (tests)."""

    def __init__(self, url, secret, project, opener=None):
        self.url, self.secret, self.project = url, secret, project
        self.opener = opener or self._open

    @staticmethod
    def _open(req):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _call(self, method, query=None, body=None, ctype="application/json"):
        if not self.url or not self.secret:
            raise RuntimeError("notes API not configured: set the env vars named in jobs.api (url_env, secret_env)")
        q = urllib.parse.urlencode({"project": self.project, **(query or {})})
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"{self.url}/api/notes?{q}", data=data, method=method,
                                     headers={"Authorization": f"Bearer {self.secret}", "Content-Type": ctype})
        status, raw = self.opener(req)
        if status >= 400:
            raise RuntimeError(f"notes API {method}: HTTP {status} {raw[:200]!r}")
        return json.loads(raw or b"{}")

    def pending(self):
        return int(self._call("GET", {"pending": "1"}).get("pending", 0))

    def list(self, status="new", limit=None):
        q = {"status": status, **({"limit": str(limit)} if limit else {})}
        return self._call("GET", q).get("notes", [])

    def close(self, nid, status, result="", reply=None):
        return self._call("PATCH", body={"id": int(nid), "project": self.project, "status": status, "result": result,
                                         **({"reply": reply} if reply else {})})

    def send(self, file, caption="", reply_to=None):
        b = uuid.uuid4().hex
        fields = {"project": self.project, "caption": caption[:1024], **({"reply_to": str(reply_to)} if reply_to else {})}
        body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items())
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{Path(file).name}\"\r\n"
                 "Content-Type: application/octet-stream\r\n\r\n").encode() + Path(file).read_bytes() + f"\r\n--{b}--\r\n".encode()
        return self._call("POST", body=body, ctype=f"multipart/form-data; boundary={b}")


def show(n, file=None):
    lines = [f"#{n.get('id')} · {n.get('created_at', '?')} · {n.get('from') or '?'} · {n.get('kind', 'text')} · {n.get('status', '?')}"]
    if n.get("about"):
        lines.append("  ↪ about: " + " ".join(str(n["about"]).split())[:160])
    if n.get("text"):
        lines.append(f"  ✎ {n['text']}")
    if file:
        lines.append(f"  📎 {file}")
    if n.get("result"):
        lines.append(f"  → {n['result']}")
    return "\n".join(lines)


def download(cfg, n, opener=None):
    if not n.get("file_url"):
        return None
    d = config.ROOT / "data" / "notes" / cfg["name"]
    d.mkdir(parents=True, exist_ok=True)
    ext = Path(urllib.parse.urlsplit(n["file_url"]).path).suffix or ".bin"
    out = d / f"{n['id']}-{n.get('kind', 'file')}{ext}"
    if not out.exists():
        status, raw = (opener or Client._open)(urllib.request.Request(n["file_url"]))
        if status >= 400:
            return f"(download failed: HTTP {status})"
        out.write_bytes(raw)
    return str(out)


def pending(cfg, client=None):
    """How many notes wait (0 when the backend is missing or down: the notes job then simply does not start Claude)."""
    a = api_settings(cfg)
    try:
        if a["command"] and not client:
            r = subprocess.run(shlex.split(a["command"], posix=os.name != "nt") + ["pending"], capture_output=True, text=True, timeout=120)
            return int((r.stdout.strip().splitlines() or ["0"])[-1])
        return (client or Client(a["url"], a["secret"], a["project"])).pending()
    except Exception:
        return 0


def cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    cfg = config.load(argv[0])
    rest = argv[1:]
    a = api_settings(cfg)
    if a["command"]:
        return subprocess.call(shlex.split(a["command"], posix=os.name != "nt") + rest)
    c = Client(a["url"], a["secret"], a["project"])
    cmd = rest[0] if rest and not rest[0].startswith("--") else "list"
    args = rest[1:] if rest and rest[0] == cmd else rest
    if cmd == "pending":
        print(c.pending())
        return 0
    if cmd in ("list", "all"):
        brief = "--brief" in args
        try:
            notes = c.list("all", 20) if cmd == "all" else c.list("new")
        except RuntimeError as e:
            if brief:
                return 0
            print(f"error: {e}")
            return 1
        if not notes:
            if not brief:
                print("No new notes.")
            return 0
        out = [show(n, download(cfg, n) if n.get("status") == "new" else None) for n in notes]
        if brief:
            print(f"📨 {len(notes)} new note(s) for {cfg['name']}. Act on them, then close each with "
                  f"`python -m viral_scout notes {cfg['name']} done <id> \"what you did\"`.\n")
        print("\n\n".join(out))
        return 0
    if cmd in ("reply", "done", "skip"):
        if len(args) < 2:
            print(f'usage: notes <profile> {cmd} <id> "text"')
            return 2
        nid, text = args[0], args[1]
        if cmd == "reply":
            c.close(nid, "open", reply=text)
        else:
            c.close(nid, "done" if cmd == "done" else "skipped", text, reply=("✅ " if cmd == "done" else "⏭ ") + text)
        print(f"#{nid} {'answered' if cmd == 'reply' else cmd}")
        return 0
    if cmd == "send":
        if not args or not Path(args[0]).exists():
            print(f"error: file not found: {args[0] if args else ''}")
            return 2
        reply = args[args.index("--reply") + 1] if "--reply" in args else None
        caption = args[1] if len(args) > 1 and args[1] != "--reply" else ""
        r = c.send(args[0], caption, reply)
        print(f"sent (message {r.get('message_id', '?')})")
        return 0
    print(f"unknown command: {cmd}")
    return 2
