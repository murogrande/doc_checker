# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

doc_checker - Documentation drift detection for Python projects (~500 LOC). Detects undocumented APIs, broken mkdocstrings references, invalid HTTP/local links, mkdocs.yml nav errors, undocumented parameters.

## Common Commands

```bash
# Install
pip install -e .
pip install -e ".[dev]"

# Tests
pytest                                    # all tests
pytest tests/test_checkers.py            # specific file
pytest tests/test_checkers.py::test_name -v  # single test

# Linting
black src tests
ruff check src tests
mypy src/doc_checker
pre-commit run --all-files    # run all pre-commit hooks

# Run tool
doc-checker --root /path/to/project                    # basic checks
doc-checker --check-all --root /path/to/project        # includes external links
doc-checker --modules my_module --root /path/to/project
doc-checker --check-all --json --root .                # JSON output
```

## Architecture

**Flow:** CLI → DriftDetector → {parsers, code_analyzer, link_checker} → DriftReport → formatters

**6 modules:**
- `models.py` - Dataclasses (SignatureInfo, DocReference, ExternalLink, DriftReport)
- `parsers.py` - Extract mkdocstrings refs, links from markdown/notebooks/yaml
- `code_analyzer.py` - Introspect Python modules via importlib/inspect
- `link_checker.py` - Async HTTP validation (aiohttp, urllib fallback)
- `checkers.py` - DriftDetector orchestrates checks via check_all()
- `formatters.py` - Report rendering
- `cli.py` - argparse interface

**Key logic:**
- DriftDetector._check_api_coverage: Compare code_analyzer.get_public_apis() vs md_parser.find_mkdocstrings_refs()
- DriftDetector._is_valid_reference: Validate mkdocstrings refs via importlib
- DriftDetector.PULSER_REEXPORTS: Skip APIs re-exported from Pulser
- CLI defaults: --check-all if no flags, modules=["emu_mps", "emu_sv"], ignore_pulser_reexports=True

## Configuration

**pyproject.toml:**
- black/ruff: line-length 90
- mypy: strict mode
- Python >=3.9
- Optional dependencies: [async] for aiohttp, [dev] for testing/linting

**pre-commit hooks:**
- trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-added-large-files
- black, ruff (--fix), mypy (with types-PyYAML, aiohttp stubs)
- pytest (fast tests, excludes slow integration)

**GitHub Actions (CI):**
- lint job: black --check, ruff check, mypy
- test job: pytest with matrix (Python 3.9-3.12, with/without async extras)
- Coverage uploaded from Python 3.11 + async build
