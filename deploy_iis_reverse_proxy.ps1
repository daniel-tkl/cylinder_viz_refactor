
# Load .env if present
$envPath = Join-Path $PSScriptRoot ".env"
if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    if ($_ -match '^(\w+)=(.*)$') {
      $name = $matches[1]
      $value = $matches[2]
      Set-Variable -Name $name -Value $value -Scope Script -Force
    }
  }
}

param(
  [string]$SiteName = "CylinderVizProxy",
  [int]$PublicPort = ${PublicPort} ? [int]$PublicPort : 80,
  [string]$HostHeader = ${HostHeader} ? $HostHeader : "",
  [string]$AppRoot = ${AppRoot} ? $AppRoot : "E:\apps\cylinder_viz_refactor",
  [int]$StreamlitPort = ${StreamlitPort} ? [int]$StreamlitPort : 8501
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

Assert-Admin

$appcmd = "C:\Windows\System32\inetsrv\appcmd.exe"
if (-not (Test-Path $appcmd)) {
    throw "IIS appcmd not found. Install IIS Web-Server role first."
}

# Enable ARR reverse proxy globally.
& $appcmd set config -section:system.webServer/proxy /enabled:"True" /preserveHostHeader:"True" /reverseRewriteHostInResponseHeaders:"False" /commit:apphost
if ($LASTEXITCODE -ne 0) {
  throw "Failed to enable ARR proxy settings in IIS."
}

$proxyRoot = Join-Path $AppRoot "iis_proxy_site"
New-Item -ItemType Directory -Path $proxyRoot -Force | Out-Null

$webConfigPath = Join-Path $proxyRoot "web.config"
$webConfig = @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="StreamlitReverseProxy" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:$StreamlitPort/{R:1}" appendQueryString="true" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
"@

Set-Content -Path $webConfigPath -Value $webConfig -Encoding UTF8

$bindings = if ([string]::IsNullOrWhiteSpace($HostHeader)) {
  "http/*:{0}:" -f $PublicPort
} else {
  "http/*:{0}:{1}" -f $PublicPort, $HostHeader
}

$null = & $appcmd list site /name:$SiteName 2>$null
$siteExists = ($LASTEXITCODE -eq 0)

if (-not $siteExists -and [string]::IsNullOrWhiteSpace($HostHeader)) {
  $portPattern = "http/*:{0}:" -f $PublicPort
  $bindingConflicts = & $appcmd list site /text:name,bindings | Select-String -SimpleMatch $portPattern
  if ($bindingConflicts) {
    $conflictText = ($bindingConflicts | ForEach-Object { $_.Line }) -join [Environment]::NewLine
    throw "Port $PublicPort is already bound. Use -HostHeader, a different -PublicPort, or reuse that site.`n$conflictText"
  }
}

if ($siteExists) {
  & $appcmd set vdir /vdir.name:"$SiteName/" /physicalPath:"$proxyRoot"
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to update site physical path for $SiteName."
  }
    & $appcmd set site /site.name:$SiteName /bindings:"$bindings"
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to update site bindings for $SiteName."
  }
} else {
    & $appcmd add site /name:$SiteName /bindings:$bindings /physicalPath:"$proxyRoot"
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create site $SiteName with binding $bindings."
  }
}

& $appcmd start site /site.name:$SiteName
if ($LASTEXITCODE -ne 0) {
  throw "Failed to start site $SiteName."
}

Write-Host "IIS reverse proxy site configured." -ForegroundColor Green
Write-Host "SiteName: $SiteName"
Write-Host "Binding : $bindings"
Write-Host "Proxy   : http://127.0.0.1:$StreamlitPort"
