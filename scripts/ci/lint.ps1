$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "services/shared-python"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
  throw "Python was not found in PATH. Install Python 3.11+ and retry."
}

python -m compileall services/shared-python services/api-gateway/src services/negotiation-orchestrator/src services/communication-service/src services/war-room-realtime/src
