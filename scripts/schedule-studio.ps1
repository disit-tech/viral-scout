# Registers a profile's studio jobs in Windows Task Scheduler (current user). The OWNER runs this once:
# Claude may not register scheduled tasks (it counts as unauthorized persistence), so a job never installs itself.
#   pwsh -NoProfile -File D:/repo/viral-scout/scripts/schedule-studio.ps1 -Profile myhomes [-Paused]
#   pwsh -NoProfile -File D:/repo/viral-scout/scripts/schedule-studio.ps1 -Profile myhomes -Remove
# What gets registered comes from the profile (jobs: and publish.morning_pack): `python -m viral_scout jobs <p> install-plan`.
# Tasks are named "viral-scout <profile>.<job>", so the dashboard's Schedule page lists them.
# Gotchas from the solar pipeline, built in:
#   - full pwsh.exe path (a task has no PATH lookup for the shell), -NoProfile -NonInteractive -WindowStyle Hidden
#   - runs on battery and keeps running when the laptop unplugs
#   - StartWhenAvailable: a run missed while the PC was off starts as soon as it is back
#   - daily jobs repeat hourly until evening (daily triggers miss days when the PC sleeps; .done markers stop the extra runs)
#   - ExecutionTimeLimit (default 3 h, a film render is long) and MultipleInstances IgnoreNew (no overlapping runs)
#   - wake timers must be allowed in the power plan for WakeToRun; a PC that is shut down does not run anything
# From a Claude Code "!" prompt use forward slashes in the path (bash strips backslashes).
param([Parameter(Mandatory)][string]$Profile, [switch]$Paused, [switch]$Remove)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
if ($Profile -notmatch '^[\w.-]+$') { throw "bad profile name: $Profile" }

if ($Remove) {
  $ours = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "viral-scout $Profile.*" })
  $ours | Unregister-ScheduledTask -Confirm:$false
  "removed $($ours.Count) studio task(s) of $Profile"
  return
}

$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell).Source }
$env:PYTHONIOENCODING = "utf-8"
Push-Location $repo
try { $json = & python -m viral_scout jobs $Profile install-plan --json } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "install-plan failed: $json" }
$plan = $json | ConvertFrom-Json
if (-not $plan.tasks) { "no studio jobs are on for $Profile (jobs.<job>.enabled / publish.morning_pack.enabled)"; return }

function New-StudioTrigger($t) {
  if ($t.type -eq "every") {
    return New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes $t.minutes)
  }
  $at = [datetime]::ParseExact($t.at, "HH:mm", $null)
  $trig = if ($t.type -eq "weekly") { New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t.days -At $at } else { New-ScheduledTaskTrigger -Daily -At $at }
  if ($t.repeat_minutes -gt 0 -and $t.repeat_hours -gt 0) {
    # Daily/weekly triggers take a repetition pattern copied from a -Once trigger.
    $rep = New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Minutes $t.repeat_minutes) -RepetitionDuration (New-TimeSpan -Hours $t.repeat_hours)
    $trig.Repetition = $rep.Repetition
  }
  $trig
}

foreach ($t in $plan.tasks) {
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours $t.time_limit_hours) -MultipleInstances IgnoreNew
  $action = New-ScheduledTaskAction -Execute $pwsh -WorkingDirectory $repo `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$repo\scripts\studio.ps1`" $($t.args)"
  Register-ScheduledTask -TaskName $t.name -Action $action -Trigger (New-StudioTrigger $t.trigger) -Settings $settings `
    -Description "viral-scout studio: $($t.what)" -Force | Out-Null
  if ($Paused) { Disable-ScheduledTask -TaskName $t.name | Out-Null }
  $next = (Get-ScheduledTaskInfo -TaskName $t.name).NextRunTime
  "{0,-34} {1}  (next: {2}){3}" -f $t.name, $t.what, $next, $(if ($Paused) { " paused" } else { "" })
}
"The PC must be on (or asleep with wake timers allowed) and you logged in. Logs: data/logs/studio/. Manage them on the dashboard's Schedule page."
