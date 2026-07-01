.PHONY: check fmt install-hooks

SOURCES := usr/lib/pifos tests

check:
	ruff format --check $(SOURCES) $(wildcard bin/*)
	ruff check $(SOURCES) $(wildcard bin/*)
	mypy --strict $(SOURCES) $(wildcard bin/*)
	pytest

fmt:
	ruff check --fix $(SOURCES) $(wildcard bin/*)
	ruff format $(SOURCES) $(wildcard bin/*)

install-hooks:
	pre-commit install
