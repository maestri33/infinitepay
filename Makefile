.PHONY: install dev run test lint fmt clean

install:
	uv sync

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 80

test:
	uv run pytest

lint:
	uv run ruff check app/

fmt:
	uv run ruff format app/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
