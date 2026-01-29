"""Tests for code_analyzer module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from doc_checker.code_analyzer import CodeAnalyzer


@pytest.fixture
def sample_module(tmp_path: Path) -> ModuleType:
    """Create a sample Python module for testing."""
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    # Create __init__.py with sample code
    init_file = module_dir / "__init__.py"
    code = '''
"""Sample module for testing."""

__all__ = ["PublicClass", "public_function"]


class PublicClass:
    """A public class."""

    def __init__(self, param1: int, param2: str = "default"):
        """Initialize with params."""
        self.param1 = param1
        self.param2 = param2

    def method(self) -> str:
        """A method."""
        return "result"


def public_function(x: int, y: int = 10) -> int:
    """A public function."""
    return x + y


def _private_function():
    """Should not be included."""
    pass


class _PrivateClass:
    """Should not be included."""
    pass
'''
    init_file.write_text(code)

    # Add to sys.path and import
    sys.path.insert(0, str(tmp_path))
    import test_module

    return test_module


class TestCodeAnalyzer:
    """Test CodeAnalyzer."""

    def test_get_public_apis(self, sample_module: ModuleType, tmp_path: Path):
        analyzer = CodeAnalyzer(tmp_path)
        apis = analyzer.get_public_apis("test_module")

        assert len(apis) == 2
        names = {api.name for api in apis}
        assert "PublicClass" in names
        assert "public_function" in names

    def test_class_signature_extraction(self, sample_module: ModuleType, tmp_path: Path):
        analyzer = CodeAnalyzer(tmp_path)
        apis = analyzer.get_public_apis("test_module")

        class_api = next(api for api in apis if api.name == "PublicClass")
        assert class_api.kind == "class"
        assert class_api.is_public is True
        assert len(class_api.parameters) == 2
        assert class_api.parameters[0].startswith("param1")
        assert "int" in class_api.parameters[0]
        assert class_api.docstring == "A public class."

    def test_function_signature_extraction(
        self, sample_module: ModuleType, tmp_path: Path
    ):
        analyzer = CodeAnalyzer(tmp_path)
        apis = analyzer.get_public_apis("test_module")

        func_api = next(api for api in apis if api.name == "public_function")
        assert func_api.kind == "function"
        assert func_api.is_public is True
        assert len(func_api.parameters) == 2
        assert "int" in func_api.return_annotation
        assert func_api.docstring == "A public function."

    def test_parameter_formatting(self, sample_module: ModuleType, tmp_path: Path):
        analyzer = CodeAnalyzer(tmp_path)
        apis = analyzer.get_public_apis("test_module")

        func_api = next(api for api in apis if api.name == "public_function")
        params = func_api.parameters

        # Check param with type
        assert any("x" in p and "int" in p for p in params)
        # Check param with default
        assert any("y" in p and "=" in p and "10" in p for p in params)

    def test_nonexistent_module(self, tmp_path: Path):
        analyzer = CodeAnalyzer(tmp_path)
        apis = analyzer.get_public_apis("nonexistent_module")

        assert apis == []

    def test_get_all_public_apis_with_submodules(self, tmp_path: Path):
        """Test recursive submodule discovery."""
        pkg = tmp_path / "nested_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["TopFunc"]\ndef TopFunc(): "top"\n')

        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text('__all__ = ["SubFunc"]\ndef SubFunc(): "sub"\n')

        sys.path.insert(0, str(tmp_path))
        try:
            analyzer = CodeAnalyzer(tmp_path)
            apis, _ = analyzer.get_all_public_apis("nested_pkg")
            names = {api.name for api in apis}
            assert "TopFunc" in names
            assert "SubFunc" in names
            assert len(names) >= 2
        finally:
            sys.modules.pop("nested_pkg", None)
            sys.modules.pop("nested_pkg.sub", None)

    def test_get_all_public_apis_ignore_submodules(self, tmp_path: Path):
        """Test ignore_submodules skips matching submodules."""
        pkg = tmp_path / "ign_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["Top"]\ndef Top(): "top"\n')
        sub = pkg / "skip_me"
        sub.mkdir()
        (sub / "__init__.py").write_text('__all__ = ["Skipped"]\ndef Skipped(): "skip"\n')
        keep = pkg / "keep"
        keep.mkdir()
        (keep / "__init__.py").write_text('__all__ = ["Kept"]\ndef Kept(): "keep"\n')

        sys.path.insert(0, str(tmp_path))
        try:
            analyzer = CodeAnalyzer(tmp_path)
            apis, _ = analyzer.get_all_public_apis(
                "ign_pkg",
                ignore_submodules={"ign_pkg.skip_me"},
            )
            names = {api.name for api in apis}
            assert "Top" in names
            assert "Kept" in names
            assert "Skipped" not in names
        finally:
            sys.modules.pop("ign_pkg", None)
            sys.modules.pop("ign_pkg.skip_me", None)
            sys.modules.pop("ign_pkg.keep", None)

    def test_get_all_public_apis_ignore_nonexistent_warns(self, tmp_path: Path):
        """Warn when ignore_submodules entry matches nothing."""
        pkg = tmp_path / "warn_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["W"]\ndef W(): "w"\n')
        # Need a real subpackage so the warning logic runs
        sub = pkg / "real_sub"
        sub.mkdir()
        (sub / "__init__.py").write_text("__all__ = []\n")

        sys.path.insert(0, str(tmp_path))
        try:
            analyzer = CodeAnalyzer(tmp_path)
            _, unmatched = analyzer.get_all_public_apis(
                "warn_pkg",
                ignore_submodules={"warn_pkg.nonexistent"},
            )
            assert "warn_pkg.nonexistent" in unmatched
        finally:
            sys.modules.pop("warn_pkg", None)
            sys.modules.pop("warn_pkg.real_sub", None)

    def test_get_all_public_apis_ignore_no_warn_other_module(self, tmp_path: Path):
        """No warning when ignore entry targets a different module."""
        pkg = tmp_path / "other_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["F"]\ndef F(): "f"\n')

        sys.path.insert(0, str(tmp_path))
        try:
            analyzer = CodeAnalyzer(tmp_path)
            _, unmatched = analyzer.get_all_public_apis(
                "other_pkg",
                ignore_submodules={"different_pkg.sub"},
            )
            assert len(unmatched) == 0
        finally:
            sys.modules.pop("other_pkg", None)

    def test_get_all_public_apis_skips_py_files(self, tmp_path: Path):
        """Internal .py files are not treated as submodules."""
        pkg = tmp_path / "flat_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '__all__ = ["Public"]\n' "from .internal import Internal as Public\n"
        )
        # .py file with its own classes — should NOT be discovered
        (pkg / "internal.py").write_text('class Internal:\n    "impl detail"\n')

        sys.path.insert(0, str(tmp_path))
        try:
            analyzer = CodeAnalyzer(tmp_path)
            apis, _ = analyzer.get_all_public_apis("flat_pkg")
            names = {(api.module, api.name) for api in apis}
            # Only top-level export, not internal.py's class
            assert ("flat_pkg", "Public") in names
            assert not any(m == "flat_pkg.internal" for m, _ in names)
        finally:
            sys.modules.pop("flat_pkg", None)
            sys.modules.pop("flat_pkg.internal", None)

    def test_get_all_public_apis_flat_module(
        self, sample_module: ModuleType, tmp_path: Path
    ):
        """Flat module: get_all_public_apis == get_public_apis."""
        analyzer = CodeAnalyzer(tmp_path)
        flat = analyzer.get_public_apis("test_module")
        recursive, _ = analyzer.get_all_public_apis("test_module")
        assert {a.name for a in flat} == {a.name for a in recursive}

    def test_get_all_public_apis_nonexistent(self, tmp_path: Path):
        analyzer = CodeAnalyzer(tmp_path)
        apis, unmatched = analyzer.get_all_public_apis("nonexistent_module_xyz")
        assert apis == []
        assert unmatched == set()

    def test_module_without_all(self, tmp_path: Path):
        """Test module without __all__ attribute."""
        module_dir = tmp_path / "test_module_no_all"
        module_dir.mkdir()

        init_file = module_dir / "__init__.py"
        code = '''
"""Module without __all__."""

def public_func():
    """Public function."""
    pass

def _private_func():
    """Private function."""
    pass
'''
        init_file.write_text(code)

        sys.path.insert(0, str(tmp_path))
        analyzer = CodeAnalyzer(tmp_path)
        apis = analyzer.get_public_apis("test_module_no_all")

        # Should include public_func but not _private_func
        names = {api.name for api in apis}
        assert "public_func" in names
        assert "_private_func" not in names
