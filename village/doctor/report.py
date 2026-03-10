"""Report generation and interactive selection."""

import json

import questionary

from village.chat.task_extractor import BeadsTaskSpec, create_draft_tasks
from village.config import Config
from village.doctor.base import AnalyzerResult, Finding
from village.logging import get_logger

logger = get_logger(__name__)


def format_report(results: list[AnalyzerResult], format: str = "text") -> str:
    """Format analysis results."""
    if format == "json":
        return _format_json(results)
    return _format_text(results)


def _format_json(results: list[AnalyzerResult]) -> str:
    """Format as JSON."""
    data = {
        "results": [
            {
                "analyzer": r.analyzer_name,
                "description": r.analyzer_description,
                "findings": [
                    {
                        "id": f.id,
                        "title": f.title,
                        "description": f.description,
                        "severity": f.severity,
                        "category": f.category,
                        "file": f.file,
                        "line": f.line,
                        "metadata": f.metadata,
                    }
                    for f in r.findings
                ],
                "error": r.error,
            }
            for r in results
        ],
        "summary": {
            "total_findings": sum(len(r.findings) for r in results),
            "analyzers_run": len(results),
            "analyzers_with_errors": sum(1 for r in results if r.error),
        },
    }
    return json.dumps(data, indent=2)


def _format_text(results: list[AnalyzerResult]) -> str:
    """Format as human-readable text."""
    lines = []
    total_findings = 0

    for result in results:
        if result.error:
            lines.append(f"[{result.analyzer_name}] Error: {result.error}")
            continue

        if not result.findings:
            continue

        total_findings += len(result.findings)
        lines.append(f"\n[{result.analyzer_name}] {len(result.findings)} findings")

        for finding in result.findings:
            severity_marker = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(finding.severity, "•")
            location = f" ({finding.file}:{finding.line})" if finding.file else ""
            lines.append(f"  {severity_marker} [{finding.severity.upper()}] {finding.title}{location}")

    lines.insert(0, f"\nVillage Doctor Report: {total_findings} findings\n")
    return "\n".join(lines)


def interactive_select(results: list[AnalyzerResult]) -> list[Finding]:
    """Interactive selection of findings using questionary."""
    all_findings = []
    for result in results:
        all_findings.extend(result.findings)

    if not all_findings:
        questionary.print("No findings to select.")
        return []

    choices = []
    for f in all_findings:
        label = f"[{f.severity.upper()}] {f.title}"
        if f.file:
            label += f" ({f.file}"
            if f.line:
                label += f":{f.line}"
            label += ")"
        choices.append(questionary.Choice(title=label, value=f))

    selected = questionary.checkbox(
        "Select findings to create as tasks:", choices=choices, instruction="(Use space to select, enter to confirm)"
    ).ask()

    return selected or []


async def create_tasks_from_findings(
    findings: list[Finding],
    config: Config,
) -> dict[str, str]:
    """Create beads tasks from selected findings."""
    specs = []
    for finding in findings:
        spec = BeadsTaskSpec(
            title=finding.title,
            description=finding.description,
            estimate="unknown",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id=f"doctor-{finding.category}",
            parent_task_id=None,
            custom_fields={
                "category": finding.category,
                "severity": finding.severity,
                "file": finding.file or "",
                "line": str(finding.line) if finding.line else "",
            },
            bump="patch",
        )
        if finding.file:
            spec.description += f"\n\nFile: {finding.file}"
            if finding.line:
                spec.description += f":{finding.line}"
        specs.append(spec)

    return await create_draft_tasks(specs, config)
