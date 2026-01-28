# doc_checker

Check documentation drift: broken links, undocumented APIs, invalid references

## Features

- **API Coverage**: Ensure all public APIs documented
- **Reference Validation**: Check mkdocstrings references point to valid code
- **Link Checking**: Verify external HTTP links (async)
- **Local Links**: Validate file paths in markdown
- **Parameter Docs**: Check function parameters documented
- **mkdocs.yml Validation**: Verify nav paths exist
- **LLM Quality Checks**: Evaluate docstring quality (english, code-alignment, completeness)

## Installation

```bash
pip install -e .
pip install -e ".[async]"         # async link checking (recommended)
pip install -e ".[llm]"           # LLM quality checks (ollama)
pip install -e ".[llm-openai]"    # LLM quality checks (openai)
pip install -e ".[dev]"           # all dev dependencies
```

## Usage

```bash
# All checks (basic + external links + LLM quality)
doc-checker --root /path/to/project

# Basic checks only (API coverage, references, params, local links, mkdocs)
doc-checker --check-basic --root /path/to/project

# External HTTP link validation only (slow)
doc-checker --check-external-links --root /path/to/project

# LLM quality checks
doc-checker --check-quality --root /path/to/project                    # ollama (default)
doc-checker --check-quality --llm-backend openai --root /path/to/project  # openai
doc-checker --check-quality --quality-sample 0.1 --root /path/to/project  # 10% sample

# Custom modules + JSON output
doc-checker --modules my_module --json --root /path/to/project

# Combine flags
doc-checker --check-basic --check-external-links -v --root /path/to/project
```

## Architecture

```
CLI → DriftDetector → {parsers, code_analyzer, link_checker, llm_checker} → DriftReport → formatters
```

**Modules:**
- `models.py` - Dataclasses (SignatureInfo, DocReference, DriftReport, etc.)
- `parsers.py` - MarkdownParser/YamlParser for mkdocstrings refs and links
- `code_analyzer.py` - Introspect Python modules via importlib/inspect
- `link_checker.py` - Async HTTP validation (aiohttp or urllib fallback)
- `llm_backends.py` - LLMBackend abstraction (Ollama, OpenAI)
- `llm_checker.py` - QualityChecker for LLM docstring evaluation
- `prompts.py` - LLM prompt templates
- `checkers.py` - DriftDetector orchestrates all checks
- `formatters.py` - Report rendering (text/JSON)
- `cli.py` - Command-line interface

## Example Output

```
============================================================
DOCUMENTATION DRIFT REPORT
============================================================

Missing from docs (2):
  - emu_mps.MPS.canonical_form
  - emu_sv.StateVector.measure

Broken references (1):
  - emu_mps.old_class in docs/api.md:42

Broken external links (1):
  docs/guide.md:15: https://broken-link.com (status: 404)

Undocumented parameters (1):
  - emu_mps.MPS.__init__: chi, precision

============================================================
```
