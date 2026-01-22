param(
  [string]$AppSource = "",
  [string]$BackendSource = "dist\\ReferenceMiner.exe"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$payloadRoot = Join-Path $root "installer\\payload"
$appTarget = Join-Path $payloadRoot "app"
$backendTarget = Join-Path $payloadRoot "backend"

if (-not $AppSource) {
  $candidate = Get-ChildItem -Path (Join-Path $root "dist-electron") -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*win-unpacked*" } |
    Select-Object -First 1
  if ($candidate) {
    $AppSource = $candidate.FullName
  }
}

if (-not $AppSource -or -not (Test-Path $AppSource)) {
  throw "App source not found. Provide -AppSource or build Electron app to dist-electron/win-unpacked."
}

if (-not (Test-Path $BackendSource)) {
  throw "Backend source not found at $BackendSource. Build backend to dist/ReferenceMiner.exe."
}

Remove-Item -Recurse -Force $appTarget -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $backendTarget -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force $appTarget | Out-Null
New-Item -ItemType Directory -Force $backendTarget | Out-Null

Copy-Item -Path $AppSource -Destination $appTarget -Recurse -Force
Copy-Item -Path $BackendSource -Destination (Join-Path $backendTarget "ReferenceMiner.exe") -Force

$files = Get-ChildItem -Path $payloadRoot -Recurse -File | Where-Object { $_.Name -ne "manifest.json" }
$items = @()
foreach ($file in $files) {
  $relative = $file.FullName.Substring($payloadRoot.Length + 1)
  $hash = Get-FileHash -Path $file.FullName -Algorithm SHA256
  $items += [pscustomobject]@{
    path   = $relative
    size   = $file.Length
    sha256 = $hash.Hash.ToLower()
  }
}

$packageJson = Get-Content (Join-Path $root "package.json") | ConvertFrom-Json
$manifest = [ordered]@{
  productName = "ReferenceMiner"
  version = $packageJson.version
  entry = @{
    appExe = "app\\ReferenceMiner.exe"
    backendExe = "backend\\ReferenceMiner.exe"
  }
  files = $items
}

$manifestPath = Join-Path $payloadRoot "manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 $manifestPath

Write-Host "Payload prepared at $payloadRoot"
