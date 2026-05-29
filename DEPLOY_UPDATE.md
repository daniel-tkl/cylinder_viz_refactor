# Deployment Update — WinSW Service + ISS Server proxy

This file documents the updated Windows deployment approach implemented in this repo.

## Summary of changes
- Added an alternative Windows Service wrapper using WinSW (Windows Service Wrapper) for environments that prefer a Service Control Manager entry.
- Added ISS Server Proxy
- Added an idempotent PowerShell installer: `scripts/create_scheduled_task.ps1`.
- `scripts/scheduler.bat` now loads optional service account creds and calls the installer.
- `scripts/start_cylinder_viz_app.bat` now explicitly activates the `.venv`, creates `logs/`, and redirects stdout/stderr to timestamped log files.

## Quick usage

1. From an elevated (Administrator) PowerShell or cmd prompt in the repo root, run:

```powershell
.\scripts\scheduler.bat
```

This will register the scheduled task `CylinderVizApp` (or recreate it if present) and start it.

Service-based supervision (WinSW) — recommended for production

For a robust production deployment it's recommended installing the app as a Windows Service using WinSW (Windows Service Wrapper). Running the Python process directly under the service provides a clean 1:1 mapping between Service Control Manager actions and the Streamlit process and prevents detached child processes from surviving service stop.

## Quick install (elevated PowerShell):

```powershell
.\scripts\install_winsw_service.ps1 -ServiceName CylinderVizAppService -DisplayName "Cylinder Viz" -Install
```

What `install_winsw_service.ps1` creates (under `scripts/winsw/`):
- `CylinderVizAppService.exe` — WinSW executable for controlling the service
- `CylinderVizAppService.xml` — WinSW configuration (executable, arguments, log path and failure policy)


## Recommended WinSW configuration
- Run the venv Python interpreter directly instead of a batch wrapper. Example XML snippet (update paths):

```xml
<service>
  <id>CylinderVizAppService</id>
  <name>Cylinder Viz Win Service</name>
  <description>Cylinder Viz Streamlit service wrapper</description>

  <executable>E:\apps\dev\cylinder_viz_refactor\.venv\Scripts\python.exe</executable>
  <arguments>-m streamlit run E:\apps\dev\cylinder_viz_refactor\streamlit_app.py --server.port 9501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false</arguments>

  <logpath>..\logs\CylinderVizAppService</logpath>
  <log mode="roll">true</log>
  <stoptimeout>15000</stoptimeout>
  <onfailure action="restart" delay="5000" />
</service>
```

## Service account and ACLs
- Create a dedicated local account (or use a domain gMSA) and grant it the minimal rights required (read/execute app files, write logs). Assign the account "Log on as a service" right via Local Security Policy or GPO.
- Prefer gMSA or a secrets vault for credentials; avoid storing plaintext passwords in the generated XML. If you must use a local account, set the account via the Services MMC (preferred) or pass `-ServiceUser`/`-ServicePassword` to the installer (be aware of plaintext risk).

## Install / update sequence (elevated)
```powershell
# generate wrapper and install
.\scripts\install_winsw_service.ps1 -ServiceName CylinderVizAppService -DisplayName "Cylinder Viz" -Install

# after editing XML manually, reinstall
Push-Location .\scripts\winsw
.\CylinderVizAppService.exe stop
.\CylinderVizAppService.exe uninstall
# edit CylinderVizAppService.xml as needed
.\CylinderVizAppService.exe install
.\CylinderVizAppService.exe start
Pop-Location
```

Or install with least privelege users
```powershell
# run elevated from repo root
.\scripts\install_winsw_service.ps1 -ServiceName CylinderVizApp -ServiceUser ".\cylvizsvc" -ServicePassword 'PlainTextPassword' -Install
```

Service management and verification

```powershell
Get-Service -Name CylinderVizAppService
Stop-Service -Name CylinderVizAppService
Start-Service -Name CylinderVizAppService
sc.exe qc CylinderVizAppService | Select-String SERVICE_START_NAME
```

## Healthchecks, logging and recovery (Next Task)

- Use `scripts/smoke_test.ps1` or an external monitor to probe `http://127.0.0.1:9501/` and restart the service if unhealthy.
- WinSW log rolling plus a scheduled cleanup job is a simple retention strategy; consider shipping logs to a central store.
- Configure Windows service failure actions (via `sc failure` or WinSW `onfailure`) to provide controlled backoff and alerting in case of repeated crashes.

Migration from Scheduled Task

- If you previously used the Scheduled Task supervisor, unregister it after confirming the WinSW service is operating to avoid duplicate supervisors:

```powershell
Unregister-ScheduledTask -TaskName "CylinderVizApp" -Confirm:$false
```

## Troubleshooting

