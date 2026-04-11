"""Onboard -- adaptive project onboarding for Village."""

from village.onboard.detector import ProjectInfo, detect_project
from village.onboard.generator import GenerationResult, Generator
from village.onboard.generator import InterviewResult as GenInterviewResult
from village.onboard.interview import InterviewEngine, InterviewResult
from village.onboard.scaffolds import ScaffoldTemplate, get_scaffold

__all__ = [
    "GenerationResult",
    "Generator",
    "GenInterviewResult",
    "InterviewEngine",
    "InterviewResult",
    "ProjectInfo",
    "ScaffoldTemplate",
    "detect_project",
    "get_scaffold",
]
