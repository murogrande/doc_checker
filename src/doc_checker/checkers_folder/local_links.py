from __future__ import annotations

from pathlib import Path
from typing import Iterator

from doc_checker import DriftReport
from doc_checker.models import BrokenLinkInfo, LocalLink
from doc_checker.parsers import MarkdownParser, YamlParser

from .base import DocArtifactChecker


class LocalLinksChecker(DocArtifactChecker):
    """Detect broken local file links in markdown and notebooks."""

    def __init__(
        self, root_path: Path, md_parser: MarkdownParser, yaml_parser: YamlParser
    ):
        self.root_path = root_path
        self.md_parser = md_parser
        self.nav: set[str] | None = yaml_parser.get_nav_files()

    def collect(self) -> Iterator[LocalLink]:
        """Yield all local links from markdown/notebook files."""
        yield from self.md_parser.find_local_links()

    def validate(self, link: LocalLink, report: DriftReport) -> None:
        """Resolve link and append to report.broken_local_links if broken."""
        link_path = link.path.split("#")[0].rstrip("/")
        suffix, link_dir = link.file_path.suffix, link.file_path.parent
        resolved = LocalLinksChecker._resolve_path(
            root_path=self.root_path,
            link_dir=link_dir,
            link_path=link_path,
            suffix=suffix,
        )
        if not resolved:
            report.broken_local_links.append(self._broken(link, link_path))
        elif suffix == ".ipynb" and link_path.endswith(".ipynb"):
            report.broken_local_links.append(
                self._broken(link, link_path, "notebook links should omit .ipynb")
            )
        elif link_path.endswith(".py") and self.nav:
            try:
                if str(resolved.relative_to(self.root_path / "docs")) not in self.nav:
                    report.broken_local_links.append(
                        self._broken(link, link.path, ".py file not in mkdocs nav")
                    )
            except ValueError:
                pass

    @staticmethod
    def _resolve_path(
        root_path: Path, link_dir: Path, link_path: str, suffix: str
    ) -> Path | None:
        """Try multiple strategies to resolve a local link path.

        Resolution order: (1) direct relative from link's dir, (2) ../ from
        docs root, (3) absolute from project root, (4) mkdocs URL-style with
        auto-extension for notebooks.

        Args:
            link_dir: Directory containing the source file with the link.
            link_path: Link path (may be relative, absolute, or URL-style).
            suffix: Source file extension (.md or .ipynb).

        Returns:
            Resolved Path if file exists, None otherwise.
        """
        docs = root_path / "docs"
        # Direct relative
        if (resolved := (link_dir / link_path).resolve()).exists():
            return resolved
        # ../ from docs root
        if (
            link_path.startswith("..")
            and (resolved := (docs / link_path).resolve()).exists()
        ):
            return resolved
        # Absolute from project root
        if (
            link_path.startswith("/")
            and (resolved := (root_path / link_path.lstrip("/")).resolve()).exists()
        ):
            return resolved
        # mkdocs URL-style
        if link_path.startswith(".."):
            src_file = next(
                (file for file in link_dir.iterdir() if file.suffix == suffix),
                link_dir / (link_dir.name + suffix),
            )
            resolved = (link_dir / src_file.stem / link_path).resolve()
            if resolved.exists():
                return resolved
            if not resolved.suffix:
                for ext in (".md", ".ipynb") if suffix == ".ipynb" else (".md",):
                    if resolved.with_suffix(ext).exists():
                        return resolved.with_suffix(ext)
        return None

    def _broken(
        self, link: LocalLink, path: str, reason: str | None = None
    ) -> BrokenLinkInfo:
        """Create a BrokenLinkInfo dict from a LocalLink.

        Args:
            link: Source LocalLink with file_path, line_number, text.
            path: The broken path string to report.
            reason: Optional explanation (e.g., "notebook links should omit .ipynb").

        Returns:
            BrokenLinkInfo dict with path, location, text, and optional reason.
        """
        info: BrokenLinkInfo = {
            "path": path,
            "location": f"{link.file_path}:{link.line_number}",
            "text": link.text,
        }
        if reason:
            info["reason"] = reason
        return info
