param(
    [string]$Dataset = "",
    [int]$MaxSelect = 50
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    $cliParams = @("qa_automation/streamlit_qa_sidebar_toggle.py", "--max-select", "$MaxSelect")
    if ($Dataset -ne "") {
        $cliParams += @("--dataset", $Dataset)
    }

    python @cliParams
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
