# QA Automation for Streamlit App

This folder contains automated QA smoke scripts for the Streamlit app.

## What it checks
- Starts `streamlit_app.py` in headless mode.
- Waits for Streamlit health endpoint (`/_stcore/health`) to return `ok`.
- Verifies root page `/` is reachable.
- Stops the app process and exits with pass/fail code.

## Run from PowerShell

```powershell
qa_automation/run_qa.ps1
```

Optional parameters:

```powershell
qa_automation/run_qa.ps1 -Port 8512 -TimeoutSec 120
```

## Run Python script directly

```powershell
python qa_automation/streamlit_qa_smoke.py --port 8510 --timeout 90
```

## Exit codes
- `0`: pass
- `1`: smoke check failed (app not healthy before timeout)
- `2`: app entry file missing
