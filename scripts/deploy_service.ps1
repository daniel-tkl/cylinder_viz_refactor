<#
Deploy Cylinder Viz as a Windows Service via WinSW.

This script will optionally create a local service account, grant ACLs on the app folder,
attempt to grant the "Log on as a service" right (if `ntrights.exe` or `secedit` is available),
and call `install_winsw_service.ps1` to generate and install the WinSW wrapper.

Usage (elevated):
  .\scripts\deploy_service.ps1 -ServiceUser cylvizsvc -ServicePassword 'P@ssw0rd!' -Install

If you prefer to create the account manually, provide `-ServiceUser` and `-SkipCreateUser`.
#>

param(
    [string]$ServiceName = 'CylinderVizApp',
    [string]$ServiceUser = '',
    [string]$ServicePassword = '',
    [string]$AppRoot = "",
    [switch]$SkipCreateUser,
    [switch]$Install
)

. "$PSScriptRoot\common.ps1"
Ensure-Strict
Assert-Admin

# Try to load repo .env for defaults if present
$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot '.env'
if (Test-Path $envPath) {
    Load-EnvFile -Path $envPath -ToScriptScope
    if (-not $AppRoot -and (Get-Variable -Name APP_ROOT -Scope Script -ErrorAction SilentlyContinue)) {
        $AppRoot = (Get-Variable -Name APP_ROOT -Scope Script).Value
    }
}

# Fallback to repo root when no explicit AppRoot is provided
if (-not $AppRoot -or $AppRoot -eq '') { $AppRoot = $repoRoot }

# Normalize path
$AppRoot = (Resolve-Path -Path $AppRoot).ProviderPath

if ($ServiceUser -and -not $SkipCreateUser) {
    $userExists = Get-LocalUser -Name $ServiceUser -ErrorAction SilentlyContinue
    if (-not $userExists) {
        if (-not $ServicePassword) { throw "ServicePassword is required when creating a new local user." }
        Write-Host "Creating local user $ServiceUser"
        $securePass = ConvertTo-SecureString $ServicePassword -AsPlainText -Force
        New-LocalUser -Name $ServiceUser -Password $securePass -Description "CylinderViz service account" -NoPasswordExpired | Out-Null
        Add-LocalGroupMember -Group Users -Member $ServiceUser
    } else {
        Write-Host "Local user $ServiceUser already exists."
    }

    Write-Host "Granting ACLs to $AppRoot for $ServiceUser"
    icacls $AppRoot /grant "$ServiceUser:(OI)(CI)M" | Out-Null

    # Try to grant 'Log on as a service' if tools are present
    $granted = $false
    if (Get-Command ntrights.exe -ErrorAction SilentlyContinue) {
        Write-Host "Granting 'Log on as a service' via ntrights.exe"
        & ntrights.exe +r SeServiceLogonRight -u $ServiceUser
        $granted = $true
    } elseif (Get-Command secedit.exe -ErrorAction SilentlyContinue) {
        Write-Host "Attempting to grant 'Log on as a service' via secedit (may require manual steps)"
        # TODO: implement secedit template export/modify/import if needed
    } else {
        Write-Warning "Could not automatically assign 'Log on as a service'. Please assign it manually via Local Security Policy (secpol.msc) or a GPO."
    }
}

# Call WinSW installer helper
$installer = Join-Path $PSScriptRoot 'install_winsw_service.ps1'
if (-not (Test-Path $installer)) { throw "install_winsw_service.ps1 not found in scripts folder" }

$args = @('-ServiceName', $ServiceName, '-DisplayName', 'Cylinder Viz')
if ($ServiceUser) { $args += '-ServiceUser'; $args += $ServiceUser }
if ($ServicePassword) { $args += '-ServicePassword'; $args += $ServicePassword }
if ($Install) { $args += '-Install' }

Write-Host "Invoking WinSW installer helper with: $($args -join ' ')"
& $installer @args

Write-Host "WinSW deploy helper completed. Verify the service with Get-Service -Name $ServiceName"
