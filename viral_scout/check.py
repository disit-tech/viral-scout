"""Pre-publish check for YOUR OWN video file: technical standards, pacing, sound, script structure.

  python -m viral_scout check <profile> <video file> [--platform tiktok|reels|shorts]
Measures with the system ffmpeg/ffprobe (and faster-whisper if installed), writes a report next to the profile's
reports (<output_dir>/checks/) and JSON in data/checks/<profile>/. Frames are saved so the /viral-scout skill can
judge first-frame impact, on-screen text and captions, then fill the 20-criteria scorecard (score set ... check:<id>).
Targets are practical starting points, not platform rules; each result says what it compared against.
"""
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import config

TARGETS = {
    "aspect": 9 / 16, "min_w": 1080, "min_h": 1920, "min_fps": 24,
    "lufs": (-16.0, -12.0),          # common loudness target for mobile/streaming platforms (~-14 LUFS)
    "true_peak": -1.0,               # dBTP ceiling to avoid clipping after platform transcoding
    "first_cut_s": 3.0,              # first visual change within the hook window
    "avg_shot_s": 4.0,               # heuristic for short-form pacing
    "max_shot_s": 8.0,               # a single shot longer than this risks drop-off
    "speech_start_s": 1.0,           # talking starts within the first second
    "max_len_s": {"tiktok": 180, "reels": 180, "shorts": 180, "any": 180},
}


def _run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout + p.stderr


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    d = json.loads(out or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    rate = v.get("avg_frame_rate", "0/1").split("/")
    fps = float(rate[0]) / float(rate[1]) if len(rate) == 2 and float(rate[1] or 0) else 0
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    rot = int((v.get("tags") or {}).get("rotate", 0) or 0)
    for sd in v.get("side_data_list") or []:
        rot = int(sd.get("rotation", rot) or rot)
    if abs(rot) in (90, 270):
        w, h = h, w
    return {"width": w, "height": h, "fps": round(fps, 2), "codec": v.get("codec_name"),
            "duration": float(d.get("format", {}).get("duration") or 0), "has_audio": a is not None,
            "bitrate_kbps": round(int(d.get("format", {}).get("bit_rate") or 0) / 1000)}


def loudness(path):
    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", out)
    return {"lufs": float(i[-1]) if i else None, "true_peak": float(tp[-1]) if tp else None}


def silences(path, noise="-35dB", dur=0.6):
    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", f"silencedetect=n={noise}:d={dur}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", out)]
    return [(max(0.0, s), e) for s, e in zip(starts, ends)]


def cuts(path, threshold=0.3):
    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf",
                f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)]


def black_start(path):
    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", "blackdetect=d=0.2:pix_th=0.1",
                "-an", "-t", "3", "-f", "null", "-"])
    m = re.search(r"black_start:0(?:\.0+)? black_end:([\d.]+)", out)
    return float(m.group(1)) if m else 0.0


def frames(path, folder, duration):
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for name, t in [("first", 0.0), ("1s", 1.0), ("3s", 3.0), ("middle", duration / 2), ("last", max(duration - 1.0, 0))]:
        if t > duration:
            continue
        f = folder / f"frame-{name}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale='min(720,iw)':-2", str(f)], capture_output=True)
        if f.exists():
            out.append(str(f))
    return out


def transcript(path, duration, errors):
    try:
        from . import whisper
        if not whisper.available():
            return None
        from .transcripts import split
        audio = whisper._decode(Path(path))
        segs, info = whisper._model("base").transcribe(audio, vad_filter=True, beam_size=1)
        segments = [(s.start, s.text) for s in segs]
        parts = split(segments, info.duration or duration)
        parts["speech_start"] = segments[0][0] if segments else None
        return parts
    except Exception as err:
        errors.append(f"transcript: {str(err)[:150]}")
        return None


def status(ok, warn=False):
    return "pass" if ok else ("warn" if warn else "fail")


