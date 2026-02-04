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
