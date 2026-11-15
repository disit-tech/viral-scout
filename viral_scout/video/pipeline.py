"""Recording + script → edit brief (cut) → captioned 1080×1920 master (render).

  cut:    transcript, rough cut, captions, draft edit brief → <job>/edit.json (no video yet)
  render: builds the video from <job>/edit.json (after Claude/you edited the cards)

Output in <job>: <slug>.mp4 (1080×1920, 30 fps, −14 LUFS), <slug>.srt, cover.png, edit.json, report.md.
Modes: camera (a video file, profile mode REAL) keeps the footage and adds captions; voice (an audio file, profile mode
VOICE+CARDS) puts brand cards behind the voice: a timing check or draft, not a finished post.
"""
import json
import re
import shutil
import time
from pathlib import Path

from . import captions, cards, media, plan
from .cut import build_timeline, match_script_words, rough_cut
from .script import load_script
from .settings import allowed, vocabulary

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
MODE_OF = {"camera": "REAL", "voice": "VOICE+CARDS"}


def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "video"


def find_script(v: dict, script: str) -> Path:
    p = Path(script)
    if not p.exists() and v.get("script_dir") and (v["script_dir"] / script).exists():
        p = v["script_dir"] / script
    if not p.exists():
        raise SystemExit(f"error: script not found: {script}" + (f" (also looked in {v['script_dir']})" if v.get("script_dir") else ""))
    return p.resolve()


def cut(v: dict, recording: str, script: str, section=None, name=None, broll=None, mode="auto", model=None,
        slug=None, out=None) -> Path:
    rec = Path(recording).resolve()
    if not rec.exists():
        raise SystemExit(f"error: recording not found: {rec}")
    script_path = find_script(v, script)
    try:
        sc = load_script(script_path, section, name or v.get("owner") or None)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    if not sc["lines"]:
        raise SystemExit("error: no spoken lines found in the script.")
    info = media.probe(rec)
    mode = mode if mode != "auto" else ("camera" if info["video"] else "voice")
    if not allowed(v, MODE_OF[mode]):
        raise SystemExit(f"error: mode {MODE_OF[mode]} is not in this profile's video.modes ({', '.join(v['modes'])}).")
    slug = slug or slugify(f"{sc['title']}" if section else rec.stem)
    job = Path(out or v["output_dir"]).resolve() / slug
    work = job / "work"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    log(f"[1/4] {rec.name}: {info['duration']:.1f}s, mode={mode} ({MODE_OF[mode]})")
    wav48, wav16 = media.extract_audio(rec, work)

    log("[2/4] transcript")
    from .transcribe import transcribe
    cache = work / f"words-{rec.stat().st_size}.json"
    words = match_script_words(transcribe(wav16, cache, model or v.get("whisper_model") or None, log,
                                          v.get("language") or "en"), sc["lines"])

    log(f"[3/4] rough cut against the script ({len(sc['lines'])} lines)")
    rc = rough_cut(sc["lines"], words, log)
    if not rc["lines"]:
        raise SystemExit("error: none of the script lines were found in the recording. Wrong script or section?")
    segs, timed = build_timeline(rc, words, info["duration"])
    fixed = captions.fix_words(rc["lines"], timed, vocabulary(v))
    out_dur = sum(e - s for s, e in segs)
    log(f"      {info['duration']:.1f}s → {out_dur:.1f}s, dropped {len(rc['dropped'])} piece(s): read `dropped` in edit.json")

    log("[4/4] draft edit brief")
    clips = sorted(p for p in Path(broll).iterdir() if p.suffix.lower() in VIDEO_EXT) if broll else []
    visuals, cover = plan.draft(rc["lines"], clips, v["cta_card"], v.get("stat_units"))
    edit = {
        "title": sc["title"], "slug": slug, "profile": v["name"], "recording": str(rec), "script": str(script_path),
        "mode": mode, "duration": round(out_dur, 3), "segments": segs,
        "lines": [{"text": l["text"], "part": l["part"], "t0": l["t0"], "t1": l["t1"], "take": l["take"]} for l in rc["lines"]],
        "words": fixed, "dropped": rc["dropped"], "missing": rc["missing"],
        "visuals": visuals, "cover": cover, "music": None,
    }
    text = json.dumps(edit, indent=1, ensure_ascii=False)
    (job / "edit.json").write_text(text, encoding="utf-8")
    (job / "edit.draft.json").write_text(text, encoding="utf-8")   # the auto draft, kept for comparison
    log(f"edit brief: {job / 'edit.json'}  ({time.time() - t0:.0f}s)")
    return job


def transcript(v: dict, media_file: str, out: str | None = None, model: str | None = None) -> Path:
    """Plain transcript of a recording (for repurposing): <out>.txt plus the word times in <out>.json."""
    from .transcribe import transcribe
    import tempfile
    rec = Path(media_file).resolve()
    if not rec.exists():
        raise SystemExit(f"error: recording not found: {rec}")
    txt = Path(out).resolve() if out else rec.with_suffix(".txt")
    txt.parent.mkdir(parents=True, exist_ok=True)
    cache = txt.with_suffix(".json")
    with tempfile.TemporaryDirectory() as d:
        _, wav16 = media.extract_audio(rec, Path(d))
        words = transcribe(wav16, cache, model or v.get("whisper_model") or None, log, v.get("language") or "en")
    txt.write_text(" ".join(w["w"] for w in words) + "\n", encoding="utf-8")
    return txt


