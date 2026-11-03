# Registers the daily viral-scout tasks in Windows Task Scheduler (current user, wake to run).
#   scripts/schedule.ps1 -Profiles englishSchool,northForge,nfSolarPanels -Start 07:00 -GapMinutes 30 -Analyze -Publish
# Profiles run one after another, GapMinutes apart (YouTube rate-limits bursts). -Publish adds a final task that
# exports and deploys the dashboard. Remove with: scripts/schedule.ps1 -Remove
param(
  [string[]]$Profiles = @(),
  [string]$Start = "07:00",
  [int]$GapMinutes = 30,
  [switch]$Analyze,
  [switch]$Publish,
  [switch]$Remove
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell).Source }

$existing = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "viral-scout *" }
if ($Remove) { $existing | Unregister-ScheduledTask -Confirm:$false; "removed $($existing.Count) tasks"; return }
if (-not $Profiles) { throw "Pass -Profiles name1,name2" }
# `pwsh -File` passes "a,b,c" as one string: split it.
$Profiles = @($Profiles | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$at = [datetime]::ParseExact($Start, "HH:mm", $null)
foreach ($p in $Profiles) {
  $args = "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\run-daily.ps1`" -Profile $p" + $(if ($Analyze) { " -Analyze" } else { "" })
  $action = New-ScheduledTaskAction -Execute $pwsh -Argument $args -WorkingDirectory $repo
  Register-ScheduledTask -TaskName "viral-scout $p" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At $at) `
    -Settings $settings -Force | Out-Null
  "viral-scout $p  daily $($at.ToString('HH:mm'))"
  $at = $at.AddMinutes($GapMinutes)
}
if ($Publish) {
  $action = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\publish.ps1`"" -WorkingDirectory $repo
  Register-ScheduledTask -TaskName "viral-scout publish" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At $at) `
    -Settings $settings -Force | Out-Null
  "viral-scout publish  daily $($at.ToString('HH:mm'))"
}
"Wake timers must be allowed in the power plan (Power Options → Sleep → Allow wake timers)."
