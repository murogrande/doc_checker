"""CLI for documentation checker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from doc_checker.checkers import DriftDetector
from doc_checker.formatters import format_report


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Documentation drift detection for Python projects"
    )
    parser.add_argument(
        "--check-all", action="store_true", help="Run all drift detection checks"
    )
    parser.add_argument(
        "--check-signatures", action="store_true", help="Check API signature coverage"
    )
    parser.add_argument(
        "--check-external-links",
        action="store_true",
        help="Check external HTTP links (can be slow)",
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
    if not any([args.check_all, args.check_signatures, args.check_external_links]):
        args.check_all = True

    # Add root to Python path for imports
    sys.path.insert(0, str(args.root))

    detector = DriftDetector(
        args.root,
        modules=args.modules,
        ignore_pulser_reexports=args.ignore_pulser_reexports,
    )

    # Run checks
    if args.check_all or args.check_signatures:
        if not args.json:
            print("Running documentation drift detection...")

        include_external = args.check_all or args.check_external_links
        report = detector.check_all(
            check_external_links=include_external, verbose=args.verbose
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
        report = detector.check_all(check_external_links=True, verbose=args.verbose)

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
