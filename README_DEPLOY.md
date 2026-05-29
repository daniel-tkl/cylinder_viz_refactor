## Goal
Deploy the Streamlit app behind IIS reverse proxy on Windows Server Core without NSSM.

## Quick Start for New Server

Run these commands in an elevated PowerShell session from the repo root.

### 1) Ensure IIS ARR + URL Rewrite are available
choco install iis-arr --ignore-dependencies -y --no-progress

### 2) Register and start Streamlit startup task
.\scheduler.bat

### 3) Configure IIS reverse proxy (LAN-friendly binding)
.\deploy_iis_reverse_proxy.ps1 -SiteName CylinderVizProxy -PublicPort 8080 -HostHeader "" -AppRoot E:\apps\cylinder_viz_refactor -StreamlitPort 8501

### 4) Open firewall for 8080
New-NetFirewallRule -DisplayName "CylinderViz-8080-In" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow

### 5) Verify locally on server
Invoke-WebRequest http://localhost:8080

### 6) Access from same network
Open in browser:
- http://<SERVER_IP>:8080

To get server IP:
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254*' -and $_.IPAddress -ne '127.0.0.1' }

Notes:
- Streamlit backend runs on 127.0.0.1:8501.
- IIS listens publicly on 8080 and reverse-proxies to Streamlit.

## Final Working State
- Streamlit runs as a Scheduled Task at startup.
- Streamlit listens on 127.0.0.1:8501.
- IIS site CylinderVizProxy reverse-proxies to Streamlit.
- Working LAN endpoint: http://10.215.34.155:8080

## Files Created or Updated
- start_cylinder_viz_app.bat
- scheduler.bat
- deploy_iis_reverse_proxy.ps1
- iis_proxy_site/web.config

## What Was Done, Error by Error

### 1) Chocolatey dependency install failed (UrlRewrite MSI 1603)
Observed error:
- UrlRewrite MSI exited with code 1603.
- Chocolatey then failed iis-arr due to dependency failure.

Investigation:
- Checked chocolatey.log and UrlRewrite MSI log.
- MSI log showed Return Value 3 and SecureRepair/source lookup problems.
- Found IIS URL Rewrite Module 2 was already installed in Windows.

Fix:
- Installed ARR while skipping already-satisfied dependency:
  choco install iis-arr --ignore-dependencies -y --no-progress

Result:
- ARR installed successfully at OS product level.

### 2) Startup script mismatch
Observed issue:
- Existing startup script referenced .env but project uses .venv.

Fix:
- Updated start_cylinder_viz_app.bat to activate .venv.
- Added explicit Streamlit runtime arguments:
  - server address 127.0.0.1
  - fixed port 8501
  - headless mode

### 3) Scheduled task robustness
Observed issue:
- Task creation script was one-shot and not idempotent.

Fix:
- Updated scheduler.bat to:
  - force update existing task (/f)
  - run the task immediately after create

### 4) PowerShell parse error in deploy script
Observed error:
- Invalid variable reference for strings like http/*:$PublicPort:

Cause:
- PowerShell interpolation edge case with colon-delimited binding strings.

Fix:
- Replaced with format strings:
  - http/*:{0}:
  - http/*:{0}:{1}

### 5) Site existence detection bug in deploy script
Observed error:
- appcmd reported site not found, but script still ran update path and printed success.

Cause:
- Site detection logic based on output/null check was unreliable.

Fix:
- Switched to appcmd exit-code based detection.
- Added strict failure checks after each appcmd command.
- Added binding conflict guard for no-host-header port usage.

### 6) Wrong appcmd command for physical path update
Observed error:
- Invalid collection index format when updating physical path.

Cause:
- set site with [path='/'] syntax was invalid in this context.

Fix:
- Changed update path operation to:
  appcmd set vdir /vdir.name:"SiteName/" /physicalPath:"..."

### 7) Host header set to placeholder value
Observed issue:
- Site bound to host header your-fqdn, so site did not match normal requests.

Fix:
- Rebound site with suitable settings.
- For LAN/IP access, used no host header on alternate port 8080.

### 8) IIS 500.52 (URL Rewrite Module Error, 0x80070021)
Observed error:
- Request returned 500.52 and pointed to allowedServerVariables block in web.config.

Cause:
- allowedServerVariables was locked at higher IIS config level.

Fix:
- Removed serverVariables and allowedServerVariables blocks from site web.config.
- Updated deploy_iis_reverse_proxy.ps1 template so future deploys do not recreate them.

### 9) Browser showed favicon and infinite reload from another machine
Observed issue:
- App shell appeared but kept reloading.

Actions:
- Verified Streamlit task and listener on 127.0.0.1:8501.
- Installed IIS WebSocket feature.
- Added reverse-proxy friendly Streamlit flags:
  - --server.enableCORS false
  - --server.enableXsrfProtection false

### 10) IIS 500.19 after WebSocket feature install
Observed error:
- 500.19 with WebSocketModule, config lock (0x80070021).

Cause:
- Site-level webSocket section in web.config was locked.

Fix:
- Removed webSocket section from site web.config.
- Removed webSocket section generation from deploy script template.

### 11) IIS service interruption during restart attempt
Observed issue:
- iisreset command failed with access/remote-style message.
- W3SVC ended up stopped.

Fix:
- Started W3SVC service.
- Started CylinderVizProxy site explicitly with appcmd.
- Verified endpoint returned HTTP 200.

## Current Known-Good Configuration
- IIS site: CylinderVizProxy
- Binding: http/*:8080:
- Proxy target: http://127.0.0.1:8501
- Firewall rule: inbound TCP 8080 allowed
- Streamlit task: CylinderVizApp (running)

## Operational Commands

### Start task manually
schtasks /run /tn "CylinderVizApp"

### Re-apply IIS proxy config
.\deploy_iis_reverse_proxy.ps1 -SiteName CylinderVizProxy -PublicPort 8080 -HostHeader "" -AppRoot E:\apps\cylinder_viz_refactor -StreamlitPort 8501

### Verify local proxy health
Invoke-WebRequest http://localhost:8080

### Verify Streamlit backend listener
Get-NetTCPConnection -LocalPort 8501 -State Listen

## Lessons Learned
- On this server, some IIS sections are locked; avoid site-level allowedServerVariables and webSocket entries.
- For LAN testing, host-header-free binding on non-conflicting port is the fastest path.
- Use appcmd exit code checks in automation, not output text/null heuristics.
- If UrlRewrite MSI fails but URL Rewrite is already installed, install ARR with dependency bypass.
