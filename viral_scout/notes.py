"""Owner notes: replies from the Telegram group → work for the notes job (port of solar's site/scripts/notes.mjs).

  python -m viral_scout notes <profile> [list] [--brief] | all | pending
  python -m viral_scout notes <profile> reply|done|skip <id> "text"
  python -m viral_scout notes <profile> send <file> "caption" [--reply <id>] [--tags "film idea92"]
  python -m viral_scout notes <profile> direct          can files go straight to Telegram? (sends nothing)

Backends (jobs: block of the profile):
  api      (default) the ideas API / service: {url}/api/notes, "Authorization: Bearer <secret>", ?project=<project>
             GET  ?status=new | ?status=all&limit=20 → {notes: [...]}     GET ?pending=1 → {pending: n}
             PATCH {id, project, status: done|skipped|open, result?, reply?}  (reply = answer in the note's thread)
             POST  multipart: project, caption, reply_to?, file → {message_id}
             POST  JSON {project, prepare: true, name, caption?, tags?, reply_to?} → {bot_id, chat_id, method, field,
                   caption, reply_parameters?}: how the service would send that file, without sending anything
           URL and secret come from the env vars named in jobs.api (url_env, secret_env), the env file jobs.api.env_file
           or the ideas: block. A note is {id, created_at, from, kind, status, text, about, file_url, result}.
  command  jobs.notes_command: a CLI with the same verbs (e.g. "node D:/repo/solar-site/site/scripts/notes.mjs");
           arguments are passed through unchanged.

Files go straight to the Telegram Bot API from this PC when the token of the service's video bot is here
(jobs.api.token_env, default: the morning pack's token_env). A Vercel function takes request bodies up to ~4.5 MB and
the Bot API takes uploads up to 50 MB, so a 25 MB film master reaches the group as it is. The service still decides
the chat, the caption (header and tags) and the reply target (`prepare`, no side effects), and its bot id must match
the token's. Without that token, files up to ~4 MB go through the service as before. A video over 49 MB goes as a
smaller preview (ffmpeg), with the master's path in the caption.
Retries: once, and only when the request can't have arrived (the connection or the upload failed, or HTTP 429). A
timeout while waiting for the answer is not resent: the message may be in the group already.
The token never appears in output or errors.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import config

SERVICE_MAX = 4_000_000            # bytes a file may have to go through the service (Vercel: ~4.5 MB per request body)
TELEGRAM_MAX = 49 * 1024 * 1024    # Bot API uploads: 50 MB; a little room for the multipart overhead
RETRY_WAIT = 3


def api_settings(cfg):
    from .jobs import settings as S
    from .publish import core as pub
    from .publish.pack import read_env_file
    s = S.settings(cfg)
    a = s["api"]
    ps = pub.settings(cfg)
    mp = ps["morning_pack"]
    env = {**read_env_file(ps["env_file"]), **read_env_file(mp.get("env_file")), **read_env_file(a.get("env_file")),
           **os.environ}
    token_env, chat_env = a.get("token_env") or mp["token_env"], a.get("chat_env") or mp["chat_env"]
    ideas = cfg.get("ideas") if isinstance(cfg.get("ideas"), dict) else {}
    return {"url": (env.get(a["url_env"], "") or "").rstrip("/"), "secret": env.get(a["secret_env"], ""), "project": a["project"],
            "command": s.get("notes_command") or "",
            # the direct route to the Bot API (module doc); the token only ever goes into the request URL
            "token": env.get(token_env, "") or "", "token_env": token_env,
            "chat": (env.get(chat_env, "") or "").split(",")[0].strip(), "header": ideas.get("header") or ""}


def client(cfg, opener=None):
    """The notes client of a profile, with the direct Telegram route when its bot token is set."""
    from . import hashtags
    a = api_settings(cfg)
    direct = {"token": a["token"], "chat": a["chat"], "header": a["header"], "token_env": a["token_env"],
              "tags": lambda kind, extra: hashtags.line(cfg, kind, *extra)} if a["token"] else None
    return Client(a["url"], a["secret"], a["project"], opener, direct=direct)


class NotSent(RuntimeError):
    """The request can't have reached the server (it failed before it was fully sent)."""


def _kind(name):
    n = name.lower()
    return "video" if re.search(r"\.(mp4|mov|m4v)$", n) else "photo" if re.search(r"\.(jpe?g|png|webp)$", n) else "document"


METHOD = {"video": "sendVideo", "photo": "sendPhoto", "document": "sendDocument"}
KIND_TAG = {"video": "video", "photo": "image", "document": "file"}


def _multipart(fields, file_field=None, file=None):
    b = uuid.uuid4().hex
    body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items())
    if file_field:
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{Path(file).name}\"\r\n"
                 "Content-Type: application/octet-stream\r\n\r\n").encode() + Path(file).read_bytes() + f"\r\n--{b}--\r\n".encode()
    else:
        body += f"--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"


