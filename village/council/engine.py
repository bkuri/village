"""Council engine -- orchestrates multi-persona deliberations."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from village.config import CouncilConfig
from village.council.personas import Persona, PersonaLoader
from village.council.resolution import ResolutionResult, ResolutionStrategy, resolve_debate
from village.council.transcript import Transcript, TurnEntry, save_transcript


@dataclass
class MeetingState:
    council_id: str
    meeting_type: str
    topic: str
    personas: list[Persona] = field(default_factory=list)
    turns: list[TurnEntry] = field(default_factory=list)
    current_round: int = 0
    max_rounds: int = 3
    resolution_strategy: ResolutionStrategy = ResolutionStrategy.SYNTHESIS
    status: str = "pending"
    resolution: Optional[ResolutionResult] = None


class CouncilEngine:
    def __init__(
        self,
        config: CouncilConfig,
        personas_dir: Path | None = None,
        wiki_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.loader = PersonaLoader(personas_dir)
        self.wiki_dir = wiki_dir
        self._meetings: dict[str, MeetingState] = {}

    def start_meeting(
        self,
        topic: str,
        meeting_type: str | None = None,
        persona_names: list[str] | None = None,
        resolution_strategy: str | None = None,
    ) -> MeetingState:
        short_id = uuid.uuid4().hex[:8]
        council_id = f"council-{short_id}"

        mtype = meeting_type or self.config.default_type
        strategy_str = resolution_strategy or self.config.resolution_strategy
        strategy = ResolutionStrategy(strategy_str)

        personas: list[Persona] = []
        if persona_names:
            for name in persona_names:
                try:
                    personas.append(self.loader.load(name))
                except FileNotFoundError:
                    personas.append(self.loader.create_persona(name, ""))
        else:
            all_personas = self.loader.load_all()
            if all_personas:
                personas = all_personas[:2]
            else:
                personas = [
                    self.loader.create_persona("skeptic", "You are a skeptical thinker who questions assumptions."),
                    self.loader.create_persona(
                        "pragmatist", "You are a pragmatic thinker who focuses on practical solutions."
                    ),
                ]

        rounds = self.config.default_rounds if mtype == "debate" else 1

        state = MeetingState(
            council_id=council_id,
            meeting_type=mtype,
            topic=topic,
            personas=personas,
            max_rounds=rounds,
            resolution_strategy=strategy,
            status="active",
        )
        self._meetings[council_id] = state
        return state

    def run_round(
        self,
        state: MeetingState,
        persona_responses: dict[str, str] | None = None,
        wiki_context: str | None = None,
    ) -> list[TurnEntry]:
        if state.status != "active":
            return []

        if state.current_round >= state.max_rounds:
            state.status = "max_rounds_reached"
            return []

        turns: list[TurnEntry] = []
        now = datetime.now(timezone.utc)

        context_prefix = ""
        if wiki_context:
            context_prefix = f"\nWiki context:\n{wiki_context}\n\n"

        if persona_responses:
            for persona in state.personas:
                response = persona_responses.get(persona.name, "")
                if response:
                    turn = TurnEntry(
                        persona_name=persona.name,
                        content=context_prefix + response if context_prefix and state.current_round == 0 else response,
                        timestamp=now,
                    )
                    turns.append(turn)
                    state.turns.append(turn)
        else:
            for persona in state.personas:
                turn = TurnEntry(
                    persona_name=persona.name,
                    content=f"[{persona.name} perspective on: {state.topic}]",
                    timestamp=now,
                )
                turns.append(turn)
                state.turns.append(turn)

        state.current_round += 1

        if state.current_round >= state.max_rounds:
            state.status = "ready_for_resolution"

        return turns

    def resolve(self, state: MeetingState) -> ResolutionResult:
        persona_responses: dict[str, str] = {}
        for turn in state.turns:
            existing = persona_responses.get(turn.persona_name, "")
            if existing:
                persona_responses[turn.persona_name] = existing + "\n\n" + turn.content
            else:
                persona_responses[turn.persona_name] = turn.content

        result = resolve_debate(
            strategy=state.resolution_strategy,
            persona_responses=persona_responses,
            topic=state.topic,
        )

        state.resolution = result
        state.status = "resolved"
        return result

    def get_transcript(self, state: MeetingState) -> Transcript:
        return Transcript(
            council_id=state.council_id,
            meeting_type=state.meeting_type,
            topic=state.topic,
            turns=list(state.turns),
        )

    def save_and_close(self, state: MeetingState) -> Path | None:
        if self.wiki_dir is None:
            return None

        transcript = self.get_transcript(state)
        return save_transcript(transcript, self.wiki_dir)

    def get_meeting(self, council_id: str) -> MeetingState | None:
        return self._meetings.get(council_id)

    def list_meetings(self) -> list[MeetingState]:
        return list(self._meetings.values())
