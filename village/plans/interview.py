"""Reverse-prompting session for planner resume.

Loads draft + interview history as context. Session runs interactively
with LLM, saves interview.jsonl after each turn.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from village.plans.models import Plan


@dataclass
class InterviewTurn:
    """A single turn in the interview session."""

    turn_number: int
    role: str  # "user" or "agent"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InterviewSession:
    """An interview session for reverse-prompting."""

    plan_slug: str
    turns: list[InterviewTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_turn(self, role: str, content: str) -> None:
        self.turns.append(
            InterviewTurn(
                turn_number=len(self.turns) + 1,
                role=role,
                content=content,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_slug": self.plan_slug,
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "role": t.role,
                    "content": t.content,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in self.turns
            ],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterviewSession":
        session = cls(plan_slug=data["plan_slug"])
        session.created_at = datetime.fromisoformat(data["created_at"])
        for turn_data in data.get("turns", []):
            session.turns.append(
                InterviewTurn(
                    turn_number=turn_data["turn_number"],
                    role=turn_data["role"],
                    content=turn_data["content"],
                    timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                )
            )
        return session


def load_session(plan_dir: Path) -> InterviewSession | None:
    """Load existing interview session from plan directory."""
    import json

    session_file = plan_dir / "interview.jsonl"
    if not session_file.exists():
        return None

    with open(session_file) as f:
        data = json.loads(f.read())
    return InterviewSession.from_dict(data)


def save_session(plan_dir: Path, session: InterviewSession) -> None:
    """Save interview session to plan directory."""
    import json

    session_file = plan_dir / "interview.jsonl"
    session_file.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")


def _format_conversation(messages: list[dict[str, str]]) -> str:
    """Format conversation history as readable text for the LLM."""
    lines: list[str] = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = msg["role"].capitalize()
        lines.append(f"[{role}]: {msg['content']}")
    return "\n".join(lines)


def run_interview_session(
    plan: Plan,
    plan_dir: Path,
    llm_client: Any,
) -> None:
    """Run an interactive reverse-prompting session.

    Args:
        plan: The plan being edited
        plan_dir: Path to plan directory
        llm_client: LLM client for generating responses
    """
    session = load_session(plan_dir) or InterviewSession(plan_slug=plan.slug)

    system_prompt = f"""You are helping refine a plan with the following objective:

{plan.objective}

Current plan status:
- State: {plan.state.value}
- Tasks: {len(plan.task_ids)}

The user will ask questions or suggest changes. Respond helpfully and update the plan as needed.
"""

    messages: list[dict[str, str]] = []

    for turn in session.turns:
        if turn.role == "user":
            messages.append({"role": "user", "content": turn.content})
        else:
            messages.append({"role": "assistant", "content": turn.content})

    print(f"Resuming plan: {plan.slug}")
    print(f"Objective: {plan.objective}")
    print(f"Previous turns: {len(session.turns)}")
    print("\n(Type 'exit' to end the session)\n")

    from village.errors import GracefulExit
    from village.prompt import InterruptGuard

    guard = InterruptGuard()

    while True:
        try:
            user_input = input("You: ").strip()
        except EOFError:
            print("")
            break
        except KeyboardInterrupt:
            try:
                guard.check_interrupt()
            except GracefulExit:
                print("")
                break
            continue

        if user_input.lower() in ("exit", "quit"):
            break

        if not user_input:
            continue

        session.add_turn("user", user_input)
        messages.append({"role": "user", "content": user_input})

        # Format conversation for LLM call
        conversation_text = _format_conversation(messages)
        response = llm_client.call(
            prompt=conversation_text,
            system_prompt=system_prompt,
            max_tokens=1024,
        )

        session.add_turn("agent", response)
        messages.append({"role": "assistant", "content": response})

        save_session(plan_dir, session)
        print(f"\nAgent: {response}\n")
