# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

doc_checker - Documentation drift detection for Python projects (~1000 LOC). Detects undocumented APIs, broken mkdocstrings references, invalid HTTP/local links, mkdocs.yml nav errors, undocumented parameters.

## Common Commands

```bash
# Install
pip install -e .                  # base install
pip install -e ".[async]"         # with async link checking (recommended)
pip install -e ".[llm]"           # with LLM quality checks (ollama)
pip install -e ".[llm-openai]"    # with OpenAI quality checks
pip install -e ".[dev]"           # dev dependencies
pip install pytest pytest-asyncio pytest-cov  # test dependencies

# Tests
pytest                                                        # all tests
pytest tests/test_checkers.py                                 # specific file
pytest tests/test_checkers.py::test_name -v                   # single test
pytest -v --cov=doc_checker --cov-report=term-missing         # with coverage
pytest -v --cov=doc_checker --cov-report=term-missing --cov-report=xml  # CI coverage

# Linting
black src tests                   # format code
black --check src tests           # check formatting (CI)
ruff check src tests              # lint
ruff check --fix src tests        # lint with autofix
mypy src/doc_checker              # type check
pre-commit run --all-files        # run all pre-commit hooks

# Run tool
doc-checker --root /path/to/project                    # basic checks
doc-checker --check-all --root /path/to/project        # includes external links
doc-checker --modules my_module --root /path/to/project
doc-checker --check-all --json --root .                # JSON output

# LLM quality checks (new)
doc-checker --check-quality --root /path/to/project             # ollama qwen2.5:3b (default)
doc-checker --check-quality --llm-backend openai --root .       # openai (needs OPENAI_API_KEY)
doc-checker --check-quality --quality-sample 0.1 --root .       # check 10% of APIs
doc-checker --check-quality --llm-model gemma2:2b --verbose --root .  # faster model (4GB GPU)
doc-checker --check-quality --llm-model phi3.5 --verbose --root .     # alternative model
```

## Architecture

**Flow:** CLI → DriftDetector → {parsers, code_analyzer, link_checker, llm_checker} → DriftReport → formatters

**10 modules:**
- `models.py` - Dataclasses (SignatureInfo, DocReference, LocalLink, ExternalLink, QualityIssue, DriftReport)
- `parsers.py` - MarkdownParser/YamlParser extract mkdocstrings refs, links from md/notebooks/mkdocs.yml
- `code_analyzer.py` - CodeAnalyzer introspects Python modules via importlib/inspect
- `link_checker.py` - LinkChecker async HTTP validation (aiohttp if installed, else urllib fallback)
- `llm_backends.py` - LLMBackend abstraction (OllamaBackend, OpenAIBackend)
- `llm_checker.py` - QualityChecker runs LLM quality checks
- `prompts.py` - Prompt templates for LLM (english, code-alignment, completeness, combined)
- `checkers.py` - DriftDetector orchestrates all checks via check_all()
- `formatters.py` - format_report() renders as text/JSON
- `cli.py` - argparse interface

**Key logic:**
- DriftDetector._check_api_coverage: Compare code_analyzer.get_public_apis() vs md_parser.find_mkdocstrings_refs()
- DriftDetector._is_valid_reference: Validate mkdocstrings refs via importlib
- DriftDetector._check_quality: Optional LLM quality checks (graceful fallback if deps missing)
- QualityChecker.check_module_quality: LLM evaluates docstrings for english, code-alignment, completeness
- Prompts request simple language + concrete examples in LLM responses
- CLI behavior: If no check flags passed, defaults to --check-all (excludes external links + quality unless explicitly requested)
- Default modules: ["emu_mps", "emu_sv"] (Pasqal-specific; override with --modules for other projects)
- API key security: OPENAI_API_KEY env var (never in code/CLI args)

## Configuration

**pyproject.toml:**
- black/ruff: line-length 90
- mypy: strict mode
- Python >=3.9
- Optional dependencies: [async] aiohttp, [llm] ollama, [llm-openai] openai, [dev] testing/linting

**pre-commit hooks:**
- trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-added-large-files, check-merge-conflict, debug-statements
- black, ruff (--fix), mypy (with types-PyYAML, aiohttp stubs, excludes tests/)
- pytest (-v --tb=short -x: verbose, short traceback, stop at first failure)

**GitHub Actions (CI):**
- lint job: black --check, ruff check, mypy
- test job: pytest with matrix (Python 3.9-3.12, with/without async extras)
- Coverage uploaded from Python 3.11 + async build
