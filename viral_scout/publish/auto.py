"""The posting job: `python -m viral_scout publish <profile> autopost [--dry-run]` (task "viral-scout <p>.autopost",
every 30 min). No Claude: it only posts what the film and posts jobs queued, through the official APIs.

Films (ready-to-post.md): a row whose date is today (or up to publish.late_days back, when the PC was off) and whose
time came (the n-th row of a date posts at publish.times[n]) goes to every platform with auto_post: true, if it is
approved (✅, or `✅ auto` when publish.approval is auto) and not stopped (🛑). Caption: caption.md in the film folder.
Text/photo posts (Social/post-queue.md): the same, at publish.posts.times, to publish.posts.platforms.
Each platform posts once (published.jsonl); when every auto platform is done the row becomes `📤 posted <date>`.
Then the comment challenges: see replies.py.
"""
import json
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import config
from ..jobs.state import Lock
from . import cli as pcli
from . import connect, core

NODE = Path(__file__).resolve().parent / "node"


def data_dir(cfg):
    d = config.ROOT / "data" / "publish" / cfg["name"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def published(cfg):
    """[(platform, key)] already posted: key = the video file name or the post file name."""
    f = data_dir(cfg) / "published.jsonl"
    out = set()
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            out.add((r.get("platform"), r.get("video") or r.get("post")))
    return out


def set_status(path, match, status):
    """Replace the last cell of the queue line that contains `match` (the mp4 or post file path)."""
    p = Path(path)
    lines = p.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", line) and match in line:
            cells = line.rstrip().rstrip("|").split("|")
            cells[-1] = f" {status} "
            lines[i] = "|".join(cells) + "|"
            break
    p.write_text("\n".join(lines), encoding="utf-8")


def due(s, rows, row, now, times, late_days):
    """None when the row should post now, else why not."""
    try:
        d = date.fromisoformat(row["date"])
    except ValueError:
        return "bad date"
    today = now.date()
    if core.posted(row):
        return "posted"
    if core.stopped(row):
        return "stopped"
    if d > today:
        return "later"
    if d < today - timedelta(days=late_days):
        return "missed"
    t = core.post_time(s, rows, row, times)
    if d == today and now.strftime("%H:%M") < t:
        return f"at {t}"
    if not core.approved(row) and s["approval"] != "auto":       # auto: every queued row that is not 🛑 counts
        return "waiting for approval"
    return None


def caption_for(video):
    v = Path(video)
    film = v.parent.parent if v.parent.name == "out" else v.parent
    return next((f for f in (film / "caption.md", v.with_suffix(".caption.md")) if f.exists()), None)


def _node(cmd, cfg, dry):
    if dry:
        return 0, "dry run: " + " ".join(cmd[:4]) + " …"
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=pcli.node_env(cfg), cwd=str(NODE))
    return p.returncode, (p.stdout + p.stderr).strip()


def _remember_challenge(cfg, cap, key, before):
    """After a post: every new published.jsonl line for `key` gets the caption's challenge (replies.py reads it)."""
    if not (cap.get("challenge") or cap.get("mentions")):
        return
    f = data_dir(cfg) / "published.jsonl"
    out = data_dir(cfg) / "challenges.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        for line in f.read_text(encoding="utf-8").splitlines()[before:]:
            r = json.loads(line)
            if (r.get("video") or r.get("post")) == key:
                fh.write(json.dumps({**r, "challenge": cap.get("challenge", ""), "mentions": cap.get("mentions", 0),
                                     "reward": cap.get("reward", "")}, ensure_ascii=False) + "\n")


def _count(cfg):
    f = data_dir(cfg) / "published.jsonl"
    return len(f.read_text(encoding="utf-8").splitlines()) if f.exists() else 0


