# Daily idea run for one profile: runs the /studio-ideas Claude Code skill headless (your Claude subscription, no API key).
# The ideas go through the ideas API the profile's ideas.api names (today the solar site), so it must be reachable.
# By hand only. The schedule runs ideas through the studio job runner instead (python -m viral_scout jobs <profile> run ideas,
# installed by scripts/schedule-studio.ps1), so every unattended Claude job shares one lock and one log folder.
# Usage:
#   pwsh scripts/ideas-daily.ps1 -Profile myhomes [-Count 3] [-Topic "lights"] [-PostsOnly]
# -Count    default: the profile's ideas.daily.count
# -PostsOnly only the content packs for ✅ / 📝 ideas (/studio-ideas <profile> posts); exits early when none are queued.
# Logs: data/logs/ideas-<profile>-<date>.log (git-ignored).
param([Parameter(Mandatory = $true)][string]$Profile, [int]$Count = 0, [string]$Topic = "", [switch]$PostsOnly)
$ErrorActionPreference = "Stop"

$repo = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("ideas-{0}-{1}.log" -f $Profile, (Get-Date -Format yyyy-MM-dd))
function Log([string]$m) { "{0} {1}" -f (Get-Date -Format HH:mm:ss), $m | Tee-Object -FilePath $log -Append }
$env:PYTHONIOENCODING = "utf-8"

Push-Location $repo
try {
  # The resolved ideas block (fails clearly when the profile has none).
  $info = & python -m viral_scout ideas $Profile info 2>&1
  if ($LASTEXITCODE -ne 0) { Log "ERROR: $info"; exit 1 }
  $info = $info | Out-String | ConvertFrom-Json
  if ($Count -le 0) { $Count = [int]$info.daily.count }
  if ($Count -le 0) { $Count = 5 }

  $prompt = if ($PostsOnly) { "/studio-ideas $Profile posts" } else { "/studio-ideas $Profile $Count $Topic".Trim() }
  Log "=== $prompt (project $($info.project))"

  # Fail early if the ideas API can't be reached or the secret is missing.
  $check = & python -m viral_scout ideas $Profile pull 2>&1
  if ($LASTEXITCODE -ne 0) { Log "ERROR: ideas API not reachable: $check"; exit 1 }
  if ($PostsOnly) {
    if (-not $info.packs.enabled) { Log "=== packs are off for $Profile"; exit 0 }
    $queued = @(($check | Out-String | ConvertFrom-Json).ideas | Where-Object { $_.status -eq "approved" -or $_.stage -eq "pack" })
    if ($queued.Count -eq 0) { Log "=== no packs queued"; exit 0 }
    Log ("packs queued: #" + (($queued | ForEach-Object { $_.id }) -join ", #"))
  }

  $claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
  if (-not $claude) { Log "ERROR: claude CLI not found on PATH"; exit 1 }

  # Narrow allowlist: files in this repo and the vault, web lookups for facts, and only this profile's ideas CLI
  # in the shell. Extra folders the instructions need (e.g. a voice skill) come from ideas.daily.add_dirs.
  $dirs = @("--add-dir", $env:OBSIDIAN_VAULT)
  foreach ($d in @($info.daily.add_dirs)) { if ($d) { $dirs += @("--add-dir", $d) } }
  & $claude -p $prompt `
    --permission-mode acceptEdits `
    @dirs `
    --allowedTools "Read" "Glob" "Grep" "Edit" "Write" "WebSearch" "WebFetch" "Bash(python -m viral_scout ideas ${Profile}:*)" "Bash(PYTHONIOENCODING=utf-8 python -m viral_scout ideas ${Profile}:*)" 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
  $code = $LASTEXITCODE
} finally { Pop-Location }
Log "=== done (exit $code)"
exit $code
