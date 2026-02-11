from __future__ import annotations

from pathlib import Path

from doc_checker.code_analyzer import CodeAnalyzer
from doc_checker.models import DriftReport, SignatureInfo
from doc_checker.parsers import MarkdownParser

from .base import ApiChecker


class DocstringsLinksChecker(ApiChecker):
    """Check that docstring links point to existing files."""

    def __init__(
        self,
        code_analyzer: CodeAnalyzer,
        modules: list[str],
        ignore_submodules: set[str],
        root_path: Path,
        md_parser: MarkdownParser,
    ):
        super().__init__(code_analyzer, modules, ignore_submodules)

        self.root_path = root_path
        self.md_parser = md_parser
        self.docs = root_path / "docs"
        self.refs: dict[str, Path] = {}

    def setup(self, report: DriftReport) -> None:
        self.refs = {
            ref.reference: ref.file_path.parent
            for ref in self.md_parser.find_mkdocstrings_refs()
        }
        for reference, parent_dir in list(self.refs.items()):
            short = reference.split(".")[0] + "." + reference.rsplit(".", 1)[-1]
            if short != reference:
                self.refs.setdefault(short, parent_dir)

    def check_api(self, api: SignatureInfo, report: DriftReport) -> None:
        if not api.docstring:
            return
        fqn = f"{api.module}.{api.name}"
        base = self.refs.get(fqn, self.docs)
        for link in self.md_parser.parse_local_links_in_text(api.docstring, base):
            link_path = link.path.split("#")[0]
            if not self._resolve_ds_link(link_path, base, self.docs):
                report.broken_local_links.append(
                    {
                        "path": link.path,
                        "location": f"{fqn} (docstring):{link.line_number}",
                        "text": link.text,
                    }
                )

    def _resolve_ds_link(self, link_path: str, base: Path, docs: Path) -> Path | None:
        """Resolve a docstring link using multiple base directories.

        Tries: (1) relative from base (API's doc page dir), (2) ../ from
        docs root, (3) absolute from project root.

        Args:
            link_path: Link path from docstring (fragment stripped).
            base: Directory of md file containing ::: directive for this API.
            docs: Project docs/ directory.

        Returns:
            Resolved Path if file exists, None otherwise.
        """
        for base_dir, prefix in [(base, ""), (docs, ".."), (self.root_path, "/")]:
            if not prefix or link_path.startswith(prefix):
                resolved = (
                    base_dir / (link_path.lstrip("/") if prefix == "/" else link_path)
                ).resolve()
                if resolved.exists():
                    return resolved
        return None
