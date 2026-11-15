"""Step 1: word-level transcript with WhisperX (GPU when CUDA works, CPU fallback). Cached next to the job.

WhisperX needs its own Python 3.11 env (`.venv-video`, see scripts/setup-video.ps1). The main CLI calls `transcribe()`,
which runs in this interpreter if WhisperX is importable here, else in the video env as
  <video python> -m viral_scout.video.transcribe <wav16k> <cache.json> [--model M] [--language en]
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def transcribe(wav16k: Path, cache: Path, model_name: str | None = None, log=print, language: str = "en") -> list[dict]:
    """Returns [{"w": "word", "s": start_sec, "e": end_sec}, ...] in recording order."""
    if cache.exists():
        log(f"transcript: cached {cache.name}")
        return json.loads(cache.read_text(encoding="utf-8"))
    if importlib.util.find_spec("whisperx") is None:
        from .deps import ROOT, video_python
        py = video_python(required=True)
        args = [str(py), "-m", "viral_scout.video.transcribe", str(wav16k), str(cache), "--language", language]
        if model_name:
            args += ["--model", model_name]
        p = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0 or not cache.exists():
            raise SystemExit(f"transcription failed in {py} (exit {p.returncode})")
        return json.loads(cache.read_text(encoding="utf-8"))
    return _whisperx(wav16k, cache, model_name, log, language)


def _whisperx(wav16k: Path, cache: Path, model_name, log, language) -> list[dict]:
    _quiet()
    import torch  # imported first so ctranslate2 finds torch's CUDA DLLs on Windows
    import whisperx

    cuda = torch.cuda.is_available()
    device = "cuda" if cuda else "cpu"
    cpu_model = "small.en" if language == "en" else "small"
    model_name = model_name or ("large-v3" if cuda else cpu_model)
    compute = "float16" if cuda else "int8"
    log(f"transcript: WhisperX {model_name} on {device}")

    audio = whisperx.load_audio(str(wav16k))
    try:
        model = whisperx.load_model(model_name, device, compute_type=compute, language=language)
    except Exception as e:  # CUDA libs missing for ctranslate2 → CPU
        if not cuda:
            raise
        log(f"transcript: GPU load failed ({e.__class__.__name__}: {e}); falling back to CPU {cpu_model}")
        device, model_name = "cpu", cpu_model
        model = whisperx.load_model(model_name, device, compute_type="int8", language=language)
    result = model.transcribe(audio, batch_size=8 if device == "cuda" else 4, language=language)
    del model
    if device == "cuda":
        torch.cuda.empty_cache()

    align_model, meta = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(result["segments"], align_model, meta, audio, device, return_char_alignments=False)

    words: list[dict] = []
    for seg in aligned["segments"]:
        for w in seg.get("words", []):
            text = w.get("word", "").strip()
            if not text:
                continue
            if "start" not in w:  # numbers/symbols the aligner couldn't place: interpolate later
                words.append({"w": text, "s": None, "e": None})
            else:
                words.append({"w": text, "s": round(w["start"], 3), "e": round(w["end"], 3)})
    fill_missing_times(words)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(words, indent=1), encoding="utf-8")
    log(f"transcript: {len(words)} words")
    return words


def fill_missing_times(words: list[dict]) -> None:
    for i, w in enumerate(words):
        if w["s"] is not None:
            continue
        prev_e = next((words[j]["e"] for j in range(i - 1, -1, -1) if words[j]["e"] is not None), 0.0)
        nxt_s = next((words[j]["s"] for j in range(i + 1, len(words)) if words[j]["s"] is not None), prev_e + 0.4)
        w["s"], w["e"] = prev_e, max(prev_e + 0.05, nxt_s)


def _quiet() -> None:
    """WhisperX's dependencies (pyannote, lightning, torchcodec, HF hub) are chatty; keep the console readable."""
    import logging
    import os
    import warnings

    warnings.filterwarnings("ignore")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    for name in ("whisperx", "pyannote", "lightning", "lightning.pytorch", "pytorch_lightning", "speechbrain",
                 "lightning_fabric", "lightning.fabric", "pytorch_lightning.utilities.migration",
                 "lightning.pytorch.utilities.migration", "torchcodec", "huggingface_hub", "faster_whisper", "urllib3"):
        logging.getLogger(name).setLevel(logging.ERROR)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="viral_scout.video.transcribe")
    ap.add_argument("wav")
    ap.add_argument("cache")
    ap.add_argument("--model")
    ap.add_argument("--language", default="en")
    a = ap.parse_args()
    if importlib.util.find_spec("whisperx") is None:
        print("error: WhisperX is not installed in this Python (run scripts/setup-video.ps1)", file=sys.stderr)
        return 3
    _whisperx(Path(a.wav), Path(a.cache), a.model, lambda m: print(m, flush=True), a.language)
    return 0


if __name__ == "__main__":
    sys.exit(main())
