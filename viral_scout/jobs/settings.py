"""The profile's jobs: block over the defaults. Every job is off until the profile turns it on."""
from pathlib import Path

from .. import config

JOBS = ("ideas", "script", "notes", "film", "blog")

# period: one success per day/week (marker); None = no marker (notes runs whenever there is work).
# done_by: who writes the .done marker. "runner" = on exit code 0; "claude" = the prompt's last step (film: only
# when a film was really delivered, so a run that broke halfway is retried).
# retry_until: the task repeats hourly from `at` until this time (daily triggers miss days when the PC sleeps).
JOB_DEFAULTS = {
    "ideas": {"enabled": False, "at": "08:00", "days": "daily", "retry_until": "20:00", "period": "day", "done_by": "runner", "max_tries": 2},
    "script": {"enabled": False, "at": "08:30", "days": "daily", "retry_until": "20:00", "period": "day", "done_by": "runner", "max_tries": 2},
    "notes": {"enabled": False, "every_minutes": 15, "period": None, "done_by": None, "max_tries": 0},
    "film": {"enabled": False, "at": "06:00", "days": "daily", "retry_until": "22:00", "period": "day", "done_by": "claude", "max_tries": 2},
    "blog": {"enabled": False, "at": "08:45", "days": "Monday", "retry_until": "20:00", "period": "week", "done_by": "runner", "max_tries": 2},
}

DEFAULTS = {
    "cwd": "",                 # where Claude runs (default: the viral-scout repo)
    "add_dirs": [],            # extra --add-dir folders (the vault is always added)
    "language": "English",     # language of messages to the owner
    "owner": "the owner",      # how prompts name the person who approves
    "delivery": "none",        # telegram (via the ideas API / service) | none (results stay in the vault)
    "api": {},                 # notes/ideas API: {url_env, secret_env, env_file, project}; falls back to the ideas: block
    "notes_command": "",       # alternative notes backend: a CLI with the same verbs (e.g. solar's notes.mjs)
    "permission_mode": "acceptEdits",
    "lock_hours": 3,
    "time_limit_hours": 3,     # Task Scheduler ExecutionTimeLimit
    "allowed_tools": {},       # {all: [...], film: [...]}: extra --allowedTools per job
    "instructions": {},        # {film: "extra lines for this job"} on top of the studio.instructions note
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def settings(cfg):
    raw = cfg.get("jobs") or {}
    s = _merge(DEFAULTS, {k: v for k, v in raw.items() if k not in JOBS})
    for j in JOBS:
        v = raw.get(j)
        if isinstance(v, dict) and True in v:      # YAML 1.1 reads a bare `on:` key as True
            v = {**{k: x for k, x in v.items() if k is not True}, "enabled": bool(v[True])}
        s[j] = _merge(JOB_DEFAULTS[j], v if isinstance(v, dict) else {"enabled": bool(v)} if j in raw else {})
    s["cwd"] = s["cwd"] or str(config.ROOT)
    ideas = cfg.get("ideas") if isinstance(cfg.get("ideas"), dict) else {}
    # The older daily idea runs (scripts/ideas-daily.ps1) read ideas.daily.add_dirs: the jobs get the same folders.
    daily = ideas.get("daily") if isinstance(ideas.get("daily"), dict) else {}
    if not s["add_dirs"] and isinstance(daily.get("add_dirs"), list):
        s["add_dirs"] = daily["add_dirs"]
    # The ideas: block keeps its API settings under ideas.api (docs/ideas.md); the project slug sits on ideas itself.
    ideas_api = ideas.get("api") if isinstance(ideas.get("api"), dict) else {}
    found = {k: ideas_api.get(k) or ideas.get(k) for k in ("url_env", "secret_env", "env_file")}
    found["project"] = ideas.get("project")
    s["api"] = {"url_env": "IDEAS_SITE_URL", "secret_env": "IDEAS_API_SECRET", "env_file": "", "project": cfg["name"],
                **{k: v for k, v in found.items() if v}, **s["api"]}
    return s


def enabled(cfg):
    s = settings(cfg)
    return [j for j in JOBS if s[j]["enabled"]]


def studio(cfg):
    st = cfg.get("studio") or {}
    return {"brand": st.get("brand", cfg["name"]), "vault_dir": st.get("vault_dir", ""), "instructions": st.get("instructions", ""),
            "compliance": st.get("compliance", ""), "cta": st.get("cta") or {}}


def state_dir(cfg):
    d = config.ROOT / "data" / "jobs" / cfg["name"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir():
    d = config.ROOT / "data" / "logs" / "studio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def lock_path():
    """One lock for the whole PC: a film render and a notes run of two profiles must not overlap."""
    d = config.ROOT / "data" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "claude.lock"


def vault():
    import os
    v = os.environ.get("OBSIDIAN_VAULT", "")
    if not v and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, "OBSIDIAN_VAULT")[0]
        except OSError:
            v = ""
    return v


def exists(p):
    return bool(p) and Path(p).exists()
