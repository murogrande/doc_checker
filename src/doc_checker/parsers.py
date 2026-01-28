"""Parsers for extracting references and links from documentation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from doc_checker.models import DocReference, ExternalLink, LocalLink


class MarkdownParser:
    """Parse markdown files and notebooks for documentation references and links.

    Scans docs directory recursively for .md and .ipynb files, extracting:
    - mkdocstrings references (::: module.Class syntax)
    - External HTTP links (markdown links + bare URLs)
    - Local file links (relative paths to .py, .md, .yml, etc.)

    Attributes:
        docs_path: Root directory to scan for documentation files.
    """

    MKDOCSTRINGS_PATTERN = re.compile(
        r"^:::?\s+([\w.]+)", re.MULTILINE
    )  # identify ::: mypackage.MyClass
    MARKDOWN_LINK_PATTERN = re.compile(
        r"\[([^\]]*)\]\((https?://[^)]+)\)"
    )  # identiy [Documentation](http://example.org/docs)
    LOCAL_LINK_PATTERN = re.compile(
        r"\[([^\]]*)\]\(([^)]+?(?:\.py|\.ipynb|\.md|\.txt|\.yml|\.yaml|\.json|\.toml))\)"
    )  # identifies [source code](../src/utils.py) and [config](./config.yml)
    # and [notebook](docs/example.ipynb) and [docs](README.md)
    BARE_URL_PATTERN = re.compile(
        r"(?<![(\[])(https?://[^\s\)>\]\"']+)"
    )  # identify check https://example.com for more info

    def __init__(self, docs_path: Path):
        """Initialize parser with docs directory path.

        Args:
            docs_path: Root directory containing documentation files.
        """
        self.docs_path = docs_path

    def find_mkdocstrings_refs(self) -> list[DocReference]:
        """Find all mkdocstrings references in markdown files.

        Scans all .md files recursively for ::: or :: syntax used by mkdocstrings
        to auto-generate API documentation (e.g., `::: mypackage.MyClass`).

        Returns:
            List of DocReference objects with reference string, file path, line number.
        """
        refs: list[DocReference] = []
        for md_file in self.docs_path.rglob("*.md"):
            refs.extend(self._parse_refs_in_file(md_file))
        return refs

    def find_external_links(self) -> list[ExternalLink]:
        """Find all external HTTP/HTTPS links in docs.

        Scans .md files and .ipynb notebooks for:
        - Markdown links: [text](https://example.com)
        - Bare URLs: https://example.com

        Deduplicates URLs that appear both as markdown link and bare URL on same
            line.

        Returns:
            List of ExternalLink objects with URL, text, file path, line number.
        """
        links: list[ExternalLink] = []
        for md_file in self.docs_path.rglob("*.md"):
            links.extend(self._parse_external_links_in_file(md_file))
        for ipynb_file in self.docs_path.rglob("*.ipynb"):
            links.extend(self._parse_links_in_notebook(ipynb_file))
        return links

    def find_local_links(self) -> list[LocalLink]:
        """Find all local file links in markdown files.

        Detects markdown links pointing to local files with extensions:
        .py, .ipynb, .md, .txt, .yml, .yaml, .json, .toml

        Returns:
            List of LocalLink objects with path, text, file path, line number.
        """
        links: list[LocalLink] = []
        for md_file in self.docs_path.rglob("*.md"):
            links.extend(self._parse_local_links_in_file(md_file))
        return links

    def _parse_refs_in_file(self, file_path: Path) -> list[DocReference]:
        """Parse mkdocstrings references in a single markdown file.

        Args:
            file_path: Path to the markdown file.

        Returns:
            List of DocReference objects found in file. Empty list on read error.
        """
        refs: list[DocReference] = []
        try:
            content = file_path.read_text()
            for line_num, line in enumerate(content.split("\n"), 1):
                match = self.MKDOCSTRINGS_PATTERN.match(line.strip())
                if match:
                    refs.append(
                        DocReference(
                            reference=match.group(1),
                            file_path=file_path,
                            line_number=line_num,
                        )
                    )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
        return refs

    def _parse_external_links_in_file(self, file_path: Path) -> list[ExternalLink]:
        """Parse external HTTP links in a single markdown file.

        Extracts both markdown-style links and bare URLs, deduplicating when
        the same URL appears in both formats on the same line.

        Args:
            file_path: Path to the markdown file.

        Returns:
            List of ExternalLink objects found in file. Empty list on read error.
        """
        links: list[ExternalLink] = []
        try:
            content = file_path.read_text()
            for line_num, line in enumerate(content.split("\n"), 1):
                # Markdown links
                for match in self.MARKDOWN_LINK_PATTERN.finditer(line):
                    text, url = match.groups()
                    links.append(
                        ExternalLink(
                            url=url, text=text, file_path=file_path, line_number=line_num
                        )
                    )
                # Bare URLs
                for match in self.BARE_URL_PATTERN.finditer(line):
                    url = match.group(0)
                    if not any(
                        link.url == url and link.line_number == line_num for link in links
                    ):
                        links.append(
                            ExternalLink(
                                url=url,
                                text="",
                                file_path=file_path,
                                line_number=line_num,
                            )
                        )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
        return links

    def _parse_links_in_notebook(self, file_path: Path) -> list[ExternalLink]:
        """Parse external HTTP links in a Jupyter notebook.

        Iterates through notebook cells, extracting links from cell source.
        Line number corresponds to cell index (1-based).

        Args:
            file_path: Path to the .ipynb file.

        Returns:
            List of ExternalLink objects found in notebook. Empty list on
                read/parse error.
        """
        links: list[ExternalLink] = []
        try:
            notebook = json.loads(file_path.read_text())
            for cell_idx, cell in enumerate(notebook.get("cells", [])):
                source = cell.get("source", [])
                if isinstance(source, list):
                    source = "".join(source)
                line_num = cell_idx + 1

                # Markdown + bare URLs
                for match in self.MARKDOWN_LINK_PATTERN.finditer(source):
                    text, url = match.groups()
                    links.append(
                        ExternalLink(
                            url=url, text=text, file_path=file_path, line_number=line_num
                        )
                    )
                for match in self.BARE_URL_PATTERN.finditer(source):
                    url = match.group(0)
                    if not any(
                        link.url == url and link.line_number == line_num for link in links
                    ):
                        links.append(
                            ExternalLink(
                                url=url,
                                text="",
                                file_path=file_path,
                                line_number=line_num,
                            )
                        )
        except Exception as e:
            print(f"Warning: Could not read notebook {file_path}: {e}")
        return links

    def _parse_local_links_in_file(self, file_path: Path) -> list[LocalLink]:
        """Parse local file links in a single markdown file.

        Filters out http:// and https:// URLs to only capture relative file paths.

        Args:
            file_path: Path to the markdown file.

        Returns:
            List of LocalLink objects found in file. Empty list on read error.
        """
        links: list[LocalLink] = []
        try:
            content = file_path.read_text()
            for line_num, line in enumerate(content.split("\n"), 1):
                for match in self.LOCAL_LINK_PATTERN.finditer(line):
                    text, path = match.groups()
                    if not path.startswith(("http://", "https://")):
                        links.append(
                            LocalLink(
                                path=path,
                                text=text,
                                file_path=file_path,
                                line_number=line_num,
                            )
                        )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
        return links


class YamlParser:
    """Parse mkdocs.yml for navigation structure validation.

    Extracts and validates file paths from the nav: section of mkdocs config,
    checking that referenced documentation files exist.

    Attributes:
        mkdocs_path: Path to mkdocs.yml config file.
        docs_path: Root directory where documentation files should exist.
    """

    def __init__(self, mkdocs_path: Path, docs_path: Path):
        """Initialize parser with mkdocs config and docs paths.

        Args:
            mkdocs_path: Path to mkdocs.yml file.
            docs_path: Root docs directory for validating nav paths.
        """
        self.mkdocs_path = mkdocs_path
        self.docs_path = docs_path

    def get_nav_files(self) -> set[str] | None:
        """Extract all file paths referenced in nav section.

        Returns:
            Set of file path strings from nav, or None if mkdocs.yml missing/no nav.
        """
        if not self.mkdocs_path.exists():
            return None
        try:
            import yaml

            config = yaml.safe_load(self.mkdocs_path.read_text())
            if "nav" not in config:
                return None

            files: set[str] = set()
            self._extract_files(config["nav"], files)
            return files
        except Exception as e:
            print(f"Warning: Could not parse {self.mkdocs_path}: {e}")
            return None

    def check_nav_paths(self) -> list[dict[str, str]]:
        """Validate all nav paths exist in docs directory.

        Returns:
            List of dicts with 'path' and 'location' keys for each broken path.
            Empty list if mkdocs.yml missing, no nav section, or all paths valid.
        """
        if not self.mkdocs_path.exists():
            return []
        try:
            import yaml

            config = yaml.safe_load(self.mkdocs_path.read_text())
            if "nav" not in config:
                return []

            broken: list[dict[str, str]] = []
            self._check_nav_item(config["nav"], broken)
            return broken
        except Exception as e:
            print(f"Warning: Could not validate {self.mkdocs_path}: {e}")
            return []

    def _extract_files(self, nav_item: Any, files: set[str]) -> None:
        """Recursively extract file paths from nested nav structure.

        Handles nav items as strings, dicts, or lists (mkdocs nav format).

        Args:
            nav_item: Nav element (str path, dict, or list of items).
            files: Set to accumulate discovered file paths (mutated in place).
        """
        if isinstance(nav_item, str):
            files.add(nav_item)
        elif isinstance(nav_item, dict):
            for value in nav_item.values():
                if isinstance(value, str):
                    files.add(value)
                elif isinstance(value, list):
                    for item in value:
                        self._extract_files(item, files)
        elif isinstance(nav_item, list):
            for item in nav_item:
                self._extract_files(item, files)

    def _check_nav_item(self, nav_item: Any, broken: list[dict[str, str]]) -> None:
        """Recursively validate nav paths exist in docs directory.

        Args:
            nav_item: Nav element (str path, dict, or list of items).
            broken: List to accumulate broken paths (mutated in place).
        """
        if isinstance(nav_item, str):
            if not (self.docs_path / nav_item).exists():
                broken.append({"path": nav_item, "location": "mkdocs.yml"})
        elif isinstance(nav_item, dict):
            for value in nav_item.values():
                if isinstance(value, str):
                    if not (self.docs_path / value).exists():
                        broken.append({"path": value, "location": "mkdocs.yml"})
                elif isinstance(value, list):
                    for item in value:
                        self._check_nav_item(item, broken)
        elif isinstance(nav_item, list):
            for item in nav_item:
                self._check_nav_item(item, broken)