- If `Stop-Service` does not terminate the app, ensure WinSW runs Python directly (not a batch file that spawns detached children). If necessary, add a stop helper script that force-kills the process tree during shutdown.
- Inspect WinSW logs under `scripts\winsw\..\logs\CylinderVizAppService` for startup/stop diagnostics.

Optional: Run the task under a dedicated service account

- Create a low-privilege service account (local or domain) with just the rights it needs (read/execute app folder, write logs). Prefer a managed account or gMSA when available.
- Add credentials to the `.env` file in the repo root (DO NOT commit secrets):

```
SERVICE_USER=MYDOMAIN\svc_cylviz
SERVICE_PASS=PlainTextPassword
```

 - Re-run `scripts/scheduler.bat` from an elevated prompt. The script will pass these values to `scripts/create_scheduled_task.ps1`, which will use `schtasks.exe` to register the task under that account.

## Important security notes
- Avoid storing passwords in plaintext. Alternatives:
  - Use Group Managed Service Accounts (gMSA) for domain environments.
  - Use a secrets vault (Azure Key Vault, HashiCorp Vault) and fetch credentials at provisioning.
  - Create the scheduled task manually using secure credential entry, then remove `SERVICE_*` from `.env`.
  - If running via WinSW, prefer a dedicated local user or gMSA instead of embedding passwords in the XML.
- Restrict file permissions: grant the service account only the access it needs (execute app, write logs).

## Logging and rotation
 - Logs are written to `logs/streamlit_YYYYMMDD_HHMMSS.log` and `..._err.log` by `scripts/start_cylinder_viz_app.bat`.
.\scripts\scheduler.bat

```powershell
Get-ChildItem -Path E:\apps\cylinder_viz_refactor\logs -File | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force
```

## IIS reverse proxy
- The project includes `scripts/deploy_iis_reverse_proxy.ps1` that configures ARR + URL Rewrite and creates a small site at `iis_proxy_site/` with a `web.config` rewrite rule pointing to `http://127.0.0.1:8501` by default.
- Typical usage (example from repo):

```powershell
.\scripts\deploy_iis_reverse_proxy.ps1 -SiteName CylinderVizProxyDev -PublicPort 9090 -HostHeader "" -AppRoot E:\apps\dev\cylinder_viz_refactor -StreamlitPort 9501
```

Be aware of locked IIS sections on some servers — the deploy script avoids writing locked sections like `allowedServerVariables` or `webSocket` at site level.

**Important — IIS/ARR is required for production deployments**

This application expects to run behind IIS Application Request Routing (ARR) in production. The IIS site created by `scripts/deploy_iis_reverse_proxy.ps1` provides the public-facing binding and reverse-proxies requests to the local Streamlit server on `127.0.0.1:8501`. For production you must configure IIS/ARR (and URL Rewrite); the app is not intended to be exposed directly to the public internet on Streamlit's port.

Prerequisites (server):
- Windows Server with Web-Server (IIS) role installed
- URL Rewrite module
- Application Request Routing (ARR)
- (Recommended) Web-WebSockets feature if you need WebSocket support

High-level production steps:
1. Ensure the server meets prerequisites and install URL Rewrite + ARR.
2. Copy the application repo to a stable path (e.g. `E:\apps\dev\cylinder_viz_refactor`).
3. On a developer or CI machine, generate a pinned `requirements.txt` using `scripts/generate_locked_requirements.ps1` and commit it. (Avoid compiling on the server when possible.)
4. From an elevated PowerShell prompt on the server, run the one-shot checklist which performs venv creation, dependency install, scheduled task registration, IIS configuration, firewall opening, and a smoke test:

```powershell
.\scripts\deploy_checklist.ps1 -CreateVenv -InstallDeps -RegisterTask -RunIIS -InstallWebSockets -OpenFirewall -SmokeTest
```

5. Alternatively run the IIS deploy and task registration steps individually:
  - Configure ARR + site binding:

```powershell
.\scripts\deploy_iis_reverse_proxy.ps1 -SiteName CylinderVizProxy -PublicPort 8080 -AppRoot E:\apps\dev\cylinder_viz_refactor -StreamlitPort 8501
```

  - Register supervised Scheduled Task to run the app at startup:

```powershell
.\scripts\scheduler.bat
```

  - `scripts/scheduler.bat` reads optional `SERVICE_USER` and `SERVICE_PASS` from `.env` and calls `scripts/create_scheduled_task.ps1` to register the `CylinderVizApp` task. Use a managed account or vault when possible.

6. Verify:
- Check site: `appcmd list site /name:CylinderVizProxy`
- Check proxy config: `appcmd list config -section:system.webServer/proxy`
- Check scheduled task: `schtasks /Query /TN "CylinderVizApp" /V /FO LIST` or in PowerShell `Get-ScheduledTask -TaskName CylinderVizApp`
- Smoke test: `.\scripts\smoke_test.ps1` (verifies 8080 and 8501 respond with HTTP 200)

