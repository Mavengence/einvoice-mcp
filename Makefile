.PHONY: dev docker-up docker-down docker-push test lint fmt install build clean type-check

install:
	pip install -e ".[dev]"

dev:
	python -m einvoice_mcp

docker-up:
	docker compose -f docker/docker-compose.yml up -d --build

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-push:
	docker compose -f docker/docker-compose.yml build
	docker tag einvoice-mcp:latest $(REGISTRY)/einvoice-mcp:$(VERSION)
	docker push $(REGISTRY)/einvoice-mcp:$(VERSION)

test:
	pytest --cov=einvoice_mcp --cov-report=term-missing --cov-fail-under=80 -x -q

test-unit:
	pytest tests/unit --cov=einvoice_mcp --cov-report=term-missing -x -q

test-integration:
	pytest tests/integration -m integration --cov=einvoice_mcp -x -q

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

fmt:
	ruff check --fix src/ tests/
	ruff format src/ tests/

build:
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf .coverage htmlcov/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

type-check:
	mypy src/ --strict
