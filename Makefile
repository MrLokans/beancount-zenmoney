.PHONY: install test lint format format-check typecheck check build clean

install:
	uv sync --dev

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run ty check src

check: lint format-check typecheck test

build:
	uv build

clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .ruff_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
