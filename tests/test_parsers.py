"""Tests for parsers module."""

from __future__ import annotations

from pathlib import Path

from doc_checker.parsers import MarkdownParser, YamlParser


class TestMarkdownParser:
    """Test MarkdownParser."""

    def test_find_mkdocstrings_refs(self, sample_markdown: Path, tmp_docs: Path):
        parser = MarkdownParser(tmp_docs)
        refs = parser.find_mkdocstrings_refs()

        assert len(refs) == 2
        assert refs[0].reference == "emu_mps.MPS"
        assert refs[1].reference == "emu_sv.StateVector"
        assert all(ref.file_path == sample_markdown for ref in refs)

    def test_find_external_links_markdown(self, sample_markdown: Path, tmp_docs: Path):
        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()

        urls = {link.url for link in links}
        assert "https://www.pasqal.com" in urls
        assert "https://github.com/pasqal-io" in urls
        assert len(links) == 2

    def test_find_external_links_notebook(self, sample_notebook: Path, tmp_docs: Path):
        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()

        assert len(links) == 1
        assert links[0].url == "https://example.com"
        assert links[0].file_path == sample_notebook

    def test_find_local_links(self, sample_markdown: Path, tmp_docs: Path):
        parser = MarkdownParser(tmp_docs)
        links = parser.find_local_links()

        assert len(links) == 1
        assert links[0].path == "../example.py"
        assert links[0].text == "example"

    def test_find_local_links_notebook(
        self, sample_notebook_with_local_links: Path, tmp_docs: Path
    ):
        parser = MarkdownParser(tmp_docs)
        links = parser.find_local_links()

        assert len(links) == 4
        paths = {link.path for link in links}
        assert "../advanced/algorithms.md#dmrg" in paths
        assert "./config.yml" in paths
        assert "utils.py" in paths
        assert "../../advanced/algorithms/#anchor" in paths  # mkdocs internal link
        assert all(link.file_path == sample_notebook_with_local_links for link in links)

    def test_empty_directory(self, tmp_path: Path):
        empty_docs = tmp_path / "empty_docs"
        empty_docs.mkdir()
        parser = MarkdownParser(empty_docs)

        assert parser.find_mkdocstrings_refs() == []
        assert parser.find_external_links() == []
        assert parser.find_local_links() == []


class TestYamlParser:
    """Test YamlParser."""

    def test_get_nav_files(self, sample_mkdocs_yml: Path, tmp_docs: Path):
        parser = YamlParser(sample_mkdocs_yml, tmp_docs)
        nav_files = parser.get_nav_files()

        assert nav_files is not None
        assert "index.md" in nav_files
        assert "api/mps.md" in nav_files
        assert len(nav_files) == 2

    def test_check_nav_paths_valid(self, sample_mkdocs_yml: Path, tmp_docs: Path):
        parser = YamlParser(sample_mkdocs_yml, tmp_docs)
        broken = parser.check_nav_paths()

        assert broken == []

    def test_check_nav_paths_broken(self, tmp_path: Path, tmp_docs: Path):
        mkdocs_file = tmp_path / "mkdocs.yml"
        content = """
nav:
  - Home: index.md
  - Missing: missing.md
"""
        mkdocs_file.write_text(content)
        (tmp_docs / "index.md").write_text("# Home")

        parser = YamlParser(mkdocs_file, tmp_docs)
        broken = parser.check_nav_paths()

        assert len(broken) == 1
        assert broken[0]["path"] == "missing.md"
        assert broken[0]["location"] == "mkdocs.yml"

    def test_missing_mkdocs_yml(self, tmp_path: Path, tmp_docs: Path):
        missing_file = tmp_path / "missing.yml"
        parser = YamlParser(missing_file, tmp_docs)

        assert parser.get_nav_files() is None
        assert parser.check_nav_paths() == []

    def test_nested_nav_structure(self, tmp_path: Path, tmp_docs: Path):
        mkdocs_file = tmp_path / "mkdocs.yml"
        content = """
nav:
  - Home: index.md
  - Guides:
    - Getting Started: guides/start.md
    - Advanced:
      - Topic 1: guides/advanced/topic1.md
"""
        mkdocs_file.write_text(content)

        # Create files
        (tmp_docs / "index.md").write_text("# Home")
        guides = tmp_docs / "guides"
        guides.mkdir()
        (guides / "start.md").write_text("# Start")
        advanced = guides / "advanced"
        advanced.mkdir()
        (advanced / "topic1.md").write_text("# Topic 1")

        parser = YamlParser(mkdocs_file, tmp_docs)
        nav_files = parser.get_nav_files()
        broken = parser.check_nav_paths()

        assert nav_files is not None
        assert len(nav_files) == 3
        assert "guides/start.md" in nav_files
        assert "guides/advanced/topic1.md" in nav_files
        assert broken == []


class TestParserEdgeCases:
    """Test parser error handling for malformed inputs."""

    def test_malformed_notebook_json(self, tmp_docs: Path):
        """Malformed notebook JSON returns empty list, no crash."""
        nb_file = tmp_docs / "broken.ipynb"
        nb_file.write_text("{invalid json content")

        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()
        local_links = parser.find_local_links()

        # Should gracefully return empty, not crash
        assert links == []
        assert local_links == []

    def test_notebook_missing_cells_key(self, tmp_docs: Path):
        """Notebook without cells key returns empty list."""
        nb_file = tmp_docs / "no_cells.ipynb"
        nb_file.write_text('{"metadata": {}}')

        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()
        local_links = parser.find_local_links()

        assert links == []
        assert local_links == []

    def test_notebook_empty_cells(self, tmp_docs: Path):
        """Notebook with empty cells array returns empty list."""
        nb_file = tmp_docs / "empty_cells.ipynb"
        nb_file.write_text('{"cells": []}')

        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()

        assert links == []

    def test_notebook_cell_source_as_string(self, tmp_docs: Path):
        """Notebook with source as string (not list) still parses."""
        import json

        nb_file = tmp_docs / "string_source.ipynb"
        notebook = {"cells": [{"source": "[link](https://example.com)"}]}
        nb_file.write_text(json.dumps(notebook))

        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()

        assert len(links) == 1
        assert links[0].url == "https://example.com"

    def test_markdown_file_read_error(self, tmp_docs: Path):
        """Unreadable markdown file returns empty list."""
        md_file = tmp_docs / "unreadable.md"
        md_file.write_text("# Test")
        md_file.chmod(0o000)  # Remove read permissions

        try:
            parser = MarkdownParser(tmp_docs)
            refs = parser.find_mkdocstrings_refs()
            # Should gracefully skip unreadable file
            assert not any(r.file_path == md_file for r in refs)
        finally:
            md_file.chmod(0o644)  # Restore permissions for cleanup

    def test_notebook_cell_missing_source(self, tmp_docs: Path):
        """Notebook cell without source key handled gracefully."""
        import json

        nb_file = tmp_docs / "no_source.ipynb"
        notebook = {"cells": [{"cell_type": "code"}]}
        nb_file.write_text(json.dumps(notebook))

        parser = MarkdownParser(tmp_docs)
        links = parser.find_external_links()

        assert links == []

    def test_single_colon_mkdocstrings_syntax(self, tmp_docs: Path):
        """Single colon mkdocstrings syntax (:: module.Class) is parsed."""
        md_file = tmp_docs / "single_colon.md"
        md_file.write_text(":: my_module.MyClass\n")

        parser = MarkdownParser(tmp_docs)
        refs = parser.find_mkdocstrings_refs()

        assert len(refs) == 1
        assert refs[0].reference == "my_module.MyClass"
