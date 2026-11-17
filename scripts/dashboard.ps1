# Keep the local dashboard (web/, http://localhost:3210) running on this PC: starts at logon, hidden, restarts if it stops.
#   dashboard.ps1 install     register the "viral-scout-dashboard" task (at logon, current user) and start it now
#   dashboard.ps1 uninstall   stop it and remove the task
#   dashboard.ps1 status      task state, whether port 3210 answers, log tail
#   dashboard.ps1 restart     stop and start again (after a git pull or npm install)
#   dashboard.ps1 serve       what the task runs: `npm run dev` bound to 127.0.0.1, log in data/logs/dashboard.log
# It runs `next dev`, not a production build: the business pages are pre-rendered in a build, so `next start` would
# show the data as it was at build time, while dev re-reads web/data/*.json after every run.
# Task name has no space after "viral-scout", so the Schedule page (tasks.ps1, "viral-scout *") doesn't list it.
param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet("install", "uninstall", "status", "restart", "serve")]
  [string]$Command
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$web = Join-Path $repo "web"
$task = "viral-scout-dashboard"
$port = 3210
$logDir = Join-Path $repo "data\logs"
$log = Join-Path $logDir "dashboard.log"

function Get-Listener { Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 }

function Stop-Dashboard {
  $t = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
  if ($t -and $t.State -eq "Running") { Stop-ScheduledTask -TaskName $task }
  $l = Get-Listener   # next dev runs in a child node process the task stop doesn't always reach
  if ($l) { Stop-Process -Id $l.OwningProcess -Force -ErrorAction SilentlyContinue }
}

switch ($Command) {
  "serve" {
    New-Item -ItemType Directory -Force $logDir | Out-Null
    if (Get-Listener) { "port $port already in use; not starting a second dashboard" | Out-File $log -Append; exit 0 }
    if (-not (Test-Path (Join-Path $web "node_modules"))) { & cmd /c "cd /d `"$web`" && npm install >> `"$log`" 2>&1" }
    "=== $(Get-Date -Format s) starting dashboard ===" | Out-File $log -Encoding utf8   # one run per log, no growth
    & cmd /c "cd /d `"$web`" && npm run dev -- -H 127.0.0.1 >> `"$log`" 2>&1"
    exit $LASTEXITCODE
  }
  "install" {
    $ps = (Get-Command powershell.exe).Source   # Windows PowerShell: the Store pwsh alias doesn't start from Task Scheduler
    $action = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $repo `
      -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`" serve"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
      -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
      -Description "viral-scout local dashboard on http://localhost:$port (scripts/dashboard.ps1)" -Force | Out-Null
    Start-ScheduledTask -TaskName $task
    "installed '$task'; starting on http://localhost:$port (log: $log)"
  }
  "uninstall" {
    Stop-Dashboard
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
    "removed '$task'"
  }
  "restart" {
    Stop-Dashboard
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $task
    "restarted; http://localhost:$port"
  }
  "status" {
    $t = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
    "task:   $(if ($t) { $t.State } else { 'not installed' })"
    "port:   $(if (Get-Listener) { "listening on $port" } else { 'not listening' })"
    if (Test-Path $log) { "log:    $log"; Get-Content $log -Tail 8 }
  }
}
