# gfunk task runner

default:
    @echo "Usage: just <recipe>"
    @echo ""
    @echo "  release   Interactive version bump, review, and publish"
    @echo "  test      Run the test suite"
    @echo "  lint      Run all pre-commit hooks"

release:
    uv run python scripts/release.py

test:
    uv run pytest tests/ -q

lint:
    uv run pre-commit run --all-files
