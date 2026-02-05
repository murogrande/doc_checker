# doc_checker

Check documentation drift: broken links, undocumented APIs, invalid references.

**Requires:** Python >=3.9, mkdocs project with `mkdocs.yml` containing a `nav:` section and `docs/` directory. Works with [mkdocstrings](https://mkdocstrings.github.io/) `::: module.Class` syntax for API documentation.

## Features

- **API Coverage**: Ensure all public APIs have mkdocstrings references (recursive submodule discovery)
- **Reference Validation**: Check `::: module.Class` references resolve to valid Python objects
- **Link Checking**: Verify external HTTP links (async)
- **Local Links**: Validate file paths in markdown/notebooks and Python docstrings
- **Parameter Docs**: Check function parameters mentioned in docstrings
- **mkdocs.yml Validation**: Verify nav paths exist
- **LLM Quality Checks**: Evaluate docstring quality (english, code-alignment, completeness)

## Installation

```bash
# From GitHub
pip install git+https://github.com/murogrande/doc_checker.git

# Or clone and install
git clone https://github.com/murogrande/doc_checker.git
cd doc_checker
pip install -e .

# Optional extras
pip install -e ".[async]"         # async link checking (recommended)
pip install -e ".[llm]"           # LLM quality checks (ollama)
pip install -e ".[llm-openai]"    # LLM quality checks (openai)
pip install -e ".[dev]"           # all dev dependencies
```

## Usage

```bash
# All checks (basic + external links + LLM quality)
doc-checker --modules my_package --root /path/to/project

# Basic checks only (API coverage, references, params, local links, mkdocs)
doc-checker --modules my_package --check-basic --root /path/to/project

# External HTTP link validation only (slow)
doc-checker --modules my_package --check-external-links --root /path/to/project

# LLM quality checks (default: ollama/qwen2.5:3b, openai/gpt-4o-mini)
doc-checker --modules my_package --check-quality --root /path/to/project
doc-checker --modules my_package --check-quality --llm-backend openai --root .
doc-checker --modules my_package --check-quality --llm-model gpt-4o --root .
doc-checker --modules my_package --check-quality --quality-sample 0.1 --root .

# Multiple modules
doc-checker --modules my_package other_pkg --root /path/to/project

# Skip specific submodules (fully qualified paths)
doc-checker --modules my_package --ignore-submodules my_package.internal --root .

# JSON output
doc-checker --modules my_package --json --root /path/to/project

# Non-blocking (report issues but exit 0)
doc-checker --modules my_package --check-basic --warn-only --root /path/to/project

# Verbose
doc-checker --modules my_package --check-basic -v --root /path/to/project
```

## Pre-commit Hook

Add to your `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/murogrande/doc_checker
  rev: main  # use a tag for stable usage
  hooks:
    # Basic checks: API coverage, broken refs, params, local links, mkdocs nav
    - id: doc-checker-basic
      args: ["--modules", "my_package"]

    # External link validation (slower, runs async HTTP requests)
    - id: doc-checker-links
      args: ["--modules", "my_package"]
      verbose: true
```

Hooks use `language: system`, so `doc-checker` must be installed in your environment.

Use `--warn-only` for non-blocking checks:

```yaml
    - id: doc-checker-basic
      args: ["--modules", "my_package", "--warn-only"]
```

## Architecture

```
CLI -> DriftDetector -> {parsers, code_analyzer, link_checker, llm_checker} -> DriftReport -> formatters
```

**Modules:**
- `checkers.py` - DriftDetector orchestrates all checks
- `parsers.py` - MarkdownParser (single-pass scan, cached) / YamlParser
- `code_analyzer.py` - Introspect Python modules via importlib/inspect (cached)
- `link_checker.py` - Async HTTP validation (aiohttp or urllib fallback)
- `llm_checker.py` - QualityChecker for LLM docstring evaluation
- `models.py` - Dataclasses (SignatureInfo, DocReference, DriftReport, etc.)
- `formatters.py` - Report rendering (text/JSON)
- `cli.py` - Command-line interface

## Example Output

```
============================================================
DOCUMENTATION DRIFT REPORT
============================================================

Missing from docs (2):
  - my_package.MyClass.some_method
  - my_package.utils.helper_func

Broken references (1):
  - my_package.OldClass in docs/api.md:42

Broken local links (1):
  docs/guide.md:15: ../missing-file.md

Broken external links (1):
  docs/guide.md:20: https://example.com/broken (status: 404)

Undocumented parameters (1):
  - my_package.MyClass.__init__: timeout, retries

============================================================
```
