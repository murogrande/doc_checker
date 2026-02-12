from __future__ import annotations

import importlib
from typing import Iterator

from doc_checker.models import DocReference, DriftReport
from doc_checker.parsers import MarkdownParser

from .base import DocArtifactChecker


class ReferencesChecker(DocArtifactChecker):

    def __init__(self, md_parser: MarkdownParser):
        self.md_parser = md_parser

    def collect(self) -> Iterator[DocReference]:
        yield from self.md_parser.find_mkdocstrings_refs()

    def validate(self, item: DocReference, report: DriftReport) -> None:
        if not self._is_valid_reference(item.reference):
            report.broken_references.append(
                f"{item.reference} in {item.file_path}:{item.line_number}"
            )

    def _is_valid_reference(self, reference: str) -> bool:
        """Check if dotted reference resolves to a Python object.

        Tries progressively shorter module prefixes (a.b.c → a.b → a) then
        getattr for remaining parts. Returns True if any combo succeeds.

        Args:
            reference: Dotted path like "pkg.module.Class.method".

        Returns:
            True if reference can be imported and resolved.
        """
        parts = reference.split(".")
        for i in range(len(parts), 0, -1):
            try:
                mod = importlib.import_module(".".join(parts[:i]))
                for attr in parts[i:]:
                    mod = getattr(mod, attr)
                return True
            except (ImportError, AttributeError):
                continue
        return False
