"""Content packs: a vault note → one message per platform, plus the checks that run before anything is sent.

Note format (ported from solar site/scripts/ideas.mjs, same output):
  - frontmatter and anything above the first `## ` heading are for the vault only
  - every `## Platform` section is one Telegram message (a reply to the idea)
  - every `### Label` inside it is a separate copyable block
  - lines starting with `>` are notes for the owner (shown above the block, not inside it)
  - a block with only notes becomes the note of the next block
  - sections called Checks / Claims checked / Notes / Перевірка are not sent
"""
import re

SKIP = re.compile(r"^(checks?|claims checked|notes?|перевірка)\b", re.I)
FRONTMATTER = re.compile(r"^---\r?\n[\s\S]*?\r?\n---\r?\n")

# The API's own limits (solar site/src/app/api/ideas/route.ts, PackSection and PACK_MESSAGE_MAX).
API = {"sections": 15, "parts": 10, "title": 80, "label": 80, "note": 600, "text": 3500, "message": 3900, "path": 300}

# House style for every profile: an em dash reads as AI.
EM_DASH = {"pattern": "—", "why": "has an em dash (reads as AI; use a comma, colon or full stop)", "level": "warning"}


def parse(md):
    """Markdown → [{title, parts: [{label?, note?, text}]}] (same shape the API takes)."""
    lines = FRONTMATTER.sub("", md, count=1).splitlines()
    raw, sec, part = [], None, None

    def flush():
        if part is not None and sec is not None:
            sec["parts"].append(part)

    for line in lines:
        h2 = re.match(r"^## (.+?)\s*$", line)
        h3 = re.match(r"^### (.+?)\s*$", line)
        if h2:
            flush()
            sec = {"title": h2.group(1), "parts": []}
            raw.append(sec)
            part = {"lines": []}
        elif h3 and sec is not None:
            flush()
            part = {"label": h3.group(1), "lines": []}
        elif part is not None:
            part["lines"].append(line)
    flush()

    sections = []
    for s in raw:
        if SKIP.match(s["title"]):
            continue
        parts, carry = [], ""
        for r in s["parts"]:
            notes = [re.sub(r"^>\s?", "", x).strip() for x in r["lines"] if x.startswith(">")]
            note = " ".join(x for x in [carry, *notes] if x)
            text = "\n".join(x for x in r["lines"] if not x.startswith(">")).strip()
            if not text:
                carry = f"{r['label']}: {note}".strip() if r.get("label") else note
                continue
            carry = ""
            p = {}
            if r.get("label"):
                p["label"] = r["label"]
            if note:
                p["note"] = note
            p["text"] = text
            parts.append(p)
        if carry:
            parts.append({"text": carry})
        if parts:
            sections.append({"title": s["title"], "parts": parts})
    return sections


def _rules(words):
    """banned_words entries → [{regex, why, level}]. A plain string is a whole word, case-insensitive."""
    out = []
    for w in words or []:
        if isinstance(w, str):
            out.append({"regex": re.compile(rf"\b{re.escape(w)}\b", re.I), "why": f'says "{w}"', "level": "error"})
        else:
            out.append({"regex": re.compile(w["pattern"], 0 if w.get("case") else re.I),
                        "why": w.get("why") or f"matches {w['pattern']}", "level": w.get("level", "error")})
    return out


def text_problems(where, text, banned_words):
    """House text checks on one piece of text → (errors, warnings)."""
    errors, warnings = [], []
    for r in _rules(banned_words) + _rules([EM_DASH]):
        if r["regex"].search(text):
            (errors if r["level"] == "error" else warnings).append(f"{where}: {r['why']}")
    return errors, warnings


def check(sections, limits=None, banned_words=None):
    """Platform limits, API limits and banned words → (errors, warnings).

    limits: {<word in the section title>: {per_part: N, total: N, hashtags: [min, max]}}, e.g.
      {threads: {per_part: 500}, google: {total: 1500}, linkedin: {total: 3000, hashtags: [3, 8]}}
    """
    errors, warnings = [], []
    if not sections:
        errors.append('no "## Platform" sections found')
    if len(sections) > API["sections"]:
        errors.append(f"{len(sections)} sections, the API takes at most {API['sections']}")
    for s in sections:
        title = s["title"]
        t = title.lower()
        parts = s["parts"]
        whole = "\n".join(p["text"] for p in parts)
        # what the API refuses
        if len(title) > API["title"]:
            errors.append(f"{title[:40]}…: section title over {API['title']} chars")
        if len(parts) > API["parts"]:
            errors.append(f"{title}: {len(parts)} blocks, the API takes at most {API['parts']}")
        for p in parts:
            name = f"{title} / {p.get('label', 'post')}"
            if len(p["text"]) > API["text"]:
                errors.append(f"{name}: {len(p['text'])} chars, the API takes at most {API['text']} per block")
            if len(p.get("label", "")) > API["label"]:
                errors.append(f"{name}: label over {API['label']} chars")
            if len(p.get("note", "")) > API["note"]:
                errors.append(f"{name}: owner note over {API['note']} chars")
        size = len(title) + sum(len(p["text"]) + len(p.get("label", "")) + len(p.get("note", "")) + 40 for p in parts)
        if size > API["message"]:
            errors.append(f'{title}: too long for one Telegram message; split it')
        # the platform's own limits (from the profile)
        for key, lim in (limits or {}).items():
            if str(key).lower() not in t:
                continue
            if lim.get("per_part"):
                for p in parts:
                    if len(p["text"]) > lim["per_part"]:
                        errors.append(f"{title} / {p.get('label', 'post')}: {len(p['text'])} chars, "
                                      f"{key} allows {lim['per_part']:,} per post")
            if lim.get("total") and len(whole) > lim["total"]:
                errors.append(f"{title}: {len(whole)} chars, {key} allows {lim['total']:,}")
            if lim.get("hashtags"):
                lo, hi = lim["hashtags"]
                n = len(re.findall(r"#\w+", whole))
                if n < lo or n > hi:
                    warnings.append(f"{title}: {n} hashtags (aim for {lo}-{hi})")
        e, w = text_problems(title, whole, banned_words)
        errors += e
        warnings += w
    return errors, warnings


def render(sections):
    """What --dry-run prints: every message with its blocks and their lengths."""
    out = []
    for s in sections:
        out.append(f"\n━━━━━━━━ {s['title']}")
        for p in s["parts"]:
            if p.get("label"):
                out.append(f"[{p['label']}]")
            if p.get("note"):
                out.append(f"(note) {p['note']}")
            out.append(f"{p['text']}\n  ↳ {len(p['text'])} chars")
    return "\n".join(out)
