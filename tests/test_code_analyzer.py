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
