# Publish the dashboard to Vercel (free Hobby plan) as a read-only snapshot.
# The data is exported on this PC and uploaded with the deploy; it is never committed to git.
# First time: npx vercel login; then this script links the project (web/.vercel, git-ignored).
# Password: set SITE_PASSWORD and SESSION_SECRET once with scripts/publish.ps1 -SetPassword.
param([switch]$SetPassword, [switch]$Preview)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$web = Join-Path $repo "web"
$env:PYTHONIOENCODING = "utf-8"

Push-Location $repo
try { & python -m viral_scout export; if ($LASTEXITCODE) { throw "export failed" } } finally { Pop-Location }

Push-Location $web
try {
  if (-not (Test-Path ".vercel\project.json")) {
    & npx --yes vercel@latest link --yes --project viral-scout
    if ($LASTEXITCODE) { throw "vercel link failed (run: npx vercel login)" }
  }
  if ($SetPassword) {
    $pw = Read-Host "Dashboard password" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw))
    $secret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
    foreach ($pair in @(@("SITE_PASSWORD", $plain), @("SESSION_SECRET", $secret))) {
      & npx --yes vercel@latest env rm $pair[0] production --yes 2>$null | Out-Null
      $pair[1] | & npx --yes vercel@latest env add $pair[0] production
    }
  }
  if ($Preview) { & npx --yes vercel@latest deploy } else { & npx --yes vercel@latest deploy --prod }
} finally { Pop-Location }
