"""Reads the spoken lines of a script: a content-plan section, a /studio-video script file, or plain text.

Format: docs/video.md#script-files. `**Hook:** "..."`, `**Body:** "..."`, `**CTA:** "..."` (also `Line N`, `Close`,
`Outro`): the quoted text is spoken. A file without labels is plain text: every non-heading line is spoken.
"""
import re
from pathlib import Path

LABEL = re.compile(r"\*\*(Hook[^*]*|Body|CTA|Line \d+|Close|Outro)\s*:?\*\*\s*:?\s*(.*)", re.I)
QUOTED = re.compile(r"[\"“]([^\"”]+)[\"”]")
SENTENCE = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'’”]))\s+(?=[A-Z0-9\"'“‘])")


def _part(label: str) -> str:
    l = label.lower()
    return "hook" if l.startswith("hook") else "cta" if l.startswith(("cta", "close", "outro")) else "body"


def load_script(path: Path, section: str | None = None, name: str | None = None) -> dict:
    """Returns {"title", "lines": [{"text", "part"}], "on_screen"}; one line per spoken sentence."""
    text = path.read_text(encoding="utf-8")
    title = path.stem
    if section:
        text, title = _pick_section(text, section)
    parts: list[tuple[str, str]] = []
    on_screen = None
    for raw in text.splitlines():
        m = LABEL.search(raw)
        if m:
            quoted = QUOTED.findall(m.group(2))
            spoken = " ".join(quoted) if quoted else m.group(2).strip()
            if spoken:
                parts.append((_part(m.group(1)), spoken))
        elif raw.strip().lower().startswith("**on screen"):
            on_screen = raw.split(":", 1)[-1].strip(" *")
    if not parts:  # plain text: every non-empty, non-heading line is spoken
        body = [l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith(("#", ">", "---"))]
        parts = [("body", " ".join(body))]
    lines = []
    for part, spoken in parts:
        if name:
            spoken = spoken.replace("[NAME]", name)
        spoken = re.sub(r"\s*[—–]\s*", ", ", spoken)
        spoken = re.sub(r"\s+", " ", re.sub(r"\s*,(\s*,)+", ",", spoken)).strip()
        for s in SENTENCE.split(spoken):
            s = s.strip()
            if s:
                lines.append({"text": s, "part": part})
    return {"title": title, "lines": lines, "on_screen": on_screen}


def _pick_section(text: str, section: str) -> tuple[str, str]:
    """Section by number ("1" → '### 1. ...') or by a piece of its heading."""
    heads = list(re.finditer(r"^(#{2,4})\s+(.+)$", text, re.M))
    for i, h in enumerate(heads):
        heading = h.group(2).strip()
        hit = re.match(rf"{re.escape(section)}[.)]\s", heading) if section.isdigit() else section.lower() in heading.lower()
        if hit:
            end = next((x.start() for x in heads[i + 1 :] if len(x.group(1)) <= len(h.group(1))), len(text))
            return text[h.end() : end], heading
    raise ValueError(f"Section '{section}' not found in the script file.")
