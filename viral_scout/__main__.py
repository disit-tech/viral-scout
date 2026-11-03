"""viral-scout CLI.

  python -m viral_scout run <profile> [--no-recheck] [--no-discover] [--quiet]
  python -m viral_scout add <profile> <url> [<url> ...]      track posts (e.g. reels someone sent you)
  python -m viral_scout save <profile> <id|url> ... [--note]  save to the Obsidian swipe file
  python -m viral_scout dismiss <profile> <id|url> ...        hide from future reports
  python -m viral_scout profiles
"""
import argparse
import sys

from . import config


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config.load_env()
    from . import run   # after load_env, so VIRAL_SCOUT_YTDLP from .env applies
    from .report import n

    p = argparse.ArgumentParser(prog="viral_scout")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="scout a profile and write the report")
    r.add_argument("profile")
    r.add_argument("--no-recheck", action="store_true", help="skip re-measuring earlier finds")
    r.add_argument("--no-discover", action="store_true", help="only watch list, seeds and re-checks")
    r.add_argument("--quiet", action="store_true")
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
    sub.add_parser("profiles", help="list profiles")
    args = p.parse_args(argv)

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

    res, (md, js) = run.scout(cfg, quiet=args.quiet, recheck=not args.no_recheck, discover=not args.no_discover)
    print(f"report: {md}\ndata:   {js}\nposts: {len(res['items'])}, new: {len(res['new'])}, "
          f"errors: {len(res['errors'])}, skipped sources: {len(res['skipped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
