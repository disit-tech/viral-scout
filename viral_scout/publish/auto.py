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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .. import config
from ..jobs.state import Lock
from . import cli as pcli
from . import connect, core, threads, tiktok

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


def log_published(cfg, platform, pid, key, **extra):
    f = data_dir(cfg) / "published.jsonl"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "platform": platform, "id": pid,
                             "video": key, **extra}, ensure_ascii=False) + "\n")


def _tiktok(cfg, row, video, cap, dry):
    """The film → the business's TikTok inbox as a draft, and its TikTok caption to the owner's bot."""
    if dry:
        return "dry run: tiktok draft"
    r = tiktok.upload_draft(cfg, video)
    text = core.parse_caption(cap.read_text(encoding="utf-8"))["tiktok"]
    log_published(cfg, "tiktok", r["id"], video.name, mode="draft", caption=text[:2200])
    return tiktok.tell_owner(cfg, row["title"], text)


def film_link(cfg, video_name, s):
    """Where the film can be watched: its Instagram Reel, else its YouTube Short, else the site's link."""
    f = data_dir(cfg) / "published.jsonl"
    rows = []
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    for want in ("instagram", "youtube"):
        r = next((x for x in reversed(rows) if x.get("platform") == want and x.get("video") == video_name and x.get("permalink")), None)
        if r:
            return r["permalink"]
    return core.utm_link(s["link"], "threads", Path(video_name).stem, s)


def _threads(cfg, text, link, key, field, dry):
    if dry:
        return "dry run: threads post"
    r = threads.post(cfg, text, link)
    with (data_dir(cfg) / "published.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "platform": "threads",
                             "id": r["id"], "permalink": r["link"], field: key}, ensure_ascii=False) + "\n")
    return r["link"] or r["id"]


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
            if "tiktok" in pp["auto"]:
                try:
                    out.append(f"film {row['title']} → tiktok draft: {_tiktok(cfg, row, video, cap, dry)}")
                except Exception as e:  # TikTok down must not stop the other platforms
                    out.append(f"film {row['title']} → tiktok: {str(e)[:300]}")
                pp["auto"] = [p for p in pp["auto"] if p != "tiktok"]
            want_threads = "threads" in pp["auto"]
            pp["auto"] = [p for p in pp["auto"] if p != "threads"]
            if pp["auto"]:
                args = type("A", (), {"dry_run": dry, "at": None, "video_url": None, "cover_url": None, "cover": None})()
                before = _count(cfg)
                code, log = (run_node or _node)(pcli.node_command(cfg, pp, cap, args), cfg, dry)
                if not dry:
                    _remember_challenge(cfg, core.parse_caption(cap.read_text(encoding="utf-8")), video.name, before)
                out.append(f"film {row['title']} → {', '.join(pp['auto'])}: exit {code}" + (f"\n{log[-600:]}" if code else ""))
            if want_threads:              # after the others, so it can link to the Reel / Short
                try:
                    text = core.parse_caption(cap.read_text(encoding="utf-8"))["threads"]
                    out.append(f"film {row['title']} → threads: {_threads(cfg, text, film_link(cfg, video.name, s), video.name, 'video', dry)}")
                except Exception as e:
                    out.append(f"film {row['title']} → threads: {str(e)[:300]}")
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
    plats = [p for p in ps.get("platforms") or [] if p in ("facebook", "linkedin", "threads") and core.auto_post(s, p)]
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
        if "threads" in todo:             # text only: Threads takes photos from a public URL alone
            try:
                out.append(f"post {row['title']} → threads: {_threads(cfg, cap['threads'], '', f.name, 'post', dry)}")
            except Exception as e:
                out.append(f"post {row['title']} → threads: {str(e)[:300]}")
            todo = [p for p in todo if p != "threads"]
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
