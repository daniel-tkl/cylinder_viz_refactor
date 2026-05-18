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

## Sidebar Select/Deselect QA

This additional automation checks sidebar control stability by toggling each menu:
- multiselect menus: select none, then select options
- radio menus: switch to alternate option, then switch back

Run from PowerShell:

```powershell
qa_automation/run_qa_sidebar_toggle.ps1
```

Optional parameters:

```powershell
qa_automation/run_qa_sidebar_toggle.ps1 -Dataset data/your_file.csv -MaxSelect 100
```

Run Python script directly:

```powershell
python qa_automation/streamlit_qa_sidebar_toggle.py --dataset data/your_file.csv --max-select 100
```

## Exit codes
- `0`: pass
- `1`: smoke check failed (app not healthy before timeout)
- `2`: app entry file missing

Sidebar toggle script:
- `0`: pass
- `1`: one or more toggle checks failed
- `2`: app entry or dataset missing
