from doc_checker.constants import IGNORE_PARAMS
from doc_checker.models import DriftReport, SignatureInfo
from doc_checker.utils.code_analyzer import CodeAnalyzer

from .base import ApiChecker


class ParamDocsChecker(ApiChecker):
    """Check that all parameters of public APIs are documented in the docstring."""

    def __init__(
        self,
        code_analyzer: CodeAnalyzer,
        modules: list[str],
        ignore_submodules: set[str],
    ):
        super().__init__(code_analyzer, modules, ignore_submodules)

    def check_api(self, api: SignatureInfo, report: DriftReport) -> None:
        """Append params not mentioned in docstring to report.undocumented_params."""
        if not api.docstring or not api.parameters:
            return  # Skip APIs without docstrings (caught by other checkers)
        undoc = [
            param.split(".")[0].split("=")[0].strip()
            for param in api.parameters
            if param.split(":")[0].split("=")[0].strip() not in IGNORE_PARAMS
            and param.split(":")[0].split("=")[0].strip() not in (api.docstring or "")
        ]
        if undoc:
            report.undocumented_params.append(
                {"name": f"{api.module}.{api.name}", "params": ", ".join(undoc)}
            )
