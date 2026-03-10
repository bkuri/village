"""Base analyzer class and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Finding:
    """A single finding from an analyzer."""

    id: str
    title: str
    description: str
    severity: str
    category: str
    file: str | None = None
    line: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class AnalyzerResult:
    """Result from running an analyzer."""

    analyzer_name: str
    analyzer_description: str
    findings: list[Finding]
    error: str | None = None


class Analyzer(ABC):
    """Base class for all analyzers."""

    name: str = ""
    description: str = ""
    category: str = ""

    @abstractmethod
    def run(self) -> AnalyzerResult:
        """Run the analyzer and return findings."""
        ...

    def is_available(self) -> bool:
        """Check if this analyzer can run (dependencies available)."""
        return True