def films(cfg, now, dry=False, run_node=None):
    s = core.settings(cfg)
    auto = [p for p in s["platforms"] if core.auto_post(s, p)]
    out = []
    if not auto:
        return out
    rows = core.read_queue(s["queue"])
    done = published(cfg)
    for row in rows:
        why = due(s, rows, row, now, s["times"], int(s.get("late_days", 1)))
        if why:
            if why == "waiting for approval":
                out.append(f"film {row['date']} {row['title']}: {why}")
            continue
        video = Path(row["video"])
        cap = caption_for(video) if row["video"] else None
        if not video.exists() or not cap:
            out.append(f"film {row['date']} {row['title']}: {'video not found' if not video.exists() else 'no caption.md in the film folder'}")
            continue
        todo = [p for p in auto if (p, video.name) not in done]
        if todo:
            pp = pcli.post_plan(cfg, video, cap.read_text(encoding="utf-8"), todo)
            if pp["problems"]:
                out.append(f"film {row['title']}: caption problems: {'; '.join(pp['problems'])}")
                continue
            if not pp["auto"]:
                out.append(f"film {row['title']}: keys missing for {', '.join(pp['missing'])}")
                continue
            args = type("A", (), {"dry_run": dry, "at": None, "video_url": None, "cover_url": None, "cover": None})()
            before = _count(cfg)
            code, log = (run_node or _node)(pcli.node_command(cfg, pp, cap, args), cfg, dry)
            if not dry:
                _remember_challenge(cfg, core.parse_caption(cap.read_text(encoding="utf-8")), video.name, before)
            out.append(f"film {row['title']} → {', '.join(pp['auto'])}: exit {code}" + (f"\n{log[-600:]}" if code else ""))
            done = published(cfg)
        left = [p for p in auto if (p, video.name) not in done]
        if not left and not dry:
            set_status(s["queue"], row["video"], f"📤 posted {now:%Y-%m-%d} (auto)")
        elif left and not todo:
            out.append(f"film {row['title']}: still not on {', '.join(left)}")
    return out


def posts(cfg, now, dry=False, run_node=None):
    s = core.settings(cfg)
    ps = s["posts"]
    plats = [p for p in ps.get("platforms") or [] if p in ("facebook", "linkedin") and core.auto_post(s, p)]
    out = []
    if not ps.get("enabled") or not plats:
        return out
    rows = core.read_posts(s["posts_queue"])
    done = published(cfg)
    for row in rows:
        why = due(s, rows, row, now, ps.get("times") or ["10:00"], int(s.get("late_days", 1)))
        if why:
            if why == "waiting for approval":
                out.append(f"post {row['date']} {row['title']}: {why}")
            continue
        f = Path(row["file"])
        if not f.exists():
            out.append(f"post {row['title']}: file not found {f}")
            continue
        cap = core.parse_caption(f.read_text(encoding="utf-8"))
        todo = [p for p in plats if (p, f.name) not in done]
        if todo:
            cmd = ["node", str(NODE / "post.mjs"), "--caption-file", str(f), "--only", ",".join(todo),
                   "--log", str(data_dir(cfg) / "published.jsonl")]
            if cap["photo"]:
                photo = Path(cap["photo"]) if Path(cap["photo"]).is_absolute() else f.parent / cap["photo"]
                cmd += ["--photo", str(photo)]
            if dry:
                cmd.append("--dry-run")
            before = _count(cfg)
            code, log = (run_node or _node)(cmd, cfg, dry)
            if not dry:
                _remember_challenge(cfg, cap, f.name, before)
            out.append(f"post {row['title']} → {', '.join(todo)}: exit {code}" + (f"\n{log[-600:]}" if code else ""))
            done = published(cfg)
        if not [p for p in plats if (p, f.name) not in done] and not dry:
            set_status(s["posts_queue"], row["file"], f"📤 posted {now:%Y-%m-%d} (auto)")
    return out


def run(cfg, now=None, dry=False, run_node=None, replier=None):
    s = core.settings(cfg)
    now = now or core.now_in(s["timezone"])
    now = now.replace(tzinfo=None) if isinstance(now, datetime) else now
    lock = Lock(data_dir(cfg) / "autopost.lock", 2, f"{cfg['name']}:autopost")
    if not dry and not lock.acquire():
        return "busy: another autopost run is posting"
    try:
        out = films(cfg, now, dry, run_node) + posts(cfg, now, dry, run_node)
        if s["challenges"].get("enabled"):
            from . import replies
            out += (replier or replies.run)(cfg, dry=dry)
        out += connect.expiring(cfg, now.date())
        return "\n".join(out) or "nothing due"
    finally:
        lock.release()
