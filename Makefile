.PHONY: run test migrate revision infra-up infra-down infra-logs worker

# Infrastructure (PostgreSQL & Redis in Docker)
infra-up:
	docker compose up -d db redis

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f db redis

# Local Application Services (via Astral uv)
run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	uv run arq app.core.worker.WorkerSettings

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(name)"
