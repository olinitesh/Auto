$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "services/shared-python"
uvicorn main:app --app-dir services/war-room-realtime/src --host 0.0.0.0 --port 8020 --reload
