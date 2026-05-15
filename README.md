# Streamlit Time Series Visualization App

A Streamlit web application for uploading, filtering, and visualizing time series machine equipment data by device, module, and item.

## Features
- Upload CSV/Excel files
- Parse measurement columns named as `Module/Item/Variant` (multi-word variants supported)
- Filter by Machine No / Device SN, Module, and Item
- Aggregate hourly data into daily summaries (max, min, average, count, range)
- Plot multiple variants per Module+Item with threshold lines
- Interactive charts (zoom, pan, tooltips)

## Setup

### 1. Create environment and install dependencies
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run the app
```powershell
streamlit run streamlit_app.py
```

## Build Windows EXE

Use the PowerShell helper to create a single-file executable for non-technical users.

```powershell
# From repo root
scripts/build_exe.ps1

# Optional: clean previous build artifacts first
scripts/build_exe.ps1 -Clean
```

Output: `dist/CylinderViz.exe`. Double-click it to launch; your default browser opens at http://localhost:8501 where users can upload their CSV/Excel.

Tip: You can also run the launcher directly without packaging for a quick check:

```powershell
python scripts/app_launcher.py
```

## Troubleshooting
- Logs: Check `%LOCALAPPDATA%/CylinderViz/logs/` for files like `cylinderviz_YYYYMMDD_HHMMSS.log`.
- Port busy: Change the port in [scripts/app_launcher.py](scripts/app_launcher.py#L63-L74) and rebuild, or stop the process using 8501.
- Antivirus: Some AV tools flag PyInstaller onefile EXEs. Code-signing and/or excluding the file may be needed in corporate environments.

## Notes
- Ensure your dataset includes an identifier (e.g., `Machine No` or `Device SN`) and a datetime column.
- Measurement columns must follow `Module/Item/Variant` naming.
- Thresholds are calculated relative to averaged daily values per variant.
