<#
Diagnose Cylinder Viz processes: parent chains and scheduled tasks.
Run elevated.
#>
. "$PSScriptRoot\common.ps1"
Ensure-Strict

function Show-Chain([int]$startPid){
    while ($startPid -and $startPid -ne 0) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$startPid" -ErrorAction SilentlyContinue
        if (-not $p) { break }
        $wmi = Get-WmiObject Win32_Process -Filter "ProcessId=$startPid" -ErrorAction SilentlyContinue
        $ownerStr = '\'
        if ($wmi) { $o = $wmi.GetOwner(); $ownerStr = "$($o.Domain)\$($o.User)" }
        Write-Host "PID=$($p.ProcessId) Name=$($p.Name) Parent=$($p.ParentProcessId) Owner=$ownerStr Cmd=$($p.CommandLine)"
        $startPid = $p.ParentProcessId
    }
}

Write-Host "Finding processes with command line containing 'streamlit' or the start script or venv python..."
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'streamlit' -or $_.CommandLine -match 'start_cylinder_viz_app.bat' -or $_.CommandLine -match '\\.venv\\Scripts\\python.exe') }
if (-not $procs) { Write-Host "No matching processes found."; exit 0 }

foreach ($p in $procs) {
    Write-Host '---'
    Show-Chain $p.ProcessId
}

Write-Host '---\nScheduled tasks matching Cylinder*:'
Get-ScheduledTask | Where-Object TaskName -like '*Cylinder*' | Select-Object TaskName,State,LastRunTime,NextRunTime | Format-List

Write-Host '---\nScheduled tasks with recent last run (last 1 hour):'
Get-ScheduledTask | Where-Object { $_.LastRunTime -gt (Get-Date).AddHours(-1) } | Select-Object TaskName,State,LastRunTime | Format-List
