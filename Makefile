PY := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

.PHONY: db api web worker scheduler migrate seed check backup

db:
	docker compose -f deploy/docker-compose.yml up -d postgres

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && .venv/bin/python -m app.cli seed

check:
	cd backend && .venv/bin/python -m app.cli check

backup:
	bash deploy/scripts/backup.sh

worker:
	cd backend && .venv/bin/python -m app.workers.worker

scheduler:
	cd backend && .venv/bin/python -m app.workers.scheduler

api:
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

web:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
