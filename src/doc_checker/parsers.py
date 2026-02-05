"""Parsers for extracting references and links from documentation.

Provides MarkdownParser for scanning .md/.ipynb files and YamlParser for
mkdocs.yml nav validation. Uses single-pass scanning with caching for efficiency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, cast

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

    # Regex: ::: or :: followed by dotted identifier (mkdocstrings directive)
    MKDOCSTRINGS_PATTERN = re.compile(r"^:::?\s+([\w.]+)", re.MULTILINE)
    # Regex: [text](https://...) - markdown link with http(s) URL
    MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
    # Regex: bare URL not preceded by ( or [ (avoids matching inside markdown links)
    BARE_URL_PATTERN = re.compile(r"(?<![(\[])(https?://[^\s\)>\]\"']+)")

    # Supported local file extensions for link detection
    _FILE_EXTENSIONS = r"\.py|\.ipynb|\.md|\.txt|\.yml|\.yaml|\.json|\.toml"
    # Regex: [text](path) where path ends in known extension or starts with ./ or ../
    LOCAL_LINK_PATTERN = re.compile(
        rf"\[([^\]]*)\]\(([^)]+?(?:{_FILE_EXTENSIONS})(?:#[^)]*)?|\.\.?/[^)]+)\)"
    )

    def __init__(self, docs_path: Path):
        """Initialize parser with docs directory path.

        Args:
            docs_path: Root directory containing documentation files.
        """
        self.docs_path = docs_path
        self._refs_cache: list[DocReference] | None = None
        self._external_cache: list[ExternalLink] | None = None
        self._local_cache: list[LocalLink] | None = None
        self._scanned = False

    # -------------------------------------------------------------------------
    # Public methods
    # -------------------------------------------------------------------------

    def find_mkdocstrings_refs(self) -> list[DocReference]:
        """Find all mkdocstrings references in markdown files.

        Scans all .md files recursively for ::: or :: syntax used by mkdocstrings
        to auto-generate API documentation (e.g., `::: mypackage.MyClass`).

        Returns:
            List of DocReference objects with reference string, file path, line number.
        """
        self._ensure_scanned()
        return self._refs_cache or []

    def find_external_links(self) -> list[ExternalLink]:
        """Find all external HTTP/HTTPS links in docs.

        Scans .md files and .ipynb notebooks for:
        - Markdown links: [text](https://example.com)
        - Bare URLs: https://example.com

        Deduplicates URLs that appear both as markdown link and bare URL on same line.

        Returns:
            List of ExternalLink objects with URL, text, file path, line number.
        """
        self._ensure_scanned()
        return self._external_cache or []

    def find_local_links(self) -> list[LocalLink]:
        """Find all local file links in markdown files and notebooks.

        Detects markdown links pointing to local files with extensions:
        .py, .ipynb, .md, .txt, .yml, .yaml, .json, .toml

        Returns:
            List of LocalLink objects with path, text, file path, line number.
        """
        self._ensure_scanned()
        return self._local_cache or []

    def parse_local_links_in_text(self, text: str, source_path: Path) -> list[LocalLink]:
        """Parse local file links from arbitrary text (e.g. docstrings).

        Args:
            text: Text content to scan for local links.
            source_path: Path used as file_path in returned LocalLink objects.

        Returns:
            List of LocalLink objects found in text.
        """
        links: list[LocalLink] = []
        for line_num, line in enumerate(text.split("\n"), 1):
            for match in self.LOCAL_LINK_PATTERN.finditer(line):
                link_text, path = match.groups()
                if not path.startswith(("http://", "https://")):
                    links.append(
                        LocalLink(
                            path=path,
                            text=link_text,
                            file_path=source_path,
                            line_number=line_num,
                        )
                    )
        return links

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _ensure_scanned(self) -> None:
        """Single pass through all docs, populating all caches.

        Scans .md files for refs/links/local links, and .ipynb files for
        external/local links only (notebooks don't have mkdocstrings refs).
        Called lazily on first access to any public find_* method.
        """
        if self._scanned:
            return
        self._refs_cache = []
        self._external_cache = []
        self._local_cache = []

        # Markdown files
        for md_file in self.docs_path.rglob("*.md"):
            content = self._read_file(md_file)
            if content is None:
                continue
            self._extract_from_markdown(content, md_file)

        # Notebooks
        for nb_file in self.docs_path.rglob("*.ipynb"):
            for cell_num, cell_text in self._iter_notebook_cells(nb_file):
                self._extract_external_links_to_cache(cell_text, nb_file, cell_num)
                for match in self.LOCAL_LINK_PATTERN.finditer(cell_text):
                    text, path = match.groups()
                    if not path.startswith(("http://", "https://")):
                        self._local_cache.append(
                            LocalLink(
                                path=path,
                                text=text,
                                file_path=nb_file,
                                line_number=cell_num,
                            )
                        )

        self._scanned = True

    def _extract_from_markdown(self, content: str, md_file: Path) -> None:
        """Extract refs, external links, local links from a single md file.

        Args:
            content: Full text content of the markdown file.
            md_file: Path to the source file (for location tracking).
        """
        for line_num, line in enumerate(content.split("\n"), 1):
            # mkdocstrings refs
            match = self.MKDOCSTRINGS_PATTERN.match(line.strip())
            if match:
                self._refs_cache.append(  # type: ignore[union-attr]
                    DocReference(
                        reference=match.group(1),
                        file_path=md_file,
                        line_number=line_num,
                    )
                )
            # External links
            self._extract_external_links_to_cache(line, md_file, line_num)
            # Local links
            for lmatch in self.LOCAL_LINK_PATTERN.finditer(line):
                link_text, path = lmatch.groups()
                if not path.startswith(("http://", "https://")):
                    self._local_cache.append(  # type: ignore[union-attr]
                        LocalLink(
                            path=path,
                            text=link_text,
                            file_path=md_file,
                            line_number=line_num,
                        )
                    )

    def _extract_external_links_to_cache(
        self, text: str, file_path: Path, line_num: int
    ) -> None:
        """Extract external links to cache (used during single-pass scan).

        Finds both markdown links and bare URLs. Deduplicates URLs that appear
        as both formats on the same line (markdown link takes precedence).

        Args:
            text: Line or cell text to scan.
            file_path: Source file for location tracking.
            line_num: Line or cell number for location tracking.
        """
        seen_urls: set[str] = set()
        for match in self.MARKDOWN_LINK_PATTERN.finditer(text):
            link_text, url = match.groups()
            self._external_cache.append(  # type: ignore[union-attr]
                ExternalLink(
                    url=url, text=link_text, file_path=file_path, line_number=line_num
                )
            )
            seen_urls.add(url)
        for match in self.BARE_URL_PATTERN.finditer(text):
            url = match.group(0)
            if url not in seen_urls:
                self._external_cache.append(  # type: ignore[union-attr]
                    ExternalLink(
                        url=url, text="", file_path=file_path, line_number=line_num
                    )
                )
                seen_urls.add(url)

    def _read_file(self, file_path: Path) -> str | None:
        """Read file content, return None on error.

        Args:
            file_path: Path to file to read.

        Returns:
            File content as string, or None if read fails (logs warning).
        """
        try:
            return file_path.read_text()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return None

    def _iter_notebook_cells(self, file_path: Path) -> list[tuple[int, str]]:
        """Yield (cell_number, cell_text) for each cell in notebook.

        Args:
            file_path: Path to .ipynb file.

        Returns:
            List of (1-based cell index, cell source text) tuples.
        """
        try:
            notebook = json.loads(file_path.read_text())
            result = []
            for idx, cell in enumerate(notebook.get("cells", [])):
                source = cell.get("source", [])
                if isinstance(source, list):
                    source = "".join(source)
                result.append((idx + 1, source))
            return result
        except Exception as e:
            print(f"Warning: Could not read notebook {file_path}: {e}")
            return []


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
        nav = self._load_nav()
        if nav is None:
            return None
        return set(self._collect_nav_paths(nav))

    def check_nav_paths(self) -> list[dict[str, str]]:
        """Validate all nav paths exist in docs directory.

        Returns:
            List of dicts with 'path' and 'location' keys for each broken path.
            Empty list if mkdocs.yml missing, no nav section, or all paths valid.
        """
        nav = self._load_nav()
        if nav is None:
            return []

        broken = []
        for path in self._collect_nav_paths(nav):
            if not (self.docs_path / path).exists():
                broken.append({"path": path, "location": "mkdocs.yml"})
        return broken

    def _load_nav(self) -> list[Any] | None:
        """Load nav section from mkdocs.yml.

        Returns:
            Nav list if found, None if file missing/no nav/parse error.
        """
        if not self.mkdocs_path.exists():
            return None
        try:
            import yaml

            config = yaml.safe_load(self.mkdocs_path.read_text())
            return cast(Optional[list[Any]], config.get("nav"))
        except Exception as e:
            print(f"Warning: Could not parse {self.mkdocs_path}: {e}")
            return None

    def _collect_nav_paths(self, nav_item: Any) -> list[str]:
        """Recursively collect all file paths from nav structure.

        Handles nav items as strings, dicts, or lists (mkdocs nav format).

        Args:
            nav_item: Nav element (str path, dict, or list of items).

        Returns:
            List of file path strings found in nav_item.
        """
        paths: list[str] = []

        if isinstance(nav_item, str):
            paths.append(nav_item)
        elif isinstance(nav_item, dict):
            for value in nav_item.values():
                paths.extend(self._collect_nav_paths(value))
        elif isinstance(nav_item, list):
            for item in nav_item:
                paths.extend(self._collect_nav_paths(item))

        return paths
