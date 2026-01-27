"""Prompt templates for LLM quality checks."""

# ruff: noqa: E501
# Prompts contain long lines for readability

from __future__ import annotations


def get_english_quality_prompt(docstring: str, api_name: str) -> str:
    """Prompt for English quality check (grammar, clarity, style).

    Args:
        docstring: The docstring to check
        api_name: Full API name (e.g., "emu_mps.MPS.evolve")

    Returns:
        Formatted prompt
    """
    return f"""Think longer. You are a technical documentation reviewer for a Python quantum computing library with 15 years of experience.  # noqa: E501

Task: Review the English quality of this docstring for `{api_name}`.

Check for:
1. Grammar and spelling errors
2. Unclear or ambiguous phrasing
3. Passive voice (prefer active)
4. Missing articles (a, an, the)
5. Run-on sentences
6. Technical writing best practices

Docstring:
```
{docstring}
```

IMPORTANT: Use simple, clear language in your feedback. Always provide concrete examples.

Respond ONLY with valid JSON (no markdown):
{{
  "issues": [
    {{
      "severity": "critical|warning|suggestion",
      "category": "grammar|spelling|clarity|style",
      "message": "Simple explanation of the issue",
      "suggestion": "Clear fix with before/after example",
      "line_reference": "exact text with issue"
    }}
  ],
  "score": 0-100,
  "summary": "One sentence assessment"
}}

Example issue format:
{{
  "message": "Passive voice makes it unclear who performs the action",
  "suggestion": "Change 'The state is evolved' to 'This method evolves the state'",
  "line_reference": "The state is evolved"
}}

Score guide: 90-100 excellent, 70-89 good, 50-69 needs improvement, <50 poor"""


def get_code_alignment_prompt(
    signature: str, docstring: str, api_name: str, code_snippet: str | None = None
) -> str:
    """Prompt for code-doc alignment check.

    Args:
        signature: Function signature (e.g., "def foo(x: int, y: str = 'default') -> bool")
        docstring: The docstring
        api_name: Full API name
        code_snippet: Optional code body (first ~20 lines)

    Returns:
        Formatted prompt
    """
    code_section = ""
    if code_snippet:
        code_section = f"""
Code implementation (excerpt):
```python
{code_snippet}
```
"""

    return f"""Think longer. You are a code reviewer for a Python quantum computing library with 15 years of experience.

Task: Check if the docstring accurately describes what the code does for `{api_name}`.

Signature:
```python
{signature}
```

Docstring:
```
{docstring}
```
{code_section}

Check for:
1. Parameter descriptions match signature
2. Return value description matches return type
3. Docstring describes what code actually does
4. Missing or incorrectly documented exceptions
5. Type hints vs docstring type descriptions

IMPORTANT: Explain mismatches in simple terms with specific examples.

Respond ONLY with valid JSON (no markdown):
{{
  "issues": [
    {{
      "severity": "critical|warning|suggestion",
      "category": "params|returns|exceptions|description|types",
      "message": "Simple explanation of mismatch",
      "suggestion": "Show exactly what to change with example",
      "line_reference": "specific problematic text"
    }}
  ],
  "score": 0-100,
  "summary": "One sentence assessment"
}}

Example issue format:
{{
  "message": "Parameter 'chi' is in signature but not documented",
  "suggestion": "Add to docstring: 'chi (int): Maximum bond dimension for MPS truncation'",
  "line_reference": null
}}

Score guide: 90-100 accurate, 70-89 minor issues, 50-69 needs work, <50 misleading"""


