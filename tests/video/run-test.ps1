# End-to-end test with the real tools (WhisperX, Playwright cards, FFmpeg): a SAPI voice reads fixture script 1
# with two flubbed takes → cut → cards → master. Needs the video setup (scripts/setup-video.ps1 -Node) or
# VIRAL_SCOUT_VIDEO_PY / VIRAL_SCOUT_VIDEO_NODE_MODULES pointing at existing installs.
param([string]$Out = "$PSScriptRoot\_out")
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
& "$PSScriptRoot\make-test-voice.ps1" -Out "$PSScriptRoot\_test-voice.wav"
$env:PYTHONIOENCODING = "utf-8"
Push-Location $root
try {
  python -m viral_scout video tests/fixtures/video/profile.yaml make "$PSScriptRoot\_test-voice.wav" tests/fixtures/video/script.md --section 1 --slug test-script-1 --out $Out
  exit $LASTEXITCODE
} finally { Pop-Location }
