# Convenience targets. `PY` and `WIKI` can be overridden, e.g. `make lint WIKI=wiki`.
PY ?= PYTHONPATH=src python3 -m llmwiki.cli
WIKI ?= wiki

.PHONY: help install install-dev test lint validate index search stats mcp clean

help:
	@echo "make install       - install the package (editable)"
	@echo "make install-dev   - install with dev extras (pytest, PyYAML)"
	@echo "make test          - run the test suite"
	@echo "make lint          - lint-validate the wiki (strict)"
	@echo "make index         - (re)build the search index"
	@echo "make stats         - show wiki health metrics"
	@echo "make search Q=...  - search the wiki"
	@echo "make mcp           - run the MCP server over stdio"
	@echo "make clean         - remove the generated index and caches"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	python3 -m pytest

# Wiki operations
lint validate:
	$(PY) --root $(WIKI) lint --strict

index:
	$(PY) --root $(WIKI) index

stats:
	$(PY) --root $(WIKI) stats

search:
	$(PY) --root $(WIKI) search "$(Q)" --expand

mcp:
	LLMWIKI_ROOT=$(WIKI) PYTHONPATH=src python3 -m llmwiki.mcp_server

clean:
	rm -rf $(WIKI)/.llmwiki .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
