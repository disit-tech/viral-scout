# Daily viral-scout run for one profile. For Task Scheduler (turn on "wake the computer to run").
param([Parameter(Mandatory = $true)][string]$Profile)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("{0}-{1}.log" -f $Profile, (Get-Date -Format yyyy-MM-dd))
$env:PYTHONIOENCODING = "utf-8"
Push-Location $repo
try {
  "=== {0} run {1}" -f (Get-Date -Format "HH:mm:ss"), $Profile | Tee-Object -FilePath $log -Append
  & python -m viral_scout run $Profile 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
  $code = $LASTEXITCODE
} finally { Pop-Location }
"=== {0} done (exit {1})" -f (Get-Date -Format "HH:mm:ss"), $code | Tee-Object -FilePath $log -Append
exit $code
