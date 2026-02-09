# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

doc_checker - Documentation drift detection for mkdocs projects. Detects undocumented APIs, broken mkdocstrings references, invalid HTTP/local links, mkdocs.yml nav errors, undocumented parameters, and LLM-based quality issues.

## Commands

```bash
# Install
pip install -e ".[dev]"           # all dev deps (recommended)

# Tests
pytest                            # all
pytest tests/test_checkers.py -v  # single file
pytest tests/test_checkers.py::TestDriftDetector::test_name -v  # single test
pytest -v --cov=doc_checker       # coverage

# Lint
pre-commit run --all-files
mypy src/doc_checker              # type check only

# Run
doc-checker --modules my_pkg --root .                          # all checks
doc-checker --modules my_pkg --check-basic --root .            # basic only
doc-checker --modules my_pkg --check-external-links --root .   # links only
doc-checker --modules my_pkg --check-quality --root .          # LLM quality
doc-checker --modules my_pkg --ignore-submodules my_pkg.internal --root .
doc-checker --modules my_pkg --check-basic --warn-only --root .
```

## Architecture

Source lives in `src/doc_checker/`.

```
CLI (cli.py) -> DriftDetector (checkers.py) -> {parsers, code_analyzer, link_checker, llm_checker} -> DriftReport (models.py) -> formatters.py
```

- `DriftDetector.check_all()` orchestrates all checks
- `CodeAnalyzer.get_all_public_apis()` discovers APIs via `pkgutil.walk_packages()`; **cached** by `(module, ignore_submodules)` tuple
- `MarkdownParser` uses **single-pass scanning**: `_ensure_scanned()` populates refs/external/local caches in one traversal
- `LinkChecker` uses async aiohttp with urllib fallback; HEAD first, GET on 405; concurrency capped at 5
- `QualityChecker` lazily imported to avoid hard deps on ollama/openai

**Reference validation** (`_is_valid_reference`): progressively imports dotted path — tries `importlib.import_module("a.b.c")`, then `"a.b"` + `getattr(mod, "c")`, etc. Returns True on first success.

**Local link resolution** order: direct relative from file dir → `../` from docs root → absolute from project root → mkdocs URL-style with auto `.ipynb` extension.

**Key behaviors:**
- No check flags -> runs all checks; `--check-basic` skips external/quality
- `--warn-only` always exits 0 (non-blocking for CI)
- Docstring links resolve relative to the md file with the `:::` directive
- Notebook links: `.md` -> `.ipynb` required; `.ipynb` -> `.ipynb` forbidden

## Tests

Tests use `tmp_path` fixtures in `conftest.py`. Each creates isolated temp project structure with fake modules and docs.

## Config

- line-length: 90 (black/ruff)
- mypy: strict (excludes tests/, ignores ollama/openai imports)
- Python >=3.9
