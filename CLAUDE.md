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
doc-checker --root /path/to/project                         # basic checks
doc-checker --check-external-links --root .                 # include HTTP links (slow)
doc-checker --check-quality --root .                        # LLM quality (ollama)
doc-checker --check-quality --llm-backend openai --root .   # LLM via openai
doc-checker --check-quality --quality-sample 0.1 --root .   # sample 10% of APIs
doc-checker --modules my_module --json --root .             # custom modules, JSON out
```

## Architecture

```
CLI → DriftDetector → {parsers, code_analyzer, link_checker, llm_checker} → DriftReport → formatters
```

**Modules (src/doc_checker/):**
- `models.py` - Dataclasses: SignatureInfo, DocReference, LocalLink, ExternalLink, QualityIssue, DriftReport
- `parsers.py` - MarkdownParser/YamlParser: extract mkdocstrings refs, links from md/notebooks/mkdocs.yml
- `code_analyzer.py` - CodeAnalyzer: introspect Python modules via importlib/inspect
- `link_checker.py` - LinkChecker: async HTTP validation (aiohttp or urllib fallback)
- `llm_backends.py` - LLMBackend ABC + OllamaBackend, OpenAIBackend
- `llm_checker.py` - QualityChecker: LLM evaluates docstrings
- `prompts.py` - LLM prompt templates
- `checkers.py` - DriftDetector: orchestrates all checks via check_all()
- `formatters.py` - format_report() renders text/JSON
- `cli.py` - argparse entry point

**Key methods:**
- `DriftDetector._check_api_coverage`: Compare get_public_apis() vs find_mkdocstrings_refs()
- `DriftDetector._is_valid_reference`: Validate mkdocstrings refs via importlib
- `DriftDetector._check_quality`: LLM quality (graceful fallback if deps missing)

**CLI defaults:**
- No flags → runs all checks including external links and quality (--check-all implied)
- Default modules: `["emu_mps", "emu_sv"]` - override with `--modules` for other projects
- OpenAI needs OPENAI_API_KEY env var
- Default LLM models: qwen2.5:3b (ollama), gpt-4o-mini (openai)

## Config

- line-length: 90 (black/ruff)
- mypy: strict, ignores ollama/openai stubs
- Python >=3.9
- pre-commit: trailing-whitespace, end-of-file-fixer, check-yaml/toml, check-merge-conflict, debug-statements, black, ruff --fix, mypy (excludes tests/), pytest -x