def preview(file, limit=TELEGRAM_MAX, run=None):
    """A smaller copy of a video for Telegram (≤ limit), or None when ffmpeg is missing or can't get it small enough."""
    if run is None:
        if not shutil.which("ffmpeg"):
            return None
        run = subprocess.run
    out = Path(tempfile.gettempdir()) / f"{Path(file).stem}-preview.mp4"
    for height, crf in ((1280, 26), (960, 30), (720, 34)):
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(file), "-vf", f"scale=-2:{height}", "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", str(crf), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)],
                capture_output=True, text=True)
        if r.returncode == 0 and out.exists() and out.stat().st_size <= limit:
            return out
    return None


class Client:
    """HTTP client for the notes contract above. `opener(req) -> (status, bytes)` can be injected (tests); it carries
    the direct Bot API calls too. direct = {token, chat, header, token_env, tags(kind, extra)} or None."""

    def __init__(self, url, secret, project, opener=None, direct=None, sleep=time.sleep):
        self.url, self.secret, self.project = url, secret, project
        self.opener = opener or self._open
        self.direct, self.sleep = direct, sleep

    @staticmethod
    def _open(req):
        try:
            with urllib.request.urlopen(req, timeout=getattr(req, "timeout_s", 60)) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _clean(self, e):
        t = str(e)
        tok = (self.direct or {}).get("token")
        return t.replace(tok, "<token>") if tok else t

    def _request(self, req, what):
        """Send once; again once only when it can't have arrived (urllib's URLError comes from connecting or sending
        the body; an error while waiting for the answer comes as a plain OSError) or on HTTP 429."""
        for attempt in (1, 2):
            try:
                status, raw = self.opener(req)
            except urllib.error.URLError as e:
                if attempt == 2:
                    raise NotSent(f"{what}: not sent ({self._clean(e.reason)})") from None
                self.sleep(RETRY_WAIT)
                continue
            except OSError as e:          # TimeoutError "The read operation timed out", a reset: it may have arrived
                raise RuntimeError(f"{what}: no answer ({self._clean(e) or type(e).__name__}); not resent, "
                                   "it may have arrived") from None
            if status == 429 and attempt == 1:
                try:
                    wait = int(json.loads(raw or b"{}").get("parameters", {}).get("retry_after", RETRY_WAIT))
                except (ValueError, AttributeError, TypeError):
                    wait = RETRY_WAIT
                self.sleep(min(max(wait, 1), 30))
                continue
            return status, raw

    def _call(self, method, query=None, body=None, ctype="application/json", timeout=60):
        if not self.url or not self.secret:
            raise RuntimeError("notes API not configured: set the env vars named in jobs.api (url_env, secret_env)")
        q = urllib.parse.urlencode({"project": self.project, **(query or {})})
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"{self.url}/api/notes?{q}", data=data, method=method,
                                     headers={"Authorization": f"Bearer {self.secret}", "Content-Type": ctype})
        req.timeout_s = timeout
        status, raw = self._request(req, f"notes API {method}")
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

    def prepare(self, name, caption="", reply_to=None, tags=""):
        """How the service would send a file: {bot_id, chat_id, method, field, caption, reply_parameters?}. Sends nothing."""
        return self._call("POST", body={"project": self.project, "prepare": True, "name": name, "caption": caption[:1024],
                                        **({"reply_to": int(reply_to)} if reply_to else {}), **({"tags": tags} if tags else {})},
                          timeout=30)

    def _local_plan(self, name, caption, tags):
        """The service's plan rebuilt here (header from ideas.header, tags like the service), for when the service
        can't be asked. No reply target: only the service knows the note's message."""
        d = self.direct
        if not d.get("chat"):
            return None
        kind = _kind(name)
        tag_line = d["tags"](KIND_TAG[kind], tags.split())
        header = d.get("header") or ""
        if header and not header.rstrip().endswith("·"):
            header += " · "
        body = f"{header}{caption}".strip()
        return {"bot_id": "", "chat_id": d["chat"], "method": METHOD[kind], "field": kind,
                "caption": f"{body[:1024 - len(tag_line) - 2]}\n\n{tag_line}".strip()}

    def _telegram(self, method, fields, file_field=None, file=None):
        body, ctype = _multipart(fields, file_field, file)
        req = urllib.request.Request(f"https://api.telegram.org/bot{self.direct['token']}/{method}", data=body,
                                     method="POST", headers={"Content-Type": ctype})
        req.timeout_s = 300 if file else 30         # urllib's timeout is per socket read/write, not the whole upload
        status, raw = self._request(req, f"Telegram {method}")
        try:
            res = json.loads(raw or b"{}")
        except ValueError:
            res = {}
        if not res.get("ok"):
            raise RuntimeError(f"Telegram {method}: HTTP {status} {self._clean(res.get('description') or raw[:200])}")
        return res["result"]

    def send(self, file, caption="", reply_to=None, tags=""):
        """tags: extra hashtag words ("film idea92"); the business and the file kind are added.
        Returns {message_id, route: telegram|service, preview?}."""
        size = Path(file).stat().st_size
        if self.direct:
            return self._send_direct(file, size, caption, reply_to, tags)
        if size > SERVICE_MAX:
            raise RuntimeError(f"{Path(file).name} is {size / 1e6:.1f} MB; the service takes files up to "
                               f"{SERVICE_MAX / 1e6:.0f} MB. Put the video bot's token in the env (jobs.api.token_env) "
                               "so files go straight to Telegram.")
        return self._service_upload(file, caption, reply_to, tags)

    def _service_upload(self, file, caption, reply_to, tags):
        fields = {"project": self.project, "caption": caption[:1024], **({"reply_to": str(reply_to)} if reply_to else {}),
                  **({"tags": tags} if tags else {})}
        body, ctype = _multipart(fields, "file", file)
        return {**self._call("POST", body=body, ctype=ctype, timeout=120), "route": "service"}

    def _send_direct(self, file, size, caption, reply_to, tags):
        name, small = Path(file).name, None
        if size > TELEGRAM_MAX:
            if _kind(name) != "video":
                raise RuntimeError(f"{name} is {size / 1e6:.0f} MB, over Telegram's 50 MB")
            small = preview(file)
            if not small:
                raise RuntimeError(f"{name} is {size / 1e6:.0f} MB, over Telegram's 50 MB, and no preview could be made (ffmpeg)")
            caption = f"{caption}\n(preview: the {size / 1e6:.0f} MB master is over Telegram's 50 MB; master: {file})".strip()
        try:
            plan = self.prepare(name, caption, reply_to, tags)
        except RuntimeError as e:
            plan = self._local_plan(name, caption, tags)
            if not plan:
                raise RuntimeError(f"can't ask the service how to send {name} ({e}), and no chat is set for a direct send") from None
            print(f"note: the service didn't answer ({e}); sending with the local header and tags", flush=True)
        if plan.get("bot_id") and plan["bot_id"] != self.direct["token"].split(":")[0]:
            # Another bot would post it, and replies to it would not become notes of the service's video bot.
            if size <= SERVICE_MAX:
                return self._service_upload(file, caption, reply_to, tags)
            raise RuntimeError(f"{self.direct['token_env']} is not the service's video bot (bot {plan['bot_id']}): set "
                               "jobs.api.token_env to the env var that holds that bot's token")
        fields = {"chat_id": plan["chat_id"], **({"caption": plan["caption"]} if plan.get("caption") else {})}
        if plan["field"] == "video":
            fields["supports_streaming"] = "true"
        if plan.get("reply_parameters"):
            fields["reply_parameters"] = json.dumps(plan["reply_parameters"])
        res = self._telegram(plan["method"], fields, plan["field"], small or file)
        return {"message_id": res.get("message_id"), "route": "telegram", **({"preview": str(small)} if small else {})}

    def direct_status(self):
        """Whether files can go straight to Telegram. Sends nothing."""
        if not self.direct:
            return "off: no bot token in the env (jobs.api.token_env); files over 4 MB can't be sent"
        mine = self.direct["token"].split(":")[0]
        try:
            plan = self.prepare("check.mp4")
        except RuntimeError as e:
            return f"unknown: the service didn't answer the prepare call ({e}); direct sends would use the local chat and header"
        if plan.get("bot_id") and plan["bot_id"] != mine:
            return f"mismatch: {self.direct['token_env']} is bot {mine}, the service's video bot is {plan['bot_id']}"
        return f"on: {self.direct['token_env']} is the service's video bot ({mine}), chat {plan.get('chat_id')}"


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
    c = client(cfg)
    cmd = rest[0] if rest and not rest[0].startswith("--") else "list"
    args = rest[1:] if rest and rest[0] == cmd else rest
    if cmd == "pending":
        print(c.pending())
        return 0
    if cmd == "direct":
        print(c.direct_status())
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
        tags = args[args.index("--tags") + 1] if "--tags" in args else ""
        caption = args[1] if len(args) > 1 and not args[1].startswith("--") else ""
        try:
            r = c.send(args[0], caption, reply, tags)
        except RuntimeError as e:
            print(f"error: {e}")
            return 1
        how = r.get("route", "service") + (f", as a preview: {r['preview']}" if r.get("preview") else "")
        print(f"sent (message {r.get('message_id', '?')}, via {how})")
        return 0
    print(f"unknown command: {cmd}")
    return 2
