"""Job prompt = header + core prompt (jobs/prompts/<job>.md, generic) + the profile's part + footer.

The profile's part: the studio.instructions note (business rules: brand, voice, reference film, sources, what never to
show) and jobs.instructions.<job> (extra lines for one job). Placeholders are {{name}}, filled from the profile.
"""
import re
from datetime import datetime
from pathlib import Path

from .. import config
from . import settings as S

DIR = Path(__file__).resolve().parent / "prompts"
PY = "python -m viral_scout"


def values(cfg, job, now=None, done_file=""):
    s, st = S.settings(cfg), S.studio(cfg)
    from ..publish import core as pub
    ps = pub.settings(cfg)
    p = cfg["name"]
    j = s[job]
    auto_list = ", ".join(x for x in ps["platforms"] if pub.auto_post(ps, x)) or "no platform (auto_post is off)"
    return {
        "job": job, "profile": p, "brand": st["brand"], "repo": str(config.ROOT), "vault_dir": st["vault_dir"] or "(studio.vault_dir not set)",
        "today": (now or datetime.now()).strftime("%Y-%m-%d"), "owner": s["owner"], "language": s["language"],
        "cta_text": st["cta"].get("text", "(no CTA set)"), "cta_link": st["cta"].get("link", "(no link set)"),
        "compliance": f"`{st['compliance']}`" if st["compliance"] else "(no compliance note set: be conservative, no claims without a source)",
        "delivery": "Telegram, through the ideas API / service (commands below)" if s["delivery"] == "telegram"
                    else "none: leave results in the vault and the daily note; skip the send steps",
        "ideas": f"{PY} ideas {p}", "notes": f"{PY} notes {p}", "video": f"{PY} video {p}", "publish": f"{PY} publish {p}", "check": f"{PY} check {p}",
        "queue": ps["queue"] or "(no queue: set studio.vault_dir)", "platforms": ", ".join(ps["platforms"]),
        "approval_intro": (f"Films are approved automatically (publish.approval: auto): the posting job puts each one on "
                           f"{auto_list} at its time without waiting for {s['owner']}. {s['owner']} can still stop one until then. "
                           "So the quality bar below is the last check: a film you would not post is not delivered."
                           if ps["approval"] == "auto" else f"{s['owner']} reviews only the finished film; nothing is posted without them."),
        "queue_status": "✅ auto" if ps["approval"] == "auto" else f"waiting for {s['owner']}",
        "review_line": (f"Posts automatically on {auto_list} at its time. Reply 🛑 to stop it, or with changes."
                        if ps["approval"] == "auto" else "Watch with sound. Reply with changes or ✅."),
        "auto_platforms": auto_list, "per_day": str(ps["per_day"]), "times": ", ".join(ps["times"][: max(1, int(ps["per_day"]))]),
        "posts_queue": ps["posts_queue"] or "(no posts queue: set studio.vault_dir)", "posts_per_day": str(ps["posts"].get("per_day", 1)),
        "posts_platforms": ", ".join(ps["posts"].get("platforms") or []),
        "challenges": ("on: a post or film may end with a comment challenge (rules in the posts job)" if ps["challenges"].get("enabled") else "off"),
        "done_file": done_file, "max_tries": str(j.get("max_tries", 2)), "count": str(j.get("count", 5)), "buffer": str(j.get("buffer", 4)),
    }


def fill(text, vals):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: vals.get(m.group(1), m.group(0)), text)


def profile_part(cfg, job):
    st, s = S.studio(cfg), S.settings(cfg)
    out = []
    note = st["instructions"]
    if note and Path(note).exists():
        out.append(f"## Business rules (from `{note}`)\n\n" + Path(note).read_text(encoding="utf-8").strip())
    elif note:
        out.append(f"## Business rules\n\nThe note `{note}` is missing. Work conservatively and say so in the daily note.")
    else:
        out.append("## Business rules\n\nNo studio.instructions note is set for this profile. Use the profile's `business:` text: "
                   + (cfg.get("business") or "(empty)").strip())
    extra = (s.get("instructions") or {}).get(job)
    if extra:
        out.append(f"## Extra for this job\n\n{extra.strip()}")
    return "\n\n".join(out)


def assemble(cfg, job, now=None, done_file=""):
    if job not in S.JOBS:
        raise ValueError(f"unknown job {job!r} (jobs: {', '.join(S.JOBS)})")
    vals = values(cfg, job, now, done_file)
    parts = [(DIR / "_header.md").read_text(encoding="utf-8"), (DIR / f"{job}.md").read_text(encoding="utf-8"),
             profile_part(cfg, job), (DIR / "_footer.md").read_text(encoding="utf-8")]
    return fill("\n\n".join(x.strip() for x in parts), vals) + "\n"


# --allowedTools per job: files, web lookups for facts, and only the viral_scout commands the job needs.
BASE = ["Read", "Glob", "Grep", "Edit", "Write"]
WEB = ["WebSearch", "WebFetch"]


def allowed_tools(cfg, job):
    p, s = cfg["name"], S.settings(cfg)
    cmd = lambda c: f"Bash({PY} {c} {p}:*)"  # noqa: E731
    tools = {
        "ideas": BASE + WEB + [cmd("ideas"), f"Bash({PY} search:*)"],
        "script": BASE + WEB + [cmd("ideas")],
        "notes": BASE + WEB + [cmd("notes"), cmd("ideas"), cmd("video"), cmd("check")],
        "blog": BASE + WEB + [cmd("ideas"), cmd("notes")],
        "posts": BASE + WEB + [cmd("ideas"), cmd("notes"), cmd("video"), f"Bash({PY} publish {p} plan:*)"],
        "film": BASE + WEB + [cmd("ideas"), cmd("notes"), cmd("video"), cmd("check"), f"Bash({PY} publish {p} plan:*)"],
    }[job]
    extra = s.get("allowed_tools") or {}
    for t in list(extra.get("all") or []) + list(extra.get(job) or []):
        if t not in tools:
            tools.append(t)
    # Posting is never allowed to an unattended job, whatever the profile adds.
    return [t for t in tools if "viral_scout publish" not in t or t == f"Bash({PY} publish {p} plan:*)"]
