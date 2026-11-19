"""Alerts to the owner when the unattended pipeline breaks: a post that fails or can't go out, a film or posts job that
fails or gives up, a day with fewer films than planned, a sign-in about to expire.

Delivery: the business's bot (the notes API of jobs.api: a small .txt with the details, the summary as its caption),
else the morning pack's Telegram bot, else only data/publish/<profile>/alerts.log. Every alert is also written to that
log. The same alert goes out at most once per REPEAT_HOURS, so a broken key doesn't message every 30 minutes.
"""
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from .. import config

REPEAT_HOURS = 24
# Lines of an autopost run that mean something went wrong (the rest is "posted", "at 18:30", "dry run" …).
PROBLEM = re.compile(r"exit [1-9]|failed|error|✖|missing|not found|no caption|problems|expire|HTTP \d{3}|"
                     r"not connected|still not on|missed|only \d+ of \d+|TikTok\w*Error|Threads\w*Error", re.I)


def _dir(cfg):
    d = config.ROOT / "data" / "publish" / cfg["name"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def problems(lines):
    return [l for l in lines if l and PROBLEM.search(l) and not l.startswith(("dry run", "perf"))]


def _fresh(cfg, msgs, now):
    """Messages not sent in the last REPEAT_HOURS; remembers the ones returned."""
    f = _dir(cfg) / "alerts-sent.json"
    try:
        sent = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sent = {}
    cutoff = now - timedelta(hours=REPEAT_HOURS)
    sent = {k: v for k, v in sent.items() if datetime.fromisoformat(v) > cutoff}
    out = []
    for m in msgs:
        k = hashlib.sha1(re.sub(r"\d{2}:\d{2}:\d{2}", "", m).encode()).hexdigest()[:16]
        if k not in sent:
            sent[k] = now.isoformat(timespec="seconds")
            out.append(m)
    f.write_text(json.dumps(sent), encoding="utf-8")
    return out


def _deliver(cfg, title, body):
    from .. import notes
    a = notes.api_settings(cfg)
    f = Path(tempfile.gettempdir()) / f"viral-scout-alert-{cfg['name']}.txt"
    f.write_text(body + "\n", encoding="utf-8")
    caption = f"⚠️ {title}\n\n{body}"[:1000]
    if a["url"] and a["secret"]:
        notes.Client(a["url"], a["secret"], a["project"]).send(str(f), caption, tags="alert")
        return "bot"
    from . import core, pack
    mp = core.settings(cfg)["morning_pack"]
    env = {**pack.read_env_file(mp.get("env_file") or core.settings(cfg)["env_file"]), **os.environ}
    token, chat = env.get(mp["token_env"], ""), (env.get(mp["chat_env"], "") or "").split(",")[0].strip()
    if token and chat:
        pack._telegram(token, "sendMessage", {"chat_id": chat, "text": caption})
        return "telegram"
    return "log only"


def alert(cfg, title, lines, now=None, send=None):
    """Send the new ones of `lines` (deduplicated). Returns how it went out, or "" when there was nothing new."""
    now = now or datetime.now()
    lines = [l.strip() for l in lines if l and l.strip()]
    new = _fresh(cfg, lines, now)
    if not new:
        return ""
    body = "\n".join(f"• {l[:400]}" for l in new) + f"\n\nDetails: dashboard → {cfg['name']} → Posting. Logs: data/logs/studio/"
    with (_dir(cfg) / "alerts.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{now:%Y-%m-%d %H:%M} {title}\n{body}\n\n")
    if send is None and os.environ.get("VIRAL_SCOUT_NO_ALERTS") == "1":     # tests: log only, never a real message
        return "log only (VIRAL_SCOUT_NO_ALERTS)"
    try:
        return (send or _deliver)(cfg, f"{cfg.get('display_name') or cfg['name']}: {title}", body)
    except Exception as e:          # an alert that can't go out must not break the job that raised it
        with (_dir(cfg) / "alerts.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{now:%Y-%m-%d %H:%M} (not delivered: {e})\n\n")
        return f"not delivered: {e}"
