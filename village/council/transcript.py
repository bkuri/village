"""Transcript archival for council meetings."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TurnEntry:
    persona_name: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Transcript:
    council_id: str
    meeting_type: str
    topic: str
    turns: list[TurnEntry] = field(default_factory=list)
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def format_transcript(transcript: Transcript) -> str:
    lines: list[str] = [
        f"# Council Transcript: {transcript.council_id}",
        "",
        f"- **Type**: {transcript.meeting_type}",
        f"- **Topic**: {transcript.topic}",
        f"- **Created**: {transcript.created.isoformat()}",
        f"- **Turns**: {len(transcript.turns)}",
        "",
        "---",
        "",
    ]

    for i, turn in enumerate(transcript.turns, 1):
        ts = turn.timestamp.strftime("%H:%M:%S")
        lines.append(f"## Turn {i}: {turn.persona_name} [{ts}]")
        lines.append("")
        lines.append(turn.content)
        lines.append("")

    return "\n".join(lines)


def save_transcript(transcript: Transcript, wiki_dir: Path) -> Path:
    council_dir = wiki_dir / "councils" / transcript.council_id
    council_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = council_dir / "transcript.md"
    content = format_transcript(transcript)
    transcript_path.write_text(content, encoding="utf-8")

    return transcript_path
