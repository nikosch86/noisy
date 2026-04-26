PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip

.PHONY: help install lock hooks test coverage lint format clean

help:
	@echo "Targets:"
	@echo "  install   Install runtime + dev dependencies (editable)"
	@echo "  lock      Regenerate requirements.lock from pyproject.toml"
	@echo "  hooks     Install the pre-commit git hooks"
	@echo "  test      Run the unit test suite"
	@echo "  coverage  Run tests with coverage report (fails under 85%)"
	@echo "  lint      Run ruff (check + format --check)"
	@echo "  format    Apply ruff format"
	@echo "  clean     Remove caches and coverage artifacts"

install:
	$(PIP) install -e ".[dev]"

lock:
	$(PYTHON) -m piptools compile --no-emit-index-url --no-emit-trusted-host \
	  --output-file=requirements.lock pyproject.toml

hooks:
	$(PYTHON) -m pre_commit install

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov=noisy --cov-report=term-missing --cov-fail-under=85

lint:
	$(PYTHON) -m ruff check noisy.py tests
	$(PYTHON) -m ruff format --check noisy.py tests

format:
	$(PYTHON) -m ruff format noisy.py tests

clean:
	rm -rf .pytest_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
