# Manage the viral-scout tasks in Windows Task Scheduler, one at a time. Backend of the dashboard's Schedule page;
# scripts/schedule.ps1 is still the one-shot "register them all" command. Only touches tasks named "viral-scout *".
#   tasks.ps1 list                                     JSON: every viral-scout task, its trigger, state, last result, log tail
#   tasks.ps1 enable|disable|run|stop|remove -Name "viral-scout myhomes"
#   tasks.ps1 set -Name "viral-scout myhomes" -Day Monday -Time 07:30 [-Analyze 1|0]
#   tasks.ps1 add -Profile myhomes -Day Monday -Time 07:30 [-Analyze 1]     (-Profile publish = the export+deploy task)
# Studio jobs ("viral-scout <profile>.<job>", scripts/studio.ps1) are listed too and can be paused, run, stopped or removed;
# their schedule comes from the profile, so "set" refuses them: the dashboard edits jobs: in the profile, then runs
#   tasks.ps1 studio-sync -Profile myhomes      registers the profile's studio jobs (new ones paused, paused ones stay paused,
#                                               on ones stay on) and removes the ones the profile no longer has
# Older idea and content tasks outside viral-scout (an ideas-daily.ps1 or a site's scripts\jobs\run.ps1, e.g. "Homeworks Ideas") are listed
# as kind "legacy" and can be paused, run, stopped or removed, not rescheduled.
param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet("list", "enable", "disable", "run", "stop", "set", "add", "remove", "studio-sync")]
  [string]$Command,
  [string]$Name,
  [string]$Profile,
  [ValidateSet("", "Daily", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]
  [string]$Day = "",
  [string]$Time = "",
  [ValidateSet("", "0", "1")]
  [string]$Analyze = ""
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell).Source }
$days = "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"   # DaysOfWeek bit order

function Fail([string]$m) { [Console]::Error.WriteLine($m); exit 2 }
function Iso($d) { if ($d -and $d.Year -gt 1999) { $d.ToString("o") } else { $null } }

function Test-Legacy($t) {   # an idea/content task registered by another repo: ideas-daily.ps1 or a site's scripts\jobs\run.ps1
  $t.TaskName -notlike "viral-scout *" -and
    (($t.Actions | ForEach-Object { "$($_.Arguments)" }) -join " ") -match 'ideas-daily\.ps1|[\\/]scripts[\\/]jobs[\\/]run\.ps1'
}

function Get-Ours([string]$n) {
  if ($n -notmatch '^[\w .-]{1,80}$') { Fail "bad task name: $n" }
  $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  if (-not $t) { Fail "no task named '$n'" }
  if ($n -notmatch '^viral-scout [\w.-]+$' -and -not (Test-Legacy $t)) { Fail "not a viral-scout or idea task: $n" }
  $t
}

function New-StudioTrigger($t) {   # same triggers as scripts/schedule-studio.ps1
  if ($t.type -eq "every") {
    return New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes $t.minutes)
  }
  $at = [datetime]::ParseExact($t.at, "HH:mm", $null)
  $trig = if ($t.type -eq "weekly") { New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t.days -At $at } else { New-ScheduledTaskTrigger -Daily -At $at }
  if ($t.repeat_minutes -gt 0 -and $t.repeat_hours -gt 0) {
    $rep = New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Minutes $t.repeat_minutes) -RepetitionDuration (New-TimeSpan -Hours $t.repeat_hours)
    $trig.Repetition = $rep.Repetition
  }
  $trig
}

function New-Trigger([string]$d, [string]$hhmm) {
  if ($hhmm -notmatch '^([01]\d|2[0-3]):[0-5]\d$') { Fail "time must be HH:mm, got '$hhmm'" }
  $at = [datetime]::ParseExact($hhmm, "HH:mm", $null)
  if ($d -eq "Daily") { New-ScheduledTaskTrigger -Daily -At $at } else { New-ScheduledTaskTrigger -Weekly -DaysOfWeek $d -At $at }
}

