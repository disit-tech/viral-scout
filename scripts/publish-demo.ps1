# Publish the PUBLIC demo (no login, sample data only) to a separate Vercel project "viral-scout-demo".
# Demo data comes from web/data-demo (sanitized copies: generic profile names, no business strategy, public posts only).
# The real dashboard (scripts/publish.ps1) stays separate and password-protected.
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$web = Join-Path $repo "web"
$out = Join-Path $repo "data\demo-site"
if (-not (Test-Path (Join-Path $web "data-demo\index.json"))) { throw "web/data-demo is empty: build the demo data first" }

# Fresh copy of the app without local state, with the demo data as its data/.
$keepLink = Join-Path $out ".vercel"
$tmpLink = Join-Path $repo "data\demo-vercel-link"
if (Test-Path $keepLink) { Copy-Item $keepLink $tmpLink -Recurse -Force }
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force $out | Out-Null
$skip = @("node_modules", ".next", ".vercel", "data", "data-demo", ".env.local")
Get-ChildItem $web -Force | Where-Object { $skip -notcontains $_.Name } | ForEach-Object { Copy-Item $_.FullName $out -Recurse -Force }
Copy-Item (Join-Path $web "data-demo") (Join-Path $out "data") -Recurse -Force
Set-Content (Join-Path $out ".vercelignore") "node_modules`n.next`n.vercel`n.env*.local"
if (Test-Path $tmpLink) { Copy-Item $tmpLink $keepLink -Recurse -Force; Remove-Item $tmpLink -Recurse -Force }

Push-Location $out
try {
  if (-not (Test-Path ".vercel\project.json")) {
    & npx --yes vercel@latest link --yes --project viral-scout-demo
    "1" | & npx --yes vercel@latest env add VIRAL_SCOUT_PUBLIC_DEMO production
  }
  & npx --yes vercel@latest deploy --prod --yes
} finally { Pop-Location }
