.PHONY: install test lint validate

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -q

lint:
	ruff check .

validate: lint test
	python scripts/sync_assistant_trees.py --check
	python scripts/generate_agent_asset_inventory.py --check
	python scripts/ci/check_agent_frontmatter.py
	python scripts/ci/check_secrets.py
	python scripts/okf_lint.py --profile project --exclude-prefix archive/ docs