def run_check(cfg, video, platform="any"):
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(video)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg/ffprobe not found on PATH")
    errors = []
    slug = re.sub(r"[^\w-]+", "-", video.stem.lower()).strip("-")[:50] + "-" + datetime.now().strftime("%Y%m%d-%H%M")
    data_dir = config.ROOT / "data" / "checks" / cfg["name"] / slug
    p = probe(video)
    dur = p["duration"]
    loud = loudness(video) if p["has_audio"] else {"lufs": None, "true_peak": None}
    sil = silences(video) if p["has_audio"] else []
    cut = cuts(video)
    black = black_start(video)
    pics = frames(video, data_dir, dur)
    tr = transcript(video, dur, errors) if p["has_audio"] else None

    shots = [b - a for a, b in zip([0.0] + cut, cut + [dur])] if dur else []
    avg_shot = sum(shots) / len(shots) if shots else None
    first_cut = cut[0] if cut else None
    silent_hook = sum(min(e, 3) - s for s, e in sil if s < 3)
    t = TARGETS
    ratio = p["width"] / p["height"] if p["height"] else 0
    results = [
        ("Aspect ratio", status(abs(ratio - t["aspect"]) < 0.02, warn=ratio < 1),
         f"{p['width']}×{p['height']} ({ratio:.3f}); target 9:16 vertical"),
        ("Resolution", status(p["width"] >= t["min_w"] and p["height"] >= t["min_h"], warn=p["height"] >= 1280),
         f"target at least 1080×1920"),
        ("Frame rate", status(p["fps"] >= t["min_fps"]), f"{p['fps']} fps; target 24+"),
        ("Length", status(dur <= t["max_len_s"].get(platform, 180), warn=True),
         f"{dur:.1f} s; keep each second earning its place (long-form needs a reason)"),
        ("Audio present", status(p["has_audio"]), "a silent video loses most viewers who watch with sound on"),
    ]
    if loud["lufs"] is not None:
        lo, hi = t["lufs"]
        results.append(("Loudness", status(lo <= loud["lufs"] <= hi, warn=lo - 4 <= loud["lufs"] <= hi + 2),
                        f"{loud['lufs']:.1f} LUFS integrated; aim for about -14 (-16 to -12)"))
    if loud["true_peak"] is not None:
        results.append(("Peaks", status(loud["true_peak"] <= t["true_peak"], warn=loud["true_peak"] <= 0),
                        f"true peak {loud['true_peak']:.1f} dBTP; keep at or below -1 to avoid clipping"))
    results += [
        ("Black frames at start", status(black < 0.2, warn=black < 0.5), f"{black:.2f} s of black at the start"),
        ("First visual change", status(first_cut is not None and first_cut <= t["first_cut_s"], warn=first_cut is not None and first_cut <= 5),
         f"first cut at {first_cut:.1f} s" if first_cut is not None else "no cuts detected (one continuous shot)"),
        ("Pacing", status(avg_shot is not None and avg_shot <= t["avg_shot_s"], warn=avg_shot is not None and avg_shot <= 6),
         f"{len(cut)} cuts, average shot {avg_shot:.1f} s" if avg_shot else "n/a"),
        ("Pattern interrupts", status(bool(shots) and max(shots) <= t["max_shot_s"], warn=bool(shots) and max(shots) <= 12),
         f"longest shot {max(shots):.1f} s; keep a change every few seconds" if shots else "n/a"),
        ("Silence in the hook", status(silent_hook < 0.5, warn=silent_hook < 1.2),
         f"{silent_hook:.1f} s of silence in the first 3 s"),
    ]
    if tr:
        ss = tr.get("speech_start")
        results.append(("Speech starts", status(ss is not None and ss <= t["speech_start_s"], warn=ss is not None and ss <= 2),
                        f"first words at {ss:.1f} s" if ss is not None else "no speech detected"))
        results.append(("Clear CTA in the ending", status(bool(tr.get("cta")), warn=True),
                        f"ending: “{tr['cta']}”" if tr.get("cta") else "nothing said in the last 5 s; add a next step"))
    manual = ["Captions are accurate, readable, high-contrast and timed (check the frames)",
              "Important text sits inside platform safe zones (not under the buttons and caption)",
              "Branding is recognizable without dominating the first seconds",
              "Claims are accurate, disclosures present, rights to music and footage secured",
              "Works on a phone: text and product details readable at small size"]
    report = {
        "file": str(video), "name": video.name, "slug": slug, "profile": cfg["name"], "platform": platform,
        "checked": datetime.now().isoformat(timespec="seconds"), "probe": p, "loudness": loud,
        "silences": sil, "cuts": cut, "shots": [round(s, 2) for s in shots], "black_start": black,
        "frames": pics, "transcript": tr, "errors": errors,
        "results": [{"area": a, "status": s, "detail": d} for a, s, d in results], "manual": manual,
        "summary": {k: sum(1 for r in results if r[1] == k) for k in ("pass", "warn", "fail")},
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    md = _markdown(report)
    out = Path(cfg["output_dir"]) / "checks"
    out.mkdir(parents=True, exist_ok=True)
    note = out / f"{slug}.md"
    note.write_text(md, encoding="utf-8")
    return report, note


def _markdown(r):
    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
    tr = r.get("transcript") or {}
    lines = ["---", "type: video-check", f"profile: {r['profile']}", f"file: \"{r['name']}\"", f"date: {r['checked'][:10]}",
             "---", "", f"# Pre-publish check: {r['name']}", "",
             f"{r['summary']['pass']} pass · {r['summary']['warn']} warn · {r['summary']['fail']} fail · "
             f"{r['probe']['duration']:.1f} s · {r['probe']['width']}×{r['probe']['height']}", "",
             "| Area | Result | Detail |", "|---|---|---|"]
    lines += [f"| {x['area']} | {icon[x['status']]} | {x['detail']} |" for x in r["results"]]
    if tr:
        lines += ["", "## Script", "", f"> **Hook (first 4 s):** {tr.get('hook') or '—'}", "",
                  f"> **Ending (last 5 s):** {tr.get('cta') or '—'}", "", f"Pace: {tr.get('wpm') or '—'} words/min", "",
                  "### Transcript", "", tr.get("transcript", "")]
    lines += ["", "## Check by eye", ""] + [f"- [ ] {m}" for m in r["manual"]]
    lines += ["", "## Creative scorecard", "",
              f"Run `/viral-scout {r['profile']} check {r['slug']}` in Claude Code to score the 20 criteria (100 points) "
              "from the frames and the transcript.", ""]
    return "\n".join(lines)
