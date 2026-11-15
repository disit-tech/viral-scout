"""FFmpeg steps: probe, audio extract, cut + clean audio (denoise, −14 LUFS), visuals, final burn-in, cover."""
import json
import re
import subprocess
from pathlib import Path

FPS = 30
W, H = 1080, 1920
VCODEC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def run(args: list[str], log=None) -> str:
    from .deps import require
    require(args[0])
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit(f"ffmpeg step failed:\n{' '.join(args[:12])} ...\n{p.stderr[-2000:]}")
    return p.stderr


def probe(path: Path) -> dict:
    from .deps import require
    require("ffprobe")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, encoding="utf-8")
    info = json.loads(out.stdout or "{}")
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"
                  and s.get("disposition", {}).get("attached_pic") != 1), None)
    return {"duration": float(info.get("format", {}).get("duration", 0)), "video": video}


def extract_audio(src: Path, work: Path) -> tuple[Path, Path]:
    wav48, wav16 = work / "voice-48k.wav", work / "voice-16k.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "48000", str(wav48)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(wav48), "-ac", "1", "-ar", "16000", str(wav16)])
    return wav48, wav16


def _concat_filter(segs: list[tuple[float, float]], video: bool) -> str:
    parts, labels = [], []
    for n, (s, e) in enumerate(segs):
        parts.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={max(0, e - s - 0.012):.3f}:d=0.012[a{n}]")
        labels.append(f"[a{n}]")
        if video:
            parts.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS[v{n}]")
    if video:
        inter = "".join(f"[v{n}][a{n}]" for n in range(len(segs)))
        parts.append(f"{inter}concat=n={len(segs)}:v=1:a=1[vc][ac]")
    else:
        parts.append(f"{''.join(labels)}concat=n={len(segs)}:v=0:a=1[ac]")
    return ";".join(parts)


def cut_audio(wav48: Path, segs, work: Path) -> Path:
    """Cuts, then cleans: high-pass, FFT denoise, gentle compression, two-pass loudnorm to −14 LUFS / −1 dBTP."""
    raw = work / "cut-raw.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(wav48), "-filter_complex", _concat_filter(segs, False),
         "-map", "[ac]", str(raw)])
    clean_chain = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-24dB:ratio=3:attack=5:release=120:makeup=4dB"
    stats = run(["ffmpeg", "-y", "-hide_banner", "-i", str(raw), "-af",
                 f"{clean_chain},loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(stats[stats.rindex("{"): stats.rindex("}") + 1])
    final = work / "voice-final.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
         f"{clean_chain},loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,alimiter=limit=0.89:level=false",
         "-ar", "48000", str(final)])
    return final


def cut_camera(src: Path, segs, work: Path) -> Path:
    """Camera recordings: the same cut on the picture, scaled/cropped to a 1080×1920 frame."""
    out = work / "camera-cut.mp4"
    fc = _concat_filter(segs, True) + f";[vc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}[vout];[ac]anullsink"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter_complex", fc, "-map", "[vout]", "-an", *VCODEC, str(out)])
    return out


def still_clip(png: Path, dur: float, out: Path, zoom_in: bool = True) -> None:
    """A card as a clip with a slow push-in (Ken Burns), so a voice-only video never sits still."""
    frames = max(1, round(dur * FPS))
    z = "min(1+0.00055*on,1.08)" if zoom_in else "max(1.08-0.00055*on,1)"
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png), "-filter_complex",
         f"[0:v]scale={W * 2}:{H * 2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p[v]",
         "-map", "[v]", "-frames:v", str(frames), *VCODEC, str(out)])


def broll_clip(src: Path, dur: float, out: Path) -> None:
    """B-roll: cover-cropped to 9:16, muted, looped if short, slightly darkened so captions stay readable."""
    run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{dur:.3f}", "-an", "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},eq=brightness=-0.06:saturation=1.05,format=yuv420p",
         *VCODEC, str(out)])


def concat_clips(clips: list[Path], out: Path, work: Path) -> None:
    lst = work / "clips.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


def _ass_path(p: Path) -> str:
    # ffmpeg filter syntax on Windows: forward slashes, escaped drive colon
    return re.sub(r"^([A-Za-z]):", r"\1\\:", p.resolve().as_posix())


def final_render(picture: Path, voice: Path, ass: Path, out: Path, music: Path | None = None) -> None:
    """Burns the captions in, adds the voice (and optional music −20 dB under it), writes the master."""
    inputs = ["-i", str(picture), "-i", str(voice)]
    vf = f"[0:v]subtitles=filename='{_ass_path(ass)}'[v]"
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        af = "[2:a]volume=-20dB[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]"
        amap = "[a]"
        fc = f"{vf};{af}"
    else:
        fc, amap = vf, "1:a"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", amap,
         *VCODEC, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)])


def frame_png(video: Path, t: float, out: Path) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(out)])
