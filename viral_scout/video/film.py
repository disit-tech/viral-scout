"""Animated films with HyperFrames (HeyGen, Apache 2.0): HTML/CSS compositions rendered to MP4 locally.

  film words  <dir> <voice.wav> <script.md> [--section N]   word times for the scenes + the voice check
  film check  <dir> [hyperframes check options]             lint, runtime, layout and contrast gate (0 errors)
  film render <dir> [--out FILE] [--quality delivery]       MP4, then loudness against −14 LUFS / −1 dBTP

<dir> is a film folder (SPEC.md, index.html, compositions/, assets/); a bare name is looked up in video.films_dir.
The voice is the clock: `words` writes <dir>/work-words.json ([{w, s, e, i}], i = script sentence) for the
compositions' timelines and captions. HyperFrames' own Claude skills ship in its package (dist/skills/).
"""
import json
import shutil
import subprocess
from pathlib import Path

from . import deps

LONG_WORD = 0.8   # a single word longer than this may hide a repeated word ("two two") the aligner merged
LUFS, TRUE_PEAK = (-16.0, -12.0), -1.0


def resolve_dir(v: dict, d: str) -> Path:
    p = Path(d)
    if not p.exists() and v.get("films_dir") and (v["films_dir"] / d).exists():
        p = v["films_dir"] / d
    if not p.is_dir():
        raise SystemExit(f"error: film folder not found: {d}" + (f" (also looked in {v['films_dir']})" if v.get("films_dir") else ""))
    return p.resolve()


def _hf(args: list[str], cwd: Path) -> int:
    deps.require("node")
    hf = deps.hyperframes_bin(required=True)
    return subprocess.run([str(hf), *args], cwd=cwd).returncode


def check(v: dict, d: str, extra: list[str] | None = None) -> int:
    film = resolve_dir(v, d)
    return _hf(["check", str(film), *(extra or [])], film)


def render(v: dict, d: str, out: str | None = None, quality: str = "delivery", extra: list[str] | None = None) -> int:
    film = resolve_dir(v, d)
    target = Path(out).resolve() if out else film / "out" / f"{film.name}-film.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    rc = _hf(["render", str(film), "-o", str(target), "-q", quality, *(extra or [])], film)
    if rc != 0:
        return rc
    if target.exists() and shutil.which("ffmpeg"):
        from ..check import loudness
        ld = loudness(target)
        lufs, tp = ld["lufs"], ld["true_peak"]
        ok = lufs is not None and LUFS[0] <= lufs <= LUFS[1] and (tp is None or tp <= TRUE_PEAK)
        print(f"{'✓' if ok else '⚠'} loudness {lufs} LUFS, true peak {tp} dBTP (target about −14 LUFS, peak ≤ −1 dBTP)")
    print(f"film: {target}")
    return 0


def words(v: dict, d: str, voice: str, script: str, section: str | None = None, model: str | None = None) -> int:
    """Transcribe the film's voice, align it to the script, write work-words.json and a voice check."""
    from . import media
    from .captions import fix_words
    from .cut import match_script_words, rough_cut
    from .pipeline import find_script
    from .script import load_script
    from .settings import vocabulary
    from .transcribe import transcribe

    film = resolve_dir(v, d)
    wav = Path(voice).resolve()
    if not wav.exists():
        raise SystemExit(f"error: voice file not found: {wav}")
    sc = load_script(find_script(v, script), section, v.get("owner") or None)
    work = film / "work"
    work.mkdir(exist_ok=True)
    _, wav16 = media.extract_audio(wav, work)
    raw = transcribe(wav16, work / f"words-{wav.stat().st_size}.json", model or v.get("whisper_model") or None,
                     print, v.get("language") or "en")
    ws = match_script_words(raw, sc["lines"])
    rc = rough_cut(sc["lines"], ws, print)
    timed, i = [], -1
    for k, line in enumerate(rc["lines"]):
        i = next(n for n in range(i + 1, len(sc["lines"])) if sc["lines"][n]["text"] == line["text"])
        for w in ws[line["take"]["i"]:line["take"]["j"]]:
            timed.append({"w": w["w"], "s": w["s"], "e": w["e"], "line": k, "i": i})
    fixed = fix_words(rc["lines"], timed, vocabulary(v), keep_digits=False)
    out = [{"w": w["w"], "s": w["s"], "e": w["e"], "i": w["i"]} for w in fixed]
    (film / "work-words.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    long = [w for w in out if w["e"] - w["s"] > LONG_WORD]
    rows = [f"# Voice check: {wav.name}", "",
            f"- {len(out)} words, {len(rc['lines'])}/{len(sc['lines'])} script sentences found",
            "", "## Missing sentences (regenerate them)", *([f"- {m}" for m in rc["missing"]] or ["- none"]),
            "", "## Extra speech (repeats, wrong words: regenerate or mute)", *([f"- {x}" for x in rc["dropped"]] or ["- none"]),
            "", f"## Words longer than {LONG_WORD} s (may hide a repeat: look at the loudness envelope there)",
            *([f"- {w['s']:.2f}–{w['e']:.2f}s \"{w['w']}\" (sentence {w['i']})" for w in long] or ["- none"]),
            "", "Ears catch what this can't: watch the film with sound before it goes out."]
    (film / "voice-check.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    problems = len(rc["missing"]) + len(rc["dropped"]) + len(long)
    print(f"{'✓' if not problems else '⚠'} voice check: {len(rc['missing'])} missing, {len(rc['dropped'])} extra, "
          f"{len(long)} long word(s) → {film / 'voice-check.md'}")
    print(f"word times: {film / 'work-words.json'}")
    return 0 if not problems else 1
