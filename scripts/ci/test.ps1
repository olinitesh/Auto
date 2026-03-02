$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "services/shared-python"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
  throw "Python was not found in PATH. Install Python 3.11+ and retry."
}

python -m pytest -q