**Security notes**
- Do not expose the Streamlit port directly; always use the IIS reverse proxy with network-level protections and TLS.
- Prefer gMSA or secret vaults over `SERVICE_PASS` in `.env`.
- Restrict ACLs on code and `logs/` directories and run the scheduled task with least privilege.

**ARR options**
- `-RequestTimeout` — sets ARR proxy `requestTimeout` value when enabling the proxy (format `hh:mm:ss`). Default: `00:10:00` (10 minutes). Use this to avoid ARR closing long-running requests.
- `-InstallWebSockets` — optional switch that installs the server-level WebSocket feature (`Web-WebSockets`) before enabling ARR. This avoids writing site-level `<webSocket>` sections which may be locked.

Examples:

```powershell
# Configure ARR proxy with a 10 minute request timeout (default)
.\scripts\deploy_iis_reverse_proxy.ps1 -SiteName CylinderVizProxy -PublicPort 8080 -AppRoot E:\apps\dev\cylinder_viz_refactor -StreamlitPort 8501 -RequestTimeout "00:10:00"

# Ensure WebSocket feature is installed and configure ARR
.\scripts\deploy_iis_reverse_proxy.ps1 -InstallWebSockets -SiteName CylinderVizProxy -PublicPort 8080 -AppRoot E:\apps\dev\cylinder_viz_refactor -StreamlitPort 8501
```

Streamlit runtime flags
- `scripts/start_cylinder_viz_app.bat` launches Streamlit with these flags (adjust as needed):

```
--server.port 8501
--server.address 127.0.0.1
--server.headless true
--browser.gatherUsageStats false
--server.enableCORS false
--server.enableXsrfProtection false
```

**Notes on CORS / XSRF flags (Next Task)**
- These are disabled to accommodate reverse-proxy behavior; ensure network-level access controls and TLS are in place before disabling protections in production.
**
Healthchecks and monitoring (Next Task)**
- Add a lightweight healthcheck (HTTP probe) to ensure Streamlit responds; configure ARR or an external monitor to call the endpoint and alert / restart the service if unhealthy.

**Reproducible environment**
- Use a pinned `requirements.txt` or a lockfile (pip-tools/Poetry) to ensure consistent installs between deployments.
- Consider packaging the app into a Docker image if your infrastructure supports it — simplifies CI/CD and reproducibility.

**Manual operations and troubleshooting**
- To unregister a task and start fresh:

```powershell
schtasks /Delete /TN "CylinderVizApp" /F
.\scripts\scheduler.bat
```

- To view logs on the server: inspect `logs/` in the app root.
- To inspect the task: `schtasks /Query /TN "CylinderVizApp" /V /FO LIST`

Contact / Notes
- Deployment scripts are under `scripts/`. Review `scripts/create_scheduled_task.ps1`, `scripts/start_cylinder_viz_app.bat`, and `scripts/deploy_iis_reverse_proxy.ps1` for implementation details.

## Updates In This Repo
- **New scripts:**
  - `scripts/create_scheduled_task.ps1` — idempotent Scheduled Task installer (supports optional service account).
  - `scripts/generate_locked_requirements.ps1` — helper to run `pip-compile` locally.
  - `scripts/deploy_checklist.ps1` — one-shot deploy checklist that performs venv creation, dependency install, task registration, IIS deploy, firewall open, and smoke test.
- **Updated scripts:** `scripts/scheduler.bat` (forwards service-user flags), `scripts/start_cylinder_viz_app.bat` (activates `.venv` and logs stdout/stderr), `scripts/deploy_iis_reverse_proxy.ps1` (adds `-RequestTimeout` and `-InstallWebSockets`).
- **Config/CI:** `requirements.in` added and `.github/workflows/ci.yml` validates building a pinned `requirements.txt` and runs tests.
- **Example env:** `.env.example` added (no secrets).

**One-shot deploy (recommended for initial provisioning)**
Run from an elevated PowerShell prompt in the repo root:

```powershell
# create venv, install deps, register task, configure IIS, open firewall, smoke test
.\scripts\deploy_checklist.ps1 -CreateVenv -InstallDeps -RegisterTask -RunIIS -InstallWebSockets -OpenFirewall -SmokeTest
```

## Local Quick Start — get the app running on localhost:8501
1. (Developer machine) Create and activate the virtual environment, then install pinned requirements if you prefer doing the steps manually instead of the checklist:

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the app directly (temporary/manual run):

```powershell
.\scripts\start_cylinder_viz_app.bat
```

 - `scripts/start_cylinder_viz_app.bat`: activates `.venv`, creates `logs/`, launches Streamlit on port 8501 and redirects stdout/stderr to timestamped log files.

