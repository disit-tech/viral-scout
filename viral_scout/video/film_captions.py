"""`film captions <dir>`: compositions/captions.html (word-highlight captions) from the film's work-words.json.

Replaces the per-film make_captions.py scripts: an unattended job may run viral_scout commands, not a Python file
in a film folder. What used to be edited in each copy of that script lives in the film's optional captions.json:

  {"fix":   {"backup": "BACKUP"},                       one word → caption text (exact word, as in work-words.json)
   "merge": {"three hundred": "300", "five minutes.": "5 minutes."},   word runs → one caption item
   "max_words": 3, "max_chars": 16, "gap": 0.15,      a new caption group after N words, N characters, a pause > gap s
   "color": "#ffffff", "highlight": "#ffc45c",        word color, color of the word being spoken
   "css": "..."}                                       the whole <style> block's content

The look (the <style> block and the two colors) is kept from the film's current compositions/captions.html, which
`film new --from` copies from the reference film, so a new film captions like its reference. Without one: the
profile's video.colors (caption, accent, caption_outline) and video.fonts.caption.
"""
import json
import re
from html import escape
from pathlib import Path

MAX_WORDS, MAX_CHARS, GAP = 3, 16, 0.15
CONFIG = "captions.json"


def default_css(v: dict) -> str:
    c, f = v.get("colors") or {}, v.get("fonts") or {}
    font = f.get("caption") or "Segoe UI Black"
    return f"""
    #root {{ position: absolute; inset: 0; }}
    .cap {{
      position: absolute; left: 0; right: 0; top: 1176px; text-align: center; opacity: 0;
      font-family: "{font}", "Segoe UI", Arial, sans-serif; font-weight: 800; font-size: 76px; line-height: 1.1;
      color: {c.get("caption") or "#ffffff"}; -webkit-text-stroke: 6px {c.get("caption_outline") or "#101010"}; paint-order: stroke fill;
      text-shadow: 0 3px 10px rgba(0, 0, 0, 0.8);
    }}
    .cap .pl {{
      display: inline-block; padding: 4px 28px 12px; border-radius: 28px;
      background: rgba(0, 0, 0, 0.6); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }}
  """.rstrip() + "\n  "


def existing_look(html: str) -> dict:
    """The <style> block and the word colors of a captions.html (this command's or an old make_captions.py's)."""
    look = {}
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if m:
        look["css"] = m.group(1)
    m = re.search(r'data-color="([^"]+)"\s+data-highlight="([^"]+)"', html)
    if m:
        look["color"], look["highlight"] = m.group(1), m.group(2)
    else:  # an old make_captions.py file: highlight set at the word's start, then the base color
        cols = re.findall(r'tl\.set\("#cw\d+_\d+", \{ color: "([^"]+)" \}', html)
        if len(cols) >= 2:
            look["highlight"], look["color"] = cols[0], cols[1]
    return look


def _merges(m) -> list[tuple[list[str], str]]:
    if isinstance(m, dict):
        return [(str(k).split(), str(x)) for k, x in m.items()]
    return [(list(seq) if isinstance(seq, list) else str(seq).split(), str(rep)) for seq, rep in (m or [])]


def items(words: list[dict], fix: dict | None = None, merge=None) -> list[dict]:
    """work-words.json → [{t, s, e}]: fixed words, then word runs merged into one item ("three hundred" → "300")."""
    fix, merge = fix or {}, _merges(merge)
    its = [{"t": fix.get(w["w"], w["w"]), "s": w["s"], "e": w["e"]} for w in words]
    k, out = 0, []
    while k < len(its):
        for seq, rep in merge:
            if seq and [x["t"] for x in its[k:k + len(seq)]] == seq:
                out.append({"t": rep, "s": its[k]["s"], "e": its[k + len(seq) - 1]["e"]})
                k += len(seq)
                break
        else:
            out.append(its[k])
            k += 1
    return out


