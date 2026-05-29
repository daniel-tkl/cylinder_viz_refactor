<#
Ensure ARR and URL Rewrite are installed/upgraded via Chocolatey.

Usage (elevated PowerShell):
  .\scripts\ensure_arr.ps1

This script attempts to upgrade URL Rewrite and ARR. It requires Chocolatey
and an elevated session. It is conservative: if Chocolatey is missing it will
print instructions instead of attempting a risky install.
#>

. "$PSScriptRoot\common.ps1"
Ensure-Strict
Assert-Admin

function Ensure-ChocoAvailable {
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Error "Chocolatey not found. Install Chocolatey first: https://chocolatey.org/install"
        return $false
    }
    return $true
}

if (-not (Ensure-ChocoAvailable)) { exit 1 }

$errors = @()

Write-Host "Upgrading URL Rewrite (if installed)..."
try {
    & choco upgrade urlrewrite -y --no-progress
    if ($LASTEXITCODE -ne 0) { throw "choco exit $LASTEXITCODE" }
    Write-Host "URL Rewrite upgrade attempted (check Chocolatey output)."
} catch {
    $errors += "urlrewrite: $_"
}

Write-Host "Upgrading ARR..."
try {
    & choco upgrade iis-arr -y --no-progress --ignore-dependencies
    if ($LASTEXITCODE -ne 0) { throw "choco exit $LASTEXITCODE" }
    Write-Host "ARR upgrade attempted (check Chocolatey output)."
} catch {
    $errors += "iis-arr: $_"
}

if ($errors.Count -gt 0) {
    Write-Warning "Some upgrades failed. Review the errors below and consider running the commands manually as an administrator:"
    $errors | ForEach-Object { Write-Warning $_ }
    exit 2
}

Write-Host "ARR/URL Rewrite upgrade attempts finished. Please restart IIS if instructed by Chocolatey (or run: iisreset).
If you still see the deploy script fallback warning about /requestTimeout, the installed ARR version does not expose that attribute and an OS-level ARR/Rewrite update may be required."
