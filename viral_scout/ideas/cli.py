"""`python -m viral_scout ideas <profile> <command>`: the ideas CLI (port of solar site/scripts/ideas.mjs).

  info                                  the resolved ideas block, notes to read, newest market data (no network)
  pull                                  every idea of the profile's project with ratings, tags, comments (JSON)
  push <file.json> [--dry-run]          {batch, ideas: [...]} → stored and posted to the ideas bot
  tracked <id ...>                      mark ideas as added to the vault tracker
  repost <id ...>                       post again through the project's current bot
  script <id> <file.md>                 send the scenario for approval
  stage <id> <stage> [--draft <path>]   production stage: making | draft | posted
  pack <id> <note.md> [--dry-run] [--store-only]   content pack from a vault note (packs.enabled profiles only)
  blog <slug> "<title>" <summary.txt> | blog-list | blog-published <id>   blog review (ideas.blog profiles only)

The project slug comes from the profile's ideas.project. There is no --project flag on purpose.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from .. import config
from . import packs
from .client import Client, check_batch, check_stage
from .settings import (PLATFORMS, IdeasError, credentials, ideas_cfg, market_files, resolve, studio_cfg)

COMMANDS = ("info", "pull", "push", "tracked", "repost", "script", "stage", "pack", "blog", "blog-list",
            "blog-published")


def register(subparsers):
    """Add `ideas` to the main viral_scout parser (or any argparse subparsers object)."""
    p = subparsers.add_parser("ideas", help="ideas for a profile: pull | push | tracked | pack ... (docs/ideas.md)")
    p.add_argument("profile")
    sub = p.add_subparsers(dest="ideas_cmd", required=True)
    sub.add_parser("info", help="resolved settings, notes to read, newest market data")
    sub.add_parser("pull", help="all ideas of this project (JSON)")
    s = sub.add_parser("push", help="push a batch file")
    s.add_argument("file")
    s.add_argument("--dry-run", action="store_true", help="only check the batch")
    for name in ("tracked", "repost"):
        s = sub.add_parser(name)
        s.add_argument("ids", nargs="+", type=int)
    s = sub.add_parser("script")
    s.add_argument("id", type=int)
    s.add_argument("file")
    s = sub.add_parser("stage")
    s.add_argument("id", type=int)
    s.add_argument("stage")
    s.add_argument("--draft")
    s = sub.add_parser("pack")
    s.add_argument("id", type=int)
    s.add_argument("note")
    s.add_argument("--dry-run", action="store_true", help="check and print the messages, send nothing")
    s.add_argument("--store-only", action="store_true", help="store it for the CRM without sending to Telegram")
    s = sub.add_parser("blog")
    s.add_argument("slug")
    s.add_argument("title")
    s.add_argument("summary_file")
    sub.add_parser("blog-list")
    s = sub.add_parser("blog-published")
    s.add_argument("id", type=int)
    s = sub.add_parser("status", help="are this business's ideas and video bots connected? (profile `all` = every business)")
    s.add_argument("--test", choices=["ideas", "video"], help="also send a test message through that bot")
    return p


def _profiles_with_ideas():
    """Names of the profiles that have an ideas: block."""
    out = []
    for p in sorted(config.PROFILES.glob("*.yaml")):
        if p.name.startswith("_") or p.stem.startswith("example"):
            continue
        try:
            cfg = config.load(p.stem)
        except Exception:
            continue
        if isinstance(cfg.get("ideas"), dict) and cfg["ideas"].get("project"):
            out.append(cfg["name"])
    return out


def status(args, transport=None, environ=None):
    """`ideas <p> status [--test ideas|video]` and `ideas all status`: the bot service's /api/status, per profile."""
    names = _profiles_with_ideas() if args.profile == "all" else [args.profile]
    out = {"profiles": []}
    for name in names:
        row = {"profile": name}
        try:
            cfg = config.load(name)
            ic = ideas_cfg(cfg)
            base, secret = credentials(ic, environ, service=True)
            c = Client(ic["project"], base, secret, transport)
            row["service"] = base
            if args.test:
                if args.profile == "all":
                    raise IdeasError("--test needs one profile, not all")
                row["test"] = c.test_bot(args.test)
            s = c.status()
            row.update(s["projects"][0] if s.get("projects") else {})
            row["checkedAt"] = s.get("checkedAt")
        except (IdeasError, OSError, json.JSONDecodeError, KeyError) as e:
            row["error"] = str(e)
        out["profiles"].append(row)
    _print(out if args.profile == "all" else out["profiles"][0])
    return 0 if all("error" not in r for r in out["profiles"]) else 1


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _vault_path(path):
    """The note's path inside the vault (shown in the Telegram header), like ideas.mjs."""
    vault = os.environ.get("OBSIDIAN_VAULT", "").replace("\\", "/").rstrip("/")
    p = str(path).replace("\\", "/")
    if vault and p.lower().startswith(vault.lower() + "/"):
        return p[len(vault) + 1:]
    return p.split("/")[-1]


