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
```

## Architecture

```
CLI → DriftDetector → {parsers, code_analyzer, link_checker, llm_checker} → DriftReport → formatters
```

**Modules (src/doc_checker/):**
- `models.py` - Dataclasses: SignatureInfo, DocReference, LocalLink, ExternalLink, QualityIssue, DriftReport
- `parsers.py` - MarkdownParser/YamlParser: extract mkdocstrings refs, links from md/notebooks/mkdocs.yml
- `code_analyzer.py` - CodeAnalyzer: introspect Python modules via importlib/inspect. `get_all_public_apis()` recursively discovers sub-packages (not .py files) via pkgutil.walk_packages(), returns `(apis, unmatched_ignores)` tuple
- `link_checker.py` - LinkChecker: async HTTP validation (aiohttp or urllib fallback)
- `llm_backends.py` - LLMBackend ABC + OllamaBackend, OpenAIBackend
- `llm_checker.py` - QualityChecker: LLM evaluates docstrings
- `prompts.py` - LLM prompt templates
- `checkers.py` - DriftDetector: orchestrates all checks via check_all()
- `formatters.py` - format_report() renders text/JSON
- `cli.py` - argparse entry point

**Key methods:**
- `DriftDetector.check_all(skip_basic_checks=False)`: Main entry, skip_basic_checks=True for standalone external/quality checks
- `DriftDetector._check_api_coverage`: Compare get_all_public_apis() (recursive) vs find_mkdocstrings_refs()
- `DriftDetector._is_valid_reference`: Validate mkdocstrings refs via importlib
- `DriftDetector._check_quality`: LLM quality (graceful fallback if deps missing)

**CLI flags:**
- No flags → `--check-all` auto-set (basic + external + quality)
- `--check-basic` → basic checks only (API coverage, refs, params, local links, mkdocs)
- `--check-external-links` → external links only (skips basic checks)
- `--check-quality` → LLM quality only (runs basic checks too)
- `--ignore-submodules` → skip submodules by fully qualified path (e.g. `emu_mps.optimatrix`), warns if unmatched
- Default modules: `["emu_mps", "emu_sv"]` - override with `--modules`
- OpenAI needs `OPENAI_API_KEY` env var
- LLM models: qwen2.5:3b (ollama), gpt-4o-mini (openai)

## Config

- line-length: 90 (black/ruff)
- mypy: strict (excludes tests/), ignores ollama/openai stubs
- Python >=3.9
- pre-commit runs: black, ruff --fix, mypy, pytest -x
