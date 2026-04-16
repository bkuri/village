"""Role-based chat system with routing, skills, and greeting templates."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import click

from village.prompt import sync_prompt


class RoutingAction(str, Enum):
    ROUTE = "route"
    ADVISE = "advise"
    NONE = "none"


@dataclass
class RoutingConfig:
    route: list[str] = field(default_factory=list)
    advise: list[str] = field(default_factory=list)


@dataclass
class RoutingResult:
    action: RoutingAction
    target_role: str | None = None
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)


ROLE_ROUTING: dict[str, RoutingConfig] = {
    "planner": RoutingConfig(
        route=["builder"],
        advise=["council", "scribe"],
    ),
    "builder": RoutingConfig(
        route=["planner"],
        advise=["scribe", "council"],
    ),
    "scribe": RoutingConfig(
        route=["council"],
        advise=["planner", "builder"],
    ),
    "council": RoutingConfig(
        route=["scribe"],
        advise=["planner", "builder"],
    ),
    "doctor": RoutingConfig(
        route=["scribe"],
        advise=["scribe", "council"],
    ),
    "watcher": RoutingConfig(
        route=["scribe"],
        advise=["builder", "planner"],
    ),
    "greeter": RoutingConfig(
        route=["planner", "builder", "scribe", "council", "doctor", "watcher"],
        advise=[],
    ),
}


GREETING_TEMPLATES: dict[str, str] = {
    "planner": "What do you want to accomplish?",
    "builder": "Which workflow shall I run?",
    "scribe": "What do you want to know?",
    "council": "What shall we discuss?",
    "doctor": "What seems to be the problem?",
    "watcher": "What would you like to observe?",
    "greeter": "How can I help?",
}


@dataclass
class RoleSkill:
    name: str
    description: str


ROLE_SKILLS: dict[str, list[RoleSkill]] = {
    "planner": [
        RoleSkill("workflows", "List available workflows"),
        RoleSkill("show", "Display a workflow's steps"),
        RoleSkill("design", "Design a new workflow"),
        RoleSkill("refine", "Refine an existing workflow"),
    ],
    "builder": [
        RoleSkill("run", "Execute a workflow"),
        RoleSkill("status", "Check a run's status"),
    ],
    "scribe": [
        RoleSkill("see", "Ingest knowledge source"),
        RoleSkill("ask", "Query the knowledge base"),
        RoleSkill("curate", "Health check and regenerate"),
        RoleSkill("goals", "Show goal hierarchy"),
        RoleSkill("stats", "Show wiki statistics"),
        RoleSkill("ledger show", "View task audit trail"),
        RoleSkill("ledger list", "List tasks with traces"),
    ],
    "council": [
        RoleSkill("debate", "Start a debate"),
        RoleSkill("list", "List past councils"),
        RoleSkill("show", "View council transcript"),
        RoleSkill("rematch", "Re-run a council"),
    ],
    "doctor": [
        RoleSkill("check", "Run diagnostics"),
    ],
    "watcher": [
        RoleSkill("status", "Show village status"),
        RoleSkill("locks", "List locks"),
        RoleSkill("events", "Show recent events"),
        RoleSkill("dashboard", "Real-time dashboard"),
        RoleSkill("cleanup", "Remove stale locks and worktrees"),
        RoleSkill("unlock", "Unlock a task"),
        RoleSkill("monitor", "Watch wiki ingest for new files"),
        RoleSkill("ledger show", "View task audit trail"),
        RoleSkill("ledger list", "List tasks with traces"),
        RoleSkill("ready", "Check if village is ready for work"),
    ],
    "greeter": [
        RoleSkill("help", "General guidance and routing"),
    ],
}


class RoleChat:
    def __init__(
        self,
        role_name: str,
        llm_call_fn: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.role_name = role_name
        self._llm_call = llm_call_fn
        self._context = context or {}
        self._conversation: list[tuple[str, str]] = []
        self._routing = ROLE_ROUTING.get(role_name, RoutingConfig())
        self._skills = ROLE_SKILLS.get(role_name, [])
        self._greeting = GREETING_TEMPLATES.get(role_name, "How can I help?")

    @property
    def greeting(self) -> str:
        return self._greeting

    @property
    def skills(self) -> list[RoleSkill]:
        return self._skills

    @property
    def routing(self) -> RoutingConfig:
        return self._routing

    @property
    def context(self) -> dict[str, Any]:
        return self._context

    def get_system_prompt(self) -> str:
        skill_list = "\n".join(f"- {s.name}: {s.description}" for s in self._skills)
        route_list = ", ".join(self._routing.route) if self._routing.route else "none"
        advise_list = ", ".join(self._routing.advise) if self._routing.advise else "none"

        return (
            f"You are the Village {self.role_name.title()}. "
            f"Help the user with their request.\n\n"
            f"Available skills:\n{skill_list}\n\n"
            f"You can route to: {route_list}\n"
            f"You can suggest: {advise_list}\n\n"
            f"If the user's request is better handled by another role, "
            f"say [ROUTE:role_name] or [ADVISE:role_name] at the start of your response.\n"
            f"Otherwise, help directly or suggest a specific skill to use."
        )

    def run(self, user_input: str) -> str:
        self._conversation.append(("user", user_input))

        if self._llm_call:
            prompt = self.get_system_prompt()
            if self._conversation:
                history = "\n".join(
                    f"{'User' if role == 'user' else 'Assistant'}: {msg}" for role, msg in self._conversation
                )
                prompt = f"{prompt}\n\nConversation:\n{history}"
            result = self._llm_call(prompt)
            response = str(result)
        else:
            response = self._echo_response(user_input)

        self._conversation.append(("assistant", response))
        return response

    def _echo_response(self, user_input: str) -> str:
        return f"[{self.role_name}] Received: {user_input}"

    def detect_cross_role(self, response: str) -> RoutingResult | None:
        if response.startswith("[ROUTE:"):
            role = response.split("[ROUTE:")[1].split("]")[0].strip()
            if role in self._routing.route:
                return RoutingResult(
                    action=RoutingAction.ROUTE,
                    target_role=role,
                    message=response.split("]", 1)[1].strip() if "]" in response else "",
                    context=self._build_handoff_context(),
                )
        elif response.startswith("[ADVISE:"):
            role = response.split("[ADVISE:")[1].split("]")[0].strip()
            if role in self._routing.advise:
                return RoutingResult(
                    action=RoutingAction.ADVISE,
                    target_role=role,
                    message=response.split("]", 1)[1].strip() if "]" in response else "",
                    context=self._build_handoff_context(),
                )
        return None

    def _build_handoff_context(self) -> dict[str, Any]:
        summary = self._conversation[-3:] if len(self._conversation) > 3 else self._conversation
        return {
            "from_role": self.role_name,
            "conversation_summary": [(r, m) for r, m in summary],
            **self._context,
        }

    def can_route_to(self, role: str) -> bool:
        return role in self._routing.route

    def can_advise(self, role: str) -> bool:
        return role in self._routing.advise


def run_role_chat(
    role_name: str,
    llm_call_fn: Any | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    chat = RoleChat(role_name, llm_call_fn=llm_call_fn, context=context)
    click.echo(f"{chat.greeting}\n")

    while True:
        try:
            user_input = sync_prompt("", default="", show_default=False)
        except (click.exceptions.Abort, EOFError):
            click.echo("")
            break

        if not user_input or user_input.strip().lower() in ("/exit", "/quit"):
            break

        if user_input.strip().lower() == "/help":
            click.echo(f"Available: {', '.join(s.name for s in chat.skills)}")
            click.echo("/exit to quit, /help for commands\n")
            continue

        response = chat.run(user_input)

        routing = chat.detect_cross_role(response)
        if routing and routing.target_role:
            if routing.action == RoutingAction.ROUTE:
                click.echo(f"  ── Routing to {routing.target_role} ──────────")
                run_role_chat(routing.target_role, context=routing.context)
                break
            elif routing.action == RoutingAction.ADVISE:
                click.echo(f"  That sounds like a job for the {routing.target_role}.")
                confirm = sync_prompt("  Want me to start it? [Y/n]", default="Y")
                if confirm.strip().lower() in ("y", "yes", ""):
                    click.echo(f"  ── Routing to {routing.target_role} ──────────")
                    run_role_chat(routing.target_role, context=routing.context)
                    break
                else:
                    click.echo(f"  You can run: village {routing.target_role}\n")
        else:
            click.echo(f"  {response}\n")
