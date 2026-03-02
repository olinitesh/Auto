$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "services/shared-python"
uvicorn main:app --app-dir services/communication-service/src --host 0.0.0.0 --port 8010 --reload
