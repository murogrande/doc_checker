from doc_checker.code_analyzer import CodeAnalyzer
from doc_checker.constants import PULSER_REEXPORTS
from doc_checker.models import DriftReport, SignatureInfo
from doc_checker.parsers import MarkdownParser

from .base import ApiChecker


def _is_api_documented(
    api: SignatureInfo, documented: set[str], doc_names: dict[str, set[str]]
) -> bool:
    """Check if API is documented via any naming convention.

    Checks three patterns: (1) short name in module's doc_names set,
    (2) exact fqn match in documented, (3) suffix match for re-exports.

    Args:
        api: SignatureInfo with module and name attributes.
        documented: Set of all ::: reference strings found in docs.
        doc_names: Mapping of base module -> set of documented names/refs.

    Returns:
        True if API is documented via any naming pattern.
    """
    base = api.module.split(".")[0]
    return (
        api.name in doc_names.get(base, set())
        or f"{api.module}.{api.name}" in documented
        or any(ref.endswith(f".{api.name}") for ref in documented)
    )


class ApiCoverageChecker(ApiChecker):
    """Flag public APIs missing from mkdocstrings ::: refs."""

    def __init__(
        self,
        code_analyzer: CodeAnalyzer,
        modules: list[str],
        ignore_submodules: set[str],
        md_parser: MarkdownParser,
        ignore_pulser_reexports: bool,
    ):
        super().__init__(code_analyzer, modules, ignore_submodules)
        self.md_parser = md_parser
        self.ignore_pulser_reexports = ignore_pulser_reexports

    def setup(self, report: DriftReport) -> None:
        """Build documented-names lookup from mkdocstrings refs."""
        refs = self.md_parser.find_mkdocstrings_refs()
        self.documented = {ref.reference for ref in refs}
        self.doc_names: dict[str, set[str]] = {m: set() for m in self.modules}
        for ref in self.documented:
            parts = ref.split(".")
            if len(parts) >= 2 and parts[0] in self.doc_names:
                self.doc_names[parts[0]].update([parts[-1], ref])

    def check_api(self, api: SignatureInfo, report: DriftReport) -> None:
        """Append undocumented API to report.missing_in_docs."""
        if self.ignore_pulser_reexports and api.name in PULSER_REEXPORTS:
            return
        if not _is_api_documented(api, self.documented, self.doc_names):
            report.missing_in_docs.append(f"{api.module}.{api.name}")
