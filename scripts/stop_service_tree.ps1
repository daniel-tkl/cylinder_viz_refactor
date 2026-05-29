<#
Stop and optionally force-kill service process trees for Cylinder Viz.

Usage (run elevated from repo root):
  # Dry-run (shows processes)
  .\scripts\stop_service_tree.ps1

  # Force-kill identified processes without prompting
  .\scripts\stop_service_tree.ps1 -Force

This script:
- Finds processes listening on common Streamlit and proxy ports (9501, 8501, 9090, 8080)
- Also finds processes whose command line contains 'streamlit' or 'start_cylinder_viz_app.bat'
- Displays owners and command lines, then stops the service (if WinSW) and kills the process trees.
#>

. "$PSScriptRoot\common.ps1"
Ensure-Strict
Assert-Admin

# simple arg parse to avoid param block parsing issues in some shells
$Force = $false
if ($args -and ($args -contains '-Force' -or $args -contains '/Force')) { $Force = $true }

function Get-ServicePid([string]$serviceName) {
    try {
        $svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" -ErrorAction Stop
        return $svc.ProcessId
    } catch {
        return $null
    }
}

function Get-ChildProcs($pid){
    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $pid } |
      ForEach-Object { $_; Get-ChildProcs $_.ProcessId }
}

function Kill-Tree($pid){
    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $pid } |
      ForEach-Object { Kill-Tree $_.ProcessId }
    try { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } catch {}
}

Write-Host "Scanning for Cylinder Viz related processes..."

# common ports used by Streamlit and the IIS proxy
$ports = @(9501,9090)
$listeners = @()
foreach ($p in $ports) {
    try {
        $c = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
        if ($c) { $listeners += $c }
    } catch {}
}


# Prefer command-line matches (more precise); fall back to listening ports if none found
$cmdMatches = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -and ($_.CommandLine -match 'streamlit' -or $_.CommandLine -match 'start_cylinder_viz_app.bat' -or $_.CommandLine -match '\.venv\\Scripts\\python.exe')) }
if ($cmdMatches) {
    $pids = $cmdMatches.ProcessId | Sort-Object -Unique
} else {
    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
}

# filter out system and invalid PIDs
$pids = $pids | Where-Object { $_ -and $_ -ne 0 -and $_ -gt 4 } | Sort-Object -Unique

if (-not $pids) {
    Write-Host "No matching CylViz processes found listening on common ports or matching command line."
    exit 0
}

Write-Host "Found PIDs: $($pids -join ', ')"
foreach ($targetPid in $pids) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$targetPid" -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    # use WMI to get owner method
    $wmi = Get-WmiObject Win32_Process -Filter "ProcessId=$targetPid" -ErrorAction SilentlyContinue
    $ownerStr = '\' 
    if ($wmi) { $o = $wmi.GetOwner(); $ownerStr = "$($o.Domain)\$($o.User)" }
    Write-Host "PID=$targetPid Name=$($proc.Name) Owner=$ownerStr Cmd=$($proc.CommandLine)"
}

if (-not $Force) {
    $ok = Read-Host "Proceed to stop/killing these processes? Type Y to continue"
    if ($ok -ne 'Y') { Write-Host "Aborting."; exit 0 }
}

foreach ($targetPid in $pids) {
    # If a service is associated with this PID, try to stop the service first
    $svc = Get-CimInstance Win32_Service | Where-Object { $_.ProcessId -eq $targetPid }
    if ($svc) {
        Write-Host "Stopping service $($svc.Name)"
        try { Stop-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue } catch {}
    }

    Write-Host "Killing process tree for PID $targetPid"
    try { Kill-Tree $targetPid } catch {}
}

Start-Sleep -Seconds 1

# verify
 $still = @()
foreach ($p in $pids) {
    if (Get-Process -Id $p -ErrorAction SilentlyContinue) { $still += $p }
}
if ($still) {
    Write-Warning "Some PIDs still present: $($still -join ', ')"
} else {
    Write-Host "All target processes terminated."
}
