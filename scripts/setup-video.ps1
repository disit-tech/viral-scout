# One-time setup for video generation (python -m viral_scout video ...). Research-only users skip this.
#
#   pwsh scripts/setup-video.ps1            WhisperX env (.venv-video, Python 3.11, CUDA torch): cut, make, film words
#   pwsh scripts/setup-video.ps1 -Node      Playwright + HyperFrames in viral_scout/video/node: cards, render, film
#   pwsh scripts/setup-video.ps1 -Voice     Chatterbox env (.venv-voice, Python 3.11, CUDA torch): voice
#   pwsh scripts/setup-video.ps1 -All       all three
#   pwsh scripts/setup-video.ps1 -Check     print the plan and what is installed; installs nothing
#   add -Cpu to skip the CUDA builds of torch (slow, but works without an NVIDIA GPU)
#
# Needs: FFmpeg with libass on PATH (choco install ffmpeg), Node.js 22+ for -Node, and uv or the `py` launcher.
# Downloads several GB (torch, the Whisper model on first use, Chromium). Ported from solar-site tools/video/setup.ps1.
param([switch]$Node, [switch]$Voice, [switch]$All, [switch]$Check, [switch]$Cpu)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$whisper = $All -or (-not $Node -and -not $Voice)
$Node = $Node -or $All
$Voice = $Voice -or $All

function Get-Uv {
  $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
  if ($uv) { return $uv }
  if ($Check) { return "uv (would be installed with: py -3.12 -m pip install --user uv)" }
  py -3.12 -m pip install --user -q uv
  return Join-Path (py -3.12 -c "import site;print(site.getuserbase())") "Python312\Scripts\uv.exe"
}

function Step($what, [scriptblock]$do) {
  if ($Check) { Write-Output "would: $what" } else { Write-Output "== $what"; & $do }
}

Push-Location $root
try {
  $uv = Get-Uv
  if ($whisper) {
    Step "create .venv-video (Python 3.11) and install requirements-video.txt (WhisperX)" {
      & $uv venv --python 3.11 .venv-video
      & $uv pip install --python .venv-video -r requirements-video.txt
    }
    if (-not $Cpu) {
      Step "put the CUDA 12.8 build of torch 2.8 into .venv-video (falls back to CPU at run time without CUDA)" {
        & $uv pip install --python .venv-video --reinstall-package torch --reinstall-package torchaudio --reinstall-package torchvision `
          "torch==2.8.0+cu128" "torchaudio==2.8.0+cu128" "torchvision==0.23.0+cu128" `
          --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match
      }
    }
    Step "report torch and CUDA in .venv-video" {
      .\.venv-video\Scripts\python -c "import torch; print('torch', torch.__version__, 'CUDA', torch.cuda.is_available())"
    }
  }
  if ($Voice) {
    Step "create .venv-voice (Python 3.11) and install requirements-voice.txt (Chatterbox)" {
      & $uv venv --python 3.11 .venv-voice
      & $uv pip install --python .venv-voice -r requirements-voice.txt
    }
    if (-not $Cpu) {
      Step "put the CUDA 12.4 build of torch 2.6 into .venv-voice (the version Chatterbox pins)" {
        & $uv pip install --python .venv-voice --reinstall-package torch --reinstall-package torchaudio `
          "torch==2.6.0+cu124" "torchaudio==2.6.0+cu124" `
          --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match
      }
    }
  }
  if ($Node) {
    Step "npm install in viral_scout/video/node (Playwright, HyperFrames) and download Chromium for the cards" {
      Push-Location viral_scout\video\node
      try { npm install; npx playwright install chromium } finally { Pop-Location }
    }
  }
  $ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
  if (-not $ff) { Write-Warning "FFmpeg is not on PATH: choco install ffmpeg" }
  elseif (-not (ffmpeg -hide_banner -filters 2>$null | Select-String " subtitles ")) { Write-Warning "FFmpeg without libass: captions won't burn in" }
  $env:PYTHONIOENCODING = "utf-8"
  python -m viral_scout video doctor
} finally { Pop-Location }
