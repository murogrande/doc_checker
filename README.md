# doc_checker

Check documentation drift: broken links, undocumented APIs, invalid references

## Features

- **API Coverage**: Ensure all public APIs documented
- **Reference Validation**: Check mkdocstrings references point to valid code
- **Link Checking**: Verify external HTTP links (async)
- **Local Links**: Validate file paths in markdown
- **Parameter Docs**: Check function parameters documented
- **mkdocs.yml Validation**: Verify nav paths exist

## Installation

```bash
pip install -e .
# Optional: async link checking (recommended)
pip install -e ".[async]"
```

## Usage

```bash
# Check everything (except slow external links)
doc-checker --root /path/to/project

# Check all including external links
doc-checker --check-all --root /path/to/project

# Just API coverage
doc-checker --check-signatures --root /path/to/project

# Just external links
doc-checker --check-external-links --root /path/to/project

# Verbose + JSON output
doc-checker --check-all --verbose --json --root /path/to/project

# Custom modules
doc-checker --modules my_module other_module --root /path/to/project
```

## Architecture

**~500 lines, 6 focused modules:**

- `models.py` - Dataclasses only
- `parsers.py` - Extract refs/links from markdown/yaml
- `code_analyzer.py` - Extract API signatures via introspection
- `link_checker.py` - Async HTTP validation (aiohttp or urllib fallback)
- `checkers.py` - Drift detection logic
- `formatters.py` - Report rendering
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
