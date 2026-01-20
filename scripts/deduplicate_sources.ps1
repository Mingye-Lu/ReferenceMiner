param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$ReferencesDir = "",
    [switch]$Delete
)

if (-not $ReferencesDir) {
    $ReferencesDir = Join-Path $Root "references"
}

if (-not (Test-Path -LiteralPath $ReferencesDir)) {
    Write-Error "References directory not found: $ReferencesDir"
    exit 1
}

$files = Get-ChildItem -LiteralPath $ReferencesDir -File -Recurse
$hashGroups = @{}

foreach ($file in $files) {
    try {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLower()
    } catch {
        Write-Warning "Failed to hash: $($file.FullName)"
        continue
    }

    if (-not $hashGroups.ContainsKey($hash)) {
        $hashGroups[$hash] = New-Object System.Collections.ArrayList
    }
    [void]$hashGroups[$hash].Add($file)
}

$dupeGroups = $hashGroups.Values | Where-Object { $_.Count -gt 1 }

if (-not $dupeGroups) {
    Write-Host "No duplicate files found under: $ReferencesDir"
    exit 0
}

foreach ($group in $dupeGroups) {
    $sorted = $group | Sort-Object LastWriteTime, FullName
    $keep = $sorted[0]
    Write-Host "Keep: $($keep.FullName)"

    $dupes = $sorted | Select-Object -Skip 1
    foreach ($dup in $dupes) {
        if ($Delete) {
            Remove-Item -LiteralPath $dup.FullName -Force
            Write-Host "Removed: $($dup.FullName)"
        } else {
            Write-Host "Dup: $($dup.FullName)"
        }
    }
}

if (-not $Delete) {
    Write-Host "Run with -Delete to remove duplicates."
}
