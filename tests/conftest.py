"""Pytest fixtures for doc_checker tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_docs(tmp_path: Path) -> Path:
    """Create temporary docs directory."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return docs


@pytest.fixture
def sample_markdown(tmp_docs: Path) -> Path:
    """Create sample markdown file."""
    md_file = tmp_docs / "sample.md"
    content = """
# Sample Documentation

::: emu_mps.MPS

Another reference:
::: emu_sv.StateVector

External links:
[Pasqal](https://www.pasqal.com)
https://github.com/pasqal-io

Local link: [example](../example.py)
"""
    md_file.write_text(content)
    return md_file


@pytest.fixture
def sample_notebook(tmp_docs: Path) -> Path:
    """Create sample Jupyter notebook."""
    import json

    nb_file = tmp_docs / "sample.ipynb"
    notebook = {
        "cells": [
            {
                "source": [
                    "# Title\n",
                    "[Link](https://example.com)\n",
                ],
            }
        ],
    }
    nb_file.write_text(json.dumps(notebook))
    return nb_file


@pytest.fixture
def sample_mkdocs_yml(tmp_path: Path, tmp_docs: Path) -> Path:
    """Create sample mkdocs.yml."""
    mkdocs_file = tmp_path / "mkdocs.yml"
    content = """
site_name: Test Docs
nav:
  - Home: index.md
  - API:
    - MPS: api/mps.md
"""
    mkdocs_file.write_text(content)

    # Create referenced files
    (tmp_docs / "index.md").write_text("# Home")
    api_dir = tmp_docs / "api"
    api_dir.mkdir()
    (api_dir / "mps.md").write_text("# MPS API")

    return mkdocs_file
