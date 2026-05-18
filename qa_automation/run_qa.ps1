param(
    [int]$Port = 8510,
    [int]$TimeoutSec = 90
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    python qa_automation/streamlit_qa_smoke.py --port $Port --timeout $TimeoutSec
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