def info(cfg, ic):
    st = studio_cfg(cfg)
    notes = {k: resolve(cfg, v) for k, v in (("instructions", st.get("instructions")),
                                             ("compliance", st.get("compliance")),
                                             ("taste_note", ic["taste_note"]), ("tracker", ic["tracker"])) if v}
    return {
        "profile": cfg["name"], "project": ic["project"], "header": ic["header"], "brand": st.get("brand", ""),
        "cta": st.get("cta", {}), "rubrics": ic["rubrics"], "score": ic["score"],
        "experiment_share": ic["experiment_share"],
        "notes": {k: {"path": v, "exists": Path(v).exists()} for k, v in notes.items()},
        "sources": [{"path": resolve(cfg, s), "exists": Path(resolve(cfg, s)).exists()} for s in ic["sources"]],
        "market_data": {"dir": ic["market_data"]["dir"], "min_share": ic["market_data"]["min_share"],
                        "max_age_days": ic["market_data"]["max_age_days"], "newest": market_files(ic)},
        "packs": {**ic["packs"], "platforms": ic["packs"].get("platforms") or PLATFORMS},
        "blog": bool(ic["blog"]), "batch_dir": ic["batch_dir"], "daily": ic["daily"],
    }


def dispatch(args, transport=None, environ=None):
    """Run a parsed `ideas` command. transport/environ are for tests (no network)."""
    if args.ideas_cmd == "status":
        return status(args, transport, environ)
    try:
        cfg = config.load(args.profile)
        ic = ideas_cfg(cfg)
        cmd = args.ideas_cmd
        if cmd == "info":
            _print(info(cfg, ic))
            return 0
        if cmd == "push":
            batch = json.loads(Path(args.file).read_text(encoding="utf-8"))
            errors, warnings = check_batch(batch, ic)
            for w in warnings:
                print("warning:", w, file=sys.stderr)
            if errors:
                for e in errors:
                    print("error:", e, file=sys.stderr)
                return 1
            if args.dry_run:
                print(f"(dry run: {len(batch['ideas'])} ideas for {ic['project']}, batch {batch['batch']}; nothing sent)")
                return 0
        if cmd == "pack":
            if not ic["packs"].get("enabled"):
                raise IdeasError(f"content packs are off for {cfg['name']} (ideas.packs.enabled)")
            sections = packs.parse(Path(args.note).read_text(encoding="utf-8"))
            errors, warnings = packs.check(sections, ic["packs"].get("limits"), ic["packs"].get("banned_words"))
            for w in warnings:
                print("warning:", w, file=sys.stderr)
            if errors:
                for e in errors:
                    print("error:", e, file=sys.stderr)
                return 1
            note = _vault_path(args.note)[-300:]
            if args.dry_run:
                print(packs.render(sections))
                print(f"\n(dry run: {len(sections)} messages for idea #{args.id}, note {note}; nothing sent)")
                return 0
        if cmd in ("blog", "blog-list", "blog-published") and not ic["blog"]:
            raise IdeasError(f"blog review is off for {cfg['name']} (ideas.blog)")
        if cmd == "stage":
            check_stage(args.stage)
        script = None
        if cmd == "script":
            script = Path(args.file).read_text(encoding="utf-8")
            if not 20 <= len(script.strip()) <= 3500:
                raise IdeasError(f"the script is {len(script.strip())} chars; the API takes 20-3,500")

        base, secret = credentials(ic, environ)
        c = Client(ic["project"], base, secret, transport)
        if cmd == "pull":
            out = c.pull()
        elif cmd == "push":
            out = c.push(batch)
        elif cmd == "tracked":
            out = c.tracked(args.ids)
        elif cmd == "repost":
            out = c.repost(args.ids)
        elif cmd == "script":
            out = c.script(args.id, script)
        elif cmd == "stage":
            out = c.stage(args.id, args.stage, args.draft)
        elif cmd == "pack":
            out = c.pack(args.id, sections, note, args.store_only)
        elif cmd == "blog":
            out = c.blog(args.slug, args.title, Path(args.summary_file).read_text(encoding="utf-8"))
        elif cmd == "blog-list":
            out = c.blog_list()
        elif cmd == "blog-published":
            out = c.blog_published(args.id)
        else:
            raise IdeasError(f"unknown command {cmd}")
        _print(out)
        return 0
    except (IdeasError, FileNotFoundError, json.JSONDecodeError) as e:
        print("error:", e, file=sys.stderr)
        return 1


def main(argv, transport=None, environ=None):
    if argv and argv[0] == "board":                 # every business's ideas for the dashboard's Ideas board
        from .board import cli as board_cli
        return board_cli(argv[1:])
    p = argparse.ArgumentParser(prog="viral_scout")
    sub = p.add_subparsers(dest="cmd", required=True)
    register(sub)
    return dispatch(p.parse_args(["ideas", *argv]), transport, environ)
