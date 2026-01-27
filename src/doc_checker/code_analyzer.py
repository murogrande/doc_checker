"""Analyze Python code to extract public API signatures."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

from .models import SignatureInfo


class CodeAnalyzer:
    """Extract public APIs from Python modules."""

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def get_public_apis(self, module_name: str) -> list[SignatureInfo]:
        """Extract all public APIs from module."""
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
        """Extract signature from Python object."""
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
        """Extract class signature (uses __init__)."""
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
        """Extract function signature."""
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
