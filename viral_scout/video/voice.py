"""Cloned voice of the profile's owner with Chatterbox (MIT, runs locally; GPU if CUDA works).

Main CLI:  python -m viral_scout video <profile> voice <ref.wav|profile> <out.wav> <text | script.md | file.txt>
Runs in the voice env (`.venv-voice`) as
  <voice python> -m viral_scout.video.voice <ref.wav> <out.wav> <text file> [--cfg 0.5 0.3] [--exaggeration 0.5] [--seed 1]

Reference: 8–12 s of clean speech by the consenting owner. The text is spoken sentence by sentence (a short pause
between) so long scripts stay stable. Several --cfg values give one file each (out-cfg0.3.wav ...); lower cfg carries
less accent over from the reference and slows the pace.
Output is an AI voice: label it on every platform. Videos only, never phone calls or voicemails (FCC 24-17).
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def text_of(arg: str, section: str | None = None, name: str | None = None) -> str:
    """Literal text, a .txt file, or a script .md (its spoken lines)."""
    p = Path(arg)
    if len(arg) < 260 and p.suffix and p.exists():
        if p.suffix.lower() == ".md":
            from .script import load_script
            return " ".join(l["text"] for l in load_script(p, section, name)["lines"])
        return p.read_text(encoding="utf-8").strip()
    return arg.strip()


def clone(v: dict, reference: str, out: str, text: str, cfg=None, exaggeration=None, seed=None, pause=None,
          section=None) -> int:
    from .deps import ROOT, voice_python
    ref = v["voice"].get("reference") if reference in ("profile", "-", "") else Path(reference)
    if not ref or not Path(ref).exists():
        raise SystemExit(f"error: voice reference not found: {ref or 'video.voice.reference is not set'}")
    spoken = text_of(text, section, v.get("owner") or None)
    if not spoken:
        raise SystemExit("error: no text to speak")
    py = voice_python(required=True)
    vc = v["voice"]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(spoken)
    args = [str(py), "-m", "viral_scout.video.voice", str(ref), str(Path(out).resolve()), f.name,
            "--cfg", *[str(c) for c in (cfg or [vc.get("cfg", 0.5)])],
            "--exaggeration", str(exaggeration if exaggeration is not None else vc.get("exaggeration", 0.5)),
            "--seed", str(seed if seed is not None else vc.get("seed", 1)),
            "--pause", str(pause if pause is not None else vc.get("pause", 0.25))]
    try:
        rc = subprocess.run(args, cwd=ROOT).returncode
    finally:
        Path(f.name).unlink(missing_ok=True)
    if rc == 0:
        print(f"AI voice: turn the platform AI label ON; first caption line: \"{v['ai_label']}\"")
    return rc


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    p = argparse.ArgumentParser(prog="viral_scout.video.voice")
    p.add_argument("reference")
    p.add_argument("out")
    p.add_argument("text", help="text, or a file with the text")
    p.add_argument("--cfg", type=float, nargs="+", default=[0.5])
    p.add_argument("--exaggeration", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--pause", type=float, default=0.25, help="seconds of silence between sentences")
    a = p.parse_args()
    try:
        import torch
        import torchaudio as ta
        from chatterbox.tts import ChatterboxTTS
    except ImportError as e:
        print(f"error: Chatterbox is not installed in this Python ({e}); run scripts/setup-video.ps1 -Voice", file=sys.stderr)
        return 3

    text = text_of(a.text)
    model = ChatterboxTTS.from_pretrained(device="cuda" if torch.cuda.is_available() else "cpu")
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    gap = torch.zeros(1, int(model.sr * a.pause))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for cfg in a.cfg:
        torch.manual_seed(a.seed)
        parts = []
        for s in sentences:
            parts += [model.generate(s, audio_prompt_path=a.reference, cfg_weight=cfg, exaggeration=a.exaggeration).cpu(), gap]
        target = out if len(a.cfg) == 1 else out.with_name(f"{out.stem}-cfg{cfg}{out.suffix}")
        ta.save(str(target), torch.cat(parts[:-1], dim=1), model.sr)
        print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
