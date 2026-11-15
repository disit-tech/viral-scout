"""Optional heavy tools: where they live, whether they are installed, and a clear error when they are not.

  ffmpeg / ffprobe      system PATH (with libass for burned-in captions)
  WhisperX + torch      .venv-video (Python 3.11)            or $VIRAL_SCOUT_VIDEO_PY
  Chatterbox            .venv-voice (Python 3.11)            or $VIRAL_SCOUT_VOICE_PY
  Playwright, HyperFrames   viral_scout/video/node/node_modules   or $VIRAL_SCOUT_VIDEO_NODE_MODULES
  Pillow                the Python running the CLI (stills)
The two Python envs are separate because Chatterbox pins torch 2.6 / numpy 1.26 and WhisperX needs torch 2.8 / numpy 2.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ..config import ROOT

NODE_DIR = Path(__file__).resolve().parent / "node"
SETUP = "scripts/setup-video.ps1"
MISSING_EXIT = 3


class MissingDependency(SystemExit):
    """Raised (as a clean exit with code 3 and a message) when an optional tool isn't installed."""

    def __init__(self, what: str, how: str):
        super().__init__(f"error: {what} is not installed. {how}")
        self.code = MISSING_EXIT
        self.message = f"error: {what} is not installed. {how}"

    def __str__(self):
        return self.message


HOW = {
    "ffmpeg": "Install FFmpeg with libass and put it on PATH (Windows: choco install ffmpeg).",
    "ffprobe": "It comes with FFmpeg (choco install ffmpeg).",
    "node": "Install Node.js 22+ (https://nodejs.org).",
}


def require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise MissingDependency(tool, HOW.get(tool, f"Put {tool} on PATH."))
    return path


def _venv_python(env_var: str, folder: str) -> Path | None:
    if os.environ.get(env_var):
        p = Path(os.environ[env_var])
        return p if p.exists() else None
    for rel in ("Scripts/python.exe", "bin/python"):
        p = ROOT / folder / rel
        if p.exists():
            return p
    return None


def video_python(required: bool = False) -> Path | None:
    p = _venv_python("VIRAL_SCOUT_VIDEO_PY", ".venv-video")
    if not p and required:
        raise MissingDependency("WhisperX (the .venv-video env)",
                                f"Run `pwsh {SETUP}` once, or set VIRAL_SCOUT_VIDEO_PY to a Python that has whisperx.")
    return p


def voice_python(required: bool = False) -> Path | None:
    p = _venv_python("VIRAL_SCOUT_VOICE_PY", ".venv-voice")
    if not p and required:
        raise MissingDependency("Chatterbox (the .venv-voice env)",
                                f"Run `pwsh {SETUP} -Voice` once, or set VIRAL_SCOUT_VOICE_PY to a Python that has chatterbox-tts.")
    return p


def node_modules() -> Path:
    env = os.environ.get("VIRAL_SCOUT_VIDEO_NODE_MODULES")
    return Path(env) if env else NODE_DIR / "node_modules"


def node_package(name: str, required: bool = False) -> Path | None:
    p = node_modules() / name
    if p.exists():
        return p
    if required:
        require("node")
        raise MissingDependency(f"the Node package {name}",
                                f"Run `pwsh {SETUP} -Node` (npm install in viral_scout/video/node), "
                                "or set VIRAL_SCOUT_VIDEO_NODE_MODULES to a node_modules that has it.")
    return None


def hyperframes_bin(required: bool = False) -> Path | None:
    bin_dir = node_modules() / ".bin"
    for name in ("hyperframes.cmd", "hyperframes"):
        if (bin_dir / name).exists():
            return bin_dir / name
    if required:
        node_package("hyperframes", required=True)
        raise MissingDependency("the hyperframes CLI", f"Run `pwsh {SETUP} -Node` again.")
    return None


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _out(args, timeout=30) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return (p.stdout + p.stderr).strip()
    except Exception as e:  # noqa: BLE001 (a report, never a crash)
        return f"ERROR {e.__class__.__name__}: {e}"


def report(v: dict | None = None, deep: bool = False) -> list[tuple[str, bool, str]]:
    """[(item, ok, detail)]. deep=True imports torch in the video env to report CUDA (takes ~10 s)."""
    rows = []
    for tool in ("ffmpeg", "ffprobe"):
        p = shutil.which(tool)
        rows.append((tool, bool(p), p or HOW[tool]))
    if shutil.which("ffmpeg"):
        libass = " subtitles " in _out(["ffmpeg", "-hide_banner", "-filters"])
        rows.append(("ffmpeg libass (burned-in captions)", libass, "ok" if libass else "this FFmpeg has no subtitles filter"))
    node = shutil.which("node")
    ver = _out(["node", "--version"]) if node else ""
    m = re.match(r"v(\d+)", ver)
    rows.append(("node (22+ for HyperFrames)", bool(m and int(m.group(1)) >= 22), ver or HOW["node"]))
    for pkg in ("playwright", "hyperframes"):
        p = node_package(pkg)
        rows.append((f"node package {pkg}", bool(p), str(p) if p else f"pwsh {SETUP} -Node"))
    py = video_python()
    if py:
        code = ("import importlib.util as u; print('whisperx', bool(u.find_spec('whisperx')))"
                if not deep else
                "import torch, whisperx; print('whisperx ok, torch', torch.__version__, 'CUDA', torch.cuda.is_available())")
        out = _out([str(py), "-c", code], timeout=180)
        rows.append(("WhisperX (transcripts, cut)", "True" in out or "ok" in out, f"{py}: {out[-200:]}"))
    else:
        rows.append(("WhisperX (transcripts, cut)", has_module("whisperx"),
                     "in this Python" if has_module("whisperx") else f"no .venv-video: pwsh {SETUP}"))
    vpy = voice_python()
    if vpy:
        out = _out([str(vpy), "-c", "import importlib.util as u; print(bool(u.find_spec('chatterbox')))"])
        rows.append(("Chatterbox (voice clone)", out.endswith("True"), str(vpy)))
    else:
        rows.append(("Chatterbox (voice clone)", has_module("chatterbox"),
                     "in this Python" if has_module("chatterbox") else f"no .venv-voice: pwsh {SETUP} -Voice"))
    rows.append(("Pillow (stills)", has_module("PIL"), sys.executable if has_module("PIL") else "pip install pillow"))
    if v:
        ref = v["voice"].get("reference")
        rows.append(("profile: voice reference", bool(ref and ref.exists()), str(ref or "video.voice.reference not set")))
        for k in ("footage_dir", "script_dir", "music_dir", "logo", "card_template"):
            p = v.get(k)
            if p:
                rows.append((f"profile: {k}", p.exists(), str(p)))
        for k in ("still_bold", "still_regular"):
            p = v["fonts"].get(k)
            if p:
                rows.append((f"profile: fonts.{k}", p.exists(), str(p)))
        rows.append(("profile: output_dir", True, str(v["output_dir"])))
        rows.append(("profile: modes", True, ", ".join(v["modes"])))
    return rows
