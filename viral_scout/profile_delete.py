"""Delete a business: move everything viral-scout keeps for it to data/deleted/<name>-<time>/ and remove its tasks.

  python -m viral_scout profile <name> delete --confirm <name>       (the dashboard's Settings → Delete business)

Nothing is erased: the profile, its database, run data, frames, checks, scores, idea batches, paid ads data and the
dashboard's copies are moved into one folder, so a mistake is undone by moving them back (and `export`). Its
Windows tasks ("viral-scout <name>" and "viral-scout <name>.<job>") are removed so nothing runs for it any more.
Not touched: notes in the Obsidian vault, the business's ideas in the bot service, and its keys in .env (shared).
Only exact file names are moved, so deleting "test" never touches a "test-2" business.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from . import config

FILES = ["{n}.sqlite", "{n}.sqlite-wal", "{n}.sqlite-shm", "{n}-latest.json", "{n}-ads-latest.json", "{n}-ads-extra.json",
         "{n}-demand.json", "{n}-demand-raw.json", "{n}-perf-latest.json", "paid/{n}.json", "paid/{n}-log.jsonl",
         "scores/{n}.json", "jobs/{n}.json"]
DIRS = ["frames/{n}", "checks/{n}", "ideas/{n}", "ad-media/{n}", "jobs/{n}", "video/{n}", "publish/{n}"]
WEB = ["{n}.json", "ads/{n}.json", "demand/{n}.json", "perf/{n}.json", "paid/{n}.json"]


def _tasks(name):
    """Task Scheduler tasks of this business (Windows only)."""
    if sys.platform != "win32":
        return []
    ps = shutil.which("pwsh") or shutil.which("powershell")
    script = config.ROOT / "scripts" / "tasks.ps1"
    if not ps or not script.exists():
        return []
    r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "list"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    try:
        tasks = json.loads(r.stdout).get("tasks") or []
    except ValueError:
        return []
    return [t["name"] for t in tasks if t.get("profile") == name or t.get("name") in (f"viral-scout {name}",)
            or str(t.get("name", "")).startswith(f"viral-scout {name}.")]


def _remove_task(task):
    ps = shutil.which("pwsh") or shutil.which("powershell")
    r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(config.ROOT / "scripts" / "tasks.ps1"),
                        "remove", "-Name", task], capture_output=True, text=True, encoding="utf-8", timeout=120)
    return r.returncode == 0


def delete(name, confirm, remove_tasks=True, web_data=None):
    if confirm != name:
        raise ValueError(f"type the business name exactly to confirm ({name})")
    prof = config.PROFILES / f"{name}.yaml"
    if not prof.exists():
        raise ValueError(f"no business called {name}")
    from .export import WEB_DATA
    web = Path(web_data or WEB_DATA)
    data = config.ROOT / "data"
    dest = data / "deleted" / f"{name}-{datetime.now():%Y%m%d-%H%M%S}"
    moved = []

    def move(src, rel):
        if src.exists():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(target))
            moved.append(rel)

    tasks = _tasks(name) if remove_tasks else []
    removed = [t for t in tasks if _remove_task(t)]
    move(prof, f"profiles/{name}.yaml")
    for pat in FILES + DIRS:
        rel = pat.format(n=name)
        move(data / rel, f"data/{rel}")
    for pat in WEB:
        rel = pat.format(n=name)
        move(web / rel, f"web/data/{rel}")
    (dest / "DELETED.md").write_text(
        f"# {name}, deleted {datetime.now():%Y-%m-%d %H:%M}\n\nTo restore: move these back to the repo (same paths), "
        f"then `python -m viral_scout export` and re-register its tasks on the Schedule page.\n\nTasks removed: "
        f"{', '.join(removed) or 'none'}\n\nMoved:\n" + "".join(f"- {m}\n" for m in moved), encoding="utf-8")
    try:                                   # the Businesses page and index without it
        from .export import export_all
        export_all()
    except Exception:  # noqa: BLE001 (the files are moved; the next export catches up)
        pass
    return {"ok": True, "deleted": name, "folder": str(dest), "moved": moved, "tasks_removed": removed,
            "tasks_left": [t for t in tasks if t not in removed]}
