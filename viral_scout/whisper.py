"""Local speech-to-text for posts without public captions (Instagram reels, TikTok, uncaptioned Shorts).

Optional: `pip install faster-whisper`. Downloads the post's audio with yt-dlp (public posts only), transcribes
on the CPU (int8), deletes the audio. The first run downloads the model (~150 MB for "base").
Profile:  transcribe: {whisper: true, model: base, max_per_run: 8, max_seconds: 180}
"""
import os
import tempfile
from pathlib import Path

from . import usage
from .transcripts import apply, split

_MODEL = {}


def available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _model(name):
    if name not in _MODEL:
        from faster_whisper import WhisperModel
        _MODEL[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODEL[name]


def _decode(path):
    """Audio file → 16 kHz mono float32 via the system ffmpeg (avoids PyAV version clashes)."""
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe(item, cfg, errors):
    """Fill item.transcript/hook/cta/wpm from the audio. Returns True on success."""
    from .ytdlp import yt_dlp
    opts = cfg.get("transcribe") or {}
    if item.duration and item.duration > opts.get("max_seconds", 180):
        return False
    with tempfile.TemporaryDirectory(prefix="vs-audio-") as tmp:
        ydl_opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "bestaudio/best",
                    "outtmpl": os.path.join(tmp, "a.%(ext)s"), "socket_timeout": 30, "noplaylist": True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item.url])
        except Exception as err:
            errors.append(f"whisper {item.key}: audio download failed: {str(err)[:120]}")
            return False
        files = list(Path(tmp).glob("a.*"))
        if not files:
            return False
        try:
            audio = _decode(files[0])
            segs, info = _model(opts.get("model", "base")).transcribe(audio, vad_filter=True, beam_size=1)
            segments = [(s.start, s.text) for s in segs]
        except Exception as err:
            errors.append(f"whisper {item.key}: {str(err)[:120]}")
            return False
    usage.add("whisper_seconds", int(info.duration or 0))
    parts = split(segments, info.duration or item.duration)
    if parts["transcript"]:
        apply(item, parts)
        return True
    return False
