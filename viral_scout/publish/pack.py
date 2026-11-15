"""Morning post pack (port of solar's site/scripts/post-today.mjs, generic).

Once a day after publish.morning_pack.hour: today's film from the queue, its "Don't / Do" still and its POST.md
(one message per "▶ PLATFORM" block) go to the owner, so they can post from the phone. No Claude involved.
Delivery: telegram (bot token + chat from the env file) or none (the pack is written to data/publish/<profile>/).
Marker: data/jobs/<profile>/post-<date>.done.
"""
import json
import os
import re
import urllib.request
import uuid
from pathlib import Path

from .. import config
from . import core


def read_env_file(path):
    """KEY=VALUE lines (quotes stripped). Missing file → {}."""
    out = {}
    p = Path(path) if path else None
    if not p or not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if m and not line.lstrip().startswith("#"):
            out[m.group(1)] = m.group(2).strip('"')
    return out


def state_dir(cfg):
    d = config.ROOT / "data" / "jobs" / cfg["name"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def build(cfg, day):
    """What would be sent for `day`: a list of messages {kind: video|photo|text, file?, text}. Pure (reads files only)."""
    s = core.settings(cfg)
    rows = core.read_queue(s["queue"])
    row = next((r for r in rows if r["date"] == day), None)
    if not row:
        nxt = sorted((r for r in rows if r["date"] > day), key=lambda r: r["date"])
        tail = f" Next: {nxt[0]['date']} \"{nxt[0]['title']}\"." if nxt else ""
        return row, [{"kind": "text", "text": f"⚠️ {day}: no video queued for today.{tail} Queue: {s['queue']}"}]
    head = (f"📤 POST TODAY ({day}): \"{row['title']}\"\n"
            + ("✅ Approved by you." if core.approved(row) else "👀 Not approved yet: watch it with sound first (or reply with changes).")
            + "\nThe full posting pack follows ↓")
    msgs = []
    video = Path(row["video"]) if row["video"] else None
    if video and video.exists() and video.stat().st_size < 49 * 1024 * 1024:
        msgs.append({"kind": "video", "file": str(video), "text": head[:1024]})
    else:
        msgs.append({"kind": "text", "text": f"{head}\n\n⚠️ Video not found or over 49 MB: {row['video']}"})
    film = None
    if video:
        film = video.parent.parent if video.parent.name == "out" else video.parent
        still = next((film / f for f in ("still.png", "still.jpg") if (film / f).exists()), None)
        if still:
            msgs.append({"kind": "photo", "file": str(still),
                         "text": "🖼 \"Don't / Do\" still → Threads, Instagram Story (+ link sticker), groups. Text in the blocks below."})
    pack = film / "POST.md" if film else None
    if pack and pack.exists():
        text = re.sub(r"^---[\s\S]*?---\s*", "", pack.read_text(encoding="utf-8")).strip()
        for sec in re.split(r"\n\s*\n(?=▶ )", text):
            # {link} in a "▶ INSTAGRAM STORY" block → the CTA link with utm_source=instagram_story, and so on.
            h = re.match(r"▶\s*([A-Za-z]+)(?:\s+(STORY|STORIES))?", sec, re.I)
            plat = (h.group(1).lower() + ("_story" if h.group(2) else "")) if h else "post"
            sec = sec.replace("{link}", core.utm_link(s["link"], plat, film.name, s))
            msgs.extend({"kind": "text", "text": c} for c in core.chunks(sec))
    else:
        msgs.append({"kind": "text", "text": f"⚠️ No POST.md found ({pack}). Captions are in the film's script note."})
    return row, msgs


def _telegram(token, method, fields, file=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    if file:
        kind, path = file
        b = uuid.uuid4().hex
        body = b""
        for k, v in fields.items():
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{kind}\"; filename=\"{Path(path).name}\"\r\n"
                 "Content-Type: application/octet-stream\r\n\r\n").encode() + Path(path).read_bytes() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request(url, data=json.dumps(fields).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read())
    if not res.get("ok"):
        raise RuntimeError(f"{method}: {res.get('description')}")
    return res["result"]


def send(cfg, msgs, sender=None):
    """Deliver the messages. sender(msg) can be injected (tests); default: per publish.morning_pack.delivery."""
    mp = core.settings(cfg)["morning_pack"]
    if sender is None:
        if mp["delivery"] != "telegram":
            out = config.ROOT / "data" / "publish" / cfg["name"]
            out.mkdir(parents=True, exist_ok=True)
            f = out / "morning-pack.txt"
            f.write_text("\n\n-----\n\n".join(f"[{m['kind']}{' ' + m['file'] if m.get('file') else ''}]\n{m['text']}" for m in msgs),
                         encoding="utf-8")
            print(f"delivery: none → {f}")
            return
        env = {**read_env_file(mp.get("env_file") or core.settings(cfg)["env_file"]), **os.environ}
        token, chat = env.get(mp["token_env"], ""), (env.get(mp["chat_env"], "") or "").split(",")[0].strip()
        if not token or not chat:
            raise RuntimeError(f"{mp['token_env']} / {mp['chat_env']} missing (env or publish.morning_pack.env_file)")

        def sender(m):
            if m["kind"] == "text":
                return _telegram(token, "sendMessage", {"chat_id": chat, "text": m["text"], "link_preview_options": {"is_disabled": True}})
            fields = {"chat_id": chat, "caption": m["text"][:1024]}
            if m["kind"] == "video":
                fields["supports_streaming"] = "true"
            return _telegram(token, "sendVideo" if m["kind"] == "video" else "sendPhoto", fields, (m["kind"], m["file"]))
    for m in msgs:
        sender(m)


def today(cfg, day=None, force=False, dry=False, sender=None, now=None):
    """The morning job. Returns a short status line. Dry: prints, sends nothing, writes no marker."""
    s = core.settings(cfg)
    now = now or core.now_in(s["timezone"])
    day = day or now.strftime("%Y-%m-%d")
    marker = state_dir(cfg) / f"post-{day}.done"
    if not dry and not force:
        if marker.exists():
            return f"already sent {day}"
        if now.hour < int(s["morning_pack"]["hour"]):
            return f"before {s['morning_pack']['hour']}:00, nothing to do"
    row, msgs = build(cfg, day)
    if dry:
        for m in msgs:
            print(f"--- {m['kind']}{' ' + m['file'] if m.get('file') else ''}\n{m['text']}")
        return f"dry run: {len(msgs)} message(s) for {day}, nothing sent"
    send(cfg, msgs, sender)
    marker.write_text(row["title"] if row else "none", encoding="utf-8")
    return f"sent {day}: {row['title'] if row else 'no video'}"
