"""Lock file, .done markers and the tries counter (port of solar's site/scripts/jobs/run.ps1). No Claude, no network."""
import json
import os
import time
from datetime import datetime
from pathlib import Path


class Lock:
    """One Claude job at a time. A lock older than `stale_hours` is stale (a crashed run) and is taken over.

    with Lock(path) as got:  →  got is False when another live job holds it (then do nothing).
    """

    def __init__(self, path, stale_hours=3, owner=""):
        self.path, self.stale, self.owner, self.held = Path(path), stale_hours * 3600, owner, False

    def age(self):
        try:
            return time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return None

    def acquire(self):
        a = self.age()
        if a is not None and a >= self.stale:
            self.path.unlink(missing_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"owner": self.owner, "pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds")}, f)
        self.held = True
        return True

    def release(self):
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False

    def info(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()


def period_key(period, now=None):
    """day → 2026-11-15, week → 2026-W46 (ISO week), None → None."""
    now = now or datetime.now()
    if period == "day":
        return now.strftime("%Y-%m-%d")
    if period == "week":
        y, w, _ = now.isocalendar()
        return f"{y}-W{w:02d}"
    return None


class Markers:
    """<state>/<job>-<key>.done and <job>-<key>.tries for one profile."""

    def __init__(self, state_dir, job, key):
        self.dir, self.job, self.key = Path(state_dir), job, key

    @property
    def done_file(self):
        return self.dir / f"{self.job}-{self.key}.done"

    @property
    def tries_file(self):
        return self.dir / f"{self.job}-{self.key}.tries"

    def done(self):
        return self.key is not None and self.done_file.exists()

    def mark_done(self, text="done"):
        if self.key is not None:
            self.done_file.write_text(text, encoding="utf-8")

    def tries(self):
        try:
            return int(self.tries_file.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            return 0

    def add_try(self):
        n = self.tries() + 1
        if self.key is not None:
            self.tries_file.write_text(str(n), encoding="utf-8")
        return n
