.PHONY: dev docker-up docker-down test lint fmt install

install:
	pip install -e ".[dev]"

dev:
	python -m einvoice_mcp.server

dev-http:
	uvicorn einvoice_mcp.server:mcp --host 0.0.0.0 --port 8000

docker-up:
	docker compose -f docker/docker-compose.yml up -d --build

docker-down:
	docker compose -f docker/docker-compose.yml down

test:
	pytest --cov=einvoice_mcp --cov-report=term-missing -x -q

test-unit:
	pytest tests/unit --cov=einvoice_mcp --cov-report=term-missing -x -q

test-integration:
	pytest tests/integration -m integration --cov=einvoice_mcp -x -q

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/

fmt:
	ruff check --fix src/ tests/
	ruff format src/ tests/
