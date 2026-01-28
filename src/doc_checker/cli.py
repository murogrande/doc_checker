"""CLI for documentation checker."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .checkers import DriftDetector
from .formatters import format_report


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Documentation drift detection for Python projects"
    )
    parser.add_argument(
        "--check-all", action="store_true", help="Run all drift detection checks"
    )
    parser.add_argument(
        "--check-basic",
        action="store_true",
        help="Run basic checks (API coverage, references, params, local links, mkdocs)",
    )
    parser.add_argument(
        "--check-external-links",
        action="store_true",
        help="Check external HTTP links (can be slow)",
    )
    parser.add_argument(
        "--check-quality",
        action="store_true",
        help="Check documentation quality using LLM",
    )
    parser.add_argument(
        "--llm-backend",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM backend to use (default: ollama)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        help="LLM model name (defaults: qwen2.5:3b for ollama, gpt-4o-mini for openai)",  # noqa: E501
    )
    parser.add_argument(
        "--quality-sample",
        type=float,
        default=1.0,
        help="Sample rate for quality checks (0.0-1.0, default: 1.0 = all APIs)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--ignore-pulser-reexports",
        action="store_true",
        default=True,
        help="Ignore Pulser re-exported APIs (default: True)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Root path of repository (default: current dir)",
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        default=["emu_mps", "emu_sv"],
        help="Modules to check (default: emu_mps emu_sv)",
    )

    args = parser.parse_args()

    # Default to --check-all if nothing specified
    if not any(
        [
            args.check_all,
            args.check_basic,
            args.check_external_links,
            args.check_quality,
        ]
    ):
        args.check_all = True

    # Add root to Python path for imports
    sys.path.insert(0, str(args.root))

    detector = DriftDetector(
        args.root,
        modules=args.modules,
        ignore_pulser_reexports=args.ignore_pulser_reexports,
    )

    # Get API key for OpenAI if needed
    api_key = None
    if args.check_quality and args.llm_backend == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
            print("Set with: export OPENAI_API_KEY='sk-proj-...'", file=sys.stderr)
            return 1

    # Run checks
    if args.check_all or args.check_basic or args.check_quality:
        if not args.json:
            print("Running documentation drift detection...")

        include_external = args.check_all or args.check_external_links
        include_quality = args.check_all or args.check_quality

        report = detector.check_all(
            check_external_links=include_external,
            check_quality=include_quality,
            quality_backend=args.llm_backend,
            quality_model=args.llm_model,
            quality_api_key=api_key,
            quality_sample_rate=args.quality_sample,
            verbose=args.verbose,
        )

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(format_report(report))

        return 1 if report.has_issues() else 0

    # Standalone external links check
    if args.check_external_links:
        if not args.json:
            print("Checking external links...")
        report = detector.check_all(
            check_external_links=True, verbose=args.verbose, skip_basic_checks=True
        )

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            if report.broken_external_links:
                print(f"\nBroken external links ({len(report.broken_external_links)}):")
                for link_info in report.broken_external_links:
                    status = link_info.get("status", "unknown")
                    url = link_info.get("url", "unknown")
                    location = link_info.get("location", "unknown")
                    print(f"  {location}: {url} (status: {status})")
                return 1
            else:
                print("All external links OK")
                return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
