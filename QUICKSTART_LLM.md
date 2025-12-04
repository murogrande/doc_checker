# LLM Quality Checks - Quick Start Guide

## For 4GB GPU Users

### 1. Install Ollama

```bash
# Linux/Mac
curl -fsSL https://ollama.ai/install.sh | sh

# Start service
ollama serve
```

### 2. Pull Model (Choose One)

**Recommended for 4GB GPU:**

```bash
# Best quality (2GB VRAM)
ollama pull qwen2.5:3b

# Fastest (1.5GB VRAM)
ollama pull gemma2:2b

# Alternative (2.5GB VRAM)
ollama pull phi3.5
```

### 3. Install doc-checker with LLM Support

```bash
cd /path/to/doc_checker
pip install -e ".[llm]"
```

### 4. Run Quality Checks

```bash
# Basic check (uses qwen2.5:3b by default)
doc-checker --check-quality --root /path/to/project

# With verbose output
doc-checker --check-quality --verbose --root /path/to/project

# Check only 10% of APIs (faster for testing)
doc-checker --check-quality --quality-sample 0.1 --verbose --root .

# Use faster model
doc-checker --check-quality --llm-model gemma2:2b --root .

# Combine with other checks
doc-checker --check-all --check-quality --root .
```

### 5. Verify GPU Usage

```bash
# While doc-checker is running, open another terminal:
nvidia-smi

# Should show ollama process using GPU
```

## Model Comparison

| Model | VRAM | Speed | Quality | Command |
|-------|------|-------|---------|---------|
| **qwen2.5:3b** | 2GB | Fast | ⭐⭐⭐⭐⭐ | `--llm-model qwen2.5:3b` (default) |
| gemma2:2b | 1.5GB | Very Fast | ⭐⭐⭐ | `--llm-model gemma2:2b` |
| phi3.5 | 2.5GB | Fast | ⭐⭐⭐⭐ | `--llm-model phi3.5` |
| llama3.2:3b | 2GB | Fast | ⭐⭐⭐⭐ | `--llm-model llama3.2:3b` |

## Example Output

```
Running documentation drift detection...
Running LLM quality checks (backend: ollama)...
Checking 15 APIs in emu_mps...
  Checking emu_mps.MPS.evolve...
    Found 2 issues (score: 75)
  Checking emu_mps.MPS.canonical_form...
    Found 0 issues (score: 95)
...

============================================================
DOCUMENTATION DRIFT REPORT
============================================================

Quality issues (3):

  ✘ CRITICAL (1):
    emu_mps.MPS.evolve [params]
      Issue: Parameter 'dt' is not documented
      Fix: Add: 'dt (float): Time step in nanoseconds. Default: 10'

  ⚠ WARNING (1):
    emu_mps.MPS.__init__ [clarity]
      Issue: Passive voice makes it unclear who performs the action
      Fix: Change 'The state is evolved' to 'This method evolves the state'
      Text: The state is evolved

  ℹ SUGGESTION (1):
    emu_mps.MPS.truncate [completeness]
      Issue: Missing example showing basic usage
      Fix: Add: 'Example:\n    >>> mps.truncate(precision=1e-5)'

============================================================
```

## Using OpenAI Instead

If you prefer OpenAI (requires API key):

```bash
# Set API key
export OPENAI_API_KEY='sk-proj-...'

# Run with OpenAI
doc-checker --check-quality --llm-backend openai --root .

# Use specific model
doc-checker --check-quality --llm-backend openai --llm-model gpt-4o --root .
```

## Troubleshooting

### "Ollama service not running"
```bash
ollama serve
# Wait 2 seconds, then retry doc-checker
```

### "Model not found"
```bash
ollama list  # Check installed models
ollama pull qwen2.5:3b  # Install model
```

### Out of Memory Error
```bash
# Use smaller model
doc-checker --check-quality --llm-model gemma2:2b --root .

# Or check fewer APIs
doc-checker --check-quality --quality-sample 0.2 --root .
```

### GPU Not Used (CPU fallback)
```bash
# Check CUDA available
nvidia-smi

# Restart ollama
pkill ollama
ollama serve
```

## Security Note

- Ollama runs **locally** - no data sent to external servers
- OpenAI sends docstrings to API - set `OPENAI_API_KEY` env var (never in code)
- API keys stored securely via environment variables only

## Next Steps

1. Run on small sample: `--quality-sample 0.1`
2. Review output, adjust if needed
3. Run on full codebase
4. Integrate into CI/CD (GitHub Actions example in CLAUDE.md)
