"""Animated films with HyperFrames (HeyGen, Apache 2.0): HTML/CSS compositions rendered to MP4 locally.

  film new    <name> --from <reference film>                a new film folder seeded from a reference film
  film words  <dir> <voice.wav> <script.md> [--section N] [--force]   word times for the scenes + the voice check
  film captions <dir>                                       compositions/captions.html from work-words.json (+ captions.json)
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


# Left out when a new film is seeded from a reference: renders, caches, the reference's own voice, word times,
# review and post pack. Kept: SPEC.md, index.html, compositions/ (its captions.html sets the caption look), assets/
# (fonts, sfx and their CREDITS.md), captions.json, other scripts.
SKIP_NAMES = {"out", "work", ".hyperframes", "snapshots", "work-words.json", "voice-check.md", "REVIEW.md",
              "POST.md", "still.png",
              "make_captions.py"}   # replaced by `film captions` (an unattended job can't run a film folder's Python)
SKIP_DIRS_CONTENT = {Path("assets") / "voice"}


def new(v: dict, name: str, reference: str) -> int:
    """Copy a reference film into a new folder, so an unattended job can reuse its structure, fonts and sound
    effects (binary files Claude can't write). The new folder must not exist yet."""
    src = resolve_dir(v, reference)
    p = Path(name)
    target = (v["films_dir"] / name) if v.get("films_dir") and len(p.parts) == 1 else p
    target = target.resolve()
    if target.exists():
        raise SystemExit(f"error: film folder already exists: {target}")

    def ignore(folder: str, names: list[str]) -> set[str]:
        rel = Path(folder).resolve().relative_to(src)
        if rel in SKIP_DIRS_CONTENT:
            return set(names)
        return {n for n in names if n in SKIP_NAMES}

    shutil.copytree(src, target, ignore=ignore)
    print(f"film: {target} (from {src.name}; renders, word times, voice, REVIEW.md and POST.md left out)")
    print("SPEC.md, index.html and compositions/ are the reference's: rewrite them for the new film.")
    return 0


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


def recover_edges(rc: dict, words: list[dict]) -> list[dict]:
    """A take that lost its first or last script word because Whisper heard it differently ("Do" as "so",
    "Save" as "Tape"): the take starts at the script's second word (or ends at its second-to-last), and the word
    just outside it is extra speech no other take uses. Extend the take by that word (the audio is the script
    word) and return [{heard, script, line, n}] (n = index in `words`). Changes rc in place (takes, `dropped`)."""
    from .cut import FILLERS, WILD, dropped_between, norm, tokens
    said = [norm(w["w"]) for w in words]
    heard = []

    def free(n: int) -> bool:
        return 0 <= n < len(words) and said[n] not in FILLERS and not any(
            l["take"]["i"] <= n < l["take"]["j"] for l in rc["lines"])

    for k, line in enumerate(rc["lines"]):
        script_words = [x for x in line["text"].split() if tokens(x)]
        toks = [tokens(x)[0] for x in script_words]
        take = line["take"]
        if len(toks) < 2 or WILD in (toks[0], toks[-1]):
            continue
        n = take["i"] - 1
        if said[take["i"]] == toks[1] != toks[0] and free(n) and said[n] != toks[1]:
            heard.append({"heard": words[n]["w"], "script": script_words[0], "line": k, "n": n})
            take.update(i=n, s=words[n]["s"])
        n = take["j"]
        if said[take["j"] - 1] == toks[-2] != toks[-1] and free(n) and said[n] != toks[-2]:
            heard.append({"heard": words[n]["w"], "script": script_words[-1], "line": k, "n": n})
            take.update(j=n + 1, e=words[n]["e"])
    if heard:
        rc["dropped"] = dropped_between(words, [(l["take"]["i"], l["take"]["j"]) for l in rc["lines"]])
    return heard


def align(lines: list[dict], raw: list[dict], vocab: dict | None = None, log=print) -> tuple[list[dict], dict, list[dict]]:
    """Transcript + script lines → (word times [{w, s, e, i}] in the script's words, rough cut, heard differently)."""
    from .captions import fix_words
    from .cut import match_script_words, rough_cut
    ws = match_script_words(raw, lines)
    rc = rough_cut(lines, ws, log)
    heard = recover_edges(rc, ws)
    script_text = {h["n"]: h["script"] for h in heard}  # the audio there is the script word: use the script's text
    timed, i = [], -1
    for k, line in enumerate(rc["lines"]):
        i = next(n for n in range(i + 1, len(lines)) if lines[n]["text"] == line["text"])
        for n in range(line["take"]["i"], line["take"]["j"]):
            w = ws[n]
            timed.append({"w": script_text.get(n, w["w"]), "s": w["s"], "e": w["e"], "line": k, "i": i})
    fixed = fix_words(rc["lines"], timed, vocab or {}, keep_digits=False)
    return [{"w": w["w"], "s": w["s"], "e": w["e"], "i": w["i"]} for w in fixed], rc, heard


def captions(v: dict, d: str) -> int:
    """Word-highlight captions for the film from work-words.json; settings in the film's captions.json."""
    from .film_captions import build
    out, n_items, n_groups = build(v, resolve_dir(v, d))
    print(f"captions: {n_items} words, {n_groups} caption groups → {out}")
    return 0


def words(v: dict, d: str, voice: str, script: str, section: str | None = None, model: str | None = None,
          force: bool = False) -> int:
    """Transcribe the film's voice, align it to the script, write work-words.json and a voice check."""
    from . import media
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
                     print, v.get("language") or "en", source=wav, force=force)
    out, rc, heard = align(sc["lines"], raw, vocabulary(v))
    (film / "work-words.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    long = [w for w in out if w["e"] - w["s"] > LONG_WORD]
    rows = [f"# Voice check: {wav.name}", "",
            f"- {len(out)} words, {len(rc['lines'])}/{len(sc['lines'])} script sentences found",
            "", "## Missing sentences (regenerate them)", *([f"- {m}" for m in rc["missing"]] or ["- none"]),
            "", "## Extra speech (repeats, wrong words: regenerate or mute)", *([f"- {x}" for x in rc["dropped"]] or ["- none"]),
            "", "## Heard differently (first or last word of a sentence; the script's word is used, listen to check)",
            *([f"- heard differently: {h['heard']} → {h['script']}" for h in heard] or ["- none"]),
            "", f"## Words longer than {LONG_WORD} s (may hide a repeat: look at the loudness envelope there)",
            *([f"- {w['s']:.2f}–{w['e']:.2f}s \"{w['w']}\" (sentence {w['i']})" for w in long] or ["- none"]),
            "", "Ears catch what this can't: watch the film with sound before it goes out."]
    (film / "voice-check.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    problems = len(rc["missing"]) + len(rc["dropped"]) + len(long)
    print(f"{'✓' if not problems else '⚠'} voice check: {len(rc['missing'])} missing, {len(rc['dropped'])} extra, "
          f"{len(heard)} heard differently, {len(long)} long word(s) → {film / 'voice-check.md'}")
    print(f"word times: {film / 'work-words.json'}")
    return 0 if not problems else 1
