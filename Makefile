.PHONY: help install dev-install clean lint format test test-cov run-backend run-frontend run pre-commit-install pre-commit-run

# Default target - show help
help:
	@echo "LLM Council - Available Make Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install           Install production dependencies"
	@echo "  make dev-install       Install dev dependencies (includes testing, linting)"
	@echo "  make pre-commit-install Install pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              Run ruff linter (check only)"
	@echo "  make lint-fix          Run ruff linter with auto-fix"
	@echo "  make lint-unsafe       Run ruff with unsafe auto-fixes"
	@echo "  make format            Run ruff formatter"
	@echo "  make format-check      Check formatting without changes"
	@echo "  make pre-commit-run    Run all pre-commit hooks manually"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run pytest tests"
	@echo "  make test-cov          Run tests with coverage report"
	@echo ""
	@echo "Development:"
	@echo "  make run-backend       Start FastAPI backend server"
	@echo "  make run-frontend      Start Vite frontend dev server"
	@echo "  make run               Run both backend and frontend (parallel)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             Remove cache files and build artifacts"

# Installation
install:
	uv sync

dev-install:
	uv sync --extra dev
	@echo "✓ Dev dependencies installed. Run 'make pre-commit-install' to set up hooks."

pre-commit-install:
	uv pip install pre-commit
	pre-commit install
	@echo "✓ Pre-commit hooks installed"

# Code Quality
lint:
	@echo "Running ruff linter..."
	uv run ruff check .

lint-fix:
	@echo "Running ruff linter with auto-fix..."
	uv run ruff check --fix .

lint-unsafe:
	@echo "Running ruff linter with unsafe auto-fixes..."
	uv run ruff check --fix --unsafe-fixes .

format:
	@echo "Running ruff formatter..."
	uv run ruff format .

format-check:
	@echo "Checking code formatting..."
	uv run ruff format --check .

pre-commit-run:
	@echo "Running all pre-commit hooks..."
	pre-commit run --all-files

# Testing
test:
	@echo "Running tests..."
	uv run python -m pytest

test-cov:
	@echo "Running tests with coverage..."
	uv run python -m pytest --cov=backend --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# Development servers
run-backend:
	@echo "Starting FastAPI backend on http://localhost:8001"
	uv run python -m backend.main

run-frontend:
	@echo "Starting Vite frontend on http://localhost:5173"
	cd frontend && pnpm run dev

run:
	@echo "Starting both backend and frontend..."
	@echo "Backend: http://localhost:8001"
	@echo "Frontend: http://localhost:5173"
	@echo "Press Ctrl+C to stop both servers"
	@trap 'kill 0' SIGINT; \
	(uv run python -m backend.main) & \
	(cd frontend && pnpm run dev) & \
	wait

# Cleanup
clean:
	@echo "Cleaning up cache and build files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf build dist htmlcov .coverage
	@echo "✓ Cleanup complete"
