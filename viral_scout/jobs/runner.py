"""Run one studio job for a profile (port of solar's site/scripts/jobs/run.ps1).

Order: job on? → already done this day/week? → lock free (one Claude job on the PC; stale after lock_hours) →
work waiting (notes only) → tries left (max_tries per day/week) → `claude -p` with the assembled prompt on stdin,
--permission-mode acceptEdits, a narrow --allowedTools, --add-dir <vault> → log → .done on success (done_by: runner).
"""
import os
import shutil
import subprocess
from datetime import datetime

from .. import config
from . import prompts
from . import settings as S
from .state import Lock, Markers, period_key


def claude_command(cfg, job, claude="claude"):
    s = S.settings(cfg)
    cmd = [claude, "-p", "--permission-mode", s["permission_mode"], "--allowedTools", *prompts.allowed_tools(cfg, job)]
    v = S.vault()
    for d in ([v] if v else []) + list(s.get("add_dirs") or []) + ([S.studio(cfg)["vault_dir"]] if S.studio(cfg)["vault_dir"] else []):
        if d and d not in cmd:
            cmd += ["--add-dir", d]
    return cmd


def _env():
    """The job's environment: viral_scout importable from any cwd (a business repo), UTF-8 output."""
    env = dict(os.environ)
    paths = [str(config.ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _execute(cmd, prompt, log, cwd):
    with open(log, "a", encoding="utf-8") as fh:
        p = subprocess.run(cmd, input=prompt, stdout=fh, stderr=subprocess.STDOUT, text=True, encoding="utf-8", cwd=cwd,
                           env=_env())
    return p.returncode


def run(cfg, job, now=None, force=False, dry=False, execute=None, pending=None, which=shutil.which):
    """Returns (exit code, message). execute(cmd, prompt, log_path, cwd) and pending(cfg) are injectable for tests."""
    if job not in S.JOBS:
        return 2, f"unknown job {job!r} (jobs: {', '.join(S.JOBS)})"
    s = S.settings(cfg)
    j = s[job]
    now = now or datetime.now()
    if not j["enabled"] and not force:
        return 0, f"{job} is off for {cfg['name']} (jobs.{job}.enabled)"
    m = Markers(S.state_dir(cfg), job, period_key(j["period"], now))
    log = S.log_dir() / f"{cfg['name']}-{job}-{now:%Y-%m-%d}.log"

    def note(msg):
        if not dry:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%H:%M:%S} {msg}\n")
        return msg

    if m.done() and not force:
        return 0, f"{job} already done ({m.key})"
    lock = Lock(S.lock_path(), s["lock_hours"], f"{cfg['name']}:{job}")
    if not lock.acquire():
        return 0, f"busy: {(lock.info() or {}).get('owner', 'another job')} holds the lock"
    try:
        if job == "notes":
            from .. import notes
            n = (pending or notes.pending)(cfg)
            if n <= 0:
                return 0, "nothing waiting"
            note(f"=== {n} waiting")
        if j.get("max_tries") and m.key is not None and m.tries() >= j["max_tries"] and not force:
            return 0, f"{job}: {m.tries()} tries used ({m.key}), waiting for the next period"
        claude = which("claude")
        if not claude and not dry:
            return 1, note("ERROR: claude CLI not found on PATH")
        prompt = prompts.assemble(cfg, job, now, str(m.done_file) if j["done_by"] == "claude" else "")
        cmd = claude_command(cfg, job, claude or "claude")
        if dry:
            return 0, "dry run, would start (prompt on stdin, cwd " + s["cwd"] + "):\n  " + " ".join(
                f'"{c}"' if " " in c else c for c in cmd) + f"\n  prompt: {len(prompt)} characters"
        if m.key is not None and j.get("max_tries"):
            m.add_try()
        note(f"=== job {job} start (try {m.tries() or 1})")
        code = (execute or _execute)(cmd, prompt, log, s["cwd"])
        if code == 0 and j["done_by"] == "runner":
            m.mark_done(now.isoformat(timespec="seconds"))
        note(f"=== job {job} done (exit {code})")
        return code, f"{job} exit {code}, log {log}"
    finally:
        lock.release()