def card_specs(edit: dict) -> list[dict]:
    specs = [dict(x["card"], id=x["id"]) for x in edit["visuals"] if not x.get("broll")]
    return specs + [dict(edit["cover"], id="cover")]


def render_cards(v: dict, job: Path) -> list[Path]:
    edit = json.loads((job / "edit.json").read_text(encoding="utf-8"))
    return cards.render(v, card_specs(edit), job / "work", job / "work" / "cards")


def render(v: dict, job: Path, music: str | None = None) -> Path:
    t0 = time.time()
    edit_file = job / "edit.json"
    if not edit_file.exists():
        raise SystemExit(f"error: no edit.json in {job} (run `cut` first)")
    edit = json.loads(edit_file.read_text(encoding="utf-8"))
    work = job / "work"
    work.mkdir(exist_ok=True)
    slug = edit["slug"]
    lines, words = edit["lines"], edit["words"]
    total = edit["duration"]
    rec = Path(edit["recording"])
    log(f"render {slug}: {total:.1f}s, mode={edit['mode']}")

    voice = media.cut_audio(work / "voice-48k.wav", [tuple(s) for s in edit["segments"]], work)

    ass, srt = work / "captions.ass", job / f"{slug}.srt"
    hook = {i for i, l in enumerate(lines) if l["part"] == "hook"}
    style = {"font": v["fonts"]["caption"], "accent": v["colors"]["accent"], "text": v["colors"]["caption"],
             "outline": v["colors"]["caption_outline"]}
    captions.write_ass(words, ass, hook, style)
    captions.write_srt(words, srt)

    if edit["mode"] == "camera":
        picture = media.cut_camera(rec, [tuple(s) for s in edit["segments"]], work)
    else:
        cards.render(v, card_specs(edit), work, work / "cards")
        clips = []
        vs = edit["visuals"]
        for n, x in enumerate(vs):
            start = 0.0 if n == 0 else lines[x["lines"][0]]["t0"]
            end = total if n + 1 == len(vs) else lines[vs[n + 1]["lines"][0]]["t0"]
            clip = work / f"{x['id']}.mp4"
            if x.get("broll"):
                media.broll_clip(Path(x["broll"]), end - start, clip)
            else:
                media.still_clip(work / "cards" / f"{x['id']}.png", end - start, clip, zoom_in=n % 2 == 0)
            clips.append(clip)
        picture = work / "picture.mp4"
        media.concat_clips(clips, picture, work)
        shutil.copy(work / "cards" / "cover.png", job / "cover.png")

    unsourced = [x["id"] for x in edit["visuals"] if "ADD SOURCE" in json.dumps(x["card"])]
    if unsourced and edit["mode"] == "voice":
        log(f"⚠ cards without a real source: {', '.join(unsourced)} (fill `source` in edit.json before posting)")
    master = job / f"{slug}.mp4"
    music = music or edit.get("music")
    if music and not Path(music).exists() and v.get("music_dir") and (v["music_dir"] / music).exists():
        music = str(v["music_dir"] / music)
    media.final_render(picture, voice, ass, master, Path(music) if music else None)
    if edit["mode"] == "camera":  # cover: a hook frame (platforms let you pick another)
        media.frame_png(master, min(1.0, total / 2), job / "cover.png")
    write_report(v, job, edit, media.probe(master), master)
    log(f"done in {time.time() - t0:.0f}s → {master}")
    return master


def write_report(v: dict, job: Path, edit: dict, info: dict, master: Path) -> None:
    vi = info["video"] or {}
    srcs = sorted({x["card"].get("source") for x in edit["visuals"] if x["card"].get("source")})
    compliance = (v.get("studio") or {}).get("compliance")
    rows = [
        f"# {edit['title']}", "",
        f"- Master: `{master.name}` ({vi.get('width')}×{vi.get('height')}, {info['duration']:.1f}s), captions `{edit['slug']}.srt`, `cover.png`",
        f"- Mode: {edit['mode']} ({MODE_OF.get(edit['mode'], '')}) · recording `{Path(edit['recording']).name}` · profile `{v['name']}`",
        "", "## Takes used", *[f"- {l['t0']:.1f}–{l['t1']:.1f}s ({l['take']['score']:.2f}) {l['text']}" for l in edit["lines"]],
        "", "## Dropped (flubs, retakes, chatter)", *([f"- {d}" for d in edit["dropped"]] or ["- none"]),
        "", "## Missing script lines (not found in the recording)", *([f"- {m}" for m in edit["missing"]] or ["- none"]),
        "", "## Before posting",
        "- Watch it once with sound. Every on-screen number needs a real source (cards with `ADD SOURCE` are not ready).",
        "- Sources on cards: " + (", ".join(srcs) if srcs else "none"),
        f"- AI voice or realistic AI visuals → platform AI label ON and first caption line: \"{v['ai_label']}\". "
        "Own voice + cards: no label needed.",
        "- Compliance check on the captions and description" + (f" against `{compliance}`" if compliance else "") + ".",
        f"- Technical check: `python -m viral_scout check {v['name']} \"{master}\"`.",
    ]
    if edit["mode"] == "voice":
        rows.append("- VOICE+CARDS is a draft and timing check, not a finished post (static cards read as boring).")
    (job / "report.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
