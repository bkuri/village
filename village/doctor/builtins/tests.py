"""Analyzer for failing and skipped tests."""

import subprocess

from village.doctor.base import Analyzer, AnalyzerResult, Finding
from village.logging import get_logger
from village.probes.tools import run_command

logger = get_logger(__name__)


class TestAnalyzer(Analyzer):
    """Detect failing, skipped, and error tests."""

    name = "tests"
    description = "Detect failing, skipped, and error tests"
    category = "test"

    def is_available(self) -> bool:
        """Check if pytest is available."""
        try:
            run_command(["pytest", "--version"], capture=True, check=False)
            return True
        except FileNotFoundError:
            return False

    def run(self) -> AnalyzerResult:
        """Run pytest and parse results."""
        findings = []

        try:
            result = subprocess.run(
                ["pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return AnalyzerResult(
                analyzer_name=self.name,
                analyzer_description=self.description,
                findings=[],
                error="pytest collection timed out",
            )
        except Exception as e:
            return AnalyzerResult(
                analyzer_name=self.name,
                analyzer_description=self.description,
                findings=[],
                error=str(e),
            )

        for line in result.stdout.split("\n"):
            if "SKIPPED" in line:
                finding = self._parse_test_line(line, "SKIPPED")
                if finding:
                    findings.append(finding)

        try:
            result = subprocess.run(
                ["pytest", "-x", "--tb=no", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            for line in result.stdout.split("\n"):
                if "FAILED" in line:
                    finding = self._parse_test_line(line, "FAILED")
                    if finding:
                        findings.append(finding)
        except Exception as e:
            logger.warning(f"pytest run failed: {e}")

        return AnalyzerResult(
            analyzer_name=self.name,
            analyzer_description=self.description,
            findings=findings,
        )

    def _parse_test_line(self, line: str, status: str) -> Finding | None:
        """Parse a test output line into a Finding."""
        if status not in line:
            return None

        parts = line.split()
        test_name = None
        for part in parts:
            if "::" in part:
                test_name = part
                break

        if not test_name:
            return None

        file_path = test_name.split("::")[0] if "::" in test_name else None

        severity = "high" if status == "FAILED" else "medium"

        return Finding(
            id=f"test-{hash(test_name) % 10000:04d}",
            title=f"{status}: {test_name.split('::')[-1] if '::' in test_name else test_name}",
            description=f"Test {status.lower()}: {test_name}\n\nRun `pytest {test_name}` to reproduce.",
            severity=severity,
            category="test",
            file=file_path,
            metadata={"test_name": test_name, "status": status},
        )
