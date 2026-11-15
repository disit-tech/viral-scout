"""Step 4: caption text fixed against the script, then word-highlight ASS (burned in) and an SRT (for upload).

Brand values (font, accent color for the spoken word, vocabulary fixes) come from the profile's `video:` block.
"""
import re
from difflib import SequenceMatcher

from .cut import norm, tokens, WILD
from .settings import ass_color

W, H = 1080, 1920
MAX_WORDS, MAX_CHARS = 3, 18  # 1–3 words per screen
MARGIN_V = 600  # caption baseline at y≈1320: clear of the bottom 20% (platform buttons start at y=1536)


def fix_words(lines: list[dict], timed: list[dict], vocab: dict | None = None, keep_digits: bool = True) -> list[dict]:
    """Spelling/case/punctuation from the script where the words match; numbers stay as digits (punchier on screen)
    unless keep_digits=False (films: the words are exactly the script).
    Then `vocab` ({regex: text}) fixes names Whisper gets wrong that the script may not contain."""
    vocab = vocab or {}
    out = []
    for k, line in enumerate(lines):
        ws = [w for w in timed if w["line"] == k]
        script_words = [x for x in re.split(r"\s+", line["text"]) if x]
        script_toks = [tokens(x)[0] if tokens(x) else "" for x in script_words]
        said = [norm(w["w"]) for w in ws]
        fixed = []
        sm = SequenceMatcher(None, script_toks, said, autojunk=False)
        for op, a0, a1, b0, b1 in sm.get_opcodes():
            part = [dict(w) for w in ws[b0:b1]]
            if op == "equal" or (op == "replace" and a1 - a0 == b1 - b0):
                for a, w in zip(range(a0, a1), part):
                    if script_toks[a] == WILD or (keep_digits and re.search(r"\d", w["w"])):
                        continue
                    w["w"] = script_words[a].strip("'\"“”‘’")
            elif op == "replace" and not keep_digits and _numeric(script_toks[a0:a1], part):
                # "one eight hundred" heard as "1-800", "forty eight" as "48": the script's words, the heard time
                part = _respell(script_words[a0:a1], part)
            fixed.extend(part)
        for w in fixed:
            w["w"] = apply_vocab(w["w"], vocab)
        out.extend(fixed)
    return out


def _numeric(script_toks: list[str], heard: list[dict]) -> bool:
    return bool(script_toks and heard) and all(re.fullmatch(r"\d+(?:st|nd|rd|th)?", t) for t in script_toks) \
        and all(re.search(r"\d", w["w"]) for w in heard)


def _respell(script_words: list[str], heard: list[dict]) -> list[dict]:
    """The heard span's time shared among the script's words by length."""
    s, e = heard[0]["s"], heard[-1]["e"]
    texts = [x.strip("'\"“”‘’") for x in script_words]
    total = sum(len(x) for x in texts) or 1
    out, t = [], s
    for x in texts:
        end = t + (e - s) * len(x) / total
        out.append({**heard[0], "w": x, "s": round(t, 3), "e": round(end, 3)})
        t = end
    out[-1]["e"] = e
    return out


def apply_vocab(text: str, vocab: dict) -> str:
    for pat, rep in vocab.items():
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def groups(words: list[dict]) -> list[list[dict]]:
    """1–3 words per screen; break after punctuation and at line changes."""
    gs: list[list[dict]] = []
    for w in words:
        g = gs[-1] if gs else None
        text = " ".join(x["w"] for x in g) + " " + w["w"] if g else w["w"]
        if (not g or len(g) >= MAX_WORDS or len(text) > MAX_CHARS or g[-1]["line"] != w["line"]
                or re.search(r"[.,!?:;]$", g[-1]["w"])):
            gs.append([w])
        else:
            g.append(w)
    return gs


def _t(sec: float) -> str:
    cs = int(round(sec * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def write_ass(words: list[dict], path, hook_lines: set[int], style: dict | None = None) -> None:
    """style: {"font", "accent", "text", "outline"} (hex colors); defaults are white text, yellow active word."""
    style = style or {}
    font = style.get("font") or "Segoe UI Black"
    glow = ass_color(style.get("accent") or "#ffc45c")
    white = ass_color(style.get("text") or "#ffffff")
    outline = ass_color(style.get("outline") or "#101010")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},96,{white},{white},{outline},&H64000000,0,0,0,0,100,100,0,0,1,7,3,2,60,60,{MARGIN_V},1
Style: Hook,{font},118,{white},{white},{outline},&H64000000,0,0,0,0,100,100,0,0,1,8,3,2,50,50,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    gs = groups(words)
    for n, g in enumerate(gs):
        end_g = g[-1]["e"]
        nxt = gs[n + 1][0]["s"] if n + 1 < len(gs) else end_g + 0.6
        end_g = nxt if nxt - end_g < 0.35 else end_g + 0.25
        st = "Hook" if g[0]["line"] in hook_lines else "Cap"
        for i, w in enumerate(g):
            s = w["s"] if i else min(w["s"], g[0]["s"])
            e = g[i + 1]["s"] if i + 1 < len(g) else end_g
            parts = []
            for j, x in enumerate(g):
                t = _esc(x["w"])
                parts.append(f"{{\\c{glow}\\fscx108\\fscy108}}{t}{{\\c{white}\\fscx100\\fscy100}}" if j == i else t)
            pop = "{\\fad(60,0)}" if i == 0 else ""
            rows.append(f"Dialogue: 0,{_t(s)},{_t(e)},{st},,0,0,0,,{pop}{' '.join(parts)}")
    path.write_text(head + "\n".join(rows) + "\n", encoding="utf-8")


def write_srt(words: list[dict], path) -> None:
    """Sentence-ish cues (≤42 chars) for the platforms' own caption upload."""
    cues: list[list[dict]] = []
    for w in words:
        c = cues[-1] if cues else None
        if (not c or c[-1]["line"] != w["line"] or len(" ".join(x["w"] for x in c)) + len(w["w"]) > 42
                or re.search(r"[.!?]$", c[-1]["w"])):
            cues.append([w])
        else:
            c.append(w)

    def ts(sec: float) -> str:
        ms = int(round(sec * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    out = []
    for n, c in enumerate(cues, 1):
        end = c[-1]["e"] + 0.2
        if n < len(cues):
            end = min(end, cues[n][0]["s"] - 0.02)
        out.append(f"{n}\n{ts(c[0]['s'])} --> {ts(end)}\n{' '.join(x['w'] for x in c)}\n")
    path.write_text("\n".join(out), encoding="utf-8")
