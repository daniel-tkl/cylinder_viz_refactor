# Build a single-file Windows executable for the Streamlit app using PyInstaller.
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[i] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[✓] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }

# Move to repo root
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $RepoRoot
Write-Info "Repo root: $RepoRoot"

if ($Clean) {
  Write-Info "Cleaning build artifacts..."
  Remove-Item -ErrorAction SilentlyContinue -Recurse -Force dist, build, *.spec
}

# Ensure dependencies
Write-Info "Installing build dependencies (pyinstaller) into current environment..."
python -m pip install --upgrade pip > $null
python -m pip install pyinstaller > $null

# Compose PyInstaller args
$name = "CylinderViz"
$entry = "scripts/app_launcher.py"


$pyinstallerOpts = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--name", $name,
  "--add-data", "streamlit_app.py;.",
  "--add-data", ".streamlit\\config.toml;.streamlit/",
  "--add-data", "assets;.",
  "--collect-all", "streamlit",
  "--collect-all", "plotly",
  "--paths", "src",
  "--hidden-import", "src.cylinder_domain.aggregation",
  "--hidden-import", "src.cylinder_domain.parsing",
  "--hidden-import", "src.cylinder_domain.visualization",
  "--hidden-import", "src.shared.view",
  $entry
)

# Optional splash image shown while the onefile app unpacks/starts
if (Test-Path "assets/splash.png") {
  Write-Info "Using splash image: assets/splash.png"
  $pyinstallerOpts = @("--splash", "assets/splash.png") + $pyinstallerOpts
} else {
  Write-Warn "No splash image found at assets/splash.png; skipping --splash"
}

Write-Info "Running PyInstaller..."
pyinstaller @pyinstallerOpts

if (Test-Path "dist/$name.exe") {
  Write-Ok "Build complete: dist/$name.exe"
  Write-Info "Double-click the EXE or run: dist/$name.exe"
} else {
  Write-Warn "Build did not produce expected EXE. Check PyInstaller output."
}
