# gfunk task runner

default:
    @echo "Usage: just <recipe>"
    @echo ""
    @echo "  release   Interactive version bump, review, and publish"
    @echo "  install   Install dependencies"
    @echo "  test      Run the test suite with coverage"
    @echo "  lint      Run all pre-commit hooks"

install:
    uv sync

release:
    uv run python scripts/release.py

test:
    uv run pytest tests/ -q --cov=gfunk --cov-report=term-missing

lint:
    uv run pre-commit run --all-files
