from abc import ABC, abstractmethod
from typing import Any, Iterator

from doc_checker.code_analyzer import CodeAnalyzer
from doc_checker.models import DriftReport, SignatureInfo


class Checker(ABC):
    """Base for all checkers. Takes report, mutates it."""

    @abstractmethod
    def check(self, report: DriftReport) -> None: ...


class ApiChecker(Checker, ABC):
    """Iterate public APIs, run per-API logic.

    Subclasses implement `check_api()` for single-API checks and
    optionally `setup()` for pre-loop state (e.g. building ref sets).
    """

    def __init__(
        self,
        code_analyzer: CodeAnalyzer,
        modules: list[str],
        ignore_submodules: set[str],
    ):
        self.code_analyzer = code_analyzer
        self.modules = modules
        self.ignore_submodules = ignore_submodules

    def _iter_apis(self) -> Iterator[SignatureInfo]:
        for module in self.modules:
            apis, _ = self.code_analyzer.get_all_public_apis(
                module, self.ignore_submodules
            )
            yield from apis

    def setup(self, report: DriftReport) -> None:
        """Optional pre-loop setup. Override to build lookup tables etc."""

    @abstractmethod
    def check_api(self, api: SignatureInfo, report: DriftReport) -> None:
        """Check a single API. Append issues to report."""
        ...

    def check(self, report: DriftReport) -> None:
        self.setup(report)
        for api in self._iter_apis():
            self.check_api(api, report)


class DocArtifactChecker(Checker, ABC):
    """Iterate doc artifacts, validate each one.

    Subclasses implement `collect()` to yield items and
    `validate()` to check + append to report.
    """

    @abstractmethod
    def collect(self) -> Iterator[Any]:
        """Yield items to validate (refs, links, nav paths, etc.)."""
        pass

    @abstractmethod
    def validate(self, item: Any, report: DriftReport) -> None:
        """Validate single item. Append issues to report."""
        ...

    def check(self, report: DriftReport) -> None:
        for item in self.collect():
            self.validate(item, report)
