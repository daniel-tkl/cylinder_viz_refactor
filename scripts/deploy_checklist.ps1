<#
One-shot deploy checklist for Cylinder Viz

Usage (from an elevated PowerShell prompt in the repo root):
  .\scripts\deploy_checklist.ps1 -AppRoot "E:\apps\dev\cylinder_viz_refactor" -RunIIS -CreateVenv -InstallDeps -RegisterTask -OpenFirewall -SmokeTest -InstallWebSockets

This script performs safe, idempotent steps:
- asserts admin
- loads .env if present
- (optional) creates venv and installs pinned requirements
- (optional) registers scheduled task (calls scripts/scheduler.bat)
 - (optional) configures IIS reverse proxy (calls scripts/deploy_iis_reverse_proxy.ps1)
- (optional) opens firewall and performs a simple smoke test

Be careful with credentials in .env; prefer gMSA/secret vault in production.
#>

Param(
    [string]$AppRoot = "E:\apps\dev\cylinder_viz_refactor",
    [string]$SiteName = "CylinderVizProxy",
    [int]$PublicPort = 8080,
    [int]$StreamlitPort = 8501,
    [string]$RequestTimeout = "00:10:00",
    [switch]$InstallWebSockets,
    [switch]$RunIIS,
    [switch]$CreateVenv,
    [switch]$InstallDeps,
    [switch]$RegisterTask,
    [switch]$UseService,
    [switch]$OpenFirewall,
    [switch]$SmokeTest,
    [switch]$NonInteractive
)

. "$PSScriptRoot\common.ps1"
Ensure-Strict

function Run-Command($script, $args) {
    Write-Host "Running: $script $args"
    & $script @args
}

$envPath = Join-Path $AppRoot ".env"
Load-EnvFile -Path $envPath

# Normalize path
$AppRoot = (Resolve-Path -Path $AppRoot).ProviderPath

    # Load .env if present (already loaded above into environment)

Push-Location $AppRoot
try {
    if ($CreateVenv) {
        $venvPath = Join-Path $AppRoot ".venv"
        if (-not (Test-Path $venvPath)) {
            Write-Host "Creating virtualenv at $venvPath"
            python -m venv $venvPath
        } else {
            Write-Host "Virtualenv already exists at $venvPath"
        }
    }

    if ($InstallDeps) {
        # Activate venv in the current session for pip
        $activate = Join-Path $AppRoot ".venv\Scripts\Activate.ps1"
        if (Test-Path $activate) {
            Write-Host "Activating virtualenv"
            . $activate
        } else {
            Write-Warning "Activation script not found at $activate. Ensure Python venv exists or use -CreateVenv."
        }

        if (Test-Path "$AppRoot\requirements.txt") {
            Write-Host "Installing pinned requirements from requirements.txt"
            python -m pip install --upgrade pip
            pip install -r "$AppRoot\requirements.txt"
        } elseif (Test-Path "$AppRoot\requirements.in") {
            Write-Host "Compiling and installing from requirements.in"
            # Use the helper if present
            $gen = Join-Path $AppRoot "scripts\generate_locked_requirements.ps1"
            if (Test-Path $gen) {
                & $gen
            } else {
                Write-Host "Installing pip-tools and compiling requirements"
                python -m pip install --upgrade pip
                pip install pip-tools
                pip-compile requirements.in --output-file requirements.txt
            }
            pip install -r "$AppRoot\requirements.txt"
        } else {
            Write-Warning "No requirements.txt or requirements.in found — skipping dependency install."
        }
    }

    if ($RegisterTask) {
        if ($UseService) {
            $svc = Join-Path $AppRoot "scripts\install_winsw_service.ps1"
            if (Test-Path $svc) {
                Write-Host "Registering Windows Service using WinSW via install_winsw_service.ps1"
                $svcArgs = @('-ServiceName','CylinderVizWinService','-DisplayName','Cylinder Viz','-Install')
                if ($env:SERVICE_USER) { $svcArgs += '-ServiceUser'; $svcArgs += $env:SERVICE_USER }
                if ($env:SERVICE_PASS) { $svcArgs += '-ServicePassword'; $svcArgs += $env:SERVICE_PASS }
                & $svc @svcArgs
            } else {
                Write-Warning "install_winsw_service.ps1 not found at $svc"
            }
        } else {
            $sched = Join-Path $AppRoot "scripts\scheduler.bat"
            if (Test-Path $sched) {
                Write-Host "Registering scheduled task using scheduler.bat"
                & $sched
            } else {
                Write-Warning "scheduler.bat not found at $sched"
            }
        }
    }

    if ($RunIIS) {
        $deploy = Join-Path $AppRoot "scripts\deploy_iis_reverse_proxy.ps1"
        if (Test-Path $deploy) {
            $deployArgs = @()
            if ($InstallWebSockets) { $deployArgs += '-InstallWebSockets' }
            $deployArgs += '-SiteName'; $deployArgs += $SiteName
            $deployArgs += '-PublicPort'; $deployArgs += $PublicPort
            $deployArgs += '-AppRoot'; $deployArgs += $AppRoot
            $deployArgs += '-StreamlitPort'; $deployArgs += $StreamlitPort
            $deployArgs += '-RequestTimeout'; $deployArgs += $RequestTimeout
            Write-Host "Running IIS deploy: $deploy $deployArgs"
            & $deploy @deployArgs
        } else {
            Write-Warning "deploy_iis_reverse_proxy.ps1 not found at $deploy"
        }
    }

    if ($OpenFirewall) {
        Write-Host "Adding firewall rule for TCP port $PublicPort"
        if (-not (Get-NetFirewallRule -DisplayName "CylinderViz-$PublicPort-In" -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName "CylinderViz-$PublicPort-In" -Direction Inbound -Protocol TCP -LocalPort $PublicPort -Action Allow
        } else {
            Write-Host "Firewall rule already exists."
        }
    }

    if ($SmokeTest) {
        $url = "http://localhost:$PublicPort/"
        Write-Host "Running smoke test against $url"
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) {
                Write-Host "Smoke test passed: $($r.StatusCode)"
            } else {
                Write-Warning "Smoke test returned status $($r.StatusCode)"
            }
        } catch {
            Write-Warning "Smoke test failed: $_"
        }
    }

    # Verification: show ARR proxy config if appcmd available
    $appcmd = Join-Path $env:windir "system32\inetsrv\appcmd.exe"
    if (Test-Path $appcmd) {
        Write-Host "Current ARR proxy config:"
        & $appcmd list config -section:system.webServer/proxy
    }

    Write-Host "Deploy checklist completed. Review output for any warnings/errors."
} finally {
    Pop-Location
}
