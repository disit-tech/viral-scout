"""The Task Scheduler plan for a profile's studio jobs. scripts/schedule-studio.ps1 reads `jobs <p> install-plan --json`.

Task names: "viral-scout <profile>.<job>" (the dashboard's Schedule page and scripts/tasks.ps1 accept that shape).
Daily jobs repeat hourly from their time until retry_until: daily triggers miss days when the PC sleeps, and the
.done marker makes the extra runs exit at once.
"""
from pathlib import Path

from .. import config
from . import settings as S

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _hours_between(a, b):
    """Repetition window for hourly tries from a up to and including b. Task Scheduler's window end is exclusive,
    so one hour more: 07:15 → 20:00 gives 13 h (last try 19:15; 12 h dropped it), 06:00 → 22:00 gives 17 h (22:00 runs)."""
    ha, ma = map(int, a.split(":"))
    hb, mb = map(int, b.split(":"))
    d = hb * 60 + mb - ha * 60 - ma
    return d // 60 + 1 if d >= 60 else 0


def _days(v):
    if not v or v == "daily":
        return None
    items = v if isinstance(v, list) else [x.strip() for x in str(v).split(",")]
    bad = [d for d in items if d not in DAYS]
    if bad:
        raise ValueError(f"bad day(s) {bad}: use daily or {', '.join(DAYS)}")
    return items


def plan(cfg):
    from ..publish import core as pub
    s, p = S.settings(cfg), cfg["name"]
    tasks = []
    for job in S.JOBS:
        j = s[job]
        if not j["enabled"]:
            continue
        if job == "notes":
            trig = {"type": "every", "minutes": int(j["every_minutes"])}
            why = f"every {j['every_minutes']} min; starts Claude only when a note waits"
        else:
            days = _days(j.get("days"))
            rep = _hours_between(j["at"], j.get("retry_until") or j["at"])
            trig = {"type": "weekly" if days else "daily", "days": days, "at": j["at"], "repeat_minutes": 60 if rep else 0, "repeat_hours": rep}
            why = (f"{'every ' + ', '.join(days) if days else 'daily'} {j['at']}" + (f", hourly until {j['retry_until']}" if rep else "")
                   + (f"; {S.runs_per_day(cfg, job)} per {j['period']}" if S.runs_per_day(cfg, job) > 1 else f"; once per {j['period']}")
                   + (f", max {j['max_tries']} tries" + (" each" if S.runs_per_day(cfg, job) > 1 else "") if j.get("max_tries") else ""))
        tasks.append({"name": f"viral-scout {p}.{job}", "profile": p, "job": job, "trigger": trig, "time_limit_hours": s["time_limit_hours"],
                      "args": f"-Profile {p} -Job {job}", "what": why})
    mp = pub.settings(cfg)["morning_pack"]
    if mp.get("enabled"):
        at = f"{int(mp['hour']):02d}:00"
        tasks.append({"name": f"viral-scout {p}.post", "profile": p, "job": "post",
                      "trigger": {"type": "daily", "days": None, "at": at, "repeat_minutes": 60, "repeat_hours": _hours_between(at, "21:00")},
                      "time_limit_hours": 1, "args": f"-Profile {p} -Job post",
                      "what": f"morning post pack daily {at} (no Claude; once a day, marker)"})
    ps = pub.settings(cfg)
    if any(pub.auto_post(ps, x) for x in ps["platforms"] + list((ps["posts"] or {}).get("platforms") or [])):
        tasks.append({"name": f"viral-scout {p}.autopost", "profile": p, "job": "autopost",
                      "trigger": {"type": "every", "minutes": 30}, "time_limit_hours": 1, "args": f"-Profile {p} -Job autopost",
                      "what": "every 30 min: posts due films and posts through the official APIs, answers challenge comments (no Claude)"})
    return tasks


def install_command(profile, remove=False):
    script = (Path(config.ROOT) / "scripts" / "schedule-studio.ps1").as_posix()
    return f'pwsh -NoProfile -ExecutionPolicy Bypass -File "{script}" -Profile {profile}' + (" -Remove" if remove else "")
