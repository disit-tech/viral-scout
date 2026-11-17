"""The ideas board for the local dashboard (/ideas): every business's ideas and daily films in one list, with rate,
comment, remove, reason tags, notes for Claude and "posted" for films.

  python -m viral_scout ideas board get          JSON for the dashboard (every profile with an ideas: block)
  python -m viral_scout ideas board set          JSON on stdin {ids, op, value?, project?} → the change

Reads and writes go to the bot service's /api/board (GET / PATCH {ids, op, value}), the same API as the disit.tech
board, so there is one set of rules. Until /api/board is deployed (404), it falls back to the per-project
/api/ideas: reading every project, and rate (sent, good, bad, redo, approved), comment and remove. Tags, notes and
"posted" need /api/board; the answer says which mode is on ("source": "board" | "ideas").
The secret stays in this process: the dashboard only ever sees the JSON.
"""
import json
import sys

from .. import config
from .client import Client
from .settings import IdeasError, credentials, ideas_cfg

FALLBACK_RATINGS = ("sent", "good", "bad", "redo", "approved")


def _profiles():
    """(profile name, display name, ideas config) for every profile with a usable ideas: block."""
    out = []
    for p in sorted(config.PROFILES.glob("*.yaml")):
        if p.stem.startswith("_"):
            continue
        try:
            cfg = config.load(p.stem)
            ic = ideas_cfg(cfg)
        except (IdeasError, FileNotFoundError, ValueError):
            continue
        studio = cfg.get("studio") if isinstance(cfg.get("studio"), dict) else {}
        out.append((p.stem, cfg.get("display_name") or studio.get("brand") or p.stem, ic))
    return out


def _client(ic, project=None):
    base, secret = credentials(ic, service=True)
    return Client(project or ic["project"], base, secret)


def get():
    profs = _profiles()
    if not profs:
        return {"error": "no profile has an ideas: block"}
    by_slug = {ic["project"]: (name, disp) for name, disp, ic in profs}
    c = _client(profs[0][2])
    try:
        d = c.call("GET", None, "/api/board")
        src = "board"
    except Exception as err:  # noqa: BLE001 (404 until /api/board is deployed → read project by project)
        if "404" not in str(err) and "Not Found" not in str(err):
            raise
        src, d = "ideas", {"projects": [], "ideas": [], "reasons": {}, "reasonsFor": {}, "stages": {}, "final": []}
        for name, disp, ic in profs:
            one = _client(ic).pull()
            d["projects"].append({"slug": ic["project"], "label": disp})
            for i in one.get("ideas") or []:
                film = i.get("kind") == "film" or str(i.get("batch") or "").startswith("film-") or str(i.get("source") or "").startswith("film:")
                d["ideas"].append({**i, "kind": "film" if film else "idea"})
        d["final"] = ["replaced", "varied", "tracked", "deleted"]
    for p in d.get("projects") or []:
        name, disp = by_slug.get(p["slug"], (None, None))
        p["profile"], p["display"] = name, disp or p.get("label") or p["slug"]
    d["ideas"].sort(key=lambda i: -int(i.get("id") or 0))
    d["source"] = src
    d["can"] = ["rate", "comment", "remove", "tag", "note", "posted"] if src == "board" else ["rate", "comment", "remove"]
    return d


def set_(body):
    ids = [int(x) for x in body.get("ids") or []]
    op, value, project = body.get("op"), (body.get("value") or "").strip(), body.get("project")
    if not ids or op not in ("rate", "remove", "tag", "comment", "note", "posted"):
        return {"error": "need ids and an op (rate, remove, tag, comment, note, posted)"}
    profs = _profiles()
    ic = next((ic for _, _, ic in profs if ic["project"] == project), profs[0][2] if profs else None)
    if not ic:
        return {"error": "no profile has an ideas: block"}
    c = _client(ic)
    try:
        return c.call("PATCH", {"ids": ids, "op": op, **({"value": value} if value else {})}, "/api/board")
    except Exception as err:  # noqa: BLE001
        if "404" not in str(err) and "Not Found" not in str(err):
            return {"error": str(err)[:300]}
    # /api/ideas fallback: one idea per call, and only what that API can do
    if not project:
        return {"error": "project is needed until /api/board is deployed"}
    if op in ("tag", "note", "posted"):
        return {"error": f"'{op}' needs the bot service's /api/board (not deployed yet)"}
    if op == "rate" and value not in FALLBACK_RATINGS:
        return {"error": f"rating '{value}' needs /api/board; available now: {', '.join(FALLBACK_RATINGS)}"}
    if op == "comment" and not value:
        return {"error": "comment needs text"}
    c = _client(ic, project)
    changed = 0
    for i in ids:
        payload = {"id": i, "project": project}
        payload.update({"rate": value} if op == "rate" else {"comment": value} if op == "comment" else {"remove": True})
        c.call("PATCH", payload)
        changed += 1
    return {"ok": True, "changed": changed, "source": "ideas"}


def cli(argv):
    if not argv or argv[0] not in ("get", "set"):
        print("usage: python -m viral_scout ideas board get | set  (set reads JSON from stdin)")
        return 2
    try:
        out = get() if argv[0] == "get" else set_(json.loads(sys.stdin.read() or "{}"))
    except Exception as err:  # noqa: BLE001 (the dashboard shows the message)
        out = {"error": str(err)[:400]}
    print(json.dumps(out, ensure_ascii=False))
    return 1 if out.get("error") else 0
