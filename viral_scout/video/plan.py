"""The edit brief (edit.json): one visual per script line, a cover. Auto-drafted here; /studio-video edit (Claude)
refines the cards' words and sources, then `render` builds the video from it."""
import re
from pathlib import Path

NUM_WORDS = r"(?:\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred)"
BASE_UNITS = ["%", "percent", "million", "billion", "thousand", "hundred", "hours?", "days?", "years?", "minutes?",
              "dollars?"]
STOP = set("a an the and or but so i i'm im you your my we our it its is are was be to of in on for at with this that "
           "these those if then just will can do does every time some".split())
NUMS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
NUMS.update({"twenty": "20", "thirty": "30", "forty": "40", "fifty": "50"})
MIN_CARD = 1.4  # lines shorter than this keep the previous visual (no flashing cuts)
DEFAULT_CTA = {"big": "Link in bio", "pill": "Link in bio", "triggers": ["link", "comment", "dm", "check"]}


def stat_pattern(extra_units: list[str] | None = None) -> re.Pattern:
    """A number (digits or a number word) plus an optional unit. Profiles add their own units ("kwh", "homes")."""
    units = BASE_UNITS + [u if re.search(r"[?\\()|]", u) else re.escape(u) for u in (extra_units or [])]
    unit = "(?:" + "|".join(units) + ")"
    # whole words only: "seventeenth" is not "seven" + "teenth"
    return re.compile(rf"(?<!\w)(\$?{NUM_WORDS}(?!\w)(?:\s+{unit}(?!\w))?)", re.I)


STAT = stat_pattern()


def _digits(s: str) -> str:
    """Number words → digits (punchier on screen): "two million" → "2 million"."""
    return re.sub(r"(?i)\b(" + "|".join(NUMS) + r")\b", lambda x: NUMS[x.group(1).lower()], s)


def _words(s: str) -> list[str]:
    return re.findall(r"[\w$%'’-]+", s)


def auto_card(line: dict, cta: dict | None = None, stat: re.Pattern = STAT) -> dict:
    cta = {**DEFAULT_CTA, **(cta or {})}
    text = line["text"].strip()
    low = text.lower()
    if line["part"] == "cta" and any(re.search(rf"\b{re.escape(t.lower())}\b", low) for t in cta["triggers"]):
        return {"kind": "cta", "big": cta["big"], "pill": cta["pill"]}
    m = stat.search(text)
    if m and not re.fullmatch(r"(?i)one", m.group(1)):
        before = _words(text[: m.start()])[-3:]
        after = _words(text[m.end():])[:5]
        big = _digits(m.group(1))
        return {"kind": "stat", "kicker": " ".join(before), "big": big, "small": " ".join(after),
                "source": "ADD SOURCE"}
    if ":" in text or text.count(",") >= 2:
        tail = text.split(":", 1)[-1]
        items = []
        for c in re.split(r",|\band\b", tail):
            ws = [w for w in _words(c) if w.lower() not in STOP and w.lower() not in ("my", "will", "what")]
            if ws:
                items.append(" ".join(ws[:3]).capitalize() + ("?" if text.endswith("?") else ""))
        if 2 <= len(items) <= 4:
            return {"kind": "list", "items": items}
    ws = [w for w in _words(text) if w.lower() not in STOP] or _words(text)
    big = ws[:3]
    if big:
        k = max(range(len(big)), key=lambda i: len(big[i]))
        big[k] = f"*{big[k]}*"
    return {"kind": "headline", "big": " ".join(big)}


def draft(lines: list[dict], broll: list[Path], cta: dict | None = None,
          units: list[str] | None = None) -> tuple[list[dict], dict]:
    """Assigns a card (or a B-roll clip) to each line; short lines ride on the previous visual."""
    stat = stat_pattern(units)
    visuals, b = [], 0
    headline_count = 0
    for k, line in enumerate(lines):
        dur = line["t1"] - line["t0"]
        if visuals and dur < MIN_CARD and line["part"] != "cta":
            visuals[-1]["lines"].append(k)
            continue
        card = auto_card(line, cta, stat)
        v = {"id": f"v{len(visuals) + 1:02d}", "lines": [k], "card": card}
        if card["kind"] == "headline":
            headline_count += 1
            if broll and headline_count % 2 == 1:  # alternate: B-roll, card, B-roll...
                v["broll"] = str(broll[b % len(broll)])
                b += 1
        visuals.append(v)
    hook = next((l for l in lines if l["part"] == "hook"), lines[0])
    m = stat.search(hook["text"])
    cover_big = f"*{_digits(m.group(1))}*" if m else " ".join(_words(hook["text"])[:4])
    cover = {"kind": "cover", "big": cover_big, "small": ""}
    return visuals, cover
