"""Resolution strategies for council debates."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ResolutionStrategy(Enum):
    SYNTHESIS = "synthesis"
    VOTE = "vote"
    ARBITER = "arbiter"


@dataclass
class ResolutionResult:
    winner: Optional[str] = None
    summary: str = ""
    reasoning: str = ""
    votes: dict[str, str] = field(default_factory=dict)


def resolve_debate(
    strategy: ResolutionStrategy,
    persona_responses: dict[str, str],
    topic: str,
    arbiter: Optional[str] = None,
) -> ResolutionResult:
    if strategy == ResolutionStrategy.SYNTHESIS:
        return _resolve_synthesis(persona_responses, topic)
    elif strategy == ResolutionStrategy.VOTE:
        return _resolve_vote(persona_responses, topic)
    elif strategy == ResolutionStrategy.ARBITER:
        return _resolve_arbiter(persona_responses, topic, arbiter)
    raise ValueError(f"Unknown resolution strategy: {strategy}")


def _resolve_synthesis(
    persona_responses: dict[str, str],
    topic: str,
) -> ResolutionResult:
    parts: list[str] = []
    for name, response in persona_responses.items():
        parts.append(f"**{name}**: {response.strip()}")

    summary = f"Synthesis on '{topic}':\n\n" + "\n\n".join(parts)
    reasoning = "Combined all persona perspectives into a unified overview."

    return ResolutionResult(
        summary=summary,
        reasoning=reasoning,
    )


def _resolve_vote(
    persona_responses: dict[str, str],
    topic: str,
) -> ResolutionResult:
    names = list(persona_responses.keys())
    votes: dict[str, str] = {}

    for i, voter in enumerate(names):
        candidates = [n for n in names if n != voter]
        vote_target = candidates[i % len(candidates)] if candidates else voter
        votes[voter] = vote_target

    tally: dict[str, int] = {}
    for target in votes.values():
        tally[target] = tally.get(target, 0) + 1

    winner = max(tally, key=lambda k: tally[k]) if tally else None

    vote_lines = [f"- {voter} voted for {target}" for voter, target in votes.items()]
    reasoning = "Vote tally:\n" + "\n".join(vote_lines)
    summary = f"'{winner}' received the most votes on '{topic}'." if winner else "No votes cast."

    return ResolutionResult(
        winner=winner,
        summary=summary,
        reasoning=reasoning,
        votes=votes,
    )


def _resolve_arbiter(
    persona_responses: dict[str, str],
    topic: str,
    arbiter: Optional[str] = None,
) -> ResolutionResult:
    names = list(persona_responses.keys())
    chosen_arbiter = arbiter or (names[-1] if names else "unknown")

    contributions: list[str] = []
    for name, response in persona_responses.items():
        if name != chosen_arbiter:
            contributions.append(f"- {name}: {response.strip()[:200]}")

    arbiter_response = persona_responses.get(chosen_arbiter, "")
    summary = f"Arbiter {chosen_arbiter} ruled on '{topic}':\n\n{arbiter_response.strip()}"
    reasoning = "Contributions considered:\n" + "\n".join(contributions) if contributions else "No other contributions."

    return ResolutionResult(
        winner=chosen_arbiter,
        summary=summary,
        reasoning=reasoning,
    )
