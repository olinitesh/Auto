.PHONY: bootstrap up test lint api worker communication warroom web

bootstrap:
	powershell -ExecutionPolicy Bypass -File scripts/dev/bootstrap.ps1

up:
	docker compose up -d

test:
	powershell -ExecutionPolicy Bypass -File scripts/ci/test.ps1

lint:
	powershell -ExecutionPolicy Bypass -File scripts/ci/lint.ps1

api:
	powershell -ExecutionPolicy Bypass -File scripts/dev/run-local.ps1

worker:
	powershell -ExecutionPolicy Bypass -File scripts/dev/run-worker.ps1

communication:
	powershell -ExecutionPolicy Bypass -File scripts/dev/run-communication.ps1

warroom:
	powershell -ExecutionPolicy Bypass -File scripts/dev/run-war-room.ps1

web:
	cd apps/web && npm install && npm run dev
