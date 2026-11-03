"""CLI for own performance.

  python -m viral_scout perf <profile> [--no-pull] [--quiet]        pull every configured source → report
  python -m viral_scout perf import <profile> <file.csv> --source meta|tiktok|youtube|generic [--no-report]
  python -m viral_scout perf auth youtube [--no-browser] [--port N] OAuth consent → YT_OAUTH_REFRESH_TOKEN in .env
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from .. import config


def main(argv):
    if argv and argv[0] == "auth":
        a = argparse.ArgumentParser(prog="viral_scout perf auth")
        a.add_argument("service", choices=["youtube"])
        a.add_argument("--no-browser", action="store_true")
        a.add_argument("--port", type=int, default=0, help="loopback port (default: any free port)")
        args = a.parse_args(argv[1:])
        from .youtube import authorize
        print(authorize(open_browser=not args.no_browser, port=args.port))
        return 0

    if argv and argv[0] == "import":
        a = argparse.ArgumentParser(prog="viral_scout perf import")
        a.add_argument("profile")
        a.add_argument("file")
        a.add_argument("--source", required=True, choices=["meta", "tiktok", "youtube", "generic"])
        a.add_argument("--no-report", action="store_true", help="only store the rows")
        args = a.parse_args(argv[1:])
        cfg = config.load(args.profile)
        from .run import build, import_csv
        recs, unknown = import_csv(cfg, args.file, args.source)
        print(f"imported {len(recs)} records from {Path(args.file).name} ({args.source})")
        if unknown:
            print("ignored columns: " + ", ".join(unknown[:40]))
        if not recs:
            print("error: no rows recognised; check --source and the header names (docs/performance.md)")
            return 1
        if not args.no_report:
            _, (md, js) = build(cfg, do_pull=False, quiet=True)
            print(f"report: {md}\ndata:   {js}")
        return 0

    a = argparse.ArgumentParser(prog="viral_scout perf")
    a.add_argument("profile")
    a.add_argument("--no-pull", action="store_true", help="don't call APIs; rebuild from stored data")
    a.add_argument("--quiet", action="store_true")
    a.add_argument("--status-file", help="write running/done/failed JSON here (dashboard/MCP jobs)")
    args = a.parse_args(argv)
    cfg = config.load(args.profile)
    sf = Path(args.status_file) if args.status_file else None

    def status(**kw):
        if sf:
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text(json.dumps({"profile": cfg["name"], "updated": datetime.now().isoformat(), **kw}),
                          encoding="utf-8")

    status(status="running")
    from .run import build
    try:
        data, (md, js) = build(cfg, do_pull=not args.no_pull, quiet=args.quiet)
    except Exception as err:
        status(status="failed", error=str(err)[:500])
        raise
    status(status="done", records=len(data["records"]), report=md)
    s = data["sources"]
    print(f"report: {md}\ndata:   {js}\nrecords: {len(data['records'])}, pulled: {s['pulled'] or 'none'}, "
          f"skipped sources: {len(s['skipped'])}, errors: {len(s['errors'])}")
    for x in s["skipped"]:
        print(f"  skipped: {x}")
    for x in s["errors"][:10]:
        print(f"  error: {x}")
    return 0
