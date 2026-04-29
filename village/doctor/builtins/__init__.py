"""Built-in analyzers."""

from typing import Type

from village.doctor.base import Analyzer
from village.doctor.builtins.git import GitAnalyzer
from village.doctor.builtins.quality import QualityAnalyzer
from village.doctor.builtins.requirements import RequirementsAnalyzer
from village.doctor.builtins.tests import TestAnalyzer

BUILTIN_ANALYZERS: list[Type[Analyzer]] = [
    RequirementsAnalyzer,
    TestAnalyzer,
    QualityAnalyzer,
    GitAnalyzer,
]

__all__ = [
    "TestAnalyzer",
    "QualityAnalyzer",
    "GitAnalyzer",
    "RequirementsAnalyzer",
    "BUILTIN_ANALYZERS",
]
