# One studio job for one profile. Task Scheduler starts this (install: scripts/schedule-studio.ps1 -Profile <p>).
#   scripts/studio.ps1 -Profile myhomes -Job film      (ideas | script | notes | film | blog | posts | post | autopost)
# The work (lock, .done markers, tries, the claude -p call, logs in data/logs/studio/) is in
# `python -m viral_scout jobs <profile> run <job>`. This wrapper only fixes the environment a scheduled task lacks.
param([Parameter(Mandatory)][string]$Profile, [Parameter(Mandatory)][ValidateSet("ideas", "script", "notes", "film", "blog", "posts", "post", "autopost")][string]$Job)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $repo "data\logs\studio"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("{0}-{1}-{2}.log" -f $Profile, $Job, (Get-Date -Format yyyy-MM-dd))
function Log([string]$m) { "{0} {1}" -f (Get-Date -Format HH:mm:ss), $m | Out-File -FilePath $log -Append -Encoding utf8 }

$env:PYTHONIOENCODING = "utf-8"
# A task started at logon may not see user-scope variables set later: read them from the registry.
if (-not $env:OBSIDIAN_VAULT) { $env:OBSIDIAN_VAULT = [Environment]::GetEnvironmentVariable("OBSIDIAN_VAULT", "User") }
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Log "ERROR: python not on PATH"; exit 1 }

Push-Location $repo
try {
  $out = & $python -m viral_scout jobs $Profile run $Job 2>&1 | ForEach-Object { "$_" }
  $code = $LASTEXITCODE
  # Quiet exits (job off, already done, busy, nothing waiting) every 15 min would flood the log: keep one line.
  $quiet = $code -eq 0 -and ($out -join " ") -match '^(nothing waiting|.* already done|busy: |.* is off for |.* tries used|before \d+:00|already sent|nothing due)'
  if ($out -and -not $quiet) { Log ("run {0}: {1}" -f $Job, (($out | Select-Object -Last 3) -join " | ")) }
} catch { Log "ERROR: $_"; $code = 1 } finally { Pop-Location }
exit $code
