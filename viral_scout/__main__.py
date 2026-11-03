"""viral-scout CLI.

  python -m viral_scout run <profile> [--no-recheck] [--no-discover] [--quiet]
  python -m viral_scout add <profile> <url> [<url> ...]      track posts (e.g. reels someone sent you)
  python -m viral_scout save <profile> <id|url> ... [--note]  save to the Obsidian swipe file
  python -m viral_scout dismiss <profile> <id|url> ...        hide from future reports
  python -m viral_scout status <profile> <note.md> <status>   move a swipe note
  python -m viral_scout export [profiles]                     data for the dashboard
  python -m viral_scout search "<query>" [--profile p]        search everything collected
  python -m viral_scout new <name> --business ... --keywords "a; b" [--research] [--run]
  python -m viral_scout competitors <profile> ["query"] [--near "City, ST"]
  python -m viral_scout keys [status | test [NAME] | set NAME [VALUE|-]]
  python -m viral_scout perf <profile> [--no-pull]               own performance (your videos and ads) → report
  python -m viral_scout perf import <profile> <file.csv> --source meta|tiktok|youtube|generic
  python -m viral_scout perf auth youtube                         OAuth for the YouTube Analytics API
  python -m viral_scout profiles
"""
import argparse
import sys

from . import config


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config.load_env()
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "perf":                 # own performance has its own sub-commands
        from .perf.cli import main as perf_main
        return perf_main(argv[1:])
    from . import run   # after load_env, so VIRAL_SCOUT_YTDLP from .env applies
    from .report import n

    p = argparse.ArgumentParser(prog="viral_scout")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="scout a profile and write the report")
    r.add_argument("profile")
    r.add_argument("--no-recheck", action="store_true", help="skip re-measuring earlier finds")
    r.add_argument("--no-discover", action="store_true", help="only watch list, seeds and re-checks")
    r.add_argument("--quiet", action="store_true")
    r.add_argument("--status-file", help="write running/done/failed JSON here (dashboard jobs)")
    a = sub.add_parser("add", help="track one or more post URLs")
    a.add_argument("profile")
    a.add_argument("urls", nargs="+")
    sv = sub.add_parser("save", help="save posts to the swipe file (ID from the report, or URL)")
    sv.add_argument("profile")
    sv.add_argument("refs", nargs="+")
    sv.add_argument("--note", default="", help="why it works / idea, written into the note")
    d = sub.add_parser("dismiss", help="hide posts from future reports")
    d.add_argument("profile")
    d.add_argument("refs", nargs="+")
    st = sub.add_parser("status", help="set a swipe note's status (idea, scripted, filmed, posted, skip)")
    st.add_argument("profile")
    st.add_argument("file", help="swipe note file name")
    st.add_argument("status", choices=["idea", "scripted", "filmed", "posted", "skip"])
    ex = sub.add_parser("export", help="export data for the web dashboard (web/data/)")
    ex.add_argument("names", nargs="*")
    se = sub.add_parser("search", help="search titles, hooks, transcripts of everything collected")
    se.add_argument("query")
    se.add_argument("--profile", action="append")
    se.add_argument("--limit", type=int, default=20)
    se.add_argument("--json", action="store_true")
    nw = sub.add_parser("new", help="create a profile for a new project (or quick research) from keywords")
    nw.add_argument("name")
    nw.add_argument("--business", default="")
    nw.add_argument("--keywords", required=True, help='separate with ";" or new lines')
    nw.add_argument("--hashtags", default="", help="space or comma separated; derived from keywords if empty")
    nw.add_argument("--languages", default="", help='"keyword=ru; other keyword=uk"')
    nw.add_argument("--vault-project", default=None, help="vault folder under projects/ for reports")
    nw.add_argument("--window", default="month")
    nw.add_argument("--region", default=None)
    nw.add_argument("--research", action="store_true", help="quick research profile (research-<name>)")
    nw.add_argument("--run", action="store_true", help="start the first run right away")
    co = sub.add_parser("competitors", help="local competitors via Google Places + their social channels")
    co.add_argument("profile")
    co.add_argument("query", nargs="?")
    co.add_argument("--near")
    ke = sub.add_parser("keys", help="API key status / test / set")
    ke.add_argument("rest", nargs="*")
    sub.add_parser("profiles", help="list profiles")
    sub.add_parser("perf", help="own performance: perf <profile> | perf import ... | perf auth youtube")
    args = p.parse_args(argv)

    if args.cmd == "keys":
        from . import keys
        rest = list(args.rest)
        if len(rest) == 3 and rest[0] == "set" and rest[2] == "-":      # value from stdin (not in the process list)
            rest[2] = sys.stdin.readline().strip()
        return keys.cli(rest)

    if args.cmd == "search":
        import json as _json
        from .search import search
        hits = search(args.query, args.profile, args.limit)
        if args.json:
            print(_json.dumps(hits, ensure_ascii=False))
            return 0
        for h in hits:
            print(f"[{h['score']}] {h['profile']} · {h['title'][:70]} · {h['channel']} · {n(h['views'] or h['likes'])}")
            print(f"     {h['url']}")
            print(f"     {h['snippet'][:150]}")
        return 0 if hits else 1

    if args.cmd == "new":
        from .newproject import create, parse_languages, parse_list
        import re as _re
        name, path = create(args.name, args.business, parse_list(args.keywords),
                            [h for h in _re.split(r"[\s,]+", args.hashtags) if h], parse_languages(args.languages),
                            args.vault_project, args.research, args.window, args.region)
        print(f"created profile {name}: {path}")
        if args.run:
            cfg = config.load(name)
            res, (md, js) = run.scout(cfg)
            print(f"report: {md}")
        return 0

    if args.cmd == "profiles":
        for f in sorted(p for p in config.PROFILES.glob("*.yaml") if not p.stem.startswith("_")):
            print(f.stem)
        return 0

    if args.cmd == "export":
        from .export import export_all
        out, names = export_all(args.names)
        print(f"exported {', '.join(names) or 'nothing'} → {out}")
        return 0

    cfg = config.load(args.profile)
    if args.cmd == "competitors":
        from . import places
        if not places.available():
            print("error: GOOGLE_PLACES_API_KEY is not set (python -m viral_scout keys)")
            return 1
        rows, note = places.competitors(cfg, args.query, args.near)
        for r in rows:
            print(f"{r['name']} · {r['rating']} ({r['reviews']}) · {r['website'] or '-'} · "
                  + ", ".join(f"{k}: {len(v)}" for k, v in r["socials"].items()))
        print("note:", note)
        return 0
    if args.cmd == "status":
        from pathlib import Path
        import re as _re
        folder = Path(cfg.get("swipe_dir") or (Path(cfg["output_dir"]) / "swipe"))
        f = folder / Path(args.file).name
        if not f.exists():
            print("error: no such swipe note:", f.name)
            return 1
        text = f.read_text(encoding="utf-8")
        text, k = _re.subn(r'^status:.*$', f'status: "{args.status}"', text, count=1, flags=_re.M)
        f.write_text(text, encoding="utf-8")
        print(f"{f.name}: status → {args.status}" if k else "error: no status field")
        return 0 if k else 1
    if args.cmd == "save":
        paths, errors = run.save(cfg, args.refs, args.note)
        for pth in paths:
            print("saved:", pth)
        for e in errors:
            print("error:", e)
        return 1 if errors and not paths else 0
    if args.cmd == "dismiss":
        done, missing = run.dismiss(cfg, args.refs)
        print(f"dismissed {len(done)}" + (f"; not found: {', '.join(missing)}" if missing else ""))
        return 0
    if args.cmd == "add":
        items, errors = run.add_seeds(cfg, args.urls)
        for it in items:
            print(f"tracking {it.platform} {it.channel} — {it.title[:60]!r}: views {n(it.views)}, likes {n(it.likes)}")
        for e in errors:
            print("error:", e)
        return 1 if errors and not items else 0

    import json as _json
    from datetime import datetime as _dt
    from pathlib import Path as _P
    sf = _P(args.status_file) if args.status_file else None

    def _status(**kw):
        if sf:
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text(_json.dumps({"profile": cfg["name"], "updated": _dt.now().isoformat(), **kw}), encoding="utf-8")

    _status(status="running", started=_dt.now().isoformat())
    try:
        res, (md, js) = run.scout(cfg, quiet=args.quiet, recheck=not args.no_recheck, discover=not args.no_discover)
    except Exception as err:
        _status(status="failed", error=str(err)[:500])
        raise
    _status(status="done", posts=len(res["items"]), errors=len(res["errors"]), report=md)
    print(f"report: {md}\ndata:   {js}\nposts: {len(res['items'])}, new: {len(res['new'])}, "
          f"errors: {len(res['errors'])}, skipped sources: {len(res['skipped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
