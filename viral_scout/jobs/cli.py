"""python -m viral_scout jobs <profile> run <job> [--force] [--dry-run] | list | prompt <job> | install-plan [--json]

  run <job>      one unattended run (Task Scheduler calls this through scripts/studio.ps1). job = ideas|script|notes|film|blog,
                 or post (the morning post pack: no Claude, same as `publish <profile> today`)
  list           the jobs, on/off, today's marker and tries, the lock
  prompt <job>   print the assembled prompt (core + profile instructions); runs nothing
  install-plan   the Task Scheduler tasks this profile wants, and the command the owner runs to register them
"""
import json
import sys
from datetime import datetime

from .. import config
from . import prompts, runner, schedule
from . import settings as S
from .state import Lock, Markers, period_key


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    cmd, rest = argv[1], argv[2:]
    if cmd == "run":
        if not rest:
            print("usage: jobs <profile> run <job>")
            return 2
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
