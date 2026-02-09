"""Report formatting utilities."""

from __future__ import annotations

from typing import Any

from .models import DriftReport


def format_report(report: DriftReport) -> str:
    """Format drift report as text."""
    lines = ["=" * 60, "DOCUMENTATION DRIFT REPORT", "=" * 60]
    if report.llm_backend and report.llm_model:
        lines.append(f"LLM: {report.llm_backend} / {report.llm_model}")
    lines.append("")

    if report.missing_in_docs:
        lines.append(f"Missing from docs ({len(report.missing_in_docs)}):")
        for item in report.missing_in_docs:
            lines.append(f"  - {item}")
        lines.append("")

    if report.signature_mismatches:
        lines.append(f"Signature mismatches ({len(report.signature_mismatches)}):")
        for mismatch in report.signature_mismatches:
            lines.append(f"  - {mismatch['name']}: {mismatch['issue']}")
        lines.append("")

    if report.broken_references:
        lines.append(f"Broken references ({len(report.broken_references)}):")
        for broken_ref in report.broken_references:
            lines.append(f"  - {broken_ref}")
        lines.append("")

    if report.total_external_links:
        broken = len(report.broken_external_links)
        total = report.total_external_links
        lines.append(f"External links: {broken}/{total} broken")
    if report.broken_external_links:
        for ext_link in report.broken_external_links:
            status = ext_link.get("status", "unknown")
            url = ext_link.get("url", "unknown")
            location = ext_link.get("location", "unknown")
            lines.append(f"  {location}: {url} (status: {status})")
        lines.append("")

    if report.broken_local_links:
        lines.append(f"Broken local links ({len(report.broken_local_links)}):")
        for local_link in report.broken_local_links:
            path = local_link.get("path", "unknown")
            location = local_link.get("location", "unknown")
            reason = local_link.get("reason", "")
            if reason:
                lines.append(f"  {location}: {path} ({reason})")
            else:
                lines.append(f"  {location}: {path}")
        lines.append("")

    if report.broken_mkdocs_paths:
        lines.append(f"Broken mkdocs.yml paths ({len(report.broken_mkdocs_paths)}):")
        for mkdocs_path in report.broken_mkdocs_paths:
            path = mkdocs_path.get("path", "unknown")
            location = mkdocs_path.get("location", "mkdocs.yml")
            lines.append(f"  {location}: {path}")
        lines.append("")

    if report.undocumented_params:
        lines.append(f"Undocumented parameters ({len(report.undocumented_params)}):")
        for undoc_param in report.undocumented_params:
            lines.append(f"  - {undoc_param['name']}: {undoc_param['params']}")
        lines.append("")

    if report.quality_issues:
        lines.append(f"Quality issues ({len(report.quality_issues)}):")
        lines.append("")

        # Group by severity
        by_severity: dict[str, list[Any]] = {
            "critical": [],
            "warning": [],
            "suggestion": [],
        }
        for issue in report.quality_issues:
            by_severity[issue.severity].append(issue)

        for severity in ["critical", "warning", "suggestion"]:
            issues = by_severity[severity]
            if not issues:
                continue

            severity_icon = {"critical": "✘", "warning": "⚠", "suggestion": "ℹ"}
            lines.append(
                f"  {severity_icon[severity]} {severity.upper()} ({len(issues)}):"
            )  # noqa: E501
            for issue in issues:
                lines.append(f"    {issue.api_name} [{issue.category}]")
                lines.append(f"      Issue: {issue.message}")
                lines.append(f"      Fix: {issue.suggestion}")
                if issue.line_reference:
                    lines.append(f"      Text: {issue.line_reference}")
                lines.append("")

    if report.warnings:
        lines.append(f"Warnings ({len(report.warnings)}):")
        for item in report.warnings:
            lines.append(f"  - {item}")
        lines.append("")

    if not report.has_issues():
        lines.append("No documentation drift detected.")

    lines.append("=" * 60)
    return "\n".join(lines)
