"""Brand cards: card.html filled with the profile's colors, fonts, logo and label, rendered to PNG by Playwright."""
import html
import json
import re
import subprocess
from pathlib import Path

from . import deps
from .settings import hex_rgb

TEMPLATE = deps.NODE_DIR / "card.html"
RENDERER = deps.NODE_DIR / "render-cards.mjs"


def _css_font(name: str) -> str:
    """A CSS font-family value: quoted family names, generic names left bare."""
    parts = [p.strip().strip("\"'") for p in str(name).split(",") if p.strip()]
    generic = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
    return ", ".join(p if p in generic else f'"{p}"' for p in parts) or "sans-serif"


def _font_faces(files: list[dict]) -> str:
    rules = []
    for f in files:
        p = f.get("path")
        if not p or not f.get("family"):
            continue
        rules.append(f'@font-face {{ font-family: "{f["family"]}"; src: url("{Path(p).resolve().as_uri()}"); '
                     f'font-weight: {int(f.get("weight", 400))}; }}')
    return "\n  ".join(rules)


def values(v: dict) -> dict:
    """Placeholder → value for the card template, from resolved video settings."""
    c, fo = v["colors"], v["fonts"]
    logo = v.get("logo")
    logo_html = (f'<img src="{html.escape(Path(logo).resolve().as_uri())}" alt="">' if logo and Path(logo).exists()
                 else '<span class="dot"></span>')
    for k in ("bg", "bg_deep", "bg_light", "accent", "text", "muted"):
        hex_rgb(c[k])                     # fail early on a bad color in the profile
    return {
        "bg": c["bg"], "bg_deep": c["bg_deep"], "bg_light": c["bg_light"], "accent": c["accent"],
        "accent_rgb": ",".join(str(x) for x in hex_rgb(c["accent"])), "text": c["text"], "muted": c["muted"],
        "font_display": _css_font(fo["display"]), "font_body": _css_font(fo["body"]),
        "font_faces": _font_faces(fo.get("files") or []),
        "logo_html": logo_html, "brand_label": html.escape(v["brand_label"]),
    }


def fill(template_text: str, vals: dict) -> str:
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals.get(m.group(1), m.group(0))), template_text)
    left = sorted(set(re.findall(r"\{\{(\w+)\}\}", out)))
    if left:
        raise ValueError(f"card template has unknown placeholders: {', '.join(left)}")
    return out


def write_template(v: dict, work: Path) -> Path:
    src = v.get("card_template") or TEMPLATE
    if not Path(src).exists():
        raise SystemExit(f"error: card template not found: {src}")
    out = work / "card.html"
    out.write_text(fill(Path(src).read_text(encoding="utf-8"), values(v)), encoding="utf-8")
    return out


def render(v: dict, cards: list[dict], work: Path, out_dir: Path) -> list[Path]:
    """cards: [{id, kind, big, ...}] → <out_dir>/<id>.png."""
    deps.require("node")
    deps.node_package("playwright", required=True)
    work.mkdir(parents=True, exist_ok=True)
    page = write_template(v, work)
    spec = work / "cards.json"
    spec.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    p = subprocess.run(["node", str(RENDERER), str(page), str(spec), str(out_dir)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=deps.NODE_DIR)
    if p.returncode != 0:
        hint = " (missing browser? run `npx playwright install chromium` in viral_scout/video/node)" \
            if "Executable doesn't exist" in p.stderr else ""
        raise SystemExit(f"card render failed{hint}:\n{p.stderr[-1500:]}")
    return [out_dir / f"{c['id']}.png" for c in cards]
