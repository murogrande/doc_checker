# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

doc_checker - Documentation drift detection for Python projects. Detects undocumented APIs, broken mkdocstrings references, invalid HTTP/local links, mkdocs.yml nav errors, undocumented parameters, and LLM-based quality issues.

## Commands

```bash
# Install
pip install -e ".[dev]"           # all dev deps (recommended)
pip install -e ".[async]"         # async link checking only
pip install -e ".[llm]"           # ollama quality checks
pip install -e ".[llm-openai]"    # openai quality checks

# Tests
pytest                                            # all
pytest tests/test_checkers.py::test_name -v       # single
pytest -v --cov=doc_checker --cov-report=term-missing  # coverage

# Lint
pre-commit run --all-files        # all hooks
mypy src/doc_checker              # type check only

# Run
doc-checker --root /path/to/project                         # all checks (default)
doc-checker --check-basic --root .                          # basic checks only
doc-checker --check-external-links --root .                 # external links only
doc-checker --check-quality --root .                        # LLM quality (ollama)
doc-checker --check-quality --llm-backend openai --root .   # LLM via openai
doc-checker --check-quality --quality-sample 0.1 --root .   # sample 10% of APIs
doc-checker --modules my_module --json --root .             # custom modules, JSON out
doc-checker --ignore-submodules emu_mps.optimatrix --root .  # skip submodules
doc-checker --check-basic --warn-only --root .               # non-blocking (always exit 0)

# Pre-commit (from consumer repo)
pre-commit run doc-checker-basic --all-files
pre-commit run doc-checker-links --all-files
```

## Architecture

```
CLI (cli.py) → DriftDetector (checkers.py) → {parsers, code_analyzer, link_checker, llm_checker} → DriftReport (models.py) → formatters.py
```

- `DriftDetector.check_all()` is the main entry point, orchestrates all checks
- `CodeAnalyzer.get_all_public_apis()` recursively discovers sub-packages via `pkgutil.walk_packages()`, returns `(apis, unmatched_ignores)` tuple
- `MarkdownParser`/`YamlParser` extract mkdocstrings `:::` refs and links from md/notebooks/mkdocs.yml; `parse_local_links_in_text()` scans Python docstrings for local links
- `LinkChecker` uses async aiohttp with urllib fallback
- `QualityChecker` and LLM backends are lazily imported in `_check_quality()` to avoid hard deps on ollama/openai
- `LLMBackend` ABC in `llm_backends.py` with `OllamaBackend` and `OpenAIBackend` implementations

**Key design notes:**
- `PULSER_REEXPORTS` in `DriftDetector` is hardcoded (TODO: make configurable via CLI)
- No flags → `--check-all` auto-set; `--check-basic` skips external/quality; `--check-external-links`/`--check-quality` skip basic checks when used standalone
- `--warn-only` prints report but always exits 0 (non-blocking for pre-commit/CI)
- `.pre-commit-hooks.yaml` provides `doc-checker-basic` and `doc-checker-links` hooks (`language: system`, `pass_filenames: false`)
- Default target modules: `["emu_mps", "emu_sv"]` — override with `--modules`
- OpenAI backend needs `OPENAI_API_KEY` env var
- LLM defaults: qwen2.5:3b (ollama), gpt-4o-mini (openai)
- Docstring local links resolve relative to the md file containing the `:::` directive (matching mkdocstrings rendering); short-name lookup handles re-exported APIs (e.g. `:::` has `pkg.sub.Cls` but API discovered as `pkg.Cls`)
- mkdocs internal links without extension resolve to `.md` only; notebook links must include `.ipynb`

## Tests

Tests use `tmp_path`-based fixtures in `conftest.py`: `tmp_docs`, `sample_markdown`, `sample_notebook`, `sample_mkdocs_yml`. Each creates a temporary project structure for isolated testing. CI runs on Python 3.9-3.12 with and without `[async]` extras.

## Config

- line-length: 90 (black/ruff)
- mypy: strict, excludes tests/, ignores ollama/openai stubs
- Python >=3.9
- pre-commit: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, black, ruff --fix, mypy (excludes tests/)