def groups(its: list[dict], max_words=MAX_WORDS, max_chars=MAX_CHARS, gap=GAP) -> list[list[dict]]:
    """1-3 words per screen: a new group after max_words, past max_chars, after . , ? ! or a pause over gap s."""
    out: list[list[dict]] = []
    for it in its:
        g = out[-1] if out else None
        if (not g or len(g) >= max_words or len(" ".join(x["t"] for x in g + [it])) > max_chars
                or re.search(r"[.,?!]$", g[-1]["t"]) or it["s"] - g[-1]["e"] > gap):
            out.append([it])
        else:
            g.append(it)
    return out


def html(gs: list[list[dict]], css: str, color: str, highlight: str) -> str:
    divs, js = [], []
    for gi, g in enumerate(gs):
        start = max(0.15, g[0]["s"] - 0.05)
        nxt = gs[gi + 1][0]["s"] - 0.05 if gi + 1 < len(gs) else g[-1]["e"] + 0.6
        end = min(g[-1]["e"] + 0.35, nxt)
        spans = " ".join(f'<span id="cw{gi}_{wi}">{escape(w["t"])}</span>' for wi, w in enumerate(g))
        divs.append(f'    <div id="cg{gi}" class="cap"><span class="pl">{spans}</span></div>')
        js.append(f'tl.fromTo("#cg{gi}", {{ opacity: 0, scale: 0.92 }}, {{ opacity: 1, scale: 1, duration: 0.12, '
                  f'ease: "power3.out", immediateRender: false }}, {start:.3f});')
        for wi, w in enumerate(g):
            js.append(f'tl.set("#cw{gi}_{wi}", {{ color: "{highlight}" }}, {w["s"]:.3f}); '
                      f'tl.set("#cw{gi}_{wi}", {{ color: "{color}" }}, {min(w["e"] + 0.05, end):.3f});')
        js.append(f'tl.to("#cg{gi}", {{ opacity: 0, duration: 0.08, ease: "power2.in" }}, {end - 0.08:.3f}); '
                  f'tl.set("#cg{gi}", {{ opacity: 0, visibility: "hidden" }}, {end:.3f});')
    body = "\n".join(divs)
    script = "\n    ".join(js)
    return f"""<template>
  <!-- Made by `python -m viral_scout video <profile> film captions` from work-words.json (+ captions.json). Run it again after the voice changes; edits here are overwritten. -->
  <style>{css}</style>
  <div id="root" data-composition-id="captions" data-width="1080" data-height="1920" data-color="{escape(color)}" data-highlight="{escape(highlight)}">
{body}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.set(".cap", {{ opacity: 0 }}, 0);
    {script}
    window.__timelines["captions"] = tl;
  </script>
</template>
"""


def build(v: dict, film: Path) -> tuple[Path, int, int]:
    """Writes <film>/compositions/captions.html. Returns (path, items, groups)."""
    ww = film / "work-words.json"
    if not ww.exists():
        raise SystemExit(f"error: {ww} not found: run `film words` first")
    words = json.loads(ww.read_text(encoding="utf-8"))
    cf = film / CONFIG
    try:
        conf = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    except json.JSONDecodeError as e:
        raise SystemExit(f"error: {cf} is not valid JSON: {e}")
    out = film / "compositions" / "captions.html"
    look = existing_look(out.read_text(encoding="utf-8")) if out.exists() else {}
    c = v.get("colors") or {}
    css = conf.get("css") or look.get("css") or default_css(v)
    color = conf.get("color") or look.get("color") or c.get("caption") or "#ffffff"
    highlight = conf.get("highlight") or look.get("highlight") or c.get("accent") or "#ffc45c"
    its = items(words, conf.get("fix"), conf.get("merge"))
    gs = groups(its, int(conf.get("max_words", MAX_WORDS)), int(conf.get("max_chars", MAX_CHARS)),
                float(conf.get("gap", GAP)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html(gs, css, color, highlight), encoding="utf-8")
    return out, len(its), len(gs)
