"""python -m viral_scout publish <profile> plan|today|post …

  plan  [--days 7] [--json]                       queued films → per platform: slot, UTM link, auto or manual
  today [--date YYYY-MM-DD] [--force] [--dry-run] morning post pack (video + still + POST.md) to the owner
  post  <video.mp4> --caption <caption.md> [--only a,b] [--at "YYYY-MM-DD HH:mm"] [--dry-run] [--video-url URL]
        posts ONLY to platforms with publish.auto_post.<platform>: true (official APIs, publish/node); every other
        platform is queued for posting by hand (data/publish/<profile>/queue.jsonl). --dry-run sends nothing.
  autopost [--dry-run]                            the posting job: due films and text/photo posts from the queues,
                                                  then the comment challenges (publish/auto.py, replies.py)
  connect meta|google|linkedin [--page P] [--org ID]   this business's posting keys → publish.env_file (connect.py)
  status --json                                   the Posting page: settings, queues, keys set or not, recent posts
  row stop|resume <file>                          🛑 or ✅ on the queue row of that mp4 / post file
"""
import argparse
import json
import os
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

from .. import config
from . import core, pack

NODE_DIR = Path(__file__).resolve().parent / "node"


def post_plan(cfg, video, caption_text, only=None):
    """Which platforms get the file through the API (auto) and which are queued for posting by hand. Pure."""
    s = core.settings(cfg)
    cap = core.parse_caption(caption_text)
    targets = [p for p in s["platforms"] if not only or p in only]
    auto = [p for p in targets if core.auto_post(s, p)]
    manual = [p for p in targets if p not in auto]
    env = {**os.environ, **pack.read_env_file(s["env_file"])}   # the business's own keys win
    missing = {}
    for p in auto:
        names = s["tokens"].get(p) or {}
        miss = [std for std in core.TOKEN_NAMES[p] if not env.get(names.get(std, std))]
        if miss:
            missing[p] = miss
    slug = Path(video).parent.parent.name if Path(video).parent.name == "out" else Path(video).stem
    return {"video": str(video), "auto": [p for p in auto if p not in missing], "manual": manual, "missing": missing,
            "problems": core.caption_problems(cap), "ai": cap["ai"],
            "title": core.youtube_title(cap["youtube"], cap["title"]),
            "links": {p: core.utm_link(s["link"], p, slug, s) for p in targets}}


def node_env(cfg):
    """Child env for the node publisher: the profile's token names mapped to the standard ones. Values never printed."""
    s = core.settings(cfg)
    src = {**os.environ, **pack.read_env_file(s["env_file"])}
    env = dict(os.environ)
    for p, names in core.TOKEN_NAMES.items():
        m = s["tokens"].get(p) or {}
        for std in names:
            v = src.get(m.get(std, std))
            if v:
                env[std] = v
    return env


def node_command(cfg, plan, caption_file, args):
    s = core.settings(cfg)
    log = config.ROOT / "data" / "publish" / cfg["name"] / "published.jsonl"
    cmd = ["node", str(NODE_DIR / "publish.mjs"), plan["video"], "--caption-file", str(caption_file),
           "--only", ",".join(plan["auto"]), "--tz", s["timezone"], "--log", str(log),
           "--category", str(s["youtube"]["category"]), "--lang", s["youtube"]["language"],
           "--privacy", s["youtube"].get("privacy", "public")]
    for k in ("at", "video_url", "cover_url", "cover"):
        v = getattr(args, k, None)
        if v:
            cmd += [f"--{k.replace('_', '-')}", v]
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def queue_manual(cfg, plan):
    f = config.ROOT / "data" / "publish" / cfg["name"] / "queue.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "video": plan["video"],
                             "platforms": plan["manual"], "links": plan["links"]}, ensure_ascii=False) + "\n")
    return f


