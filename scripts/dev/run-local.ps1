$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "services/shared-python"
uvicorn main:app --app-dir services/api-gateway/src --host 0.0.0.0 --port 8000 --reload