3. To register a supervised, restartable service using Windows Scheduled Tasks (idempotent):

```powershell
.\scripts\scheduler.bat
```

 - `scripts/scheduler.bat`: wrapper that loads optional `SERVICE_USER`/`SERVICE_PASS` from `.env` and calls `scripts/create_scheduled_task.ps1` to register and start the `CylinderVizApp` scheduled task.

 - `scripts/create_scheduled_task.ps1`: idempotently registers a Scheduled Task that runs `scripts/start_cylinder_viz_app.bat` at system startup and configures restart behavior. Use when you want the app supervised across reboots.

4. (Optional) Configure IIS reverse-proxy so the app is reachable on a public port (example binds to 8080):

```powershell
.\scripts\deploy_iis_reverse_proxy.ps1 -SiteName CylinderVizProxy -PublicPort 8080 -AppRoot E:\apps\dev\cylinder_viz_refactor -StreamlitPort 8501
```

 - `scripts/deploy_iis_reverse_proxy.ps1`: enables ARR reverse-proxy, writes a small `iis_proxy_site/web.config` rewrite rule pointing to `http://127.0.0.1:8501`, and creates/starts an IIS site bound to the specified port.

5. Quick smoke test (verifies HTTP 200 on common ports):

```powershell
.\scripts\smoke_test.ps1
```

 - `scripts/smoke_test.ps1`: lightweight check that verifies HTTP responses on ports 8080 and 8501 and prints status codes.


**Generate pinned requirements (dev machine)**
Prefer generating and committing `requirements.txt` from a developer machine or CI rather than compiling on the server:

```powershell
.\scripts\generate_locked_requirements.ps1
git add requirements.txt && git commit -m "Add pinned requirements"
```

**Security reminders**
- Do NOT store `SERVICE_PASS` in repository. Prefer gMSA or a secrets vault for credentials.
- Limit service-account privileges to the minimal required set (read/execute app, write logs). Tighten ACLs on `logs/` and app directories.

**Warnings & Migration Checklist**

When switching from the Scheduled Task supervisor to the WinSW service, follow these concrete steps to avoid duplicate supervisors, orphaned processes, and credential exposure.

1) Stop and unregister any Scheduled Task supervisor before installing the WinSW service

```powershell
if (Get-ScheduledTask -TaskName 'CylinderVizApp' -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName 'CylinderVizApp' -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName 'CylinderVizApp' -Confirm:$false
}
```

2) Ensure the app `venv` and requirements are present on the host

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Create and prepare a least-privileged service account (or use gMSA)

```powershell
$pwd = Read-Host -AsSecureString "Password for cylvizsvc"
New-LocalUser -Name "cylvizsvc" -Password $pwd -Description "CylinderViz service account"
Add-LocalGroupMember -Group "Users" -Member "cylvizsvc"
icacls "E:\apps\dev\cylinder_viz_refactor" /grant "cylvizsvc:(OI)(CI)M"
```

4) Grant the account "Log on as a service" (GUI recommended)

GUI: `secpol.msc` → Local Policies → User Rights Assignment → "Log on as a service" → Add `cylvizsvc`.

Optional automated (if `ntrights.exe` is available):

```powershell
& ntrights.exe +r SeServiceLogonRight -u cylvizsvc
```

5) Generate and install the WinSW wrapper (elevated)

```powershell
.\scripts\install_winsw_service.ps1 -ServiceName CylinderVizAppService -ServiceUser "cylvizsvc" -ServicePassword '<secure-password>' -Install
```

6) Verify service and ports

```powershell
Get-Service -Name CylinderVizAppService
Get-NetTCPConnection -LocalPort 9501 | Select LocalAddress,LocalPort,State,OwningProcess
Invoke-WebRequest http://localhost:8080 -UseBasicParsing -TimeoutSec 5
```

7) Rollback (if needed): uninstall the WinSW service and re-register the Scheduled Task

```powershell
Push-Location .\scripts\winsw
.\CylinderVizAppService.exe stop
.\CylinderVizAppService.exe uninstall
Pop-Location
.\scripts\scheduler.bat
```

Important cautions:
- Do not run both the Scheduled Task and the WinSW service at the same time — pick one supervisor.
- Avoid storing plaintext passwords in `.env` or XML files in the repo. Use interactive setup, gMSA, or a secrets vault.
- After installation, test `Stop-Service` and confirm that `127.0.0.1:9501` stops listening.

## Next recommended improvements
- Replace plaintext credentials with gMSA or secret vault.
- Add an automated post-deploy smoke test that verifies the endpoint returns expected content.
- Add log rotation task and restrict log directory ACLs.
- Optionally add a healthcheck script that restarts the scheduled task if the app is unresponsive.
