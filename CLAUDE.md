# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

doc_checker - Documentation drift detection for mkdocs projects. Detects undocumented APIs, broken mkdocstrings references, invalid HTTP/local links, mkdocs.yml nav errors, undocumented parameters, and LLM-based quality issues.

## Commands

```bash
# Install
pip install -e ".[dev]"           # all dev deps (recommended)

# Tests
pytest                            # all
pytest tests/test_checkers.py -v  # single file
pytest -v --cov=doc_checker       # coverage

# Lint
pre-commit run --all-files

# Run
doc-checker --modules my_pkg --root .                          # all checks
doc-checker --modules my_pkg --check-basic --root .            # basic only
doc-checker --modules my_pkg --check-external-links --root .   # links only
doc-checker --modules my_pkg --check-quality --root .          # LLM quality
doc-checker --modules my_pkg --ignore-submodules my_pkg.internal --root .
doc-checker --modules my_pkg --check-basic --warn-only --root .
```

## Architecture

```
CLI (cli.py) -> DriftDetector (checkers.py) -> {parsers, code_analyzer, link_checker, llm_checker} -> DriftReport (models.py) -> formatters.py
```

- `DriftDetector.check_all()` orchestrates all checks
- `CodeAnalyzer.get_all_public_apis()` discovers APIs via `pkgutil.walk_packages()`; **cached** by `(module, ignore_submodules)`
- `MarkdownParser` uses **single-pass scanning**: `_ensure_scanned()` populates refs/external/local caches in one traversal
- `LinkChecker` uses async aiohttp with urllib fallback
- `QualityChecker` lazily imported to avoid hard deps on ollama/openai

**Key behaviors:**
- No check flags -> runs all checks; `--check-basic` skips external/quality
- `--warn-only` always exits 0 (non-blocking for CI)
- Docstring links resolve relative to the md file with the `:::` directive
- Notebook links: `.md` -> `.ipynb` required; `.ipynb` -> `.ipynb` forbidden

## Tests

Tests use `tmp_path` fixtures in `conftest.py`. Each creates isolated temp project structure.

## Config

- line-length: 90 (black/ruff)
- mypy: strict, excludes tests/
- Python >=3.9
