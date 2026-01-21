# justfile for convenient developer workflows.
# See docs/development.md for details.
# Note GitHub Actions call uv directly, not this justfile.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Running `just` with no args runs the first recipe.
default: install lint test

install:
    uv sync --all-extras

lint:
    uv run python devtools/lint.py

test:
    uv run pytest

upgrade:
    uv sync --upgrade --all-extras --dev

build:
    uv build

clean:
    -rm -rf dist/
    -rm -rf *.egg-info/
    -rm -rf .pytest_cache/
    -rm -rf .mypy_cache/
    -rm -rf .venv/
    -find . -type d -name "__pycache__" -exec rm -rf {} +
