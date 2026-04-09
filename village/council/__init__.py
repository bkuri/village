"""Council -- multi-persona deliberation system for Village."""

from village.council.engine import CouncilEngine, MeetingState
from village.council.personas import Persona, PersonaLoader
from village.council.resolution import ResolutionResult, ResolutionStrategy, resolve_debate
from village.council.transcript import Transcript, TurnEntry, format_transcript, save_transcript

__all__ = [
    "CouncilEngine",
    "MeetingState",
    "Persona",
    "PersonaLoader",
    "ResolutionResult",
    "ResolutionStrategy",
    "ResolutionResult",
    "Transcript",
    "TurnEntry",
    "format_transcript",
    "resolve_debate",
    "save_transcript",
]