def get_completeness_prompt(
    signature: str, docstring: str, api_name: str, is_public: bool = True
) -> str:
    """Prompt for completeness check.

    Args:
        signature: Function signature
        docstring: The docstring
        api_name: Full API name
        is_public: Whether this is public API

    Returns:
        Formatted prompt
    """
    public_note = ""
    if is_public:
        public_note = "\nNote: This is PUBLIC API - users depend on complete docs."

    return f"""Think longer. You are a documentation auditor for a Python quantum computing library with 15 years of experience.

Task: Check completeness of documentation for `{api_name}`.{public_note}

Signature:
```python
{signature}
```

Docstring:
```
{docstring}
```

Check for:
1. All parameters documented (including optional ones)
2. Return value documented
3. Examples provided when helpful
4. Edge cases / special values documented
5. Raised exceptions documented
6. Links to related functions when relevant

IMPORTANT: Be specific about what's missing and give examples of what to add.

Respond ONLY with valid JSON (no markdown):
{{
  "issues": [
    {{
      "severity": "critical|warning|suggestion",
      "category": "missing_param|missing_return|missing_example|missing_exceptions|missing_notes",
      "message": "What's missing in simple terms",
      "suggestion": "Example of what to add",
      "line_reference": "where to add it or null"
    }}
  ],
  "score": 0-100,
  "summary": "One sentence assessment"
}}

Example issue format:
{{
  "message": "Missing example showing basic usage",
  "suggestion": "Add: 'Example:\\n    >>> mps = MPS([2, 2, 2])\\n    >>> result = mps.evolve(hamiltonian, dt=10)'",
  "line_reference": null
}}

Score guide: 90-100 comprehensive, 70-89 adequate, 50-69 incomplete, <50 severely lacking"""


def get_combined_quality_prompt(
    signature: str, docstring: str, api_name: str, code_snippet: str | None = None
) -> str:
    """Combined prompt for all quality checks (faster, single LLM call).

    Args:
        signature: Function signature
        docstring: The docstring
        api_name: Full API name
        code_snippet: Optional code body

    Returns:
        Formatted prompt
    """
    code_section = ""
    if code_snippet:
        code_section = f"""
Code implementation (excerpt):
```python
{code_snippet}
```
"""

    return f"""Think longer. You are a senior technical writer reviewing Python documentation for a quantum computing library with 15 years of experience.

Task: Comprehensive quality review of `{api_name}` documentation.

Signature:
```python
{signature}
```

Docstring:
```
{docstring}
```
{code_section}

Check ALL of:
1. **English Quality**: grammar, spelling, clarity, style
2. **Code Alignment**: docstring matches signature and implementation
3. **Completeness**: all parameters, returns, exceptions documented
4. **Technical Accuracy**: correct terminology, accurate descriptions

CRITICAL: Use simple, clear language. Provide concrete before/after examples for every issue.

Respond ONLY with valid JSON (no markdown):
{{
  "issues": [
    {{
      "severity": "critical|warning|suggestion",
      "category": "grammar|clarity|style|params|returns|exceptions|completeness|accuracy",
      "message": "Simple explanation anyone can understand",
      "suggestion": "Specific fix with before/after example",
      "line_reference": "exact problematic text or null"
    }}
  ],
  "score": 0-100,
  "summary": "One sentence overall assessment"
}}

Example issue formats:

Grammar issue:
{{
  "message": "Missing article 'the' makes sentence unclear",
  "suggestion": "Change 'Evolves state' to 'Evolves the state'",
  "line_reference": "Evolves state"
}}

Missing parameter:
{{
  "message": "Parameter 'dt' is not documented",
  "suggestion": "Add: 'dt (float): Time step in nanoseconds. Default: 10'",
  "line_reference": null
}}

Incomplete description:
{{
  "message": "Doesn't explain what MPS truncation does",
  "suggestion": "Add: 'Truncation removes small singular values to control memory, trading accuracy for performance'",
  "line_reference": "Performs MPS truncation"
}}

Severity guide:
- critical: Wrong info, missing required docs, major grammar errors
- warning: Unclear phrasing, minor inconsistencies, missing nice-to-haves
- suggestion: Style improvements, additional examples

Score guide: 90-100 excellent, 70-89 good, 50-69 needs improvement, <50 poor"""
