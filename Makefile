# ParamX Hunter - Development Makefile

.PHONY: help install dev test lint format build up down logs migrate seed clean

help:
	@echo "ParamX Hunter — available commands:"
	@echo "  make install     Install backend & frontend dependencies"
	@echo "  make dev         Run backend + frontend in dev mode (separate terminals)"
	@echo "  make test        Run backend test suite"
	@echo "  make lint        Run linters (ruff, mypy, eslint)"
	@echo "  make format      Auto-format code (black, isort)"
	@echo "  make up          Start full stack via docker-compose"
	@echo "  make down        Stop docker-compose stack"
	@echo "  make logs        Tail docker-compose logs"
	@echo "  make migrate     Run Alembic migrations"
	@echo "  make seed        Seed database with admin user"
	@echo "  make benchmark   Run performance benchmarks"
	@echo "  make clean       Remove caches and build artifacts"

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install --legacy-peer-deps
	playwright install --with-deps chromium

dev-backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-worker:
	celery -A backend.workers.scan_worker.celery_app worker --loglevel=info --concurrency=4

test:
	pytest backend/tests/unit -v
	pytest backend/tests/integration -v

lint:
	ruff check backend/
	black --check backend/
	mypy backend/ --ignore-missing-imports || true
	cd frontend && npm run lint || true

format:
	ruff check --fix backend/
	black backend/
	isort backend/

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

seed:
	python -m backend.scripts.seed

benchmark:
	python -m backend.tests.benchmarks.run_benchmarks

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf frontend/dist frontend/node_modules/.vite
