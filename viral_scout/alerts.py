"""Push alerts to Telegram (official Bot API) when something crosses the profile's thresholds.

  TELEGRAM_BOT_TOKEN  bot token from @BotFather
  TELEGRAM_CHAT_ID    your chat id (send the bot a message, then open
                      https://api.telegram.org/bot<token>/getUpdates and copy message.chat.id)
A profile can point at another env file instead (alerts.env_file), so an existing bot's token isn't copied:
  alerts: {env_file: D:/repo/site/.env.local, token_env: TELEGRAM_BOT_TOKEN, chat_env: TELEGRAM_CHAT_ID}
Each post is alerted once.
"""
import os
import re

import requests

from .report import n, x


def _creds(cfg):
    a = cfg.get("alerts") or {}
    tok, chat = a.get("token_env", "TELEGRAM_BOT_TOKEN"), a.get("chat_env", "TELEGRAM_CHAT_ID")
    vals = {}
    f = a.get("env_file")
    if f and os.path.isfile(f):
        for line in open(f, encoding="utf-8"):
            m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m and m.group(1) in (tok, chat) and m.group(1) not in vals:
                vals[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return os.environ.get(tok) or vals.get(tok), os.environ.get(chat) or vals.get(chat)


def available(cfg):
    t, c = _creds(cfg)
    return bool(t and c)


def pick(cfg, items, store):
    a = cfg.get("alerts") or {}
    min_out, min_rise, min_day = a.get("min_outlier", 10), a.get("min_rise_per_day"), a.get("min_per_day")
    hits = []
    for it in items:
        why = []
        if it.outlier and it.outlier >= min_out and (it.channel_median or it.followers or 0) >= a.get("min_baseline", 1000):
            why.append(f"{x(it.outlier)} usual")
        if min_rise and it.rise_per_day and it.rise_per_day >= min_rise:
            why.append(f"+{n(it.rise_per_day)}/day now")
        if min_day and it.per_day and it.per_day >= min_day and not it.early:
            why.append(f"{n(it.per_day)}/day")
        if why and not store.was_alerted(it.key):
            hits.append((it, why))
    hits.sort(key=lambda h: h[0].weighted + (h[0].rise_per_day or 0) / 1e4, reverse=True)
    return hits[: a.get("max", 5)]


def send(cfg, hits, report_path, errors):
    if not hits:
        return 0
    lines = [f"🔎 viral-scout · {cfg['name']}: {len(hits)} new"]
    for it, why in hits:
        lines.append(f"\n{it.label or '•'} {it.title[:90]}\n{it.channel} · {', '.join(why)}\n{it.url}")
        if it.hook:
            lines.append(f"Hook: “{it.hook[:140]}”")
    lines.append(f"\nReport: {os.path.basename(report_path)}")
    token, chat = _creds(cfg)
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": "\n".join(lines)[:4000],
                                "disable_web_page_preview": True}, timeout=30)
        if not r.ok:
            errors.append(f"telegram: HTTP {r.status_code} {r.text[:150]}")
            return 0
    except requests.RequestException as err:
        errors.append(f"telegram: {err}")
        return 0
    return len(hits)