function New-Action([string]$p, [bool]$analyze) {
  if ($p -eq "publish") {
    $a = "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\publish.ps1`""
  } else {
    $a = "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\run-daily.ps1`" -Profile $p" + $(if ($analyze) { " -Analyze" } else { "" })
  }
  New-ScheduledTaskAction -Execute $pwsh -Argument $a -WorkingDirectory $repo
}

function Describe($t) {
  $info = $t | Get-ScheduledTaskInfo
  $args = ($t.Actions | Select-Object -First 1).Arguments
  $profile = if ($args -match '-Profile\s+([\w.-]+)') { $Matches[1] } else { $null }
  $job = if ($args -match '-Job\s+(\w+)') { $Matches[1] } else { $null }
  $kind = if (Test-Legacy $t) { "legacy" } elseif ($args -match 'studio\.ps1') { "studio" } elseif ($args -match 'publish\.ps1') { "publish" } elseif ($profile) { "profile" } else { "other" }
  $trig = $t.Triggers | Select-Object -First 1
  $day = $null; $time = $null
  if ($trig) {
    $cls = $trig.CimClass.CimClassName
    if ($trig.StartBoundary) { $time = ([datetime]$trig.StartBoundary).ToString("HH:mm") }
    if ($cls -eq "MSFT_TaskDailyTrigger") { $day = "Daily" }
    elseif ($cls -eq "MSFT_TaskWeeklyTrigger") {
      $day = (0..6 | Where-Object { $trig.DaysOfWeek -band (1 -shl $_) } | ForEach-Object { $days[$_] }) -join ","
    } else { $day = $cls -replace '^MSFT_Task|Trigger$', '' }
  }
  $logTail = @(); $logFile = $null
  $script = if ($kind -eq "legacy" -and $args -match '-File\s+"?([^"]+?\.ps1)') { $Matches[1] } else { $null }
  $repeat = if ($trig -and $trig.Repetition -and $trig.Repetition.Interval) { "$($trig.Repetition.Interval)" } else { $null }
  if ($kind -eq "studio") {
    $f = Get-ChildItem (Join-Path $repo "data\logs\studio") -Filter "$profile-$job-*.log" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) { $logFile = "studio/$($f.Name)"; $logTail = [string[]]@(Get-Content $f.FullName -Tail 40 -Encoding utf8 | ForEach-Object { "$_" }) }
  } elseif ($profile) {
    $f = Get-ChildItem (Join-Path $repo "data\logs") -Filter "$profile-*.log" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) { $logFile = $f.Name; $logTail = [string[]]@(Get-Content $f.FullName -Tail 40 -Encoding utf8 | ForEach-Object { "$_" }) }
  }
  [ordered]@{
    name = $t.TaskName; kind = $kind; profile = $profile; job = $job; repeat = $repeat; what = $t.Description; state = "$($t.State)"
    day = $day; time = $time; analyze = [bool]($args -match '-Analyze')
    next_run = Iso $info.NextRunTime; last_run = Iso $info.LastRunTime; last_result = $info.LastTaskResult
    wake = [bool]$t.Settings.WakeToRun; log_file = $logFile; log_tail = $logTail
    script = $script; posts_only = [bool]($args -match '-PostsOnly')
  }
}