def main(argv):
    p = argparse.ArgumentParser(prog="viral_scout publish")
    p.add_argument("profile")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--days", type=int, default=7)
    pl.add_argument("--from", dest="start")
    pl.add_argument("--json", action="store_true")
    t = sub.add_parser("today")
    t.add_argument("--date")
    t.add_argument("--force", action="store_true")
    t.add_argument("--dry-run", action="store_true")
    po = sub.add_parser("post")
    po.add_argument("file")
    po.add_argument("--caption", required=True, help="caption file (see docs/publish-and-jobs.md)")
    po.add_argument("--only")
    po.add_argument("--at")
    po.add_argument("--video-url")
    po.add_argument("--cover-url")
    po.add_argument("--cover")
    po.add_argument("--dry-run", action="store_true")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    rw = sub.add_parser("row")
    rw.add_argument("action", choices=["stop", "resume"])
    rw.add_argument("file")
    ap = sub.add_parser("autopost")
    ap.add_argument("--dry-run", action="store_true")
    co = sub.add_parser("connect")
    co.add_argument("service", choices=["meta", "google", "linkedin"])
    co.add_argument("--page")
    co.add_argument("--org")
    co.add_argument("--no-browser", action="store_true")
    co.add_argument("--check", action="store_true", help="only say whether the sign-in can start (JSON)")
    a = p.parse_args(argv)
    cfg = config.load(a.profile)
    s = core.settings(cfg)

    if a.cmd == "plan":
        rows = core.plan(cfg, date.fromisoformat(a.start) if a.start else None, a.days)
        if a.json:
            print(json.dumps({"queue": s["queue"], "films": rows, "free_dates": core.free_dates(cfg)[:7]}, ensure_ascii=False))
            return 0
        if not rows:
            print(f"nothing queued in the next {a.days} days ({s['queue'] or 'no queue: set studio.vault_dir or publish.queue'})")
        for r in rows:
            print(f"{r['date']}  {r['title']}  [{'approved' if r['approved'] else r['status'] or 'waiting'}]")
            for x in r["posts"]:
                print(f"    {x['platform']:<10} {x['at'][11:] or '--:--'}  {x['mode']:<6} {x['handle']:<18} {x['link']}")
        print("free dates:", ", ".join(core.free_dates(cfg)[:7]))
        return 0

    if a.cmd == "status":
        from . import status
        print(json.dumps(status.build(cfg), ensure_ascii=False))
        return 0

    if a.cmd == "row":
        from . import status
        try:
            print(json.dumps({"ok": True, "status": status.set_row(cfg, a.action, a.file)}, ensure_ascii=False))
        except ValueError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            return 1
        return 0

    if a.cmd == "autopost":
        from . import auto
        print(auto.run(cfg, dry=a.dry_run))
        return 0

    if a.cmd == "connect":
        from . import connect
        if a.check:
            err = connect.check(cfg, a.service)
            print(json.dumps({"ok": not err, "error": err}))
            return 0 if not err else 1
        try:
            lines = (connect.meta(cfg, a.page) if a.service == "meta" else
                     connect.google(cfg, not a.no_browser) if a.service == "google" else connect.linkedin(cfg, a.org, not a.no_browser))
        except Exception as e:
            print(f"error: {e}")
            return 1
        print("\n".join(lines))
        return 0

    if a.cmd == "today":
        print(pack.today(cfg, a.date, a.force, a.dry_run))
        return 0

    video, cap = Path(a.file), Path(a.caption)
    if not video.exists() or not cap.exists():
        print(f"error: not found: {video if not video.exists() else cap}")
        return 2
    only = [x.strip().lower() for x in a.only.split(",")] if a.only else None
    pp = post_plan(cfg, video, cap.read_text(encoding="utf-8"), only)
    if pp["problems"]:
        print("caption problems:", "; ".join(pp["problems"]))
        return 1
    print(f"{video.name} · AI label: {'yes' if pp['ai'] else 'no'} · YouTube title: {pp['title']}")
    for x in pp["auto"]:
        print(f"  auto    {x:<10} {pp['links'].get(x, '')}")
    for x, miss in pp["missing"].items():
        print(f"  skipped {x:<10} opted in but missing {', '.join(miss)} (env or publish.env_file)")
    for x in pp["manual"]:
        print(f"  manual  {x:<10} {pp['links'].get(x, '')}")
    if pp["manual"] and not a.dry_run:
        print(f"queued for posting by hand → {queue_manual(cfg, pp)}")
    if not pp["auto"]:
        print("nothing posts automatically (publish.auto_post is off for every platform)." if not a.dry_run else "dry run: nothing sent.")
        return 0
    if not shutil.which("node"):
        print("error: node not on PATH (needed for the API publisher)")
        return 1
    cmd = node_command(cfg, pp, cap, a)
    return subprocess.call(cmd, env=node_env(cfg))
