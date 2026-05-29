Param(
    [string]$TaskName = "CylinderVizApp",
    [string]$ScriptRelativePath = "scripts/start_cylinder_viz_app.bat",
    [int]$RestartCount = 5,
    [int]$RestartIntervalSec = 10,
    [string]$ServiceUser = "",
    [string]$ServicePassword = ""
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"
Ensure-Strict

# Resolve script path relative to repo root (script lives under repo root/scripts)
$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Resolve-Path -Path (Join-Path $repoRoot $ScriptRelativePath)
$scriptPath = $scriptPath.ProviderPath

Write-Host "Registering scheduled task '$TaskName' to run: $scriptPath"

# Build action to run the batch under cmd.exe so the BAT runs correctly
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$scriptPath`""

# Trigger at system startup
$trigger = New-ScheduledTaskTrigger -AtStartup

# Ensure restart interval meets Scheduled Task minimum (1 minute)
if ($RestartIntervalSec -lt 60) {
    Write-Host "Requested RestartIntervalSec ($RestartIntervalSec)s is too small for Scheduled Tasks; clamping to 60s."
    $RestartIntervalSec = 60
}

# Settings: restart on failure, try a few times, allow start when available
$restartInterval = New-TimeSpan -Seconds $RestartIntervalSec
$settings = New-ScheduledTaskSettingsSet -RestartCount $RestartCount -RestartInterval $restartInterval -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

if ($ServiceUser -and $ServiceUser.Trim() -ne "") {
    Write-Host "Service account provided — creating task to run as $ServiceUser using schtasks.exe"

    # If task exists, delete first for idempotency
    & schtasks /Query /TN "$TaskName" > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Existing task found — deleting."
        & schtasks /Delete /TN "$TaskName" /F
    }

    # Build the command to run the batch via cmd.exe
    $tr = '"cmd.exe" /c "' + $scriptPath + '"'

    # Use schtasks to register with provided credentials
    $args = @('/Create','/TN',$TaskName,'/TR',$tr,'/SC','ONSTART','/RU',$ServiceUser,'/RP',$ServicePassword,'/RL','LIMITED','/F')
    & schtasks @args
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks failed to create task for $ServiceUser (exit $LASTEXITCODE)"
    }

    Write-Host "Starting scheduled task $TaskName"
    & schtasks /Run /TN $TaskName
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to start task immediately (exit $LASTEXITCODE), it will run on next startup."
    }

    Write-Host "Scheduled task '$TaskName' registered (user: $ServiceUser)."

} else {
    # Run as the SYSTEM service account
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Write-Host "Task exists — unregistering old task before re-registering."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal

    Start-ScheduledTask -TaskName $TaskName

    Write-Host "Scheduled task '$TaskName' registered and started as SYSTEM."
}
