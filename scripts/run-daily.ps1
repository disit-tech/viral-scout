# Daily viral-scout run for one profile. For Task Scheduler (turn on "wake the computer to run").
#   -Analyze  afterwards runs the /viral-scout skill headless (Claude Code CLI, your subscription) to write
#             <date>-viral-ideas.md: format breakdowns + ideas adapted to the profile's business.
#   -AdsDay   weekday for the weekly ads scout run (default Monday; "Never" to skip). Weekly, because paid ad
#             sources (Apify) bill per result and long-running ads change slowly. Needs ad keys; skips cleanly without.
param([Parameter(Mandatory = $true)][string]$Profile, [switch]$Analyze, [string]$AdsDay = "Monday")
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("{0}-{1}.log" -f $Profile, (Get-Date -Format yyyy-MM-dd))
function Log([string]$m) { "{0} {1}" -f (Get-Date -Format HH:mm:ss), $m | Tee-Object -FilePath $log -Append }
$env:PYTHONIOENCODING = "utf-8"

Push-Location $repo
try {
  Log "=== run $Profile"
  & python -m viral_scout run $Profile --quiet 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
  $code = $LASTEXITCODE
  if ($AdsDay -ne "Never" -and (Get-Date).DayOfWeek.ToString() -eq $AdsDay) {
    Log "=== ads $Profile (weekly)"
    & python -m viral_scout ads $Profile 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
  }
  if ($code -eq 0 -and $Analyze) {
    $claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
    if (-not $claude) { Log "analyze skipped: claude CLI not on PATH" }
    else {
      Log "=== analyze $Profile"
      $add = @()
      if ($env:OBSIDIAN_VAULT) { $add = @("--add-dir", $env:OBSIDIAN_VAULT) }
      # Narrow allowlist: read/write notes, and only the viral_scout CLI in the shell.
      & $claude -p "/viral-scout $Profile analyze" --permission-mode acceptEdits @add `
        --allowedTools "Read" "Glob" "Grep" "Edit" "Write" "Bash(python -m viral_scout:*)" 2>&1 |
        ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
      $code = $LASTEXITCODE
    }
  }
} finally { Pop-Location }
Log "=== done (exit $code)"
exit $code
