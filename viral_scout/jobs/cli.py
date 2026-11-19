"""python -m viral_scout jobs <profile> run <job> [--force] [--dry-run] | list | prompt <job> | install-plan [--json]

  run <job>      one unattended run (Task Scheduler calls this through scripts/studio.ps1). job = ideas|script|notes|film|blog,
                 or post (the morning post pack: no Claude, same as `publish <profile> today`),
                 or autopost (the posting job: no Claude, same as `publish <profile> autopost`)
  list           the jobs, on/off, today's marker and tries, the lock
  prompt <job>   print the assembled prompt (core + profile instructions); runs nothing
  install-plan   the Task Scheduler tasks this profile wants, and the command the owner runs to register them
  schedule ideas [--enabled 0|1] [--at HH:MM] [--days daily|Monday,...] [--count N]
                 edit jobs.ideas in the profile (comments kept); the dashboard's Schedule page then syncs the tasks
python -m viral_scout jobs --overview   every profile with an ideas: block and its ideas job settings (JSON)
"""
import json
import sys
from datetime import datetime

from .. import config
from . import prompts, runner, schedule
from . import settings as S
from .state import Lock, Markers, period_key


def _dirs(cfg):
    """Folders that belong to a business, lower-case with forward slashes: the Schedule page matches older tasks of
    other repos to a business by their script path (D:/repo/homes-site/scripts/... → the profile with that add_dir)."""
    ideas = cfg.get("ideas") if isinstance(cfg.get("ideas"), dict) else {}
    daily = ideas.get("daily") if isinstance(ideas.get("daily"), dict) else {}
    jobs = cfg.get("jobs") if isinstance(cfg.get("jobs"), dict) else {}
    st = cfg.get("studio") if isinstance(cfg.get("studio"), dict) else {}
    found = [*(daily.get("add_dirs") or []), *(jobs.get("add_dirs") or []), jobs.get("cwd"), st.get("vault_dir")]
    import re
    m = re.match(r"(.*?[\\/]projects[\\/][^\\/]+)", str(cfg.get("output_dir") or ""))   # the vault project folder
    if m:
        found.append(m.group(1))
    out = []
    for d in found:
        if isinstance(d, str) and d.strip() and "${" not in d:
            d = d.replace("\\", "/").rstrip("/").lower()
            if d not in out and "/.claude/skills" not in d:       # a shared skill folder says nothing about the business
                out.append(d)
    return out


def overview():
    """Every profile: its folders (for grouping tasks by business) and, with an ideas: block, the ideas job settings
    (the Schedule page's Idea generator)."""
    out = []
    for p in sorted(config.ROOT.joinpath("profiles").glob("*.yaml")):
        if p.stem.startswith(("_", "example-")):
            continue
        try:
            cfg = config.load(p.stem)
        except Exception as e:                    # a broken profile must not hide the others
            out.append({"profile": p.stem, "error": str(e)[:200]})
            continue
        base = {"profile": p.stem, "name": cfg.get("display_name") or p.stem, "dirs": _dirs(cfg)}
        if not isinstance(cfg.get("ideas"), dict):
            out.append({**base, "has_ideas": False})
            continue
        raw = (cfg.get("jobs") or {}).get("ideas")
        j = S.settings(cfg)["ideas"]
        daily = cfg["ideas"].get("daily") if isinstance(cfg["ideas"].get("daily"), dict) else {}
        has = isinstance(raw, dict)
        out.append({**base, "has_ideas": True, "configured": has, "enabled": bool(j["enabled"]),
                    # Not set up yet: suggest the older daily run's time and count.
                    "at": j["at"] if has and "at" in raw else daily.get("at", j["at"]),
                    "days": j.get("days") or "daily", "retry_until": j.get("retry_until"),
                    "count": int(j["count"]) if has and "count" in raw else int(daily.get("count", 5)),
                    "delivery": S.settings(cfg)["delivery"]})
    return out


def set_ideas(profile, rest):
    """jobs <profile> schedule ideas [--enabled 0|1] [--at HH:MM] [--days daily|Monday,Thursday] [--count N]
    `profile` is the FILE name (profiles/<profile>.yaml), never cfg["name"]: a profile's name: line can differ."""
    from .. import profile_edit
    opts = dict(zip(rest[0::2], rest[1::2]))
    patch = {}
    if "--enabled" in opts:
        patch["jobs.ideas.enabled"] = opts["--enabled"] == "1"
    if "--at" in opts:
        patch["jobs.ideas.at"] = opts["--at"]
    if "--days" in opts:
        patch["jobs.ideas.days"] = opts["--days"]
    if "--count" in opts:
        patch["jobs.ideas.count"] = opts["--count"]
    if not patch:
        raise ValueError("nothing to set")
    return profile_edit.set_fields(profile, patch)


def main(argv):
    if argv[:1] == ["--overview"]:
        print(json.dumps(overview(), ensure_ascii=False))
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    cmd, rest = argv[1], argv[2:]
    if cmd == "run":
        if not rest:
            print("usage: jobs <profile> run <job>")
            return 2
        if rest[0] == "autopost":
            from ..publish import auto
            print(auto.run(cfg, dry="--dry-run" in rest))
            return 0
        if rest[0] == "post":
            from ..publish import pack
            print(pack.today(cfg, dry="--dry-run" in rest, force="--force" in rest))
            return 0
        code, msg = runner.run(cfg, rest[0], force="--force" in rest, dry="--dry-run" in rest)
        print(msg)
        return code
    if cmd == "prompt":
        if not rest or rest[0] not in S.JOBS:
            print(f"usage: jobs <profile> prompt {'|'.join(S.JOBS)}")
            return 2
        sys.stdout.write(prompts.assemble(cfg, rest[0]))
        print("\n--- allowed tools:", " ".join(prompts.allowed_tools(cfg, rest[0])))
        return 0
    if cmd == "list":
        s = S.settings(cfg)
        now = datetime.now()
        for j in S.JOBS:
            m = Markers(S.state_dir(cfg), j, period_key(s[j]["period"], now))
            print(f"{j:<7} {'on ' if s[j]['enabled'] else 'off'}  done: {'yes' if m.done() else 'no ' if m.key else '-  '}  "
                  f"tries: {m.tries()}/{s[j].get('max_tries') or '-'}")
        info = Lock(S.lock_path()).info()
        print("lock:", f"held by {info['owner']} since {info['started']}" if info else "free")
        return 0
    if cmd == "schedule":
        if not rest or rest[0] != "ideas":
            print("usage: jobs <profile> schedule ideas [--enabled 0|1] [--at HH:MM] [--days daily|Monday,...] [--count N]")
            return 2
        try:
            print(json.dumps(set_ideas(argv[0], rest[1:])))
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            return 1
        return 0
    if cmd == "install-plan":
        tasks = schedule.plan(cfg)
        if "--json" in rest:
            print(json.dumps({"profile": cfg["name"], "tasks": tasks}))
            return 0
        if not tasks:
            print(f"no studio jobs are on for {cfg['name']} (jobs.<job>.enabled / publish.morning_pack.enabled)")
            return 0
        for t in tasks:
            print(f"{t['name']:<34} {t['what']}")
        print("\nClaude may not register scheduled tasks. Run this yourself (add -Paused to register them paused):\n  "
              + schedule.install_command(cfg["name"]))
        print("Remove them again:\n  " + schedule.install_command(cfg["name"], remove=True))
        return 0
    print(__doc__)
    return 2
