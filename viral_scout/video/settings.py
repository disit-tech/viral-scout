"""The profile's `studio:` and `video:` blocks, merged with neutral defaults.

Paths are already ${ENV}-expanded by config.load. Relative paths are resolved against the profile's folder.
"""
import copy
import re
from pathlib import Path

from .. import config

MODES = ("REAL", "VOICE+CARDS", "FILM", "TWIN")

DEFAULTS = {
    "owner": "",                      # fills [NAME] in scripts and the AI label line
    "language": "en",                 # WhisperX language code
    "modes": ["REAL", "FILM", "VOICE+CARDS"],   # TWIN (a paid avatar service) is off unless listed
    "script_dir": "",                 # where /studio-video writes scripts (vault)
    "footage_dir": "",                # raw recordings, voice samples, B-roll (outside the vault and git)
    "output_dir": "",                 # default: <footage_dir>/out, else data/video/<profile>
    "films_dir": "",                  # HyperFrames film folders; default: <footage_dir>/films
    "music_dir": "",                  # commercial-library tracks only
    "whisper_model": "",              # default: large-v3 on GPU, small(.en) on CPU
    "voice": {"reference": "", "cfg": 0.5, "exaggeration": 0.5, "seed": 1, "pause": 0.25},
    "brand_label": "",                # small label on top of every card; default: studio.brand in capitals
    "logo": "",                       # PNG/SVG shown instead of the dot next to the label
    "card_template": "",              # your own card.html (same placeholders as the built-in one)
    "colors": {
        "bg": "#0b1124", "bg_deep": "#070b16", "bg_light": "#121a33",
        "accent": "#ffc45c", "text": "#fbfaf7", "muted": "#9aa3c0",
        "caption": "#ffffff", "caption_outline": "#101010",
        "brand_label": "",            # the card's brand label; default: accent
    },
    "fonts": {
        "display": "Segoe UI Black", "body": "Segoe UI", "caption": "Segoe UI Black",
        "files": [],                  # extra font files for cards: [{family, path, weight}]
        "still_bold": "", "still_regular": "",   # .ttf files for stills; default: a system font
    },
    "vocabulary": {},                 # caption fixes: {regex: text} or a list of words whose spelling to keep
    "stat_units": [],                 # extra units that make a number a stat card ("kwh", "homes")
    "cta_card": {"big": "", "pill": "Link in bio", "triggers": ["link", "comment", "dm", "check"]},
    "ai_label": "AI voice of me, script written by me. -{owner}",
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def _path(v, base: Path):
    if not v:
        return None
    if "${" in str(v):                 # an env var that isn't set: treat as missing, never as a relative folder
        return None
    p = Path(str(v)).expanduser()
    return p if p.is_absolute() else (base / p)


def load(profile) -> dict:
    """Profile name, path or an already loaded cfg → resolved video settings."""
    cfg = profile if isinstance(profile, dict) else config.load(profile)
    base = Path(cfg.get("_path", config.PROFILES / "x.yaml")).parent
    studio = dict(cfg.get("studio") or {})
    v = _merge(copy.deepcopy(DEFAULTS), copy.deepcopy(cfg.get("video") or {}))
    v["name"] = cfg.get("name", "profile")
    v["studio"] = studio
    v["brand"] = studio.get("brand") or v["name"]
    v["brand_label"] = v["brand_label"] or v["brand"].upper()
    cta = studio.get("cta") or {}
    v["cta_card"]["big"] = v["cta_card"].get("big") or cta.get("text") or "Link in bio"
    v["modes"] = [str(m).upper().replace(" ", "") for m in v["modes"] or []]
    for k in ("script_dir", "footage_dir", "output_dir", "films_dir", "music_dir", "logo", "card_template"):
        v[k] = _path(v[k], base)
    v["voice"]["reference"] = _path(v["voice"].get("reference"), base)
    for k in ("still_bold", "still_regular"):
        v["fonts"][k] = _path(v["fonts"].get(k), base)
    v["fonts"]["files"] = [dict(f, path=_path(f.get("path"), base)) for f in v["fonts"].get("files") or []]
    if not v["output_dir"]:
        v["output_dir"] = (v["footage_dir"] / "out") if v["footage_dir"] else config.ROOT / "data" / "video" / v["name"]
    if not v["films_dir"]:
        v["films_dir"] = (v["footage_dir"] / "films") if v["footage_dir"] else v["output_dir"] / "films"
    v["ai_label"] = v["ai_label"].replace("{owner}", v["owner"] or v["brand"])
    return v


def allowed(v: dict, mode: str) -> bool:
    return mode.upper().replace(" ", "") in v["modes"]


def vocabulary(v: dict) -> dict:
    """{regex: replacement}. A list entry "CityPower" becomes {r"\\bcitypower\\b": "CityPower"} (case and spelling kept)."""
    voc = v.get("vocabulary") or {}
    if isinstance(voc, dict):
        return {str(k): str(x) for k, x in voc.items()}
    return {rf"\b{re.escape(str(w))}\b": str(w) for w in voc}


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"not a hex color: #{h}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ass_color(h: str) -> str:
    """#rrggbb → ASS &H00BBGGRR."""
    r, g, b = hex_rgb(h)
    return f"&H00{b:02X}{g:02X}{r:02X}"