switch ($Command) {
  "list" {
    $tasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "viral-scout *" -or (Test-Legacy $_) } |
      Sort-Object { ($_.Triggers | Select-Object -First 1).StartBoundary } | ForEach-Object { Describe $_ })
    $profiles = @(Get-ChildItem (Join-Path $repo "profiles") -Filter *.yaml |
      Where-Object { $_.BaseName -notlike "_*" -and $_.BaseName -notlike "example-*" } | ForEach-Object BaseName)
    [ordered]@{ now = (Get-Date).ToString("o"); tasks = $tasks; profiles = $profiles } | ConvertTo-Json -Depth 5 -Compress
  }
  "enable" { Get-Ours $Name | Enable-ScheduledTask | Out-Null; "enabled $Name" }
  "disable" { Get-Ours $Name | Disable-ScheduledTask | Out-Null; "disabled $Name" }
  "run" { Get-Ours $Name | Start-ScheduledTask; "started $Name" }
  "stop" { Get-Ours $Name | Stop-ScheduledTask; "stopped $Name" }
  "remove" { Get-Ours $Name | Unregister-ScheduledTask -Confirm:$false; "removed $Name" }
  "set" {
    $t = Get-Ours $Name
    $cur = Describe $t
    if ($cur.kind -eq "legacy") { Fail "$Name belongs to another repo ($($cur.script)); set up the idea generator here instead" }
    if ($cur.kind -eq "studio") { Fail "studio tasks follow the profile: change jobs: in profiles/$($cur.profile).yaml, then run scripts/schedule-studio.ps1 -Profile $($cur.profile)" }
    $d = if ($Day) { $Day } else { $cur.day }
    $tm = if ($Time) { $Time } else { $cur.time }
    if ($d -notin @("Daily") + $days) { Fail "pick one day or Daily (task has '$d')" }
    $p = @{ TaskName = $Name; Trigger = (New-Trigger $d $tm) }
    if ($Analyze -ne "" -and $cur.kind -eq "profile") { $p.Action = New-Action $cur.profile ($Analyze -eq "1") }
    $wasDisabled = $t.State -eq "Disabled"
    Set-ScheduledTask @p | Out-Null
    if ($wasDisabled) { Disable-ScheduledTask -TaskName $Name | Out-Null }   # editing keeps a paused task paused
    "updated $Name to $d $tm"
  }
  "add" {
    if ($Profile -notmatch '^[\w.-]+$') { Fail "bad profile name" }
    if ($Profile -ne "publish" -and -not (Test-Path (Join-Path $repo "profiles\$Profile.yaml"))) { Fail "no profiles/$Profile.yaml" }
    $n = "viral-scout $Profile"
    if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Fail "'$n' already exists" }
    $d = if ($Day) { $Day } else { "Monday" }
    $settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $n -Action (New-Action $Profile ($Analyze -eq "1")) -Trigger (New-Trigger $d $(if ($Time) { $Time } else { "07:00" })) `
      -Settings $settings | Out-Null
    # New tasks start paused: turning one on is a separate, deliberate click (paid sources run on schedule).
    Disable-ScheduledTask -TaskName $n | Out-Null
    "added $n (paused)"
  }
  "studio-sync" {
    if ($Profile -notmatch '^[\w.-]+$') { Fail "bad profile name" }
    if (-not (Test-Path (Join-Path $repo "profiles\$Profile.yaml"))) { Fail "no profiles/$Profile.yaml" }
    $env:PYTHONIOENCODING = "utf-8"
    Push-Location $repo
    try { $json = & python -m viral_scout jobs $Profile install-plan --json 2>$null } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Fail "install-plan failed: $json" }
    $plan = @(($json | Select-Object -Last 1 | ConvertFrom-Json).tasks)
    $before = @{}
    Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "viral-scout $Profile.*" } |
      ForEach-Object { $before[$_.TaskName] = "$($_.State)" }
    $out = @()
    foreach ($t in $plan) {
      $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours $t.time_limit_hours) -MultipleInstances IgnoreNew
      $action = New-ScheduledTaskAction -Execute $pwsh -WorkingDirectory $repo `
        -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$repo\scripts\studio.ps1`" $($t.args)"
      Register-ScheduledTask -TaskName $t.name -Action $action -Trigger (New-StudioTrigger $t.trigger) -Settings $settings `
        -Description "viral-scout studio: $($t.what)" -Force | Out-Null
      # Only a task that was already on stays on; a new or paused one is paused (turning it on is the owner's click).
      $on = $before.ContainsKey($t.name) -and $before[$t.name] -ne "Disabled"
      if (-not $on) { Disable-ScheduledTask -TaskName $t.name | Out-Null }
      $out += "$($t.name): $($t.what)$(if ($on) { '' } else { ' (paused)' })"
    }
    foreach ($n in $before.Keys) {
      if ($n -notin $plan.name) { Unregister-ScheduledTask -TaskName $n -Confirm:$false; $out += "$n removed (off in the profile)" }
    }
    if (-not $out) { "no studio jobs for $Profile" } else { $out -join "; " }
  }
}
