from dataclasses import dataclass, field


@dataclass
class InterviewResult:
    answers: dict[str, str] = field(default_factory=dict)
    project_summary: str = ""
    raw_transcript: list[tuple[str, str]] = field(default_factory=list)
    preamble: list[tuple[str, str]] = field(default_factory=list)
