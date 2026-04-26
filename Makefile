PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip

.PHONY: help install test coverage lint clean

help:
	@echo "Targets:"
	@echo "  install   Install runtime + dev dependencies (editable)"
	@echo "  test      Run the unit test suite"
	@echo "  coverage  Run tests with coverage report (fails under 85%)"
	@echo "  lint      Run ruff over noisy.py and tests/"
	@echo "  clean     Remove caches and coverage artifacts"

install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov=noisy --cov-report=term-missing --cov-fail-under=85

lint:
	$(PYTHON) -m ruff check noisy.py tests

clean:
	rm -rf .pytest_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
