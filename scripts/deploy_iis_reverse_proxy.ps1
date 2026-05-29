param(
  [string]$SiteName = "CylinderVizProxy",
  [int]$PublicPort = 80,
  [string]$HostHeader = "",
  [string]$AppRoot = "E:\apps\cylinder_viz_refactor",
  [int]$StreamlitPort = 8501,
  [string]$RequestTimeout = "00:10:00",
  [switch]$InstallWebSockets
)

. "$PSScriptRoot\common.ps1"
$envPath = Join-Path $PSScriptRoot ".env"
Load-EnvFile -Path $envPath -ToScriptScope

Ensure-Strict
Assert-Admin

# Override param defaults with any script-scoped variables loaded from .env
if (Get-Variable -Name 'SiteName' -Scope Script -ErrorAction SilentlyContinue) { $SiteName = (Get-Variable -Name 'SiteName' -Scope Script).Value }
if (Get-Variable -Name 'PublicPort' -Scope Script -ErrorAction SilentlyContinue) { $PublicPort = [int](Get-Variable -Name 'PublicPort' -Scope Script).Value }
if (Get-Variable -Name 'HostHeader' -Scope Script -ErrorAction SilentlyContinue) { $HostHeader = (Get-Variable -Name 'HostHeader' -Scope Script).Value }
if (Get-Variable -Name 'AppRoot' -Scope Script -ErrorAction SilentlyContinue) { $AppRoot = (Get-Variable -Name 'AppRoot' -Scope Script).Value }
if (Get-Variable -Name 'StreamlitPort' -Scope Script -ErrorAction SilentlyContinue) { $StreamlitPort = [int](Get-Variable -Name 'StreamlitPort' -Scope Script).Value }
if (Get-Variable -Name 'RequestTimeout' -Scope Script -ErrorAction SilentlyContinue) { $RequestTimeout = (Get-Variable -Name 'RequestTimeout' -Scope Script).Value }

$appcmd = "C:\Windows\System32\inetsrv\appcmd.exe"
if (-not (Test-Path $appcmd)) {
    throw "IIS appcmd not found. Install IIS Web-Server role first."
}

# Optionally ensure WebSocket server feature is installed (server-level)
if ($InstallWebSockets.IsPresent) {
  try {
    $ws = Get-WindowsFeature -Name Web-WebSockets -ErrorAction Stop
    if (-not $ws.Installed) {
      Write-Host "Web-WebSockets feature not installed. Installing..."
      Install-WindowsFeature Web-WebSockets -ErrorAction Stop | Out-Null
      Write-Host "Web-WebSockets installed."
    } else {
      Write-Host "Web-WebSockets already installed."
    }
  } catch {
    Write-Warning "Unable to query/install Web-WebSockets: $_. Skipping WebSocket install step."
  }
}

# Enable ARR reverse proxy globally and set request timeout when supported
$proxyCmdBase = @(
  'set','config','-section:system.webServer/proxy',
  "/enabled:`"True`"",
  "/preserveHostHeader:`"True`"",
  "/reverseRewriteHostInResponseHeaders:`"False`""
)

# Try applying requestTimeout if provided; if appcmd rejects the attribute, retry without it
if ($RequestTimeout) {
  $proxyCmdWithTimeout = $proxyCmdBase + ("/requestTimeout:`"$RequestTimeout`"", "/commit:apphost")
  & $appcmd @proxyCmdWithTimeout
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "appcmd failed to set proxy requestTimeout (maybe ARR version does not support this attribute). Retrying without requestTimeout."
    $proxyCmdNoTimeout = $proxyCmdBase + ("/commit:apphost")
    & $appcmd @proxyCmdNoTimeout
    if ($LASTEXITCODE -ne 0) {
      throw "Failed to enable ARR proxy settings in IIS."
    }
  }
} else {
  $proxyCmdNoTimeout = $proxyCmdBase + ("/commit:apphost")
  & $appcmd @proxyCmdNoTimeout
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to enable ARR proxy settings in IIS."
  }
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
