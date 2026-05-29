<#
Install the Streamlit app as a Windows Service using WinSW (Windows Service Wrapper).

This script will:
- Download winsw-x64.exe into `scripts\winsw\<ServiceName>.exe` (from GitHub releases)
- Create a `<ServiceName>.xml` alongside the exe with a runnable wrapper that executes
  the existing `scripts\start_cylinder_viz_app.bat` via `cmd.exe /c`.
- Optionally install the service and start it.

Usage (elevated PowerShell):
  .\scripts\install_winsw_service.ps1 -ServiceName CylinderViz -DisplayName "Cylinder Viz" -Install

Important:
- This script does not embed passwords in plain text by default. If you need the
  service to run as a specific user, provide `-ServiceUser` and `-ServicePassword`.
- Review the generated XML before installing.
#>

param(
    [Parameter(Mandatory=$false)][string]$ServiceName = "CylinderVizApp",
    [Parameter(Mandatory=$false)][string]$DisplayName = "Cylinder Viz App Win",
    [Parameter(Mandatory=$false)][string]$Description = "Cylinder Viz App Service wrapper",
    [Parameter(Mandatory=$false)][string]$ExecBatch = "scripts\start_cylinder_viz_app.bat",
    [Parameter(Mandatory=$false)][switch]$Install,
    [Parameter(Mandatory=$false)][string]$ServiceUser = "",
    [Parameter(Mandatory=$false)][string]$ServicePassword = ""
)

. "$PSScriptRoot\common.ps1"
Ensure-Strict
Assert-Admin

$repoRoot = Split-Path -Parent $PSScriptRoot
$execPath = (Resolve-Path -Path (Join-Path $repoRoot $ExecBatch)).ProviderPath

$winswDir = Join-Path $PSScriptRoot "winsw"
if (-not (Test-Path $winswDir)) { New-Item -Path $winswDir -ItemType Directory | Out-Null }

$exeName = "$ServiceName.exe"
$exePath = Join-Path $winswDir $exeName
$xmlPath = [IO.Path]::ChangeExtension($exePath, '.xml')

Write-Host "Preparing WinSW wrapper in: $winswDir"

# Download WinSW if missing
if (-not (Test-Path $exePath)) {
    Write-Host "Downloading WinSW (latest x64) to $exePath"
    $latestUrl = 'https://github.com/winsw/winsw/releases/latest/download/winsw-x64.exe'
    try {
        Invoke-WebRequest -Uri $latestUrl -OutFile $exePath -UseBasicParsing -ErrorAction Stop
    } catch {
        throw "Failed to download WinSW from $latestUrl : $_"
    }
}

Write-Host "Generating service XML: $xmlPath"

$accountXml = ''
if ($ServiceUser -and $ServicePassword) {
    $escapedUser = [System.Security.SecurityElement]::Escape($ServiceUser)
    $escapedPass = [System.Security.SecurityElement]::Escape($ServicePassword)
    $accountXml = "<serviceaccount><user>$escapedUser</user><password>$escapedPass</password></serviceaccount>"
}

$xml = @"
<service>
  <id>$ServiceName</id>
  <name>$DisplayName</name>
  <description>$Description</description>
  <executable>cmd.exe</executable>
  <arguments>/c `"$execPath`"</arguments>
  <logpath>..\logs\$ServiceName</logpath>
  <log mode="roll">true</log>
  $accountXml
  <onfailure action="restart" delay="5000" />
</service>
"@

[IO.File]::WriteAllText($xmlPath, $xml)

Write-Host "Created $xmlPath"

if ($Install.IsPresent) {
    Write-Host "Installing service via WinSW: $exePath install"
    Push-Location $winswDir
    try {
        & "$exePath" install
        if ($LASTEXITCODE -ne 0) { throw "WinSW install returned exit $LASTEXITCODE" }
        & "$exePath" start
    } finally {
        Pop-Location
    }
    Write-Host "Service installed and started. Use 'Get-Service -Name $ServiceName' to check status."
} else {
    Write-Host "Sketched wrapper created. To install run (elevated):"
    Write-Host "  Push-Location '$winswDir' ; .\\$exeName install ; .\\$exeName start"
}
