.PHONY: run test migrate lint format

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(name)"
