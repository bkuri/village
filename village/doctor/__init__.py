"""Village Doctor - Project health diagnostics."""

from village.doctor.base import Analyzer, AnalyzerResult, Finding
from village.doctor.builtins.git import GitAnalyzer
from village.doctor.builtins.quality import QualityAnalyzer
from village.doctor.builtins.tests import TestAnalyzer
from village.doctor.report import (
    create_tasks_from_findings,
    format_report,
    interactive_select,
)
from village.doctor.runner import run_analyzers

__all__ = [
    "Analyzer",
    "AnalyzerResult",
    "Finding",
    "run_analyzers",
    "format_report",
    "interactive_select",
    "create_tasks_from_findings",
    "TestAnalyzer",
    "QualityAnalyzer",
    "GitAnalyzer",
]
