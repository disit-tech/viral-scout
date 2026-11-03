"""viral-scout CLI.

  python -m viral_scout run <profile> [--no-recheck] [--no-discover] [--quiet]
  python -m viral_scout add <profile> <url> [<url> ...]      track posts (e.g. reels someone sent you)
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
    sub.add_parser("profiles", help="list profiles")
    args = p.parse_args(argv)

    if args.cmd == "profiles":
        for f in sorted(p for p in config.PROFILES.glob("*.yaml") if not p.stem.startswith("_")):
            print(f.stem)
        return 0

    cfg = config.load(args.profile)
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
