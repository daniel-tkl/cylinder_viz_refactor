<#
Common helper functions for scripts/ PowerShell scripts.

Provides:
- Assert-Admin: throw if not running elevated
- Load-EnvFile: load simple KEY=VALUE .env files into Env: or script scope
- Ensure-Strict: set strict mode and stop-on-error
#>

function Ensure-Strict {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
}

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

function Load-EnvFile {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [switch]$ToScriptScope
    )
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([^#;][^=\s]+)=(.*)$') {
            $name = $matches[1]
            $value = $matches[2]
            if ($ToScriptScope.IsPresent) {
                Set-Variable -Name $name -Value $value -Scope Script -Force
            } else {
                Set-Item -Path Env:$name -Value $value
            }
        }
    }
}

<# Usage in scripts:
. "$PSScriptRoot\common.ps1"
Ensure-Strict
Load-EnvFile -Path (Join-Path $PSScriptRoot ".env")
Assert-Admin
#>
