"""Analyze Python code to extract public API signatures."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

from .models import SignatureInfo


class CodeAnalyzer:
    """Extract public APIs from Python modules via importlib/inspect introspection.

    Discovers classes and functions exported by a module (via __all__ or dir()),
    extracts their signatures, parameters, return types, and docstrings.
    """

    def __init__(self, root_path: Path):
        """Initialize analyzer.

        Args:
            root_path: Project root path (added to sys.path for imports).
        """
        self.root_path = root_path

    def get_public_apis(self, module_name: str) -> list[SignatureInfo]:
        """Extract all public APIs from a module.

        Uses module's __all__ if defined, otherwise falls back to non-underscore
        names from dir(). Skips __version__ and non-callable objects.

        Args:
            module_name: Fully qualified module name (e.g. "emu_mps").

        Returns:
            List of SignatureInfo for each public class/function.
        """
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            print(f"Warning: Could not import {module_name}: {e}")
            return []

        # Use __all__ or fallback to non-underscore names
        all_items = getattr(module, "__all__", None)
        if all_items is None:
            all_items = [name for name in dir(module) if not name.startswith("_")]

        apis: list[SignatureInfo] = []
        for name in all_items:
            if name == "__version__":
                continue
            try:
                obj = getattr(module, name)

                sig_info = self._extract_signature(name, obj, module_name)
                if sig_info:
                    apis.append(sig_info)
            except AttributeError:
                continue

        return apis

    def _extract_signature(
        self, name: str, obj: Any, module_name: str
    ) -> SignatureInfo | None:
        """Extract signature from a Python object.

        Dispatches to class or function extraction based on object type.

        Args:
            name: Object name as exported by module.
            obj: The actual Python object (class, function, etc.).
            module_name: Parent module's fully qualified name.

        Returns:
            SignatureInfo if obj is a class/function, None otherwise.
        """
        try:
            if inspect.isclass(obj):
                return self._extract_class_signature(name, obj, module_name)
            elif inspect.isfunction(obj) or inspect.ismethod(obj):
                return self._extract_function_signature(name, obj, module_name)
        except Exception as e:
            print(f"Warning: Could not extract signature for {name}: {e}")
        return None

    def _extract_class_signature(
        self, name: str, cls: type, module_name: str
    ) -> SignatureInfo:
        """Extract class signature from its __init__ method.

        Args:
            name: Class name.
            cls: The class object.
            module_name: Parent module's fully qualified name.

        Returns:
            SignatureInfo with kind="class", parameters from __init__.
        """
        params: list[str] = []
        try:
            sig = inspect.signature(cls)
            params = [
                self._format_param(p) for p in sig.parameters.values() if p.name != "self"
            ]
        except (ValueError, TypeError):
            pass

        return SignatureInfo(
            name=name,
            module=module_name,
            parameters=params,
            return_annotation=None,
            docstring=inspect.getdoc(cls),
            is_public=not name.startswith("_"),
            kind="class",
        )

    def _extract_function_signature(
        self, name: str, func: Any, module_name: str
    ) -> SignatureInfo:
        """Extract function/method signature.

        Args:
            name: Function name.
            func: The function or method object.
            module_name: Parent module's fully qualified name.

        Returns:
            SignatureInfo with kind="function", parameters excluding self/cls.
        """
        params = []
        return_ann = None
        try:
            sig = inspect.signature(func)
            params = [
                self._format_param(p)
                for p in sig.parameters.values()
                if p.name not in ("self", "cls")
            ]
            if sig.return_annotation != inspect.Signature.empty:
                return_ann = str(sig.return_annotation)
        except (ValueError, TypeError):
            pass

        return SignatureInfo(
            name=name,
            module=module_name,
            parameters=params,
            return_annotation=return_ann,
            docstring=inspect.getdoc(func),
            is_public=not name.startswith("_"),
            kind="function",
        )

    def _format_param(self, param: inspect.Parameter) -> str:
        """Format parameter for display."""
        result = param.name
        if param.annotation != inspect.Parameter.empty:
            ann = param.annotation
            result += f": {ann.__name__ if hasattr(ann, '__name__') else ann}"
        if param.default != inspect.Parameter.empty:
            result += f" = {param.default!r}"
        return result
