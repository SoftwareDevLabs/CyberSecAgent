.PHONY: install install-tools db-migrate db-upgrade test test-unit clean

# Install Python workspace dependencies
install:
	uv sync --dev

# Install external pipeline tools (Syft, Grype, OSV-Scanner, OpenGrep) at pinned versions
install-tools:
	bash scripts/install-tools.sh

# Full setup for a new clone: Python deps + external tools + DB migration
setup: install install-tools db-upgrade

# Generate a new Alembic migration (run after changing models.py)
db-migrate:
	cd packages/pipeline && ../../.venv/bin/alembic revision --autogenerate -m "$(MSG)"

# Apply all pending migrations
db-upgrade:
	cd packages/pipeline && ../../.venv/bin/alembic upgrade head

# Run full test suite
test:
	.venv/bin/pytest tests/ -v

# Run only unit tests (no integration fixtures needed)
test-unit:
	.venv/bin/pytest tests/unit/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f cyberguard-dev.db
