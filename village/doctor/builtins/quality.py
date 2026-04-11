"""Analyzer for code quality issues."""

import json
import subprocess

from village.doctor.base import Analyzer, AnalyzerResult, Finding
from village.logging import get_logger

logger = get_logger(__name__)


class QualityAnalyzer(Analyzer):
    """Detect code quality issues using ruff."""

    name = "quality"
    description = "Detect linting and code quality issues"
    category = "quality"

    def is_available(self) -> bool:
        """Check if ruff is available."""
        try:
            subprocess.run(["ruff", "--version"], capture_output=True)
            return True
        except FileNotFoundError:
            return False

    def run(self) -> AnalyzerResult:
        """Run ruff and parse results."""
        findings = []

        try:
            result = subprocess.run(
                ["ruff", "check", ".", "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return AnalyzerResult(
                analyzer_name=self.name,
                analyzer_description=self.description,
                findings=[],
                error="ruff check timed out",
            )
        except Exception as e:
            return AnalyzerResult(
                analyzer_name=self.name,
                analyzer_description=self.description,
                findings=[],
                error=str(e),
            )

        if result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
                for issue in issues[:50]:
                    severity = "high" if issue.get("fix") else "low"
                    findings.append(
                        Finding(
                            id=f"quality-{issue.get('code', 'UNK')}-{issue.get('location', {}).get('row', 0)}",
                            title=f"{issue.get('code', 'UNK')}: {issue.get('message', 'Unknown issue')}",
                            description=(
                                f"{issue.get('message', '')}\n\n"
                                f"Rule: {issue.get('code', 'unknown')}\n"
                                f"URL: {issue.get('url', 'N/A')}"
                            ),
                            severity=severity,
                            category="quality",
                            file=issue.get("location", {}).get("path"),
                            line=issue.get("location", {}).get("row"),
                            metadata=issue,
                        )
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse ruff output")

        return AnalyzerResult(
            analyzer_name=self.name,
            analyzer_description=self.description,
            findings=findings,
        )
