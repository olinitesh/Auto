$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "services/shared-python"
python services/negotiation-orchestrator/src/worker.py
